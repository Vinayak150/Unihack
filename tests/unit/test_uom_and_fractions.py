from app.uom.engine import canonical_for_alias, format_with_space
from app.uom.fractions import decimal_to_fraction_string, fraction_string_to_decimal


def test_uom_alias_resolves_to_canonical():
    assert canonical_for_alias("inches").canonical == "in"
    assert canonical_for_alias('IN.').canonical == "in"
    assert canonical_for_alias("volts").canonical == "V"
    assert canonical_for_alias("unknown-unit-xyz").canonical is None


def test_format_with_space_rule():
    assert format_with_space("24", "in") == "24 in"
    assert format_with_space("150", "#") == "150#"


def test_fraction_lookup_exact_values():
    assert decimal_to_fraction_string(0.5) == "1/2"
    assert decimal_to_fraction_string(0.25) == "1/4"
    assert decimal_to_fraction_string(0.75) == "3/4"
    assert decimal_to_fraction_string(50.25) == "50-1/4"
    assert decimal_to_fraction_string(12.0) == "12"


def test_fraction_string_round_trip():
    assert fraction_string_to_decimal("1/2") == 0.5
    assert fraction_string_to_decimal("50-1/4") == 50.25
    assert fraction_string_to_decimal("12") == 12.0
    assert fraction_string_to_decimal("") is None
