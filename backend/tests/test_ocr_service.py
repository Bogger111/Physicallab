from app.ocr_service import NumericCandidate, normalize_numeric_text, sort_candidates
from app.ocr_metrics import cell_exact_match_accuracy, character_accuracy, correction_rate
from experiments.schema import enrich_config, validate_payload


def _item(value: str, x: float, y: float) -> NumericCandidate:
    return NumericCandidate(value, value, 0.9, [], x, y, 10)


def test_numeric_ocr_normalization_handles_common_confusions():
    assert normalize_numeric_text(" O.543 ") == "0.543"
    assert normalize_numeric_text("−12，50V") == "-12.50"
    assert normalize_numeric_text("1.23×10^4") == "1.23e4"
    assert normalize_numeric_text("无读数") is None


def test_candidates_are_sorted_in_visual_row_major_order():
    values = sort_candidates([
        _item("4", 40, 40), _item("2", 40, 10),
        _item("3", 10, 40), _item("1", 10, 10),
    ])
    assert [item.value for item in values] == ["1", "2", "3", "4"]


def test_ocr_metrics_prioritize_cell_exact_match():
    predictions = ["24.220", "24.202", "-0.315"]
    truth = ["24.220", "24.220", "-0.315"]
    assert cell_exact_match_accuracy(predictions, truth) == 2 / 3
    assert character_accuracy(predictions, truth) > 0.8
    assert correction_rate(predictions, truth) == 1 / 3


def test_schema_supports_optional_monotonic_validation():
    config = enrich_config({"id": "demo", "name": "演示", "methods": [{
        "id": "line", "name": "序列", "required": True, "rowCount": 3,
        "columns": [{"key": "x", "label": "x", "unit": "mm"}],
        "validation": {"monotonic": {"field": "x", "direction": "increasing"}},
    }]})
    result = validate_payload(config, {"line": {"rows": [{"x": 2}, {"x": 1}], "params": {}}})
    assert any(issue["code"] == "monotonic" for issue in result["warnings"])
