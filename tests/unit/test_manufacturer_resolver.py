from app.manufacturer.resolver import get_resolver


def test_exact_observed_manufacturer_resolves():
    r = get_resolver()
    res = r.resolve("Milwaukee Accessory (4031)", "some generic desc with no brand token", "XYZ")
    assert res.status == "RESOLVED"
    assert res.canonical_value == "Milwaukee Accessory"


def test_brand_token_in_text_outranks_distributor_part_manuf():
    r = get_resolver()
    res = r.resolve("Appliance Dealers Cooperative (APPDE)", "LDPH5554D LG Dishwasher BSS", "LDPH5554D")
    assert res.method == "brand_alias_token_match"
    assert res.canonical_value == "LG Electronics"
    assert res.brand_name == "LG®"


def test_confirmed_mpn_prefix_beats_distributor():
    r = get_resolver()
    res = r.resolve("Appliance Dealers Cooperative (APPDE)", "PDSH4816AF Dishwasher SS - Display Only", "PDSH4816AF")
    assert res.method == "mpn_prefix_pattern_match"
    assert res.canonical_value == "Rheem Manufacturing"
    assert res.brand_name == "FRIGIDAIRE®"


def test_placeholder_part_manuf_is_unresolved():
    r = get_resolver()
    res = r.resolve("-", "totally generic text", "ZZZ")
    assert res.status in ("UNRESOLVED", "LOW_CONFIDENCE")


def test_result_is_explainable():
    r = get_resolver()
    res = r.resolve("Milwaukee Accessory (4031)", "desc", "XYZ")
    d = res.to_dict()
    for key in ("input", "canonical_value", "entity_code", "score", "method", "status", "evidence"):
        assert key in d
    assert isinstance(d["evidence"], list) and len(d["evidence"]) > 0
