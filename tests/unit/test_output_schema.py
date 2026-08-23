from app.core.output_schema import OutputSchema


def test_schema_loads_all_official_headers():
    schema = OutputSchema.load()
    assert len(schema) == 252
    for required in ("MANUFACTURER_NAME", "BRAND_NAME", "Classpath", "MOBILE_DESC", "INVOICE_DESC", "ATTRIBUTE_LABEL 1", "ATTRIBUTE_VALUE 1", "ATTRIBUTE_UOM 1"):
        assert required in schema


def test_to_row_never_drops_or_reorders_headers():
    schema = OutputSchema.load()
    record = {"MANUFACTURER_NAME": "Acme Corp"}
    row = schema.to_row(record)
    assert len(row) == len(schema.headers)
    idx = schema.headers.index("MANUFACTURER_NAME")
    assert row[idx] == "Acme Corp"


def test_validate_flags_unknown_columns():
    schema = OutputSchema.load()
    problems = schema.validate({"NOT_A_REAL_COLUMN": "x"})
    assert problems and "NOT_A_REAL_COLUMN" in problems[0]


def test_empty_record_has_no_fabricated_values():
    schema = OutputSchema.load()
    empty = schema.empty_record()
    assert all(v == "" for v in empty.values())
