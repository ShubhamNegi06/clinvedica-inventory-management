"""
Bulk ingestion (Excel upload -> samples).

Design choice: this is NOT all-or-nothing. Each row is validated and
inserted independently inside its own savepoint, so one bad row (e.g. a
duplicate sample_id) doesn't abort the other 400 valid rows in the
file. The response tells the caller exactly which rows succeeded and
which failed and why — matching the BulkIngestError shape defined in
app/core/exceptions.py.

Expected columns (case-insensitive, matches the real Excel template):
    subject_id, sample_id, sample_type, tags (comma-separated)
    ... plus any additional columns, which are stored verbatim into
    custom_fields keyed by their (kebab-cased) column header.
"""
import re
import uuid
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import assert_site_access
from app.core.exceptions import BulkIngestError, ValidationAppError
from app.models.sample import Sample
from app.models.user import User

REQUIRED_COLUMNS = {"subject_id", "sample_id"}
KNOWN_COLUMNS = {"subject_id", "sample_id", "sample_type", "tags"}


def _kebab_case(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip()).strip("-").lower()
    return text


def _normalize_columns(columns: List[str]) -> Dict[str, str]:
    """Maps original column header -> normalized (snake-ish) key for matching against REQUIRED_COLUMNS."""
    return {col: re.sub(r"[^a-z0-9]+", "_", col.strip().lower()).strip("_") for col in columns}


def parse_and_ingest(
    db: Session,
    current_user: User,
    site_id: uuid.UUID,
    file_bytes: bytes,
    max_rows: int,
) -> Dict[str, Any]:
    assert_site_access(site_id, current_user, db)

    try:
        df = pd.read_excel(file_bytes if isinstance(file_bytes, str) else pd.io.common.BytesIO(file_bytes))
    except Exception as exc:  # noqa: BLE001 — any parse failure becomes one clear error
        raise ValidationAppError(f"Could not read the Excel file: {exc}", field="file")

    if df.empty:
        raise ValidationAppError("The uploaded file has no data rows.", field="file")
    if len(df) > max_rows:
        raise ValidationAppError(
            f"File has {len(df)} rows, which exceeds the {max_rows}-row bulk upload limit. "
            f"Please split it into smaller files.",
            field="file",
        )

    col_map = _normalize_columns(list(df.columns))
    normalized_to_original = {v: k for k, v in col_map.items()}
    missing = REQUIRED_COLUMNS - set(col_map.values())
    if missing:
        raise ValidationAppError(
            f"Missing required column(s): {', '.join(sorted(missing))}.", field="file"
        )

    created: List[str] = []
    row_errors: List[dict] = []

    for idx, row in df.iterrows():
        excel_row_number = idx + 2  # +1 for 0-index, +1 for header row
        try:
            row_data = {col_map[col]: row[col] for col in df.columns}

            subject_id = str(row_data.get("subject_id", "")).strip()
            sample_id = str(row_data.get("sample_id", "")).strip()
            if not subject_id or subject_id.lower() == "nan":
                raise ValueError("subject_id is required")
            if not sample_id or sample_id.lower() == "nan":
                raise ValueError("sample_id is required")

            sample_type_raw = row_data.get("sample_type")
            sample_type = None
            if sample_type_raw and str(sample_type_raw).strip().lower() != "nan":
                sample_type = _kebab_case(str(sample_type_raw)).replace("-", "_")

            tags_raw = row_data.get("tags")
            tags = []
            if tags_raw and str(tags_raw).strip().lower() != "nan":
                tags = [t.strip() for t in str(tags_raw).split(",") if t.strip()]

            custom_fields = {}
            for normalized_key, value in row_data.items():
                if normalized_key in KNOWN_COLUMNS:
                    continue
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    continue
                original_header = normalized_to_original.get(normalized_key, normalized_key)
                custom_fields[_kebab_case(original_header)] = value if not pd.isna(value) else None

            sample = Sample(
                id=uuid.uuid4(),
                site_id=site_id,
                subject_id=subject_id,
                sample_id=sample_id,
                sample_type=sample_type,
                tags=tags,
                custom_fields=custom_fields,
                created_by=current_user.id,
                updated_by=current_user.id,
            )

            # Savepoint per row: a duplicate sample_id (or any other
            # constraint violation) rolls back only this row, not the
            # whole batch.
            with db.begin_nested():
                db.add(sample)

            created.append(sample_id)

        except IntegrityError as exc:
            # db.begin_nested()'s context manager already rolled back this
            # row's savepoint on the exception above — no manual rollback needed here.
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint == "uq_sample_site_code":
                row_errors.append(
                    {"row": excel_row_number, "sample_id": sample_id, "error": "Duplicate sample_id at this site"}
                )
            else:
                row_errors.append({"row": excel_row_number, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001 — one bad row must not kill the batch
            row_errors.append({"row": excel_row_number, "error": str(exc)})

    db.commit()

    if not created and row_errors:
        raise BulkIngestError("No rows could be ingested.", row_errors=row_errors)

    return {"created_count": len(created), "created_sample_ids": created, "row_errors": row_errors}
