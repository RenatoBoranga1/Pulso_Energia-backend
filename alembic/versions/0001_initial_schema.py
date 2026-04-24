"""Initial relational schema for the energy bill backend."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


document_file_type = sa.Enum(
    "pdf",
    "jpg",
    "jpeg",
    "png",
    name="document_file_type",
    native_enum=False,
    validate_strings=True,
    length=16,
)
bill_extraction_status = sa.Enum(
    "PENDING_REVIEW",
    "CONFIRMED",
    "REJECTED",
    "FAILED",
    name="bill_extraction_status",
    native_enum=False,
    validate_strings=True,
    length=32,
)
insight_type = sa.Enum(
    "trend",
    "anomaly",
    "seasonality",
    "forecast",
    "general",
    name="insight_type",
    native_enum=False,
    validate_strings=True,
    length=32,
)
extraction_log_level = sa.Enum(
    "INFO",
    "WARNING",
    "ERROR",
    name="extraction_log_level",
    native_enum=False,
    validate_strings=True,
    length=16,
)
extraction_log_stage = sa.Enum(
    "upload",
    "text_extraction",
    "normalization",
    "semantic_parsing",
    "validation",
    "review",
    name="extraction_log_stage",
    native_enum=False,
    validate_strings=True,
    length=64,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "uploaded_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", document_file_type, nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_uploaded_documents_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploaded_documents")),
        sa.UniqueConstraint("file_path", name=op.f("uq_uploaded_documents_file_path")),
    )
    op.create_index(op.f("ix_uploaded_documents_user_id"), "uploaded_documents", ["user_id"], unique=False)

    op.create_table(
        "utility_bills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("concessionaria", sa.String(length=255), nullable=True),
        sa.Column("mes_referencia", sa.String(length=7), nullable=True),
        sa.Column("consumo_kwh", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("dias_faturados", sa.Integer(), nullable=True),
        sa.Column("valor_total", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("bandeira_tarifaria", sa.String(length=100), nullable=True),
        sa.Column("unidade_consumidora", sa.String(length=100), nullable=True),
        sa.Column("vencimento", sa.Date(), nullable=True),
        sa.Column(
            "extraction_status",
            bill_extraction_status,
            server_default=sa.text("'PENDING_REVIEW'"),
            nullable=False,
        ),
        sa.Column("review_required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("consumo_kwh >= 0", name=op.f("ck_utility_bills_consumo_kwh_non_negative")),
        sa.CheckConstraint("dias_faturados >= 0", name=op.f("ck_utility_bills_dias_faturados_non_negative")),
        sa.CheckConstraint("valor_total >= 0", name=op.f("ck_utility_bills_valor_total_non_negative")),
        sa.ForeignKeyConstraint(["document_id"], ["uploaded_documents.id"], name=op.f("fk_utility_bills_document_id_uploaded_documents"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_utility_bills_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_utility_bills")),
    )
    op.create_index(op.f("ix_utility_bills_document_id"), "utility_bills", ["document_id"], unique=True)
    op.create_index(op.f("ix_utility_bills_mes_referencia"), "utility_bills", ["mes_referencia"], unique=False)
    op.create_index(op.f("ix_utility_bills_user_id"), "utility_bills", ["user_id"], unique=False)

    op.create_table(
        "consumption_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bill_id", sa.Uuid(), nullable=False),
        sa.Column("mes_referencia", sa.String(length=7), nullable=False),
        sa.Column("consumo_kwh", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("dias_faturados", sa.Integer(), nullable=True),
        sa.CheckConstraint("consumo_kwh >= 0", name=op.f("ck_consumption_history_consumo_kwh_non_negative")),
        sa.CheckConstraint("dias_faturados >= 0", name=op.f("ck_consumption_history_dias_faturados_non_negative")),
        sa.ForeignKeyConstraint(["bill_id"], ["utility_bills.id"], name=op.f("fk_consumption_history_bill_id_utility_bills"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consumption_history")),
        sa.UniqueConstraint("bill_id", "mes_referencia", name="consumption_history_bill_month_unique"),
    )
    op.create_index(op.f("ix_consumption_history_bill_id"), "consumption_history", ["bill_id"], unique=False)

    op.create_table(
        "extraction_confidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bill_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=120), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.CheckConstraint("confidence_score >= 0", name=op.f("ck_extraction_confidence_score_min")),
        sa.CheckConstraint("confidence_score <= 1", name=op.f("ck_extraction_confidence_score_max")),
        sa.ForeignKeyConstraint(["bill_id"], ["utility_bills.id"], name=op.f("fk_extraction_confidence_bill_id_utility_bills"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extraction_confidence")),
        sa.UniqueConstraint("bill_id", "field_name", name="extraction_confidence_bill_field_unique"),
    )
    op.create_index(op.f("ix_extraction_confidence_bill_id"), "extraction_confidence", ["bill_id"], unique=False)

    op.create_table(
        "forecasts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bill_id", sa.Uuid(), nullable=False),
        sa.Column("mes_referencia", sa.String(length=7), nullable=False),
        sa.Column("predicted_kwh", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("lower_bound_kwh", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("upper_bound_kwh", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("model_used", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("predicted_kwh >= 0", name=op.f("ck_forecasts_predicted_kwh_non_negative")),
        sa.CheckConstraint("lower_bound_kwh >= 0", name=op.f("ck_forecasts_lower_bound_non_negative")),
        sa.CheckConstraint("upper_bound_kwh >= 0", name=op.f("ck_forecasts_upper_bound_non_negative")),
        sa.CheckConstraint("lower_bound_kwh <= upper_bound_kwh", name=op.f("ck_forecasts_bounds_ordered")),
        sa.ForeignKeyConstraint(["bill_id"], ["utility_bills.id"], name=op.f("fk_forecasts_bill_id_utility_bills"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecasts")),
        sa.UniqueConstraint("bill_id", "mes_referencia", name="forecasts_bill_month_unique"),
    )
    op.create_index(op.f("ix_forecasts_bill_id"), "forecasts", ["bill_id"], unique=False)

    op.create_table(
        "insights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bill_id", sa.Uuid(), nullable=False),
        sa.Column("insight_type", insight_type, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["utility_bills.id"], name=op.f("fk_insights_bill_id_utility_bills"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_insights")),
    )
    op.create_index(op.f("ix_insights_bill_id"), "insights", ["bill_id"], unique=False)

    op.create_table(
        "extraction_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("bill_id", sa.Uuid(), nullable=True),
        sa.Column("stage", extraction_log_stage, nullable=False),
        sa.Column("level", extraction_log_level, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source_component", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["utility_bills.id"], name=op.f("fk_extraction_logs_bill_id_utility_bills"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["uploaded_documents.id"], name=op.f("fk_extraction_logs_document_id_uploaded_documents"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extraction_logs")),
    )
    op.create_index(op.f("ix_extraction_logs_bill_id"), "extraction_logs", ["bill_id"], unique=False)
    op.create_index(op.f("ix_extraction_logs_document_id"), "extraction_logs", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_extraction_logs_document_id"), table_name="extraction_logs")
    op.drop_index(op.f("ix_extraction_logs_bill_id"), table_name="extraction_logs")
    op.drop_table("extraction_logs")

    op.drop_index(op.f("ix_insights_bill_id"), table_name="insights")
    op.drop_table("insights")

    op.drop_index(op.f("ix_forecasts_bill_id"), table_name="forecasts")
    op.drop_table("forecasts")

    op.drop_index(op.f("ix_extraction_confidence_bill_id"), table_name="extraction_confidence")
    op.drop_table("extraction_confidence")

    op.drop_index(op.f("ix_consumption_history_bill_id"), table_name="consumption_history")
    op.drop_table("consumption_history")

    op.drop_index(op.f("ix_utility_bills_user_id"), table_name="utility_bills")
    op.drop_index(op.f("ix_utility_bills_mes_referencia"), table_name="utility_bills")
    op.drop_index(op.f("ix_utility_bills_document_id"), table_name="utility_bills")
    op.drop_table("utility_bills")

    op.drop_index(op.f("ix_uploaded_documents_user_id"), table_name="uploaded_documents")
    op.drop_table("uploaded_documents")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
