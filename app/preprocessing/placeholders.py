"""Placeholder detection — treats "-- Unbranded --" style values as missing,
never as data, per the challenge's placeholder-handling rule."""
from __future__ import annotations

import csv

from app.config.settings import settings

_DEFAULT_PLACEHOLDERS = {
    "-- unbranded --", "-- no unilog brand --", "-- no dib brand --", "--",
    "n/a", "na", "unknown", "none", "null", "-", "tbd",
    "not available", "not specified", "",
}


def _load_placeholders() -> set[str]:
    path = settings.REFERENCE_DIR / "placeholders.csv"
    if not path.exists():
        return set(_DEFAULT_PLACEHOLDERS)
    values = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            values.add((row.get("placeholder_value") or "").strip().lower())
    values.add("")
    return values


PLACEHOLDERS = _load_placeholders()


def is_placeholder(value) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text.lower() in PLACEHOLDERS


def clean(value):
    """Returns None for placeholder/empty values, else the trimmed string."""
    if is_placeholder(value):
        return None
    return str(value).strip()
