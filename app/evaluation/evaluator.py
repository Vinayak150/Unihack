"""Evaluation harness.

Two honest evaluation surfaces:

1. Ground-truth field accuracy — computed ONLY against the rows we can
   actually verify (the ones present in data/raw/ground_truth_delivery_format.csv,
   matched by Mfg_Part_Num against the 1000-item input). This build ships
   with exactly 2 verified rows; the harness is written to transparently
   scale to however many the official 200-item Input-vs-Delivery-Format file
   provides once available — see docs/evaluation.md.

2. Batch coverage/validation statistics — computed over the FULL 1000-row
   input, with no ground truth needed: resolution rates, validation pass
   rate, review rate, LOV compliance, groundedness. This is what tells you
   the pipeline generalizes, not just that it memorized two rows.
"""
from __future__ import annotations

import csv
import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config.settings import settings
from app.core.output_schema import OutputSchema
from app.orchestration.output_mapper import to_output_record
from app.orchestration.pipeline import ProcessingResult, process_batch


@dataclass
class FieldAccuracy:
    field: str
    total: int = 0
    correct: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


GROUND_TRUTH_FIELDS = [
    "MANUFACTURER_NAME", "BRAND_NAME", "Classpath", "Dept", "Class", "Fine",
    "Product Name",
]


@dataclass
class EvaluationReport:
    run_id: str
    total_rows: int
    ground_truth_rows_matched: int
    field_accuracy: dict = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)
    status_counts: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


def _load_ground_truth() -> dict[str, dict]:
    with open(settings.GROUND_TRUTH_CSV, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return {r["Mfg_Part_Num"]: r for r in rows if r.get("Mfg_Part_Num")}


def evaluate(input_csv: Path | str | None = None, run_id: str = "eval") -> tuple[EvaluationReport, list[ProcessingResult], list[dict]]:
    input_csv = Path(input_csv or settings.SAMPLE_INPUT_CSV)
    with open(input_csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    schema = OutputSchema.load()
    results = process_batch(rows, run_id=run_id)
    output_records = [to_output_record(schema, r) for r in results]

    ground_truth = _load_ground_truth()
    matched = 0
    field_accuracy = {f: FieldAccuracy(f) for f in GROUND_TRUTH_FIELDS}
    error_rows = []

    for row, out_rec in zip(rows, output_records):
        gt = ground_truth.get(row.get("Mfg_Part_Num", ""))
        if not gt:
            continue
        matched += 1
        for fname in GROUND_TRUTH_FIELDS:
            expected = (gt.get(fname) or "").strip()
            actual = (out_rec.get(fname) or "").strip()
            if not expected:
                continue
            field_accuracy[fname].total += 1
            if expected == actual:
                field_accuracy[fname].correct += 1
            else:
                error_rows.append({
                    "Mfg_Part_Num": row.get("Mfg_Part_Num"), "field": fname,
                    "expected": expected, "actual": actual,
                })

    resolved_manuf = sum(1 for r in results if r.manufacturer_resolution and r.manufacturer_resolution.status == "RESOLVED")
    resolved_class = sum(1 for r in results if r.classification and r.classification.status == "RESOLVED")
    validation_pass = sum(1 for r in results if r.validation and r.validation.passed)
    review_required = sum(1 for r in results if r.review and r.review.requires_review)
    confidences = [r.confidence.overall for r in results if r.confidence]
    lov_issue_total = sum(sum(1 for i in r.validation.issues if i.check == "vocabulary.attribute_value") for r in results if r.validation)
    grounded_claim_total = sum(len(r.claim_registry.grounded_attributes()) for r in results if r.claim_registry)
    all_claim_total = sum(len(r.claim_registry.claims) for r in results if r.claim_registry)

    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    coverage = {
        "manufacturer_resolution_rate": round(resolved_manuf / len(results), 4) if results else 0,
        "classification_resolution_rate": round(resolved_class / len(results), 4) if results else 0,
        "validation_pass_rate": round(validation_pass / len(results), 4) if results else 0,
        "review_rate": round(review_required / len(results), 4) if results else 0,
        "avg_confidence": round(statistics.mean(confidences), 4) if confidences else 0,
        "groundedness_rate": round(grounded_claim_total / all_claim_total, 4) if all_claim_total else 0,
        "lov_mismatch_count": lov_issue_total,
    }

    report = EvaluationReport(
        run_id=run_id,
        total_rows=len(rows),
        ground_truth_rows_matched=matched,
        field_accuracy={k: {"total": v.total, "correct": v.correct, "accuracy": round(v.accuracy, 4)} for k, v in field_accuracy.items()},
        coverage=coverage,
        status_counts=status_counts,
        errors=error_rows,
    )
    return report, results, output_records


def write_reports(report: EvaluationReport, out_dir: Path | str | None = None):
    out_dir = Path(out_dir or settings.REPORTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "evaluation.json").write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")

    with open(out_dir / "evaluation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        for k, v in report.coverage.items():
            w.writerow([k, v])
        for k, v in report.field_accuracy.items():
            w.writerow([f"field_accuracy.{k}", v["accuracy"]])

    with open(out_dir / "errors.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Mfg_Part_Num", "field", "expected", "actual"])
        for e in report.errors:
            w.writerow([e["Mfg_Part_Num"], e["field"], e["expected"], e["actual"]])

    md_lines = [
        f"# Evaluation Report — run `{report.run_id}`", "",
        f"- Total rows processed: **{report.total_rows}**",
        f"- Ground-truth rows matched: **{report.ground_truth_rows_matched}** "
        f"(only rows present in `ground_truth_delivery_format.csv` can be scored for field accuracy — "
        f"see docs/evaluation.md for why this is currently small)",
        "", "## Field accuracy (against verified ground truth)", "",
        "| Field | Correct / Total | Accuracy |", "|---|---|---|",
    ]
    for k, v in report.field_accuracy.items():
        md_lines.append(f"| {k} | {v['correct']}/{v['total']} | {v['accuracy']:.0%} |" if v["total"] else f"| {k} | n/a | n/a |")
    md_lines += ["", "## Batch coverage & quality (full input, no ground truth needed)", "", "| Metric | Value |", "|---|---|"]
    for k, v in report.coverage.items():
        md_lines.append(f"| {k} | {v} |")
    md_lines += ["", "## Status distribution", "", "| Status | Count |", "|---|---|"]
    for k, v in report.status_counts.items():
        md_lines.append(f"| {k} | {v} |")
    (out_dir / "evaluation.md").write_text("\n".join(md_lines), encoding="utf-8")
