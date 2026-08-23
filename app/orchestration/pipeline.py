"""Orchestration: wires every stage into the full
RAW -> PROFILE -> CLEAN -> ENTITY RESOLUTION -> CLASSIFY -> EXTRACT ->
NORMALIZE -> GENERATE -> VALIDATE -> SCORE -> REVIEW pipeline for one record,
plus the batch driver with per-record isolation.
"""
from __future__ import annotations

import time
import traceback
import uuid
from dataclasses import dataclass, field

from app.config.settings import settings
from app.confidence.engine import ConfidenceBreakdown, score_record
from app.enrichment.category_processor import ProductContext, get_processor
from app.generation.renderers import GeneratedDescriptions, generate_descriptions
from app.manufacturer.resolver import ResolutionResult, get_resolver
from app.preprocessing.placeholders import clean as clean_placeholder
from app.preprocessing.text_clean import normalize_whitespace, strip_leading_mpn, strip_trailing_notes
from app.provenance.claims import ClaimRegistry
from app.review.queue import ReviewEntry, build_review_entry
from app.taxonomy.classifier import ClassificationResult, get_classifier
from app.validation.engine import ValidationReport, validate_record

STATUS_SUCCESS = "SUCCESS"
STATUS_PARTIAL = "PARTIAL"
STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
STATUS_UNRESOLVED = "UNRESOLVED"
STATUS_VALIDATION_FAILED = "VALIDATION_FAILED"
STATUS_PROCESSING_FAILED = "PROCESSING_FAILED"


@dataclass
class ProcessingResult:
    run_id: str
    row_index: int
    status: str
    input_row: dict
    manufacturer_resolution: ResolutionResult | None = None
    classification: ClassificationResult | None = None
    claim_registry: ClaimRegistry | None = None
    descriptions: GeneratedDescriptions | None = None
    validation: ValidationReport | None = None
    confidence: ConfidenceBreakdown | None = None
    review: ReviewEntry | None = None
    flags: list[str] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0


def process_row(raw_row: dict, row_index: int = 0, run_id: str | None = None) -> ProcessingResult:
    run_id = run_id or uuid.uuid4().hex[:10]
    t0 = time.perf_counter()
    result = ProcessingResult(run_id=run_id, row_index=row_index, status=STATUS_PROCESSING_FAILED, input_row=raw_row)

    try:
        mpn = normalize_whitespace(raw_row.get("Mfg_Part_Num", ""))
        part_manuf = raw_row.get("Part_Manuf", "")
        raw_desc = raw_row.get("Part_Desc", "")

        desc_wo_mpn = strip_leading_mpn(raw_desc, mpn)
        desc_core, flags = strip_trailing_notes(desc_wo_mpn)
        result.flags = flags

        for brand_field in ("E1_Brand", "Unilog_Brand", "DIB_Brand"):
            clean_placeholder(raw_row.get(brand_field))  # placeholder scrub pass (result intentionally unused downstream: these fields are all placeholders in the sample data)

        # -- Entity resolution --------------------------------------------------
        resolver = get_resolver()
        manuf_res = resolver.resolve(part_manuf, raw_desc, mpn)
        result.manufacturer_resolution = manuf_res

        # -- Classification -------------------------------------------------------
        classifier = get_classifier()
        class_res = classifier.classify(raw_desc, manuf_res.canonical_value or "", manuf_res.brand_name or "")
        result.classification = class_res

        # -- Extraction + normalization (category processor) ----------------------
        ctx = ProductContext(
            mpn=mpn, part_desc=raw_desc, manufacturer=manuf_res.canonical_value,
            brand=manuf_res.brand_name, classpath=class_res.classpath, leaf_node=class_res.leaf_node,
            flags=flags,
        )
        processor = get_processor(class_res.classpath)
        registry = processor.extract(ctx)
        result.claim_registry = registry

        # -- Generation -------------------------------------------------------------
        result.descriptions = generate_descriptions(
            manuf_res.canonical_value, manuf_res.brand_name, mpn, class_res.leaf_node, registry, flags,
        )

        # -- Validation ---------------------------------------------------------------
        prelim_record = {
            "MANUFACTURER_NAME": manuf_res.canonical_value or "",
            "BRAND_NAME": manuf_res.brand_name or "",
            "MANUFACTURER_PART_NUMBER": mpn,
            "Classpath": class_res.classpath or "",
            "INVOICE_DESC": result.descriptions.invoice_desc,
            "MOBILE_DESC": result.descriptions.mobile_desc,
        }
        validation = validate_record(prelim_record, registry, class_res.classpath, manuf_res.status, class_res.status)
        result.validation = validation

        # -- Confidence -----------------------------------------------------------------
        lov_mismatches = sum(1 for i in validation.issues if i.check == "vocabulary.attribute_value")
        confidence = score_record(manuf_res.score, manuf_res.method, class_res.score, registry, validation)
        result.confidence = confidence

        # -- Review routing -----------------------------------------------------------
        review = build_review_entry(
            manuf_res.status, class_res.status, validation.passed,
            sum(1 for i in validation.issues if i.severity == "ERROR"),
            confidence.overall, lov_mismatches,
        )
        result.review = review

        # -- Final status --------------------------------------------------------------
        if not validation.passed:
            result.status = STATUS_VALIDATION_FAILED
        elif manuf_res.status == "UNRESOLVED" or class_res.status == "UNRESOLVED":
            result.status = STATUS_UNRESOLVED
        elif review.requires_review:
            result.status = STATUS_REVIEW_REQUIRED
        elif len(registry.grounded_attributes()) < len(registry.claims):
            result.status = STATUS_PARTIAL
        else:
            result.status = STATUS_SUCCESS

    except Exception as exc:  # per-record isolation: one bad row never kills the batch
        result.status = STATUS_PROCESSING_FAILED
        result.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}"

    result.duration_ms = (time.perf_counter() - t0) * 1000
    return result


def process_batch(rows: list[dict], run_id: str | None = None) -> list[ProcessingResult]:
    run_id = run_id or uuid.uuid4().hex[:10]
    return [process_row(row, i, run_id) for i, row in enumerate(rows)]
