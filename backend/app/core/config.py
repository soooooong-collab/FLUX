"""
Application Settings — loaded from environment variables / .env file.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── App ──
    APP_ENV: str = "dev"
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    # ── Auth ──
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_EXPIRE_MINUTES: int = 1440

    # ── Database ──
    DATABASE_URL: str = "postgresql+asyncpg://flux:flux@localhost:5432/flux"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "fluxneo4j"
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── LLM ──
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # ── Embedding ──
    EMBEDDING_PROVIDER: str = "gemini"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSION: int = 768

    # ── Web Search ──
    SERPER_API_KEY: Optional[str] = None

    # ── Data ──
    RAW_DATA_DIR: str = "data/raw"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
