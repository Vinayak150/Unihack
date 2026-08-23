# Contributing

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
make setup      # installs deps, builds reference/master-data tables
make test       # 43 unit/integration/regression/evaluation tests, offline (APP_MODE=mock)
make demo       # http://localhost:8000
```

## Project layout

See `docs/architecture.md`. In short: `app/` is organized by pipeline stage
(ingestion → preprocessing → manufacturer/taxonomy/lov → extraction →
normalization → enrichment (category processors) → generation → validation
→ confidence → review → orchestration), `data/reference/` is master data,
`prompts/` is the versioned LLM prompt library, `frontend/` is a no-build
vanilla JS SPA served by the FastAPI app.

## Adding a category processor

1. Add classpath + attributes to `scripts/build_reference_data.py`
   (`LOV_ROWS`) and category keywords (`CATEGORY_KEYWORD_ROWS`), then
   `make build-index`.
2. Subclass `CategoryProcessor` in `app/enrichment/category_processor.py`
   only if the category needs extraction logic beyond the generic
   deterministic + LOV-constrained pass every classpath already gets.
3. Add a regression test once you have at least one row you can verify by
   hand.

## Rules this codebase holds itself to

- No LLM calls for deterministic string/unit/fraction work (see
  `app/uom`, `app/normalization`).
- Every fact in a generated description must trace to a `Claim` with
  `provenance_type != UNKNOWN` (see `app/provenance/claims.py`,
  `app/generation/renderers.py`).
- The official 252-column header list is never renamed, reordered, or
  dropped (see `app/core/output_schema.py` and its tests).
- No sample-specific branching (`if mpn == "..."`) anywhere in `app/`.

## Tests

```bash
python -m pytest tests/unit          # engine-level, no I/O beyond reference CSVs
python -m pytest tests/integration   # full pipeline + FastAPI, still offline
python -m pytest tests/regression    # pinned to the 2 verified ground-truth rows
python -m pytest tests/evaluation    # evaluator correctness
```

All tests run with `APP_MODE=mock` (the default) — no API key required.
