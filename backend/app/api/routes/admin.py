"""
Admin routes — Data management, Graph build, Embedding pipeline, Monitoring.

Phase 2 full implementation:
- /admin/sync             — Excel → PostgreSQL sync
- /admin/sync/upload      — Excel upload → DB sync
- /admin/graph/build      — Full Neo4j ontology build
- /admin/graph/stats      — Graph statistics
- /admin/graph/method/:name — Method subgraph
- /admin/graph/case/:id/similar — Similar cases
- /admin/graph/director/:archetype/methods — Director preferences
- /admin/embeddings/run   — Embedding pipeline
- /admin/embeddings/status — Embedding coverage
- /admin/methods          — Method CRUD
- /admin/methods/categories — Category list
- /admin/cases            — Case CRUD
- /admin/cases/:id        — Case detail (with graph)
- /admin/directors        — Director list
- /admin/health           — System health dashboard
"""
from __future__ import annotations

from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.database import get_db
from app.models.base import Method, Case, Director

router = APIRouter()


# ══════════════════════════════════════════════════════════════════
#  DATA SYNC — Excel → PostgreSQL
# ══════════════════════════════════════════════════════════════════

@router.post("/sync")
async def sync_data(db: AsyncSession = Depends(get_db)):
    """Sync raw Excel data to PostgreSQL."""
    from app.db.seed import seed_methods, seed_cases, seed_directors

    methods_count = await seed_methods(db)
    cases_count = await seed_cases(db)
    directors_count = await seed_directors(db)

    return {
        "methods_inserted": methods_count,
        "cases_inserted": cases_count,
        "directors_inserted": directors_count,
        "status": "ok",
    }


def _split_csv(val) -> Optional[List[str]]:
    if pd.isna(val) or not str(val).strip():
        return None
    return [v.strip() for v in str(val).split(",") if v.strip()]


@router.post("/sync/upload")
async def sync_from_upload(
    dataset: str = Query(..., description="methods | cases | directors"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload an Excel file and sync it to DB."""
    import tempfile

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only .xlsx or .xls files are accepted")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    df = pd.read_excel(tmp_path)
    count = 0

    if dataset == "methods":
        for _, row in df.iterrows():
            method_name = str(row.get("method_name", "")).strip()
            if not method_name:
                continue

            new_data = dict(
                category=str(row.get("category", "")) or None,
                signature_question=str(row.get("signature_question", "")) or None,
                core_principle=str(row.get("core_principle", "")) or None,
                apply_when=str(row.get("apply_when", "")) or None,
                avoid_when=str(row.get("avoid_when", "")) or None,
                risk_factors=str(row.get("risk_factors", "")) or None,
            )

            existing_result = await db.execute(select(Method).where(Method.method_name == method_name))
            existing_method = existing_result.scalar_one_or_none()

            if existing_method:
                changed = False
                for k, v in new_data.items():
                    if getattr(existing_method, k) != v:
                        setattr(existing_method, k, v)
                        changed = True
                if changed:
                    existing_method.embedding = None
                    count += 1
            else:
                db.add(Method(method_name=method_name, **new_data))
                count += 1
        await db.commit()

    elif dataset == "cases":
        for _, row in df.iterrows():
            case_id = str(row.get("case_id", "")).strip()
            if not case_id:
                continue

            new_data = dict(
                brand=str(row.get("brand", "")) or None,
                campaign_title=str(row.get("campaign_title", "")) or None,
                industry=str(row.get("industry", "")) or None,
                target=str(row.get("target", "")) or None,
                problem=str(row.get("problem", "")) or None,
                insight=str(row.get("insight", "")) or None,
                solution=str(row.get("solution", "")) or None,
                applied_methods=_split_csv(row.get("applied_methods")),
                key_channels=_split_csv(row.get("key_channels")),
                outcomes=str(row.get("outcomes", "")) or None,
                budget_tier=str(row.get("budget_tier", "")) or None,
            )

            existing_result = await db.execute(select(Case).where(Case.case_id == case_id))
            existing_case = existing_result.scalar_one_or_none()

            if existing_case:
                changed = False
                for k, v in new_data.items():
                    if getattr(existing_case, k) != v:
                        setattr(existing_case, k, v)
                        changed = True
                if changed:
                    existing_case.embedding = None
                    count += 1
            else:
                db.add(Case(case_id=case_id, **new_data))
                count += 1
        await db.commit()

    elif dataset == "directors":
        for _, row in df.iterrows():
            name = str(row.get("name", "")).strip()
            if not name:
                continue

            new_data = dict(
                tagline=str(row.get("tagline", "")) or None,
                archetype=str(row.get("archetype", "")).lower() or None,
                description=str(row.get("description", "")) or None,
                recommended_for=str(row.get("recommended_for", "")) or None,
                avoid_when=str(row.get("avoid_when", "")) or None,
                risk_notes=str(row.get("risk_notes", "")) or None,
                w_logic=float(row.get("w_logic", 0)) if not pd.isna(row.get("w_logic")) else 0.0,
                w_emotion=float(row.get("w_emotion", 0)) if not pd.isna(row.get("w_emotion")) else 0.0,
                w_culture=float(row.get("w_culture", 0)) if not pd.isna(row.get("w_culture")) else 0.0,
                w_action=float(row.get("w_action", 0)) if not pd.isna(row.get("w_action")) else 0.0,
                w_performance=float(row.get("w_performance", 0)) if not pd.isna(row.get("w_performance")) else 0.0,
            )

            existing_result = await db.execute(select(Director).where(Director.name == name))
            existing_director = existing_result.scalar_one_or_none()

            if existing_director:
                changed = False
                for k, v in new_data.items():
                    old_val = getattr(existing_director, k)
                    if isinstance(old_val, float):
                        if abs(old_val - v) > 1e-4:
                            setattr(existing_director, k, v)
                            changed = True
                    elif old_val != v:
                        setattr(existing_director, k, v)
                        changed = True
                if changed:
                    count += 1
            else:
                db.add(Director(name=name, **new_data))
                count += 1
        await db.commit()
    else:
        raise HTTPException(400, f"Unknown dataset: {dataset}. Use methods|cases|directors")

    return {"dataset": dataset, "inserted": count, "filename": file.filename}


# ══════════════════════════════════════════════════════════════════
#  FULL SYNC PIPELINE
# ══════════════════════════════════════════════════════════════════

@router.post("/pipeline/full")
async def run_full_pipeline(db: AsyncSession = Depends(get_db)):
    """Run DB Sync → Graph Build → Embeddings all at once."""
    from app.db.seed import seed_methods, seed_cases, seed_directors
    from app.services.graph import GraphService
    from app.services.embedding import EmbeddingPipeline

    # 1. DB Sync (Upsert)
    methods_count = await seed_methods(db)
    cases_count = await seed_cases(db)
    directors_count = await seed_directors(db)

    # 2. Graph Build
    graph = GraphService()
    graph.clear_graph()
    graph.create_constraints()

    methods_result = await db.execute(select(Method).where(Method.is_active == True))
    methods = methods_result.scalars().all()
    methods_data = [
        {
            "id": m.id, "method_name": m.method_name, "category": m.category,
            "signature_question": m.signature_question, "core_principle": m.core_principle,
            "apply_when": m.apply_when, "avoid_when": m.avoid_when, "risk_factors": m.risk_factors,
        }
        for m in methods
    ]

    cases_result = await db.execute(select(Case))
    cases = cases_result.scalars().all()
    cases_data = [
        {
            "case_id": c.case_id, "brand": c.brand, "campaign_title": c.campaign_title,
            "industry": c.industry, "target": c.target, "problem": c.problem,
            "insight": c.insight, "solution": c.solution, "outcomes": c.outcomes,
            "budget_tier": c.budget_tier, "applied_methods": c.applied_methods,
            "key_channels": c.key_channels,
        }
        for c in cases
    ]

    directors_result = await db.execute(select(Director).where(Director.is_active == True))
    directors = directors_result.scalars().all()
    directors_data = [
        {
            "name": d.name, "tagline": d.tagline, "archetype": d.archetype,
            "description": d.description, "w_logic": d.w_logic, "w_emotion": d.w_emotion,
            "w_culture": d.w_culture, "w_action": d.w_action, "w_performance": d.w_performance,
        }
        for d in directors
    ]

    graph.seed_methods(methods_data)
    graph.seed_cases(cases_data)
    graph.seed_directors(directors_data)
    graph.build_director_method_preferences(directors_data, methods_data)
    graph.build_case_similarity()
    graph.build_method_relatedness()

    # 3. Embedding Pipeline
    pipeline = EmbeddingPipeline(db)
    embedding_result = await pipeline.run_full_pipeline(force=False)

    return {
        "status": "success",
        "sync": {
            "methods_upserted": methods_count,
            "cases_upserted": cases_count,
            "directors_upserted": directors_count
        },
        "graph": graph.get_stats(),
        "embeddings": embedding_result
    }



# ══════════════════════════════════════════════════════════════════
#  NEO4J GRAPH BUILD
# ══════════════════════════════════════════════════════════════════

@router.post("/graph/build")
async def build_graph(
    clear: bool = Query(False, description="Clear existing graph before rebuild"),
    db: AsyncSession = Depends(get_db),
):
    """Build full Neo4j ontology graph from PostgreSQL data."""
    from app.services.graph import GraphService

    graph = GraphService()

    if clear:
        graph.clear_graph()

    graph.create_constraints()

    # Load all data from PG
    methods_result = await db.execute(select(Method).where(Method.is_active == True))
    methods = methods_result.scalars().all()
    methods_data = [
        {
            "id": m.id, "method_name": m.method_name, "category": m.category,
            "signature_question": m.signature_question, "core_principle": m.core_principle,
            "apply_when": m.apply_when, "avoid_when": m.avoid_when, "risk_factors": m.risk_factors,
        }
        for m in methods
    ]

    cases_result = await db.execute(select(Case))
    cases = cases_result.scalars().all()
    cases_data = [
        {
            "case_id": c.case_id, "brand": c.brand, "campaign_title": c.campaign_title,
            "industry": c.industry, "target": c.target, "problem": c.problem,
            "insight": c.insight, "solution": c.solution, "outcomes": c.outcomes,
            "budget_tier": c.budget_tier, "applied_methods": c.applied_methods,
            "key_channels": c.key_channels,
        }
        for c in cases
    ]

    directors_result = await db.execute(select(Director).where(Director.is_active == True))
    directors = directors_result.scalars().all()
    directors_data = [
        {
            "name": d.name, "tagline": d.tagline, "archetype": d.archetype,
            "description": d.description, "w_logic": d.w_logic, "w_emotion": d.w_emotion,
            "w_culture": d.w_culture, "w_action": d.w_action, "w_performance": d.w_performance,
        }
        for d in directors
    ]

    # Build in order
    results = {
        "methods_nodes": graph.seed_methods(methods_data),
        "cases_nodes": graph.seed_cases(cases_data),
        "directors_nodes": graph.seed_directors(directors_data),
        "director_preferences": graph.build_director_method_preferences(directors_data, methods_data),
        "case_similarity": graph.build_case_similarity(),
        "method_relatedness": graph.build_method_relatedness(),
    }
    results["stats"] = graph.get_stats()
    return results


@router.get("/graph/stats")
async def graph_stats():
    """Return Neo4j graph statistics."""
    from app.services.graph import GraphService
    return GraphService().get_stats()


@router.get("/graph/method/{method_name}")
async def graph_method_subgraph(method_name: str):
    """Get full subgraph around a Method."""
    from app.services.graph import GraphService
    return GraphService().get_method_case_subgraph(method_name)


@router.get("/graph/case/{case_id}/similar")
async def graph_similar_cases(case_id: str, limit: int = 5):
    """Get similar cases via graph."""
    from app.services.graph import GraphService
    return GraphService().find_similar_cases(case_id, limit=limit)


@router.get("/graph/director/{archetype}/methods")
async def graph_director_methods(archetype: str, limit: int = 10):
    """Get preferred methods for a director archetype."""
    from app.services.graph import GraphService
    return GraphService().find_preferred_methods(archetype, limit=limit)


# ══════════════════════════════════════════════════════════════════
#  EMBEDDING PIPELINE
# ══════════════════════════════════════════════════════════════════

@router.post("/embeddings/run")
async def run_embeddings(
    force: bool = Query(False, description="Force re-embed all records"),
    db: AsyncSession = Depends(get_db),
):
    """Run embedding pipeline for all methods and cases."""
    from app.services.embedding import EmbeddingPipeline
    pipeline = EmbeddingPipeline(db)
    return await pipeline.run_full_pipeline(force=force)


@router.get("/embeddings/status")
async def embedding_status(db: AsyncSession = Depends(get_db)):
    """Get embedding coverage status."""
    from app.services.embedding import EmbeddingPipeline
    pipeline = EmbeddingPipeline(db)
    return await pipeline.get_embedding_status()


# ══════════════════════════════════════════════════════════════════
#  METHOD CRUD
# ══════════════════════════════════════════════════════════════════

@router.get("/methods")
async def list_methods(
    category: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    query = select(Method)
    if active_only:
        query = query.where(Method.is_active == True)
    if category:
        query = query.where(Method.category == category)
    query = query.order_by(Method.category, Method.method_name)
    result = await db.execute(query)
    return [
        {
            "id": m.id, "method_name": m.method_name, "category": m.category,
            "signature_question": m.signature_question, "core_principle": m.core_principle,
            "apply_when": m.apply_when, "avoid_when": m.avoid_when,
            "risk_factors": m.risk_factors,
            "has_embedding": m.embedding is not None, "is_active": m.is_active,
        }
        for m in result.scalars().all()
    ]


@router.get("/methods/categories")
async def list_method_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Method.category, func.count(Method.id))
        .where(Method.is_active == True)
        .group_by(Method.category)
        .order_by(func.count(Method.id).desc())
    )
    return [{"category": r[0], "count": r[1]} for r in result.fetchall()]


@router.put("/methods/{method_id}")
async def update_method(method_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Method).where(Method.id == method_id))
    method = result.scalar_one_or_none()
    if not method:
        raise HTTPException(404, "Method not found")

    updatable = ["method_name", "category", "signature_question", "core_principle",
                  "apply_when", "avoid_when", "risk_factors", "is_active"]
    changed = False
    for key in updatable:
        if key in data:
            setattr(method, key, data[key])
            changed = True
    if changed:
        method.embedding = None  # invalidate embedding on content change
        await db.commit()
    return {"id": method.id, "updated": changed}


@router.delete("/methods/{method_id}")
async def deactivate_method(method_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Method).where(Method.id == method_id))
    method = result.scalar_one_or_none()
    if not method:
        raise HTTPException(404, "Method not found")
    method.is_active = False
    await db.commit()
    return {"id": method.id, "deactivated": True}


# ══════════════════════════════════════════════════════════════════
#  CASE CRUD
# ══════════════════════════════════════════════════════════════════

@router.get("/cases")
async def list_cases(
    industry: Optional[str] = None,
    budget_tier: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Case)
    if industry:
        query = query.where(Case.industry.ilike(f"%{industry}%"))
    if budget_tier:
        query = query.where(Case.budget_tier == budget_tier)
    query = query.order_by(Case.brand)
    result = await db.execute(query)
    return [
        {
            "case_id": c.case_id, "brand": c.brand, "campaign_title": c.campaign_title,
            "industry": c.industry, "target": c.target,
            "applied_methods": c.applied_methods, "budget_tier": c.budget_tier,
            "has_embedding": c.embedding is not None,
        }
        for c in result.scalars().all()
    ]


@router.get("/cases/{case_id}")
async def get_case_detail(case_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Case).where(Case.case_id == case_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Case not found")

    graph_methods = []
    similar_cases = []
    try:
        from app.services.graph import GraphService
        graph = GraphService()
        graph_methods = graph.find_methods_for_case(case_id)
        similar_cases = graph.find_similar_cases(case_id, limit=3)
    except Exception:
        pass

    return {
        "case_id": c.case_id, "brand": c.brand, "campaign_title": c.campaign_title,
        "industry": c.industry, "target": c.target,
        "problem": c.problem, "insight": c.insight, "solution": c.solution,
        "applied_methods": c.applied_methods, "key_channels": c.key_channels,
        "outcomes": c.outcomes, "budget_tier": c.budget_tier,
        "has_embedding": c.embedding is not None,
        "graph_methods": graph_methods,
        "similar_cases": similar_cases,
    }


@router.put("/cases/{case_id}")
async def update_case(case_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Case).where(Case.case_id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "Case not found")

    updatable = ["brand", "campaign_title", "industry", "target", "problem",
                  "insight", "solution", "applied_methods", "key_channels",
                  "outcomes", "budget_tier"]
    changed = False
    for key in updatable:
        if key in data:
            setattr(case, key, data[key])
            changed = True
    if changed:
        case.embedding = None
        await db.commit()
    return {"case_id": case.case_id, "updated": changed}


# ══════════════════════════════════════════════════════════════════
#  DIRECTOR CRUD
# ══════════════════════════════════════════════════════════════════

@router.get("/directors")
async def admin_list_directors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Director).order_by(Director.id))
    return [
        {
            "id": d.id, "name": d.name, "tagline": d.tagline,
            "archetype": d.archetype, "description": d.description,
            "recommended_for": d.recommended_for, "avoid_when": d.avoid_when,
            "weights": {
                "logic": d.w_logic, "emotion": d.w_emotion, "culture": d.w_culture,
                "action": d.w_action, "performance": d.w_performance,
            },
            "is_active": d.is_active,
        }
        for d in result.scalars().all()
    ]


# ══════════════════════════════════════════════════════════════════
#  SYSTEM HEALTH
# ══════════════════════════════════════════════════════════════════

@router.get("/health")
async def system_health(db: AsyncSession = Depends(get_db)):
    """Full system health check — PostgreSQL, Neo4j, Embedding coverage."""
    health = {"postgresql": False, "neo4j": False, "embedding": {}}

    try:
        m_count = (await db.execute(select(func.count()).select_from(Method))).scalar()
        c_count = (await db.execute(select(func.count()).select_from(Case))).scalar()
        d_count = (await db.execute(select(func.count()).select_from(Director))).scalar()
        health["postgresql"] = True
        health["data"] = {"methods": m_count, "cases": c_count, "directors": d_count}
    except Exception as e:
        health["pg_error"] = str(e)

    try:
        from app.services.graph import GraphService
        health["graph"] = GraphService().get_stats()
        health["neo4j"] = True
    except Exception as e:
        health["neo4j_error"] = str(e)

    try:
        from app.services.embedding import EmbeddingPipeline
        health["embedding"] = await EmbeddingPipeline(db).get_embedding_status()
    except Exception as e:
        health["embedding_error"] = str(e)

    return health
