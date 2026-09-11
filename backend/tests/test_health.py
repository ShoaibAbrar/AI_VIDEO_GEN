"""Tests for health check endpoint."""

import pytest


def test_health_check(client):
    """Test health check endpoint returns healthy status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "database" in data
    assert data["status"] in ["healthy", "degraded"]
    assert data["database"] in ["healthy", "unhealthy"]


def test_root_endpoint(client):
    """Test root endpoint returns API information."""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "docs" in data
