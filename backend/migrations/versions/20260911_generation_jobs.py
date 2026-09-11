"""Add generation jobs

Revision ID: 20260911_generation_jobs
Revises: 20260910_initial_platform_schema
Create Date: 2026-09-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260911_generation_jobs"
down_revision = "20260910_initial_platform_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    enum_values = (
        "QUEUED",
        "PROCESSING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    )
    if bind.dialect.name == "postgresql":
        generation_status = postgresql.ENUM(*enum_values, name="generation_status", create_type=False)
        postgresql.ENUM(*enum_values, name="generation_status").create(bind, checkfirst=True)
    else:
        generation_status = sa.Enum(*enum_values, name="generation_status")
    op.create_table(
        "generation_job",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", generation_status, nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("model_type", sa.String(length=255), nullable=False),
        sa.Column("generation_settings", sa.JSON(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("current_step", sa.Integer(), nullable=True),
        sa.Column("total_steps", sa.Integer(), nullable=True),
        sa.Column("phase", sa.String(length=100), nullable=True),
        sa.Column("status_text", sa.String(length=500), nullable=True),
        sa.Column("output_path", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generation_job_user_id", "generation_job", ["user_id"], unique=False)
    op.create_index("ix_generation_job_status", "generation_job", ["status"], unique=False)
    op.create_index("ix_generation_job_model_type", "generation_job", ["model_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_generation_job_model_type", table_name="generation_job")
    op.drop_index("ix_generation_job_status", table_name="generation_job")
    op.drop_index("ix_generation_job_user_id", table_name="generation_job")
    op.drop_table("generation_job")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="generation_status").drop(bind, checkfirst=True)
