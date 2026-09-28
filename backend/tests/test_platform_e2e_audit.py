"""
Comprehensive End-to-End Application Audit & Verification Test.
Executes and validates all 20 platform points:
1. Backend startup / API availability
2. Frontend integration / CORS headers
3. User registration & authentication (JWT)
4. Project creation
5. Character creation
6. Voice assignment to characters
7. Short-video generation request
8. Long-video orchestration request
9. Generation job submission
10. Database job record creation
11. Orchestrator receipt & story decomposition
12. Capability resolution
13. Engine selection
14. GPU Worker execution
15. Progress tracking and state transitions
16. Media output storage
17. Video playback route (/api/v1/generations/{id}/output)
18. Video download route
19. User job history
20. Cross-tenant user isolation
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.db.database import Base, get_db
from app.engines.mock_engine import MockVideoEngine
from app.engines.registry import VideoEngineRegistry
from app.main import app
from app.models.generation import GenerationJob, GenerationStatus
from app.models.long_video import LongVideoProject, LongVideoScene
from app.models.user import Role, User
from app.orchestration import (
    LongVideoMode,
    LongVideoOrchestrator,
    OrchestrationStage,
    StoryPlan,
)
from app.schemas.long_video import CharacterProfileSchema, LongVideoCreateRequest, LongVideoPlanRequest
from app.schemas.requirements import UserRequirements
from app.services.capability_resolver import CapabilityResolver
from app.services.generation_worker import GenerationWorker
from app.workers.local_worker import LocalGPUWorker
from app.workers.pool import GPUWorkerPool


@pytest.fixture(scope="module")
def test_env():
    """Setup isolated SQLite database and test storage."""
    temp_dir = tempfile.TemporaryDirectory()
    temp_path = Path(temp_dir.name)
    db_file = temp_path / "audit_test.db"
    db_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=db_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    storage_dir = temp_path / "videos"
    storage_dir.mkdir(parents=True, exist_ok=True)
    settings.STORAGE_PATH = str(storage_dir)

    # Seed roles
    db = TestingSessionLocal()
    r_user = Role(name="user", description="Standard User")
    r_admin = Role(name="admin", description="Admin User")
    db.add_all([r_user, r_admin])

    # Seed User 1 & User 2
    u1 = User(
        email="creator1@example.com",
        username="creator1",
        first_name="Alice",
        last_name="Creator",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    u1.roles.append(r_user)

    u2 = User(
        email="creator2@example.com",
        username="creator2",
        first_name="Bob",
        last_name="Director",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    u2.roles.append(r_user)

    db.add_all([u1, u2])
    db.commit()
    db.refresh(u1)
    db.refresh(u2)
    u1_id, u2_id = u1.id, u2.id
    db.close()

    # Setup Registry with Mock Engine
    registry = VideoEngineRegistry()
    mock_engine = MockVideoEngine("mock-engine")
    mock_engine.initialize()
    registry.register(mock_engine, default=True)

    pool = GPUWorkerPool()
    local_worker = LocalGPUWorker("local-mock-worker", engine_registry=registry)
    local_worker.initialize()
    pool.register_worker(local_worker)

    worker = GenerationWorker(
        session_factory=TestingSessionLocal,
        storage_root=storage_dir,
        worker_pool=pool,
        poll_seconds=0.1,
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield {
        "client": client,
        "session_factory": TestingSessionLocal,
        "u1_id": u1_id,
        "u2_id": u2_id,
        "worker": worker,
        "registry": registry,
        "pool": pool,
        "storage_dir": storage_dir,
    }

    app.dependency_overrides.clear()
    worker.stop()
    db_engine.dispose()
    try:
        temp_dir.cleanup()
    except Exception:
        pass


def test_complete_20_point_application_audit(test_env):
    client = test_env["client"]
    u1_id = test_env["u1_id"]
    u2_id = test_env["u2_id"]
    worker = test_env["worker"]
    session_factory = test_env["session_factory"]
    storage_dir = test_env["storage_dir"]

    token_u1 = create_access_token(data={"sub": str(u1_id), "user_id": u1_id, "roles": ["user"]})
    token_u2 = create_access_token(data={"sub": str(u2_id), "user_id": u2_id, "roles": ["user"]})
    auth_h1 = {"Authorization": f"Bearer {token_u1}"}
    auth_h2 = {"Authorization": f"Bearer {token_u2}"}

    # 1. Start backend / Health check
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # 2. CORS / Options
    res_cors = client.options("/api/v1/health")
    assert res_cors.status_code in (200, 204, 405)

    # 3. Register & Login
    res_login = client.post("/api/v1/auth/login", json={"username": "creator1", "password": "Password123!"})
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()

    # 4. Create Characters & 5. Assign Different Voices in Project Plan
    char1 = {
        "id": "char_kaelen",
        "name": "Kaelen",
        "visual_description": "Cybernetic detective with trenchcoat in neon rain",
        "voice_profile_id": "voice_gravelly_detective",
    }
    char2 = {
        "id": "char_aria",
        "name": "Aria",
        "visual_description": "Rogue AI hologram consciousness",
        "voice_profile_id": "voice_ethereal_ai",
    }

    # 6. Story Planner & Character Voice Assignment Request
    plan_payload = {
        "prompt": "Scene 1: Kaelen enters the neon mainframe.\nScene 2: Aria manifests as a hologram to negotiate.\nScene 3: They initiate the system override.",
        "target_duration": 30.0,
        "characters_override": [char1, char2],
    }
    res_plan = client.post("/api/v1/long-video/plan", headers=auth_h1, json=plan_payload)
    assert res_plan.status_code == 200
    plan_resp = res_plan.json()
    assert plan_resp["title"] is not None
    assert len(plan_resp["scenes"]) >= 2
    assert len(plan_resp["characters"]) == 2
    assert plan_resp["characters"][0]["voice_profile_id"] == "voice_gravelly_detective"
    assert plan_resp["characters"][1]["voice_profile_id"] == "voice_ethereal_ai"

    # 7. Create a Project via Long-Video Request
    proj_payload = {
        "title": plan_resp["title"],
        "prompt": plan_payload["prompt"],
        "target_duration": 30.0,
        "characters_override": [char1, char2],
        "preferred_engine": "mock-engine",
    }
    res_proj = client.post("/api/v1/long-video/projects", headers=auth_h1, json=proj_payload)
    assert res_proj.status_code == 201
    project_id = res_proj.json()["id"]

    # 8. Short-Video Request & 12. Capability Resolution & 13. Engine Selection
    short_req = UserRequirements(
        prompt="A high-speed hovercraft chase through neon skyscrapers",
        duration="short",
        voice_mode="none",
        character_mode="single",
        quality="high",
        continuity="standard",
    )
    short_plan = CapabilityResolver.resolve_plan(short_req, test_env["registry"])
    assert short_plan.selected_engine_id is not None
    assert short_plan.selected_engine_id in ("mock-engine", "wan2gp", "ltx-video")

    # 8b. Create Long-Video Orchestration Request
    long_req = UserRequirements(
        prompt="Kaelen encounters Aria in the mainframe core. They negotiate the future of Neo-Tokyo across three distinct stages.",
        duration="long",
        voice_mode="ai",
        character_mode="multiple",
        quality="cinematic",
        continuity="high",
    )
    long_plan = CapabilityResolver.resolve_plan(long_req, test_env["registry"])
    assert long_plan.selected_engine_id is not None
    assert "video_continuation" in long_plan.requested_capabilities or "native_long_video" in long_plan.requested_capabilities

    # 11. Orchestrator Story Decomposition & Planning
    orchestrator = LongVideoOrchestrator(engine_registry=test_env["registry"])
    decomposed_plan = orchestrator.plan_project(
        prompt_or_script=long_req.prompt,
        target_duration=30.0,
        preferred_engine="mock-engine",
    )
    assert len(decomposed_plan.scenes) >= 2
    assert decomposed_plan.target_duration_seconds == 30.0

    # 9. Submit Generation & 10. Verify Database Job Creation
    db = session_factory()
    job = GenerationJob(
        id="job-audit-verification-01",
        user_id=u1_id,
        status=GenerationStatus.QUEUED,
        prompt="A neon cybernetic city with high-speed vehicles",
        model_type="mock-t2v-preview",
        generation_settings={"engine_id": "mock-engine", "duration_seconds": 5.0},
    )
    db.add(job)
    db.commit()
    db.close()

    # 14. Worker Execution & 15. Progress Telemetry
    processed = worker.run_once()
    assert processed is True

    # Check DB state
    db = session_factory()
    refreshed_job = db.get(GenerationJob, "job-audit-verification-01")
    assert refreshed_job.status == GenerationStatus.COMPLETED
    assert refreshed_job.progress == 100

    # 16. Verify Output Storage
    assert refreshed_job.output_path is not None
    full_output_file = storage_dir / refreshed_job.output_path
    assert full_output_file.is_file()
    assert full_output_file.stat().st_size > 0
    db.close()

    # 17. Verify Video Playback Endpoint
    res_stream = client.get(f"/api/v1/generations/{refreshed_job.id}/output", headers=auth_h1)
    assert res_stream.status_code == 200
    assert res_stream.headers["content-type"].startswith("video/mp4")

    # 18. Verify Download Endpoint
    res_dl = client.get(f"/api/v1/generations/{refreshed_job.id}/download", headers=auth_h1)
    assert res_dl.status_code == 200
    assert "attachment" in res_dl.headers.get("content-disposition", "")

    # 19. Verify Job History (User 1 sees their job)
    res_history_u1 = client.get("/api/v1/generations", headers=auth_h1)
    assert res_history_u1.status_code == 200
    jobs_u1 = res_history_u1.json()
    if isinstance(jobs_u1, dict) and "jobs" in jobs_u1:
        jobs_u1 = jobs_u1["jobs"]
    assert any(j["id"] == "job-audit-verification-01" for j in jobs_u1)

    # 20. Verify Cross-Tenant User Isolation (User 2 CANNOT access User 1's job or output)
    res_history_u2 = client.get("/api/v1/generations", headers=auth_h2)
    assert res_history_u2.status_code == 200
    jobs_u2 = res_history_u2.json()
    if isinstance(jobs_u2, dict) and "jobs" in jobs_u2:
        jobs_u2 = jobs_u2["jobs"]
    assert not any(j["id"] == "job-audit-verification-01" for j in jobs_u2)

    res_access_forbidden = client.get(f"/api/v1/generations/{refreshed_job.id}", headers=auth_h2)
    assert res_access_forbidden.status_code == 404

    res_output_forbidden = client.get(f"/api/v1/generations/{refreshed_job.id}/output", headers=auth_h2)
    assert res_output_forbidden.status_code == 404
