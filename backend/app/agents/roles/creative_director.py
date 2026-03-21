"""
Creative Director Agent — Phase 3 (Step 7~8) 크리에이티브 전략.

v1.1: Verbal Hook (라임형 컨셉 워드) 레이어 추가.
      - s7: Consumer Promise + Verbal Hook 도출 (Sound Map → Meaning Map → Copy Map)
      - s8: 라임 기반 크리에이티브 전략 + 카피 시스템화
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.base import LLMResponse
from app.services.llm.router import get_llm_for_step
from app.services.rag import RAGService
from app.agents.prompt_loader import load_agent_prompt

STEP_CONFIG = {
    "s7": {
        "question": (
            "우리 브랜드가 왜 그렇게 바꿔줄 수 있는가? "
            "브랜드명/제품명/카테고리명/핵심 효익의 발음·음절·의미 연상을 활용하여 "
            "Verbal Hook(라임형 컨셉 워드)를 발굴하고 Consumer Promise를 도출하라."
        ),
        "model_key": "s7_promise",
    },
    "s8": {
        "question": (
            "어떻게 이를 이슈화 시킬 것인가? "
            "앞서 도출한 Verbal Hook을 기반으로 3가지 방향의 크리에이티브 아이디어를 발상하고, "
            "최적안의 카피 시스템(헤드카피/서브카피/채널별 변주)과 비주얼 가이드를 완성하라."
        ),
        "model_key": "s8_creative",
    },
}


async def run_step(
    step_key: str,
    brief_context: str,
    previous_outputs: dict[str, str],
    db: AsyncSession,
    case_refs: list[dict] | None = None,
) -> dict:
    """Execute a single CD step."""
    config = STEP_CONFIG[step_key]
    system_prompt = load_agent_prompt("creative_director")

    context_parts = [f"## 클라이언트 브리프\n{brief_context}"]
    for k, v in previous_outputs.items():
        context_parts.append(f"## {k} 결과\n{v}")

    # Always search cases for creative reference
    case_data = ""
    evidence = []
    if case_refs:
        case_data = "\n\n## 참고 캠페인 사례 (Case DB)\n"
        for c in case_refs:
            case_data += (
                f"### {c['brand']} — {c['campaign_title']}\n"
                f"- 인사이트: {c['insight']}\n"
                f"- 솔루션: {c['solution']}\n"
                f"- 성과: {c['outcomes']}\n\n"
            )
            evidence.append({"type": "case", "id": c["case_id"], "similarity": c.get("similarity", 0)})
    else:
        # Fallback: search cases if not provided by orchestrator
        rag = RAGService(db)
        query = f"{config['question'][:50]} {brief_context[:200]}"
        cases = await rag.retrieve_cases(query, top_k=3)
        if cases:
            case_data = "\n\n## 참고 캠페인 사례 (Case DB)\n"
            for c in cases:
                case_data += (
                    f"### {c['brand']} — {c['campaign_title']}\n"
                    f"- 인사이트: {c['insight']}\n"
                    f"- 솔루션: {c['solution']}\n"
                    f"- 성과: {c['outcomes']}\n\n"
                )
                evidence.append({"type": "case", "id": c["case_id"], "similarity": c["similarity"]})

    # Build verbal hook guidance for the user message
    verbal_hook_guide = ""
    if step_key == "s7":
        verbal_hook_guide = (
            "\n\n## Verbal Hook 도출 가이드\n"
            "1. 브리프에서 브랜드명, 제품명, 카테고리명, 핵심 효익 키워드를 추출하라.\n"
            "2. Sound Map: 위 키워드를 음절 단위로 분해하고, 유사 음감 후보를 15~30개 발산하라 "
            "(두운, 각운, 동음이의, 유사발음, 자모 치환, 반복, 대구 등).\n"
            "3. Meaning Map: 각 후보가 SMP와 어떤 관계를 맺는지 한 줄로 정의하라. "
            "발음만 비슷하고 의미 연결이 약한 후보는 제거하라.\n"
            "4. Copy Map: 선별된 라임 워드를 헤드카피 구조에 얹어라 "
            "(X,Y / X의 Y / X보다 Y / 반복·대구 / 전환·반전 등).\n"
            "5. 최종 Verbal Hook과 Consumer Promise를 함께 제시하라.\n"
        )
    elif step_key == "s8":
        verbal_hook_guide = (
            "\n\n## 카피 시스템화 가이드\n"
            "1. 앞서 도출한 Verbal Hook을 기반으로 3가지 방향의 크리에이티브를 발상하라:\n"
            "   - A안 (직관적/유머러스): 말맛 좋고 직관적인 라임 중심\n"
            "   - B안 (감성적/스토리텔링): 라임을 감정과 서사로 확장\n"
            "   - C안 (파격적/실험적 참여형): 소비자 참여형 언어유희 구조\n"
            "2. 최적안을 선정하고 아래 카피 시스템을 완성하라:\n"
            "   - 메인 헤드카피 3~5안\n"
            "   - 서브카피 2~3안\n"
            "   - 채널별 변주 카피 3~5안\n"
            "   - 해시태그/숏폼용 짧은 버전\n"
            "3. 비주얼 프롬프트 가이드(미드저니/DALL·E 기반)를 포함하라.\n"
        )

    user_message = (
        f"다음 전략 분석 결과를 바탕으로 {config['question']}\n\n"
        f"{''.join(context_parts)}"
        f"{case_data}"
        f"{verbal_hook_guide}\n\n"
        f"크리에이티브 관점에서 구체적이고 실행 가능한 답을 제시해주세요."
    )

    llm = get_llm_for_step(config["model_key"])
    response: LLMResponse = await llm.generate(
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        temperature=0.7,
    )

    return {
        "step_key": step_key,
        "output_text": response.text,
        "model_used": response.model,
        "tokens_used": response.input_tokens + response.output_tokens,
        "evidence_refs": evidence,
    }
