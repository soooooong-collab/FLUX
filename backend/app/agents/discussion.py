"""
Discussion Engine — 팀 토론 기반 파이프라인 실행.

각 스텝(s1~s8)마다 구조화된 토론을 실행합니다:
  Turn 1: 오케스트레이터 프레이밍 (디렉터 성격 반영)
  Turn 2: 리드 에이전트 분석 (기존 run_step 재사용)
  Turn 3+: 서포트 에이전트 반응 (보강/도전/확장)
  Final: 오케스트레이터 종합 (최종 output_text)
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, AsyncGenerator

import yaml

from app.agents.prompt_loader import load_agent_prompt
from app.agents.roles import account_planner, brand_strategist, creative_director
from app.services.llm.router import get_llm_for_step

logger = logging.getLogger(__name__)

_POLICY_DIR = Path(__file__).parent / "policies"

# ── 스텝별 참여 매트릭스 ──

STEP_PARTICIPANTS: dict[str, dict[str, Any]] = {
    "s1": {"lead": "account_planner", "support": ["brand_strategist"]},
    "s2": {"lead": "account_planner", "support": ["brand_strategist", "creative_director"]},
    "s3": {"lead": "account_planner", "support": ["creative_director"]},
    "s4": {"lead": "brand_strategist", "support": ["account_planner"]},
    "s5": {"lead": "brand_strategist", "support": ["account_planner", "creative_director"]},
    "s6": {"lead": "brand_strategist", "support": ["creative_director"]},
    "s7": {"lead": "creative_director", "support": ["brand_strategist"]},
    "s8": {"lead": "creative_director", "support": ["brand_strategist", "account_planner"]},
}

STEP_QUESTIONS = {
    "s1": "광고를 통해 얻고자 하는 궁극적인 목표는 무엇인가?",
    "s2": "시장은 왜 그렇게 흘러가고 있는가?",
    "s3": "소비자는 왜 그런 행동을 하고 있는가?",
    "s4": "진짜 경쟁자는 어떤 인식인가?",
    "s5": "그런 인식을 가지고 있는 소비자를 무엇이라 표현할 것인가?",
    "s6": "그런 소비자의 인식을 어떻게 바꿔줄 것인가?",
    "s7": "우리 브랜드가 왜 그렇게 바꿔줄 수 있는가?",
    "s8": "어떻게 이를 이슈화 시킬 것인가?",
}

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

ROLE_LABELS = {
    "account_planner": "Account Planner",
    "brand_strategist": "Brand Strategist",
    "creative_director": "Creative Director",
    "orchestrator": "Chief Director",
}

ROLE_LABELS_KR = {
    "account_planner": "AP (현상 분석가)",
    "brand_strategist": "BS (전략 기획자)",
    "creative_director": "CD (크리에이티브 디렉터)",
    "orchestrator": "팀장",
}


def load_director_persona(director_type: str) -> dict[str, Any]:
    """Load director persona from YAML including discussion style fields."""
    path = _POLICY_DIR / "director_personas.yaml"
    if not path.exists():
        return {"label": "The Strategist", "style": "hypothesis-driven",
                "framing_style": "", "moderation_style": "", "synthesis_style": ""}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    persona = data.get(director_type, data.get("strategist", {}))
    return persona


async def run_discussion(
    step_key: str,
    brief_context: str,
    previous_outputs: dict[str, str],
    director_persona: dict[str, Any],
    db: Any,
    method_refs: list[dict] | None = None,
    case_refs: list[dict] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Execute a structured team discussion for a single step.
    Yields discussion turn dicts for SSE streaming.
    """
    participants = STEP_PARTICIPANTS[step_key]
    lead_role = participants["lead"]
    support_roles = participants["support"]
    total_turns = 2 + len(support_roles) + 1  # framing + lead + supports + synthesis

    # ── Turn 1: 오케스트레이터 프레이밍 ──
    framing = await _orchestrator_frame(
        step_key, brief_context, previous_outputs, director_persona,
    )
    yield _turn(
        turn_number=1,
        speaker="orchestrator",
        role="moderator",
        content=framing,
        turn_type="framing",
        step_key=step_key,
        total_turns=total_turns,
    )

    # ── Turn 2: 리드 에이전트 분석 (기존 run_step 재사용) ──
    lead_result = await _run_lead_agent(
        lead_role, step_key, brief_context, previous_outputs,
        db, method_refs, case_refs,
    )
    lead_text = _normalize_turn_text(
        lead_result.get("output_text", ""),
        f"[{ROLE_LABELS_KR.get(lead_role, lead_role)}] 응답이 비어 있어 핵심 결론만 이어갑니다.",
    )
    yield _turn(
        turn_number=2,
        speaker=lead_role,
        role="lead",
        content=lead_text,
        turn_type="analysis",
        step_key=step_key,
        total_turns=total_turns,
    )

    # ── Turn 3+: 서포트 에이전트 반응 ──
    # 서포트가 2명이면 병렬 실행
    if len(support_roles) > 1:
        support_tasks = [
            _support_react(
                support_role, step_key, brief_context, previous_outputs,
                framing, lead_text, lead_role, [],
            )
            for support_role in support_roles
        ]
        support_responses = await asyncio.gather(*support_tasks)
        for i, (support_role, response) in enumerate(zip(support_roles, support_responses)):
            yield _turn(
                turn_number=3 + i,
                speaker=support_role,
                role="support",
                content=response,
                turn_type="reaction",
                step_key=step_key,
                total_turns=total_turns,
            )
    else:
        support_responses = []
        for i, support_role in enumerate(support_roles):
            response = await _support_react(
                support_role, step_key, brief_context, previous_outputs,
                framing, lead_text, lead_role, support_responses,
            )
            support_responses.append(response)
            yield _turn(
                turn_number=3 + i,
                speaker=support_role,
                role="support",
                content=response,
                turn_type="reaction",
                step_key=step_key,
                total_turns=total_turns,
            )

    # support_responses를 list로 통일
    if not isinstance(support_responses, list):
        support_responses = list(support_responses)

    # ── Final Turn: 오케스트레이터 종합 ──
    synthesis = await _orchestrator_synthesize(
        step_key, brief_context, previous_outputs, director_persona,
        framing, lead_role, lead_text,
        list(zip(support_roles, support_responses if isinstance(support_responses[0], str) else support_responses)),
        method_refs, case_refs,
    )
    yield _turn(
        turn_number=total_turns,
        speaker="orchestrator",
        role="moderator",
        content=synthesis,
        turn_type="synthesis",
        step_key=step_key,
        total_turns=total_turns,
    )

    # Store evidence refs from lead result for orchestrator
    yield _turn(
        turn_number=-1,  # meta turn, not displayed
        speaker="_meta",
        role="meta",
        content="",
        turn_type="meta",
        step_key=step_key,
        total_turns=total_turns,
        extra={
            "evidence_refs": lead_result.get("evidence_refs", []),
            "tokens_used": lead_result.get("tokens_used", 0),
            "model_used": lead_result.get("model_used", ""),
        },
    )


# ── Internal helpers ──


def _turn(
    turn_number: int,
    speaker: str,
    role: str,
    content: str,
    turn_type: str,
    step_key: str,
    total_turns: int,
    extra: dict | None = None,
) -> dict[str, Any]:
    """Build a discussion turn dict."""
    result = {
        "turn_number": turn_number,
        "speaker": speaker,
        "speaker_label": ROLE_LABELS.get(speaker, speaker),
        "speaker_label_kr": ROLE_LABELS_KR.get(speaker, speaker),
        "role": role,
        "content": content,
        "type": turn_type,
        "step_key": step_key,
        "total_turns": total_turns,
    }
    if extra:
        result["extra"] = extra
    return result


def _normalize_turn_text(text: str, fallback: str) -> str:
    cleaned = (text or "").strip()
    return cleaned if cleaned else fallback


def _format_previous_outputs(previous_outputs: dict[str, str]) -> str:
    """Format previous step outputs for prompt context."""
    if not previous_outputs:
        return ""
    parts = []
    for k, v in previous_outputs.items():
        label = STEP_LABELS.get(k, k)
        # Truncate long outputs to save tokens
        text = v[:1500] if len(v) > 1500 else v
        parts.append(f"### {k}: {label}\n{text}")
    return "\n\n".join(parts)


async def _orchestrator_frame(
    step_key: str,
    brief_context: str,
    previous_outputs: dict[str, str],
    director_persona: dict[str, Any],
) -> str:
    """Generate the orchestrator's framing question for a step."""
    system_prompt = load_agent_prompt("chief_director")

    persona_label = director_persona.get("label", "The Strategist")
    persona_style = director_persona.get("style", "hypothesis-driven")
    framing_style = director_persona.get("framing_style", "")
    moderation_style = director_persona.get("moderation_style", "")

    system_with_persona = (
        f"{system_prompt}\n\n"
        f"---\n\n"
        f"## 현재 디렉터 페르소나: {persona_label}\n"
        f"- 스타일: {persona_style}\n"
        f"- 프레이밍 스타일:\n{framing_style}\n"
        f"- 모더레이션 스타일:\n{moderation_style}\n"
    )

    prev_text = _format_previous_outputs(previous_outputs)
    question = STEP_QUESTIONS.get(step_key, "")
    step_label = STEP_LABELS.get(step_key, step_key)

    user_message = (
        f"지금은 [{step_label}] 단계의 팀 토론을 시작합니다.\n"
        f"이 단계의 핵심 질문: \"{question}\"\n\n"
        f"## 클라이언트 브리프\n{brief_context[:1000]}\n\n"
    )
    if prev_text:
        user_message += f"## 이전 단계 결과\n{prev_text}\n\n"

    user_message += (
        f"당신은 [{persona_label}] 스타일의 팀장입니다.\n"
        f"위 맥락을 바탕으로, 팀원들에게 이 단계의 논의를 시작할 프레이밍 질문을 제시하세요.\n"
        f"당신의 스타일({persona_style})로 3~5문장으로 간결하게 작성하세요.\n"
        f"팀원들이 깊이 있는 분석을 시작할 수 있도록 방향을 제시하되, 답을 제시하지 마세요."
    )

    llm = get_llm_for_step("orchestrator")
    response = await llm.generate(
        messages=[{"role": "user", "content": user_message}],
        system=system_with_persona,
        temperature=0.7,
        max_tokens=500,
    )
    return _normalize_turn_text(
        response.text,
        "핵심 쟁점을 정리해 토론을 이어가겠습니다. 브랜드 목표와 타겟 반응의 인과를 중심으로 의견을 주세요.",
    )


async def _run_lead_agent(
    lead_role: str,
    step_key: str,
    brief_context: str,
    previous_outputs: dict[str, str],
    db: Any,
    method_refs: list[dict] | None = None,
    case_refs: list[dict] | None = None,
) -> dict:
    """Run the lead agent using existing run_step functions."""
    if lead_role == "account_planner":
        return await account_planner.run_step(
            step_key=step_key,
            brief_context=brief_context,
            previous_outputs=previous_outputs,
        )
    elif lead_role == "brand_strategist":
        return await brand_strategist.run_step(
            step_key=step_key,
            brief_context=brief_context,
            previous_outputs=previous_outputs,
            db=db,
            case_refs=case_refs,
            method_refs=method_refs,
        )
    elif lead_role == "creative_director":
        return await creative_director.run_step(
            step_key=step_key,
            brief_context=brief_context,
            previous_outputs=previous_outputs,
            db=db,
            case_refs=case_refs,
        )
    else:
        raise ValueError(f"Unknown lead role: {lead_role}")


async def _support_react(
    support_role: str,
    step_key: str,
    brief_context: str,
    previous_outputs: dict[str, str],
    framing: str,
    lead_text: str,
    lead_role: str,
    prior_reactions: list[str],
) -> str:
    """Generate a support agent's reaction to the lead analysis."""
    system_prompt = load_agent_prompt(support_role)

    lead_label = ROLE_LABELS_KR.get(lead_role, lead_role)
    support_label = ROLE_LABELS_KR.get(support_role, support_role)
    step_label = STEP_LABELS.get(step_key, step_key)

    user_message = (
        f"지금 [{step_label}]에 대한 팀 토론 중입니다.\n\n"
        f"## 팀장의 프레이밍 질문\n{framing}\n\n"
        f"## {lead_label}의 분석\n{lead_text[:2000]}\n\n"
    )

    if prior_reactions:
        user_message += "## 다른 팀원의 의견\n"
        for reaction in prior_reactions:
            user_message += f"{reaction[:500]}\n\n"

    user_message += (
        f"## 브리프 요약\n{brief_context[:500]}\n\n"
        f"당신은 [{support_label}]로서 위 분석에 반응해주세요.\n"
        f"다음 중 하나 이상의 관점에서 의견을 제시하세요:\n"
        f"1. **보강**: 리드 분석에 동의하면서 당신의 전문 영역에서 추가 인사이트 제공\n"
        f"2. **도전**: 놓친 관점이나 반론을 제시하여 분석의 깊이를 높임\n"
        f"3. **확장**: 리드의 아이디어를 발전시켜 새로운 방향 제안\n\n"
        f"300~500자로 간결하게 반응해주세요. 긴 분석이 아니라 핵심 의견만 제시하세요."
    )

    llm = get_llm_for_step("orchestrator")  # use orchestrator model for support turns
    response = await llm.generate(
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        temperature=0.6,
        max_tokens=800,
    )
    return _normalize_turn_text(
        response.text,
        f"[{support_label}] 관점에서 핵심 근거와 보완 포인트를 간결히 제시합니다.",
    )


async def _orchestrator_synthesize(
    step_key: str,
    brief_context: str,
    previous_outputs: dict[str, str],
    director_persona: dict[str, Any],
    framing: str,
    lead_role: str,
    lead_text: str,
    support_reactions: list[tuple[str, str]],  # [(role, text), ...]
    method_refs: list[dict] | None = None,
    case_refs: list[dict] | None = None,
) -> str:
    """Synthesize all discussion turns into a final step output."""
    system_prompt = load_agent_prompt("chief_director")

    persona_label = director_persona.get("label", "The Strategist")
    persona_style = director_persona.get("style", "hypothesis-driven")
    synthesis_style = director_persona.get("synthesis_style", "")

    system_with_persona = (
        f"{system_prompt}\n\n"
        f"---\n\n"
        f"## 현재 디렉터 페르소나: {persona_label}\n"
        f"- 스타일: {persona_style}\n"
        f"- 종합 스타일:\n{synthesis_style}\n"
    )

    step_label = STEP_LABELS.get(step_key, step_key)
    question = STEP_QUESTIONS.get(step_key, "")
    lead_label_kr = ROLE_LABELS_KR.get(lead_role, lead_role)

    # Build discussion summary
    discussion_parts = [f"[팀장 프레이밍]:\n{framing}"]
    discussion_parts.append(f"\n[{lead_label_kr} - 리드 분석]:\n{lead_text}")
    for role, text in support_reactions:
        label = ROLE_LABELS_KR.get(role, role)
        discussion_parts.append(f"\n[{label} - 반응]:\n{text}")

    prev_text = _format_previous_outputs(previous_outputs)

    # Evidence context
    evidence_text = ""
    if method_refs:
        evidence_text += "\n## 참고 방법론\n"
        for m in method_refs[:3]:
            evidence_text += f"- {m['method_name']}: {m.get('core_principle', '')[:100]}\n"
    if case_refs:
        evidence_text += "\n## 참고 사례\n"
        for c in case_refs[:3]:
            evidence_text += f"- {c['brand']} — {c['campaign_title']}: {c.get('insight', '')[:100]}\n"

    user_message = (
        f"[{step_label}] 단계의 팀 토론을 종합합니다.\n"
        f"핵심 질문: \"{question}\"\n\n"
        f"## 브리프 요약\n{brief_context[:800]}\n\n"
    )
    if prev_text:
        user_message += f"## 이전 단계 결과\n{prev_text}\n\n"
    user_message += (
        f"## 팀 토론 내용\n{''.join(discussion_parts)}\n\n"
        f"{evidence_text}\n\n"
        f"위 팀 토론을 종합하여 [{step_label}]의 최종 결론을 작성하세요.\n"
        f"당신의 종합 스타일({persona_style})에 맞게 작성하되:\n"
        f"1. 단순 요약이 아니라, 팀의 다양한 관점을 통합한 더 깊은 결론\n"
        f"2. 리드 분석을 기반으로 하되 서포트의 보강/도전 포인트를 반영\n"
        f"3. 실행 가능한 전략적 방향성 포함\n"
        f"4. 근거(데이터, 사례, 방법론) 명시\n\n"
        f"최종 결론을 깊이 있게 작성해주세요."
    )

    llm = get_llm_for_step("orchestrator")
    response = await llm.generate(
        messages=[{"role": "user", "content": user_message}],
        system=system_with_persona,
        temperature=0.6,
        max_tokens=2000,
    )
    return _normalize_turn_text(
        response.text,
        f"[{step_label}] 단계 결론: 팀 의견을 통합해 실행 가능한 단일 전략 방향을 제시합니다.",
    )
