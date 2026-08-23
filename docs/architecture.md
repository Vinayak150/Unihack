# Architecture

## Pipeline

```
RAW PRODUCT (Mfg_Part_Num, Part_Desc, E1_Brand, Unilog_Brand, DIB_Brand, Part_Manuf)
    │
    ▼
PROFILE / CLEAN         app/ingestion, app/preprocessing
    - robust header detection (doesn't assume row 1 is clean)
    - placeholder scrub ("-- Unbranded --" etc → None, never a fact)
    - MPN-prefix stripping, trailing-note splitting ("- Display Only")
    │
    ▼
ENTITY RESOLUTION       app/manufacturer/resolver.py
    exact match → normalized match → brand-alias token match (catches the
    "Part_Manuf is a distributor, not the OEM" case) → confirmed MPN-prefix
    pattern → fuzzy match (rapidfuzz) → UNRESOLVED/review
    │
    ▼
CLASSIFY                app/taxonomy/classifier.py
    keyword/rule match against category_keywords.csv → RESOLVED/UNRESOLVED
    (LLM adjudication hook exists — app/core/llm.py — for ambiguous cases;
    not needed to hit 100% on the verified rows, see docs/evaluation.md)
    │
    ▼
EXTRACT                 app/enrichment/category_processor.py
                         app/extraction/deterministic.py
    Stage 1: deterministic regex extraction of values ACTUALLY PRESENT in
    Part_Desc (dimensions, grit, diameter, voltage/amperage, material code)
    → DIRECT claims. A category processor (deep for Dishwashers, generic
    elsewhere) walks the classpath's applicable LOV attributes and emits
    UNKNOWN claims for anything not evidenced — never a guess.
    │
    ▼
NORMALIZE                app/normalization/normalize.py, app/uom, 
    Table-driven UOM canonicalization + trade-fraction rendering.
    DIRECT → NORMALIZED. No LLM calls for this — it's a lookup.
    │
    ▼
GENERATE                 app/generation/renderers.py
    Invoice/Mobile/Title/Short/Long descriptions built ONLY from the claim
    registry (never raw text directly) — the no-hallucination guarantee.
    │
    ▼
VALIDATE                 app/validation/engine.py
    schema / formatting / vocabulary(LOV) / semantic / cross-field / source
    │
    ▼
SCORE                    app/confidence/engine.py
    field + record confidence from actual signals (match method, source
    authority, LOV membership, validation errors) — not the LLM's opinion
    │
    ▼
REVIEW ROUTING            app/review/queue.py
    structured reasons: unresolved_manufacturer, uncertain_classification,
    lov_mismatch, low_confidence, validation_failed
    │
    ▼
OUTPUT MAPPING             app/orchestration/output_mapper.py
    maps everything onto the exact 252-column official schema
    (app/core/output_schema.py) — headers never renamed/dropped/reordered
```

Orchestrated per-record by `app/orchestration/pipeline.py::process_row`,
batched by `process_batch` with per-record isolation (one bad row never
kills the batch — see `STATUS_PROCESSING_FAILED`).

## Category processors

```
CategoryProcessor (generic: deterministic extraction + LOV-constrained
                    validation against whatever attributes the classpath
                    defines — every classpath gets this, not just the
                    "deep" ones)
├── DishwasherProcessor   — deep: the one category with verified ground truth
├── AbrasiveDiscProcessor
└── CutOffDiscProcessor
```

New categories are added by extending the reference tables
(`scripts/build_reference_data.py`), not by writing bespoke per-category
pipelines from scratch — the generic processor already does real work for
any classpath the taxonomy knows about.

## Where the LLM fits (and where it deliberately doesn't)

`app/core/llm.py` defines `LLMProvider` (`MockProvider` / `ClaudeProvider`),
selected by `APP_MODE`. The prompt library in `prompts/` is written for the
model-routing philosophy the challenge specifies:

- **Never LLM**: casing, UOM conversion, fraction lookup, exact validation —
  all table-driven (`app/uom`, `app/normalization`).
- **LLM as adjudicator, not author**: classification/entity-resolution
  prompts constrain the model to choose from a candidate shortlist pulled
  from master data — it can never introduce a new manufacturer/brand/
  classpath. Extraction prompts require the model to omit an attribute
  entirely rather than guess. Generation prompts require every claim used
  to trace back to the grounded registry.

This build ships with `APP_MODE=mock` by default so the whole pipeline,
API, and 43-test suite run with zero external calls or credentials. Set
`APP_MODE=claude` + `ANTHROPIC_API_KEY` to route the same call sites through
Claude — no code changes required, since MockProvider and ClaudeProvider
share one interface.

## Why coverage isn't 100% across all 1000 rows, on purpose

See `docs/design-decisions.md` for the full explanation: this build's
master data (manufacturer/brand aliases, LOV/taxonomy, MPN-prefix patterns)
is seeded from the 1000-item sample plus curated public knowledge, because
the official 27k-row manufacturer list and 161k-row LOV file were not part
of this challenge's provided resources. Every loader in this codebase
checks `data/reference/external/` first and prefers those files
automatically — dropping in the real master data raises coverage with zero
code changes, which is the point of building it this way.
