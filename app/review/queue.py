"""Human review queue construction — decides whether a record needs a human
in the loop, and why, in a structured, explainable form."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.config.settings import settings


@dataclass
class ReviewReason:
    code: str
    message: str
    field: str | None = None


@dataclass
class ReviewEntry:
    requires_review: bool
    reasons: list[ReviewReason] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "requires_review": self.requires_review,
            "reasons": [{"code": r.code, "message": r.message, "field": r.field} for r in self.reasons],
        }


def build_review_entry(
    manufacturer_status: str,
    classification_status: str,
    validation_passed: bool,
    validation_error_count: int,
    overall_confidence: float,
    lov_mismatches: int,
) -> ReviewEntry:
    reasons: list[ReviewReason] = []

    if manufacturer_status == "UNRESOLVED":
        reasons.append(ReviewReason("unresolved_manufacturer", "Manufacturer could not be resolved against master data", "MANUFACTURER_NAME"))
    elif manufacturer_status == "LOW_CONFIDENCE":
        reasons.append(ReviewReason("uncertain_manufacturer", "Manufacturer resolved below the confident-match threshold", "MANUFACTURER_NAME"))

    if classification_status in ("UNRESOLVED", "LOW_CONFIDENCE"):
        reasons.append(ReviewReason("uncertain_classification", "Classpath was not confidently determined", "Classpath"))

    if not validation_passed:
        reasons.append(ReviewReason("validation_failed", f"{validation_error_count} schema/vocabulary validation error(s)", None))

    if lov_mismatches > 0:
        reasons.append(ReviewReason("lov_mismatch", f"{lov_mismatches} attribute value(s) not found in controlled vocabulary", None))

    if overall_confidence < settings.REVIEW_CONFIDENCE_THRESHOLD:
        reasons.append(ReviewReason("low_confidence", f"overall confidence {overall_confidence:.2f} below threshold {settings.REVIEW_CONFIDENCE_THRESHOLD}", None))

    return ReviewEntry(requires_review=bool(reasons), reasons=reasons)
