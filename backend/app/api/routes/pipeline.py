"""
Pipeline routes — Run pipeline, SSE streaming, slides, PPTX export.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.database import get_db
from app.models.base import User, Project, StepOutput, SlidesDeck
from app.schemas.project import RunRequest, DeckResponse, SlideData
from app.core.security import get_current_user
from app.agents.orchestrator import run_pipeline

router = APIRouter()
logger = logging.getLogger(__name__)

STEP_ORDER = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]
STEP_TITLES = {
    "s1": "Campaign Goal",
    "s2": "Market Analysis",
    "s3": "Target Insight",
    "s4": "Principle Competition",
    "s5": "Target Definition",
    "s6": "Winning Strategy",
    "s7": "Consumer Promise",
    "s8": "Creative Strategy",
}


def _format_dt_local(value: datetime | None) -> str:
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _compact_text(text: str, limit: int = 280) -> str:
    compact = re.sub(r"\s+", " ", (text or "")).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _build_brief_context(project: Project) -> str:
    """Build brief context string from project data."""
    # If a PDF brief was uploaded, use that as the primary context
    if project.brief_raw_text:
        parts = [f"브랜드: {project.brand_name}"]
        if project.industry:
            parts.append(f"산업: {project.industry}")
        parts.append(f"\n--- 클라이언트 브리프 (PDF 원문) ---\n{project.brief_raw_text}")
        return "\n".join(parts)

    # Manual entry mode
    parts = [f"브랜드: {project.brand_name}"]
    if project.product_service:
        parts.append(f"제품/서비스: {project.product_service}")
    if project.industry:
        parts.append(f"산업: {project.industry}")
    if project.target_audience:
        parts.append(f"타겟: {project.target_audience}")
    if project.main_goal:
        parts.append(f"캠페인 목표: {project.main_goal}")
    if project.campaign_success:
        parts.append(f"성공 모습: {project.campaign_success}")
    if project.current_problem:
        parts.append(f"현재 문제: {project.current_problem}")
    if project.constraints:
        parts.append(f"제약조건: {project.constraints}")
    if project.channels:
        parts.append(f"채널: {', '.join(project.channels)}")
    if project.budget:
        parts.append(f"예산: {project.budget}")
    return "\n".join(parts)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value).strip("_")
    return cleaned or "project"


def _collect_agent_index(step_outputs: dict[str, StepOutput]) -> list[dict[str, Any]]:
    agent_stats: dict[str, dict[str, Any]] = {}
    for step_key in STEP_ORDER:
        step = step_outputs.get(step_key)
        if not step:
            continue
        logs = step.discussion_log if isinstance(step.discussion_log, list) else []
        for turn in logs:
            if not isinstance(turn, dict):
                continue
            speaker = str(turn.get("speaker") or "unknown")
            entry = agent_stats.setdefault(
                speaker,
                {
                    "label_kr": turn.get("speaker_label_kr") or speaker,
                    "label_en": turn.get("speaker_label") or speaker,
                    "roles": set(),
                    "turns": 0,
                },
            )
            role = turn.get("role")
            if isinstance(role, str) and role:
                entry["roles"].add(role)
            entry["turns"] += 1

    rows = []
    for speaker, entry in agent_stats.items():
        rows.append(
            {
                "speaker": speaker,
                "label_kr": entry["label_kr"],
                "label_en": entry["label_en"],
                "roles": ", ".join(sorted(entry["roles"])) or "-",
                "turns": entry["turns"],
            }
        )
    rows.sort(key=lambda row: (-row["turns"], row["speaker"]))
    return rows


def _step_logs(step_output: StepOutput) -> list[dict[str, Any]]:
    logs = step_output.discussion_log if isinstance(step_output.discussion_log, list) else []
    return [turn for turn in logs if isinstance(turn, dict)]


def _step_synthesis_text(step_output: StepOutput) -> str:
    logs = _step_logs(step_output)
    for turn in reversed(logs):
        if turn.get("type") == "synthesis":
            content = (turn.get("content") or "").strip()
            if content:
                return content
    return (step_output.output_text or "").strip()


def _build_discussion_transcript_markdown(project: Project, step_outputs: dict[str, StepOutput]) -> str:
    now_local = datetime.now(timezone.utc).astimezone()
    lines = [
        "# FLUX 전체 회의내용 녹취",
        "",
        f"- 프로젝트: {project.brand_name or '-'}",
        f"- 프로젝트 ID: `{project.id}`",
        f"- 디렉터: `{project.director_type or 'strategist'}`",
        f"- 상태: `{project.status}`",
        f"- 프로젝트 시작 시각: {_format_dt_local(project.created_at)}",
        f"- 문서 생성 시각: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
    ]

    has_any_turn = False
    for step_key in STEP_ORDER:
        step = step_outputs.get(step_key)
        if not step:
            continue

        logs = _step_logs(step)
        lines.append(f"## {step_key.upper()} · {STEP_TITLES.get(step_key, step_key)}")
        lines.append("")
        lines.append(f"- 단계 저장 시각: {_format_dt_local(step.created_at)}")
        lines.append(f"- 발언 수: {len(logs)}")
        lines.append("")

        if not logs:
            lines.append("_저장된 대화 로그가 없습니다._")
            lines.append("")
            continue

        sorted_logs = sorted(
            [turn for turn in logs if isinstance(turn, dict)],
            key=lambda turn: int(turn.get("turn_number") or 0),
        )
        for turn in sorted_logs:
            has_any_turn = True
            turn_number = turn.get("turn_number", "?")
            speaker_kr = turn.get("speaker_label_kr") or turn.get("speaker_label") or turn.get("speaker") or "Unknown"
            speaker_en = turn.get("speaker_label") or turn.get("speaker") or "Unknown"
            role = turn.get("role", "")
            turn_type = turn.get("type", "")
            content = (turn.get("content") or "").strip() or "_(내용 없음)_"

            lines.append(f"### Turn {turn_number} · {speaker_kr} ({speaker_en})")
            meta_parts = []
            if role:
                meta_parts.append(f"role: `{role}`")
            if turn_type:
                meta_parts.append(f"type: `{turn_type}`")
            if meta_parts:
                lines.append(f"- {' / '.join(meta_parts)}")
            lines.append("")
            lines.append(content)
            lines.append("")

        conclusion = _step_synthesis_text(step)
        if conclusion:
            lines.append("#### Step 결론")
            lines.append("")
            lines.append(conclusion)
            lines.append("")

    if not has_any_turn:
        lines.append("> 아직 저장된 팀 대화가 없습니다.")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _build_discussion_minutes_markdown(project: Project, step_outputs: dict[str, StepOutput]) -> str:
    now_local = datetime.now(timezone.utc).astimezone()
    agent_index = _collect_agent_index(step_outputs)

    lines = [
        "# FLUX 팀 회의록",
        "",
        "## 문서 정보",
        f"- 프로젝트: {project.brand_name or '-'}",
        f"- 프로젝트 ID: `{project.id}`",
        f"- 디렉터: `{project.director_type or 'strategist'}`",
        f"- 상태: `{project.status}`",
        f"- 프로젝트 시작 시각: {_format_dt_local(project.created_at)}",
        f"- 회의록 생성 시각: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
    ]

    lines.append("## 에이전트 색인")
    if not agent_index:
        lines.append("- 아직 집계된 발언이 없습니다.")
    else:
        lines.append("| 에이전트 | 영문 라벨 | 역할 | 발언 수 |")
        lines.append("| --- | --- | --- | ---: |")
        for row in agent_index:
            lines.append(f"| {row['label_kr']} | {row['label_en']} | `{row['roles']}` | {row['turns']} |")
    lines.append("")

    lines.append("## 타임라인")
    lines.append("| 단계 | 제목 | 저장 시각 | 턴 수 | 리드 |")
    lines.append("| --- | --- | --- | ---: | --- |")
    for step_key in STEP_ORDER:
        step = step_outputs.get(step_key)
        if not step:
            lines.append(f"| {step_key.upper()} | {STEP_TITLES.get(step_key, step_key)} | - | 0 | - |")
            continue
        logs = _step_logs(step)
        lead = "-"
        for turn in logs:
            if turn.get("role") == "lead":
                lead = turn.get("speaker_label_kr") or turn.get("speaker_label") or turn.get("speaker") or "-"
                break
        lines.append(
            f"| {step_key.upper()} | {STEP_TITLES.get(step_key, step_key)} | {_format_dt_local(step.created_at)} | {len(logs)} | {lead} |"
        )
    lines.append("")

    lines.append("## Executive Summary")
    has_summary = False
    for step_key in STEP_ORDER:
        step = step_outputs.get(step_key)
        if not step:
            continue
        summary = _compact_text(_step_synthesis_text(step), limit=260)
        if not summary:
            continue
        has_summary = True
        lines.append(f"- {step_key.upper()} {STEP_TITLES.get(step_key, step_key)}: {summary}")
    if not has_summary:
        lines.append("- 아직 요약 가능한 회의 내용이 없습니다.")
    lines.append("")

    lines.append("## 핵심 결정사항")
    decision_steps = [k for k in ("s4", "s6", "s7", "s8") if k in step_outputs]
    if not decision_steps:
        lines.append("1. 아직 결정사항이 정리되지 않았습니다.")
    else:
        idx = 1
        for step_key in decision_steps:
            decision = _compact_text(_step_synthesis_text(step_outputs[step_key]), limit=180)
            if not decision:
                continue
            lines.append(f"{idx}. ({step_key.upper()}) {decision}")
            idx += 1
        if idx == 1:
            lines.append("1. 아직 결정사항이 정리되지 않았습니다.")
    lines.append("")

    lines.append("## 후속 액션")
    pending_steps = [k.upper() for k in STEP_ORDER if k not in step_outputs]
    if pending_steps:
        lines.append(f"- 미완료 단계: {', '.join(pending_steps)}")
    else:
        lines.append("- 모든 단계 회의 로그가 수집되었습니다.")
    lines.append("- 상세 발언 전문은 `전체 회의내용 녹취` 문서를 참고하세요.")
    lines.append("")

    return "\n".join(lines).strip() + "\n"


async def _load_project_and_latest_steps(
    project_id: str,
    user_id: str,
    db: AsyncSession,
) -> tuple[Project, dict[str, StepOutput]]:
    project_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    step_result = await db.execute(
        select(StepOutput)
        .where(StepOutput.project_id == project_id)
        .order_by(StepOutput.created_at.desc())
    )
    rows = step_result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No discussion transcript available yet")

    latest_by_step: dict[str, StepOutput] = {}
    for row in rows:
        if row.step_key not in latest_by_step:
            latest_by_step[row.step_key] = row
    return project, latest_by_step


@router.post("/{project_id}/run")
async def run_project_pipeline(
    project_id: str,
    req: Optional[RunRequest] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start pipeline execution and return SSE stream."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    director_type = (req.director_type if req and req.director_type else project.director_type) or "strategist"
    brief_context = _build_brief_context(project)

    # Recover stale status if slides already exist.
    if project.status == "running":
        deck_check = await db.execute(
            select(SlidesDeck.id)
            .where(SlidesDeck.project_id == project_id)
            .limit(1)
        )
        if deck_check.scalar_one_or_none():
            await db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(status="completed")
            )
            await db.commit()

    # Atomic status transition to avoid duplicate pipeline starts.
    updated = await db.execute(
        update(Project)
        .where(
            Project.id == project_id,
            Project.user_id == user.id,
            Project.status != "running",
        )
        .values(status="running", director_type=director_type)
    )
    await db.commit()
    if updated.rowcount == 0:
        raise HTTPException(status_code=409, detail="Pipeline already running")

    async def event_stream():
        # Collect discussion logs per step for DB persistence
        step_discussion_logs: dict[str, list] = {}

        async def _mark_status(status: str):
            await db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(status=status)
            )
            await db.commit()

        try:
            async for event in run_pipeline(project_id, brief_context, director_type, db):
                event_type = event["event"]

                # For discussion_turn events, data is already a JSON string
                if event_type == "discussion_turn":
                    turn_data = json.loads(event["data"]) if isinstance(event["data"], str) else event["data"]
                    data_payload = json.dumps({
                        "step_key": event["step_key"],
                        "data": turn_data,
                    }, ensure_ascii=False)
                    yield f"event: {event_type}\ndata: {data_payload}\n\n"

                    # Collect discussion turns for DB persistence
                    sk = event["step_key"]
                    if sk not in step_discussion_logs:
                        step_discussion_logs[sk] = []
                    step_discussion_logs[sk].append(turn_data)
                    continue

                # Save final result
                if event_type == "pipeline_complete":
                    final_data = json.loads(event["data"])
                    discussion_logs_all = final_data.get("discussion_logs", {})

                    # Update step outputs with full text and discussion logs
                    for key, txt in final_data.get("step_outputs", {}).items():
                        existing = await db.execute(
                            select(StepOutput).where(
                                StepOutput.project_id == project_id,
                                StepOutput.step_key == key,
                            )
                        )
                        step_out = existing.scalar_one_or_none()
                        disc_log = discussion_logs_all.get(key)
                        if step_out:
                            step_out.output_text = txt
                            if disc_log:
                                step_out.discussion_log = disc_log
                        else:
                            db.add(StepOutput(
                                project_id=project_id,
                                step_key=key,
                                output_text=txt,
                                discussion_log=disc_log,
                            ))

                    # Save or update slides deck
                    slides_data = final_data.get("slides", [])
                    existing_deck = await db.execute(
                        select(SlidesDeck)
                        .where(SlidesDeck.project_id == project_id)
                        .order_by(SlidesDeck.created_at.desc())
                        .limit(1)
                    )
                    deck = existing_deck.scalar_one_or_none()
                    if deck:
                        deck.slides_json = slides_data
                    else:
                        db.add(SlidesDeck(
                            project_id=project_id,
                            slides_json=slides_data,
                        ))
                    await db.commit()

                    await _mark_status("completed")

                    data_payload = json.dumps({
                        "step_key": event["step_key"],
                        "data": event["data"],
                    }, ensure_ascii=False)
                    yield f"event: {event_type}\ndata: {data_payload}\n\n"
                    continue

                # Save step outputs to DB (only s1-s8, not "slides")
                step_key = event["step_key"]
                if event_type == "step_complete" and step_key.startswith("s") and step_key != "slides":
                    existing = await db.execute(
                        select(StepOutput).where(
                            StepOutput.project_id == project_id,
                            StepOutput.step_key == step_key,
                        )
                    )
                    step_out = existing.scalar_one_or_none()
                    disc_log = step_discussion_logs.get(step_key)
                    if step_out:
                        step_out.output_text = event["data"]
                        if disc_log:
                            step_out.discussion_log = disc_log
                    else:
                        db.add(StepOutput(
                            project_id=project_id,
                            step_key=step_key,
                            output_text=event["data"],
                            discussion_log=disc_log,
                        ))
                    await db.commit()

                data_payload = json.dumps({
                    "step_key": event["step_key"],
                    "data": event["data"],
                }, ensure_ascii=False)
                yield f"event: {event_type}\ndata: {data_payload}\n\n"

        except asyncio.CancelledError:
            logger.info("Pipeline stream cancelled: project_id=%s", project_id)
            try:
                await _mark_status("failed")
            except Exception:
                logger.exception("Failed to mark cancelled pipeline as failed: project_id=%s", project_id)
            raise
        except Exception as e:
            logger.exception("Pipeline failed: project_id=%s", project_id)
            try:
                await _mark_status("failed")
            except Exception:
                logger.exception("Failed to mark pipeline as failed: project_id=%s", project_id)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            try:
                status_result = await db.execute(
                    select(Project.status).where(Project.id == project_id)
                )
                status = status_result.scalar_one_or_none()
                if status == "running":
                    await _mark_status("failed")
            except Exception:
                logger.exception("Failed final status check: project_id=%s", project_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{project_id}/discussion-transcript")
async def get_discussion_transcript(
    project_id: str,
    download: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return agent discussion transcript as markdown."""
    project, latest_by_step = await _load_project_and_latest_steps(project_id, user.id, db)

    markdown = _build_discussion_transcript_markdown(project, latest_by_step)

    headers = {}
    if download:
        filename = f"{_safe_filename(project.brand_name or 'project')}_team_discussion.md"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return PlainTextResponse(
        markdown,
        media_type="text/markdown; charset=utf-8",
        headers=headers,
    )


@router.get("/{project_id}/discussion-minutes")
async def get_discussion_minutes(
    project_id: str,
    download: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return discussion minutes (summary-focused) as markdown."""
    project, latest_by_step = await _load_project_and_latest_steps(project_id, user.id, db)
    markdown = _build_discussion_minutes_markdown(project, latest_by_step)

    headers = {}
    if download:
        filename = f"{_safe_filename(project.brand_name or 'project')}_minutes.md"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return PlainTextResponse(
        markdown,
        media_type="text/markdown; charset=utf-8",
        headers=headers,
    )


@router.get("/{project_id}/slides", response_model=DeckResponse)
async def get_slides(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    deck_result = await db.execute(
        select(SlidesDeck)
        .where(SlidesDeck.project_id == project_id)
        .order_by(SlidesDeck.created_at.desc())
        .limit(1)
    )
    deck = deck_result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Slides not generated yet")

    slides = deck.slides_json or []
    return DeckResponse(
        project_id=project_id,
        title=f"{project.brand_name} Campaign Strategy",
        total_slides=len(slides),
        slides=[
            SlideData(
                step_key=s.get("step_key", ""),
                phase=s.get("phase", ""),
                title=s.get("title", ""),
                subtitle=s.get("subtitle", ""),
                body=s.get("body", ""),
                layout=s.get("layout", "title_content"),
                key_points=s.get("key_points"),
            )
            for s in slides
        ],
    )


@router.get("/{project_id}/export/pptx")
async def export_pptx(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate and return PPTX file."""
    from app.services.pptx_export import generate_pptx

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    deck_result = await db.execute(
        select(SlidesDeck)
        .where(SlidesDeck.project_id == project_id)
        .order_by(SlidesDeck.created_at.desc())
        .limit(1)
    )
    deck = deck_result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Slides not generated yet")

    pptx_bytes = generate_pptx(project.brand_name, deck.slides_json or [])

    return StreamingResponse(
        iter([pptx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{project.brand_name}_strategy.pptx"'},
    )


@router.get("/{project_id}/export/meeting-pptx")
async def export_meeting_pptx(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate Meeting Report PPTX from discussion conclusions."""
    from app.services.meeting_extract import extract_conclusions
    from app.agents.roles.meeting_slide_designer import generate_meeting_slides
    from app.services.meeting_pptx import generate_meeting_pptx

    project, step_outputs = await _load_project_and_latest_steps(
        project_id, user.id, db,
    )

    # Phase 1: Extract conclusions
    conclusions = extract_conclusions(project, step_outputs)
    if not conclusions["sections"]:
        raise HTTPException(status_code=404, detail="No completed steps to generate meeting PPTX")

    # Phase 2: Distill via LLM → slides.json
    slides_data = await generate_meeting_slides(project.brand_name, conclusions)

    # Phase 3: Generate PPTX
    pptx_bytes = generate_meeting_pptx(slides_data)

    return StreamingResponse(
        iter([pptx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{project.brand_name}_meeting_report.pptx"'},
    )
