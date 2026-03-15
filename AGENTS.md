# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

FLUX v0.1 is an AI-powered advertising strategy & concept generation service. It uses RAG with a 3-layer ontology (Methods → Cases → Directors) to generate ad campaign strategies through an 8-step pipeline, outputting presentation slides.

## Development Commands

```bash
# Infrastructure (PostgreSQL + pgvector, Neo4j, Redis)
docker compose up -d

# Backend (FastAPI, runs on :8000)
cd backend && PYTHONPATH=. uvicorn main:app --reload

# Frontend (Next.js, runs on :3000)
cd frontend && npm run dev

# Frontend lint
cd frontend && npm run lint

# Health check
curl http://localhost:8000/healthz

# Swagger UI
open http://localhost:8000/docs
```

## Architecture

### Stack

- **Frontend:** Next.js 14 + TypeScript + Tailwind CSS (custom `flux-*` color tokens)
- **Backend:** FastAPI (async) + SQLAlchemy 2.0 + asyncpg
- **Databases:** PostgreSQL (pgvector), Neo4j 5 (knowledge graph), Redis
- **LLMs:** Codex Sonnet 4 (steps s1,s3-s8), Gemini 2.5 Pro (s2 market analysis), Gemini text-embedding-004 (768-dim embeddings)

### 3-Layer Ontology

1. **Methods (Brain):** 61 strategy frameworks with vector embeddings → `methods` table
2. **Cases (Evidence):** 21 campaign case studies with embeddings → `cases` table
3. **Directors (Control):** 6 creative personas (strategist, provocateur, storyteller, emotional_minimalist, culture_hacker, performance_hacker) → `directors` table

### Pipeline Flow (8 Steps)

```text
Brief Input → Director Selection → Pipeline Execution (SSE) → Slides → PPTX Export

Phase 1 - Account Planner (Analysis):    s1: Campaign Goal, s2: Market Analysis, s3: Target Insight
Phase 2 - Brand Strategist (Strategy):   s4: Principal Competition, s5: Target Definition, s6: Winning Strategy
Phase 3 - Creative Director (Creative):  s7: Consumer Promise, s8: Creative Strategy
Final: Presentation Designer → slides_json
```

Each director archetype has a `case_timing` policy (YAML in `agents/policies/`) that controls which steps retrieve cases/methods via hybrid search.

### RAG Service (`services/rag.py`)

Hybrid retrieval: pgvector cosine similarity → Neo4j graph enrichment (co-occurrence, APPLIED_IN edges) → director preference boosting → re-ranked results.

### LLM Routing (`services/llm/router.py`)

Per-step model assignment with abstract `LLMProvider` interface. Providers: `Codex.py`, `gemini.py`, `openai_provider.py`.

### Key Backend Paths

- `agents/orchestrator.py` — Main pipeline orchestration, SSE event emission
- `agents/roles/` — Agent personas (account_planner, brand_strategist, creative_director, presentation_designer)
- `agents/tools/` — brief_parser (pdfplumber), web_search (Serper API), method/case_search
- `services/graph.py` — Neo4j ontology build (nodes: Method, Case, Director, Industry; edges: APPLIED_IN, PREFERS, SIMILAR_TO, RELATED_TO, IN_INDUSTRY)
- `services/embedding.py` — Batch embedding pipeline
- `prompts/*.md` — LLM system prompts per agent role
- `db/seed.py` — Data seeding from Excel files in `data/raw/`

### Key Frontend Paths

- `src/lib/api.ts` — API client (JWT auth via `flux_token` in localStorage, SSE streaming)
- `src/app/brief/page.tsx` — Brief input (manual form + PDF upload with drag-and-drop)
- `src/app/pipeline/page.tsx` — Real-time pipeline viewer (SSE streaming)
- `src/app/admin/page.tsx` — Admin panel (data sync, graph build, embeddings, health)

## Data Management

```bash
# Seed data from Excel files
POST /admin/sync

# Upload custom Excel
POST /admin/sync/upload?dataset=methods|cases|directors

# Build Neo4j knowledge graph
POST /admin/graph/build

# Generate vector embeddings
POST /admin/embeddings/run
```

Tables are auto-created on backend startup via `Base.metadata.create_all`. Manual migrations go in `backend/migrations/`.

## Environment

Backend config via `backend/app/core/config.py` (pydantic-settings). Required env vars: `DATABASE_URL`, `NEO4J_URI/USER/PASSWORD`, `REDIS_URL`, `JWT_SECRET_KEY`. LLM keys: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`. Optional: `SERPER_API_KEY` (web search), `OPENAI_API_KEY`.

Frontend: `NEXT_PUBLIC_API_BASE` (defaults to `http://localhost:8000`).

## Deployment

- **Backend:** Render (see `render.yaml`) — `PYTHONPATH=. uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Frontend:** Vercel (standard Next.js), standalone output mode
- **Docker:** `docker-compose.yml` for local databases only (app runs natively)

## Conventions

- UI is primarily in Korean
- All IDs are UUIDs generated via `core/security.py`
- Project status lifecycle: `draft → running → completed | failed`
- PDF briefs store extracted text in `brief_raw_text` field; when present, pipeline uses it as primary context instead of individual form fields
- Tailwind custom colors: `flux-dark` (#1A1A2E), `flux-accent` (#FF6B35), `flux-surface` (#0F3460), `flux-muted` (#E2E8F0)
