"""
Seeds the field_definitions table with the EXACT field set from the
Clinvedica Excel template (Template__1_.xlsx, "Prospective"/"Remnant"
sheets), organized into the template's own sections.

Run with:

    uv run python scripts/seed_field_definitions.py

Idempotent and self-correcting:
  - Existing rows whose field_key is in CANONICAL_FIELD_KEYS are updated
    in place (label/section/order/type/autofill) if they differ.
  - Rows with a field_key NOT in CANONICAL_FIELD_KEYS are DEACTIVATED
    (is_active=False), not deleted — this is what cleans up the earlier,
    incorrect field set (invented fields like "accession-number",
    "chemotherapy-regimen", etc. that were never in the real template).
    Deactivating rather than deleting preserves any historical sample
    data that might reference them, while making sure they no longer
    appear in the add-sample form or bulk-ingest column matching.

IMPORTANT: bulk ingestion matches Excel column headers against
`field_label` here (see app/services/bulk_ingest_service.py). If you
change a field_label, the corresponding column header in your Excel
template must match exactly (whitespace-insensitive, case-insensitive).
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.field_definition import FieldDefinition

# (field_key, field_label, section, field_type, is_autofill)
# Order here IS the display_order within each section.
FIELD_DEFINITIONS = [
    # --- Case Details --- (Subject ID / Sample ID are dedicated Sample
    # columns, not field_definitions — see app/models/sample.py)
    ("type-of-tissue", "Type of Tissue", "case_details", "text", False),
    ("sample-category", "Sample Category", "case_details", "select", False),  # Prospective / Remnant

    # --- Demographic Details ---
    ("age", "Age", "demographic_details", "number", True),
    ("gender", "Gender", "demographic_details", "select", True),
    ("ethnicity", "Ethnicity", "demographic_details", "text", True),
    ("country-of-origin", "Country Of Origin", "demographic_details", "text", True),

    # --- Diagnosis Information ---
    ("biopsy-surgery", "Biopsy/Surgery", "diagnosis_information", "select", False),
    ("diagnostic-procedure", "Diagnostic Procedure", "diagnosis_information", "text", False),
    ("origin-site", "Origin Site", "diagnosis_information", "text", True),
    ("diagnosis-result", "Diagnosis Result", "diagnosis_information", "text", True),
    ("grade", "Grade", "diagnosis_information", "text", False),
    ("stage", "Stage", "diagnosis_information", "text", False),
    ("t", "T", "diagnosis_information", "text", False),
    ("n", "N", "diagnosis_information", "text", False),
    ("m", "M", "diagnosis_information", "text", False),

    # --- Sample Information ---
    ("sample-type", "Sample Type", "sample_information", "text", False),
    ("date-of-sample-collection", "Date of Sample Collection", "sample_information", "date", False),
    ("date-of-reporting", "Date of Reporting", "sample_information", "date", False),
    ("fixation-used", "Fixation Used", "sample_information", "text", False),
    ("tumor-percent", "Tumor %", "sample_information", "text", False),
    ("necrosis-percent", "Necrosis %", "sample_information", "text", False),
    ("storage-temperature", "Storage Temperature", "sample_information", "text", False),

    # --- Serology Report ---
    ("hiv", "HIV", "serology_report", "select", False),
    ("hbv", "HBV", "serology_report", "select", False),
    ("hcv", "HCV", "serology_report", "select", False),

    # --- Treatment Detail ---
    ("treatment-information", "Treatment Information (Adjuvant/Neo-Adjuvant)", "treatment_detail", "select", False),
    ("neo-adjuvant-treatment-details", "If Neo-Adjuvant (Treatment Details)", "treatment_detail", "text", False),

    # --- Biomarker Characterization ---
    ("biomarker-details", "Biomarker Details", "biomarker_characterization", "text", False),
]

CANONICAL_FIELD_KEYS = {key for key, *_ in FIELD_DEFINITIONS}


def run() -> None:
    db = SessionLocal()
    try:
        existing = {fd.field_key: fd for fd in db.execute(select(FieldDefinition)).scalars()}

        created, updated, deactivated = 0, 0, 0

        for order, (key, label, section, field_type, is_autofill) in enumerate(FIELD_DEFINITIONS):
            if key in existing:
                fd = existing[key]
                changed = (
                    fd.field_label != label
                    or fd.section != section
                    or fd.field_type != field_type
                    or fd.display_order != order
                    or fd.is_autofill != is_autofill
                    or not fd.is_active
                )
                if changed:
                    fd.field_label = label
                    fd.section = section
                    fd.field_type = field_type
                    fd.display_order = order
                    fd.is_autofill = is_autofill
                    fd.is_active = True
                    updated += 1
            else:
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

        # Deactivate anything in the DB that's no longer part of the
        # canonical template field set (this is what removes the earlier
        # invented fields from the form/bulk-ingest matching).
        for key, fd in existing.items():
            if key not in CANONICAL_FIELD_KEYS and fd.is_active:
                fd.is_active = False
                deactivated += 1

        db.commit()
        print(
            f"Seed complete: {created} created, {updated} updated, "
            f"{deactivated} deactivated (no longer in the template)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    run()
