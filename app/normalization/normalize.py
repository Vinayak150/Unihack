"""Stage 2: canonical normalization.

Takes DIRECT claims (raw value + raw unit, as extracted) and maps them to
approved UOM abbreviations and, for length-type values, trade-fraction
notation. This is purely deterministic — table lookups, not model calls —
per the challenge's "don't use an LLM for exact UOM/fraction conversion" rule.
Promotes the claim's provenance_type from DIRECT to NORMALIZED in place.
"""
from __future__ import annotations

from app.provenance.claims import Claim
from app.uom.engine import canonical_for_alias, format_with_space
from app.uom.fractions import decimal_to_fraction_string, fraction_string_to_decimal

LENGTH_UOMS = {"in", "ft", "mm", "cm", "m", "yd"}


def normalize_claim(claim: Claim) -> Claim:
    if claim.provenance_type != "DIRECT" or not claim.uom:
        return claim

    match = canonical_for_alias(claim.uom)
    canonical_uom = match.canonical or claim.uom

    value = claim.value
    if canonical_uom in LENGTH_UOMS and value:
        decimal = fraction_string_to_decimal(value)
        if decimal is not None:
            value = decimal_to_fraction_string(decimal)

    claim.value = value
    claim.uom = canonical_uom
    claim.provenance_type = "NORMALIZED"
    return claim


def normalize_all(claims: list[Claim]) -> list[Claim]:
    return [normalize_claim(c) for c in claims]


def formatted_value(claim: Claim) -> str:
    """Renders 'value uom' with the correct spacing rule, or just value if no uom."""
    if not claim.value:
        return ""
    if claim.uom:
        return format_with_space(claim.value, claim.uom)
    return claim.value
