# Deployment

## Local

```bash
make setup
make demo   # uvicorn app.api.main:app --reload — http://localhost:8000
```

## Docker

```bash
docker build -t unilog-product-intelligence .
docker run -p 8000:8000 -e APP_MODE=mock unilog-product-intelligence
# or
docker compose up --build
```

The image runs `scripts/build_reference_data.py` at build time so the
container is self-contained — no separate index-build step needed at
runtime.

## Switching from mock to Claude

```bash
export APP_MODE=claude
export ANTHROPIC_API_KEY=sk-ant-...
```

No code changes: `app/core/llm.py::get_provider()` picks `ClaudeProvider`
automatically. Every call site already degrades to a conservative,
non-fabricating response shape if the provider errors.

## Scaling beyond the 1000-row prototype target

The codebase is already structured for this without a rewrite:

- `app/orchestration/pipeline.py::process_batch` is a pure function over a
  list of rows — swap the caller for a task queue (Celery/RQ) processing
  chunks in parallel; per-record isolation (`STATUS_PROCESSING_FAILED`) is
  already in place so a worker crash on one row doesn't lose the batch.
- `app/api/main.py`'s in-memory `_RUNS` dict is the one spot that assumes a
  single process — move it to Redis/Postgres for multi-worker deployments.
- Entity resolution, classification, and LOV validation are all
  dictionary/table lookups (O(1) or O(candidates)) — the one O(n) fuzzy-match
  fallback in `app/manufacturer/resolver.py` is the spot to add an index
  (e.g. a blocking key on first 3 characters) if manufacturer master data
  grows past a few thousand rows.
- Caching seams exist at every external-call boundary
  (`app/core/llm.py`, the retrieval-adapter interface in
  `app/provenance/sources.py`) — wire in `data/cache/` (already
  gitignored, already created) keyed by `(mpn, manufacturer, task)` for
  reruns/incremental enrichment.

## Environment variables

See `.env.example` for the full list (`APP_MODE`, `ANTHROPIC_API_KEY`,
`CLAUDE_MODEL`, `REVIEW_CONFIDENCE_THRESHOLD`, etc).
