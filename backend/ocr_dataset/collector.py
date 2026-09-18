"""Read and validate final consented collection sessions."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.data_collection import valid_stable_field_id


FORBIDDEN_KEYS = {
    "name", "student_id", "studentid", "phone", "telephone", "wechat",
    "email", "contact", "id_number", "identity", "account", "ip",
    "ip_address", "user_agent", "browser_fingerprint", "headers",
}


@dataclass(frozen=True)
class CollectionCandidate:
    session_id: str
    experiment_id: str
    revision: int
    source_image: Path
    source_image_ref: str
    fields: dict[str, str]
    template_version: str


@dataclass(frozen=True)
class CollectionReject:
    session_id: str
    experiment_id: str
    revision: int | None
    source_image: str
    field_id: str
    reason: str
    disposition: str = "reject"


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        if any(str(key).strip().lower() in FORBIDDEN_KEYS for key in value):
            return True
        return any(_contains_forbidden_key(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_key(child) for child in value)
    return False


def _session_id(value: Any) -> str:
    text = str(value)
    if str(UUID(text)) != text:
        raise ValueError("invalid_session_id")
    return text


def _label(value: Any) -> str:
    """Preserve committed strings exactly; stringify legacy numeric values."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("invalid_label_type")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non_finite_label")
    return value if isinstance(value, str) else str(value)


def _reject(metadata: dict[str, Any], reason: str, *, source: str = "") -> CollectionReject:
    return CollectionReject(
        session_id=str(metadata.get("session_id", "")),
        experiment_id=str(metadata.get("experiment_id", "")),
        revision=metadata.get("revision") if isinstance(metadata.get("revision"), int) else None,
        source_image=source,
        field_id="",
        reason=reason,
    )


def collect_sessions(
    root: Path,
    *,
    experiment_id: str | None = None,
    session_id: str | None = None,
) -> tuple[list[CollectionCandidate], list[CollectionReject]]:
    """Return one latest valid record per session and explicit reject reasons.

    ``rglob`` intentionally supports archived revision snapshots.  Duplicate
    metadata for the same session is resolved by revision, never file order.
    """
    sessions_dir = root / "sessions"
    selected: dict[str, tuple[int, CollectionCandidate]] = {}
    rejects: list[CollectionReject] = []
    paths = sorted(sessions_dir.rglob("metadata.json")) if sessions_dir.is_dir() else []
    for path in paths:
        metadata: dict[str, Any] = {}
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
            sid = _session_id(metadata.get("session_id"))
            exp_id = str(metadata.get("experiment_id", ""))
            if experiment_id and exp_id != experiment_id:
                continue
            if session_id and sid != session_id:
                continue
            if metadata.get("consent") is not True:
                rejects.append(_reject(metadata, "consent_not_explicit"))
                continue
            if metadata.get("status") != "confirmed":
                rejects.append(_reject(metadata, "not_finally_committed"))
                continue
            revision = metadata.get("revision")
            if not isinstance(revision, int) or revision < 1:
                rejects.append(_reject(metadata, "invalid_revision"))
                continue
            if _contains_forbidden_key(metadata) or metadata.get("deidentified") is False:
                rejects.append(_reject(metadata, "personal_information_not_removed"))
                continue
            image_ref = str(metadata.get("image_path", ""))
            expected = f"sessions/{sid}/raw.jpg"
            if image_ref != expected:
                rejects.append(_reject(metadata, "invalid_source_image_reference", source=image_ref))
                continue
            source = root / image_ref
            if not source.is_file():
                rejects.append(_reject(metadata, "missing_source_image", source=image_ref))
                continue
            fields = metadata.get("fields")
            if not isinstance(fields, dict) or not fields:
                rejects.append(_reject(metadata, "missing_final_fields", source=image_ref))
                continue
            labels: dict[str, str] = {}
            for field_id, value in fields.items():
                key = str(field_id)
                if not valid_stable_field_id(exp_id, key):
                    rejects.append(CollectionReject(
                        sid, exp_id, revision, image_ref, key, "invalid_field_mapping"
                    ))
                    continue
                labels[key] = _label(value)
            if not labels:
                continue
            candidate = CollectionCandidate(
                sid, exp_id, revision, source, image_ref, labels,
                str(metadata.get("template_version", "")),
            )
            previous = selected.get(sid)
            if previous is None or revision > previous[0]:
                selected[sid] = (revision, candidate)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            reason = str(exc) if str(exc) else "invalid_metadata"
            rejects.append(_reject(metadata, reason))
    return [item[1] for item in sorted(selected.values(), key=lambda item: item[1].session_id)], rejects
