"""Controlled vocabulary (LOV) engine.

Attribute values are constrained to what the taxonomy_lov table allows for a
given classpath - the LLM/extraction layer proposes, this layer disposes.
Raw value -> candidate retrieval -> alias/synonym resolution -> constraint
validation -> canonical LOV value (or UNKNOWN if nothing matches).
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.config.settings import settings


@dataclass
class AttributeSpec:
    classpath: str
    attribute_label: str
    normalized_label: str
    data_type: str
    uom_type: str
    filtering: bool
    keywords: list[str]
    allowed_values: list[str]
    guidelines: str


@dataclass
class LovMatch:
    attribute_label: str
    raw_value: str
    canonical_value: str | None
    method: str
    score: float
    status: str  # IN_VOCABULARY | NOT_IN_VOCABULARY | NO_CONSTRAINT
    evidence: list[str] = field(default_factory=list)


class LovVocabulary:
    def __init__(self, path=None):
        self.by_classpath: dict[str, list[AttributeSpec]] = defaultdict(list)
        self._load(path)

    def _load(self, path):
        p = path or settings.EXTERNAL_REFERENCE_DIR / "taxonomy_lov.csv"
        if not p.exists():
            p = settings.REFERENCE_DIR / "taxonomy_lov.csv"
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                guideline_raw = row.get("Guidelines") or ""
                allowed_values = [v.strip() for v in guideline_raw.split("|") if v.strip()] if row.get("Data Type") == "enum" else []
                spec = AttributeSpec(
                    classpath=row["Classpath"].strip(),
                    attribute_label=row["Attribute Label"].strip(),
                    normalized_label=row["Normalized Label"].strip(),
                    data_type=row["Data Type"].strip(),
                    uom_type=row.get("UOM Type", "").strip(),
                    filtering=(row.get("Filtering", "N").strip().upper() == "Y"),
                    keywords=[k.strip() for k in (row.get("Keywords") or "").split("|") if k.strip()],
                    allowed_values=allowed_values,
                    guidelines=guideline_raw,
                )
                self.by_classpath[spec.classpath].append(spec)

    def attributes_for(self, classpath: str) -> list[AttributeSpec]:
        return self.by_classpath.get(classpath, [])

    def validate_value(self, classpath: str, attribute_label: str, raw_value: str) -> LovMatch:
        specs = [s for s in self.attributes_for(classpath) if s.attribute_label == attribute_label]
        if not specs or not specs[0].allowed_values:
            return LovMatch(attribute_label, raw_value, raw_value, "no_constraint", 1.0, "NO_CONSTRAINT",
                             ["attribute has no enumerated LOV constraint; free text/numeric accepted as-is"])
        spec = specs[0]
        raw_norm = (raw_value or "").strip().lower()
        for allowed in spec.allowed_values:
            if allowed.lower() == raw_norm:
                return LovMatch(attribute_label, raw_value, allowed, "exact_match", 1.0, "IN_VOCABULARY",
                                 [f"'{raw_value}' exact-matches LOV value '{allowed}'"])
        best, best_score = None, 0
        for allowed in spec.allowed_values:
            score = fuzz.ratio(raw_norm, allowed.lower())
            if score > best_score:
                best, best_score = allowed, score
        if best and best_score >= 85:
            return LovMatch(attribute_label, raw_value, best, "fuzzy_match", best_score / 100, "IN_VOCABULARY",
                             [f"'{raw_value}' fuzzy-matches LOV value '{best}' ({best_score:.0f})"])
        return LovMatch(attribute_label, raw_value, None, "no_match", best_score / 100 if best else 0.0, "NOT_IN_VOCABULARY",
                         [f"'{raw_value}' did not match any allowed value for '{attribute_label}': {spec.allowed_values}"])


_singleton: LovVocabulary | None = None


def get_vocabulary() -> LovVocabulary:
    global _singleton
    if _singleton is None:
        _singleton = LovVocabulary()
    return _singleton
