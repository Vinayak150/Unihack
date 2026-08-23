"""Stage 1 deterministic evidence extraction.

Pulls DIRECT claims straight out of Part_Desc using regex patterns tied to
the UOM engine and LOV attribute specs. This is what fires when the value is
*actually present in the text* — dimensions, grit, diameter, voltage,
material codes, etc. Nothing here is guessed: if a pattern doesn't match,
no claim is produced, and the attribute is later reported UNKNOWN rather
than fabricated (see app/enrichment/category_processor.py).
"""
from __future__ import annotations

import re

from app.provenance.claims import Claim
from app.uom.engine import canonical_for_alias, format_with_space
from app.uom.fractions import decimal_to_fraction_string, fraction_string_to_decimal

_DIM_TOKEN_RE = re.compile(r"(\d+(?:\.\d+)?(?:-\d+/\d+)?(?:/\d+)?)\s*[xX×]\s*", re.UNICODE)
_NUM_RE = re.compile(r"^\d+(?:\.\d+)?(?:-\d+/\d+|/\d+)?$")

MATERIAL_COLOR_CODES = {
    "ss": "Stainless Steel", "sst": "Stainless Steel", "bss": "Black Stainless Steel",
    "wh": "White", "bk": "Black", "blk": "Black", "br": "Bronze", "mb": "Matte Black",
    "bz": "Bronze", "biv": "Brushed Ivory", "wt": "White",
}

VOLTAGE_AMP_RE = re.compile(r"\b(\d{2,3})\s?V\b.{0,15}?\b(\d{1,2})\s?A\b", re.IGNORECASE)
SOUND_RE = re.compile(r"\b(\d{1,3})\s?dBA?\b", re.IGNORECASE)
GRIT_RE = re.compile(r"\bP(\d{2,4})\b")
GAUGE_AMPERAGE_ONLY_RE = re.compile(r"\b(\d{1,2})\s?A\b(?!\w)")
DIAMETER_INCH_RE = re.compile(r'(\.?\d+(?:\.\d+)?(?:-\d+/\d+|/\d+)?)\s*"')


def _num_to_str(raw: str) -> str:
    val = fraction_string_to_decimal(raw)
    return raw if val is None else raw  # keep original textual form; already trade-formatted


def extract_dimension_string(text: str) -> str | None:
    """'5"x.045"x7/8"' or '24" x 24-1/4"' style multi-part dims. Returns a
    normalized 'A in x B in x C in' style string, or None."""
    matches = list(_DIM_TOKEN_RE.finditer(text))
    parts = []
    idx = 0
    for m in re.finditer(r'(\d+(?:\.\d+)?(?:-\d+/\d+)?(?:/\d+)?)\s*"', text):
        parts.append(m.group(1))
    if len(parts) >= 2:
        return " x ".join(f"{p} in" for p in parts)
    return None


def extract_deterministic_claims(part_desc: str, mpn: str = "", applicable_attributes: set[str] | None = None) -> list[Claim]:
    claims: list[Claim] = []
    text = part_desc or ""
    applicable_attributes = applicable_attributes or set()
    # Material/color code (SS, BSS, WH, BK...) maps to whichever attribute the
    # classpath actually exposes; defaults to "Material" if neither is known.
    color_attr = "Material" if "Material" in applicable_attributes or not applicable_attributes else (
        "Color" if "Color" in applicable_attributes else "Material"
    )

    for tok in re.findall(r"\b([A-Za-z]{2,3})\b", text):
        low = tok.lower()
        if low in MATERIAL_COLOR_CODES:
            claims.append(Claim(color_attr, MATERIAL_COLOR_CODES[low], None, "DIRECT", ["input_row"], 0.8))
            break  # first hit only; avoid duplicate/contradictory codes in one string

    # Voltage + Amperage pair, e.g. "120V 15A"
    m = VOLTAGE_AMP_RE.search(text)
    if m:
        claims.append(Claim("Voltage Rating", m.group(1), "V", "DIRECT", ["input_row"], 0.95))
        claims.append(Claim("Amperage Rating", m.group(2), "A", "DIRECT", ["input_row"], 0.95))
    else:
        m2 = GAUGE_AMPERAGE_ONLY_RE.search(text)
        if m2:
            claims.append(Claim("Amperage Rating", m2.group(1), "A", "DIRECT", ["input_row"], 0.85))

    # Sound level
    m = SOUND_RE.search(text)
    if m:
        claims.append(Claim("Sound Level", m.group(1), "dBA", "DIRECT", ["input_row"], 0.9))

    # Grit (abrasives: P150, P80...)
    m = GRIT_RE.search(text)
    if m:
        claims.append(Claim("Grit", f"P{m.group(1)}", None, "DIRECT", ["input_row"], 0.95))

    # Diameter in inches, e.g. 9", 4-1/2"
    diam_matches = DIAMETER_INCH_RE.findall(text)
    if diam_matches:
        claims.append(Claim("Diameter", diam_matches[0], "in", "DIRECT", ["input_row"], 0.9))
        if len(diam_matches) >= 2:
            claims.append(Claim("Thickness", diam_matches[1], "in", "DIRECT", ["input_row"], 0.85))
        if len(diam_matches) >= 3:
            claims.append(Claim("Arbor/Bore Size", diam_matches[2], "in", "DIRECT", ["input_row"], 0.85))

    # Wattage (lighting), e.g. "10w LED"
    m = re.search(r"\b(\d{1,3})\s?[wW]\b", text)
    if m and "V" not in text.upper()[:0]:
        claims.append(Claim("Wattage", m.group(1), "W", "DIRECT", ["input_row"], 0.85))

    # Color temperature, e.g. "50k", "27k", "3000K"
    m = re.search(r"\b(\d{2}|\d{4})[kK]\b", text)
    if m:
        val = m.group(1)
        kelvin = val if len(val) == 4 else f"{val}00"
        claims.append(Claim("Color Temperature", kelvin, "K", "DIRECT", ["input_row"], 0.8))

    # Length in feet, e.g. "6'"
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*'", text)
    if m:
        claims.append(Claim("Length", m.group(1), "ft", "DIRECT", ["input_row"], 0.85))

    # "Display Only" / similar trailing qualifiers become a feature/flag claim
    if re.search(r"display\s+only", text, re.IGNORECASE):
        claims.append(Claim("Additional Information", "Display Only", None, "DIRECT", ["input_row"], 0.9))

    return claims
