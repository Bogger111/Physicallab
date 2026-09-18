"""Pack every confirmed contribution into one PhysLab_OCR ready archive.

    python -m backend.ocr_dataset.export                  # all confirmed sessions
    python -m backend.ocr_dataset.export --experiment sound-light
    python -m backend.ocr_dataset.export --output dist/physlab_ocr_dataset.zip
    python -m backend.ocr_dataset.export --dry-run

The archive carries exactly what the training repository needs::

    dataset/images/000001.png …
    dataset/labels.csv            # image,text
    dataset/manifest.json         # version, created_at, experiment_count, sample_count

Sources stay where they were collected: the archive only ever contains numeric
crops and the label index, never a source page.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from ocr_dataset.builder import (  # noqa: E402  (path bootstrap must run first)
    DEFAULT_EXPORT_NAME,
    LABELS_FILENAME,
    MANIFEST_FILENAME,
    SAMPLES_FILENAME,
    BuilderError,
    build_session_dataset,
    verify_export,
)

EXPORT_VERSION = "1.0"
DEFAULT_ZIP_NAME = "physlab_ocr_dataset.zip"
ARCHIVE_ROOT = "dataset"


@dataclass
class ExportOutcome:
    archive: Path
    sample_count: int
    experiment_count: int
    experiments: dict[str, int] = field(default_factory=dict)
    sessions_seen: int = 0
    sessions_exported: int = 0
    rejected: int = 0
    skipped_duplicates: int = 0
    dry_run: bool = False
    problems: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "Export completed",
            f"samples: {self.sample_count}",
            f"experiments: {self.experiment_count}",
            f"sessions: {self.sessions_exported}/{self.sessions_seen}",
        ]
        if self.rejected:
            lines.append(f"rejected crops: {self.rejected}")
        if self.skipped_duplicates:
            lines.append(f"already exported (skipped): {self.skipped_duplicates}")
        for problem in self.problems:
            lines.append(f"WARNING {problem}")
        if self.dry_run:
            lines.append("dry-run: nothing written")
        else:
            lines.append(f"output: {self.archive}")
        return "\n".join(lines)


def _confirmed_sessions(root: Path, experiment_id: str | None) -> list[dict[str, Any]]:
    """Confirmed (revision >= 1) sessions, newest last. Reads metadata only."""
    sessions_dir = root / "sessions"
    if not sessions_dir.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for metadata_path in sorted(sessions_dir.glob("*/metadata.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(metadata, dict):
            continue
        if metadata.get("consent") is not True or metadata.get("status") != "confirmed":
            continue
        if not isinstance(metadata.get("revision"), int) or metadata["revision"] < 1:
            continue
        if not metadata.get("fields"):
            continue
        if experiment_id and metadata.get("experiment_id") != experiment_id:
            continue
        found.append(metadata)
    return found


def export_dataset(
    output: Path | None = None,
    *,
    collection_root: Path | None = None,
    experiment_id: str | None = None,
    dry_run: bool = False,
    charset_path: Path | None = None,
    template_root: Path | None = None,
    denoise: bool = False,
) -> ExportOutcome:
    """Build every confirmed session into a staging dataset and zip it."""
    from app.data_collection import LocalFileStorage, collection_root as default_root

    root = Path(collection_root) if collection_root is not None else default_root()
    storage = LocalFileStorage(root)
    sessions = _confirmed_sessions(root, experiment_id)
    archive = Path(output) if output is not None else Path.cwd() / DEFAULT_ZIP_NAME

    staging_parent = Path(tempfile.mkdtemp(prefix="physlab_ocr_export_"))
    staging = staging_parent / DEFAULT_EXPORT_NAME
    outcome = ExportOutcome(
        archive=archive, sample_count=0, experiment_count=0, sessions_seen=len(sessions), dry_run=dry_run,
    )
    try:
        for metadata in sessions:
            session_id = str(metadata.get("session_id", ""))
            try:
                result = build_session_dataset(
                    session_id, storage=storage, output_dir=staging, charset_path=charset_path,
                    template_root=template_root, denoise=denoise,
                )
            except (BuilderError, FileNotFoundError, ValueError, OSError) as exc:
                outcome.problems.append(f"{session_id[:8]}: {exc}")
                continue
            outcome.sessions_exported += 1
            outcome.sample_count += result.samples_created
            outcome.rejected += len(result.rejected)
            outcome.skipped_duplicates += result.skipped_duplicates

        # labels.csv is the training contract (image,text only), so the per
        # experiment breakdown comes from the dataset index next to it.
        labels = staging / LABELS_FILENAME
        if labels.is_file():
            with labels.open("r", encoding="utf-8", newline="") as handle:
                outcome.sample_count = sum(1 for _ in csv.DictReader(handle))
        index = staging / SAMPLES_FILENAME
        if index.is_file():
            with index.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    key = str(row.get("experiment_id") or "unknown")
                    outcome.experiments[key] = outcome.experiments.get(key, 0) + 1
        outcome.experiment_count = len(outcome.experiments)

        outcome.problems.extend(verify_export(staging) if staging.is_dir() else ["no dataset built"])

        if not dry_run:
            _write_archive(staging, archive, outcome)
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)
    return outcome


def _write_archive(staging: Path, archive: Path, outcome: ExportOutcome) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": EXPORT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment_count": outcome.experiment_count,
        "sample_count": outcome.sample_count,
        "experiments": outcome.experiments,
        "sessions_exported": outcome.sessions_exported,
        "compatible_with": "Bogger111/PhysLab_OCR (datasets/sequencedatasets.py: image,text)",
        "contents": [f"{ARCHIVE_ROOT}/{LABELS_FILENAME}", f"{ARCHIVE_ROOT}/images/", f"{ARCHIVE_ROOT}/{MANIFEST_FILENAME}"],
    }
    manifest_path = staging / MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    temporary = archive.with_suffix(archive.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(manifest_path, f"{ARCHIVE_ROOT}/{MANIFEST_FILENAME}")
        bundle.write(staging / LABELS_FILENAME, f"{ARCHIVE_ROOT}/{LABELS_FILENAME}")
        for image in sorted((staging / "images").glob("*.png")):
            bundle.write(image, f"{ARCHIVE_ROOT}/images/{image.name}")
    temporary.replace(archive)


def extract_dataset(archive: Path, destination: Path) -> Path:
    """Unpack an archive into `<destination>/`, returning the dataset directory.

    The result is meant to be copied straight to `PhysLab_OCR/data/`.
    """
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.namelist():
            if member.startswith("/") or ".." in Path(member).parts:
                raise ValueError(f"unsafe archive member: {member}")
        bundle.extractall(destination)
    return destination / ARCHIVE_ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None,
                        help=f"archive path (default: ./{DEFAULT_ZIP_NAME})")
    parser.add_argument("--collection-root", type=Path, default=None)
    parser.add_argument("--experiment", dest="experiment_id", default=None)
    parser.add_argument("--template-root", type=Path, default=None)
    parser.add_argument("--charset-config", type=Path, default=None)
    parser.add_argument("--denoise", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    outcome = export_dataset(
        args.output, collection_root=args.collection_root, experiment_id=args.experiment_id,
        dry_run=args.dry_run, charset_path=args.charset_config, template_root=args.template_root,
        denoise=args.denoise,
    )
    print(outcome.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
