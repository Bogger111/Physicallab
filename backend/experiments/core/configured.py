"""Shared lifecycle for config-driven experiments.

Calculation functions and experiment-specific hooks live in their own modules;
this class owns only the common validation/result envelope and document calls.
"""

from __future__ import annotations

from typing import Any, Callable

from experiments.schema import definition_from_config, summarize_messages, validate_payload


Calculator = Callable[[str, list[dict], dict[str, Any]], tuple[dict, list[dict], str | None]]
PrepareParams = Callable[[str, dict[str, Any], dict[str, dict]], dict[str, Any]]
FinalizeResult = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
ExtraAnalysis = Callable[[str, dict[str, Any]], list[dict[str, Any]]]


class ConfiguredExperiment:
    def __init__(
        self,
        *,
        experiment_id: str,
        config: dict[str, Any],
        calculator: Calculator,
        formulas: dict[str, list[str]],
        public: bool = True,
        legacy: bool = False,
        catalogued: bool = True,
        prepare_params: PrepareParams | None = None,
        finalize_result: FinalizeResult | None = None,
        extra_analysis: ExtraAnalysis | None = None,
    ) -> None:
        self.id = experiment_id
        self.config = config
        self.calculator = calculator
        self.formulas = formulas
        self.public = public
        self.legacy = legacy
        self.catalogued = catalogued
        self._prepare_params = prepare_params
        self._finalize_result = finalize_result
        self._extra_analysis = extra_analysis

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return validate_payload(self.config, payload)

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        validation = self.validate(payload)
        if validation["errors"]:
            return {
                "status": "validation_error",
                "results": {}, "plots": {}, "derived": {},
                "errors": summarize_messages(validation["errors"]),
                "warnings": summarize_messages(validation["warnings"]),
                "validation": validation,
            }
        results: dict[str, dict] = {}
        plots: dict[str, str] = {}
        derived: dict[str, list[dict]] = {}
        errors: list[str] = []
        for method in self.config["methods"]:
            submitted = payload.get(method["id"], {})
            rows = submitted.get("rows", [])
            params = dict(submitted.get("params", {}))
            if not rows or not any(
                any(value not in (None, "") for value in row.values()) for row in rows
            ):
                if method.get("required"):
                    errors.append(f"{method['name']}：未提供数据")
                continue
            try:
                if self._prepare_params:
                    params = self._prepare_params(method["id"], params, results)
                result, detail, chart = self.calculator(method["id"], rows, params)
                results[method["id"]] = result
                derived[method["id"]] = detail
                if chart:
                    plots[method["id"]] = chart
            except Exception as exc:
                errors.append(f"{method['name']}：{exc}")
        status = "success" if results else "validation_error"
        response = {
            "status": status, "results": results, "plots": plots,
            "derived": derived, "errors": errors,
            "warnings": summarize_messages(validation["warnings"]),
            "validation": validation,
        }
        return self._finalize_result(payload, response) if self._finalize_result else response

    def report_analysis(self, method_id: str, result: dict[str, Any]) -> list[dict[str, Any]]:
        return self._extra_analysis(method_id, result) if self._extra_analysis else []

    def build_report(self, payload: dict[str, Any], fmt: str) -> bytes:
        from experiments.core.documents import report_bytes
        return report_bytes(self, payload, fmt)

    def build_record_sheet(self, fmt: str) -> bytes:
        from experiments.core.documents import record_bytes
        return record_bytes(self, fmt)

    def schema(self) -> dict[str, Any]:
        definition = definition_from_config(self.config)
        return {
            "schemaVersion": self.config.get("schemaVersion", "2.0"),
            "definition": {
                "id": definition.id,
                "name": definition.name,
                "category": definition.category,
                "description": definition.description,
                "methods": list(definition.methods),
            },
        }

    def catalog_entry(self) -> dict[str, Any]:
        entry = {
            "id": self.id,
            "name": self.config["name"],
            "category": self.config["category"],
            "description": self.config["description"],
            "sub_experiments": [
                {"id": method["id"], "name": method["name"],
                 "required": method.get("required", False)}
                for method in self.config["methods"]
            ],
            "measurements": [
                {"key": f"measurement_{index}", "label": label, "unit": ""}
                for index, label in enumerate(self.config.get("measurements", []), start=1)
            ],
            "record_sheet": f"/api/record-sheets/{self.id}",
            "processing_time": self.config["processingTime"],
        }
        if self.legacy:
            entry["legacy"] = True
        return entry
