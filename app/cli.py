#!/usr/bin/env python3
"""Command-line interface.

    python -m app.cli enrich --input in.csv --output out.xlsx
    python -m app.cli evaluate [--input in.csv]
    python -m app.cli profile --input in.csv
    python -m app.cli build-index
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from app.config.settings import settings


def cmd_build_index(args):
    import subprocess
    subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "build_reference_data.py")], check=True)


def cmd_profile(args):
    from app.ingestion.loader import load_tabular, profile_dataframe

    df = load_tabular(args.input)
    profile = profile_dataframe(df)
    print(f"rows={profile['rows']} columns={profile['columns']}")
    for col, stats in profile["column_stats"].items():
        print(f"  {col}: non_empty={stats['non_empty']} placeholder={stats['placeholder']} empty={stats['empty']} distinct={stats['distinct']}")


def cmd_enrich(args):
    from app.core.output_schema import OutputSchema
    from app.ingestion.loader import load_tabular
    from app.orchestration.output_mapper import to_output_record
    from app.orchestration.pipeline import process_batch

    t0 = time.perf_counter()
    df = load_tabular(args.input)
    rows = df.to_dict(orient="records")
    print(f"loaded {len(rows)} rows from {args.input}")

    results = process_batch(rows, run_id=args.run_id or "cli-run")
    schema = OutputSchema.load(args.schema) if args.schema else OutputSchema.load()
    output_records = [to_output_record(schema, r) for r in results]

    out_path = Path(args.output)
    if out_path.suffix.lower() == ".xlsx":
        schema.export_xlsx(output_records, out_path)
    else:
        schema.export_csv(output_records, out_path)

    elapsed = time.perf_counter() - t0
    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1
    print(f"wrote {len(output_records)} records to {out_path} in {elapsed:.2f}s")
    print("status distribution:", status_counts)
    if args.report_dir:
        _write_run_summary(results, args.report_dir, args.run_id or "cli-run")


def _write_run_summary(results, report_dir, run_id):
    out = Path(report_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{run_id}_records.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row_index", "mpn", "status", "manufacturer", "brand", "classpath", "confidence", "requires_review", "error"])
        for r in results:
            w.writerow([
                r.row_index, r.input_row.get("Mfg_Part_Num", ""), r.status,
                r.manufacturer_resolution.canonical_value if r.manufacturer_resolution else "",
                r.manufacturer_resolution.brand_name if r.manufacturer_resolution else "",
                r.classification.classpath if r.classification else "",
                round(r.confidence.overall, 4) if r.confidence else "",
                r.review.requires_review if r.review else "",
                r.error or "",
            ])
    print(f"wrote per-record summary to {out / f'{run_id}_records.csv'}")


def cmd_evaluate(args):
    from app.evaluation.evaluator import evaluate, write_reports

    report, results, output_records = evaluate(input_csv=args.input, run_id=args.run_id or "cli-eval")
    write_reports(report, out_dir=args.report_dir)
    print(f"evaluated {report.total_rows} rows, {report.ground_truth_rows_matched} matched against ground truth")
    print("coverage:", report.coverage)
    print(f"reports written to {args.report_dir or settings.REPORTS_DIR}")


def main():
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Unilog Product Intelligence CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_enrich = sub.add_parser("enrich", help="run the full enrichment pipeline on an input file")
    p_enrich.add_argument("--input", required=True)
    p_enrich.add_argument("--output", required=True)
    p_enrich.add_argument("--schema", default=None, help="path to a CSV whose header row defines the output schema (defaults to the official ground-truth header)")
    p_enrich.add_argument("--run-id", dest="run_id", default=None)
    p_enrich.add_argument("--report-dir", dest="report_dir", default=None)
    p_enrich.set_defaults(func=cmd_enrich)

    p_eval = sub.add_parser("evaluate", help="run enrichment + score against ground truth + write reports/")
    p_eval.add_argument("--input", default=None)
    p_eval.add_argument("--run-id", dest="run_id", default=None)
    p_eval.add_argument("--report-dir", dest="report_dir", default=None)
    p_eval.set_defaults(func=cmd_evaluate)

    p_profile = sub.add_parser("profile", help="profile a raw input file (dimensions, placeholders, distinct values)")
    p_profile.add_argument("--input", required=True)
    p_profile.set_defaults(func=cmd_profile)

    p_index = sub.add_parser("build-index", help="(re)build reference/master-data tables from data/raw")
    p_index.set_defaults(func=cmd_build_index)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
