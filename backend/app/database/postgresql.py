from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from config import settings
from app.models.postgresql_models import Base


# Sync engine for Celery workers
sync_engine = create_engine(settings.postgres_url)

# Async engine for FastAPI (lazy import to avoid import errors)
try:
    from sqlalchemy.ext.asyncio import create_async_engine
    async_database_url = settings.postgres_url.replace("postgresql://", "postgresql+asyncpg://")
    async_engine = create_async_engine(async_database_url, echo=False)
except Exception:
    # Fallback if asyncpg not installed
    async_engine = None

# Session makers
# Sync session maker for synchronous operations
SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# Async session maker for FastAPI
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


def init_db():
    """Initialize ALL database tables (production + staging + spendsense)"""
    from app.models.staging_models import Base as StagingBase
    from app.models.spendsense_models import Base as SpendSenseBase
    
    # Initialize production tables
    Base.metadata.create_all(sync_engine)
    print("✅ Production tables initialized")
    
    # Initialize staging tables
    StagingBase.metadata.create_all(sync_engine)
    print("✅ Staging tables initialized")
    
    # Initialize SpendSense tables
    SpendSenseBase.metadata.create_all(sync_engine)
    print("✅ SpendSense tables initialized")
    
    print("✅ All database tables created successfully")


async def get_db():
    """Dependency for getting async database session"""
    async with AsyncSessionLocal() as session:
        yield session

