from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.role import Role
from app.core.security import get_password_hash
import pytest


async def create_custom_user(
    db_session: AsyncSession,
    username: str,
    email: str,
    role_name: str,
    company: str = "Acme Corp"
) -> User:
    """Helper method to construct active test accounts with designated roles."""
    query = select(Role).where(Role.name == role_name)
    result = await db_session.execute(query)
    role = result.scalar_one()
    
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash("Password123!"),
        company_name=company,
        is_active=True
    )
    user.roles.append(role)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_list_roles_admin_success(client: TestClient, db_session: AsyncSession) -> None:
    """Asserts that Admin users can pull all active system roles."""
    admin_user = await create_custom_user(db_session, "super_admin", "admin@finragvault.com", "Admin")
    
    # Authenticate as Admin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@finragvault.com", "password": "Password123!"}
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/v1/roles", headers=headers)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert len(json_data["data"]) == 4  # Admin, Analyst, Auditor, Client


@pytest.mark.asyncio
async def test_list_roles_client_forbidden(client: TestClient, db_session: AsyncSession) -> None:
    """Asserts that Client accounts are blocked from fetching role schemas."""
    client_user = await create_custom_user(db_session, "client_bob", "bob@acme.com", "Client")
    
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@acme.com", "password": "Password123!"}
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/v1/roles", headers=headers)
    assert response.status_code == 403
    assert response.json()["success"] is False
    assert "Forbidden" in response.json()["message"]


@pytest.mark.asyncio
async def test_create_role_admin_success(client: TestClient, db_session: AsyncSession) -> None:
    """Asserts that Admins can provision new security role names."""
    admin_user = await create_custom_user(db_session, "super_admin2", "admin2@finragvault.com", "Admin")
    
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin2@finragvault.com", "password": "Password123!"}
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post(
        "/api/v1/roles",
        json={"name": "Compliance Analyst", "description": "Review contracts and compliance"},
        headers=headers
    )
    assert response.status_code == 201
    assert response.json()["success"] is True
    assert response.json()["data"]["name"] == "Compliance Analyst"
