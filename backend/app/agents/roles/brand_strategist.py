"""
Brand Strategist Agent — Phase 2 (Step 4~5) + Step 6 전략 기획.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.base import LLMResponse
from app.services.llm.router import get_llm_for_step
from app.services.rag import RAGService
from app.agents.prompt_loader import load_agent_prompt

STEP_CONFIG = {
    "s4": {
        "question": "진짜 경쟁자는 어떤 인식인가?",
        "model_key": "s4_competition",
        "needs_method_search": True,
    },
    "s5": {
        "question": "그런 인식을 가지고 있는 소비자를 무엇이라 표현할 것인가?",
        "model_key": "s5_definition",
        "needs_method_search": False,
    },
    "s6": {
        "question": "그런 소비자의 인식을 어떻게 바꿔줄 것인가?",
        "model_key": "s6_strategy",
        "needs_method_search": True,
    },
}


async def run_step(
    step_key: str,
    brief_context: str,
    previous_outputs: dict[str, str],
    db: AsyncSession,
    case_refs: list[dict] | None = None,
    method_refs: list[dict] | None = None,
) -> dict:
    """Execute a single BS step."""
    config = STEP_CONFIG[step_key]
    system_prompt = load_agent_prompt("brand_strategist")

    # Build context
    context_parts = [f"## 클라이언트 브리프\n{brief_context}"]
    for k, v in previous_outputs.items():
        context_parts.append(f"## {k} 결과\n{v}")

    # Method DB search for s4, s6
    # Use pre-retrieved hybrid results if available, otherwise search locally
    method_data = ""
    evidence_methods = []
    if config["needs_method_search"]:
        methods = method_refs
        if not methods:
            rag = RAGService(db)
            search_query = f"{config['question']} {brief_context[:200]}"
            methods = await rag.retrieve_methods(search_query, top_k=3)
        if methods:
            method_data = "\n\n## 관련 전략 방법론 (Method DB)\n"
            for m in methods:
                score = m.get("final_score") or m.get("similarity", 0)
                method_data += (
                    f"### {m['method_name']} ({m.get('category', '')})\n"
                    f"- 핵심 원리: {m.get('core_principle', '')}\n"
                    f"- 적용 시점: {m.get('apply_when', '')}\n"
                    f"- 관련도: {score:.3f}\n\n"
                )
                evidence_methods.append({
                    "type": "method", "id": m.get("id"),
                    "name": m["method_name"], "similarity": score,
                })

    # Case refs (injected by orchestrator based on director persona timing)
    case_data = ""
    if case_refs:
        case_data = "\n\n## 참고 캠페인 사례 (Case DB)\n"
        for c in case_refs:
            case_data += (
                f"### {c['brand']} — {c['campaign_title']}\n"
                f"- 문제: {c['problem']}\n"
                f"- 인사이트: {c['insight']}\n"
                f"- 솔루션: {c['solution']}\n\n"
            )

    user_message = (
        f"다음 분석 결과를 바탕으로 {config['question']}\n\n"
        f"{''.join(context_parts)}"
        f"{method_data}{case_data}\n\n"
        f"위 질문에 전략적으로 깊이 있게 답해주세요."
    )

    llm = get_llm_for_step(config["model_key"])
    response: LLMResponse = await llm.generate(
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        temperature=0.6,
    )

    evidence = evidence_methods
    if case_refs:
        evidence.extend([{"type": "case", "id": c["case_id"], "similarity": c.get("similarity", 0)} for c in case_refs])

    return {
        "step_key": step_key,
        "output_text": response.text,
        "model_used": response.model,
        "tokens_used": response.input_tokens + response.output_tokens,
        "evidence_refs": evidence,
    }
