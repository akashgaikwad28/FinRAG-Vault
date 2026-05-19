from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import os


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "FinRAG Vault"
    PROJECT_NAME: str = "FinRAG Vault"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    
    # CORS Settings
    ALLOWED_ORIGINS: List[str] = ["*"]
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    
    # Database Settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/finragvault"
    
    # JWT Settings
    SECRET_KEY: str = "your-super-secret-key-change-in-production-must-be-very-long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Qdrant Settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "financial_documents"
    
    # File Storage Settings
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10485760  # 10 MB in bytes
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "txt"]
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    ]
    
    # ML Models Settings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # Rate Limiting Settings
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_LOGIN: str = "10/minute"
    RATE_LIMIT_UPLOAD: str = "5/minute"
    RATE_LIMIT_DURATION: int = 60
    RATE_LIMIT_MAX_REQUESTS: int = 100
    
    # Logging
    LOG_LEVEL: str = "INFO"

    def __init__(self, **values):
        super().__init__(**values)
        # Automatically convert postgresql:// to postgresql+asyncpg:// for SQLAlchemy async engine compatibility
        if self.DATABASE_URL and self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Returns a cached singleton of Settings loaded from .env and system environments."""
    return Settings()


settings = get_settings()