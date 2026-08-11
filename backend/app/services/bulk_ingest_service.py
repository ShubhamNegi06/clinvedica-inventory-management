"""
Bulk ingestion (Excel upload -> samples).

Rewritten to actually match the real Clinvedica template, which the
original version did not handle correctly:

  - The template's header spans TWO rows: row 1 is section titles ("Case
    Details", "Demographic Details", ...), row 2 is the actual field
    labels ("Subject ID", "Age", "Gender", ...). Data starts at row 3.
    We read with header=1 (0-indexed) so pandas uses row 2 as column
    names and drops row 1 entirely.
  - The template has TWO sheets ("Prospective" and "Remnant") with
    identical columns. Both are read and combined; each row is tagged
    with which sheet it came from (stored as the "sample-category"
    custom field) so that distinction isn't silently lost.
  - Columns are matched against `field_definitions.field_label` (not an
    arbitrary kebab-cased guess of the header text) — "Subject ID" and
    "Sample ID" map to the dedicated Sample.subject_id/sample_id columns,
    "Sr. No." is ignored (it's just a row counter), and every other
    column must match a seeded FieldDefinition or the whole file is
    rejected up front with a clear list of the unrecognized column
    names. This is deliberately strict: a silently-dropped or
    silently-misfiled column is worse than an upfront error telling you
    exactly which header didn't match.

Each row is still validated and inserted independently inside its own
savepoint, so one bad row doesn't abort the rest of the file — the
response reports exactly which rows succeeded and which failed and why.
"""
import re
import uuid
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import assert_site_access
from app.core.exceptions import BulkIngestError, ValidationAppError
from app.models.field_definition import FieldDefinition
from app.models.sample import Sample
from app.models.user import User

# Special-cased columns that map to dedicated Sample columns rather than
# custom_fields, matched case-insensitively after whitespace normalization.
SUBJECT_ID_LABELS = {"subject id"}
SAMPLE_ID_LABELS = {"sample id"}
IGNORED_LABELS = {"sr. no.", "sr no", "sr. no", "s.no.", "s no"}


def _normalize_label(text: Any) -> str:
    """Collapses whitespace/newlines and lowercases, so template quirks
    like 'Treatment Information\\n(Adjuvant/Neo-Adjuvant)' or a trailing
    space in 'Type of Tissue ' still match cleanly."""
    return re.sub(r"\s+", " ", str(text).strip()).lower()


def _build_label_to_key_map(db: Session) -> Dict[str, str]:
    field_defs = db.execute(
        select(FieldDefinition).where(FieldDefinition.is_active.is_(True))
    ).scalars().all()
    return {_normalize_label(fd.field_label): fd.field_key for fd in field_defs}


def _clean_cell(value: Any) -> Any:
    """Converts pandas NaN/NaT to None, dates to ISO strings, numpy scalar
    types (np.int64, np.float64 — what pandas actually hands back for
    numeric cells, and NOT JSON-serializable as-is) to native Python
    types, whole-number floats to int (so Grade=2.0 stores as 2, not
    2.0), and strings get stripped."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "item"):  # numpy scalar (np.int64, np.float64, ...)
        value = value.item()
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if hasattr(value, "isoformat"):  # datetime/date
        return value.isoformat()
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value


def _read_all_sheets(file_bytes: bytes) -> Dict[str, "pd.DataFrame"]:
    """
    Reads every sheet in the workbook using row 2 (index 1) as the header
    row, per the template's two-row header layout. Returns {sheet_name: df}.
    """
    try:
        sheets = pd.read_excel(pd.io.common.BytesIO(file_bytes), sheet_name=None, header=1)
    except Exception as exc:  # noqa: BLE001 — any parse failure becomes one clear error
        raise ValidationAppError(f"Could not read the Excel file: {exc}", field="file")
    return sheets


def _validate_columns(columns: List[str], label_to_key: Dict[str, str]) -> Dict[str, str]:
    """
    Validates every column header matches a known field (or is Subject
    ID / Sample ID / Sr. No.). Returns a map of original column name ->
    resolved kind ("subject_id" | "sample_id" | "ignore" | field_key).
    Raises ValidationAppError listing any unrecognized columns.
    """
    resolved: Dict[str, str] = {}
    unrecognized: List[str] = []

    for col in columns:
        normalized = _normalize_label(col)
        if normalized in SUBJECT_ID_LABELS:
            resolved[col] = "subject_id"
        elif normalized in SAMPLE_ID_LABELS:
            resolved[col] = "sample_id"
        elif normalized in IGNORED_LABELS:
            resolved[col] = "ignore"
        elif normalized in label_to_key:
            resolved[col] = label_to_key[normalized]
        elif normalized.startswith("unnamed"):
            # Blank/merged header cells pandas auto-names "Unnamed: N" —
            # safe to ignore rather than treat as an unrecognized column.
            resolved[col] = "ignore"
        else:
            unrecognized.append(str(col))

    if unrecognized:
        raise ValidationAppError(
            "These column headers don't match any known field: "
            + ", ".join(f"'{c}'" for c in unrecognized)
            + ". Column headers must exactly match the Clinvedica template "
              "(e.g. 'Subject ID', 'Sample ID', 'Type of Tissue', 'Age', ...). "
              "Check for typos or an outdated template.",
            field="file",
        )
    return resolved


def parse_and_ingest(
    db: Session,
    current_user: User,
    site_id: uuid.UUID,
    file_bytes: bytes,
    max_rows: int,
) -> Dict[str, Any]:
    assert_site_access(site_id, current_user, db)

    sheets = _read_all_sheets(file_bytes)
    if not sheets:
        raise ValidationAppError("The uploaded file has no sheets.", field="file")

    total_rows = sum(len(df) for df in sheets.values())
    if total_rows == 0:
        raise ValidationAppError("The uploaded file has no data rows.", field="file")
    if total_rows > max_rows:
        raise ValidationAppError(
            f"File has {total_rows} rows across all sheets, which exceeds the {max_rows}-row "
            f"bulk upload limit. Please split it into smaller files.",
            field="file",
        )

    label_to_key = _build_label_to_key_map(db)

    created: List[str] = []
    row_errors: List[dict] = []

    for sheet_name, df in sheets.items():
        if df.empty:
            continue

        column_map = _validate_columns(list(df.columns), label_to_key)

        for idx, row in df.iterrows():
            excel_row_number = idx + 3  # +1 zero-index, +2 for the two header rows
            sample_id_value = ""
            try:
                subject_id_value = None
                sample_id_value = None
                custom_fields: Dict[str, Any] = {}

                for col, kind in column_map.items():
                    cleaned = _clean_cell(row[col])
                    if kind == "ignore":
                        continue
                    elif kind == "subject_id":
                        subject_id_value = str(cleaned).strip() if cleaned is not None else None
                    elif kind == "sample_id":
                        sample_id_value = str(cleaned).strip() if cleaned is not None else None
                    else:
                        if cleaned is not None:
                            custom_fields[kind] = cleaned

                # Tag which sheet this row came from, so the
                # Prospective/Remnant distinction survives ingestion.
                custom_fields["sample-category"] = sheet_name

                if not subject_id_value:
                    raise ValueError("Subject ID is required")
                if not sample_id_value:
                    raise ValueError("Sample ID is required")

                sample = Sample(
                    id=uuid.uuid4(),
                    site_id=site_id,
                    subject_id=subject_id_value,
                    sample_id=sample_id_value,
                    custom_fields=custom_fields,
                    created_by=current_user.id,
                    updated_by=current_user.id,
                )

                # Savepoint per row: a duplicate sample_id (or any other
                # constraint violation) rolls back only this row, not the
                # whole batch.
                with db.begin_nested():
                    db.add(sample)

                created.append(sample_id_value)

            except IntegrityError as exc:
                constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
                if constraint == "uq_sample_site_sample_id":
                    row_errors.append(
                        {
                            "sheet": sheet_name,
                            "row": excel_row_number,
                            "sample_id": sample_id_value,
                            "error": "Duplicate Sample ID at this site",
                        }
                    )
                else:
                    row_errors.append({"sheet": sheet_name, "row": excel_row_number, "error": str(exc)})
            except Exception as exc:  # noqa: BLE001 — one bad row must not kill the batch
                row_errors.append({"sheet": sheet_name, "row": excel_row_number, "error": str(exc)})

    db.commit()

    if not created and row_errors:
        raise BulkIngestError("No rows could be ingested.", row_errors=row_errors)

    return {"created_count": len(created), "created_sample_ids": created, "row_errors": row_errors}
