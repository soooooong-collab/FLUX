"""
FLUX v0.1 — AI Advertising Strategy & Concept Generation Service
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.database import engine, Base, close_neo4j

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    logger = logging.getLogger("flux.startup")

    # Startup: enable pgvector extension, then create tables
    async with engine.begin() as conn:
        try:
            from sqlalchemy import text
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass
        await conn.run_sync(Base.metadata.create_all)

    # Auto-check embedding coverage on startup
    try:
        from app.db.database import async_session
        from app.services.embedding import EmbeddingPipeline
        async with async_session() as db:
            pipeline = EmbeddingPipeline(db)
            status = await pipeline.get_embedding_status()
            m_pending = status["methods"]["pending"]
            c_pending = status["cases"]["pending"]
            if m_pending > 0 or c_pending > 0:
                logger.info(f"Pending embeddings: {m_pending} methods, {c_pending} cases")
                logger.info("Run POST /admin/embeddings/run to generate embeddings")
            else:
                logger.info("All embeddings up to date")
    except Exception as e:
        logger.warning(f"Embedding check skipped: {e}")

    yield
    # Shutdown
    await close_neo4j()
    await engine.dispose()


app = FastAPI(
    title="FLUX",
    description="AI-powered Advertising Strategy & Concept Generation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
from app.api.routes import auth, projects, pipeline, directors, admin  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
app.include_router(directors.router, prefix="/api/directors", tags=["directors"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "version": "0.1.0"}
