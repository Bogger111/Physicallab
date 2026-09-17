"""Registry wrapper around the established polarization implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.core.exceptions import ExperimentInputError
from experiments.schema import enrich_polarization_config, validate_payload


CONFIG = enrich_polarization_config(
    json.loads(Path(__file__).with_name("config.json").read_text(encoding="utf-8"))
)


class PolarizationExperiment:
    id = "polarization"
    public = True
    legacy = False
    catalogued = True
    config = CONFIG

    @staticmethod
    def _data(payload: dict[str, Any]) -> dict[str, Any]:
        return {key: payload[key] for key in ("malus", "halfwave", "quarterwave", "circular")
                if payload.get(key) is not None}

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        methods = [{
            "id": method["id"], "name": method["name"],
            "required": method.get("required", False),
            "columns": method.get("fields", []), "params": [],
        } for method in self.config.get("subExperiments", [])]
        data: dict[str, Any] = {}
        for method_id in ("malus", "halfwave", "quarterwave", "circular"):
            submitted = payload.get(method_id)
            if submitted:
                data[method_id] = {"rows": submitted.get("rows", [])}
        return validate_payload({"id": self.id, "methods": methods}, data)

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        from experiments.polarization.adapter import PolarizationAdapter

        adapter = PolarizationAdapter(
            bg_uw=payload.get("bg_uw", 0.0),
            theta_qwp=payload.get("theta_qwp", 30.0),
        )
        data: dict[str, Any] = {}
        validation_errors: list[str] = []

        if payload.get("malus"):
            rows = payload["malus"].get("rows", [])
            for index, row in enumerate(rows):
                if row.get("theta") is None:
                    validation_errors.append(f"马吕斯定律: 第 {index + 1} 行角度数据为空")
                if row.get("i_left") is None and row.get("i_right") is None:
                    validation_errors.append(f"马吕斯定律: 第 {index + 1} 行光强数据为空")
            data["malus"] = {"rows": rows}

        if payload.get("halfwave"):
            submitted = payload["halfwave"]
            initial = submitted.get("initial", {})
            rows = submitted.get("rows", [])
            missing_baseline = []
            if initial.get("c_deg") is None:
                missing_baseline.append("检偏器刻度 C")
            if initial.get("p2_deg") is None:
                missing_baseline.append("半波片刻度 P₂")
            if missing_baseline:
                validation_errors.append(
                    f"半波片: 初始读数（{'、'.join(missing_baseline)}）为空，请填写起始角度后再计算"
                )
            for index, row in enumerate(rows):
                if row.get("c_deg") is None or row.get("p2_deg") is None:
                    validation_errors.append(f"半波片: 第 {index + 1} 行数据不完整")
            data["halfwave"] = {"initial": initial, "rows": rows}

        if payload.get("quarterwave"):
            rows = payload["quarterwave"].get("rows", [])
            filled = sum(1 for row in rows if row.get("i_raw") is not None)
            if filled < 10:
                validation_errors.append(f"四分之一波片: 需要至少10个有效光强数据，当前仅有 {filled} 个")
            data["quarterwave"] = {"rows": rows}

        if payload.get("circular"):
            data["circular"] = {"rows": payload["circular"].get("rows", [])}

        if validation_errors:
            return {"status": "validation_error", "errors": validation_errors,
                    "results": {}, "plots": {}}
        if not data:
            raise ExperimentInputError("未提供任何实验数据")
        try:
            result = adapter.process_all(data)
            result["status"] = "success"
            return result
        except Exception as exc:
            return {
                "status": "calculation_error",
                "error": (
                    "计算过程中出现异常，请检查数据是否完整、有无空白或全零的读数，"
                    f"修改后重试。（技术信息：{exc}）"
                ),
                "results": {}, "plots": {},
            }

    def build_report(self, payload: dict[str, Any], fmt: str) -> bytes:
        from experiments.polarization import docbuild
        data = self._data(payload)
        if not data:
            raise ExperimentInputError("未提供任何实验数据")
        return docbuild.report_bytes(
            data,
            bg_uw=payload.get("bg_uw", 0.0),
            theta_qwp=payload.get("theta_qwp", 30.0),
            fmt=fmt,
        )

    def build_record_sheet(self, fmt: str) -> bytes:
        from experiments import record_clean
        return record_clean.record_bytes(self.id, fmt)

    def schema(self) -> dict[str, Any]:
        return {
            "schemaVersion": "2.0",
            "definition": {
                "id": self.config.get("id", self.id),
                "name": self.config.get("name", ""),
                "category": self.config.get("category", ""),
                "description": self.config.get("description", ""),
                "methods": self.config.get("subExperiments", []),
            },
        }

    def catalog_entry(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": "偏振光与双折射",
            "category": "光学",
            "description": "马吕斯定律验证、半波片/四分之一波片特性、圆偏振光分析",
            "sub_experiments": [
                {"id": "malus", "name": "马吕斯定律", "required": True},
                {"id": "halfwave", "name": "半波片", "required": True},
                {"id": "quarterwave", "name": "四分之一波片", "required": True},
                {"id": "circular", "name": "圆偏振光", "required": False},
            ],
            "measurements": [
                {"key": "theta", "label": "角度 θ", "unit": "°"},
                {"key": "intensity", "label": "光强 I", "unit": "μW"},
                {"key": "phi", "label": "方位角 φ", "unit": "°"},
            ],
            "record_sheet": "/api/record-sheets/polarization",
            "processing_time": "~30秒",
        }


EXPERIMENT = PolarizationExperiment()
