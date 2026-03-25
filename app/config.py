"""
Application configuration using pydantic-settings.
Loads from environment variables or .env files.
"""

from pydantic_settings import BaseSettings
from typing import Optional, Literal


class Settings(BaseSettings):
    """Report Synthesis Agent configuration."""

    # --- LLM Provider ---
    LLM_PROVIDER: Literal["ollama", "openai", "anthropic", "groq", "grok"] = "ollama"

    # Ollama
    OLLAMA_BASE_URL: str = ""
    OLLAMA_MODEL: str = ""

    # Claude / Anthropic
    ANTHROPIC_API_KEY: Optional[str] = None
    CLAUDE_MODEL: Optional[str] = None

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: Optional[str] = None

    # Groq
    GROQ_API_KEY: Optional[str] = "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"
    XAI_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # --- Storage ---
    STORAGE_TYPE: Literal["local", "s3"] = "local"
    REPORT_OUTPUT_PATH: str = "./reports"
    USE_S3_STORAGE: bool = False
    S3_REPORTS_BUCKET: str = "gemrslize-reports"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_PRESIGNED_EXPIRY: int = 604800  # 7 days in seconds

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379"
    REPORT_CACHE_TTL: int = 3600  # 1 hour

    # --- Server ---
    PORT: int = 8006
    USE_DOCKER: bool = True
    USE_EC2: bool = False

    # --- Templates ---
    TEMPLATE_DIR: str = "app/templates"
    STATIC_DIR: str = "static"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()
