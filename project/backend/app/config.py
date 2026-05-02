"""Application configuration management"""
import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # App
    APP_NAME: str = "GenomePipe Pro"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(False, validation_alias="GENOMEPIPE_DEBUG")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = False

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/genomepipe",
    )
    DB_ECHO: bool = False

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_EXPIRE_SECONDS: int = 3600

    # JWT
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "your-secret-key-change-in-production"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Celery
    CELERY_BROKER_URL: str = os.getenv(
        "CELERY_BROKER_URL", "redis://localhost:6379/1"
    )
    CELERY_RESULT_BACKEND: str = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/2"
    )

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD_SECONDS: int = 60
    AUTHENTICATED_RATE_LIMIT_REQUESTS: int = 1000

    # External APIs
    ESMATLAS_API_URL: str = "https://api.esmatlas.com/foldSequence/v1/pdb/"
    ESMATLAS_TIMEOUT: int = 300
    MAX_PROTEIN_LENGTH: int = 400

    # File Upload
    MAX_FILE_SIZE_MB: int = 100
    UPLOAD_DIR: str = "./uploads"
    ALLOWED_EXTENSIONS: list[str] = ["fasta", "fq", "fastq", "fa", "txt"]

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://localhost:8080",
        "https://genomepipe-pro.vercel.app",
    ]

    # Sentry (Error Tracking)
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create upload directory if it doesn't exist
def init_upload_dir():
    """Initialize upload directory"""
    settings = get_settings()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
