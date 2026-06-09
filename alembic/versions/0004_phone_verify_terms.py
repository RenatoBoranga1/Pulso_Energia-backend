"""add phone verification and terms acceptance

Revision ID: 0004_phone_verify_terms
Revises: 0003_refresh_tokens
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_phone_verify_terms"
down_revision = "0003_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_number", sa.String(length=20), nullable=True))
    op.add_column(
        "users",
        sa.Column("phone_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("users", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("two_factor_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "account_status",
            sa.String(length=64),
            server_default="pending_phone_verification",
            nullable=False,
        ),
    )
    op.add_column("users", sa.Column("accepted_terms_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("accepted_terms_version", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_users_phone_number"), "users", ["phone_number"], unique=True)
    op.create_index(op.f("ix_users_account_status"), "users", ["account_status"], unique=False)

    op.create_table(
        "phone_verification_codes",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("phone_number", sa.String(length=20), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_phone_verification_codes")),
    )
    op.create_index(
        op.f("ix_phone_verification_codes_user_id"),
        "phone_verification_codes",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_phone_verification_codes_phone_number"),
        "phone_verification_codes",
        ["phone_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_phone_verification_codes_phone_number"), table_name="phone_verification_codes")
    op.drop_index(op.f("ix_phone_verification_codes_user_id"), table_name="phone_verification_codes")
    op.drop_table("phone_verification_codes")

    op.drop_index(op.f("ix_users_account_status"), table_name="users")
    op.drop_index(op.f("ix_users_phone_number"), table_name="users")
    op.drop_column("users", "accepted_terms_version")
    op.drop_column("users", "accepted_terms_at")
    op.drop_column("users", "account_status")
    op.drop_column("users", "two_factor_enabled")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "phone_verified")
    op.drop_column("users", "phone_number")
