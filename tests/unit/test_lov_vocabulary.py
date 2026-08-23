from app.lov.vocabulary import get_vocabulary

DISHWASHER = "Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers"


def test_enum_value_exact_match():
    v = get_vocabulary()
    match = v.validate_value(DISHWASHER, "Material", "Stainless Steel")
    assert match.status == "IN_VOCABULARY"
    assert match.canonical_value == "Stainless Steel"


def test_enum_value_not_in_vocabulary():
    v = get_vocabulary()
    match = v.validate_value(DISHWASHER, "Material", "Unobtainium")
    assert match.status == "NOT_IN_VOCABULARY"


def test_non_enum_attribute_has_no_constraint():
    v = get_vocabulary()
    match = v.validate_value(DISHWASHER, "Series", "Professional Series")
    assert match.status == "NO_CONSTRAINT"
