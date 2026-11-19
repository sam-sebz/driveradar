"""initial schema: users, drives, user_drives, refresh_tokens

Revision ID: 0001
Revises:
Create Date: 2026-11-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="student"),
        sa.Column("name", sa.String(120)),
        sa.Column("branch", sa.String(80)),
        sa.Column("batch", sa.Integer()),
        sa.Column("cgpa", sa.Float()),
        sa.Column("pct_10", sa.Float()),
        sa.Column("pct_12", sa.Float()),
        sa.Column("backlogs", sa.Integer()),
        sa.Column("skills", postgresql.ARRAY(sa.Text()), nullable=False,
                  server_default="{}"),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('student', 'coordinator')", name="ck_users_role"),
        sa.CheckConstraint("cgpa IS NULL OR (cgpa >= 0 AND cgpa <= 10)", name="ck_users_cgpa"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "drives",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("uploaded_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("company", sa.String(200)),
        sa.Column("role", sa.String(200)),
        sa.Column("role_category", sa.String(50)),
        sa.Column("location", sa.String(200)),
        sa.Column("ctc_lpa_min", sa.Float()),
        sa.Column("ctc_lpa_max", sa.Float()),
        sa.Column("stipend_per_month", sa.Integer()),
        sa.Column("deadline", TS),
        sa.Column("joining_date", sa.Date()),
        sa.Column("bond_years", sa.Float()),
        sa.Column("bond_penalty_inr", sa.BigInteger()),
        sa.Column("min_cgpa", sa.Float()),
        sa.Column("min_ug_percent", sa.Float()),
        sa.Column("min_percent_10th", sa.Float()),
        sa.Column("min_percent_12th", sa.Float()),
        sa.Column("max_active_backlogs", sa.Integer()),
        sa.Column("eligible_branches", postgresql.ARRAY(sa.Text())),
        sa.Column("eligible_batch", postgresql.ARRAY(sa.Integer())),
        sa.Column("required_skills", postgresql.ARRAY(sa.Text())),
        sa.Column("selection_process", postgresql.ARRAY(sa.Text())),
        sa.Column("notes", sa.Text()),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source_filename", sa.String(255)),
        sa.Column("stored_path", sa.String(500)),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("extraction_provider", sa.String(30), nullable=False),
        sa.Column("extracted_original", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_drives_uploaded_by", "drives", ["uploaded_by"])
    op.create_index("ix_drives_deadline", "drives", ["deadline"])
    op.create_index("ix_drives_content_hash", "drives", ["content_hash"])

    op.create_table(
        "user_drives",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("drive_id", sa.Uuid(), sa.ForeignKey("drives.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("eligibility", sa.String(20), nullable=False),
        sa.Column("eligibility_reasons", postgresql.JSONB(), nullable=False),
        sa.Column("match_score", sa.Float()),
        sa.Column("matched_skills", postgresql.ARRAY(sa.Text()), nullable=False,
                  server_default="{}"),
        sa.Column("missing_skills", postgresql.ARRAY(sa.Text()), nullable=False,
                  server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="saved"),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("eligibility IN ('eligible', 'not_eligible', 'unknown')",
                           name="ck_user_drives_eligibility"),
        sa.CheckConstraint(
            "status IN ('saved', 'applied', 'shortlisted', 'rejected', 'selected')",
            name="ck_user_drives_status",
        ),
    )
    op.create_index("ix_user_drives_user_status", "user_drives", ["user_id", "status"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("user_drives")
    op.drop_table("drives")
    op.drop_table("users")
