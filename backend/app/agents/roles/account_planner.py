"""
Account Planner Agent — Phase 1 (Step 1~3) 현상 분석.
"""
from __future__ import annotations

from pathlib import Path

from app.services.llm.base import LLMResponse
from app.services.llm.router import get_llm_for_step
from app.agents.tools.web_search import execute_web_search
from app.agents.prompt_loader import load_agent_prompt

STEP_CONFIG = {
    "s1": {
        "question": "광고를 통해 얻고자 하는 궁극적인 목표는 무엇인가?",
        "model_key": "s1_goal",
    },
    "s2": {
        "question": "시장은 왜 그렇게 흘러가고 있는가?",
        "model_key": "s2_market",
    },
    "s3": {
        "question": "소비자는 왜 그런 행동을 하고 있는가?",
        "model_key": "s3_target",
    },
}


async def run_step(
    step_key: str,
    brief_context: str,
    previous_outputs: dict[str, str],
    web_search_results: list[dict] | None = None,
) -> dict:
    """Execute a single AP step and return structured output."""
    config = STEP_CONFIG[step_key]
    system_prompt = load_agent_prompt("account_planner")

    # Build context from previous steps
    context_parts = [f"## 클라이언트 브리프\n{brief_context}"]
    for k, v in previous_outputs.items():
        context_parts.append(f"## {k} 결과\n{v}")

    # For s2 (Market Analysis), do web search
    search_data = ""
    if step_key == "s2" and not web_search_results:
        # Extract brand/industry from brief for search
        search_query = f"{brief_context[:200]} 시장 동향 경쟁사 분석"
        web_search_results = await execute_web_search(search_query, num_results=5)

    if web_search_results:
        search_data = "\n\n## 웹 검색 결과\n"
        for r in web_search_results:
            search_data += f"- **{r.get('title', '')}**: {r.get('snippet', '')}\n"

    user_message = (
        f"다음 브리프와 이전 분석 결과를 바탕으로 {config['question']}\n\n"
        f"{''.join(context_parts)}"
        f"{search_data}\n\n"
        f"위 질문에 대해 깊이 있게 분석해주세요."
    )

    llm = get_llm_for_step(config["model_key"])
    response: LLMResponse = await llm.generate(
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
        temperature=0.6,
    )

    return {
        "step_key": step_key,
        "output_text": response.text,
        "model_used": response.model,
        "tokens_used": response.input_tokens + response.output_tokens,
    }
