"""Field-level and record-level confidence scoring.

Built from actual pipeline signals (match method, source authority, LOV
membership, validation results, contradiction count) - never the LLM's own
self-reported confidence statement.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.provenance.claims import ClaimRegistry
from app.validation.engine import ValidationReport

METHOD_WEIGHT = {
    "exact_normalized_match": 1.0, "mpn_prefix_pattern_match": 0.9, "brand_alias_token_match": 0.95,
    "fuzzy_match": 0.75, "unmatched_fallback": 0.4, "keyword_rule_match": 0.8, "none": 0.0,
}


@dataclass
class ConfidenceBreakdown:
    manufacturer_confidence: float
    classification_confidence: float
    attribute_confidence: float
    validation_confidence: float
    overall: float

    def to_dict(self) -> dict:
        return {
            "manufacturer_confidence": round(self.manufacturer_confidence, 4),
            "classification_confidence": round(self.classification_confidence, 4),
            "attribute_confidence": round(self.attribute_confidence, 4),
            "validation_confidence": round(self.validation_confidence, 4),
            "overall": round(self.overall, 4),
        }


def score_record(
    manufacturer_score: float,
    manufacturer_method: str,
    classification_score: float,
    registry: ClaimRegistry,
    validation: ValidationReport,
) -> ConfidenceBreakdown:
    manuf_conf = manufacturer_score * METHOD_WEIGHT.get(manufacturer_method, 0.5)

    class_conf = classification_score

    grounded = [c for c in registry.claims if c.provenance_type != "UNKNOWN"]
    attr_conf = sum(c.confidence for c in grounded) / len(grounded) if grounded else 0.0

    error_count = sum(1 for i in validation.issues if i.severity == "ERROR")
    warn_count = sum(1 for i in validation.issues if i.severity == "WARNING")
    validation_conf = max(0.0, 1.0 - 0.35 * error_count - 0.05 * warn_count)

    overall = (0.3 * manuf_conf + 0.25 * class_conf + 0.25 * attr_conf + 0.2 * validation_conf)
    return ConfidenceBreakdown(manuf_conf, class_conf, attr_conf, validation_conf, overall)
