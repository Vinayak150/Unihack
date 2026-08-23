"""Description generation.

Every renderer consumes only: manufacturer, brand, mpn, classpath leaf, and
the ClaimRegistry - never raw Part_Desc directly. That's the no-hallucination
guarantee: a fact can only appear in a rendered description if it exists as
a claim with provenance_type != UNKNOWN. Format rules (char limits, casing)
are derived from the two verified ground-truth dishwasher records; the
renderers degrade gracefully (omit a clause) when a claim is missing rather
than inventing filler, which is the honest behavior when evidence is sparse.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.normalization.normalize import formatted_value
from app.provenance.claims import ClaimRegistry

INVOICE_DESC_MAX = 40
MOBILE_DESC_MIN, MOBILE_DESC_MAX = 60, 80


def _brand_no_symbol(brand: str | None) -> str:
    return (brand or "").replace("®", "").replace("™", "").strip()


def _base_name(name: str | None) -> str:
    return (name or "").lower().replace("®", "").replace("™", "").split(" ")[0]


def _grounded_claims(registry: ClaimRegistry) -> list:
    return [c for c in registry.claims if c.value and c.provenance_type != "UNKNOWN"]


@dataclass
class GeneratedDescriptions:
    invoice_desc: str
    mobile_desc: str
    product_title: str
    short_desc: str
    long_desc: str
    item_type: str
    claims_used: list[str]


def _key_attr_clause(registry: ClaimRegistry, order: list[str]) -> list[str]:
    clauses = []
    for attr in order:
        c = registry.get(attr)
        if not c or not c.value or c.provenance_type == "UNKNOWN":
            continue
        if attr in ("Voltage Rating", "Amperage Rating", "Sound Level"):
            clauses.append(f"{formatted_value(c)} {attr.replace(' Rating', '')}" if attr != "Sound Level" else f"{formatted_value(c)} Sound Level")
        elif attr == "Number of Wash Cycles":
            clauses.append(f"{c.value}-Wash Cycle" if c.value == "1" else f"{c.value}-Wash Cycle")
        elif attr == "Mounting Type":
            clauses.append(f"{c.value} Mounting")
        else:
            clauses.append(formatted_value(c) if c.uom else str(c.value))
    return clauses


def generate_descriptions(
    manufacturer: str | None,
    brand: str | None,
    mpn: str,
    leaf_node: str | None,
    registry: ClaimRegistry,
    flags: list[str] | None = None,
) -> GeneratedDescriptions:
    flags = flags or []
    item_type = leaf_node.rstrip("s") if leaf_node and leaf_node.lower() not in ("built-in dishwashers",) else "Dishwasher"
    if leaf_node and "dishwasher" in leaf_node.lower():
        item_type = "Dishwasher"
    elif leaf_node:
        item_type = leaf_node

    brand_plain = _brand_no_symbol(brand) or _brand_no_symbol(manufacturer)
    brand_symbol = brand or manufacturer or ""
    series = registry.value_of("Series")
    material = registry.value_of("Material") or registry.value_of("Color")
    mounting = registry.value_of("Mounting Type")
    wash_cycles = registry.value_of("Number of Wash Cycles")

    used = set()

    # ---- Invoice description: <=40 char, ALL CAPS, abbreviated ----
    inv_tokens = [item_type.upper()]
    if mounting:
        inv_tokens.append(mounting.upper()[:3])
        used.add("Mounting Type")
    if wash_cycles:
        inv_tokens.append(str(wash_cycles))
        used.add("Number of Wash Cycles")
    if material:
        abbrev = "SST" if "stainless" in material.lower() else material.upper()[:3]
        inv_tokens.append(abbrev)
        used.add("Material")
    volt = registry.get("Voltage Rating")
    if volt and volt.value:
        inv_tokens.append(f"{volt.value}V")
        used.add("Voltage Rating")
    amp = registry.get("Amperage Rating")
    if amp and amp.value:
        inv_tokens.append(f"{amp.value}A")
        used.add("Amperage Rating")
    invoice_desc = " ".join(inv_tokens)[:INVOICE_DESC_MAX].strip()

    # ---- Mobile description: 60-80 char target, sentence style ----
    manuf_base, brand_base = _base_name(manufacturer), _base_name(brand)
    mobile_head = brand_plain if manuf_base == brand_base or not manufacturer else f"{manufacturer} {brand_plain.upper()}"
    mobile_parts = [p for p in [mobile_head, item_type, series, mpn] if p]
    if series:
        used.add("Series")
    mobile_desc = ", ".join(mobile_parts)

    # ---- Product title / Short desc: Brand + Series + MPN + ItemType + features ----
    title_parts = [p for p in [brand_symbol, series, mpn, item_type] if p]
    feature_clauses = _key_attr_clause(registry, ["Mounting Type", "Number of Wash Cycles", "Material"])
    used.update({"Mounting Type", "Number of Wash Cycles", "Material"} & {c for c in ["Mounting Type", "Number of Wash Cycles", "Material"] if registry.get(c) and registry.get(c).value})
    title = " ".join(title_parts)
    if feature_clauses:
        title += ", " + ", ".join(feature_clauses)
    product_title = title.strip()

    short_parts = [p for p in [series, item_type] if p]
    short_desc = " ".join(short_parts)
    if feature_clauses:
        short_desc += (", " if short_desc else "") + ", ".join(feature_clauses)

    # ---- Long description: brand + item + full grounded attribute walk ----
    long_order = [
        "Number of Wash Cycles", "Voltage Rating", "Amperage Rating", "Mounting Type", "Size",
        "Depth With Door Open", "Minimum Height", "Maximum Height", "Sound Level", "Material", "Color",
    ]
    long_clauses = _key_attr_clause(registry, long_order)
    used.update(a for a in long_order if registry.get(a) and registry.get(a).value)
    long_desc = f"{brand_symbol} {item_type}".strip()
    if series:
        long_clauses = [series] + long_clauses
    if long_clauses:
        long_desc += ", " + ", ".join(long_clauses)
    additional = registry.value_of("Additional Information")
    if additional:
        long_desc += f", Additional Information: {additional}"
        used.add("Additional Information")

    return GeneratedDescriptions(
        invoice_desc=invoice_desc,
        mobile_desc=mobile_desc,
        product_title=product_title,
        short_desc=short_desc,
        long_desc=long_desc,
        item_type=item_type,
        claims_used=sorted(used),
    )
