from app.extraction.deterministic import extract_deterministic_claims
from app.normalization.normalize import normalize_claim


def test_diameter_and_grit_extracted_from_abrasive_desc():
    claims = extract_deterministic_claims('5B-332-080 HIOLIT 5" P80')
    by_attr = {c.attribute: c for c in claims}
    assert by_attr["Grit"].value == "P80"
    assert by_attr["Diameter"].value == "5"
    assert by_attr["Diameter"].uom == "in"
    assert by_attr["Diameter"].provenance_type == "DIRECT"


def test_no_claim_when_nothing_present():
    claims = extract_deterministic_claims("16-24 Adjust Hanger")
    assert all(c.attribute not in ("Voltage Rating", "Grit") for c in claims)


def test_normalization_promotes_direct_to_normalized_and_formats_fraction():
    claims = extract_deterministic_claims('49-94-0013 Milw 5"x.045"x7/8" Metal Cut Off Disc')
    arbor = [c for c in claims if c.attribute == "Arbor/Bore Size"][0]
    assert arbor.value == "7/8"
    normalized = normalize_claim(arbor)
    assert normalized.provenance_type == "NORMALIZED"
    assert normalized.uom == "in"
