"""Validation engine: schema, vocabulary, formatting, semantic, cross-field,
and source-presence checks, run against one enriched product record.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.lov.vocabulary import get_vocabulary
from app.manufacturer.resolver import get_resolver
from app.provenance.claims import ClaimRegistry
from app.uom.engine import canonical_for_alias

REQUIRED_SCHEMA_FIELDS = ["MANUFACTURER_NAME", "MANUFACTURER_PART_NUMBER", "Classpath"]
MAX_LENGTHS = {"INVOICE_DESC": 40, "MOBILE_DESC": 80}


@dataclass
class ValidationIssue:
    check: str
    field: str
    severity: str  # ERROR | WARNING
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(i.severity == "ERROR" for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "issues": [{"check": i.check, "field": i.field, "severity": i.severity, "message": i.message} for i in self.issues],
        }


def validate_record(
    record: dict,
    registry: ClaimRegistry,
    classpath: str | None,
    manufacturer_status: str,
    classification_status: str,
) -> ValidationReport:
    report = ValidationReport()

    # -- schema: required fields present
    for f in REQUIRED_SCHEMA_FIELDS:
        if not record.get(f):
            report.issues.append(ValidationIssue("schema.required_field", f, "ERROR" if f != "Classpath" else "WARNING", f"{f} is empty"))

    # -- formatting: character limits
    for f, max_len in MAX_LENGTHS.items():
        val = record.get(f) or ""
        if len(val) > max_len:
            report.issues.append(ValidationIssue("formatting.max_length", f, "WARNING", f"{f} is {len(val)} chars, exceeds {max_len}"))
    invoice = record.get("INVOICE_DESC") or ""
    if invoice and invoice != invoice.upper():
        report.issues.append(ValidationIssue("formatting.casing", "INVOICE_DESC", "WARNING", "INVOICE_DESC should be ALL CAPS"))

    # -- vocabulary: manufacturer/brand resolved against master data
    if manufacturer_status == "UNRESOLVED":
        report.issues.append(ValidationIssue("vocabulary.manufacturer", "MANUFACTURER_NAME", "ERROR", "manufacturer could not be resolved against master data"))
    elif manufacturer_status == "LOW_CONFIDENCE":
        report.issues.append(ValidationIssue("vocabulary.manufacturer", "MANUFACTURER_NAME", "WARNING", "manufacturer resolved at low confidence"))

    # -- semantic: classification resolved / compatible
    if classification_status == "UNRESOLVED":
        report.issues.append(ValidationIssue("semantic.classification", "Classpath", "WARNING", "classpath could not be determined from available evidence"))

    # -- vocabulary: attribute values in controlled vocabulary
    if classpath:
        vocab = get_vocabulary()
        for c in registry.claims:
            if c.provenance_type == "UNKNOWN" or not c.value:
                continue
            match = vocab.validate_value(classpath, c.attribute, c.value)
            if match.status == "NOT_IN_VOCABULARY":
                report.issues.append(ValidationIssue("vocabulary.attribute_value", c.attribute, "WARNING", f"'{c.value}' not in approved LOV for {c.attribute}"))

    # -- formatting: UOM values use approved abbreviations only
    for c in registry.claims:
        if c.uom and canonical_for_alias(c.uom).canonical is None:
            report.issues.append(ValidationIssue("formatting.uom", c.attribute, "WARNING", f"uom '{c.uom}' is not an approved abbreviation"))

    # -- cross-field: Manufacturer <-> Brand consistency (both present or both absent)
    manuf_present = bool(record.get("MANUFACTURER_NAME"))
    brand_present = bool(record.get("BRAND_NAME"))
    if manuf_present != brand_present:
        report.issues.append(ValidationIssue("cross_field.manufacturer_brand", "BRAND_NAME", "WARNING", "manufacturer and brand should both be resolved or both be absent"))

    # -- source: technical claims should carry evidence
    for c in registry.claims:
        if c.provenance_type in ("DIRECT", "NORMALIZED", "DERIVED") and c.value and not c.source_ids:
            report.issues.append(ValidationIssue("source.missing_evidence", c.attribute, "WARNING", f"claim for {c.attribute} has no source_ids"))

    return report
