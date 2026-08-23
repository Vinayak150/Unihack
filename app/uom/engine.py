"""Deterministic unit-of-measure normalization engine.

Table-driven, not LLM-driven: mapping "inches"/"IN."/'"' -> "in" is a lookup,
not a reasoning task. Also owns the number+unit spacing rule (always a space,
e.g. "24 in" not "24in") and fraction rendering (delegates to app.uom.fractions).
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass

from app.config.settings import settings
from app.uom.fractions import decimal_to_fraction_string

_ALIAS_TO_CANONICAL: dict[str, str] = {}
_TYPE_TO_CANONICAL: dict[str, str] = {}


def _load():
    path = settings.EXTERNAL_REFERENCE_DIR / "uom_standards.csv"
    if not path.exists():
        path = settings.REFERENCE_DIR / "uom_standards.csv"
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            canonical = row["canonical_uom"].strip()
            mtype = row["measurement_type"].strip()
            _TYPE_TO_CANONICAL[mtype.lower()] = canonical
            _ALIAS_TO_CANONICAL[canonical.lower()] = canonical
            for alias in row["raw_variants"].split("|"):
                alias = alias.strip().lower()
                if alias:
                    _ALIAS_TO_CANONICAL[alias] = canonical


_load()


@dataclass
class UomMatch:
    canonical: str | None
    measurement_type: str | None
    matched_alias: str | None


def canonical_for_alias(raw_unit: str) -> UomMatch:
    if not raw_unit:
        return UomMatch(None, None, None)
    key = raw_unit.strip().lower().rstrip(".")
    canonical = _ALIAS_TO_CANONICAL.get(key)
    if canonical is None:
        return UomMatch(None, None, None)
    return UomMatch(canonical, None, key)


def canonical_for_type(measurement_type: str) -> str | None:
    return _TYPE_TO_CANONICAL.get((measurement_type or "").lower())


_NUM_UNIT_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>in\.?|inches?|ft\.?|feet|mm|cm|m\b|yd|volts?|v\b|amps?|a\b|"
    r"watts?|w\b|hz|lbs?|oz|kg|g\b|gal|qt|l\b|psi|db a?|dba|db\b|°?f\b|°?c\b|k\b|lm|rpm|hr|min|sec|ga|awg)",
    re.IGNORECASE,
)


def normalize_value_unit(number: float | str, raw_unit: str, prefer_fraction: bool = True) -> tuple[str, str]:
    """Returns (normalized_number_string, canonical_uom). Converts decimals to
    trade fractions for length-like units when prefer_fraction is True, e.g.
    50.25 -> '50-1/4' with unit 'in'."""
    match = canonical_for_alias(raw_unit)
    canonical = match.canonical or raw_unit.strip()
    num = float(number)
    if prefer_fraction and canonical == "in":
        num_str = decimal_to_fraction_string(num)
    elif num == int(num):
        num_str = str(int(num))
    else:
        num_str = f"{num:g}"
    return num_str, canonical


def format_with_space(number_str: str, uom: str) -> str:
    """Enforces 'always a space between the number and the unit' except for
    the small set of unit symbols that are conventionally unspaced (%, #)."""
    if uom in ("%", "#"):
        return f"{number_str}{uom}"
    return f"{number_str} {uom}".strip()


def extract_number_unit_pairs(text: str) -> list[tuple[float, str, str]]:
    """Finds (value, raw_unit, matched_span) occurrences of number+unit in free text."""
    out = []
    for m in _NUM_UNIT_RE.finditer(text or ""):
        try:
            val = float(m.group("num"))
        except ValueError:
            continue
        out.append((val, m.group("unit"), m.group(0)))
    return out
