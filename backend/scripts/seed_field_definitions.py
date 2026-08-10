"""
Seeds the field_definitions table with the standard field set matching
your Excel template, organized into the canonical sections. Run with:

    uv run python scripts/seed_field_definitions.py

Idempotent: uses field_key as the natural key and skips fields that
already exist, so it's safe to re-run after adding new entries to
FIELD_DEFINITIONS below.

NOTE: this is a starting set covering the sections you described (Case
Details, Demographics, Diagnosis, Sample Information, Serology,
Treatment, Biomarker Characterization). Adjust/extend field_key,
field_label, and field_type per your actual Excel template columns
before running against production — this file is meant to be edited to
match reality, not used verbatim.
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.field_definition import FieldDefinition

# (field_key, field_label, section, field_type, is_autofill)
FIELD_DEFINITIONS = [
    # --- Case Details ---
    ("case-id", "Case ID", "case_details", "text", False),
    ("accession-number", "Accession Number", "case_details", "text", False),
    ("collection-date", "Collection Date", "case_details", "date", False),
    ("receiving-date", "Receiving Date", "case_details", "date", False),

    # --- Demographic Details ---
    ("patient-age", "Age", "demographic_details", "number", True),
    ("patient-gender", "Gender", "demographic_details", "select", True),
    ("patient-ethnicity", "Ethnicity", "demographic_details", "text", True),

    # --- Diagnosis Information ---
    ("primary-diagnosis", "Primary Diagnosis", "diagnosis_information", "text", True),
    ("tumor-site", "Tumor Site", "diagnosis_information", "text", True),
    ("tumor-stage", "Tumor Stage", "diagnosis_information", "text", False),
    ("tumor-grade", "Tumor Grade", "diagnosis_information", "text", False),
    ("histology", "Histology", "diagnosis_information", "text", False),

    # --- Sample Information ---
    ("specimen-type", "Specimen Type", "sample_information", "select", False),
    ("preservation-method", "Preservation Method", "sample_information", "select", False),
    ("volume-quantity", "Volume / Quantity", "sample_information", "text", False),
    ("storage-condition", "Storage Condition", "sample_information", "text", False),

    # --- Serology Report ---
    ("hbv-status", "HBV Status", "serology_report", "select", False),
    ("hcv-status", "HCV Status", "serology_report", "select", False),
    ("hiv-status", "HIV Status", "serology_report", "select", False),

    # --- Treatment Detail ---
    ("treatment-history", "Treatment History", "treatment_detail", "text", True),
    ("chemotherapy-regimen", "Chemotherapy Regimen", "treatment_detail", "text", False),
    ("surgery-details", "Surgery Details", "treatment_detail", "text", False),

    # --- Biomarker Characterization ---
    ("er-status", "ER Status", "biomarker_characterization", "select", False),
    ("pr-status", "PR Status", "biomarker_characterization", "select", False),
    ("her2-status", "HER2 Status", "biomarker_characterization", "select", False),
    ("ki67-index", "Ki-67 Index", "biomarker_characterization", "text", False),
]


def run() -> None:
    db = SessionLocal()
    try:
        existing_keys = {
            row[0] for row in db.execute(select(FieldDefinition.field_key)).all()
        }
        created = 0
        for order, (key, label, section, field_type, is_autofill) in enumerate(FIELD_DEFINITIONS):
            if key in existing_keys:
                continue
            db.add(
                FieldDefinition(
                    id=uuid.uuid4(),
                    field_key=key,
                    field_label=label,
                    section=section,
                    field_type=field_type,
                    display_order=order,
                    is_autofill=is_autofill,
                )
            )
            created += 1
        db.commit()
        print(f"Seed complete: {created} new field definitions created, {len(existing_keys)} already existed.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
