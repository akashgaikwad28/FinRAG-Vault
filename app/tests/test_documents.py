from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock
import pytest
import io
import uuid

from app.models.document import Document
from app.tests.test_roles import create_custom_user


@pytest.mark.asyncio
async def test_document_upload_analyst_success(client: TestClient, db_session: AsyncSession) -> None:
    """Verifies that Financial Analysts can upload files, initiating a background indexing task."""
    analyst = await create_custom_user(db_session, "analyst_jane", "jane@finrag.com", "Financial Analyst")
    
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "jane@finrag.com", "password": "Password123!"}
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Mock stream file operations in service layer to avoid actual disk writes during unit tests
    with patch("app.services.document_service.save_upload_file_chunked") as mock_save:
        mock_save.return_value = 1000
        
        file_data = io.BytesIO(b"Dummy financial audit contents")
        response = client.post(
            "/api/v1/documents/upload",
            headers=headers,
            data={
                "title": "Jane Audits Q1",
                "company_name": "Acme Corp",
                "document_type": "report"
            },
            files={"file": ("report.txt", file_data, "text/plain")}
        )
        
        assert response.status_code == 202
        json_data = response.json()
        assert json_data["success"] is True
        assert json_data["data"]["title"] == "Jane Audits Q1"
        assert json_data["data"]["company_name"] == "Acme Corp"
        assert json_data["data"]["status"] == "processing"


@pytest.mark.asyncio
async def test_document_upload_client_forbidden(client: TestClient, db_session: AsyncSession) -> None:
    """Asserts that Clients are completely blocked from uploading documents (HTTP 403)."""
    client_user = await create_custom_user(db_session, "client_alice", "alice@acme.com", "Client")
    
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@acme.com", "password": "Password123!"}
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    file_data = io.BytesIO(b"Dummy client upload contents")
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={
            "title": "Alice Client Doc",
            "company_name": "Acme Corp",
            "document_type": "report"
        },
        files={"file": ("report.txt", file_data, "text/plain")}
    )
    
    assert response.status_code == 403
    assert response.json()["success"] is False


@pytest.mark.asyncio
async def test_multitenant_isolation_document_list(client: TestClient, db_session: AsyncSession) -> None:
    """Asserts that Clients ONLY list documents belonging to their company boundary."""
    # 1. Create two Clients from different companies
    acme_client = await create_custom_user(
        db_session, "acme_bob", "bob@acme.com", "Client", company="Acme Corp"
    )
    globex_client = await create_custom_user(
        db_session, "globex_charlie", "charlie@globex.com", "Client", company="Globex"
    )
    
    # 2. Add two documents manually to SQLite DB (one for Acme, one for Globex)
    doc_acme = Document(
        id=uuid.uuid4(),
        title="Acme Secrets",
        filename="acme.txt",
        company_name="Acme Corp",
        document_type="report",
        status="indexed",
        storage_path="/tmp/acme.txt",
        uploaded_by=acme_client.id
    )
    doc_globex = Document(
        id=uuid.uuid4(),
        title="Globex Earnings",
        filename="globex.txt",
        company_name="Globex",
        document_type="report",
        status="indexed",
        storage_path="/tmp/globex.txt",
        uploaded_by=globex_client.id
    )
    db_session.add_all([doc_acme, doc_globex])
    await db_session.commit()
    
    # 3. Fetch list as Acme Client
    login_acme = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@acme.com", "password": "Password123!"}
    )
    token_acme = login_acme.json()["data"]["access_token"]
    headers_acme = {"Authorization": f"Bearer {token_acme}"}
    
    acme_list = client.get("/api/v1/documents", headers=headers_acme)
    assert acme_list.status_code == 200
    acme_data = acme_list.json()["data"]["items"]
    
    # Acme client should ONLY see the Acme document (Globex document is completely filtered out!)
    assert len(acme_data) == 1
    assert acme_data[0]["title"] == "Acme Secrets"
    assert acme_data[0]["company_name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_multitenant_isolation_document_detail(client: TestClient, db_session: AsyncSession) -> None:
    """Asserts that Clients are forbidden from loading document details of other companies."""
    # 1. Create two Clients from different companies
    acme_client = await create_custom_user(
        db_session, "acme_user", "acme@acme.com", "Client", company="Acme Corp"
    )
    globex_client = await create_custom_user(
        db_session, "globex_user", "globex@globex.com", "Client", company="Globex"
    )
    
    # 2. Manual SQLite inserts
    doc_globex = Document(
        id=uuid.uuid4(),
        title="Globex Sensitive Financials",
        filename="globex.txt",
        company_name="Globex",
        document_type="report",
        status="indexed",
        storage_path="/tmp/globex.txt",
        uploaded_by=globex_client.id
    )
    db_session.add(doc_globex)
    await db_session.commit()
    
    # 3. Log in as Acme Client and attempt to query Globex document detail
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "acme@acme.com", "password": "Password123!"}
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get(f"/api/v1/documents/{doc_globex.id}", headers=headers)
    
    # Strictly rejected!
    assert response.status_code == 403
    assert response.json()["success"] is False
    assert "Forbidden" in response.json()["message"]
