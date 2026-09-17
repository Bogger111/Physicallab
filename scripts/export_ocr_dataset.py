#!/usr/bin/env python3
"""Export explicitly consented, confirmed data for future OCR research.

No training, cropping, segmentation, or OCR is performed here.  The default
mode reads the optional raw record-sheet collection and writes one CSV row per
stable field label.  The legacy SQLite cell-feedback export remains available
when ``--database`` is supplied.

Example:
    python scripts/export_ocr_dataset.py --output ocr_dataset
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sqlite3
import sys
from pathlib import Path
from uuid import UUID


BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


MANIFEST_COLUMNS = ["session_id", "experiment_id", "field_id", "value", "image_path"]
FORBIDDEN_METADATA_KEYS = {
    "name", "student_id", "phone", "wechat", "email", "ip", "ip_address",
    "user_agent", "browser_fingerprint", "account", "headers",
}
REQUIRED_METADATA_KEYS = {
    "session_id", "experiment_id", "template_version", "consent", "status",
    "revision", "created_at", "confirmed_at", "updated_at", "image_path", "fields",
}


def _contains_forbidden_metadata(value: object) -> bool:
    if isinstance(value, dict):
        if any(str(key).lower() in FORBIDDEN_METADATA_KEYS for key in value):
            return True
        return any(_contains_forbidden_metadata(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_metadata(child) for child in value)
    return False


def export_collection_dataset(collection_root: Path, output: Path) -> int:
    """Export confirmed labels and their uncropped source sheet to manifest.csv."""
    from app.data_collection import valid_stable_field_id

    output.mkdir(parents=True, exist_ok=True)
    images = output / "images"
    images.mkdir(exist_ok=True)
    manifest_path = output / "manifest.csv"
    rows: list[dict[str, object]] = []
    metadata_dir = collection_root / "metadata"

    for metadata_path in sorted(metadata_dir.glob("*.json")) if metadata_dir.is_dir() else []:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not REQUIRED_METADATA_KEYS.issubset(metadata):
                continue
            session_id = str(metadata["session_id"])
            if str(UUID(session_id)) != session_id or metadata_path.stem != session_id:
                continue
            if metadata.get("consent") is not True or metadata.get("status") != "confirmed":
                continue
            if not isinstance(metadata.get("template_version"), str) or not metadata["template_version"]:
                continue
            if not isinstance(metadata.get("confirmed_at"), str) or not metadata["confirmed_at"]:
                continue
            if not isinstance(metadata.get("revision"), int) or metadata["revision"] < 1:
                continue
            if _contains_forbidden_metadata(metadata):
                continue
            experiment_id = str(metadata["experiment_id"])
            fields = metadata.get("fields")
            if not isinstance(fields, dict) or not fields:
                continue
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in fields.values()
            ):
                continue
            expected_image_path = f"raw/{session_id}.jpg"
            if metadata.get("image_path") != expected_image_path:
                continue
            source = collection_root / expected_image_path
            if not source.is_file():
                continue
            if any(not valid_stable_field_id(experiment_id, str(field_id)) for field_id in fields):
                continue
            destination = images / f"{session_id}.jpg"
            shutil.copy2(source, destination)
            relative = f"images/{destination.name}"
            for field_id, value in sorted(fields.items()):
                rows.append({
                    "session_id": session_id,
                    "experiment_id": experiment_id,
                    "field_id": field_id,
                    "value": value,
                    "image_path": relative,
                })
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
            continue

    with manifest_path.open("w", encoding="utf-8", newline="") as manifest:
        writer = csv.DictWriter(manifest, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def export_legacy_dataset(database: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    images = output / "images"
    images.mkdir(exist_ok=True)
    labels_path = output / "labels.tsv"
    metadata_path = output / "metadata.jsonl"
    if not database.exists():
        labels_path.write_text("", encoding="utf-8")
        metadata_path.write_text("", encoding="utf-8")
        return 0
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT * FROM ocr_feedback
           WHERE consent=1 AND verified=1 AND cell_image_path IS NOT NULL
           ORDER BY created_at, sample_id"""
    ).fetchall()
    exported = 0
    with labels_path.open("w", encoding="utf-8") as labels, metadata_path.open("w", encoding="utf-8") as metadata:
        for row in rows:
            source = Path(row["cell_image_path"])
            if not source.is_file():
                continue
            name = f"{row['sample_id']}{source.suffix.lower() or '.png'}"
            destination = images / name
            shutil.copy2(source, destination)
            relative = f"images/{name}"
            labels.write(f"{relative}\t{row['confirmed_value']}\n")
            metadata.write(json.dumps({
                "image": relative,
                "experiment_id": row["experiment_id"],
                "field_id": row["field_id"],
                "ocr_prediction": row["prediction"],
                "confidence": row["confidence"],
                "ocr_provider": row["ocr_provider"],
                "ocr_model_version": row["ocr_model_version"],
                "was_corrected": bool(row["was_corrected"]),
            }, ensure_ascii=False) + "\n")
            exported += 1
    return exported


# Keep the original import-level API compatible for callers that used the
# pre-collection SQLite exporter directly.
export_dataset = export_legacy_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=None,
                        help="legacy telemetry.sqlite3 cell-feedback export")
    parser.add_argument("--collection-root", type=Path, default=None,
                        help="raw/metadata root (defaults to PHYSICSLAB_COLLECTION_ROOT)")
    parser.add_argument("--output", type=Path, default=Path("ocr_dataset"))
    args = parser.parse_args()
    if args.database is not None:
        count = export_legacy_dataset(args.database, args.output)
        print(f"exported {count} verified OCR cells to {args.output}")
        return
    if args.collection_root is None:
        from app.data_collection import collection_root
        args.collection_root = collection_root()
    count = export_collection_dataset(args.collection_root, args.output)
    print(f"exported {count} confirmed field labels to {args.output / 'manifest.csv'}")


if __name__ == "__main__":
    main()
