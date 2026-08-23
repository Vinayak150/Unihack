"""Regression tests pinned to the two verified ground-truth records. If
these ever regress, a real accuracy bug was introduced."""
import csv

from app.config.settings import settings
from app.orchestration.pipeline import process_row


def _ground_truth_row(mpn: str) -> dict:
    with open(settings.GROUND_TRUTH_CSV, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["Mfg_Part_Num"] == mpn:
                return row
    raise AssertionError(f"{mpn} not found in ground truth")


def _input_row(mpn: str) -> dict:
    with open(settings.SAMPLE_INPUT_CSV, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["Mfg_Part_Num"] == mpn:
                return row
    raise AssertionError(f"{mpn} not found in sample input")


def test_frigidaire_dishwasher_manufacturer_brand_classpath():
    gt = _ground_truth_row("PDSH4816AF")
    result = process_row(_input_row("PDSH4816AF"))
    assert result.manufacturer_resolution.canonical_value == gt["MANUFACTURER_NAME"]
    assert result.manufacturer_resolution.brand_name == gt["BRAND_NAME"]
    assert result.classification.classpath == gt["Classpath"]


def test_whirlpool_dishwasher_manufacturer_brand_classpath():
    gt = _ground_truth_row("WDTS7024RZ")
    result = process_row(_input_row("WDTS7024RZ"))
    assert result.manufacturer_resolution.canonical_value == gt["MANUFACTURER_NAME"]
    assert result.manufacturer_resolution.brand_name == gt["BRAND_NAME"]
    assert result.classification.classpath == gt["Classpath"]
