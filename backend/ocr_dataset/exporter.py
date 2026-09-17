"""Dataset file writer, manifest builder, and visual contact sheet."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


LABEL_COLUMNS = [
    "image", "text", "experiment_id", "field_id", "session_id",
    "source_image", "revision", "segmentation_method", "quality_score",
]
REJECT_COLUMNS = [
    "sample_id", "experiment_id", "field_id", "session_id", "source_image",
    "revision", "disposition", "reason",
]


@dataclass
class AcceptedSample:
    sample_id: str
    image: np.ndarray
    text: str
    experiment_id: str
    field_id: str
    session_id: str
    source_image: str
    revision: int
    segmentation_method: str
    quality_score: float


@dataclass
class RejectedSample:
    sample_id: str
    experiment_id: str
    field_id: str
    session_id: str
    source_image: str
    revision: int | None
    disposition: str
    reasons: tuple[str, ...]


@dataclass
class BuildResult:
    accepted: list[AcceptedSample] = field(default_factory=list)
    rejected: list[RejectedSample] = field(default_factory=list)
    sessions_seen: int = 0
    registration_failures: int = 0

    @property
    def reason_counts(self) -> dict[str, int]:
        counts = Counter(reason for item in self.rejected for reason in item.reasons)
        return dict(sorted(counts.items()))

    @property
    def segmentation_counts(self) -> dict[str, int]:
        counts = Counter(item.segmentation_method for item in self.accepted)
        return dict(sorted(counts.items()))


def deterministic_sample_id(session_id: str, field_id: str, revision: int) -> str:
    value = f"{session_id}\x1f{field_id}\x1f{revision}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _filename(sample: AcceptedSample) -> str:
    field = re.sub(r"[^A-Za-z0-9_-]+", "_", sample.field_id).strip("_")
    return f"{sample.session_id}_{field}_{sample.sample_id[:12]}.png"


def _contact_sheet(samples: list[AcceptedSample], path: Path) -> None:
    tile_width, tile_height = 360, 150
    columns = 3
    rows = max(1, (len(samples) + columns - 1) // columns)
    canvas = Image.new("L", (columns * tile_width, rows * tile_height), 255)
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, sample in enumerate(samples):
        left = (index % columns) * tile_width
        top = (index // columns) * tile_height
        crop = Image.fromarray(sample.image.astype(np.uint8), mode="L")
        crop.thumbnail((tile_width - 20, 82), Image.Resampling.LANCZOS)
        canvas.paste(crop, (left + 10, top + 8))
        label = f"GT: {sample.text}"
        meta = f"{sample.experiment_id} | {sample.field_id}"
        draw.text((left + 10, top + 96), label, fill=0, font=font)
        draw.text((left + 10, top + 116), meta[:56], fill=0, font=font)
        draw.rectangle((left, top, left + tile_width - 1, top + tile_height - 1), outline=190)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, format="PNG", optimize=True)


def export_dataset(
    result: BuildResult,
    output: Path,
    *,
    charset: str,
    charset_version: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        if not overwrite:
            raise FileExistsError(f"output is not empty: {output}; pass --overwrite")
        shutil.rmtree(output)
    images_dir = output / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    label_rows: list[dict[str, Any]] = []
    for sample in sorted(result.accepted, key=lambda item: item.sample_id):
        filename = _filename(sample)
        if not cv2.imwrite(str(images_dir / filename), sample.image):
            raise OSError(f"failed to write crop: {filename}")
        label_rows.append({
            "image": f"images/{filename}", "text": sample.text,
            "experiment_id": sample.experiment_id, "field_id": sample.field_id,
            "session_id": sample.session_id, "source_image": sample.source_image,
            "revision": sample.revision, "segmentation_method": sample.segmentation_method,
            "quality_score": f"{sample.quality_score:.4f}",
        })
    with (output / "labels.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LABEL_COLUMNS)
        writer.writeheader()
        writer.writerows(label_rows)
    with (output / "rejected.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REJECT_COLUMNS)
        writer.writeheader()
        for item in sorted(result.rejected, key=lambda value: (value.session_id, value.field_id, value.sample_id)):
            writer.writerow({
                "sample_id": item.sample_id, "experiment_id": item.experiment_id,
                "field_id": item.field_id, "session_id": item.session_id,
                "source_image": item.source_image, "revision": item.revision or "",
                "disposition": item.disposition, "reason": ";".join(item.reasons),
            })
    _contact_sheet(sorted(result.accepted, key=lambda item: item.sample_id),
                   output / "preview" / "contact_sheet.png")
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "charset": {"version": charset_version, "characters": charset},
        "counts": {
            "sessions": result.sessions_seen,
            "sessions_not_registered": result.registration_failures,
            "accepted": len(result.accepted),
            "rejected_or_review": len(result.rejected),
        },
        "segmentation": result.segmentation_counts,
        "reasons": result.reason_counts,
        "privacy": {
            "contains_full_source_pages": False,
            "contains_numeric_crops_only": True,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def write_contact_sheet(samples: list[AcceptedSample], path: Path) -> None:
    """Public helper used by tests and manual review tooling."""
    _contact_sheet(samples, path)
