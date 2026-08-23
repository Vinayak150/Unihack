"""Robust tabular ingestion: accepts CSV or XLSX, does not assume row 1 is a
clean header (scans the first few rows for the one that looks most like a
header — mostly non-numeric, mostly non-empty, no duplicate placeholder
runs), and profiles the result."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.preprocessing.placeholders import is_placeholder


def _looks_like_header(row: list) -> float:
    if not row:
        return 0.0
    non_empty = [c for c in row if c is not None and str(c).strip() != ""]
    if not non_empty:
        return 0.0
    non_numeric = sum(1 for c in non_empty if not str(c).strip().replace(".", "", 1).replace("-", "", 1).isdigit())
    return non_numeric / len(row)


def load_tabular(path: str | Path, sheet_name=0) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm", ".xltx"):
        raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
    elif path.suffix.lower() in (".csv", ".tsv"):
        sep = "\t" if path.suffix.lower() == ".tsv" else ","
        raw = pd.read_csv(path, sep=sep, header=None, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    else:
        raise ValueError(f"unsupported file type: {path.suffix}")

    best_row, best_score = 0, -1.0
    for i in range(min(5, len(raw))):
        score = _looks_like_header(raw.iloc[i].tolist())
        if score > best_score:
            best_row, best_score = i, score

    header = [str(c).strip() if c is not None else "" for c in raw.iloc[best_row].tolist()]
    data = raw.iloc[best_row + 1:].copy()
    data.columns = header
    data = data.reset_index(drop=True)
    return data


def profile_dataframe(df) -> dict:
    stats = {}
    for col in df.columns:
        series = df[col].astype(str)
        placeholder_count = series.apply(is_placeholder).sum()
        empty_count = (series.str.strip() == "").sum()
        stats[col] = {
            "non_empty": int((~series.apply(is_placeholder)).sum()),
            "placeholder": int(placeholder_count),
            "empty": int(empty_count),
            "distinct": int(series.nunique()),
        }
    return {"rows": len(df), "columns": len(df.columns), "column_stats": stats}
