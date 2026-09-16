#!/usr/bin/env python3
"""Export explicitly consented, verified OCR cells for future fine-tuning.

No training is performed here.  Only feedback rows with a consented, verified
cell image are copied; rows collected without an image remain in analytics but
cannot accidentally become a training example.

Example:
    python scripts/export_ocr_dataset.py --output ocr_dataset
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path


def export_dataset(database: Path, output: Path) -> int:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=None,
                        help="telemetry.sqlite3 path (defaults to PHYSICSLAB_TELEMETRY_DB)")
    parser.add_argument("--output", type=Path, default=Path("ocr_dataset"))
    args = parser.parse_args()
    if args.database is None:
        from app.telemetry import database_path
        args.database = database_path()
    count = export_dataset(args.database, args.output)
    print(f"exported {count} verified OCR cells to {args.output}")


if __name__ == "__main__":
    main()
