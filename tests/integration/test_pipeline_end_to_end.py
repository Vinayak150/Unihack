"""Integration tests: run the full orchestration pipeline (no mocking of
internal engines) and check the invariants that must always hold, on both
known and completely unseen inputs."""
from app.core.output_schema import OutputSchema
from app.orchestration.output_mapper import to_output_record
from app.orchestration.pipeline import process_row


def test_verified_dishwasher_row_resolves_correctly():
    row = {
        "Mfg_Part_Num": "PDSH4816AF", "Part_Desc": "PDSH4816AF Dishwasher SS - Display Only",
        "E1_Brand": "-- Unbranded --", "Unilog_Brand": "-- No Unilog Brand --",
        "DIB_Brand": "-- No DIB Brand --", "Part_Manuf": "Appliance Dealers Cooperative (APPDE)",
    }
    result = process_row(row)
    assert result.manufacturer_resolution.canonical_value == "Rheem Manufacturing"
    assert result.manufacturer_resolution.brand_name == "FRIGIDAIRE®"
    assert result.classification.classpath == "Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers"
    assert result.error is None


def test_output_record_preserves_full_official_schema():
    row = {
        "Mfg_Part_Num": "PDSH4816AF", "Part_Desc": "PDSH4816AF Dishwasher SS - Display Only",
        "E1_Brand": "-- Unbranded --", "Unilog_Brand": "-- No Unilog Brand --",
        "DIB_Brand": "-- No DIB Brand --", "Part_Manuf": "Appliance Dealers Cooperative (APPDE)",
    }
    result = process_row(row)
    schema = OutputSchema.load()
    record = to_output_record(schema, result)
    assert set(record.keys()) == set(schema.headers)
    assert record["MANUFACTURER_NAME"] == "Rheem Manufacturing"


def test_completely_unseen_row_never_crashes_and_never_fabricates_manufacturer():
    row = {
        "Mfg_Part_Num": "TOTALLY-NEW-MPN-9999", "Part_Desc": "Unrecognized Widget Assembly Type Z",
        "E1_Brand": "-- Unbranded --", "Unilog_Brand": "-- No Unilog Brand --",
        "DIB_Brand": "-- No DIB Brand --", "Part_Manuf": "Some Totally New Distributor LLC",
    }
    result = process_row(row)
    assert result.error is None
    assert result.status in ("UNRESOLVED", "REVIEW_REQUIRED", "PARTIAL", "VALIDATION_FAILED")
    # never invents a manufacturer/brand string that isn't grounded in master data or the input text
    assert result.manufacturer_resolution.status in ("UNRESOLVED", "LOW_CONFIDENCE")


def test_malformed_row_is_isolated_not_fatal():
    row = {"Mfg_Part_Num": None, "Part_Desc": None, "Part_Manuf": None}
    result = process_row(row)
    assert result.status in ("PROCESSING_FAILED", "UNRESOLVED", "REVIEW_REQUIRED", "VALIDATION_FAILED", "PARTIAL")


def test_generated_descriptions_only_reference_grounded_claims():
    row = {
        "Mfg_Part_Num": "DBD090094101F", "Part_Desc": 'DBD090094101F Diablo 9" - Metal Cut-Off Disc',
        "E1_Brand": "-- Unbranded --", "Unilog_Brand": "-- No Unilog Brand --",
        "DIB_Brand": "-- No DIB Brand --", "Part_Manuf": "Freud Inc (2435)",
    }
    result = process_row(row)
    forbidden_marketing_terms = ["premium performance", "commercial-grade", "energy efficient", "best in class"]
    long_desc_low = result.descriptions.long_desc.lower()
    for term in forbidden_marketing_terms:
        assert term not in long_desc_low
