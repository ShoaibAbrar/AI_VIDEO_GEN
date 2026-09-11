"""GPU-free Phase 4 API and worker tests using a service-shaped fake."""

from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker

from app.api import generations
from app.models.generation import GenerationJob, GenerationStatus
from app.models.user import User
from app.services.generation_worker import GenerationWorker
from app.services.wan2gp_service import Wan2GPProgress


class FakeService:
    def validate_generation(self, payload):
        if payload["model_type"] != "fake-video":
            raise ValueError("Unknown Wan2GP model")
        return {**payload, "model_type": "fake-video"}

    def list_models(self):
        return [{"model_type": "fake-video", "name": "Fake Video", "availability": {"available": True}}]


class FakeWorker:
    def __init__(self):
        self.wake_count = 0

    def wake(self):
        self.wake_count += 1


class FakeResult:
    def __init__(self, path=None, success=True, errors=()):
        self.success = success
        self.generated_files = [] if path is None else [str(path)]
        self.artifacts = ()
        self.errors = errors


class FakeWan2GP:
    def __init__(self, output_path, failures=0):
        self.output_path = Path(output_path)
        self.failures = failures
        self.submitted = 0

    def submit_generation(self, settings, on_progress):
        self.submitted += 1
        on_progress(Wan2GPProgress(progress=40, current_step=4, total_steps=10, phase="inference", status="Generating"))
        return SimpleNamespace()

    def wait_for_result(self, handle):
        if self.failures:
            self.failures -= 1
            return FakeResult(success=False, errors=("mock failure",))
        return FakeResult(self.output_path)

    def shutdown(self):
        pass


def auth_token(client, username, email):
    client.post("/api/v1/auth/register", json={"username": username, "email": email, "password": "strongpass123"})
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "strongpass123"})
    return response.json()["access_token"]


def test_generation_request_is_queued_and_user_isolation(client):
    fake_service = FakeService()
    fake_worker = FakeWorker()
    from app.main import app
    app.dependency_overrides[generations.get_wan2gp_service] = lambda: fake_service
    app.dependency_overrides[generations.get_generation_worker] = lambda: fake_worker

    try:
        token_a = auth_token(client, "phase4a", "phase4a@example.com")
        token_b = auth_token(client, "phase4b", "phase4b@example.com")
        payload = {"prompt": "a quiet lake", "model_type": "fake-video", "video_length": 17, "num_inference_steps": 4, "seed": 2}
        created = client.post("/api/v1/generations", headers={"Authorization": f"Bearer {token_a}"}, json=payload)
        assert created.status_code == 202, created.text
        assert created.json()["status"] == "QUEUED"
        assert fake_worker.wake_count == 1

        job_id = created.json()["id"]
        hidden = client.get(f"/api/v1/generations/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert hidden.status_code == 404
        listed = client.get("/api/v1/generations", headers={"Authorization": f"Bearer {token_b}"})
        assert listed.status_code == 200
        assert listed.json() == []
    finally:
        app.dependency_overrides.clear()


def test_generation_rejects_unknown_model_and_extra_parameter(client):
    from app.main import app
    app.dependency_overrides[generations.get_wan2gp_service] = lambda: FakeService()
    app.dependency_overrides[generations.get_generation_worker] = lambda: FakeWorker()
    try:
        token = auth_token(client, "phase4invalid", "phase4invalid@example.com")
        unknown = client.post(
            "/api/v1/generations",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "test", "model_type": "missing", "video_length": 17, "num_inference_steps": 4},
        )
        assert unknown.status_code == 422
        extra = client.post(
            "/api/v1/generations",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "test", "model_type": "fake-video", "video_length": 17, "num_inference_steps": 4, "command": "rm -rf /"},
        )
        assert extra.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_queued_generation_can_be_cancelled(client):
    from app.main import app
    app.dependency_overrides[generations.get_wan2gp_service] = lambda: FakeService()
    app.dependency_overrides[generations.get_generation_worker] = lambda: FakeWorker()
    try:
        token = auth_token(client, "phase4cancel", "phase4cancel@example.com")
        created = client.post(
            "/api/v1/generations",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "test", "model_type": "fake-video", "video_length": 17, "num_inference_steps": 4},
        )
        cancelled = client.post(f"/api/v1/generations/{created.json()['id']}/cancel", headers={"Authorization": f"Bearer {token}"})
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLED"
    finally:
        app.dependency_overrides.clear()


def test_worker_completes_and_stores_output(db, tmp_path):
    user = User(username="workeruser", email="worker@example.com", hashed_password="hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    source = tmp_path / "wan-output.mp4"
    source.write_bytes(b"fake video")
    job = GenerationJob(
        id="job-complete",
        user_id=user.id,
        status=GenerationStatus.QUEUED,
        prompt="test",
        model_type="fake-video",
        generation_settings={"model_type": "fake-video", "prompt": "test"},
    )
    db.add(job)
    db.commit()

    service = FakeWan2GP(source)
    worker = GenerationWorker(sessionmaker(bind=db.get_bind()), service, tmp_path / "storage")
    assert worker.run_once() is True
    updated = db.get(GenerationJob, "job-complete")
    assert updated.status == GenerationStatus.COMPLETED
    assert updated.output_path == "videos/%s/job-complete/output.mp4" % user.id
    assert (tmp_path / "storage" / updated.output_path).is_file()


def test_worker_marks_failure_and_continues(db, tmp_path):
    user = User(username="failureuser", email="failure@example.com", hashed_password="hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    for job_id in ("job-fail", "job-next"):
        db.add(GenerationJob(id=job_id, user_id=user.id, status=GenerationStatus.QUEUED, prompt="test", model_type="fake-video", generation_settings={"model_type": "fake-video"}))
    db.commit()
    source = tmp_path / "wan-output.mp4"
    source.write_bytes(b"fake video")
    service = FakeWan2GP(source, failures=1)
    worker = GenerationWorker(sessionmaker(bind=db.get_bind()), service, tmp_path / "storage")
    assert worker.run_once() is True
    assert worker.run_once() is True
    assert db.get(GenerationJob, "job-fail").status == GenerationStatus.FAILED
    assert db.get(GenerationJob, "job-next").status == GenerationStatus.COMPLETED
