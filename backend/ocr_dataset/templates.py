"""Portable experiment templates: which record-sheet cell belongs to which field.

`backend/ocr_layouts/<experiment_id>.json` is the template consumed by
`ocr_dataset.builder`.  A university physics record sheet has a fixed layout, so
a template beats generic text detection: the cell is known, only the handwriting
inside it is unknown.

The coordinates are *derived* from the calibrated layouts in
`ocr_dataset/layouts/` (produced by `calibrate.py` from the record sheets this
repository renders), so a template and its calibration can never disagree: the
generator fails loudly if a field id is not in the calibration.  Run

    python -m ocr_dataset.templates --check      # verify all templates match
    python -m ocr_dataset.templates --write      # regenerate from calibration
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

TEMPLATE_SCHEMA_VERSION = "1.0"
TEMPLATES_DIRNAME = "ocr_layouts"
CALIBRATION_DIRNAME = "layouts"


def templates_root() -> Path:
    """`backend/ocr_layouts/` — the template directory shipped with the backend."""
    return Path(__file__).resolve().parents[1] / TEMPLATES_DIRNAME


def calibration_root() -> Path:
    """`backend/ocr_dataset/layouts/` — the calibrated ROI layouts."""
    return Path(__file__).with_name(CALIBRATION_DIRNAME)


def template_path(experiment_id: str, root: Path | None = None) -> Path:
    return (root or templates_root()) / f"{experiment_id}.json"


def build_template(layout: dict[str, Any]) -> dict[str, Any]:
    """Convert one calibrated layout into the portable template schema."""
    experiment_id = layout["experiment_id"]
    cells = [
        {
            "field_id": field_id,
            "bbox": [float(spec["x1"]), float(spec["y1"]), float(spec["x2"]), float(spec["y2"])],
            "page": int(spec.get("page", 1)),
            "confidence": float(spec.get("confidence", 1.0)),
        }
        for field_id, spec in sorted(layout["fields"].items())
    ]
    return {
        "schema_version": TEMPLATE_SCHEMA_VERSION,
        "experiment": experiment_id,
        "experiment_id": experiment_id,
        "template_version": layout.get("template_version", "2.0"),
        "reference_size": [int(value) for value in layout["reference_size"]],
        "source": {
            "kind": "calibrated_record_sheet",
            "calibration": f"ocr_dataset/{CALIBRATION_DIRNAME}/{experiment_id}.json",
            "capture_scope": layout.get("capture_scope", "calibrated_page_1"),
        },
        "cells": cells,
        "registration": {
            "anchors": layout.get("anchors", []),
            "lattice": layout.get("lattice", {}),
        },
    }


def _fail(path: Path, message: str) -> ValueError:
    return ValueError(f"invalid ocr template {path}: {message}")


def load_template(experiment_id: str, root: Path | None = None) -> dict[str, Any]:
    """Load and validate a template, rejecting anything the builder cannot trust."""
    path = template_path(experiment_id, root)
    if not path.is_file():
        raise FileNotFoundError(f"missing ocr template: {path}")
    template = json.loads(path.read_text(encoding="utf-8"))
    if template.get("experiment_id") != experiment_id or template.get("experiment") != experiment_id:
        raise _fail(path, "experiment mismatch")
    if template.get("schema_version") != TEMPLATE_SCHEMA_VERSION:
        raise _fail(path, f"unsupported schema_version {template.get('schema_version')!r}")
    reference = template.get("reference_size")
    if not (isinstance(reference, list) and len(reference) == 2
            and all(isinstance(value, int) and value > 0 for value in reference)):
        raise _fail(path, "reference_size must be two positive integers")
    cells = template.get("cells")
    if not isinstance(cells, list) or not cells:
        raise _fail(path, "cells must be a non-empty list")
    seen: set[str] = set()
    for cell in cells:
        if not isinstance(cell, dict):
            raise _fail(path, "each cell must be an object")
        field_id = cell.get("field_id")
        box = cell.get("bbox")
        if not isinstance(field_id, str) or not field_id:
            raise _fail(path, "cell without field_id")
        if field_id in seen:
            raise _fail(path, f"duplicate field_id {field_id}")
        seen.add(field_id)
        if not (isinstance(box, list) and len(box) == 4
                and all(isinstance(value, (int, float)) for value in box)):
            raise _fail(path, f"cell {field_id} bbox must be four numbers")
        x1, y1, x2, y2 = (float(value) for value in box)
        if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
            raise _fail(path, f"cell {field_id} bbox outside the page")
    return template


def template_fields(template: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """`{field_id: {x1, y1, x2, y2, page, confidence}}` as `segment.py` expects."""
    fields: dict[str, dict[str, Any]] = {}
    for cell in template["cells"]:
        x1, y1, x2, y2 = (float(value) for value in cell["bbox"])
        fields[cell["field_id"]] = {
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "page": int(cell.get("page", 1)),
            "confidence": float(cell.get("confidence", 1.0)),
        }
    return fields


def template_layout(template: dict[str, Any]) -> dict[str, Any]:
    """Template as an internal layout dict, so the calibrated crop path is reused."""
    registration = template.get("registration") or {}
    return {
        "experiment_id": template["experiment_id"],
        "template_version": template.get("template_version", "2.0"),
        "reference_size": list(template["reference_size"]),
        "fields": template_fields(template),
        "anchors": registration.get("anchors", []),
        "lattice": registration.get("lattice", {}),
    }


def validate_field_ids(experiment_id: str, template: dict[str, Any]) -> list[str]:
    """Return the field ids that the collection schema does not accept."""
    from app.data_collection import valid_stable_field_id

    return [
        cell["field_id"]
        for cell in template["cells"]
        if not valid_stable_field_id(experiment_id, cell["field_id"])
    ]


def generate_templates(
    root: Path | None = None,
    *,
    calibration: Path | None = None,
    experiment_ids: list[str] | None = None,
) -> list[Path]:
    """(Re)write templates from the calibrated layouts. Returns written paths."""
    target_root = root or templates_root()
    source_root = calibration or calibration_root()
    if experiment_ids is None:
        from experiments.core.registry import PUBLIC_EXPERIMENT_IDS

        experiment_ids = list(PUBLIC_EXPERIMENT_IDS)
    target_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for experiment_id in experiment_ids:
        source = source_root / f"{experiment_id}.json"
        if not source.is_file():
            raise FileNotFoundError(f"missing calibration: {source}")
        layout = json.loads(source.read_text(encoding="utf-8"))
        if layout.get("experiment_id") != experiment_id:
            raise ValueError(f"calibration experiment mismatch: {source}")
        template = build_template(layout)
        invalid = validate_field_ids(experiment_id, template)
        if invalid:
            raise ValueError(f"{experiment_id}: template field ids rejected by the schema: {invalid[:5]}")
        path = template_path(experiment_id, target_root)
        path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def check_templates(root: Path | None = None, *, calibration: Path | None = None) -> list[str]:
    """Return drift messages; empty means every shipped template matches calibration."""
    target_root = root or templates_root()
    source_root = calibration or calibration_root()
    problems: list[str] = []
    for source in sorted(source_root.glob("*.json")):
        experiment_id = source.stem
        try:
            template = load_template(experiment_id, target_root)
        except (FileNotFoundError, ValueError) as exc:
            problems.append(str(exc))
            continue
        expected = build_template(json.loads(source.read_text(encoding="utf-8")))
        if template["cells"] != expected["cells"] or template["reference_size"] != expected["reference_size"]:
            problems.append(f"{experiment_id}: template differs from calibration")
        invalid = validate_field_ids(experiment_id, template)
        if invalid:
            problems.append(f"{experiment_id}: field ids not in schema: {invalid[:5]}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenerate templates from calibration")
    parser.add_argument("--check", action="store_true", help="verify templates match calibration")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.write:
        for path in generate_templates(args.root):
            print(f"wrote {path}")
        return 0
    problems = check_templates(args.root)
    if problems:
        for problem in problems:
            print(f"DRIFT {problem}")
        return 1
    print("all templates match calibration")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
