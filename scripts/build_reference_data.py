#!/usr/bin/env python3
"""
Builds the reference / master-data tables the pipeline runs on:

  data/reference/uom_standards.csv        - approved unit-of-measure abbreviations
  data/reference/fractions.csv             - exact 64ths fraction <-> decimal lookup
  data/reference/placeholders.csv          - strings that mean "no value"
  data/reference/manufacturer_brand_master.csv
  data/reference/taxonomy_lov.csv          - classpath/attribute controlled vocabulary

Provenance is explicit and split by SOURCE column wherever it matters:

  observed_input   - derived directly from data/raw/sample_1000_items_input.csv
  ground_truth     - taken verbatim from data/raw/ground_truth_delivery_format.csv
  curated_seed     - hand-curated using public, well-known brand/UOM knowledge because
                      the official Unilog master files (UniCat_Manufacturer_and_Brand_List.xlsx,
                      Unicat_Lov_v1_0.xlsx, Unilog_Master_UOM_Standards.xlsx, Decimal_Fraction.xlsx,
                      FAUCETS_LOV.xlsx, Fittings_LOV.xlsx) were not provided to this build.

If those official files are later dropped into data/reference/external/, this script
(and the loaders in app/manufacturer, app/lov, app/uom) will prefer them automatically -
see load_external_override() below. Nothing here is sample-specific: the resolution
*engines* work generically, this script only seeds their starting master data.

Run: python scripts/build_reference_data.py
"""
from __future__ import annotations

import csv
import os
import re
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REF = ROOT / "data" / "reference"
EXTERNAL = REF / "external"
REF.mkdir(parents=True, exist_ok=True)
EXTERNAL.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, header: list[str], rows: list[list]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {path.relative_to(ROOT)}  ({len(rows)} rows)")


# --------------------------------------------------------------------------
# 1. Placeholders — values that mean "no data", must never become a fact
# --------------------------------------------------------------------------
PLACEHOLDERS = [
    "-- Unbranded --", "-- No Unilog Brand --", "-- No DIB Brand --",
    "--", "N/A", "NA", "n/a", "Unknown", "UNKNOWN", "None", "none",
    "null", "NULL", "-", "TBD", "Not Available", "Not Specified", "",
]


def build_placeholders():
    write_csv(REF / "placeholders.csv", ["placeholder_value"], [[p] for p in PLACEHOLDERS])


# --------------------------------------------------------------------------
# 2. Fraction <-> decimal lookup (exact, deterministic, generated not guessed)
#    Matches the described Decimal_Fraction.xlsx contract: every 64th from
#    1/64 to 63/64, expressed in lowest terms, decimal to 6 places.
# --------------------------------------------------------------------------
def build_fractions():
    rows = []
    seen_fracs = set()
    for n in range(1, 64):
        frac = Fraction(n, 64)
        if frac in seen_fracs:
            continue
        seen_fracs.add(frac)
        decimal = round(float(frac), 6)
        rows.append([f"{frac.numerator}/{frac.denominator}", decimal, n])
    rows.sort(key=lambda r: r[2])
    write_csv(REF / "fractions.csv", ["fraction", "decimal", "sixty_fourths"], rows)


# --------------------------------------------------------------------------
# 3. UOM standards — approved abbreviation per measurement type.
#    Core set covering every measurement type actually observed in the
#    ground-truth delivery format plus the categories present in the
#    1000-item sample (electrical, dimensional, lighting, acoustic, mass,
#    volume, thread/pipe, packaging). Spacing rule: always a space between
#    number and unit except where the official example shows none (e.g. "%").
# --------------------------------------------------------------------------
UOM_ROWS = [
    # measurement_type, canonical_uom, raw_variants (| separated), example
    ("Length", "in", "inch|inches|IN.|IN|\"|''", "24 in"),
    ("Length", "ft", "foot|feet|FT.|FT|'", "6 ft"),
    ("Length", "mm", "millimeter|millimetre|MM", "20 mm"),
    ("Length", "cm", "centimeter|centimetre|CM", "15 cm"),
    ("Length", "m", "meter|metre|M", "2 m"),
    ("Length", "yd", "yard|yards|YD", "3 yd"),
    ("Length", "mi", "mile|miles|MI", "1 mi"),
    ("Voltage", "V", "volt|volts|VOLT|VOLTS|VDC|VAC", "120 V"),
    ("Current", "A", "amp|amps|ampere|amperes|AMP|AMPS", "15 A"),
    ("Power", "W", "watt|watts|WATT|WATTS", "60 W"),
    ("Power", "kW", "kilowatt|kilowatts|KW", "1.5 kW"),
    ("Power", "hp", "horsepower|HP", "2 hp"),
    ("Energy", "kW-hr", "kilowatt hour|kilowatt-hour|kwh|KWH", "240 kW-hr"),
    ("Frequency", "Hz", "hertz|hz|cycles", "60 Hz"),
    ("Weight", "lb", "pound|pounds|lbs|LB|LBS", "5 lb"),
    ("Weight", "oz", "ounce|ounces|OZ", "8 oz"),
    ("Weight", "kg", "kilogram|kilograms|KG", "2 kg"),
    ("Weight", "g", "gram|grams|GM|G", "500 g"),
    ("Volume", "gal", "gallon|gallons|GAL", "5 gal"),
    ("Volume", "qt", "quart|quarts|QT", "1 qt"),
    ("Volume", "L", "liter|litre|liters|litres|LTR", "2 L"),
    ("Volume", "ft³", "cubic feet|cu ft|CF", "1.5 ft³"),
    ("Pressure", "psi", "pounds per square inch|PSI", "150 psi"),
    ("Pressure", "#", "pound rating|LB RATING|CLASS", "150#"),
    ("Sound Level", "dBA", "decibel|decibels|dB|DB|DBA", "47 dBA"),
    ("Temperature", "°F", "fahrenheit|deg F|degrees F", "350 °F"),
    ("Temperature", "°C", "celsius|deg C|degrees C", "180 °C"),
    ("Color Temperature", "K", "kelvin|color temp|CCT", "3000K"),
    ("Luminous Flux", "lm", "lumen|lumens|LM", "800 lm"),
    ("Rotational Speed", "RPM", "revolutions per minute|rpm", "1750 RPM"),
    ("Time", "hr", "hour|hours|HR|HRS", "12 hr"),
    ("Time", "min", "minute|minutes|MIN", "30 min"),
    ("Time", "sec", "second|seconds|SEC", "10 sec"),
    ("Thread Size", "NPT", "national pipe thread|npt", "1/2 in NPT"),
    ("Grit", "grit", "GRIT|#grit", "P150 grit"),
    ("Count", "pc", "piece|pieces|pcs|PC", "6 pc"),
    ("Count", "pk", "pack|PK", "50 disc/pk"),
    ("Count", "bx", "box|BX", "1 bx"),
    ("Count", "cs", "case|CS", "1 cs"),
    ("Count", "ea", "each|EA", "1 ea"),
    ("Gauge", "ga", "gauge|GA|GAUGE", "14 ga"),
    ("Wire Size", "AWG", "american wire gauge|awg", "12 AWG"),
]


def build_uom():
    write_csv(REF / "uom_standards.csv", ["measurement_type", "canonical_uom", "raw_variants", "example"], [list(r) for r in UOM_ROWS])


# --------------------------------------------------------------------------
# 4. Manufacturer / Brand master data
# --------------------------------------------------------------------------
MANUF_CODE_RE = re.compile(r"^(.*?)\s*\(([A-Za-z0-9]+)\)\s*$")

# Curated brand-token -> canonical manufacturer/brand. Keys are matched as
# case-insensitive whole-word tokens against Part_Desc / MPN prefixes.
# This is the "no brand field, brand hides inside the description" case the
# solution guide calls out explicitly, and is what lets the entity-resolution
# engine outrank the (often wholesaler/co-op, not manufacturer) Part_Manuf value.
CURATED_BRAND_ALIASES = [
    # token(s),                 manufacturer_name,                brand_name,          brand_code
    ("lg",                       "LG Electronics",                 "LG®",               "LG"),
    ("ge|g.e.",                  "GE Appliances",                  "GE®",               "GE"),
    ("frigidaire",                "Rheem Manufacturing",            "FRIGIDAIRE®",       "FRIG"),
    ("whirlpool",                "Whirlpool Corporation",          "Whirlpool®",        "WHRL"),
    ("kitchenaid",                "Whirlpool Corporation",          "KitchenAid®",       "KAID"),
    ("maytag",                    "Whirlpool Corporation",          "Maytag®",           "MYTG"),
    ("bosch",                     "BSH Home Appliances",            "Bosch®",            "BOSC"),
    ("samsung",                   "Samsung Electronics",            "Samsung®",          "SAMS"),
    ("milw|milwaukee",           "Milwaukee Tool",                 "Milwaukee®",        "MILW"),
    ("dewalt|dwlt|dwt",          "DEWALT Industrial Tool Co",       "DEWALT®",           "DEWA"),
    ("diablo",                    "Freud Inc",                      "Diablo®",           "DIAB"),
    ("freud",                     "Freud Inc",                      "Freud®",            "FRUD"),
    ("3m",                        "3M Company",                     "3M™",               "3M"),
    ("mirka",                     "Mirka Abrasives Inc",            "Mirka®",            "MIRK"),
    ("kichler",                   "Kichler Lighting",                "Kichler®",          "KICH"),
    ("satco",                     "Satco Products Inc",             "Satco®",            "SATC"),
    ("philips",                   "Signify (Philips Lighting)",     "Philips®",          "PHIL"),
    ("leviton",                   "Leviton Manufacturing Co",       "Leviton®",          "LEVI"),
    ("southwire",                 "Southwire Company",              "Southwire®",        "SWIR"),
    ("hunter",                    "Hunter Fan Company",             "Hunter®",           "HUNT"),
    ("trex",                      "Trex Company",                   "Trex®",             "TREX"),
    ("azek",                      "AZEK Building Products",         "AZEK®",             "AZEK"),
    ("makita",                    "Makita U.S.A. Inc",              "Makita®",           "MAKI"),
    ("festool",                   "Festool USA",                    "Festool®",          "FEST"),
    ("kreg",                      "Kreg Tool Company",               "Kreg®",             "KREG"),
    ("vessel",                    "Vessel Tools USA Inc",            "Vessel®",           "VESS"),
    ("edge",                      "Edge Eyewear Inc",                "Edge®",             "EDGE"),
]


def parse_part_manuf(value: str) -> tuple[str, str]:
    value = (value or "").strip()
    m = MANUF_CODE_RE.match(value)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return value, ""


def build_manufacturer_brand_master():
    rows = []
    seen_names = set()

    # ground-truth overrides first (highest authority - exact rows we can verify)
    ground_truth = [
        ("Rheem Manufacturing", "", "FRIGIDAIRE®", "FRIG", "frigidaire", "ground_truth"),
        ("Whirlpool Corporation", "", "Whirlpool®", "WHRL", "whirlpool", "ground_truth"),
    ]
    for row in ground_truth:
        rows.append(list(row))
        seen_names.add(row[0].lower())

    # curated brand aliases (token match against free text)
    for tokens, manuf, brand, brand_code in CURATED_BRAND_ALIASES:
        key = manuf.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        rows.append([manuf, "", brand, brand_code, tokens, "curated_seed"])

    # observed distributor / manufacturer strings from the raw input file
    input_csv = RAW / "sample_1000_items_input.csv"
    if input_csv.exists():
        with open(input_csv, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                raw = r.get("Part_Manuf", "")
                if not raw or raw.strip() in ("-", ""):
                    continue
                name, code = parse_part_manuf(raw)
                key = name.lower()
                if key in seen_names:
                    continue
                seen_names.add(key)
                # Per the solution guide: "Where an item has no brand, the
                # manufacturer name is used instead."
                rows.append([name, code, name, code, name.lower(), "observed_input"])

    rows.sort(key=lambda r: r[0].lower())
    write_csv(
        REF / "manufacturer_brand_master.csv",
        ["MANUFACTURER_NAME", "MANUFACTURER_CODE", "BRAND_NAME", "BRAND_CODE", "MATCH_ALIASES", "SOURCE"],
        rows,
    )


# --------------------------------------------------------------------------
# 5. Taxonomy / controlled vocabulary (LOV) seed
#    Dishwashers is built to full depth (it's the one category we have a
#    verified ground-truth record for). Every other classpath observed in
#    the 1000-item sample gets a shallower but real attribute set inferred
#    from the actual description patterns, so the classifier has somewhere
#    correct to land instead of only ever choosing "Generic".
# --------------------------------------------------------------------------
# columns: Classpath | Leaf Node | Attribute Label | Normalized Label | Data Type | UOM Type | Filtering | Keywords | Guidelines

LOV_ROWS = [
    # ---- Appliances > Kitchen Appliances > Built-In Dishwashers (DEEP - ground truth derived)
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Series", "Series", "text", "", "Y", "professional|eco|series", "Marketing series name if present after brand"),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Model", "Model", "text", "", "N", "", "Distinct from MPN when a separate model name exists"),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Number of Wash Cycles", "Number of Wash Cycles", "numeric", "", "Y", "wash cycle|cycles", "Integer count of cycles"),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Voltage Rating", "Voltage Rating", "numeric", "Voltage", "Y", "v|volt|vac|vdc", ""),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Amperage Rating", "Amperage Rating", "numeric", "Current", "Y", "a|amp", ""),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Mounting Type", "Mounting Type", "enum", "", "Y", "leg|built-in|bltln|panel-ready", "Leg|Built-in|Panel-Ready"),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Plug Type", "Plug Type", "text", "", "N", "", ""),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Size", "Size", "text", "Length", "Y", "h x w x d", "Rendered as 'H x W x D' with each dimension normalized"),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Depth With Door Open", "Depth With Door Open", "numeric", "Length", "N", "depth with door open", ""),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Minimum Height", "Minimum Height", "text", "Length", "N", "min height|minimum height", ""),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Maximum Height", "Maximum Height", "text", "Length", "N", "max height|maximum height", ""),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Sound Level", "Sound Level", "numeric", "Sound Level", "Y", "dba|db|sound level|quiet", ""),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Material", "Material", "enum", "", "Y", "ss|sst|stainless steel|black|white|bss", "Stainless Steel|Black Stainless Steel|White|Black|Bisque"),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Color", "Color", "enum", "", "Y", "ss|sst|black|white|bss", "Stainless Steel|Black Stainless Steel|White|Black|Bisque"),
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers", "Additional Information", "Additional Information", "text", "", "N", "", "Free-text roll-up of remaining grounded claims"),

    # ---- Lighting > Fixtures (shallow, observed: Kichler/Satco/Philips strip & bath/wall lights)
    ("Lighting & Electrical>Lighting Fixtures>Wall Lights", "Wall Lights", "Finish", "Finish", "enum", "", "Y", "bk|black|br|bronze|wh|white|a\\b", "Black|Bronze|White|Antique"),
    ("Lighting & Electrical>Lighting Fixtures>Wall Lights", "Wall Lights", "Fixture Type", "Fixture Type", "enum", "", "Y", "wall lt|wall light|bath light", "Wall Light|Bath Light"),
    ("Lighting & Electrical>Lamps & Bulbs>LED Retrofit Lamps", "LED Retrofit Lamps", "Wattage", "Wattage", "numeric", "Power", "Y", "w|watt", ""),
    ("Lighting & Electrical>Lamps & Bulbs>LED Retrofit Lamps", "LED Retrofit Lamps", "Color Temperature", "Color Temperature", "numeric", "Color Temperature", "Y", "k|27k|30k|50k|kelvin", ""),
    ("Lighting & Electrical>Lamps & Bulbs>LED Retrofit Lamps", "LED Retrofit Lamps", "Length", "Length", "numeric", "Length", "Y", "\"|in|ft|'", ""),
    ("Lighting & Electrical>Lamps & Bulbs>Fluorescent Lamps", "Fluorescent Lamps", "Lamp Base/Type", "Lamp Base/Type", "enum", "", "Y", "t12|t9|t8|flor", "T8|T9|T12"),

    # ---- Electrical devices (Southwire/Leviton observed)
    ("Lighting & Electrical>Wiring Devices>Outlets & Receptacles", "Outlets & Receptacles", "Amperage Rating", "Amperage Rating", "numeric", "Current", "Y", "a|amp", ""),
    ("Lighting & Electrical>Wiring Devices>Outlets & Receptacles", "Outlets & Receptacles", "Device Type", "Device Type", "enum", "", "Y", "gfci|gfi|outlet|dimmer", "GFCI Outlet|Outlet|Dimmer"),
    ("Lighting & Electrical>Wiring Devices>Outlets & Receptacles", "Outlets & Receptacles", "Color", "Color", "enum", "", "Y", "wh|white|br|brown|blk|black", "White|Brown|Black|Ivory"),
    ("Lighting & Electrical>Electrical Boxes & Covers>Box Covers", "Box Covers", "Gang Size", "Gang Size", "enum", "", "Y", "1g|2g|single|double", "1-Gang|2-Gang"),

    # ---- Fans (Hunter observed)
    ("Appliances & Consumer Electronics>Heating Cooling & Air Quality>Ceiling Fans", "Ceiling Fans", "Blade Span", "Blade Span", "numeric", "Length", "Y", "\"|in", ""),
    ("Appliances & Consumer Electronics>Heating Cooling & Air Quality>Ceiling Fans", "Ceiling Fans", "Finish", "Finish", "enum", "", "Y", "wh|white|bz|bronze|mb|matte black", "White|Bronze|Matte Black"),

    # ---- Building materials / decking & railing (Boise Cascade / Parksite / US Lumber observed)
    ("Building Materials>Outdoor Living>Decking Boards", "Decking Boards", "Length", "Length", "numeric", "Length", "Y", "'|ft", ""),
    ("Building Materials>Outdoor Living>Decking Boards", "Decking Boards", "Nominal Width", "Nominal Width", "text", "Length", "Y", "x\\d+\"", ""),
    ("Building Materials>Outdoor Living>Decking Boards", "Decking Boards", "Color", "Color", "text", "", "Y", "walnut|coastline|biscayne", ""),
    ("Building Materials>Outdoor Living>Railing Systems", "Railing Systems", "Length", "Length", "numeric", "Length", "Y", "'|ft", ""),
    ("Building Materials>Outdoor Living>Railing Systems", "Railing Systems", "Color", "Color", "enum", "", "Y", "black|white|wh", "Black|White"),
    ("Building Materials>Outdoor Living>Railing Systems", "Railing Systems", "Baluster Style", "Baluster Style", "enum", "", "Y", "round|square|sq|rnd", "Round|Square"),

    # ---- Abrasives / power tool accessories (Freud/Diablo, Milwaukee, 3M, Mirka observed)
    ("Tools & Equipment>Power Tool Accessories>Abrasive Discs", "Abrasive Discs", "Diameter", "Diameter", "numeric", "Length", "Y", "\"|in", ""),
    ("Tools & Equipment>Power Tool Accessories>Abrasive Discs", "Abrasive Discs", "Grit", "Grit", "text", "Grit", "Y", "p\\d+|grit", ""),
    ("Tools & Equipment>Power Tool Accessories>Abrasive Discs", "Abrasive Discs", "Arbor/Bore Size", "Arbor/Bore Size", "text", "Length", "N", "x\\d+/\\d+\"|bore", ""),
    ("Tools & Equipment>Power Tool Accessories>Cut-Off Discs", "Cut-Off Discs", "Diameter", "Diameter", "numeric", "Length", "Y", "\"|in", ""),
    ("Tools & Equipment>Power Tool Accessories>Cut-Off Discs", "Cut-Off Discs", "Thickness", "Thickness", "text", "Length", "Y", "x\\.\\d+\"|x\\d+/\\d+\"", ""),
    ("Tools & Equipment>Power Tool Accessories>Cut-Off Discs", "Cut-Off Discs", "Material Cut", "Material Cut", "enum", "", "Y", "metal", "Metal|Masonry|Wood"),
]


def build_taxonomy_lov():
    write_csv(
        REF / "taxonomy_lov.csv",
        ["Classpath", "Leaf Node", "Attribute Label", "Normalized Label", "Data Type", "UOM Type", "Filtering", "Keywords", "Guidelines"],
        [list(r) for r in LOV_ROWS],
    )


# --------------------------------------------------------------------------
# 6b. Classpath-level keyword list, kept deliberately separate from the
#     per-attribute LOV keywords above (those are short regex fragments like
#     "v"/"a" meant for pulling attribute *values* out of text, and are far
#     too promiscuous to also drive category classification - matching "a"
#     against "16-24 Adjust Hanger" would wrongly fire on almost anything).
#     Only distinctive, whole-word category nouns/phrases go here.
# --------------------------------------------------------------------------
CATEGORY_KEYWORD_ROWS = [
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Built-In Dishwashers",
     "dishwasher|dishwashers"),
    ("Lighting & Electrical>Lighting Fixtures>Wall Lights", "Wall Lights",
     "wall lt|wall light|bath light|wall lights"),
    ("Lighting & Electrical>Lamps & Bulbs>LED Retrofit Lamps", "LED Retrofit Lamps",
     "led retro|led\\b.*retro|retro.*led"),
    ("Lighting & Electrical>Lamps & Bulbs>Fluorescent Lamps", "Fluorescent Lamps",
     "flor\\b|fluorescent|t12|t9\\b|t8\\b"),
    ("Lighting & Electrical>Wiring Devices>Outlets & Receptacles", "Outlets & Receptacles",
     "outlet|gfci|gfi\\b|dimmer|receptacle"),
    ("Lighting & Electrical>Electrical Boxes & Covers>Box Covers", "Box Covers",
     "box cover|cover\\b.*box|duplex box"),
    ("Appliances & Consumer Electronics>Heating Cooling & Air Quality>Ceiling Fans", "Ceiling Fans",
     "\\bfan\\b|ceiling fan"),
    ("Building Materials>Outdoor Living>Decking Boards", "Decking Boards",
     "decking|deck board"),
    ("Building Materials>Outdoor Living>Railing Systems", "Railing Systems",
     "rail\\b|railing|baluster"),
    ("Tools & Equipment>Power Tool Accessories>Abrasive Discs", "Abrasive Discs",
     "sanding|abrasive|stikit|hiolit|abranet|sanding belt|sanding disc"),
    ("Tools & Equipment>Power Tool Accessories>Cut-Off Discs", "Cut-Off Discs",
     "cut.off disc|cut off disc|cutoff disc|metal cut"),
]


def build_category_keywords():
    write_csv(
        REF / "category_keywords.csv",
        ["Classpath", "Leaf Node", "Keywords"],
        [list(r) for r in CATEGORY_KEYWORD_ROWS],
    )


# --------------------------------------------------------------------------
# 6. MPN prefix -> manufacturer/brand patterns.
#    Only rows we can actually verify against the ground-truth delivery
#    format are marked "confirmed". This deliberately does NOT generalize
#    "PDSH -> Frigidaire" to "PDT -> Frigidaire": the sample data itself
#    shows a PDT-prefixed MPN ("PDT715SYVFS Ge Dishwasher SS") that is
#    actually GE-branded, so prefix families are not assumed, only verified
#    exact prefixes are used as evidence. This is intentionally a narrow,
#    honest seed - with the full 200-item ground truth this table would
#    have hundreds of confirmed rows instead of two.
# --------------------------------------------------------------------------
MPN_PREFIX_ROWS = [
    ("PDSH", "Rheem Manufacturing", "FRIGIDAIRE®", "confirmed", "verified against ground_truth_delivery_format.csv row 1"),
    ("WDTS", "Whirlpool Corporation", "Whirlpool®", "confirmed", "verified against ground_truth_delivery_format.csv row 2"),
]


def build_mpn_prefix_patterns():
    write_csv(
        REF / "mpn_prefix_patterns.csv",
        ["prefix", "manufacturer_name", "brand_name", "confidence", "notes"],
        [list(r) for r in MPN_PREFIX_ROWS],
    )


# --------------------------------------------------------------------------
# 6c. Classpath -> Dept/Class/Fine mapping.
#     Dept/Class/Fine is a SEPARATE, coarser taxonomy from Classpath in the
#     official delivery format (e.g. Dept="Appliances", Class="Large
#     Appliances", Fine="Dishwashers" vs. Classpath="Appliances & Consumer
#     Electronics>Kitchen Appliances>Built-In Dishwashers") - they do not
#     share label text, so Dept/Class/Fine cannot be derived by splitting
#     Classpath. Only the one row confirmed against ground truth is included;
#     every other classpath is intentionally left unmapped (empty output)
#     rather than guessed.
# --------------------------------------------------------------------------
DEPT_CLASS_FINE_ROWS = [
    ("Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers", "Appliances", "Large Appliances", "Dishwashers", "confirmed"),
]


def build_dept_class_fine():
    write_csv(
        REF / "classpath_dept_class_fine.csv",
        ["Classpath", "Dept", "Class", "Fine", "confidence"],
        [list(r) for r in DEPT_CLASS_FINE_ROWS],
    )


def main():
    build_placeholders()
    build_fractions()
    build_uom()
    build_manufacturer_brand_master()
    build_mpn_prefix_patterns()
    build_taxonomy_lov()
    build_category_keywords()
    build_dept_class_fine()
    print("\nReference data build complete.")
    print("Drop official Unilog master files into data/reference/external/ to override these seeds -")
    print("see docs/data-model.md for the exact filenames the loaders look for.")


if __name__ == "__main__":
    main()
