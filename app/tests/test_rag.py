from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, AsyncMock
import pytest
import uuid

from app.models.document import Document
from app.tests.test_roles import create_custom_user


@pytest.mark.asyncio
async def test_semantic_search_analyst_success(client: TestClient, db_session: AsyncSession) -> None:
    """Verifies that Financial Analysts can perform semantic search queries."""
    analyst = await create_custom_user(db_session, "analyst_jane", "jane@finrag.com", "Financial Analyst")
    
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "jane@finrag.com", "password": "Password123!"}
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Pre-populate relational DB with document matching mock vector database candidates
    doc_acme = Document(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        title="Q1 2026 Earnings Report",
        filename="acme.txt",
        company_name="Acme Corp",
        document_type="report",
        status="indexed",
        storage_path="/tmp/acme.txt",
        uploaded_by=analyst.id
    )
    db_session.add(doc_acme)
    await db_session.commit()
    
    # Mock CPU-heavy Embedding and Reranking predictions in service layer
    with patch("app.services.embedding_service.EmbeddingService.generate_query_embedding_async") as mock_embed, \
         patch("app.services.rerank_service.RerankService.rerank_candidates_async") as mock_rerank:
         
        mock_embed.return_value = [0.1] * 384
        
        # Mock cross-encoder sorted output candidate chunks
        mock_rerank.return_value = [
            {
                "document_id": "11111111-1111-1111-1111-111111111111",
                "chunk_id": "c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1",
                "chunk_text": "Company revenue increased by 15% in Q1 2026.",
                "company_name": "Acme Corp",
                "document_type": "report",
                "uploaded_by": str(analyst.id),
                "created_at": "2026-05-19T00:00:00Z",
                "chunk_index": 0,
                "title": "Q1 2026 Earnings Report",
                "score": 0.895
            }
        ]
        
        response = client.post(
            "/api/v1/rag/search",
            headers=headers,
            json={"query": "What was the revenue increase in Q1 2026?"}
        )
        
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["success"] is True
        assert len(json_data["data"]) == 1
        assert json_data["data"][0]["chunk_text"] == "Company revenue increased by 15% in Q1 2026."
        assert json_data["data"][0]["score"] == 0.895
        assert json_data["data"][0]["title"] == "Q1 2026 Earnings Report"


@pytest.mark.asyncio
async def test_semantic_search_client_isolation(client: TestClient, db_session: AsyncSession) -> None:
    """Verifies that Clients are isolated and can only query vectors for their company."""
    # Create client from Globex Corp
    globex_client = await create_custom_user(
        db_session, "globex_user", "globex@globex.com", "Client", company="Globex"
    )
    
    # 2. Add two documents to PostgreSQL (Acme and Globex)
    doc_acme = Document(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        title="Q1 2026 Earnings Report",
        filename="acme.txt",
        company_name="Acme Corp",
        document_type="report",
        status="indexed",
        storage_path="/tmp/acme.txt",
        uploaded_by=globex_client.id
    )
    doc_globex = Document(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        title="Globex Earnings Report",
        filename="globex.txt",
        company_name="Globex",
        document_type="report",
        status="indexed",
        storage_path="/tmp/globex.txt",
        uploaded_by=globex_client.id
    )
    db_session.add_all([doc_acme, doc_globex])
    await db_session.commit()
    
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "globex@globex.com", "password": "Password123!"}
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # When Globex Client searches, the vector service gets called with company_name="Globex" filter!
    with patch("app.services.embedding_service.EmbeddingService.generate_query_embedding_async") as mock_embed, \
         patch("app.services.vector_service.VectorService.search_similar_chunks") as mock_search, \
         patch("app.services.rerank_service.RerankService.rerank_candidates_async") as mock_rerank:
         
        mock_embed.return_value = [0.1] * 384
        mock_search.return_value = []  # No candidates returned for simplicity
        
        response = client.post(
            "/api/v1/rag/search",
            headers=headers,
            json={"query": "debt risk"}
        )
        
        assert response.status_code == 200
        # Check that VectorService was queried with company_name="Globex" filter injection!
        mock_search.assert_called_once_with(
            vector=[0.1] * 384,
            limit=20,
            company_name="Globex",
            document_type=None,
            uploaded_by=None,
            start_date=None,
            end_date=None
        )
