"""Optional, consent-first collection of original laboratory record sheets.

This module is deliberately separate from calculation and reporting.  A
storage failure must never affect validation, processing, or report creation.
The collected image is the full user-provided record sheet.  Dividing it into
training cells happens offline in ``ocr_dataset`` (see
``ocr_dataset.builder``), which reads sessions through this module's storage
interface and writes the derived dataset outside the repository.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_COLLECTION_IMAGE_BYTES = 12 * 1024 * 1024
MAX_COLLECTION_IMAGE_PIXELS = 40_000_000
TEMPLATE_VERSION = "2.0"
ALLOWED_IMAGE_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff",
}


class CollectionValidationError(ValueError):
    """The submitted collection payload is not safe or schema-compatible."""


class CollectionNotFoundError(FileNotFoundError):
    """The requested collection session does not exist."""


def collection_enabled() -> bool:
    return os.getenv("ENABLE_DATA_COLLECTION", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def collection_root() -> Path:
    configured = os.getenv("PHYSICSLAB_COLLECTION_ROOT", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data_collection"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_session_id(value: str) -> str:
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise CollectionValidationError("无效的数据贡献会话") from exc
    if str(parsed) != value:
        raise CollectionValidationError("无效的数据贡献会话")
    return value


def validate_template_version(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", value or ""):
        raise CollectionValidationError("模板版本格式无效")
    return value


def sanitize_record_image(content: bytes) -> bytes:
    """Decode and re-encode to JPEG, removing EXIF and embedded metadata."""
    if not content:
        raise CollectionValidationError("没有收到记录表图片")
    if len(content) > MAX_COLLECTION_IMAGE_BYTES:
        raise CollectionValidationError("记录表图片不能超过 12 MB")
    try:
        with Image.open(io.BytesIO(content)) as source:
            source.verify()
        with Image.open(io.BytesIO(content)) as source:
            if source.width * source.height > MAX_COLLECTION_IMAGE_PIXELS:
                raise CollectionValidationError("记录表图片像素尺寸过大")
            image = ImageOps.exif_transpose(source).convert("RGB")
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
    except CollectionValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise CollectionValidationError("无法读取记录表图片") from exc
    return output.getvalue()


_NUMERIC_TEXT = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def _numeric(value: Any) -> int | float | str | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise CollectionValidationError("确认数据必须是有限数字")
    if isinstance(value, str) and not _NUMERIC_TEXT.fullmatch(value):
        raise CollectionValidationError("确认数据必须是有限数字")
    number = float(value)
    if not math.isfinite(number):
        raise CollectionValidationError("确认数据不得包含 NaN 或 Inf")
    return value


def _method_specs(experiment_id: str) -> tuple[dict[str, dict[str, set[str]]], set[str]]:
    """Return stable schema keys derived from the canonical experiment config."""
    if experiment_id == "polarization":
        config_path = Path(__file__).resolve().parents[1] / "experiments" / "polarization" / "config.json"
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        from experiments.schema import enrich_polarization_config
        config = enrich_polarization_config(raw)
        methods = config.get("subExperiments", [])
        specs = {
            method["id"]: {
                "rows": {field["key"] for field in method.get("fields", [])},
                "params": set(),
                "initial": ({"c_deg", "c_min", "p2_deg", "p2_min"}
                            if method["id"] == "halfwave" else set()),
            }
            for method in methods
        }
        return specs, {field["key"] for field in config.get("setupFields", [])}

    if experiment_id == "sound-light":
        config_path = Path(__file__).resolve().parents[1] / "experiments" / "soundlight" / "config.json"
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        from experiments.schema import enrich_soundlight_config
        methods = enrich_soundlight_config(raw)
        specs = {
            method["id"]: {
                "rows": {field["key"] for field in method.get("fields", [])},
                "params": {field["key"] for field in method.get("params", [])},
                "initial": set(),
            }
            for method in methods
        }
        return specs, set()

    from experiments.core.exceptions import UnknownExperimentError
    from experiments.core.registry import registry
    try:
        config = registry.get(experiment_id).config
    except UnknownExperimentError:
        raise CollectionValidationError("实验不存在或未公开")
    specs = {
        method["id"]: {
            "rows": {field["key"] for field in method.get("columns", [])},
            "params": {field["key"] for field in method.get("params", [])},
            "initial": set(),
        }
        for method in config.get("methods", [])
    }
    return specs, set()


def _store_value(fields: dict[str, int | float | str], field_id: str, value: Any) -> None:
    number = _numeric(value)
    if number is not None:
        fields[field_id] = number


def normalize_confirmed_fields(experiment_id: str, data: dict[str, Any]) -> dict[str, int | float | str]:
    """Flatten report data to semantic field IDs independent of DOM ordering."""
    if not isinstance(data, dict):
        raise CollectionValidationError("确认数据必须是对象")
    specs, setup_fields = _method_specs(experiment_id)
    fields: dict[str, int | float | str] = {}

    for key, value in data.items():
        if key in setup_fields:
            _store_value(fields, f"setup.{key}", value)
            continue
        if key not in specs:
            raise CollectionValidationError(f"未知实验字段：{key}")
        if value is None:
            continue
        if not isinstance(value, dict):
            raise CollectionValidationError(f"{key} 数据必须是对象")
        allowed_sections = {"rows", "params", "initial"}
        unknown_sections = set(value) - allowed_sections
        if unknown_sections:
            raise CollectionValidationError(f"{key} 包含未知字段：{sorted(unknown_sections)[0]}")
        spec = specs[key]

        params = value.get("params") or {}
        if not isinstance(params, dict):
            raise CollectionValidationError(f"{key}.params 必须是对象")
        for param_key, param_value in params.items():
            if param_key not in spec["params"]:
                raise CollectionValidationError(f"未知实验字段：{key}.params.{param_key}")
            _store_value(fields, f"{key}.params.{param_key}", param_value)

        initial = value.get("initial") or {}
        if not isinstance(initial, dict):
            raise CollectionValidationError(f"{key}.initial 必须是对象")
        for initial_key, initial_value in initial.items():
            if initial_key not in spec["initial"]:
                raise CollectionValidationError(f"未知实验字段：{key}.initial.{initial_key}")
            _store_value(fields, f"{key}.initial.{initial_key}", initial_value)

        rows = value.get("rows") or []
        if experiment_id == "sound-light":
            if not isinstance(rows, dict):
                raise CollectionValidationError(f"{key}.rows 必须是列数组对象")
            for column_key, values in rows.items():
                if column_key not in spec["rows"]:
                    raise CollectionValidationError(f"未知实验字段：{key}.rows.{column_key}")
                if not isinstance(values, list):
                    raise CollectionValidationError(f"{key}.rows.{column_key} 必须是数组")
                for index, row_value in enumerate(values, start=1):
                    _store_value(fields, f"{key}.rows.row_{index:02d}.{column_key}", row_value)
        else:
            if not isinstance(rows, list):
                raise CollectionValidationError(f"{key}.rows 必须是数组")
            for index, row in enumerate(rows, start=1):
                if not isinstance(row, dict):
                    raise CollectionValidationError(f"{key}.rows 第 {index} 行必须是对象")
                for column_key, row_value in row.items():
                    if column_key not in spec["rows"]:
                        raise CollectionValidationError(f"未知实验字段：{key}.rows.{column_key}")
                    _store_value(fields, f"{key}.rows.row_{index:02d}.{column_key}", row_value)
    return fields


def valid_stable_field_id(experiment_id: str, field_id: str) -> bool:
    """Validate an already flattened label against the current config schema."""
    specs, setup_fields = _method_specs(experiment_id)
    if field_id.startswith("setup."):
        return field_id.removeprefix("setup.") in setup_fields
    parts = field_id.split(".")
    if len(parts) == 3 and parts[0] in specs and parts[1] in {"params", "initial"}:
        return parts[2] in specs[parts[0]][parts[1]]
    if len(parts) == 4 and parts[0] in specs and parts[1] == "rows":
        return bool(re.fullmatch(r"row_[0-9]{2,}", parts[2])) and parts[3] in specs[parts[0]]["rows"]
    return False


@dataclass(frozen=True)
class SessionRecord:
    """One stored collection session, read back without knowing the backend."""

    session_id: str
    experiment_id: str
    template_version: str
    revision: int
    consent: bool
    status: str
    fields: dict[str, Any]
    image_bytes: bytes
    image_ref: str
    metadata: dict[str, Any]
    collection_mode: bool = False


class CollectionStorage(ABC):
    """Storage boundary: local files for development, object storage in production.

    A production deployment supplies an implementation backed by a private
    bucket; nothing in this interface assumes a local filesystem.
    """

    @abstractmethod
    def create_session(self, *, experiment_id: str, template_version: str, image: bytes,
                       collection_mode: bool = False) -> dict[str, Any]:
        """Store one uploaded record sheet.

        ``collection_mode`` records whether the contributor entered through the
        AI co-build入口; only such sessions become OCR training data.
        """
        raise NotImplementedError

    @abstractmethod
    def commit_session(self, *, session_id: str, experiment_id: str,
                       template_version: str, fields: dict[str, int | float | str]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def load_session(self, session_id: str) -> SessionRecord:
        """Read one session (metadata + raw image bytes) for dataset building."""
        raise NotImplementedError

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def dataset_root(self) -> Any:
        """Base location for derived datasets (never inside the repository)."""
        raise NotImplementedError


class LocalFileStorage(CollectionStorage):
    """Filesystem implementation using UUID directories and atomic metadata writes.

    Layout mirrors the production object-store prefix one to one::

        <root>/sessions/<uuid>/raw.jpg
        <root>/sessions/<uuid>/metadata.json
        <root>/datasets/<export>/images/*.png
        <root>/datasets/<export>/labels.csv
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or collection_root()

    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_dir / _canonical_session_id(session_id)

    def _raw_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "raw.jpg"

    def _metadata_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "metadata.json"

    def _image_ref(self, session_id: str) -> str:
        return f"sessions/{session_id}/raw.jpg"

    def dataset_root(self) -> Path:
        return self.root / "datasets"

    def dataset_dir(self, name: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,60}", name or ""):
            raise CollectionValidationError("数据集目录名无效")
        return self.dataset_root() / name

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def create_session(self, *, experiment_id: str, template_version: str, image: bytes,
                       collection_mode: bool = False) -> dict[str, Any]:
        session_id = str(uuid4())
        directory = self.session_dir(session_id)
        directory.mkdir(parents=True, exist_ok=True)
        raw_path = self._raw_path(session_id)
        temporary_raw_path = directory / "raw.jpg.tmp"
        metadata_path = self._metadata_path(session_id)
        try:
            temporary_raw_path.write_bytes(image)
            temporary_raw_path.replace(raw_path)
            now = _now()
            metadata: dict[str, Any] = {
                "session_id": session_id,
                "experiment_id": experiment_id,
                "template_version": template_version,
                "collection_mode": bool(collection_mode),
                "consent": True,
                "status": "pending_confirmation",
                "revision": 0,
                "created_at": now,
                "confirmed_at": None,
                "updated_at": now,
                "image_path": self._image_ref(session_id),
                "fields": {},
            }
            self._write_json(metadata_path, metadata)
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        return metadata

    def commit_session(self, *, session_id: str, experiment_id: str,
                       template_version: str, fields: dict[str, int | float | str]) -> dict[str, Any]:
        if not fields:
            raise CollectionValidationError("没有可保存的最终确认数值")
        path = self._metadata_path(session_id)
        if not path.is_file():
            raise CollectionNotFoundError("数据贡献会话不存在")
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if metadata.get("experiment_id") != experiment_id:
            raise CollectionValidationError("实验与数据贡献会话不一致")
        if metadata.get("template_version") != template_version:
            raise CollectionValidationError("模板版本与数据贡献会话不一致")
        if metadata.get("consent") is not True:
            raise CollectionValidationError("该会话没有有效授权")
        if not self._raw_path(session_id).is_file():
            raise CollectionNotFoundError("原始记录表图片不存在")
        now = _now()
        metadata.update({
            "status": "confirmed",
            "revision": int(metadata.get("revision", 0)) + 1,
            "confirmed_at": now,
            "updated_at": now,
            "fields": fields,
        })
        self._write_json(path, metadata)
        return metadata

    def load_session(self, session_id: str) -> SessionRecord:
        canonical = _canonical_session_id(session_id)
        path = self._metadata_path(canonical)
        if not path.is_file():
            raise CollectionNotFoundError("数据贡献会话不存在")
        metadata = json.loads(path.read_text(encoding="utf-8"))
        image_ref = str(metadata.get("image_path", ""))
        image_path = self.root / image_ref if image_ref else Path()
        if image_ref != self._image_ref(canonical) or not image_path.is_file():
            raise CollectionNotFoundError("原始记录表图片不存在")
        fields = metadata.get("fields")
        return SessionRecord(
            session_id=canonical,
            experiment_id=str(metadata.get("experiment_id", "")),
            template_version=str(metadata.get("template_version", "")),
            revision=int(metadata.get("revision", 0)) if isinstance(metadata.get("revision"), int) else 0,
            consent=metadata.get("consent") is True,
            status=str(metadata.get("status", "")),
            fields=dict(fields) if isinstance(fields, dict) else {},
            image_bytes=image_path.read_bytes(),
            image_ref=image_ref,
            metadata=metadata,
            collection_mode=metadata.get("collection_mode") is True,
        )

    def delete_session(self, session_id: str) -> None:
        """Withdraw one contribution: session bytes *and* its dataset samples."""
        directory = self.session_dir(session_id)
        if not directory.exists():
            raise CollectionNotFoundError("数据贡献会话不存在")
        shutil.rmtree(directory, ignore_errors=False)
        purge_dataset_session(self.dataset_root(), session_id)


#: Backwards-compatible alias: the class was called LocalCollectionStorage.
LocalCollectionStorage = LocalFileStorage


def purge_dataset_session(dataset_root: Path, session_id: str) -> dict[str, int]:
    """Drop every exported sample that came from one session.

    A withdrawal has to leave no training trace: the crop images, the
    `samples.csv` rows, the `rejected.csv` rows and the manifest counts are all
    updated here. Session directories are not touched.
    """
    dataset_root = Path(dataset_root)
    removed_images = 0
    removed_samples = 0
    removed_rejections = 0
    if not dataset_root.is_dir():
        return {"images": 0, "samples": 0, "rejections": 0}

    for export_dir in sorted(path for path in dataset_root.iterdir() if path.is_dir()):
        samples_path = export_dir / "samples.csv"
        rows: list[dict[str, str]] = []
        kept: list[dict[str, str]] = []
        if samples_path.is_file():
            with samples_path.open("r", encoding="utf-8", newline="") as handle:
                rows = [dict(row) for row in csv.DictReader(handle)]
            kept = [row for row in rows if row.get("session_id") != session_id]
            removed_samples += len(rows) - len(kept)
            for row in rows:
                if row.get("session_id") != session_id:
                    continue
                image = str(row.get("image", ""))
                path = export_dir / "images" / image
                if image and path.is_file():
                    path.unlink()
                    removed_images += 1
            if rows != kept:
                _write_rows(samples_path, kept, SAMPLE_COLUMNS)

        labels_path = export_dir / "labels.csv"
        if labels_path.is_file() and rows:
            with labels_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(["image", "text"])
                for row in kept:
                    writer.writerow([row.get("image", ""), row.get("text", "")])

        rejected_path = export_dir / "rejected.csv"
        if rejected_path.is_file():
            with rejected_path.open("r", encoding="utf-8", newline="") as handle:
                rejected = [dict(row) for row in csv.DictReader(handle)]
            remaining = [row for row in rejected if row.get("session_id") != session_id]
            removed_rejections += len(rejected) - len(remaining)
            if len(remaining) != len(rejected):
                _write_rows(rejected_path, remaining, list(rejected[0].keys()) if rejected else [])

        manifest_path = export_dir / "manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = None
            if isinstance(manifest, dict) and isinstance(manifest.get("dataset"), dict):
                manifest["dataset"]["samples"] = len(kept)
                manifest["dataset"]["images"] = len(list((export_dir / "images").glob("*.png")))
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"images": removed_images, "samples": removed_samples, "rejections": removed_rejections}


def _write_rows(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    fields = columns or (list(rows[0].keys()) if rows else [])
    if not fields:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fields})


SAMPLE_COLUMNS = ["image", "text", "field_id", "session_id", "experiment_id", "revision",
                  "source_image", "segmentation_method", "quality_score", "sample_key", "notes"]


def local_storage() -> LocalFileStorage:
    """The development/production-default implementation of CollectionStorage.

    Local files for now; a bucket-backed implementation simply replaces this
    accessor, since every caller goes through the interface.
    """
    return LocalFileStorage(collection_root())
