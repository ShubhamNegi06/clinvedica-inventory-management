"""
align samples table with the real Excel template

Revision ID: 0002_align_with_template
Revises: 66df86a9ed75
Create Date: 2026-08-11

Changes:
1. Rename samples.subject_code -> samples.subject_id
2. Rename samples.sample_code -> samples.sample_id
3. Rename the sample/site unique constraint
4. Remove the invented sample_type column
5. Remove the free-form tags column and its GIN index
6. Rename reports.sample_id -> reports.sample_pk
7. Rename the corresponding reports index

Important:
The samples table was manually restored after it had been deleted from
the database. Some indexes that existed in the original migration history
are missing, so index operations are intentionally made idempotent.

The reports -> samples foreign key is intentionally NOT recreated here
because the current database contains an existing report whose sample_id
points to a deleted sample. The orphaned report must be handled separately
before adding that foreign key.
"""

from typing import Sequence, Union

from alembic import op


# ---------------------------------------------------------------------------
# Alembic revision identifiers
# ---------------------------------------------------------------------------

revision: str = "0002_align_with_template"

# IMPORTANT:
# 0002 must continue from the migration that is currently applied to the DB.
down_revision: Union[str, None] = "66df86a9ed75"

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Rename samples.subject_code -> subject_id
    # -----------------------------------------------------------------------
    #
    # Current DB:
    #   subject_code
    #
    # Desired application/template schema:
    #   subject_id
    #
    op.alter_column(
        "samples",
        "subject_code",
        new_column_name="subject_id",
    )

    # -----------------------------------------------------------------------
    # 2. Rename samples.sample_code -> sample_id
    # -----------------------------------------------------------------------
    #
    # Current DB:
    #   sample_code
    #
    # Desired application/template schema:
    #   sample_id
    #
    op.alter_column(
        "samples",
        "sample_code",
        new_column_name="sample_id",
    )

    # -----------------------------------------------------------------------
    # 3. Replace old subject/sample indexes
    # -----------------------------------------------------------------------
    #
    # The old indexes may not exist because the samples table was manually
    # recreated. Therefore use IF EXISTS.
    #
    op.execute(
        "DROP INDEX IF EXISTS ix_samples_subject_code"
    )

    op.execute(
        "DROP INDEX IF EXISTS ix_samples_sample_code"
    )

    # The desired indexes may already exist in some repaired databases.
    # Therefore use CREATE INDEX IF NOT EXISTS.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_samples_subject_id
        ON samples (subject_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_samples_sample_id
        ON samples (sample_id)
        """
    )

    # -----------------------------------------------------------------------
    # 4. Replace the old unique constraint
    # -----------------------------------------------------------------------
    #
    # Old:
    #   uq_sample_site_code
    #
    # New:
    #   uq_sample_site_sample_id
    #
    # The old constraint is expected to exist because the samples table was
    # recreated from the 66df86a9ed75 schema.
    #
    op.execute(
        """
        ALTER TABLE samples
        DROP CONSTRAINT IF EXISTS uq_sample_site_code
        """
    )

    op.execute(
        """
        ALTER TABLE samples
        ADD CONSTRAINT uq_sample_site_sample_id
        UNIQUE (site_id, sample_id)
        """
    )

    # -----------------------------------------------------------------------
    # 5. Remove sample_type
    # -----------------------------------------------------------------------
    #
    # The real Excel template does not use a dedicated sample_type column.
    # Template fields such as "Sample Type" and "Type of Tissue" are stored
    # inside custom_fields.
    #
    op.execute(
        """
        ALTER TABLE samples
        DROP COLUMN IF EXISTS sample_type
        """
    )

    # -----------------------------------------------------------------------
    # 6. Remove tags
    # -----------------------------------------------------------------------
    #
    # Filtering is now performed against custom_fields rather than a
    # free-form tags array.
    #
    op.execute(
        "DROP INDEX IF EXISTS ix_samples_tags_gin"
    )

    op.execute(
        """
        ALTER TABLE samples
        DROP COLUMN IF EXISTS tags
        """
    )

    # -----------------------------------------------------------------------
    # 7. Rename reports.sample_id -> reports.sample_pk
    # -----------------------------------------------------------------------
    #
    # IMPORTANT:
    #
    # samples.sample_id is the business identifier from the Excel template.
    #
    # reports.sample_id actually stores the UUID of the Sample database row.
    #
    # Therefore the application now calls this field sample_pk.
    #
    op.alter_column(
        "reports",
        "sample_id",
        new_column_name="sample_pk",
    )

    # -----------------------------------------------------------------------
    # 8. Replace reports index
    # -----------------------------------------------------------------------

    op.execute(
        "DROP INDEX IF EXISTS ix_reports_sample_id"
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_reports_sample_pk
        ON reports (sample_pk)
        """
    )

    # -----------------------------------------------------------------------
    # 9. DO NOT add the reports -> samples foreign key here
    # -----------------------------------------------------------------------
    #
    # There is currently one report whose sample_pk points to a sample that
    # was deleted from the database.
    #
    # Adding this FK now would fail with:
    #
    #   insert or update on table "reports" violates foreign key constraint
    #
    # We will repair the orphaned report separately, then add the FK in a
    # subsequent migration.
    #


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Restore reports.sample_pk -> reports.sample_id
    # -----------------------------------------------------------------------

    op.alter_column(
        "reports",
        "sample_pk",
        new_column_name="sample_id",
    )

    op.execute(
        "DROP INDEX IF EXISTS ix_reports_sample_pk"
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_reports_sample_id
        ON reports (sample_id)
        """
    )

    # -----------------------------------------------------------------------
    # Restore tags
    # -----------------------------------------------------------------------

    op.execute(
        """
        ALTER TABLE samples
        ADD COLUMN IF NOT EXISTS tags VARCHAR[]
        NOT NULL DEFAULT '{}'
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_samples_tags_gin
        ON samples USING GIN (tags)
        """
    )

    # -----------------------------------------------------------------------
    # Restore sample_type
    # -----------------------------------------------------------------------

    op.execute(
        """
        ALTER TABLE samples
        ADD COLUMN IF NOT EXISTS sample_type VARCHAR(30)
        """
    )

    # -----------------------------------------------------------------------
    # Restore old unique constraint
    # -----------------------------------------------------------------------

    op.execute(
        """
        ALTER TABLE samples
        DROP CONSTRAINT IF EXISTS uq_sample_site_sample_id
        """
    )

    op.execute(
        """
        ALTER TABLE samples
        ADD CONSTRAINT uq_sample_site_code
        UNIQUE (site_id, sample_id)
        """
    )

    # -----------------------------------------------------------------------
    # Restore old index names
    # -----------------------------------------------------------------------

    op.execute(
        "DROP INDEX IF EXISTS ix_samples_subject_id"
    )

    op.execute(
        "DROP INDEX IF EXISTS ix_samples_sample_id"
    )

    # -----------------------------------------------------------------------
    # Restore old column names
    # -----------------------------------------------------------------------

    op.alter_column(
        "samples",
        "sample_id",
        new_column_name="sample_code",
    )

    op.alter_column(
        "samples",
        "subject_id",
        new_column_name="subject_code",
    )

    # -----------------------------------------------------------------------
    # Restore old indexes
    # -----------------------------------------------------------------------

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_samples_subject_code
        ON samples (subject_code)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_samples_sample_code
        ON samples (sample_code)
        """
    )