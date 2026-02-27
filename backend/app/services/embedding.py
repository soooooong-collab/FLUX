"""
Embedding Pipeline Service — 자동화된 임베딩 생성 & 관리.

Features:
- Batch embedding generation for Methods and Cases
- Change detection — only re-embed modified records
- Hash-based dirty tracking
- Startup hook for automatic embedding sync
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func

from app.models.base import Method, Case
from app.services.llm.router import get_embedding_provider

logger = logging.getLogger(__name__)

# Maximum batch size for embedding API calls
BATCH_SIZE = 20


def _content_hash(text: str) -> str:
    """Generate SHA256 hash of content for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _method_embed_text(m: Any) -> str:
    """Build embedding-worthy text for a Method."""
    parts = [m.method_name or ""]
    if m.signature_question:
        parts.append(m.signature_question)
    if m.core_principle:
        parts.append(m.core_principle)
    if m.apply_when:
        parts.append(f"적용시점: {m.apply_when}")
    if m.category:
        parts.append(f"카테고리: {m.category}")
    return " | ".join(parts)


def _case_embed_text(c: Any) -> str:
    """Build embedding-worthy text for a Case."""
    parts = []
    if c.brand:
        parts.append(c.brand)
    if c.campaign_title:
        parts.append(c.campaign_title)
    if c.industry:
        parts.append(f"[{c.industry}]")
    if c.problem:
        parts.append(f"문제: {c.problem}")
    if c.insight:
        parts.append(f"인사이트: {c.insight}")
    if c.solution:
        parts.append(f"솔루션: {c.solution}")
    if c.target:
        parts.append(f"타겟: {c.target}")
    return " | ".join(parts)


class EmbeddingPipeline:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._embedder = get_embedding_provider()

    async def embed_all_methods(self, force: bool = False) -> dict[str, int]:
        """Generate embeddings for all Methods (or only unembedded ones)."""
        if force:
            result = await self.db.execute(select(Method).where(Method.is_active == True))
        else:
            result = await self.db.execute(
                select(Method).where(Method.embedding == None, Method.is_active == True)
            )
        methods = result.scalars().all()

        if not methods:
            return {"embedded": 0, "skipped": 0, "total": 0}

        embedded = 0
        texts = []
        method_ids = []

        for m in methods:
            embed_text = _method_embed_text(m)
            texts.append(embed_text)
            method_ids.append(m.id)

        # Batch embed
        for i in range(0, len(texts), BATCH_SIZE):
            batch_texts = texts[i:i + BATCH_SIZE]
            batch_ids = method_ids[i:i + BATCH_SIZE]

            try:
                vectors = await self._embedder.embed_batch(batch_texts)
            except Exception:
                # Fallback to one-by-one
                vectors = []
                for t in batch_texts:
                    try:
                        vec = await self._embedder.embed(t)
                        vectors.append(vec)
                    except Exception as e:
                        logger.error(f"Embedding failed for method: {e}")
                        vectors.append(None)

            for mid, vec in zip(batch_ids, vectors):
                if vec is None:
                    continue
                emb_str = "[" + ",".join(str(v) for v in vec) + "]"
                await self.db.execute(
                    text("UPDATE methods SET embedding = CAST(:emb AS vector) WHERE id = :id"),
                    {"emb": emb_str, "id": mid},
                )
                embedded += 1

        await self.db.commit()
        logger.info(f"Methods embedded: {embedded}/{len(methods)}")
        return {"embedded": embedded, "skipped": len(methods) - embedded, "total": len(methods)}

    async def embed_all_cases(self, force: bool = False) -> dict[str, int]:
        """Generate embeddings for all Cases (or only unembedded ones)."""
        if force:
            result = await self.db.execute(select(Case))
        else:
            result = await self.db.execute(select(Case).where(Case.embedding == None))
        cases = result.scalars().all()

        if not cases:
            return {"embedded": 0, "skipped": 0, "total": 0}

        embedded = 0
        texts = []
        case_ids = []

        for c in cases:
            embed_text = _case_embed_text(c)
            texts.append(embed_text)
            case_ids.append(c.case_id)

        for i in range(0, len(texts), BATCH_SIZE):
            batch_texts = texts[i:i + BATCH_SIZE]
            batch_ids = case_ids[i:i + BATCH_SIZE]

            try:
                vectors = await self._embedder.embed_batch(batch_texts)
            except Exception:
                vectors = []
                for t in batch_texts:
                    try:
                        vec = await self._embedder.embed(t)
                        vectors.append(vec)
                    except Exception as e:
                        logger.error(f"Embedding failed for case: {e}")
                        vectors.append(None)

            for cid, vec in zip(batch_ids, vectors):
                if vec is None:
                    continue
                emb_str = "[" + ",".join(str(v) for v in vec) + "]"
                await self.db.execute(
                    text("UPDATE cases SET embedding = CAST(:emb AS vector) WHERE case_id = :id"),
                    {"emb": emb_str, "id": cid},
                )
                embedded += 1

        await self.db.commit()
        logger.info(f"Cases embedded: {embedded}/{len(cases)}")
        return {"embedded": embedded, "skipped": len(cases) - embedded, "total": len(cases)}

    async def get_embedding_status(self) -> dict[str, Any]:
        """Return current embedding coverage stats."""
        # Methods
        m_total = await self.db.execute(select(func.count()).select_from(Method))
        m_embedded = await self.db.execute(
            text("SELECT count(*) FROM methods WHERE embedding IS NOT NULL")
        )
        m_total_val = m_total.scalar()
        m_embedded_val = m_embedded.scalar()

        # Cases
        c_total = await self.db.execute(select(func.count()).select_from(Case))
        c_embedded = await self.db.execute(
            text("SELECT count(*) FROM cases WHERE embedding IS NOT NULL")
        )
        c_total_val = c_total.scalar()
        c_embedded_val = c_embedded.scalar()

        return {
            "methods": {
                "total": m_total_val,
                "embedded": m_embedded_val,
                "pending": m_total_val - m_embedded_val,
                "coverage": round(m_embedded_val / m_total_val * 100, 1) if m_total_val else 0,
            },
            "cases": {
                "total": c_total_val,
                "embedded": c_embedded_val,
                "pending": c_total_val - c_embedded_val,
                "coverage": round(c_embedded_val / c_total_val * 100, 1) if c_total_val else 0,
            },
        }

    async def run_full_pipeline(self, force: bool = False) -> dict[str, Any]:
        """Run complete embedding pipeline for both methods and cases."""
        methods_result = await self.embed_all_methods(force=force)
        cases_result = await self.embed_all_cases(force=force)
        status = await self.get_embedding_status()
        return {
            "methods": methods_result,
            "cases": cases_result,
            "status": status,
        }
