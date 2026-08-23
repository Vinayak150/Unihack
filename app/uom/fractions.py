"""Deterministic decimal <-> trade-fraction conversion (64ths lookup).

Never generated probabilistically: this is a closed, exact lookup table
identical in shape to the described Decimal_Fraction.xlsx (1/64 .. 63/64).
"""
from __future__ import annotations

import csv
from fractions import Fraction

from app.config.settings import settings

_DECIMAL_TO_FRACTION: dict[float, str] = {}
_FRACTION_TO_DECIMAL: dict[str, float] = {}


def _load():
    path = settings.EXTERNAL_REFERENCE_DIR / "fractions.csv"
    if not path.exists():
        path = settings.REFERENCE_DIR / "fractions.csv"
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            frac, dec = row["fraction"], float(row["decimal"])
            _DECIMAL_TO_FRACTION[round(dec, 6)] = frac
            _FRACTION_TO_DECIMAL[frac] = dec


_load()


def nearest_64th(value: float) -> Fraction:
    return Fraction(round(value * 64), 64)


def decimal_to_fraction_string(value: float, max_denominator: int = 64) -> str:
    """50.25 -> '50-1/4'; 12.0 -> '12'; 0.5 -> '1/2'."""
    whole = int(value)
    frac_part = round(value - whole, 6)
    if frac_part == 0:
        return str(whole)
    frac = nearest_64th(abs(frac_part))
    if frac.numerator == 0:
        return str(whole)
    frac_str = _DECIMAL_TO_FRACTION.get(round(float(frac), 6)) or f"{frac.numerator}/{frac.denominator}"
    return f"{whole}-{frac_str}" if whole else frac_str


def fraction_string_to_decimal(text: str) -> float | None:
    """'50-1/4' or '1/2' or '50' -> float. Returns None if unparseable."""
    text = (text or "").strip()
    if not text:
        return None
    whole = 0
    rest = text
    if "-" in text:
        whole_part, rest = text.split("-", 1)
        try:
            whole = int(whole_part)
        except ValueError:
            return None
    if "/" in rest:
        known = _FRACTION_TO_DECIMAL.get(rest)
        if known is not None:
            return round(whole + known, 6)
        try:
            num, den = rest.split("/")
            return round(whole + float(num) / float(den), 6)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return round(whole + float(rest), 6)
    except ValueError:
        return None
