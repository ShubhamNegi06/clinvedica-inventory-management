"""initial schema — users, sites, samples, reports, field_definitions

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-10

Written by hand rather than via `alembic revision --autogenerate` because
this sandbox has no network path to the live Supabase instance (only a
fixed allow-list of package-registry domains). Run
`alembic upgrade head` against the real DATABASE_URL to apply. The
model metadata this migration mirrors was independently verified to
build correctly (see the SQLAlchemy metadata dump from the previous
checkpoint) — table names, columns, and constraint names match exactly.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- sites (created before users because users.site_id FKs to it,
    #     but sites.owned_by_user_id/created_by FK to users — resolved
    #     via ALTER TABLE ... ADD CONSTRAINT after both tables exist) ---
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("site_type", sa.String(30), nullable=False, server_default="partner_site"),
        sa.Column("owned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(320), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_sites_code", "sites", ["code"], unique=True)

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False, server_default="site_user"),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_site_id", "users", ["site_id"])

    # Deferred FKs from sites -> users, added now that users exists.
    op.create_foreign_key(
        "fk_sites_owned_by_user_id", "sites", "users", ["owned_by_user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key("fk_sites_created_by", "sites", "users", ["created_by"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_users_created_by", "users", "users", ["created_by"], ["id"], ondelete="SET NULL")

    # --- samples ---
    op.create_table(
        "samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("subject_id", sa.String(100), nullable=False),
        sa.Column("sample_id", sa.String(150), nullable=False),
        sa.Column("sample_type", sa.String(30), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("custom_fields", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("site_id", "sample_id", name="uq_sample_site_code"),
    )
    op.create_index("ix_samples_site_id", "samples", ["site_id"])
    op.create_index("ix_samples_subject_id", "samples", ["subject_id"])
    op.create_index("ix_samples_sample_id", "samples", ["sample_id"])
    op.create_index("ix_samples_is_deleted", "samples", ["is_deleted"])
    # GIN indexes for JSONB/array search performance — this is the whole
    # reason custom_fields is JSONB rather than a wide sparse table.
    op.execute("CREATE INDEX ix_samples_custom_fields_gin ON samples USING GIN (custom_fields)")
    op.execute("CREATE INDEX ix_samples_tags_gin ON samples USING GIN (tags)")

    # --- reports ---
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sample_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("samples.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("file_key", sa.String(1024), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("content_type", sa.String(150), nullable=False, server_default="application/pdf"),
        sa.Column("report_type", sa.String(20), nullable=False, server_default="original"),
        sa.Column(
            "original_report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reports_sample_id", "reports", ["sample_id"])
    op.create_index("ix_reports_site_id", "reports", ["site_id"])

    # --- field_definitions ---
    op.create_table(
        "field_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("field_key", sa.String(150), nullable=False),
        sa.Column("field_label", sa.String(255), nullable=False),
        sa.Column("section", sa.String(50), nullable=False),
        sa.Column("field_type", sa.String(30), nullable=False, server_default="text"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_autofill", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("field_key", name="uq_field_definition_key"),
    )


def downgrade() -> None:
    op.drop_table("field_definitions")
    op.drop_table("reports")
    op.drop_table("samples")
    op.drop_constraint("fk_users_created_by", "users", type_="foreignkey")
    op.drop_constraint("fk_sites_created_by", "sites", type_="foreignkey")
    op.drop_constraint("fk_sites_owned_by_user_id", "sites", type_="foreignkey")
    op.drop_table("users")
    op.drop_table("sites")
