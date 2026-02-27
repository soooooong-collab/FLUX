"""
RAG Service — Hybrid Search (Vector + Graph) for Methods & Cases.

Phase 2 Upgrade:
- Vector search via pgvector (cosine similarity)
- Graph enrichment via Neo4j (relationship traversal)
- Re-ranking: combine vector score + graph relevance
- Director-aware method boosting
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.llm.router import get_embedding_provider

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._embedder = get_embedding_provider()
        self._graph = None

    def _get_graph(self):
        if self._graph is None:
            try:
                from app.services.graph import GraphService
                self._graph = GraphService()
            except Exception:
                self._graph = None
        return self._graph

    # ══════════════════════════════════════════════════════════════════
    #  VECTOR SEARCH (pgvector)
    # ══════════════════════════════════════════════════════════════════

    async def _vector_search_methods(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Pure vector search for Methods."""
        vec = await self._embedder.embed(query)
        embedding_str = "[" + ",".join(str(v) for v in vec) + "]"

        sql = text("""
            SELECT id, method_name, category, signature_question,
                   core_principle, apply_when, avoid_when, risk_factors,
                   1 - (embedding <=> CAST(:emb AS vector)) AS similarity
            FROM methods
            WHERE embedding IS NOT NULL AND is_active = true
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """)
        result = await self.db.execute(sql, {"emb": embedding_str, "k": top_k})
        return [
            {
                "id": r.id,
                "method_name": r.method_name,
                "category": r.category,
                "signature_question": r.signature_question,
                "core_principle": r.core_principle,
                "apply_when": r.apply_when,
                "avoid_when": r.avoid_when,
                "risk_factors": r.risk_factors,
                "similarity": float(r.similarity),
                "source": "vector",
            }
            for r in result.fetchall()
        ]

    async def _vector_search_cases(
        self, query: str, top_k: int = 5, industry: str | None = None,
    ) -> list[dict[str, Any]]:
        """Pure vector search for Cases."""
        vec = await self._embedder.embed(query)
        embedding_str = "[" + ",".join(str(v) for v in vec) + "]"

        where = "embedding IS NOT NULL"
        params: dict[str, Any] = {"emb": embedding_str, "k": top_k}
        if industry:
            where += " AND industry ILIKE :industry"
            params["industry"] = f"%{industry}%"

        sql = text(f"""
            SELECT case_id, brand, campaign_title, industry, target,
                   problem, insight, solution, applied_methods,
                   key_channels, outcomes, budget_tier,
                   1 - (embedding <=> CAST(:emb AS vector)) AS similarity
            FROM cases
            WHERE {where}
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """)
        result = await self.db.execute(sql, params)
        return [
            {
                "case_id": r.case_id,
                "brand": r.brand,
                "campaign_title": r.campaign_title,
                "industry": r.industry,
                "target": r.target,
                "problem": r.problem,
                "insight": r.insight,
                "solution": r.solution,
                "applied_methods": r.applied_methods,
                "key_channels": r.key_channels,
                "outcomes": r.outcomes,
                "budget_tier": r.budget_tier,
                "similarity": float(r.similarity),
                "source": "vector",
            }
            for r in result.fetchall()
        ]

    # ══════════════════════════════════════════════════════════════════
    #  HYBRID SEARCH (Vector + Graph)
    # ══════════════════════════════════════════════════════════════════

    async def retrieve_methods(
        self,
        query: str,
        top_k: int = 3,
        director_archetype: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Hybrid method retrieval:
        1. Vector search → top candidates
        2. Graph enrichment → related methods via co-occurrence
        3. Director boost → if director_archetype specified, boost preferred methods
        4. Re-rank and deduplicate
        """
        # Step 1: Vector search (wider pool)
        vector_results = await self._vector_search_methods(query, top_k=top_k * 2)

        graph = self._get_graph()
        if not graph:
            return vector_results[:top_k]

        # Step 2: Graph enrichment — find related methods for top results
        graph_bonus: dict[str, float] = {}
        for vr in vector_results[:3]:  # only expand top 3
            try:
                related = graph.find_related_methods(vr["method_name"], limit=3)
                for rel in related:
                    name = rel["method_name"]
                    co_occ = rel.get("co_occurrence", 1)
                    bonus = min(co_occ * 0.05, 0.15)  # max 0.15 bonus
                    graph_bonus[name] = max(graph_bonus.get(name, 0), bonus)
            except Exception:
                pass

        # Step 3: Director preference boost
        director_boost: dict[str, float] = {}
        if director_archetype:
            try:
                preferred = graph.find_preferred_methods(director_archetype, limit=15)
                for pref in preferred:
                    name = pref["method_name"]
                    weight = pref.get("weight", 0)
                    director_boost[name] = weight * 0.1  # max ~0.1 boost
            except Exception:
                pass

        # Step 4: Re-rank
        seen = set()
        scored = []
        for vr in vector_results:
            name = vr["method_name"]
            if name in seen:
                continue
            seen.add(name)

            final_score = vr["similarity"]
            final_score += graph_bonus.get(name, 0)
            final_score += director_boost.get(name, 0)

            vr["final_score"] = round(final_score, 4)
            vr["graph_boost"] = round(graph_bonus.get(name, 0), 4)
            vr["director_boost"] = round(director_boost.get(name, 0), 4)
            scored.append(vr)

        # Add graph-discovered methods not in vector results
        for name, bonus in graph_bonus.items():
            if name not in seen and bonus >= 0.1:
                scored.append({
                    "method_name": name,
                    "category": None,
                    "signature_question": None,
                    "core_principle": None,
                    "apply_when": None,
                    "avoid_when": None,
                    "risk_factors": None,
                    "similarity": 0.0,
                    "final_score": bonus,
                    "graph_boost": bonus,
                    "director_boost": director_boost.get(name, 0),
                    "source": "graph",
                })
                seen.add(name)

        scored.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return scored[:top_k]

    async def retrieve_cases(
        self,
        query: str,
        top_k: int = 3,
        industry: str | None = None,
        method_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Hybrid case retrieval:
        1. Vector search → semantic similarity
        2. Graph search → cases linked to specific methods
        3. Similar cases expansion via SIMILAR_TO edges
        4. Merge, deduplicate, re-rank
        """
        # Step 1: Vector search
        vector_results = await self._vector_search_cases(query, top_k=top_k * 2, industry=industry)

        graph = self._get_graph()
        if not graph:
            return vector_results[:top_k]

        # Step 2: Graph-based case discovery via method links
        graph_cases: dict[str, dict] = {}
        if method_names:
            for method_name in method_names[:3]:
                try:
                    linked_cases = graph.find_cases_by_method(method_name, limit=3)
                    for lc in linked_cases:
                        cid = lc["case_id"]
                        if cid not in graph_cases:
                            graph_cases[cid] = {**lc, "graph_score": 0.2, "source": "graph_method"}
                        else:
                            graph_cases[cid]["graph_score"] += 0.1
                except Exception:
                    pass

        # Step 3: Similar cases expansion
        similar_bonus: dict[str, float] = {}
        for vr in vector_results[:2]:
            try:
                similars = graph.find_similar_cases(vr["case_id"], limit=3)
                for sim in similars:
                    cid = sim["case_id"]
                    score = sim.get("score", 0)
                    similar_bonus[cid] = max(similar_bonus.get(cid, 0), score * 0.2)
            except Exception:
                pass

        # Step 4: Merge and re-rank
        seen = set()
        scored = []

        for vr in vector_results:
            cid = vr["case_id"]
            if cid in seen:
                continue
            seen.add(cid)

            final_score = vr["similarity"]
            final_score += similar_bonus.get(cid, 0)
            if cid in graph_cases:
                final_score += graph_cases[cid].get("graph_score", 0)

            vr["final_score"] = round(final_score, 4)
            scored.append(vr)

        # Add graph-only cases not found by vector search
        for cid, gc in graph_cases.items():
            if cid not in seen:
                gc["final_score"] = gc.get("graph_score", 0.1) + similar_bonus.get(cid, 0)
                scored.append(gc)
                seen.add(cid)

        scored.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return scored[:top_k]

    # ══════════════════════════════════════════════════════════════════
    #  CONVENIENCE — 단순 검색 (Phase 1 호환)
    # ══════════════════════════════════════════════════════════════════

    async def simple_method_search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Vector-only method search (backward compatible)."""
        return await self._vector_search_methods(query, top_k=top_k)

    async def simple_case_search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Vector-only case search (backward compatible)."""
        return await self._vector_search_cases(query, top_k=top_k)
