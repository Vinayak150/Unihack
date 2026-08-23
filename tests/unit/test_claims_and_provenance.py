import pytest

from app.provenance.claims import Claim, ClaimRegistry


def test_invalid_provenance_type_rejected():
    with pytest.raises(ValueError):
        Claim("Voltage Rating", "120", "V", "MADE_UP", [], 0.9)


def test_registry_grounded_attributes_excludes_unknown():
    reg = ClaimRegistry()
    reg.add(Claim("Voltage Rating", "120", "V", "DIRECT", ["input_row"], 0.9))
    reg.add(Claim("Series", None, None, "UNKNOWN", [], 0.0))
    assert reg.grounded_attributes() == {"Voltage Rating"}
    assert reg.value_of("Series") is None
    assert reg.value_of("Voltage Rating") == "120"
