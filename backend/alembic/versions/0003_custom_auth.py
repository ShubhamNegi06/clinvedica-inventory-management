"""custom auth: hashed_password + refresh_tokens + password_reset_tokens

Revision ID: 0003_custom_auth
Revises: 0002_align_with_template
Create Date: 2026-08-11

Adds everything needed to replace Supabase Auth with local
username/password authentication:
  1. users.hashed_password — bcrypt hash, NOT NULL. Added as nullable
     first, backfilled, then made NOT NULL in the same migration (see
     upgrade() for why this order matters for existing rows).
  2. refresh_tokens table — server-side revocable refresh tokens.
  3. password_reset_tokens table — single-use, expiring tokens shared by
     both the invite and forgot-password flows.

IMPORTANT — existing users have no password:
Every user row created under the old Supabase-backed system has no
password of any kind. This migration backfills hashed_password with a
hash of a random, never-communicated placeholder value (NOT a usable
password) purely so the NOT NULL constraint can be added without
breaking existing rows. Existing users CANNOT log in until an admin
either sends them a password-reset email or sets a temporary password
via the "Set Temp Password" admin action — this is a required manual
step, not something this migration can safely automate (it would mean
either emailing every user during a schema migration, which is a bad
mix of concerns, or generating passwords with no way to deliver them
to their owners). See scripts/backfill_existing_user_passwords.py for a
one-off helper that (re)generates a fresh placeholder + optionally
queues reset emails for every existing user in one pass.
"""
import uuid
from typing import Sequence, Union

import bcrypt
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_custom_auth"
down_revision: Union[str, None] = "0002_align_with_template"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. users.hashed_password
    # -----------------------------------------------------------------
    op.add_column("users", sa.Column("hashed_password", sa.String(255), nullable=True))

    # Backfill every existing row with a hash of a random, unusable
    # placeholder (each row gets its OWN random value — never a shared
    # constant — so no two existing accounts end up with the same
    # underlying password by coincidence of this migration).
    connection = op.get_bind()
    user_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM users")).fetchall()]
    for user_id in user_ids:
        placeholder = bcrypt.hashpw(str(uuid.uuid4()).encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        connection.execute(
            sa.text("UPDATE users SET hashed_password = :hp WHERE id = :uid"),
            {"hp": placeholder, "uid": user_id},
        )

    op.alter_column("users", "hashed_password", nullable=False)

    # -----------------------------------------------------------------
    # 2. refresh_tokens
    # -----------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "replaced_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # -----------------------------------------------------------------
    # 3. password_reset_tokens
    # -----------------------------------------------------------------
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False, server_default="reset"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
    op.drop_table("refresh_tokens")
    op.drop_column("users", "hashed_password")
