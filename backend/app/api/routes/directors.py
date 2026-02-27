"""
Directors routes — list available director personas.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.base import Director

router = APIRouter()


@router.get("")
async def list_directors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Director).where(Director.is_active == True).order_by(Director.id)
    )
    directors = result.scalars().all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "tagline": d.tagline,
            "archetype": d.archetype,
            "description": d.description,
            "recommended_for": d.recommended_for,
            "avoid_when": d.avoid_when,
            "weights": {
                "logic": d.w_logic,
                "emotion": d.w_emotion,
                "culture": d.w_culture,
                "action": d.w_action,
                "performance": d.w_performance,
            },
        }
        for d in directors
    ]
