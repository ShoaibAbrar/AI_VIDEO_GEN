"""
Unit tests for the MockVideoEngine.
Validates GPU-free Windows developer mode and end-to-end simulated generation.
"""

import tempfile
from pathlib import Path

from app.engines.base import EngineProgress
from app.engines.mock_engine import MockVideoEngine
from app.engines.registry import VideoEngineRegistry


def test_mock_engine_metadata_and_capabilities():
    engine = MockVideoEngine("mock-test-engine")
    assert engine.engine_id == "mock-test-engine"
    assert engine.is_available is True

    status = engine.get_runtime_status()
    assert status["available"] is True
    assert status["models_available"] >= 1

    models = engine.list_models()
    assert len(models) >= 1
    assert any(m["model_type"] == "mock-t2v-preview" for m in models)

    caps = engine.capabilities
    assert caps.text_to_video is True
    assert caps.image_to_video is True
    assert caps.native_long_video is True


def test_mock_engine_simulated_generation_and_output():
    engine = MockVideoEngine("mock-test-engine")
    engine.initialize()

    progress_steps = []
    def on_progress(p: EngineProgress):
        progress_steps.append(p)

    settings = {"prompt": "A futuristic city skyline in 8k", "duration_seconds": 5.0}
    validated = engine.validate_generation(settings)
    assert validated["prompt"] == settings["prompt"]

    handle = engine.submit_generation(validated, on_progress)
    assert handle.engine_id == "mock-test-engine"
    assert len(progress_steps) == 5
    assert progress_steps[-1].progress == 100

    result = engine.wait_for_result(handle)
    assert result.success is True
    assert len(result.output_files) == 1
    assert Path(result.output_files[0]).is_file()

    # Cancel test
    engine.cancel_generation(handle)
    engine.shutdown()
