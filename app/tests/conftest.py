import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.api.deps.deps import get_db
from app.models.base import Base
from app.models.role import Role
from app.models.user import User
from app.core.security import get_password_hash

# 1. Setup in-memory SQLite for high-speed, zero-dependency testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Creates a session-wide event loop for running async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function", autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Drops and re-creates the SQLite database schemas for every test function isolated state."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a test database session."""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture(scope="function", autouse=True)
async def seed_test_roles(db_session: AsyncSession) -> None:
    """Pre-seeds mandatory roles into the test DB."""
    roles = [
        Role(name="Admin", description="Admin permissions"),
        Role(name="Financial Analyst", description="Analyst permissions"),
        Role(name="Auditor", description="Auditor permissions"),
        Role(name="Client", description="Client boundaries")
    ]
    db_session.add_all(roles)
    await db_session.commit()


@pytest.fixture(scope="function")
def client(db_session: AsyncSession) -> Generator[TestClient, None, None]:
    """FastAPI TestClient injecting the test SQLite database session."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function", autouse=True)
def mock_vector_service() -> Generator[AsyncMock, None, None]:
    """Mocks VectorService endpoints to prevent actual network calls to Qdrant."""
    with patch("app.services.rag_service.VectorService") as mock_vector, \
         patch("app.services.document_service.VectorService") as mock_doc_vector, \
         patch("app.api.routes.rag.VectorService") as mock_route_vector:
         
        # Mock search_similar_chunks return payload
        mock_candidates = [
            {
                "document_id": "11111111-1111-1111-1111-111111111111",
                "chunk_id": "c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1",
                "chunk_text": "Company revenue increased by 15% in Q1 2026.",
                "company_name": "Acme Corp",
                "document_type": "report",
                "uploaded_by": "22222222-2222-2222-2222-222222222222",
                "created_at": "2026-05-19T00:00:00Z",
                "chunk_index": 0,
                "title": "Q1 2026 Earnings Report"
            }
        ]
        
        mock_vector.search_similar_chunks.return_value = mock_candidates
        mock_vector.fetch_document_chunks.return_value = mock_candidates
        mock_vector.upsert_document_chunks.return_value = None
        mock_vector.delete_document_vectors.return_value = None
        
        yield mock_vector
