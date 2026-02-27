"""
Creative Director Agent — Phase 3 (Step 7~8) 크리에이티브 전략.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.base import LLMResponse
from app.services.llm.router import get_llm_for_step
from app.services.rag import RAGService

PROMPT_PATH = Path(__file__).parent.parent.parent.parent / "prompts" / "creative_director.md"

STEP_CONFIG = {
    "s7": {
        "question": "우리 브랜드가 왜 그렇게 바꿔줄 수 있는가?",
        "model_key": "s7_promise",
    },
    "s8": {
        "question": "어떻게 이를 이슈화 시킬 것인가?",
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
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

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
        query = f"{config['question']} {brief_context[:200]}"
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

    user_message = (
        f"다음 전략 분석 결과를 바탕으로 {config['question']}\n\n"
        f"{''.join(context_parts)}"
        f"{case_data}\n\n"
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
