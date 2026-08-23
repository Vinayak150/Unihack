"""
Output schema registry.

The official delivery format has a fixed, exact set of ~252 column headers.
Whatever the pipeline does internally, the exported file must:
  - contain every one of those headers, spelled and capitalized exactly
  - never rename, drop, or reorder them
  - contain nothing that isn't grounded (empty string, not a guess, when unknown)

This module is the single place that knows what "the official header row" is.
Everything downstream maps its internal product-intelligence record onto this
schema; nothing downstream is allowed to invent its own column names.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GROUND_TRUTH = ROOT / "data" / "raw" / "ground_truth_delivery_format.csv"

# Columns that repeat with a numeric suffix (ATTRIBUTE_LABEL 1..50, ITEM_FEATURES_1..20)
REPEATING_ATTRIBUTE_SLOTS = 50
REPEATING_FEATURE_SLOTS = 20


class OutputSchema:
    """Loads and enforces the official output header contract."""

    def __init__(self, headers: list[str]):
        if not headers:
            raise ValueError("OutputSchema loaded with zero headers")
        self.headers = list(headers)
        self._index = {h: i for i, h in enumerate(self.headers)}

    # -- construction ------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path = DEFAULT_GROUND_TRUTH) -> "OutputSchema":
        path = Path(path)
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            headers = next(reader)
        return cls(headers)

    # -- introspection -------------------------------------------------------
    def __len__(self):
        return len(self.headers)

    def __contains__(self, header: str) -> bool:
        return header in self._index

    def attribute_slots(self) -> list[tuple[str, str, str]]:
        """Returns (label_col, value_col, uom_col) for each of the 50 attribute slots."""
        slots = []
        for i in range(1, REPEATING_ATTRIBUTE_SLOTS + 1):
            label_col, value_col, uom_col = f"ATTRIBUTE_LABEL {i}", f"ATTRIBUTE_VALUE {i}", f"ATTRIBUTE_UOM {i}"
            if label_col in self._index:
                slots.append((label_col, value_col, uom_col))
        return slots

    def feature_slots(self) -> list[str]:
        return [c for c in (f"ITEM_FEATURES_{i}" for i in range(1, REPEATING_FEATURE_SLOTS + 1)) if c in self._index]

    # -- validation / export --------------------------------------------------
    def validate(self, record: dict) -> list[str]:
        """Returns a list of problems: unknown keys the record tried to set."""
        problems = []
        for key in record.keys():
            if key not in self._index:
                problems.append(f"unknown output column: {key!r} is not part of the official schema")
        return problems

    def to_row(self, record: dict) -> list[str]:
        """Projects an internal record dict onto the exact official column order.
        Any header not present in `record` is exported as an empty string -
        never fabricated, never dropped."""
        return [str(record.get(h, "") if record.get(h) is not None else "") for h in self.headers]

    def empty_record(self) -> dict:
        return {h: "" for h in self.headers}

    def export_csv(self, records: list[dict], path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(self.headers)
            for r in records:
                w.writerow(self.to_row(r))

    def export_xlsx(self, records: list[dict], path: str | Path):
        from openpyxl import Workbook

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        ws = wb.active
        ws.title = "Delivery Format"
        ws.append(self.headers)
        for r in records:
            ws.append(self.to_row(r))
        wb.save(path)
