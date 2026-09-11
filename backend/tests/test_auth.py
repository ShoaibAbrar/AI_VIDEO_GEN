import pytest
from fastapi.testclient import TestClient


def test_register_and_login_flow(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "strongpass123",
            "first_name": "Alice",
            "last_name": "User",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert "id" in body

    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": "alice",
            "password": "strongpass123",
        },
    )
    assert login.status_code == 200, login.text
    token_data = login.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert me.status_code == 200, me.text
    assert me.json()["username"] == "alice"


def test_login_with_bad_password(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "bob",
            "email": "bob@example.com",
            "password": "strongpass123",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "bob",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401


def test_refresh_token_flow(client: TestClient):
    register = client.post(
        "/api/v1/auth/register",
        json={
            "username": "charlie",
            "email": "charlie@example.com",
            "password": "strongpass123",
        },
    )
    assert register.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={
            "username": "charlie",
            "password": "strongpass123",
        },
    )
    refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    assert refresh.status_code == 200, refresh.text
    payload = refresh.json()
    assert "access_token" in payload
    assert payload["token_type"] == "bearer"
