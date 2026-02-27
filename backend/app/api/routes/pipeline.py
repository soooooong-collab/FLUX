"""
Pipeline routes — Run pipeline, SSE streaming, slides, PPTX export.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db.database import get_db
from app.models.base import User, Project, StepOutput, SlidesDeck
from app.schemas.project import RunRequest, DeckResponse, SlideData
from app.core.security import get_current_user
from app.agents.orchestrator import run_pipeline

router = APIRouter()


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
    if project.status == "running":
        raise HTTPException(status_code=409, detail="Pipeline already running")

    director_type = (req.director_type if req and req.director_type else project.director_type) or "strategist"
    brief_context = _build_brief_context(project)

    # Update status
    project.status = "running"
    project.director_type = director_type
    await db.commit()

    async def event_stream():
        try:
            async for event in run_pipeline(project_id, brief_context, director_type, db):
                event_type = event["event"]
                data_payload = json.dumps({
                    "step_key": event["step_key"],
                    "data": event["data"],
                }, ensure_ascii=False)
                yield f"event: {event_type}\ndata: {data_payload}\n\n"

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
                    if step_out:
                        step_out.output_text = event["data"]
                    else:
                        db.add(StepOutput(
                            project_id=project_id,
                            step_key=step_key,
                            output_text=event["data"],
                        ))
                    await db.commit()

                # Save final result
                if event_type == "pipeline_complete":
                    final_data = json.loads(event["data"])

                    # Update step outputs with full text
                    for key, txt in final_data.get("step_outputs", {}).items():
                        existing = await db.execute(
                            select(StepOutput).where(
                                StepOutput.project_id == project_id,
                                StepOutput.step_key == key,
                            )
                        )
                        step_out = existing.scalar_one_or_none()
                        if step_out:
                            step_out.output_text = txt
                        else:
                            db.add(StepOutput(
                                project_id=project_id,
                                step_key=key,
                                output_text=txt,
                            ))

                    # Save slides
                    slides_data = final_data.get("slides", [])
                    deck = SlidesDeck(
                        project_id=project_id,
                        slides_json=slides_data,
                    )
                    db.add(deck)
                    await db.commit()

                    # Re-fetch project to update status (avoids stale ORM object)
                    await db.execute(
                        update(Project)
                        .where(Project.id == project_id)
                        .values(status="completed")
                    )
                    await db.commit()

        except Exception as e:
            try:
                await db.execute(
                    update(Project)
                    .where(Project.id == project_id)
                    .values(status="failed")
                )
                await db.commit()
            except Exception:
                pass
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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
        select(SlidesDeck).where(SlidesDeck.project_id == project_id)
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
        select(SlidesDeck).where(SlidesDeck.project_id == project_id)
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
