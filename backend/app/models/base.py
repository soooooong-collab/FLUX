"""
ORM Models — FLUX 3-Layer Ontology + Production Data

Layer 1 (Brain):    Method   — Strategy frameworks / methodologies
Layer 2 (Evidence): Case     — Real campaign case studies
Layer 3 (Control):  Director — Creative director personas
Production:         User, Project, StepOutput, SlidesDeck
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Float,
    ForeignKey, ARRAY, JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


def _vector_col(dim: int):
    if Vector is not None:
        return Column(Vector(dim))
    return Column(JSON)


# ── Layer 1: Method (Brain) ─────────────────────────────────────

class Method(Base):
    __tablename__ = "methods"

    id = Column(Integer, primary_key=True, index=True)
    method_name = Column(String, unique=True, index=True, nullable=False)
    category = Column(String)
    signature_question = Column(Text)
    core_principle = Column(Text)
    apply_when = Column(Text)
    avoid_when = Column(Text)
    risk_factors = Column(Text)
    version = Column(String, default="1.0")
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    embedding = _vector_col(768)


# ── Layer 2: Case (Evidence) ────────────────────────────────────

class Case(Base):
    __tablename__ = "cases"

    case_id = Column(String, primary_key=True)
    brand = Column(String)
    campaign_title = Column(String)
    industry = Column(String)
    target = Column(String)
    problem = Column(Text)
    insight = Column(Text)
    solution = Column(Text)
    applied_methods = Column(ARRAY(String))
    key_channels = Column(ARRAY(String))
    outcomes = Column(Text)
    budget_tier = Column(String)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    embedding = _vector_col(768)


# ── Layer 3: Director (Control) ─────────────────────────────────

class Director(Base):
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    tagline = Column(String)
    archetype = Column(String)  # strategist | provocateur | storyteller | emotional_minimalist | culture_hacker | performance_hacker
    description = Column(Text)
    recommended_for = Column(Text)
    avoid_when = Column(Text)
    risk_notes = Column(Text)
    # Weight factors for style
    w_logic = Column(Float, default=0.0)
    w_emotion = Column(Float, default=0.0)
    w_culture = Column(Float, default=0.0)
    w_action = Column(Float, default=0.0)
    w_performance = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


# ── Production: User ────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)  # UUID
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    display_name = Column(String)
    plan_tier = Column(String, default="free")  # free | pro | enterprise
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    projects = relationship("Project", back_populates="user")


# ── Production: Project ─────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    brand_name = Column(String)
    product_service = Column(String)
    industry = Column(String)
    target_audience = Column(String)
    main_goal = Column(Text)
    campaign_success = Column(Text)
    current_problem = Column(Text)
    constraints = Column(Text)
    channels = Column(ARRAY(String))
    budget = Column(String)
    brief_raw_text = Column(Text)  # Full text extracted from uploaded PDF brief
    brief_pdf_url = Column(String)
    director_type = Column(String, default="strategist")
    status = Column(String, default="draft")  # draft | running | completed | failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="projects")
    step_outputs = relationship("StepOutput", back_populates="project", cascade="all, delete-orphan")
    slides_deck = relationship("SlidesDeck", back_populates="project", uselist=False, cascade="all, delete-orphan")


# ── Production: StepOutput ──────────────────────────────────────

class StepOutput(Base):
    __tablename__ = "step_outputs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    step_key = Column(String, nullable=False)  # s1 ~ s8
    output_text = Column(Text)
    evidence_refs = Column(JSON)  # [{"type": "method"|"case", "id": ..., "similarity": ...}]
    discussion_log = Column(JSON)  # [{turn_number, speaker, role, content, type}, ...]
    llm_model_used = Column(String)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="step_outputs")


# ── Production: SlidesDeck ──────────────────────────────────────

class SlidesDeck(Base):
    __tablename__ = "slides_decks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("projects.id"), unique=True, nullable=False)
    slides_json = Column(JSON)
    pptx_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="slides_deck")
