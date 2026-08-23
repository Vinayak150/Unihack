"""FastAPI backend for the Unilog Product Intelligence prototype.

Endpoints wrap the same orchestration pipeline the CLI uses — there is no
separate "demo" code path. Uploads are processed synchronously in-memory
(fine at the 1000-row scale this prototype targets; app/orchestration is
already the seam where a Celery/RQ worker would plug in for larger batches -
see docs/deployment.md).
"""
from __future__ import annotations

import io
import time
import uuid
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config.settings import settings
from app.core.output_schema import OutputSchema
from app.deduplication.engine import find_duplicates
from app.evaluation.evaluator import evaluate, write_reports
from app.ingestion.loader import load_tabular, profile_dataframe
from app.orchestration.output_mapper import to_output_record
from app.orchestration.pipeline import ProcessingResult, process_batch

app = FastAPI(title="Unilog Product Intelligence API", version=settings.PIPELINE_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# in-memory run store — fine for a hackathon prototype; documented as the
# spot to swap in Redis/Postgres for a persistent multi-worker deployment.
_RUNS: dict[str, dict] = {}
_UPLOAD_DIR = settings.CACHE_DIR / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _serialize_result(r: ProcessingResult) -> dict:
    return {
        "row_index": r.row_index,
        "status": r.status,
        "mpn": r.input_row.get("Mfg_Part_Num", ""),
        "part_desc": r.input_row.get("Part_Desc", ""),
        "manufacturer": r.manufacturer_resolution.to_dict() if r.manufacturer_resolution else None,
        "classification": r.classification.to_dict() if r.classification else None,
        "claims": r.claim_registry.to_list() if r.claim_registry else [],
        "descriptions": {
            "invoice_desc": r.descriptions.invoice_desc,
            "mobile_desc": r.descriptions.mobile_desc,
            "product_title": r.descriptions.product_title,
            "short_desc": r.descriptions.short_desc,
            "long_desc": r.descriptions.long_desc,
            "claims_used": r.descriptions.claims_used,
        } if r.descriptions else None,
        "validation": r.validation.to_dict() if r.validation else None,
        "confidence": r.confidence.to_dict() if r.confidence else None,
        "review": r.review.to_dict() if r.review else None,
        "flags": r.flags,
        "error": r.error,
        "duration_ms": round(r.duration_ms, 2),
    }


class SingleEnrichRequest(BaseModel):
    part_desc: str
    mfg_part_num: str = ""
    part_manuf: str = ""
    e1_brand: str = "-- Unbranded --"
    unilog_brand: str = "-- No Unilog Brand --"
    dib_brand: str = "-- No DIB Brand --"


@app.post("/api/enrich-single")
def enrich_single(req: SingleEnrichRequest):
    """Ad-hoc single-record enrichment for the live demo view — exercises the
    exact same orchestration pipeline as batch processing, just for one row
    that was never part of any sample file."""
    row = {
        "Mfg_Part_Num": req.mfg_part_num, "Part_Desc": req.part_desc,
        "E1_Brand": req.e1_brand, "Unilog_Brand": req.unilog_brand,
        "DIB_Brand": req.dib_brand, "Part_Manuf": req.part_manuf,
    }
    from app.orchestration.pipeline import process_row

    result = process_row(row, run_id="single")
    schema = OutputSchema.load()
    output_record = to_output_record(schema, result)
    payload = _serialize_result(result)
    payload["output_record"] = output_record
    return payload


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app_mode": settings.APP_MODE,
        "pipeline_version": settings.PIPELINE_VERSION,
        "schema_version": settings.SCHEMA_VERSION,
        "taxonomy_version": settings.TAXONOMY_VERSION,
    }


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    upload_id = uuid.uuid4().hex[:12]
    dest = _UPLOAD_DIR / f"{upload_id}_{file.filename}"
    dest.write_bytes(content)

    try:
        df = load_tabular(dest)
    except Exception as exc:
        raise HTTPException(400, f"could not parse uploaded file: {exc}")

    profile = profile_dataframe(df)
    _RUNS[upload_id] = {"path": str(dest), "filename": file.filename, "rows": len(df), "profile": profile, "status": "uploaded"}
    return {"upload_id": upload_id, "filename": file.filename, "rows": len(df), "profile": profile}


class ProcessRequest(BaseModel):
    upload_id: str


@app.post("/api/process/{upload_id}")
def process(upload_id: str):
    run = _RUNS.get(upload_id)
    if not run:
        raise HTTPException(404, "unknown upload_id")

    t0 = time.perf_counter()
    df = load_tabular(run["path"])
    rows = df.to_dict(orient="records")
    results = process_batch(rows, run_id=upload_id)
    schema = OutputSchema.load()
    output_records = [to_output_record(schema, r) for r in results]
    dedup_groups = find_duplicates(rows)

    status_counts: dict[str, int] = {}
    confidences = []
    for r in results:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1
        if r.confidence:
            confidences.append(r.confidence.overall)

    review_count = sum(1 for r in results if r.review and r.review.requires_review)
    lov_compliant = sum(
        1 for r in results if r.validation and not any(i.check == "vocabulary.attribute_value" for i in r.validation.issues)
    )
    grounded_total = sum(len(r.claim_registry.grounded_attributes()) for r in results if r.claim_registry)
    all_claims_total = sum(len(r.claim_registry.claims) for r in results if r.claim_registry)

    run.update({
        "status": "processed",
        "results": results,
        "output_records": output_records,
        "dedup_groups": [{"key": g.key, "kind": g.kind, "row_indices": g.row_indices, "similarity": g.similarity} for g in dedup_groups],
        "summary": {
            "total": len(results),
            "status_counts": status_counts,
            "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0,
            "review_required": review_count,
            "lov_compliance_rate": round(lov_compliant / len(results), 4) if results else 0,
            "groundedness_rate": round(grounded_total / all_claims_total, 4) if all_claims_total else 0,
            "duplicate_groups": len(dedup_groups),
            "processing_time_s": round(time.perf_counter() - t0, 2),
        },
    })
    return {"upload_id": upload_id, "summary": run["summary"]}


@app.get("/api/results/{upload_id}")
def results(upload_id: str, offset: int = 0, limit: int = 50, status: str | None = None):
    run = _RUNS.get(upload_id)
    if not run or "results" not in run:
        raise HTTPException(404, "run not processed yet")
    rs = run["results"]
    if status:
        rs = [r for r in rs if r.status == status]
    page = rs[offset: offset + limit]
    return {"total": len(rs), "offset": offset, "limit": limit, "items": [_serialize_result(r) for r in page]}


@app.get("/api/record/{upload_id}/{row_index}")
def record_detail(upload_id: str, row_index: int):
    run = _RUNS.get(upload_id)
    if not run or "results" not in run:
        raise HTTPException(404, "run not processed yet")
    for r in run["results"]:
        if r.row_index == row_index:
            return _serialize_result(r)
    raise HTTPException(404, "row not found")


@app.get("/api/review-queue/{upload_id}")
def review_queue(upload_id: str, offset: int = 0, limit: int = 50):
    run = _RUNS.get(upload_id)
    if not run or "results" not in run:
        raise HTTPException(404, "run not processed yet")
    flagged = [r for r in run["results"] if r.review and r.review.requires_review]
    page = flagged[offset: offset + limit]
    return {"total": len(flagged), "offset": offset, "limit": limit, "items": [_serialize_result(r) for r in page]}


@app.get("/api/download/{upload_id}")
def download(upload_id: str, fmt: str = "xlsx"):
    run = _RUNS.get(upload_id)
    if not run or "output_records" not in run:
        raise HTTPException(404, "run not processed yet")
    schema = OutputSchema.load()
    out_path = settings.CACHE_DIR / f"{upload_id}_output.{fmt}"
    if fmt == "xlsx":
        schema.export_xlsx(run["output_records"], out_path)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        schema.export_csv(run["output_records"], out_path)
        media = "text/csv"
    return FileResponse(out_path, media_type=media, filename=f"unilog_enriched_{upload_id}.{fmt}")


@app.post("/api/evaluate")
def run_evaluation():
    report, _, _ = evaluate(run_id=f"api-eval-{uuid.uuid4().hex[:6]}")
    write_reports(report)
    from dataclasses import asdict
    return asdict(report)


@app.get("/api/system-health")
def system_health():
    from app.core.llm import get_provider
    from app.lov.vocabulary import get_vocabulary
    from app.manufacturer.resolver import get_resolver
    from app.taxonomy.classifier import get_classifier

    return {
        "app_mode": settings.APP_MODE,
        "llm_provider": get_provider().name,
        "manufacturer_master_rows": len(get_resolver().records),
        "classpaths_supported": len(get_classifier().classpaths()),
        "lov_attribute_rows": sum(len(v) for v in get_vocabulary().by_classpath.values()),
        "pipeline_version": settings.PIPELINE_VERSION,
        "schema_version": settings.SCHEMA_VERSION,
        "active_runs": len(_RUNS),
    }


_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
