"""PhysLab → PhysLab_OCR dataset builder (consent-first, template-driven).

Pipeline::

    confirmed collection session
        → raw record-sheet image (private storage)
        → EXIF/page/perspective normalisation  (preprocess)
        → experiment template ROI per stable field id  (ocr_layouts/<experiment>.json)
        → single-cell crop, table lines removed        (segment)
        → label = the confirmed string for that field id
        → quality gate                                 (quality)
        → PhysLab_OCR compatible dataset:
              images/000001.png …
              labels.csv            (header exactly: image,text)
              samples.csv, rejected.csv, manifest.json   (extra provenance, separate)

Compatibility contract with `Bogger111/PhysLab_OCR`:

* ``labels.csv`` has exactly two columns, ``image,text``; ``image`` is a bare
  filename inside ``images/`` (their loader does ``Path(image_dir) / row["image"]``);
* every label character must be in the OCR charset (``0123456789.``), because
  their ``encode()`` raises on anything else — units, signs and spaces must never
  reach ``labels.csv``;
* PNG, grayscale, original aspect ratio: resizing/padding to 160x80 is their
  dataset transform's job, not ours.

Run standalone::

    python -m ocr_dataset.builder --session-id <uuid> --output <dir>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ocr_dataset import templates
from ocr_dataset.preprocess import PreprocessedPage, preprocess_content
from ocr_dataset.quality import evaluate_crop, load_charset, validate_label
from ocr_dataset.segment import segmenter_for

DEFAULT_EXPORT_NAME = "ocr_export"
LABELS_FILENAME = "labels.csv"
SAMPLES_FILENAME = "samples.csv"
REJECTED_FILENAME = "rejected.csv"
MANIFEST_FILENAME = "manifest.json"
IMAGES_DIRNAME = "images"
LABEL_COLUMNS = ("image", "text")

#: Segmentation notes that must block an export: the value may be clipped or the
#: crop may sit on the wrong cell.  Other notes (a decimal point is legitimately
#: detached ink) are recorded as provenance instead of disqualifying the sample.
BLOCKING_NOTES = ("ink_touches_roi_border", "low_segmentation_confidence")


@dataclass(frozen=True)
class SampleRecord:
    image: str
    text: str
    field_id: str
    session_id: str
    experiment_id: str
    revision: int
    source_image: str
    segmentation_method: str
    quality_score: float
    sample_key: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RejectedSample:
    field_id: str
    text: str
    reason: str
    disposition: str
    session_id: str
    revision: int
    source_image: str
    quality_score: float = 0.0
    sample_key: str = ""


@dataclass
class BuildOutcome:
    session_id: str
    experiment_id: str
    revision: int
    export_name: str
    output_dir: Path
    images_dir: Path
    labels_path: Path
    samples_created: int
    rejected: list[RejectedSample] = field(default_factory=list)
    skipped_duplicates: int = 0
    registration: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False

    @property
    def reason_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.rejected:
            counts[item.reason] = counts.get(item.reason, 0) + 1
        return counts

    def as_api_payload(self) -> dict[str, Any]:
        """The three documented keys first, then operational detail."""
        return {
            "success": True,
            "samples_created": self.samples_created,
            "output": self.export_name,
            "session_id": self.session_id,
            "experiment_id": self.experiment_id,
            "revision": self.revision,
            "rejected": len(self.rejected),
            "skipped_duplicates": self.skipped_duplicates,
            "dry_run": self.dry_run,
            "reason_counts": self.reason_counts,
        }


class BuilderError(RuntimeError):
    """Raised when a session may not be turned into training data at all."""


def sample_key(session_id: str, field_id: str, revision: int) -> str:
    """Deterministic identity of one sample, so re-runs never duplicate a crop."""
    digest = hashlib.sha256(f"{session_id}|{field_id}|{revision}".encode("utf-8"))
    return digest.hexdigest()[:32]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ session gate

def _session_gate(record: Any) -> None:
    """Same admission rules the offline collector applies, applied earlier."""
    if record.consent is not True:
        raise BuilderError("该会话没有有效授权")
    if record.status != "confirmed":
        raise BuilderError("会话尚未确认最终数值，不能生成 OCR 数据集")
    if record.revision < 1:
        raise BuilderError("会话没有确认修订，不能生成 OCR 数据集")
    if not record.fields:
        raise BuilderError("会话没有最终确认数值")
    if not record.image_bytes:
        raise BuilderError("原始记录表图片缺失")


# ------------------------------------------------------------------ helpers

def _existing_samples(export_dir: Path) -> list[dict[str, str]]:
    """Read back `samples.csv` so numbering and dedupe survive across sessions."""
    path = export_dir / SAMPLES_FILENAME
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _next_index(existing: list[dict[str, str]]) -> int:
    highest = 0
    for row in existing:
        stem = Path(str(row.get("image", ""))).stem
        if stem.isdigit():
            highest = max(highest, int(stem))
    return highest


def _write_png(path: Path, image: np.ndarray) -> None:
    if not cv2.imwrite(str(path), image):
        raise OSError(f"cannot write {path}")


def _label_of(fields: dict[str, Any], field_id: str) -> str:
    """Confirmed value exactly as submitted — never parsed into a float."""
    value = fields.get(field_id)
    if value is None:
        return ""
    if isinstance(value, bool):
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value).strip()


# ------------------------------------------------------------------ main build

def build_session_dataset(
    session_id: str,
    *,
    storage: Any = None,
    output_dir: Path | None = None,
    export_name: str = DEFAULT_EXPORT_NAME,
    template_root: Path | None = None,
    charset_path: Path | None = None,
    denoise: bool = False,
    dry_run: bool = False,
    overwrite: bool = False,
) -> BuildOutcome:
    """Turn one confirmed session into PhysLab_OCR samples.

    ``dry_run`` reports what would be written (and why anything is rejected)
    without creating a single file.
    """
    from app.data_collection import local_storage

    store = storage if storage is not None else local_storage()
    record = store.load_session(session_id)
    _session_gate(record)

    template = templates.load_template(record.experiment_id, template_root)
    layout = templates.template_layout(template)
    reference_size = (int(template["reference_size"][0]), int(template["reference_size"][1]))
    characters, charset_version = load_charset(charset_path)

    export_dir = Path(output_dir) if output_dir is not None else Path(store.dataset_dir(export_name))
    if overwrite and export_dir.exists() and not dry_run:
        import shutil

        shutil.rmtree(export_dir)
    images_dir = export_dir / IMAGES_DIRNAME

    page = preprocess_content(record.image_bytes, reference_size, denoise=denoise)
    segmenter = segmenter_for(page, layout)
    registration = {
        "registered": bool(segmenter.registration.registered),
        "score": round(float(segmenter.registration.score), 4),
        "coverage": round(float(segmenter.registration.coverage), 4),
        "detail": segmenter.registration.detail,
    }

    fields = ordered_field_ids(template)
    existing = [] if overwrite else _existing_samples(export_dir)
    known_keys = {str(row.get("sample_key", "")) for row in existing}
    counter = _next_index(existing)

    samples: list[SampleRecord] = []
    rejected: list[RejectedSample] = []
    skipped = 0

    for field_id in fields:
        key = sample_key(record.session_id, field_id, record.revision)
        label = _label_of(record.fields, field_id)
        if label == "":
            # Fields the student left empty are simply not training data.
            continue
        if key in known_keys:
            skipped += 1
            continue

        def reject(reason: str, disposition: str = "reject", score: float = 0.0) -> None:
            rejected.append(RejectedSample(
                field_id=field_id, text=label, reason=reason, disposition=disposition,
                session_id=record.session_id, revision=record.revision,
                source_image=record.image_ref, quality_score=score, sample_key=key,
            ))

        # A label the OCR charset cannot encode is unusable no matter how clean
        # the crop is, so it is refused before any segmentation work.
        illegal = [reason for reason in validate_label(label, characters) if reason != "empty_label"]
        if illegal:
            reject(illegal[0])
            continue
        if not registration["registered"]:
            reject(registration["detail"] or "page_not_registered")
            continue

        crop_result = segmenter.crop(field_id)
        decision = evaluate_crop(
            crop_result.image,
            label=label,
            charset=characters,
            segmentation_confidence=crop_result.confidence,
            touches_roi_border=crop_result.touches_roi_border,
            segmentation_notes=tuple(note for note in crop_result.notes if note in BLOCKING_NOTES),
        )
        if crop_result.image is None:
            reject(crop_result.reason or "missing_crop")
            continue
        if decision.disposition == "reject":
            reject(decision.reasons[0] if decision.reasons else "rejected_crop",
                   "reject", decision.score)
            continue
        if decision.disposition == "review":
            reject(decision.reasons[0] if decision.reasons else "needs_review",
                   "review", decision.score)
            continue

        counter += 1
        name = f"{counter:06d}.png"
        samples.append(SampleRecord(
            image=name, text=label, field_id=field_id, session_id=record.session_id,
            experiment_id=record.experiment_id, revision=record.revision,
            source_image=record.image_ref, segmentation_method=crop_result.method,
            quality_score=decision.score, sample_key=key,
            notes=tuple(crop_result.notes),
        ))
        if not dry_run:
            images_dir.mkdir(parents=True, exist_ok=True)
            _write_png(images_dir / name, crop_result.image)

    outcome = BuildOutcome(
        session_id=record.session_id,
        experiment_id=record.experiment_id,
        revision=record.revision,
        export_name=export_dir.name,
        output_dir=export_dir,
        images_dir=images_dir,
        labels_path=export_dir / LABELS_FILENAME,
        samples_created=len(samples),
        rejected=rejected,
        skipped_duplicates=skipped,
        registration=registration,
        dry_run=dry_run,
    )

    if not dry_run:
        _write_export(export_dir, existing, samples, rejected, outcome, characters,
                      charset_version, template)
    return outcome


def ordered_field_ids(template: dict[str, Any]) -> list[str]:
    """Cell order is the page order of the template (stable across runs)."""
    ordered = sorted(template["cells"], key=lambda cell: (int(cell.get("page", 1)),
                                                          float(cell["bbox"][1]), float(cell["bbox"][0])))
    return [cell["field_id"] for cell in ordered]


def _write_export(
    export_dir: Path,
    existing: list[dict[str, str]],
    samples: list[SampleRecord],
    rejected: list[RejectedSample],
    outcome: BuildOutcome,
    characters: str,
    charset_version: str,
    template: dict[str, Any],
) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)

    rows = list(existing) + [
        {
            "image": sample.image,
            "text": sample.text,
            "field_id": sample.field_id,
            "session_id": sample.session_id,
            "experiment_id": sample.experiment_id,
            "revision": str(sample.revision),
            "source_image": sample.source_image,
            "segmentation_method": sample.segmentation_method,
            "quality_score": f"{sample.quality_score:.4f}",
            "sample_key": sample.sample_key,
            "notes": "|".join(sample.notes),
        }
        for sample in samples
    ]

    # labels.csv is the training contract: exactly two columns, nothing else.
    labels_path = export_dir / LABELS_FILENAME
    with labels_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(LABEL_COLUMNS)
        for row in rows:
            writer.writerow([row["image"], row["text"]])

    sample_columns = ["image", "text", "field_id", "session_id", "experiment_id", "revision",
                      "source_image", "segmentation_method", "quality_score", "sample_key", "notes"]
    with (export_dir / SAMPLES_FILENAME).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sample_columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    previous_rejections: list[dict[str, str]] = []
    rejected_path = export_dir / REJECTED_FILENAME
    if rejected_path.is_file():
        with rejected_path.open("r", encoding="utf-8", newline="") as handle:
            previous_rejections = [dict(row) for row in csv.DictReader(handle)]
    with rejected_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["session_id", "revision", "field_id", "text", "reason", "disposition",
                      "source_image", "quality_score", "sample_key"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in previous_rejections:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
        for item in rejected:
            writer.writerow({
                "session_id": item.session_id, "revision": item.revision, "field_id": item.field_id,
                "text": item.text, "reason": item.reason, "disposition": item.disposition,
                "source_image": item.source_image, "quality_score": f"{item.quality_score:.4f}",
                "sample_key": item.sample_key,
            })

    manifest = {
        "schema_version": "1.0",
        "generated_at": _now(),
        "last_session": {
            "session_id": outcome.session_id,
            "experiment_id": outcome.experiment_id,
            "revision": outcome.revision,
            "source_image": f"sessions/{outcome.session_id}/raw.jpg",
        },
        "dataset": {
            "labels": LABELS_FILENAME,
            "columns": list(LABEL_COLUMNS),
            "images_dir": IMAGES_DIRNAME,
            "samples": len(rows),
            "images": len(list((export_dir / IMAGES_DIRNAME).glob("*.png")))
            if (export_dir / IMAGES_DIRNAME).is_dir() else 0,
            "compatible_with": "PhysLab_OCR datasets/sequencedatasets.py (image,text)",
        },
        "charset": {"version": charset_version, "characters": characters},
        "template": {
            "experiment": template["experiment_id"],
            "schema_version": template["schema_version"],
            "cells": len(template["cells"]),
        },
        "registration": outcome.registration,
        "last_run": {
            "samples_created": outcome.samples_created,
            "skipped_duplicates": outcome.skipped_duplicates,
            "rejected": [item.__dict__ for item in outcome.rejected],
            "reason_counts": outcome.reason_counts,
        },
    }
    (export_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_export(export_dir: Path) -> list[str]:
    """Check an export against the PhysLab_OCR contract; returns problems."""
    export_dir = Path(export_dir)
    problems: list[str] = []
    labels_path = export_dir / LABELS_FILENAME
    images_dir = export_dir / IMAGES_DIRNAME
    if not labels_path.is_file():
        return [f"missing {LABELS_FILENAME}"]
    if not images_dir.is_dir():
        problems.append(f"missing {IMAGES_DIRNAME}/")
    characters, _ = load_charset()
    with labels_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    if not rows or rows[0] != list(LABEL_COLUMNS):
        problems.append(f"header must be exactly {','.join(LABEL_COLUMNS)}")
        return problems
    for index, row in enumerate(rows[1:], start=2):
        if len(row) != 2:
            problems.append(f"line {index}: {len(row)} columns")
            continue
        name, text = row
        if Path(name).name != name:
            problems.append(f"line {index}: image must be a bare filename ({name})")
        if not (images_dir / name).is_file():
            problems.append(f"line {index}: missing image {name}")
        if text == "":
            problems.append(f"line {index}: empty label")
        if any(character not in characters for character in text):
            problems.append(f"line {index}: label {text!r} outside charset {characters!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output", type=Path, default=None,
                        help="export directory (default: <collection>/datasets/ocr_export)")
    parser.add_argument("--collection-root", type=Path, default=None)
    parser.add_argument("--template-root", type=Path, default=None)
    parser.add_argument("--charset-config", type=Path, default=None)
    parser.add_argument("--denoise", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    storage = None
    if args.collection_root is not None:
        from app.data_collection import LocalCollectionStorage

        storage = LocalCollectionStorage(args.collection_root)

    outcome = build_session_dataset(
        args.session_id, storage=storage, output_dir=args.output,
        template_root=args.template_root, charset_path=args.charset_config,
        denoise=args.denoise, dry_run=args.dry_run, overwrite=args.overwrite,
    )
    print(json.dumps(outcome.as_api_payload(), ensure_ascii=False, indent=2))
    for reason, count in sorted(outcome.reason_counts.items()):
        print(f"  rejected[{reason}] = {count}")
    if not outcome.dry_run:
        problems = verify_export(outcome.output_dir)
        for problem in problems:
            print(f"  INVALID {problem}")
        print(f"  export: {outcome.output_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
