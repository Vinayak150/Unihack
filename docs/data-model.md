# Data model

## Reference / master data (`data/reference/`, built by `scripts/build_reference_data.py`)

| File | Columns | Role |
|---|---|---|
| `placeholders.csv` | `placeholder_value` | strings treated as "no data" |
| `fractions.csv` | `fraction, decimal, sixty_fourths` | exact 1/64..63/64 lookup |
| `uom_standards.csv` | `measurement_type, canonical_uom, raw_variants, example` | approved UOM abbreviations |
| `manufacturer_brand_master.csv` | `MANUFACTURER_NAME, MANUFACTURER_CODE, BRAND_NAME, BRAND_CODE, MATCH_ALIASES, SOURCE` | canonical manufacturer/brand entities |
| `mpn_prefix_patterns.csv` | `prefix, manufacturer_name, brand_name, confidence, notes` | narrow, ground-truth-verified MPN→OEM patterns |
| `taxonomy_lov.csv` | `Classpath, Leaf Node, Attribute Label, Normalized Label, Data Type, UOM Type, Filtering, Keywords, Guidelines` | controlled vocabulary per classpath |
| `category_keywords.csv` | `Classpath, Leaf Node, Keywords` | classifier keyword rules (kept separate from attribute-value regex) |
| `classpath_dept_class_fine.csv` | `Classpath, Dept, Class, Fine, confidence` | the separate coarse taxonomy the output format also expects |

**Overriding with official files**: every loader checks
`data/reference/external/<same filename>` first. Drop the real
`UniCat_Manufacturer_and_Brand_List.xlsx` (converted to the same column
shape), `Unicat_Lov_v1_0.xlsx`, `Unilog_Master_UOM_Standards.xlsx`,
`Decimal_Fraction.xlsx`, `FAUCETS_LOV.xlsx`, `Fittings_LOV.xlsx` in there
and every engine picks them up automatically.

## Runtime data model (`app/`)

- **`Claim`** (`app/provenance/claims.py`) — the atomic fact:
  `attribute, value, uom, provenance_type ∈ {DIRECT, NORMALIZED, DERIVED,
  INFERRED, UNKNOWN, CONFLICT}, source_ids, confidence`. A `ClaimRegistry`
  holds every claim for one product.
- **`ResolutionResult`** (`app/manufacturer/resolver.py`) — explainable
  entity-resolution outcome: `input, canonical_value, entity_code,
  brand_name, brand_code, score, method, status, evidence[]`.
- **`ClassificationResult`** (`app/taxonomy/classifier.py`) — `classpath,
  leaf_node, method, score, status, evidence[]`.
- **`ValidationReport`** (`app/validation/engine.py`) — list of
  `ValidationIssue{check, field, severity, message}`.
- **`ConfidenceBreakdown`** (`app/confidence/engine.py`) — per-signal +
  overall confidence.
- **`ReviewEntry`** (`app/review/queue.py`) — `requires_review,
  reasons[{code, message, field}]`.
- **`ProcessingResult`** (`app/orchestration/pipeline.py`) — bundles all of
  the above for one row plus `status ∈ {SUCCESS, PARTIAL, REVIEW_REQUIRED,
  UNRESOLVED, VALIDATION_FAILED, PROCESSING_FAILED}`.

## Output schema

`app/core/output_schema.py::OutputSchema` loads the exact 252-column header
row from `data/raw/ground_truth_delivery_format.csv` (or any CSV whose
first row is the desired header, via `--schema` on the CLI) and is the only
place downstream code is allowed to know column names. `to_row()` /
`export_csv()` / `export_xlsx()` guarantee every header is present, in
order, with unpopulated fields as `""` — never dropped, renamed, or
fabricated.
