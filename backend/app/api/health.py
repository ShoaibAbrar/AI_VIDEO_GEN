"""Health check endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.db.database import get_db
from app.services.wan2gp_service import Wan2GPService

router = APIRouter(tags=["health"])
_wan2gp_service = Wan2GPService()


def _get_gpu_info() -> dict[str, Any]:
    gpu_info: dict[str, Any] = {
        "available": False,
        "cuda_available": False,
        "device_name": None,
        "vram_total_mb": None,
        "vram_free_mb": None,
        "torch_version": None,
        "cuda_version": None,
    }
    try:
        import torch

        gpu_info["torch_version"] = getattr(torch, "__version__", None)
        cuda_avail = torch.cuda.is_available()
        gpu_info["cuda_available"] = cuda_avail
        if cuda_avail:
            gpu_info["available"] = True
            gpu_info["device_name"] = torch.cuda.get_device_name(0)
            if hasattr(torch.version, "cuda"):
                gpu_info["cuda_version"] = torch.version.cuda
            try:
                free, total = torch.cuda.mem_get_info()
                gpu_info["vram_free_mb"] = free // (1024 * 1024)
                gpu_info["vram_total_mb"] = total // (1024 * 1024)
            except Exception:
                pass
    except Exception:
        # PyTorch or CUDA not installed/available
        pass
    return gpu_info


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint.
    Returns application, database, GPU, and Wan2GP runtime status.
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        db_status = "unhealthy"

    gpu_info = _get_gpu_info()
    wan2gp_info = _wan2gp_service.get_runtime_status()

    is_overall_healthy = db_status == "healthy"

    return {
        "status": "healthy" if is_overall_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "gpu": gpu_info,
        "wan2gp": wan2gp_info,
    }
