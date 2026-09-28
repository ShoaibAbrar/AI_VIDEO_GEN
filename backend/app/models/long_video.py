"""
Database models for Long-Video Orchestration projects and scenes.
"""

from datetime import datetime
from enum import Enum
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.orchestration.models import LongVideoMode, OrchestrationStage, SceneStatus


class LongVideoProject(Base):
    __tablename__ = "long_video_project"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="Untitled Project")
    prompt = Column(Text, nullable=False)
    synopsis = Column(Text, nullable=True)
    status = Column(
        SqlEnum(OrchestrationStage, name="orchestration_stage"),
        nullable=False,
        default=OrchestrationStage.PLANNING,
        index=True,
    )
    generation_mode = Column(
        SqlEnum(LongVideoMode, name="long_video_mode"),
        nullable=False,
        default=LongVideoMode.SEGMENTED_CONTINUATION,
    )
    engine_name = Column(String(100), nullable=False, default="wan2gp")
    world_setting = Column(JSON, nullable=False, default=dict)
    characters = Column(JSON, nullable=False, default=list)
    total_scenes = Column(Integer, nullable=False, default=1)
    current_scene = Column(Integer, nullable=False, default=0)
    progress_percent = Column(Float, nullable=False, default=0.0)
    status_text = Column(String(500), nullable=True, default="Generating your long video...")
    output_video_path = Column(String(500), nullable=True)
    error_message = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="long_video_projects")
    scenes = relationship(
        "LongVideoScene",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="LongVideoScene.scene_index",
    )


class LongVideoScene(Base):
    __tablename__ = "long_video_scene"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(
        String(36), ForeignKey("long_video_project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_index = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False, default="")
    visual_prompt = Column(Text, nullable=False)
    enriched_prompt = Column(Text, nullable=True)
    action_description = Column(Text, nullable=True)
    characters_present = Column(JSON, nullable=False, default=list)
    dialogue = Column(JSON, nullable=False, default=list)
    camera_motion = Column(String(100), nullable=False, default="static")
    transition_to_next = Column(String(100), nullable=False, default="cut")
    duration_seconds = Column(Float, nullable=False, default=5.0)
    status = Column(
        SqlEnum(SceneStatus, name="scene_status"),
        nullable=False,
        default=SceneStatus.PENDING,
        index=True,
    )
    video_clip_path = Column(String(500), nullable=True)
    audio_clip_path = Column(String(500), nullable=True)
    error_message = Column(String(1000), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("LongVideoProject", back_populates="scenes")
