"""Add MIME type and file size metadata to uploaded documents."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_uploaded_document_metadata"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "uploaded_documents",
        sa.Column("mime_type", sa.String(length=255), nullable=False, server_default="application/octet-stream"),
    )
    op.add_column(
        "uploaded_documents",
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
    )
    with op.batch_alter_table("uploaded_documents") as batch_op:
        batch_op.alter_column("mime_type", existing_type=sa.String(length=255), server_default=None)
        batch_op.alter_column("file_size_bytes", existing_type=sa.Integer(), server_default=None)


def downgrade() -> None:
    op.drop_column("uploaded_documents", "file_size_bytes")
    op.drop_column("uploaded_documents", "mime_type")
