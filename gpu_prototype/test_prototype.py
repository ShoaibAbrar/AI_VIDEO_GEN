"""Lightweight unit tests for the GPU prototype API."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from gpu_prototype.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "gpu" in data
    assert "cuda_available" in data["gpu"]


def test_models_endpoint():
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "unavailable" in data
    assert "setup_command" in data
    assert "python scripts/download_model.py" in data["setup_command"]


def test_generate_request_validation():
    # Blank prompt -> 422
    response = client.post("/api/generate", json={"prompt": "   ", "frames": 33, "steps": 20})
    assert response.status_code == 422

    # Steps out of range -> 422
    response = client.post("/api/generate", json={"prompt": "Valid prompt", "steps": 0})
    assert response.status_code == 422


def test_generate_unavailable_model_behavior():
    # Attempt generating with a non-existent or unavailable model
    response = client.post("/api/generate", json={"prompt": "Test prompt", "model": "non_existent_model_xyz"})
    assert response.status_code == 503
    data = response.json()
    assert "detail" in data
    detail = data["detail"]
    assert "download_model.py" in detail or "PyTorch is not installed" in detail or "unavailable" in detail.lower()
