"""Registry wrapper around the established sound/light implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.core.exceptions import ExperimentInputError
from experiments.schema import enrich_soundlight_config, validate_payload


CONFIG = enrich_soundlight_config(
    json.loads(Path(__file__).with_name("config.json").read_text(encoding="utf-8"))
)


class SoundLightExperiment:
    id = "sound-light"
    public = True
    legacy = False
    catalogued = True
    config = CONFIG

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        method_id = payload.get("method")
        method = next((item for item in self.config if item["id"] == method_id), None)
        if method is None:
            raise ExperimentInputError("实验方法不存在")
        rows_by_column = payload.get("rows") or {}
        keys = [field["key"] for field in method.get("fields", [])]
        max_rows = max((len(rows_by_column.get(key, [])) for key in keys), default=0)
        rows = [{
            key: (rows_by_column.get(key, [None] * max_rows)[index]
                  if index < len(rows_by_column.get(key, [])) else None)
            for key in keys
        } for index in range(max_rows)]
        generic = {"id": self.id, "methods": [{
            "id": method["id"], "name": method["name"],
            "required": method.get("type") == "required",
            "columns": method.get("fields", []), "params": method.get("params", []),
        }]}
        return validate_payload(generic, {
            method_id: {"rows": rows, "params": payload.get("params") or {}}
        })

    def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        from experiments.soundlight import engine
        return engine.process_method(
            payload.get("method", ""), payload.get("rows") or {}, payload.get("params") or {}
        )

    def build_report(self, payload: dict[str, Any], fmt: str) -> bytes:
        if not payload:
            raise ExperimentInputError("未提供任何实验数据")
        from experiments.soundlight import docs
        return docs.report_bytes(payload, fmt)

    def build_record_sheet(self, fmt: str) -> bytes:
        from experiments import record_clean
        return record_clean.record_bytes(self.id, fmt)

    def schema(self) -> dict[str, Any]:
        return {
            "schemaVersion": "2.0",
            "definition": {
                "id": self.id, "name": "声速光速的测量",
                "category": "波动", "description": "声速与光速测量",
                "methods": self.config,
            },
        }

    def catalog_entry(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": "声速光速的测量",
            "category": "波动",
            "description": "空气共振法、水中相位法、飞行时间法测声速；正弦、方波相位法与李萨如法测光速",
            "sub_experiments": [
                {"id": method["id"], "name": method["name"],
                 "required": method["type"] == "required"}
                for method in self.config
            ],
            "record_sheet": "/api/record-sheets/sound-light",
            "processing_time": "~1分钟",
        }


EXPERIMENT = SoundLightExperiment()
