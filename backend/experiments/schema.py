"""Shared experiment schema and canonical, warning-first validation.

The calculation adapters remain experiment-specific.  This module owns the
small contract shared by every experiment so API callers, OCR and future
imports can validate data in the same way without duplicating frontend rules.
"""

from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ExperimentField:
    id: str
    label: str
    unit: str = ""
    type: str = "float"
    required: bool = True
    expected_range: tuple[float, float] | None = None
    decimal_places: int | None = None


@dataclass(frozen=True)
class ExperimentValidationIssue:
    method_id: str
    field_id: str
    row: int | None
    level: str
    code: str
    message: str


@dataclass(frozen=True)
class ExperimentDefinition:
    id: str
    name: str
    category: str
    description: str
    methods: tuple[dict[str, Any], ...]
    schema_version: str = "2.0"


@dataclass(frozen=True)
class ExperimentCalculation:
    """Metadata for an adapter entry; the executable formula stays in Python."""

    method_id: str
    adapter: str


@dataclass(frozen=True)
class ExperimentResult:
    key: str
    label: str
    unit: str = ""


# These are deliberately guidance ranges.  They are warnings, never hard
# bounds, because an unusual but real laboratory reading must remain usable.
_RANGES: dict[tuple[str, str, str], tuple[float, float]] = {
    ("photoelectric", "planck", "wavelength"): (300, 800),
    ("photoelectric", "compensation", "wavelength"): (300, 800),
    ("franck-hertz", "peaks", "peak_voltage"): (0, 100),
    ("sound-light", "air_resonance", "temperature_degC"): (0, 50),
    ("sound-light", "air_resonance", "f_khz"): (30, 50),
    ("sound-light", "water_phase", "f_mhz"): (0.5, 2),
    ("sound-light", "light_sine", "f_mhz"): (100, 200),
    ("sound-light", "light_square", "f_mhz"): (100, 200),
    ("sound-light", "light_lissajous", "f_mhz"): (100, 200),
}


def _infer_type(key: str, label: str = "") -> str:
    token = f"{key} {label}".lower()
    if any(mark in token for mark in ("_code", "编码", "序号", "count", "次数")):
        return "integer"
    return "float"


def _infer_range(experiment_id: str, method_id: str, field: dict[str, Any]) -> tuple[float, float]:
    key = str(field.get("key", ""))
    explicit = _RANGES.get((experiment_id, method_id, key))
    if explicit:
        return explicit
    label = str(field.get("label", ""))
    token = f"{key} {label}".lower()
    unit = str(field.get("unit", ""))
    if "wavelength" in token or "波长" in token or unit == "nm":
        return (200, 1200)
    if "angle" in token or "角度" in token or "方位" in token or "phi" in token:
        return (0, 360)
    if "temperature" in token or "温度" in token:
        return (-50, 300)
    if "frequency" in token or "频率" in token:
        return (0, 1_000_000)
    if "fringe_count" in key or "fringes_per_step" in key:
        return (1, 10_000)
    if "tail_count" in key:
        return (0, 100)
    if unit in {"mm", "cm", "m", "°", "°C"}:
        return (0, 10_000)
    if unit in {"μs", "us", "ms", "s"}:
        return (0, 1_000_000)
    if unit in {"V", "A"}:
        return (-1_000, 1_000)
    if unit in {"mA", "μA", "nA", "mV", "μW", "Ω", "kΩ", "N"}:
        return (-10_000, 10_000)
    if _infer_type(key, label) == "integer":
        return (0, 10)
    return (-1_000_000, 1_000_000)


def _field_dict(experiment_id: str, method_id: str, field: dict[str, Any], *, required: bool) -> dict[str, Any]:
    item = dict(field)
    item.setdefault("type", _infer_type(str(item.get("key", "")), str(item.get("label", ""))))
    item.setdefault("required", required)
    item.setdefault("expected_range", list(_infer_range(experiment_id, method_id, item)))
    if "decimal_places" not in item:
        item["decimal_places"] = 0 if item["type"] == "integer" else 3
    return item


def enrich_config(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a backwards-compatible config with the 2.0 field contract."""
    config = copy.deepcopy(raw)
    config.setdefault("schemaVersion", "2.0")
    config.setdefault("metadata", {
        "id": config.get("id", ""),
        "name": config.get("name", ""),
        "category": config.get("category", ""),
        "description": config.get("description", ""),
    })
    config.setdefault("validation", {
        "expectedRangeIsWarning": True,
        "finiteNumbers": True,
        "decimalPlacesAreWarning": True,
    })
    for method in config.get("methods", []):
        method.setdefault("tableId", method.get("id", ""))
        method.setdefault("validation", {})
        method["validation"].setdefault("finiteNumbers", True)
        method["validation"].setdefault("expectedRangeIsWarning", True)
        method["columns"] = [
            _field_dict(config["id"], method["id"], field,
                        required=bool(field.get("required", False)))
            for field in method.get("columns", [])
        ]
        method["params"] = [
            _field_dict(config["id"], method["id"], field,
                        required=bool(field.get("required", False)))
            for field in method.get("params", [])
        ]
        method["fields"] = copy.deepcopy(method["columns"])
    return config


def definition_from_config(config: dict[str, Any]) -> ExperimentDefinition:
    return ExperimentDefinition(
        id=config["id"], name=config["name"], category=config["category"],
        description=config.get("description", ""),
        methods=tuple(copy.deepcopy(config.get("methods", []))),
        schema_version=str(config.get("schemaVersion", "2.0")),
    )


def _iter_values(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        yield from value.values()
    elif isinstance(value, list):
        yield from value


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def validate_payload(config: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Validate a generic payload, returning errors and non-blocking warnings."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    methods = {method["id"]: method for method in config.get("methods", [])}
    for method_id, method in methods.items():
        payload = data.get(method_id) or {}
        rows = payload.get("rows") or []
        fields = method.get("columns", [])
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(asdict(ExperimentValidationIssue(
                    method_id, "", row_index, "error", "row_type", "数据行必须是对象")))
                continue
            active = any(value not in (None, "") for value in row.values())
            if not active:
                continue
            for field in fields:
                key = field["key"]
                value = row.get(key)
                if value in (None, ""):
                    if field.get("required", True):
                        errors.append(asdict(ExperimentValidationIssue(
                            method_id, key, row_index, "error", "required",
                            f"{method['name']}：第 {row_index + 1} 行{field.get('label', key)}为空")))
                    continue
                number = _number(value)
                if number is None:
                    errors.append(asdict(ExperimentValidationIssue(
                        method_id, key, row_index, "error", "numeric",
                        f"{method['name']}：第 {row_index + 1} 行{field.get('label', key)}必须是有限数字")))
                    continue
                if field.get("type") == "integer" and not number.is_integer():
                    errors.append(asdict(ExperimentValidationIssue(
                        method_id, key, row_index, "error", "integer",
                        f"{method['name']}：第 {row_index + 1} 行{field.get('label', key)}必须是整数")))
                expected = field.get("expected_range")
                if expected and (number < expected[0] or number > expected[1]):
                    warnings.append(asdict(ExperimentValidationIssue(
                        method_id, key, row_index, "warning", "expected_range",
                        f"{method['name']}：第 {row_index + 1} 行{field.get('label', key)}={value} 超出常见范围 {expected[0]}–{expected[1]}，请核对原始记录")))
                places = field.get("decimal_places")
                if places is not None and isinstance(value, str) and "." in value:
                    actual = len(value.split(".", 1)[1])
                    if actual > places:
                        warnings.append(asdict(ExperimentValidationIssue(
                            method_id, key, row_index, "warning", "decimal_places",
                            f"{method['name']}：第 {row_index + 1} 行{field.get('label', key)}建议保留不超过 {places} 位小数")))
        for field in method.get("params", []):
            key = field["key"]
            value = (payload.get("params") or {}).get(key)
            if value in (None, ""):
                continue
            number = _number(value)
            if number is None:
                errors.append(asdict(ExperimentValidationIssue(
                    method_id, key, None, "error", "numeric",
                    f"{method['name']}：参数{field.get('label', key)}必须是有限数字")))
                continue
            expected = field.get("expected_range")
            if expected and (number < expected[0] or number > expected[1]):
                warnings.append(asdict(ExperimentValidationIssue(
                    method_id, key, None, "warning", "expected_range",
                    f"{method['name']}：参数{field.get('label', key)}={value} 超出常见范围 {expected[0]}–{expected[1]}，请核对")))
        monotonic = method.get("monotonic") or method.get("validation", {}).get("monotonic")
        if monotonic:
            field_key = monotonic if isinstance(monotonic, str) else monotonic.get("field")
            direction = "increasing" if isinstance(monotonic, str) else monotonic.get("direction", "increasing")
            sequence = [_number(row.get(field_key)) for row in rows if isinstance(row, dict)]
            sequence = [value for value in sequence if value is not None]
            valid = all((b >= a if direction == "increasing" else b <= a)
                        for a, b in zip(sequence, sequence[1:]))
            if len(sequence) > 1 and not valid:
                warnings.append(asdict(ExperimentValidationIssue(
                    method_id, str(field_key), None, "warning", "monotonic",
                    f"{method['name']}：{field_key} 未保持{direction}顺序，请核对读数")))
        for relationship in method.get("validation", {}).get("relationships", []):
            left, right = relationship.get("left"), relationship.get("right")
            operator = relationship.get("operator", "<")
            if not left or not right:
                continue
            for row_index, row in enumerate(rows):
                a, b = _number(row.get(left)), _number(row.get(right))
                if a is None or b is None:
                    continue
                passed = {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "=": a == b}.get(operator, True)
                if not passed:
                    warnings.append(asdict(ExperimentValidationIssue(
                        method_id, left, row_index, "warning", "relationship",
                        f"{method['name']}：第 {row_index + 1} 行不满足 {left} {operator} {right}，请核对")))
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def enrich_polarization_config(config: dict[str, Any]) -> dict[str, Any]:
    """Attach the same field metadata to the hand-written polarization schema."""
    result = copy.deepcopy(config)
    result["schemaVersion"] = "2.0"
    result["metadata"] = {
        "id": result.get("id", "polarization"), "name": result.get("name", ""),
        "category": result.get("category", ""), "description": result.get("description", ""),
    }
    columns = {
        "malus": [("theta", "角度 θ", "°"), ("i_left", "左旋光强", "μW"), ("i_right", "右旋光强", "μW")],
        "halfwave": [("offset", "偏移量", "°"), ("c_deg", "C 度", "°"), ("c_min", "C 分", "′"), ("p2_deg", "P₂ 度", "°"), ("p2_min", "P₂ 分", "′")],
        "quarterwave": [("phi", "方位角 φ", "°"), ("i_raw", "光强 I", "μW")],
        "circular": [("angle", "检偏器角度", "°"), ("i_raw", "光强 I", "μW")],
    }
    for method in result.get("subExperiments", []):
        method["tableId"] = method["id"]
        method["fields"] = [
            _field_dict(result["id"], method["id"], {"key": key, "label": label, "unit": unit}, required=False)
            for key, label, unit in columns.get(method["id"], [])
        ]
    result["validation"] = {"expectedRangeIsWarning": True, "finiteNumbers": True}
    return result


def enrich_soundlight_config(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize the legacy method-array schema without changing its shape."""
    result = copy.deepcopy(items)
    for method in result:
        method["schemaVersion"] = "2.0"
        method["tableId"] = method.get("id", "")
        method["fields"] = [
            _field_dict("sound-light", method["id"], field, required=False)
            for field in method.get("table_cols", [])
        ]
        method["validation"] = {"expectedRangeIsWarning": True, "finiteNumbers": True}
    return result
