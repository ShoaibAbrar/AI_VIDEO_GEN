"""Database model for Wan2GP generation jobs."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SqlEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class GenerationStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GenerationJob(Base):
    __tablename__ = "generation_job"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(SqlEnum(GenerationStatus, name="generation_status"), nullable=False, default=GenerationStatus.QUEUED, index=True)
    prompt = Column(Text, nullable=False)
    model_type = Column(String(255), nullable=False, index=True)
    generation_settings = Column(JSON, nullable=False, default=dict)
    progress = Column(Integer, nullable=True)
    current_step = Column(Integer, nullable=True)
    total_steps = Column(Integer, nullable=True)
    phase = Column(String(100), nullable=True)
    status_text = Column(String(500), nullable=True)
    output_path = Column(String(500), nullable=True)
    error_message = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="generation_jobs")

    def can_transition_to(self, next_status: GenerationStatus) -> bool:
        transitions = {
            GenerationStatus.QUEUED: {GenerationStatus.PROCESSING, GenerationStatus.CANCELLED},
            GenerationStatus.PROCESSING: {GenerationStatus.COMPLETED, GenerationStatus.FAILED, GenerationStatus.CANCELLED},
            GenerationStatus.COMPLETED: set(),
            GenerationStatus.FAILED: set(),
            GenerationStatus.CANCELLED: set(),
        }
        return next_status in transitions.get(self.status, set())
