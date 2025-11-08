import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: Optional[str] = "mongodb://localhost:27017"
    mongodb_db_name: str = "monytix_rawdata"
    
    # Supabase (supports both SUPABASE_URL and supabase_url from env)
    supabase_url: Optional[str] = "https://your-project.supabase.co"
    supabase_key: Optional[str] = "your-supabase-anon-key"
    
    # PostgreSQL
    postgres_url: Optional[str] = "postgresql://localhost:5432/monytix"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Gmail API
    gmail_client_id: Optional[str] = None
    gmail_client_secret: Optional[str] = None
    gmail_redirect_uri: Optional[str] = "http://localhost:8000/auth/google/callback"
    
    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    # JWT
    jwt_secret_key: Optional[str] = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    
    # Environment
    environment: str = "development"
    
    # Ingest mode: "mongo_first" or "direct_pg"
    ingest_mode: str = os.getenv("INGEST_MODE", "mongo_first")
    
    # S3 configuration (optional, for file storage)
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    s3_region: str = os.getenv("S3_REGION", "us-east-1")
    
    # PDF parsing engine
    pdf_engine: str = os.getenv("PDF_ENGINE", "fitz")  # "fitz" (PyMuPDF) or "pdfminer"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields


settings = Settings()

