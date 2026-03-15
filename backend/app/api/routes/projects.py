"""
Project routes — CRUD, PDF upload.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.base import User, Project, StepOutput
from app.schemas.project import (
    ProjectCreate, ProjectSummary, ProjectDetail, StepOutputResponse,
)
from app.core.security import get_current_user, generate_uuid
from app.agents.tools.brief_parser import extract_text_from_pdf

router = APIRouter()


@router.post("", response_model=ProjectSummary)
async def create_project(
    req: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        id=generate_uuid(),
        user_id=user.id,
        brand_name=req.brand_name,
        product_service=req.product_service,
        industry=req.industry,
        target_audience=req.target_audience,
        main_goal=req.main_goal,
        campaign_success=req.campaign_success,
        current_problem=req.current_problem,
        constraints=req.constraints,
        channels=req.channels,
        budget=req.budget,
        brief_raw_text=req.brief_raw_text,
        director_type=req.director_type,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectSummary(
        id=project.id,
        brand_name=project.brand_name,
        main_goal=project.main_goal,
        director_type=project.director_type,
        status=project.status,
        created_at=str(project.created_at),
    )


@router.get("", response_model=list[ProjectSummary])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user.id)
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return [
        ProjectSummary(
            id=p.id,
            brand_name=p.brand_name,
            main_goal=p.main_goal,
            director_type=p.director_type,
            status=p.status,
            created_at=str(p.created_at),
        )
        for p in projects
    ]


@router.post("/parse-pdf")
async def parse_brief_pdf(
    file: UploadFile = File(...),
):
    """PDF 파일에서 텍스트를 추출합니다 (프로젝트 생성 전 사용)."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = extract_text_from_pdf(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return {"text": text, "filename": file.filename}


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load step outputs
    steps_result = await db.execute(
        select(StepOutput)
        .where(StepOutput.project_id == project_id)
        .order_by(StepOutput.step_key)
    )
    steps = steps_result.scalars().all()

    return ProjectDetail(
        id=project.id,
        brand_name=project.brand_name,
        main_goal=project.main_goal,
        director_type=project.director_type,
        status=project.status,
        created_at=str(project.created_at),
        product_service=project.product_service,
        industry=project.industry,
        target_audience=project.target_audience,
        campaign_success=project.campaign_success,
        current_problem=project.current_problem,
        constraints=project.constraints,
        channels=project.channels,
        budget=project.budget,
        brief_raw_text=project.brief_raw_text,
        brief_pdf_url=project.brief_pdf_url,
        step_outputs=[
            StepOutputResponse(
                step_key=s.step_key,
                output_text=s.output_text,
                evidence_refs=s.evidence_refs,
                llm_model_used=s.llm_model_used,
            )
            for s in steps
        ],
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)
    await db.commit()
    return {"ok": True, "deleted_id": project_id}


@router.post("/{project_id}/upload-brief")
async def upload_brief_pdf(
    project_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = extract_text_from_pdf(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
            
    return {"text": text, "filename": file.filename}
