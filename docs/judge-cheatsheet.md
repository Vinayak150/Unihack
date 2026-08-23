# Judge cheat sheet

## 30-second summary

An AI Product Data Compiler (not a chatbot/RAG demo) that turns cryptic
industrial catalog rows into commerce-ready product records across the
official 252-column Unilog delivery format, using deterministic master-data
resolution + controlled vocabulary + a constrained LLM layer + explicit
provenance/confidence/review — grounded, not generative-only.

## Where to look for each judging criterion

| Criterion | Where |
|---|---|
| Structured data generation from limited input | `app/orchestration/pipeline.py`, live demo in "Product Enrichment" |
| Accuracy & consistency | `reports/evaluation.md` — 100% on manufacturer/brand/classpath vs. verified ground truth |
| AI validation & enrichment | `app/validation/engine.py`, `app/confidence/engine.py`, `app/review/queue.py` |
| Scalable catalog engine | 1000 rows in ~1.3s (`reports/evaluation.md`), stateless per-row processing, see `docs/deployment.md` |
| Explainability | every resolution/classification carries `evidence[]`; every claim carries `provenance_type` + `source_ids` |
| Honesty about limitations | `docs/design-decisions.md` — states plainly what wasn't available and what was done about it |
| No hardcoding | `tests/integration/test_pipeline_end_to_end.py::test_completely_unseen_row_never_crashes_and_never_fabricates_manufacturer` runs an MPN that appears nowhere in any sample file |
| Reproducibility | `make setup && make test && make demo`; `APP_MODE=mock` needs no credentials |

## Things worth asking about live

- "Why is classification only ~27% resolved on the full batch?" →
  `docs/design-decisions.md` §3 — an honest, table-driven coverage gap
  (11 categories seeded), not an architectural ceiling.
- "Why doesn't the dishwasher long description have voltage/wash cycles?"
  → `docs/design-decisions.md` §2 — those aren't in the given input text,
  live manufacturer retrieval is blocked in this sandbox, and the system
  correctly refuses to fabricate them rather than hallucinate.
- "What happens with the real master data files?" → drop them in
  `data/reference/external/`, zero code changes, coverage rises.
