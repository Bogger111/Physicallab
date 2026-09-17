"""Public combined adapter preserving both legacy modern-physics engines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.photoelectric import EXPERIMENT as PHOTOELECTRIC
from experiments.franck_hertz import EXPERIMENT as FRANCK_HERTZ
from experiments.schema import definition_from_config, enrich_config


CONFIG = enrich_config(json.loads(Path(__file__).with_name("config.json").read_text(encoding="utf-8")))


class PhotoelectricFranckHertzExperiment:
    id = "photoelectric-franck-hertz"
    public = True
    legacy = False
    catalogued = True
    config = CONFIG
    formulas = {**PHOTOELECTRIC.formulas, **FRANCK_HERTZ.formulas}
    sources = (PHOTOELECTRIC, FRANCK_HERTZ)

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        issues = {"valid": True, "errors": [], "warnings": []}
        for source in self.sources:
            method_ids = {method["id"] for method in source.config["methods"]}
            result = source.validate({key: value for key, value in payload.items() if key in method_ids})
            issues["errors"].extend(result["errors"])
            issues["warnings"].extend(result["warnings"])
        issues["valid"] = not issues["errors"]
        return issues

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        combined = {
            "status": "success", "results": {}, "plots": {}, "derived": {},
            "errors": [], "warnings": [],
            "validation": {"valid": True, "errors": [], "warnings": []},
        }
        for source in self.sources:
            method_ids = {method["id"] for method in source.config["methods"]}
            result = source.process({key: value for key, value in payload.items() if key in method_ids})
            combined["results"].update(result.get("results", {}))
            combined["plots"].update(result.get("plots", {}))
            combined["derived"].update(result.get("derived", {}))
            combined["errors"].extend(result.get("errors", []))
            combined["warnings"].extend(result.get("warnings", []))
            combined["validation"]["errors"].extend(result.get("validation", {}).get("errors", []))
            combined["validation"]["warnings"].extend(result.get("validation", {}).get("warnings", []))
        combined["validation"]["valid"] = not combined["validation"]["errors"]
        if combined["validation"]["errors"] or not combined["results"]:
            combined["status"] = "validation_error"
        return combined

    def report_analysis(self, method_id: str, result: dict[str, Any]) -> list[dict[str, Any]]:
        return []

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
                "id": definition.id, "name": definition.name,
                "category": definition.category, "description": definition.description,
                "methods": list(definition.methods),
            },
        }

    def catalog_entry(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.config["name"],
            "category": self.config["category"], "description": self.config["description"],
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


EXPERIMENT = PhotoelectricFranckHertzExperiment()
