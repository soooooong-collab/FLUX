"""
Presentation Designer Agent — 컨셉워드 도출 + 슬라이드 구조 생성.

2단계 LLM 호출:
  1) _derive_concept_word: 8단계 결과에서 컨셉워드 도출
  2) _generate_concept_slides: 컨셉워드 + 결과물로 7-Phase 슬라이드 생성
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.services.llm.base import LLMResponse
from app.services.llm.router import get_llm_for_step
from app.agents.prompt_loader import load_agent_prompt

logger = logging.getLogger(__name__)

STEP_LABELS = {
    "s1": "Campaign Goal",
    "s2": "Market Analysis",
    "s3": "Target Insight",
    "s4": "Principle Competition",
    "s5": "Target Definition",
    "s6": "Winning Strategy",
    "s7": "Consumer Promise",
    "s8": "Creative Strategy",
}


async def generate_slides(
    brand_name: str,
    all_step_outputs: dict[str, str],
) -> list[dict]:
    """Generate slide structure from all step outputs via concept word derivation."""

    # Step 1: 컨셉워드 도출
    concept_data = await _derive_concept_word(brand_name, all_step_outputs)
    logger.info("Concept word derived: %s", concept_data.get("concept_word", "N/A"))

    # Step 2: 컨셉워드 기반 슬라이드 생성
    slides = await _generate_concept_slides(brand_name, all_step_outputs, concept_data)
    return slides


# ──────────────────────────────────────────────
# Step 1: 컨셉워드 도출
# ──────────────────────────────────────────────

_CONCEPT_DERIVATION_PROMPT = """\
당신은 브랜드 전략 전문가입니다. 아래 5개 단계의 분석 결과를 종합하여, 브랜드/캠페인의 본질을 담은 하나의 컨셉워드를 도출해주세요.

## 도출 프로세스

1. s3(Target Insight) + s5(Target Definition)에서 소비자의 핵심 tension을 한 문장으로 포착
2. s6(Winning Strategy)에서 기존 관점(Before)과 새로운 관점(After) 대비
3. s7(Consumer Promise) + s8(Creative Strategy)에서 브랜드 가치의 본질 압축
4. 위 세 요소의 교차점에서 3~5단어의 컨셉워드 확정

## 출력 형식 (JSON)

반드시 유효한 JSON 객체만 출력하세요:

```json
{
  "concept_word": "컨셉워드 (한국어, 3~5단어)",
  "concept_word_en": "Concept Word (English)",
  "derivation_logic": "도출 근거 요약 (2~3문장)",
  "brand_story": ["시적 내러티브 문장 1", "시적 내러티브 문장 2 (선택)"],
  "golden_circle": {
    "why": "브랜드의 존재이유",
    "how": "차별화 방법",
    "what": "제공하는 것"
  },
  "before_after": {
    "before": ["기존 관점/인식 항목1", "항목2", "항목3"],
    "after": ["새로운 관점/인식 항목1", "항목2", "항목3"]
  },
  "value_flow": ["핵심인사이트", "전략방향", "브랜드본질", "컨셉워드"]
}
```
"""


async def _derive_concept_word(
    brand_name: str,
    all_step_outputs: dict[str, str],
) -> dict:
    """Derive concept word from key step outputs."""

    # Collect relevant steps
    relevant_steps = {}
    for key in ["s3", "s5", "s6", "s7", "s8"]:
        if key in all_step_outputs:
            relevant_steps[key] = all_step_outputs[key]

    steps_text = ""
    for key in ["s3", "s5", "s6", "s7", "s8"]:
        if key in relevant_steps:
            steps_text += f"\n## Step {key[-1]}: {STEP_LABELS.get(key, key)}\n{relevant_steps[key]}\n"

    user_message = (
        f"브랜드: {brand_name}\n\n"
        f"아래 분석 결과에서 컨셉워드를 도출해주세요.\n\n"
        f"{steps_text}\n\n"
        f"반드시 유효한 JSON 객체만 출력하세요."
    )

    llm = get_llm_for_step("slides")
    response: LLMResponse = await llm.generate(
        messages=[{"role": "user", "content": user_message}],
        system=_CONCEPT_DERIVATION_PROMPT,
        temperature=0.6,
        max_tokens=4096,
    )

    text = response.text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        concept_data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse concept word JSON, using fallback")
        concept_data = _fallback_concept_data(brand_name)

    return concept_data


def _fallback_concept_data(brand_name: str) -> dict:
    return {
        "concept_word": f"{brand_name}의 새로운 가치",
        "concept_word_en": f"New Value of {brand_name}",
        "derivation_logic": "파이프라인 분석 결과를 종합하여 도출된 컨셉워드입니다.",
        "brand_story": [f"{brand_name}이 제안하는 새로운 가치의 시작."],
        "golden_circle": {
            "why": "소비자의 미충족 니즈 해결",
            "how": "차별화된 브랜드 경험",
            "what": "핵심 가치 전달",
        },
        "before_after": {
            "before": ["기존 관점"],
            "after": ["새로운 관점"],
        },
        "value_flow": ["인사이트", "전략방향", "브랜드본질", "컨셉워드"],
    }


# ──────────────────────────────────────────────
# Step 2: 컨셉워드 기반 슬라이드 생성
# ──────────────────────────────────────────────

async def _generate_concept_slides(
    brand_name: str,
    all_step_outputs: dict[str, str],
    concept_data: dict,
) -> list[dict]:
    """Generate 7-Phase slide JSON using concept word and step outputs."""

    system_prompt = load_agent_prompt("presentation_designer")

    # Build context from all 8 steps
    steps_text = ""
    for key in ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]:
        if key in all_step_outputs:
            steps_text += f"\n## Step {key[-1]}: {STEP_LABELS.get(key, key)}\n{all_step_outputs[key]}\n"

    # Build concept word context
    concept_context = json.dumps(concept_data, ensure_ascii=False, indent=2)

    user_message = (
        f"브랜드: {brand_name}\n\n"
        f"## 도출된 컨셉워드 데이터\n```json\n{concept_context}\n```\n\n"
        f"## 8단계 분석 결과\n{steps_text}\n\n"
        f"위 컨셉워드와 분석 결과를 바탕으로 7-Phase 슬라이드 구조를 JSON 배열로 생성해주세요.\n\n"
        f"## 사용 가능한 slide_pattern\n"
        f"- cover: 대형 중앙 텍스트 (표지)\n"
        f"- statement: 임팩트 한 문장, **하이라이트** 지원 (섹션 오프너, 전환점)\n"
        f"- title_body: 제목 + 본문 (분석 내용, 데이터)\n"
        f"- quote: 이미지 배경 + 인용문 (소비자 목소리)\n"
        f"- comparison: 좌우 대비 구조 (Before/After)\n"
        f"- diagram: 흐름도/구조도 (전략, Golden Circle)\n"
        f"- narrative: 시적 내러티브, **하이라이트** 지원 (브랜드 스토리)\n"
        f"- reveal: 초대형 영문 텍스트 (영문 컨셉워드)\n"
        f"- reveal_kr: 초대형 한국어 텍스트 (한국어 컨셉워드)\n\n"
        f"## 규칙\n"
        f"- Executive Summary 슬라이드를 절대 생성하지 마세요\n"
        f"- 총 슬라이드 수: 20~25장 (25장 초과 금지)\n"
        f"- Phase 5 감성적 내러티브: 최대 2장\n"
        f"- Phase 7 컨셉 활성화: 최대 2장\n"
        f"- 연속 3장 이상 같은 slide_pattern 사용 금지\n"
        f"- 컨셉워드 '{concept_data.get('concept_word', '')}' 가 Phase 6에서 reveal + reveal_kr로 공개되어야 합니다\n"
        f"- Golden Circle, Before/After, Value Flow 데이터를 해당 슬라이드에 반영하세요\n"
        f"- compare, flow_items, quote 등 패턴별 필수 필드를 반드시 포함하세요\n"
        f"- 헤드라인은 파이프라인 스텝명이 아닌 전략적 카피로 작성하세요\n"
        f"- 각 슬라이드에 반드시 slide_pattern 필드를 포함하세요 (layout 아님)\n\n"
        f"반드시 유효한 JSON 배열만 출력하세요."
    )

    llm = get_llm_for_step("slides")
    response: LLMResponse = await llm.generate(
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        temperature=0.5,
        max_tokens=24576,
    )

    text = response.text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        slides = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse concept slides JSON, using fallback")
        slides = _fallback_slides(brand_name, all_step_outputs, concept_data)

    return slides


# ──────────────────────────────────────────────
# Fallback slide generation
# ──────────────────────────────────────────────

def _fallback_slides(
    brand_name: str,
    outputs: dict[str, str],
    concept_data: dict,
) -> list[dict]:
    """Generate basic concept-derivation slide structure when JSON parsing fails."""

    concept_word = concept_data.get("concept_word", f"{brand_name} 캠페인")
    golden_circle = concept_data.get("golden_circle", {"why": "", "how": "", "what": ""})
    before_after = concept_data.get("before_after", {"before": [], "after": []})
    brand_story = concept_data.get("brand_story", [])
    value_flow = concept_data.get("value_flow", [])

    slides: list[dict] = []

    # Phase 1: Cover
    slides.append({
        "step_key": "cover", "phase": "cover",
        "title": f"{brand_name} Campaign Strategy",
        "subtitle": concept_word,
        "slide_pattern": "cover",
    })

    # Phase 2: 현황 분석
    slides.append({
        "step_key": "phase2_opener", "phase": "phase2",
        "title": "왜 **변해야** 하는가",
        "slide_pattern": "statement",
    })

    step_info_phase2 = [
        ("s1", "phase2", "캠페인이 해결해야 할 과제"),
        ("s2", "phase2", "시장은 이미 움직이고 있다"),
        ("s4", "phase2", "진짜 경쟁은 어디에 있는가"),
    ]
    for key, phase, title in step_info_phase2:
        if key in outputs:
            slides.append({
                "step_key": key, "phase": phase,
                "title": title,
                "body": outputs[key][:2000],
                "slide_pattern": "title_body",
            })

    # Phase 3: 인사이트 & 타겟
    slides.append({
        "step_key": "phase3_opener", "phase": "phase3",
        "title": "**누구의** 마음을 움직여야 하는가",
        "slide_pattern": "statement",
    })

    if "s3" in outputs:
        slides.append({
            "step_key": "s3", "phase": "phase3",
            "quote": outputs["s3"][:500],
            "quote_source": "소비자 분석",
            "slide_pattern": "quote",
        })
    if "s5" in outputs:
        slides.append({
            "step_key": "s5", "phase": "phase3",
            "title": "타겟의 재정의",
            "compare": before_after if before_after.get("before") else {"before": ["기존 타겟"], "after": ["재정의 타겟"]},
            "slide_pattern": "comparison",
        })

    # Phase 4: 전략 방향 전환
    slides.append({
        "step_key": "s6_compare", "phase": "phase4",
        "title": "관점의 전환",
        "compare": before_after,
        "slide_pattern": "comparison",
    })

    if "s6" in outputs:
        slides.append({
            "step_key": "s6", "phase": "phase4",
            "title": "전략의 흐름",
            "flow_items": value_flow if value_flow else ["분석", "인사이트", "전략", "실행"],
            "slide_pattern": "diagram",
        })

    # Phase 5: 브랜드 스토리텔링
    for story_line in brand_story[:2]:
        slides.append({
            "step_key": "brand_story", "phase": "story",
            "body": story_line,
            "slide_pattern": "narrative",
        })

    # Phase 6: 컨셉워드 결정화
    concept_word_en = concept_data.get("concept_word_en", concept_word)
    slides.append({
        "step_key": "concept_reveal", "phase": "concept",
        "concept_word": concept_word_en,
        "slide_pattern": "reveal",
    })
    slides.append({
        "step_key": "concept_reveal_kr", "phase": "concept",
        "concept_word": concept_word,
        "slide_pattern": "reveal_kr",
    })
    if value_flow:
        slides.append({
            "step_key": "golden_circle", "phase": "concept",
            "title": "Golden Circle",
            "flow_items": [
                f"WHY: {golden_circle.get('why', '')}",
                f"HOW: {golden_circle.get('how', '')}",
                f"WHAT: {golden_circle.get('what', '')}",
            ],
            "slide_pattern": "diagram",
        })

    # Phase 7: 컨셉 활성화
    if "s7" in outputs or "s8" in outputs:
        combined = ""
        if "s7" in outputs:
            combined += outputs["s7"][:1000]
        if "s8" in outputs:
            combined += "\n\n" + outputs["s8"][:1000]
        slides.append({
            "step_key": "activation", "phase": "activation",
            "title": "이렇게 실현합니다",
            "body": combined,
            "slide_pattern": "title_body",
        })

    return slides
