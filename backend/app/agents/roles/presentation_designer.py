"""
Presentation Designer Agent — 슬라이드 구조 생성.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.services.llm.base import LLMResponse
from app.services.llm.router import get_llm_for_step
from app.agents.prompt_loader import load_agent_prompt


async def generate_slides(
    brand_name: str,
    all_step_outputs: dict[str, str],
) -> list[dict]:
    """Generate slide structure from all step outputs."""
    system_prompt = load_agent_prompt("presentation_designer")

    # Build full context
    steps_text = ""
    step_labels = {
        "s1": "Campaign Goal",
        "s2": "Market Analysis",
        "s3": "Target Insight",
        "s4": "Principle Competition",
        "s5": "Target Definition",
        "s6": "Winning Strategy",
        "s7": "Consumer Promise",
        "s8": "Creative Strategy",
    }
    for key in ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]:
        if key in all_step_outputs:
            steps_text += f"\n## Step {key[-1]}: {step_labels.get(key, key)}\n{all_step_outputs[key]}\n"

    user_message = (
        f"브랜드: {brand_name}\n\n"
        f"아래 8단계 분석 결과를 바탕으로 C-Level 피치 수준의 슬라이드 구조를 "
        f"JSON 배열로 생성해주세요.\n\n"
        f"{steps_text}\n\n"
        f"반드시 유효한 JSON 배열만 출력하세요. 각 슬라이드는 "
        f'{{ "step_key", "phase", "title", "subtitle", "body", "layout", "key_points" }} 형식입니다.'
    )

    llm = get_llm_for_step("slides")
    response: LLMResponse = await llm.generate(
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        temperature=0.5,
        max_tokens=16384,
    )

    # Parse JSON from response
    text = response.text.strip()
    # Handle markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        slides = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: generate basic slides from outputs
        slides = _fallback_slides(brand_name, all_step_outputs)

    return slides


def _fallback_slides(brand_name: str, outputs: dict[str, str]) -> list[dict]:
    """Generate basic slide structure when JSON parsing fails."""
    step_info = [
        ("s1", "phase1", "Campaign Goal", "캠페인의 궁극적 목표"),
        ("s2", "phase1", "Market Analysis", "시장 맥락 분석"),
        ("s3", "phase1", "Target Insight", "소비자 인사이트"),
        ("s4", "phase2", "Principle Competition", "진짜 경쟁자"),
        ("s5", "phase2", "Target Definition", "타겟 재정의"),
        ("s6", "phase2", "Winning Strategy", "승리 전략"),
        ("s7", "phase3", "Consumer Promise", "소비자 약속"),
        ("s8", "phase3", "Creative Strategy", "크리에이티브 전략"),
    ]
    slides = [
        {
            "step_key": "cover",
            "phase": "cover",
            "title": f"{brand_name} Campaign Strategy",
            "subtitle": "Powered by FLUX",
            "body": "",
            "layout": "title_content",
            "key_points": None,
        }
    ]
    for key, phase, title, subtitle in step_info:
        if key in outputs:
            slides.append({
                "step_key": key,
                "phase": phase,
                "title": title,
                "subtitle": subtitle,
                "body": outputs[key][:2000],
                "layout": "title_content",
                "key_points": None,
            })
    return slides
