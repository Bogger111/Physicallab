"""Contribution statistics and sample estimates for the data-collection loop.

Reads only `metadata.json` files and the dataset `samples.csv`: counting sessions
never touches images, so the numbers stay cheap to produce on any deployment.

Access to the statistics endpoint is deliberately restricted.  Two switches:

* ``PHYSICSLAB_ADMIN_KEY`` — when set, callers must send the same value in the
  ``X-Admin-Key`` header (constant-time comparison).  This is what production
  should use, and a configured key always wins over development mode.
* ``PHYSICSLAB_DEV_MODE=true`` — local development only; statistics are readable
  without a key.  Default off, so a fresh deployment exposes nothing.
"""

from __future__ import annotations

import csv
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAMPLE_COLUMNS = ("image", "text", "field_id", "session_id", "experiment_id", "revision",
                  "source_image", "segmentation_method", "quality_score", "sample_key", "notes")


def dev_mode() -> bool:
    return os.getenv("PHYSICSLAB_DEV_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


def admin_key() -> str | None:
    configured = os.getenv("PHYSICSLAB_ADMIN_KEY", "").strip()
    return configured or None


def stats_allowed(provided_key: str | None) -> bool:
    """A configured admin key always wins; otherwise development mode allows it."""
    configured = admin_key()
    if configured:
        return provided_key is not None and secrets.compare_digest(provided_key, configured)
    return dev_mode()


def experiment_name(experiment_id: str) -> str:
    """Human-readable experiment name for the contribution card.

    `catalog_entry()["name"]` is the authoritative display name (it also covers
    experiments whose config is a list of methods, e.g. sound-light).
    """
    try:
        from experiments.core.registry import registry

        entry = registry.get(experiment_id).catalog_entry()
        name = entry.get("name") if isinstance(entry, dict) else None
        if name:
            return str(name)
    except Exception:  # unknown/legacy ids still deserve a label
        pass
    return experiment_id


# ------------------------------------------------------------------ estimates

def estimate_samples(experiment_id: str, fields: dict[str, Any] | None = None) -> int:
    """Samples this session can produce, without running segmentation.

    With ``fields`` this mirrors the builder's admission rules (the value must be
    a non-empty label the OCR charset can encode and the field must have a
    template cell).  Without ``fields`` it is the upper bound: every cell of the
    record sheet that the template knows about.
    """
    import sys

    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    try:
        from ocr_dataset.quality import load_charset, validate_label
        from ocr_dataset.templates import load_template
    except ImportError:  # pragma: no cover - dataset tooling unavailable
        return 0

    try:
        template = load_template(experiment_id)
    except (FileNotFoundError, ValueError):
        return 0
    cell_ids = {str(cell["field_id"]) for cell in template["cells"]}
    if fields is None:
        return len(cell_ids)

    characters, _ = load_charset()
    count = 0
    for field_id, value in fields.items():
        if field_id not in cell_ids or value is None:
            continue
        label = str(value).strip()
        if not label or validate_label(label, characters):
            continue
        count += 1
    return count


# ------------------------------------------------------------------ statistics

def _session_summaries(root: Path) -> list[dict[str, Any]]:
    """One entry per session directory; archived revision snapshots are ignored."""
    sessions_dir = root / "sessions"
    if not sessions_dir.is_dir():
        return []
    summaries: list[dict[str, Any]] = []
    for metadata_path in sorted(sessions_dir.glob("*/metadata.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(metadata, dict):
            continue
        summaries.append({
            "session_id": str(metadata.get("session_id", metadata_path.parent.name)),
            "experiment_id": str(metadata.get("experiment_id", "")),
            "status": str(metadata.get("status", "")),
            "revision": metadata.get("revision") if isinstance(metadata.get("revision"), int) else 0,
            "fields": len(metadata.get("fields") or {}) if isinstance(metadata.get("fields"), dict) else 0,
            "consent": metadata.get("consent") is True,
            "collection_mode": metadata.get("collection_mode") is True,
        })
    return summaries


def _dataset_counts(dataset_dir: Path) -> tuple[int, dict[str, int], dict[str, int]]:
    """Sample counts from `samples.csv` — the dataset index, never the images."""
    samples = dataset_dir / "samples.csv"
    if not samples.is_file():
        return 0, {}, {}
    total = 0
    by_experiment: dict[str, int] = {}
    by_session: dict[str, int] = {}
    with samples.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            total += 1
            experiment = str(row.get("experiment_id") or "unknown")
            by_experiment[experiment] = by_experiment.get(experiment, 0) + 1
            session = str(row.get("session_id") or "unknown")
            by_session[session] = by_session.get(session, 0) + 1
    return total, by_experiment, by_session


def collection_stats(root: Path) -> dict[str, Any]:
    """Overview for the developer dashboard."""
    sessions = _session_summaries(root)
    confirmed = [item for item in sessions if item["status"] == "confirmed" and item["revision"] >= 1]
    dataset_dir = root / "datasets" / "ocr_export"
    samples_created, samples_by_experiment, samples_by_session = _dataset_counts(dataset_dir)

    # An experiment is listed when it has sessions or exported samples.
    experiments = dict(samples_by_experiment)
    for item in sessions:
        experiments.setdefault(item["experiment_id"] or "unknown", 0)

    sessions_by_experiment: dict[str, int] = {}
    confirmed_by_experiment: dict[str, int] = {}
    for item in sessions:
        key = item["experiment_id"] or "unknown"
        sessions_by_experiment[key] = sessions_by_experiment.get(key, 0) + 1
    for item in confirmed:
        key = item["experiment_id"] or "unknown"
        confirmed_by_experiment[key] = confirmed_by_experiment.get(key, 0) + 1

    contributions = [item for item in sessions if item["collection_mode"]]
    contribution_confirmed = [item for item in contributions if item["status"] == "confirmed" and item["revision"] >= 1]
    return {
        "total_sessions": len(sessions),
        "confirmed_sessions": len(confirmed),
        # AI co-build figures: ordinary experiment sessions are not contributions.
        "collection_sessions": len(contributions),
        "collection_confirmed_sessions": len(contribution_confirmed),
        "plain_sessions": len(sessions) - len(contributions),
        "consented_sessions": sum(1 for item in sessions if item["consent"]),
        "samples_created": samples_created,
        "experiments": experiments,
        "sessions_by_experiment": sessions_by_experiment,
        "confirmed_by_experiment": confirmed_by_experiment,
        "sessions_awaiting_values": len(sessions) - len(confirmed),
        "dataset": {
            "export": dataset_dir.name,
            "index": "samples.csv",
            "labeled_samples": samples_created,
            "image_files": len(list((dataset_dir / "images").glob("*.png")))
            if (dataset_dir / "images").is_dir() else 0,
            "sessions_in_dataset": len(samples_by_session),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
