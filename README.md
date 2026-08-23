# Unilog Product Intelligence — AI Product Data Compiler

Turns messy industrial catalog rows (`3/8 CPLG BRS 150#`,
`PDSH4816AF Dishwasher SS - Display Only`) into commerce-ready product
records across the official 252-column Unilog delivery format — using
deterministic master-data resolution, controlled vocabulary, a
model-routed extraction/generation layer, and explicit provenance,
confidence, and human-review routing. Built for the Unilog AI-Powered
Product Intelligence for Industrial Commerce challenge.

**This is a product data compiler, not a chatbot.** It never asks an LLM to
freely generate 252 columns; it builds grounded canonical facts first,
then renders descriptions from those facts, then validates and scores the
result. See `docs/architecture.md` for the full pipeline and
`docs/design-decisions.md` for an honest account of what data this build
did and didn't have access to.

## Get a live public URL

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Vinayak150/Unihack)

One click, free tier, no config beyond connecting your GitHub — Render
builds `Dockerfile` and reads `render.yaml`. `APP_MODE=mock` ships as the
default env var so the deployed instance works immediately with zero
secrets; add `ANTHROPIC_API_KEY` in the Render dashboard afterward to
switch it to `APP_MODE=claude`. Any other Docker-friendly host (Railway,
Fly.io, a VPS) works the same way — `docker build -t unilog . && docker run
-p 8000:8000 unilog`.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
make setup          # installs deps + builds reference/master-data tables
make test           # 43 tests, offline, ~2s
make demo           # http://localhost:8000 — full UI + API
```

Or from the command line, no server needed:

```bash
python -m app.cli enrich --input data/raw/sample_1000_items_input.csv --output reports/enriched.xlsx
python -m app.cli evaluate --input data/raw/sample_1000_items_input.csv
```

Everything above runs with `APP_MODE=mock` (the default) — **no API key
required**. Set `APP_MODE=claude` + `ANTHROPIC_API_KEY` in `.env` (copy from
`.env.example`) to route the LLM-assisted steps through Claude instead;
every deterministic engine (UOM, fractions, entity resolution, LOV
validation) behaves identically either way.

## What's actually in this repo

| Area | Where | Status |
|---|---|---|
| Manufacturer/brand entity resolution | `app/manufacturer/resolver.py` | exact → normalized → brand-in-text → confirmed MPN-prefix → fuzzy → review, fully explainable |
| Taxonomy classification | `app/taxonomy/classifier.py` | keyword/rule engine, 11 categories seeded from the sample data |
| Controlled vocabulary (LOV) | `app/lov/vocabulary.py` | attribute values constrained to approved lists, fuzzy-matched, never invented |
| UOM & fraction normalization | `app/uom/` | deterministic, table-driven, no LLM |
| Claim/provenance model | `app/provenance/claims.py` | DIRECT/NORMALIZED/DERIVED/INFERRED/UNKNOWN/CONFLICT |
| Grounded description generation | `app/generation/renderers.py` | Invoice/Mobile/Title/Short/Long, built only from claims |
| Validation / confidence / review | `app/validation`, `app/confidence`, `app/review` | schema/vocab/format/semantic/cross-field checks, signal-based confidence, structured review queue |
| Deduplication | `app/deduplication/engine.py` | exact (manufacturer+MPN) + near-duplicate (description similarity) |
| Official 252-column output contract | `app/core/output_schema.py` | headers loaded from the ground-truth file, never renamed/dropped |
| LLM provider abstraction | `app/core/llm.py` | Mock / Claude, shared interface, `APP_MODE` switch |
| Prompt library | `prompts/*.md` | versioned, each with role/task/evidence/prohibited-behavior/output-schema |
| CLI | `app/cli.py` | `enrich`, `evaluate`, `profile`, `build-index` |
| API | `app/api/main.py` | upload/process/results/review-queue/evidence/evaluate/download |
| Frontend | `frontend/` | no-build vanilla JS SPA: Dashboard, Product Enrichment, Batch Upload, Review Queue, Evidence Explorer, Evaluation, System Health |
| Tests | `tests/{unit,integration,regression,evaluation}` | 43 tests, all offline |
| Evaluation | `app/evaluation/evaluator.py` | ground-truth field accuracy + full-batch coverage/quality, writes `reports/` |

## Data this build actually received

Only two files were provided: the 1000-row `sample_1000_items_input.csv`
and a CSV with the header row plus 2 verified example records of the
delivery format (`ground_truth_delivery_format.csv`, both dishwashers).
The official master-data spreadsheets (manufacturer/brand list, cross-
category LOV, UOM standards, decimal-fraction table, FAUCETS_LOV,
Fittings_LOV, content guidelines) referenced in the challenge brief were
**not** part of this build's inputs. `scripts/build_reference_data.py`
builds honestly-labeled seed tables instead of fabricating them — see
`docs/design-decisions.md` for exactly what was done and why, and how to
drop the real files in (`data/reference/external/`) with zero code changes.

## Measured results (not claimed)

On the two ground-truth rows this build could actually verify:
**Manufacturer, Brand, and Classpath: 100% accurate.** Full honest coverage
numbers over the entire 1000-row batch (resolution rates, validation pass
rate, review rate, groundedness) are in `reports/evaluation.md` — regenerate
with `make evaluate`. See `docs/evaluation.md` for what each number means
and why the ground-truth sample is currently small.

## Docs

- `docs/architecture.md` — full pipeline + category-processor design
- `docs/data-model.md` — reference tables + runtime data model
- `docs/api.md` — endpoint reference
- `docs/evaluation.md` — metrics methodology
- `docs/deployment.md` — Docker, scaling notes, env vars
- `docs/demo-script.md` — the live demo walkthrough
- `docs/judge-cheatsheet.md` — criterion → code/evidence map
- `docs/design-decisions.md` — **read this one** — honest limitations and why

## License

MIT — see `LICENSE`.
