"""Maps a ProcessingResult onto the exact official 252-column output schema.

Every column not derivable from grounded pipeline output is left as an empty
string - never guessed. This is also where "digital assets" (images, spec
sheets, manuals) would be populated by a manufacturer-asset connector; none
is wired up in this build (no live retrieval access - see
docs/design-decisions.md), so those columns are honestly empty rather than
faked with placeholder filenames.
"""
from __future__ import annotations

import csv

from app.config.settings import settings
from app.core.output_schema import OutputSchema
from app.orchestration.pipeline import ProcessingResult

_DEPT_CLASS_FINE: dict[str, tuple[str, str, str]] = {}


def _load_dept_class_fine():
    if _DEPT_CLASS_FINE:
        return
    path = settings.EXTERNAL_REFERENCE_DIR / "classpath_dept_class_fine.csv"
    if not path.exists():
        path = settings.REFERENCE_DIR / "classpath_dept_class_fine.csv"
    if not path.exists():
        return
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            _DEPT_CLASS_FINE[row["Classpath"].strip()] = (row["Dept"].strip(), row["Class"].strip(), row["Fine"].strip())


def _dept_class_fine(classpath: str | None) -> tuple[str, str, str]:
    """Dept/Class/Fine is a separate, coarser taxonomy from Classpath - it
    cannot be derived by splitting the Classpath string (their label text
    doesn't match). Only classpaths with a confirmed mapping get populated;
    everything else stays honestly empty rather than guessed."""
    _load_dept_class_fine()
    if not classpath:
        return "", "", ""
    return _DEPT_CLASS_FINE.get(classpath, ("", "", ""))


def to_output_record(schema: OutputSchema, result: ProcessingResult) -> dict:
    raw = result.input_row
    record = schema.empty_record()

    dept, cls, fine = _dept_class_fine(result.classification.classpath if result.classification else None)
    record["Dept"] = dept
    record["Class"] = cls
    record["Fine"] = fine

    record["Mfg_Part_Num"] = raw.get("Mfg_Part_Num", "")
    record["Part_Desc"] = raw.get("Part_Desc", "")
    record["E1_Brand"] = raw.get("E1_Brand", "")
    record["Unilog_Brand"] = raw.get("Unilog_Brand", "")
    record["DIB_Brand"] = raw.get("DIB_Brand", "")
    record["Part_Manuf"] = raw.get("Part_Manuf", "")

    mr = result.manufacturer_resolution
    if mr:
        record["MANUFACTURER_NAME"] = mr.canonical_value or ""
        record["BRAND_NAME"] = mr.brand_name or ""
    record["MANUFACTURER_PART_NUMBER"] = raw.get("Mfg_Part_Num", "")

    if result.classification and result.classification.classpath:
        record["Classpath"] = result.classification.classpath

    if result.descriptions:
        d = result.descriptions
        record["MOBILE_DESC"] = d.mobile_desc
        record["INVOICE_DESC"] = d.invoice_desc
        record["SHORT_DESC"] = d.short_desc
        record["LONG_DESC1"] = d.long_desc
        record["Product Name"] = d.item_type

    for i, flag in enumerate(result.flags[:20], start=1):
        record[f"ITEM_FEATURES_{i}"] = flag

    if result.claim_registry:
        grounded = [c for c in result.claim_registry.claims if c.value and c.provenance_type != "UNKNOWN"]
        for i, (label_col, value_col, uom_col) in enumerate(schema.attribute_slots()):
            if i >= len(grounded):
                break
            claim = grounded[i]
            record[label_col] = claim.attribute
            record[value_col] = claim.value or ""
            record[uom_col] = claim.uom or ""

    record["Actual Image (Yes/No)"] = "No"

    return record
