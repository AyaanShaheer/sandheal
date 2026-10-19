"""baseline schema

Creates the repair_runs and repair_jobs tables.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUN_STATUS_VALUES = (
    "'received', 'reproducing', 'analyzing', 'researching', "
    "'generating_repairs', 'executing', 'verifying', 'creating_pr', "
    "'completed', 'failed', 'cancelled'"
)

JOB_STATUS_VALUES = "'pending', 'processing', 'completed', 'failed', 'cancelled'"


def upgrade() -> None:
    op.create_table(
        "repair_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("delivery_id", sa.String(length=255), nullable=False),
        sa.Column("repository", sa.String(length=255), nullable=False),
        sa.Column("commit_sha", sa.String(length=255), nullable=False),
        sa.Column("workflow_name", sa.String(length=255), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=False),
        sa.Column("conclusion", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"status IN ({RUN_STATUS_VALUES})",
            name="ck_repair_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("repair_runs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_repair_runs_delivery_id"),
            ["delivery_id"],
            unique=True,
        )

    op.create_table(
        "repair_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"status IN ({JOB_STATUS_VALUES})",
            name="ck_repair_jobs_status",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["repair_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("repair_jobs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_repair_jobs_run_id"),
            ["run_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("repair_jobs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_repair_jobs_run_id"))

    op.drop_table("repair_jobs")

    with op.batch_alter_table("repair_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_repair_runs_delivery_id"))

    op.drop_table("repair_runs")
