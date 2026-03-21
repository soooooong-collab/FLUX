"""
Meeting Slide Designer Agent — 회의 결론을 슬라이드 JSON으로 변환.

1단계 LLM 호출:
  extract_conclusions() 결과 → distill prompt → 10장 slides.json (브랜드 컬러 포함)
"""
from __future__ import annotations

import json
import logging

from app.services.llm.base import LLMResponse
from app.services.llm.router import get_llm_for_step
from app.agents.prompt_loader import load_agent_prompt
from app.services.meeting_extract import build_distill_input

logger = logging.getLogger(__name__)


async def generate_meeting_slides(
    brand_name: str,
    extracted_conclusions: dict,
) -> dict:
    """
    회의 결론 데이터를 10장 슬라이드 JSON으로 변환.

    Args:
        brand_name: 브랜드명
        extracted_conclusions: extract_conclusions()의 반환값

    Returns:
        {"meta": {..., "brand_colors": {...}}, "slides": [...]}
    """
    system_prompt = load_agent_prompt("meeting_slide_designer")

    meta = extracted_conclusions["meta"]
    sections = extracted_conclusions["sections"]

    user_message = build_distill_input(meta, sections)
    user_message += (
        "\n## 출력 형식\n"
        "위 섹션별 최종 결론을 광고전략 제안서 프레젠테이션 슬라이드용 JSON으로 구조화해주세요.\n"
        "JSON만 출력하고 다른 텍스트는 포함하지 마세요.\n"
    )

    llm = get_llm_for_step("meeting_slides")
    response: LLMResponse = await llm.generate(
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        temperature=0.5,
        max_tokens=8192,
    )

    text = response.text.strip()
    # Strip markdown code fence if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(
            lines[1:-1] if lines[-1].startswith("```") else lines[1:]
        )

    try:
        slides_data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse meeting slides JSON, using fallback")
        slides_data = _fallback_slides(brand_name, meta, sections)

    # Ensure brand_colors exists
    if "meta" not in slides_data:
        slides_data["meta"] = meta
    if "brand_colors" not in slides_data.get("meta", {}):
        slides_data["meta"]["brand_colors"] = {
            "primary": "#990011",
            "secondary": "#FCF6F5",
            "accent": "#2F3C7E",
        }

    return slides_data


def _fallback_slides(
    brand_name: str,
    meta: dict,
    sections: list,
) -> dict:
    """JSON 파싱 실패 시 기본 구조 생성."""
    slides = []

    # Cover
    slides.append({
        "slide_number": 1,
        "type": "cover",
        "label": "ADVERTISING STRATEGY PROPOSAL",
        "title": brand_name,
        "title_accent": "광고전략 제안서",
        "subtitle_line1": "FLUX AI 전략 시스템 회의 결론 보고서",
        "subtitle_line2": "",
    })

    # Content slides (one per section)
    for i, section in enumerate(sections):
        slide = {
            "slide_number": i + 2,
            "section_id": section["section_id"],
            "type": "pillars_3col",
            "section_title": section["section_name"],
            "page_label": f"{i + 2:02d} / 10",
            "core_label": f"CORE {section['section_name'].upper().split()[0]}",
            "headline": (section.get("premise") or section["conclusion_text"])[:15],
            "sub_headline": (section.get("premise") or "")[:40],
        }

        # Build pillars from evidence
        pillars = []
        for j, ev in enumerate(section.get("evidence", [])[:3]):
            pillars.append({
                "number": f"{j + 1:02d}",
                "title_ko": ev["title"][:8],
                "tag_line": ev["title"],
                "description": ev["content"][:40],
            })

        if not pillars:
            # No structured evidence — create single pillar from conclusion
            text = section["conclusion_text"][:120]
            pillars.append({
                "number": "01",
                "title_ko": "핵심 결론",
                "tag_line": section["section_name"],
                "description": text[:40],
            })

        slide["pillars"] = pillars
        slides.append(slide)

    # Closing
    slides.append({
        "slide_number": len(sections) + 2,
        "type": "closing",
        "closing_headline": "전략의 방향은",
        "closing_accent": brand_name,
        "sub_message": "경청해 주셔서 감사합니다.",
        "next_steps": [
            {"step": 1, "title": "크리에이티브 개발", "description": "컨셉 구체화", "timeline": "D+7일 이내"},
            {"step": 2, "title": "미디어 플래닝", "description": "채널 전략 수립", "timeline": "D+14일 이내"},
            {"step": 3, "title": "프로덕션", "description": "제작 착수", "timeline": "D+21일 이내"},
        ],
        "contact": {"email": "", "phone": ""},
    })

    return {
        "meta": {
            **meta,
            "campaign_tagline": f"{brand_name} 광고전략 제안",
            "brand_colors": {
                "primary": "#990011",
                "secondary": "#FCF6F5",
                "accent": "#2F3C7E",
            },
        },
        "slides": slides,
    }
