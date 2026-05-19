from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User


def test_auth_registration(client: TestClient) -> None:
    """Verifies that new Client accounts can be registered through JSON payloads."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "jane_doe",
            "email": "jane@finragvault.com",
            "password": "Password123!",
            "company_name": "Acme Corp"
        }
    )
    
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["message"] == "User registered successfully"
    assert json_data["data"]["username"] == "jane_doe"
    assert json_data["data"]["email"] == "jane@finragvault.com"
    assert "id" in json_data["data"]


def test_auth_registration_validation(client: TestClient) -> None:
    """Asserts that bad emails or short passwords fail Pydantic validation."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "jd",
            "email": "bad-email",
            "password": "short",
            "company_name": "Acme Corp"
        }
    )
    assert response.status_code == 422
    assert response.json()["success"] is False
    assert len(response.json()["errors"]) > 0


def test_auth_login_and_profile(client: TestClient) -> None:
    """Tests the full register -> login -> profile query sequence."""
    # 1. Register a user
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "login_user",
            "email": "login@finragvault.com",
            "password": "Password123!",
            "company_name": "Acme Corp"
        }
    )
    
    # 2. Login
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@finragvault.com",
            "password": "Password123!"
        }
    )
    assert login_response.status_code == 200
    token_data = login_response.json()["data"]
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    
    # 3. Retrieve user profile details using the token
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    profile_response = client.get("/api/v1/users/me", headers=headers)
    assert profile_response.status_code == 200
    profile_data = profile_response.json()["data"]
    assert profile_data["username"] == "login_user"
    assert profile_data["company_name"] == "Acme Corp"
    assert len(profile_data["roles"]) > 0
    assert profile_data["roles"][0]["name"] == "Client"


def test_unauthenticated_guard(client: TestClient) -> None:
    """Asserts that requests lacking the Bearer header are rejected with HTTP 401."""
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
