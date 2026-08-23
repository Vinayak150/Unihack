# API reference

Base URL: `http://localhost:8000`. All endpoints are implemented in
`app/api/main.py` and share the exact orchestration pipeline the CLI uses.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | app mode, pipeline/schema/taxonomy versions |
| POST | `/api/upload` | multipart file upload (CSV/XLSX) → `{upload_id, rows, profile}` |
| POST | `/api/process/{upload_id}` | runs the full batch pipeline → summary stats |
| GET | `/api/results/{upload_id}?offset&limit&status` | paginated per-record results |
| GET | `/api/record/{upload_id}/{row_index}` | one record's full detail |
| GET | `/api/review-queue/{upload_id}?offset&limit` | records with `requires_review=true` |
| GET | `/api/download/{upload_id}?fmt=xlsx|csv` | exported file, all 252 official headers |
| POST | `/api/enrich-single` | ad-hoc single-record enrichment (no upload needed) — body: `{part_desc, mfg_part_num?, part_manuf?, e1_brand?, unilog_brand?, dib_brand?}` |
| POST | `/api/evaluate` | runs `app/evaluation/evaluator.py` and returns the report |
| GET | `/api/system-health` | master-data row counts, LLM provider, versions |

## Example

```bash
curl -X POST http://localhost:8000/api/enrich-single \
  -H "Content-Type: application/json" \
  -d '{"part_desc": "PDSH4816AF Dishwasher SS - Display Only", "mfg_part_num": "PDSH4816AF", "part_manuf": "Appliance Dealers Cooperative (APPDE)"}'
```

Returns manufacturer resolution, classification, claims (with provenance),
generated descriptions, validation, confidence, and review status for that
one record — plus `output_record`, the exact 252-column mapping.

## Notes

- Runs are held in-memory (`_RUNS` dict in `app/api/main.py`) — fine for a
  single-process prototype at the 1000-row scale this targets. For a
  persistent multi-worker deployment, swap in Redis/Postgres at that same
  seam; nothing else changes (see `docs/deployment.md`).
- CORS is open (`allow_origins=["*"]`) for local/demo convenience — restrict
  this before any real deployment.
