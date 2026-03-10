"""
Chief Director Orchestrator — 팀 토론 기반 8-Step Pipeline.

각 스텝에서 AP, BS, CD가 함께 토론하며 결론을 도출합니다.
디렉터 페르소나가 오케스트레이터의 진행 스타일을 결정합니다.

  Phase 1 (s1~s3): 리드 AP, 서포트 BS/CD
  Phase 2 (s4~s6): 리드 BS, 서포트 AP/CD
  Phase 3 (s7~s8): 리드 CD, 서포트 BS/AP
  Output:          Presentation Designer
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.discussion import run_discussion, load_director_persona, STEP_LABELS
from app.agents.roles.presentation_designer import generate_slides
from app.services.rag import RAGService

logger = logging.getLogger(__name__)

_POLICY_DIR = Path(__file__).parent / "policies"


def _load_case_timing() -> dict[str, list[str]]:
    path = _POLICY_DIR / "case_timing.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return {k: v.get("timing", []) for k, v in data.items()}


CASE_TIMING = _load_case_timing()

STEP_PHASES = {
    "s1": "phase1", "s2": "phase1", "s3": "phase1",
    "s4": "phase2", "s5": "phase2", "s6": "phase2",
    "s7": "phase3", "s8": "phase3",
}


def _should_retrieve_cases(director_type: str, step_key: str) -> bool:
    """Check if this director type should retrieve Case DB at this step."""
    timing = CASE_TIMING.get(director_type, CASE_TIMING.get("strategist", []))
    return step_key in timing


async def _retrieve_cases_if_needed(
    director_type: str,
    step_key: str,
    brief_context: str,
    db: AsyncSession,
    method_names: list[str] | None = None,
) -> list[dict] | None:
    """Retrieve cases via hybrid search with director timing control."""
    if not _should_retrieve_cases(director_type, step_key):
        return None

    rag = RAGService(db)
    query = f"{STEP_LABELS.get(step_key, '')} {brief_context[:300]}"
    cases = await rag.retrieve_cases(query, top_k=3, method_names=method_names)
    return cases if cases else None


async def _retrieve_methods_hybrid(
    director_type: str,
    step_key: str,
    brief_context: str,
    db: AsyncSession,
) -> tuple[list[dict] | None, list[str] | None]:
    """Retrieve methods via hybrid search with director preference boosting."""
    if step_key not in ("s4", "s6"):
        return None, None

    rag = RAGService(db)
    query = f"{STEP_LABELS.get(step_key, '')} {brief_context[:300]}"
    methods = await rag.retrieve_methods(query, top_k=3, director_archetype=director_type)
    if not methods:
        return None, None
    method_names = [m["method_name"] for m in methods if m.get("method_name")]
    return methods, method_names


async def run_pipeline(
    project_id: str,
    brief_context: str,
    director_type: str,
    db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Execute the full 8-step pipeline with team discussions.
    Yields SSE-compatible event dicts including discussion turns.
    """
    outputs: dict[str, str] = {}
    all_results: list[dict] = []

    # Load director persona for orchestrator moderation
    director_persona = load_director_persona(director_type)

    discovered_method_names: list[str] | None = None

    for step_key in ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]:
        yield _event("step_start", step_key, STEP_LABELS[step_key])

        # ── RAG Retrieval (unchanged logic) ──
        method_refs, method_names = await _retrieve_methods_hybrid(
            director_type, step_key, brief_context, db,
        )
        if method_refs:
            yield _event("methods_retrieved", step_key, f"{len(method_refs)} methods found")
            discovered_method_names = method_names

        case_refs = await _retrieve_cases_if_needed(
            director_type, step_key, brief_context, db,
            method_names=discovered_method_names,
        )
        if case_refs:
            yield _event("case_retrieved", step_key, f"{len(case_refs)} cases found")

        # ── Team Discussion ──
        discussion_turns: list[dict] = []
        meta_info: dict = {}

        async for turn in run_discussion(
            step_key=step_key,
            brief_context=brief_context,
            previous_outputs=outputs,
            director_persona=director_persona,
            db=db,
            method_refs=method_refs,
            case_refs=case_refs,
        ):
            if turn.get("type") == "meta":
                # Meta turn carries evidence refs and token info
                meta_info = turn.get("extra", {})
                continue

            discussion_turns.append(turn)

            # Emit discussion_turn SSE event for real-time streaming
            yield {
                "event": "discussion_turn",
                "step_key": step_key,
                "data": json.dumps({
                    "step_key": turn["step_key"],
                    "speaker": turn["speaker"],
                    "speaker_label": turn["speaker_label"],
                    "speaker_label_kr": turn["speaker_label_kr"],
                    "role": turn["role"],
                    "content": turn["content"],
                    "turn_number": turn["turn_number"],
                    "type": turn["type"],
                    "total_turns": turn["total_turns"],
                }, ensure_ascii=False),
            }

        # Extract final synthesized output (last synthesis turn)
        synthesis_turn = next(
            (t for t in reversed(discussion_turns) if t["type"] == "synthesis"),
            None,
        )
        final_output = synthesis_turn["content"] if synthesis_turn else ""
        outputs[step_key] = final_output

        # Build result dict compatible with existing pipeline
        step_result = {
            "step_key": step_key,
            "output_text": final_output,
            "model_used": meta_info.get("model_used", ""),
            "tokens_used": meta_info.get("tokens_used", 0),
            "evidence_refs": meta_info.get("evidence_refs", []),
            "discussion_log": [
                {
                    "turn_number": t["turn_number"],
                    "speaker": t["speaker"],
                    "speaker_label": t["speaker_label"],
                    "role": t["role"],
                    "content": t["content"],
                    "type": t["type"],
                }
                for t in discussion_turns
            ],
        }
        all_results.append(step_result)
        yield _event("step_complete", step_key, final_output)

    # ── Slides Generation ──
    yield _event("step_start", "slides", "Generating presentation")

    brand_name = brief_context.split("\n")[0][:50]
    slides = await generate_slides(brand_name, outputs)

    yield _event("step_complete", "slides", f"{len(slides)} slides generated")

    # ── Final result ──
    yield _event("pipeline_complete", "done", json.dumps({
        "project_id": project_id,
        "step_outputs": {r["step_key"]: r["output_text"] for r in all_results},
        "evidence_refs": [r.get("evidence_refs", []) for r in all_results],
        "discussion_logs": {r["step_key"]: r.get("discussion_log", []) for r in all_results},
        "slides": slides,
        "total_tokens": sum(r.get("tokens_used", 0) for r in all_results),
    }, ensure_ascii=False))


def _event(event_type: str, step_key: str, data: str) -> dict:
    return {
        "event": event_type,
        "step_key": step_key,
        "data": data,
    }
