from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator
from app.core.config import settings

# Create async engine with robust connection pooling configurations
async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,      # Actively verify connections before using
    pool_size=20,            # Max connections in pool
    max_overflow=10,         # Max connection spikes
    echo=False,
)

# Async session maker configured for explicit commits/rollbacks
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects active after transaction commits
    autocommit=False,
    autoflush=False
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for injecting async database sessions into route controllers.
    
    Yields:
        AsyncSession: An isolated session with active transactions managed per request.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
