from typing import List, Optional

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    brand_name: str
    product_service: Optional[str] = None
    industry: Optional[str] = None
    target_audience: Optional[str] = None
    main_goal: str = ""
    campaign_success: Optional[str] = None
    current_problem: Optional[str] = None
    constraints: Optional[str] = None
    channels: Optional[List[str]] = None
    budget: Optional[str] = None
    brief_raw_text: Optional[str] = None  # Full text from uploaded PDF brief
    director_type: str = "strategist"


class ProjectSummary(BaseModel):
    id: str
    brand_name: str
    main_goal: str
    director_type: str
    status: str
    created_at: str


class StepOutputResponse(BaseModel):
    step_key: str
    output_text: str
    evidence_refs: Optional[list] = None
    llm_model_used: Optional[str] = None


class ProjectDetail(ProjectSummary):
    product_service: Optional[str]
    industry: Optional[str]
    target_audience: Optional[str]
    campaign_success: Optional[str]
    current_problem: Optional[str]
    constraints: Optional[str]
    channels: Optional[List[str]]
    budget: Optional[str]
    brief_raw_text: Optional[str]
    brief_pdf_url: Optional[str]
    step_outputs: List[StepOutputResponse]


class RunRequest(BaseModel):
    director_type: Optional[str] = None  # override director if desired


class SlideData(BaseModel):
    step_key: str
    phase: str
    title: str
    subtitle: str
    body: str
    layout: str
    key_points: Optional[str] = None


class DeckResponse(BaseModel):
    project_id: str
    title: str
    total_slides: int
    slides: List[SlideData]
