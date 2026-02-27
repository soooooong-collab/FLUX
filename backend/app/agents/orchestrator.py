"""
Chief Director Orchestrator — 8-Step Pipeline with Director Persona Routing.

Manages the full pipeline execution:
  Phase 1 (s1~s3): Account Planner
  Phase 2 (s4~s6): Brand Strategist
  Phase 3 (s7~s8): Creative Director
  Output:          Presentation Designer

Case DB retrieval is controlled by the director persona's case_timing.
Each step emits SSE events for real-time frontend updates.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.roles import account_planner, brand_strategist, creative_director
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

# Step → Phase mapping
STEP_PHASES = {
    "s1": "phase1", "s2": "phase1", "s3": "phase1",
    "s4": "phase2", "s5": "phase2", "s6": "phase2",
    "s7": "phase3", "s8": "phase3",
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
    """Retrieve cases via hybrid search (Vector + Graph) with director timing control."""
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
    """Retrieve methods via hybrid search with director preference boosting.
    Returns (methods, method_names) for downstream case retrieval.
    """
    if step_key not in ("s4", "s6"):
        return None, None

    rag = RAGService(db)
    query = f"{STEP_LABELS.get(step_key, '')} {brief_context[:300]}"
    methods = await rag.retrieve_methods(query, top_k=3, director_archetype=director_type)
    if not methods:
        return None, None
    method_names = [m["method_name"] for m in methods if m.get("method_name")]
    return methods, method_names


def _review_output(output: dict) -> tuple[bool, str]:
    """Review a step output for quality. Returns (approved, feedback)."""
    text = output.get("output_text", "")
    if not text or len(text.strip()) < 100:
        return False, "결과물이 너무 짧습니다. 더 깊이 있는 분석이 필요합니다."
    if output.get("evidence_refs") is None and output["step_key"] in ("s4", "s6", "s7", "s8"):
        # These steps should have evidence references
        pass  # Soft check — don't fail, just note
    return True, "approved"


async def run_pipeline(
    project_id: str,
    brief_context: str,
    director_type: str,
    db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Execute the full 8-step pipeline as an async generator.
    Yields SSE-compatible event dicts for each step.
    """
    outputs: dict[str, str] = {}
    all_results: list[dict] = []

    # ── Phase 1: Account Planner (s1 ~ s3) ──
    for step_key in ["s1", "s2", "s3"]:
        yield _event("step_start", step_key, STEP_LABELS[step_key])

        result = await account_planner.run_step(
            step_key=step_key,
            brief_context=brief_context,
            previous_outputs=outputs,
        )
        outputs[step_key] = result["output_text"]

        # Review
        approved, feedback = _review_output(result)
        if not approved:
            yield _event("step_retry", step_key, feedback)
            result = await account_planner.run_step(
                step_key=step_key,
                brief_context=brief_context,
                previous_outputs=outputs,
            )
            outputs[step_key] = result["output_text"]

        all_results.append(result)
        yield _event("step_complete", step_key, result["output_text"][:500])

    # ── Phase 2: Brand Strategist (s4 ~ s6) ──
    discovered_method_names: list[str] | None = None
    for step_key in ["s4", "s5", "s6"]:
        yield _event("step_start", step_key, STEP_LABELS[step_key])

        # Hybrid method retrieval for strategy steps
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

        result = await brand_strategist.run_step(
            step_key=step_key,
            brief_context=brief_context,
            previous_outputs=outputs,
            db=db,
            case_refs=case_refs,
            method_refs=method_refs,
        )
        outputs[step_key] = result["output_text"]

        approved, feedback = _review_output(result)
        if not approved:
            yield _event("step_retry", step_key, feedback)
            result = await brand_strategist.run_step(
                step_key=step_key,
                brief_context=brief_context,
                previous_outputs=outputs,
                db=db,
                case_refs=case_refs,
            )
            outputs[step_key] = result["output_text"]

        all_results.append(result)
        yield _event("step_complete", step_key, result["output_text"][:500])

    # ── Phase 3: Creative Director (s7 ~ s8) ──
    for step_key in ["s7", "s8"]:
        yield _event("step_start", step_key, STEP_LABELS[step_key])

        case_refs = await _retrieve_cases_if_needed(director_type, step_key, brief_context, db)
        if case_refs:
            yield _event("case_retrieved", step_key, f"{len(case_refs)} cases found")

        result = await creative_director.run_step(
            step_key=step_key,
            brief_context=brief_context,
            previous_outputs=outputs,
            db=db,
            case_refs=case_refs,
        )
        outputs[step_key] = result["output_text"]

        approved, feedback = _review_output(result)
        if not approved:
            yield _event("step_retry", step_key, feedback)
            result = await creative_director.run_step(
                step_key=step_key,
                brief_context=brief_context,
                previous_outputs=outputs,
                db=db,
                case_refs=case_refs,
            )
            outputs[step_key] = result["output_text"]

        all_results.append(result)
        yield _event("step_complete", step_key, result["output_text"][:500])

    # ── Slides Generation ──
    yield _event("step_start", "slides", "Generating presentation")

    brand_name = brief_context.split("\n")[0][:50]  # rough extraction
    slides = await generate_slides(brand_name, outputs)

    yield _event("step_complete", "slides", f"{len(slides)} slides generated")

    # ── Final result ──
    yield _event("pipeline_complete", "done", json.dumps({
        "project_id": project_id,
        "step_outputs": {r["step_key"]: r["output_text"] for r in all_results},
        "evidence_refs": [r.get("evidence_refs", []) for r in all_results],
        "slides": slides,
        "total_tokens": sum(r.get("tokens_used", 0) for r in all_results),
    }, ensure_ascii=False))


def _event(event_type: str, step_key: str, data: str) -> dict:
    return {
        "event": event_type,
        "step_key": step_key,
        "data": data,
    }
