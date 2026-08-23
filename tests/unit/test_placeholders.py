from app.preprocessing.placeholders import clean, is_placeholder


def test_known_placeholders_detected():
    for v in ["-- Unbranded --", "-- No Unilog Brand --", "-- No DIB Brand --", "N/A", "unknown", "", None]:
        assert is_placeholder(v), f"{v!r} should be a placeholder"


def test_real_values_not_placeholders():
    assert not is_placeholder("Milwaukee")
    assert not is_placeholder("PDSH4816AF")


def test_clean_returns_none_for_placeholder():
    assert clean("-- Unbranded --") is None
    assert clean("  Milwaukee  ") == "Milwaukee"
