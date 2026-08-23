"""Canonical claim / fact model.

Every attribute value the pipeline produces is a Claim before it is ever
rendered into a description or an output column. This is what makes the
system explainable and non-hallucinating: descriptions may only reference
values that exist as claims, and every claim carries a provenance type.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

PROVENANCE_TYPES = {"DIRECT", "NORMALIZED", "DERIVED", "INFERRED", "UNKNOWN", "CONFLICT"}


@dataclass
class Claim:
    attribute: str
    value: str | None
    uom: str | None
    provenance_type: str
    source_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    claim_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def __post_init__(self):
        if self.provenance_type not in PROVENANCE_TYPES:
            raise ValueError(f"invalid provenance_type {self.provenance_type!r}")

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "attribute": self.attribute,
            "value": self.value,
            "uom": self.uom,
            "provenance_type": self.provenance_type,
            "source_ids": self.source_ids,
            "confidence": round(self.confidence, 4),
        }


class ClaimRegistry:
    """Holds every claim produced for a single product record."""

    def __init__(self):
        self.claims: list[Claim] = []

    def add(self, claim: Claim) -> Claim:
        self.claims.append(claim)
        return claim

    def get(self, attribute: str) -> Claim | None:
        for c in self.claims:
            if c.attribute == attribute:
                return c
        return None

    def value_of(self, attribute: str, default=None):
        c = self.get(attribute)
        return c.value if c and c.value else default

    def grounded_attributes(self) -> set[str]:
        return {c.attribute for c in self.claims if c.value and c.provenance_type != "UNKNOWN"}

    def to_list(self) -> list[dict]:
        return [c.to_dict() for c in self.claims]
