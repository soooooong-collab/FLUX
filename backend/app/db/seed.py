"""
Data Seed — Excel → PostgreSQL.
Loads Method_Cards, Case_graph, and director_profiles into DB.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import async_session, engine, Base
from app.models.base import Method, Case, Director

settings = get_settings()
RAW_DIR = Path(settings.RAW_DATA_DIR)


def _split_csv(val) -> list[str] | None:
    """Split comma-separated string into list, or return None."""
    if pd.isna(val) or not str(val).strip():
        return None
    return [v.strip() for v in str(val).split(",") if v.strip()]


async def seed_methods(db: AsyncSession) -> int:
    path = RAW_DIR / "Method_Cards_251119.xlsx"
    if not path.exists():
        print(f"  [SKIP] {path} not found")
        return 0

    df = pd.read_excel(path)
    count = 0
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
    return count


async def seed_cases(db: AsyncSession) -> int:
    path = RAW_DIR / "Case_graph_251125.xlsx"
    if not path.exists():
        print(f"  [SKIP] {path} not found")
        return 0

    df = pd.read_excel(path)
    count = 0
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
    return count


async def seed_directors(db: AsyncSession) -> int:
    path = RAW_DIR / "director_profiles_v2_populated.xlsx"
    if not path.exists():
        print(f"  [SKIP] {path} not found")
        return 0

    df = pd.read_excel(path)
    count = 0
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
                # Avoid precision mismatch with floats if they are roughly similar
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
    return count


async def run_seed():
    """Run all seed operations."""
    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    async with async_session() as db:
        print("[SEED] Methods...")
        m = await seed_methods(db)
        print(f"  → {m} methods inserted")

        print("[SEED] Cases...")
        c = await seed_cases(db)
        print(f"  → {c} cases inserted")

        print("[SEED] Directors...")
        d = await seed_directors(db)
        print(f"  → {d} directors inserted")

    print("[SEED] Done.")


if __name__ == "__main__":
    asyncio.run(run_seed())
