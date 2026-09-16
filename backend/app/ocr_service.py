"""Table-photo OCR helpers.

The model is loaded lazily so the rest of PhysicsLab remains usable when the
optional OCR runtime is unavailable. OCR candidates are never treated as final
measurements: the browser presents them for review before filling the table.
"""

from __future__ import annotations

import re
import threading
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Protocol

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 12 * 1024 * 1024
_ENGINE: Any = None
_PROVIDER: "OCRProvider | None" = None
_ENGINE_LOCK = threading.Lock()
_PROVIDER_LOCK = threading.Lock()
_INFERENCE_LOCK = threading.Lock()


class OCRUnavailable(RuntimeError):
    """Raised when the optional model runtime is not installed."""


class InvalidOCRImage(ValueError):
    """Raised when an upload cannot be decoded as a supported image."""


class OCRProvider(Protocol):
    """Minimal provider contract; providers return RapidOCR-like attributes."""

    name: str
    model_version: str

    def recognize(self, image: np.ndarray) -> Any: ...


class RapidOCRProvider:
    name = "rapidocr"
    model_version = "RapidOCR-3.9.2/PP-OCRv6-small"

    def __init__(self) -> None:
        self.engine = _get_engine()

    def recognize(self, image: np.ndarray) -> Any:
        return self.engine(image)


class PaddleOCRProvider:
    """Optional PP-OCRv5 provider for handwriting-capable deployments.

    PaddleOCR is intentionally not a required dependency of the local/Cloudflare
    image.  Selecting it without installing PaddleOCR produces a clear 503 and
    leaves the RapidOCR path untouched.
    """

    name = "paddleocr"
    model_version = "PaddleOCR-PP-OCRv5"

    def __init__(self) -> None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:  # pragma: no cover - optional environment
            raise OCRUnavailable(
                "PaddleOCR provider 未安装；请安装 paddleocr 后重启后端"
            ) from exc
        self.engine = PaddleOCR(
            lang="ch", use_doc_orientation_classify=False,
            use_doc_unwarping=False, use_textline_orientation=True,
        )

    def recognize(self, image: np.ndarray) -> Any:
        return self.engine.predict(image)


@dataclass(frozen=True)
class NumericCandidate:
    raw_text: str
    value: str
    confidence: float
    bbox: list[list[float]]
    center_x: float
    center_y: float
    height: float


_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def normalize_numeric_text(text: str) -> str | None:
    """Extract one normalized number from common OCR confusions."""
    cleaned = (
        text.strip()
        .replace("，", ".")
        .replace("。", ".")
        .replace("O", "0")
        .replace("o", "0")
        .replace("I", "1")
        .replace("l", "1")
        .replace("−", "-")
        .replace("—", "-")
        .replace("×10^", "e")
        .replace("×10", "e")
    )
    match = _NUMBER.search(cleaned)
    if not match:
        return None
    value = match.group(0)
    try:
        numeric = float(value)
    except ValueError:
        return None
    if not np.isfinite(numeric):
        return None
    return value


def _get_engine():
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is not None:
            return _ENGINE
        try:
            from rapidocr import RapidOCR
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise OCRUnavailable(
                "OCR 模型尚未安装；请安装 rapidocr 与 onnxruntime 后重启后端"
            ) from exc
        ort.disable_telemetry_events()
        _ENGINE = RapidOCR(params={"Global.text_score": 0.35})
        return _ENGINE


def _get_provider() -> OCRProvider:
    global _PROVIDER
    if _PROVIDER is not None:
        return _PROVIDER
    provider_name = os.getenv("PHYSICSLAB_OCR_PROVIDER", "rapidocr").strip().lower()
    with _PROVIDER_LOCK:
        if _PROVIDER is not None:
            return _PROVIDER
        if provider_name == "paddleocr":
            _PROVIDER = PaddleOCRProvider()
        elif provider_name in {"rapidocr", "rapid"}:
            _PROVIDER = RapidOCRProvider()
        else:
            raise OCRUnavailable(f"未知 OCR provider：{provider_name}")
        return _PROVIDER


def decode_image(content: bytes) -> np.ndarray:
    if not content:
        raise InvalidOCRImage("图片内容为空")
    if len(content) > MAX_IMAGE_BYTES:
        raise InvalidOCRImage("图片不能超过 12 MB")
    try:
        with Image.open(BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            if image.width < 80 or image.height < 80:
                raise InvalidOCRImage("图片尺寸过小，请重新拍摄数据表区域")
            image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
            return np.asarray(image)
    except InvalidOCRImage:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidOCRImage("无法读取图片，请使用 JPG、PNG 或 WebP") from exc


def _candidate(raw_text: str, score: float, box: Any) -> NumericCandidate | None:
    value = normalize_numeric_text(raw_text)
    if value is None:
        return None
    points = [[float(p[0]), float(p[1])] for p in box]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return NumericCandidate(
        raw_text=raw_text,
        value=value,
        confidence=round(float(score), 4),
        bbox=points,
        center_x=sum(xs) / len(xs),
        center_y=sum(ys) / len(ys),
        height=max(ys) - min(ys),
    )


def sort_candidates(candidates: list[NumericCandidate]) -> list[NumericCandidate]:
    """Group detections into visual rows, then order left-to-right."""
    rows: list[list[NumericCandidate]] = []
    for item in sorted(candidates, key=lambda c: (c.center_y, c.center_x)):
        target: list[NumericCandidate] | None = None
        for row in rows:
            mean_y = sum(candidate.center_y for candidate in row) / len(row)
            tolerance = max(10.0, max(candidate.height for candidate in row + [item]) * 0.65)
            if abs(item.center_y - mean_y) <= tolerance:
                target = row
                break
        if target is None:
            rows.append([item])
        else:
            target.append(item)
    rows.sort(key=lambda row: sum(item.center_y for item in row) / len(row))
    return [item for row in rows for item in sorted(row, key=lambda c: c.center_x)]


def recognize_numeric_candidates(content: bytes) -> dict[str, Any]:
    image = decode_image(content)
    # ONNX sessions are shared across requests; serialize table-sized inference
    # to cap memory use in the small Cloudflare container.
    with _INFERENCE_LOCK:
        provider = _get_provider()
        result = provider.recognize(image)
    boxes = getattr(result, "boxes", None)
    texts = getattr(result, "txts", None)
    scores = getattr(result, "scores", None)
    if boxes is None or texts is None or scores is None:
        return {"candidates": [], "detected_text_count": 0,
                "ocr_provider": provider.name,
                "ocr_model_version": provider.model_version}

    candidates = []
    for box, raw_text, score in zip(boxes, texts, scores):
        item = _candidate(str(raw_text), float(score), box)
        if item is not None:
            candidates.append(item)

    ordered = sort_candidates(candidates)
    return {
        "candidates": [
            {
                "raw_text": item.raw_text,
                "value": item.value,
                "confidence": item.confidence,
                "bbox": item.bbox,
            }
            for item in ordered
        ],
        "detected_text_count": len(texts),
        "ocr_provider": provider.name,
        "ocr_model_version": provider.model_version,
    }
