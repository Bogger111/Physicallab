"""Training-crop quality gates and configurable label charset."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class QualityDecision:
    disposition: str
    reasons: tuple[str, ...]
    score: float


def load_charset(path: Path | None = None) -> tuple[str, str]:
    config_path = path or Path(__file__).with_name("charset.json")
    value = json.loads(config_path.read_text(encoding="utf-8"))
    characters = value.get("characters")
    if not isinstance(characters, str) or not characters:
        raise ValueError("OCR charset config is empty")
    return characters, str(value.get("version", "unknown"))


def validate_label(text: str, charset: str) -> tuple[str, ...]:
    if text == "":
        return ("empty_label",)
    if any(character not in charset for character in text):
        return ("illegal_charset",)
    return ()


def evaluate_crop(
    image: np.ndarray | None,
    *,
    label: str,
    charset: str,
    segmentation_confidence: float,
    touches_roi_border: bool,
    segmentation_notes: tuple[str, ...] = (),
) -> QualityDecision:
    reject = list(validate_label(label, charset))
    review: list[str] = list(segmentation_notes)
    if image is None or image.size == 0:
        reject.append("missing_crop")
        return QualityDecision("reject", tuple(dict.fromkeys(reject)), 0.0)
    height, width = image.shape[:2]
    if width < 12 or height < 12 or width * height < 240:
        reject.append("extremely_small_crop")
    mean = float(np.mean(image))
    standard_deviation = float(np.std(image))
    dark_ratio = float(np.mean(image < 210))
    if mean < 18 or dark_ratio > 0.96:
        reject.append("suspiciously_dark_crop")
    if mean > 252.5 or standard_deviation < 2.0 or dark_ratio < 0.002:
        reject.append("blank_or_white_crop")
    if touches_roi_border:
        review.append("ink_touches_roi_border")
    if segmentation_confidence < 0.55:
        review.append("low_segmentation_confidence")
    score = 1.0
    score -= min(0.35, abs(mean - 215.0) / 500.0)
    score -= min(0.25, max(0.0, 0.01 - dark_ratio) * 10.0)
    score -= max(0.0, 0.75 - segmentation_confidence) * 0.5
    score -= 0.12 if touches_roi_border else 0.0
    score = round(max(0.0, min(1.0, score)), 4)
    if reject:
        return QualityDecision("reject", tuple(dict.fromkeys(reject)), score)
    if review:
        return QualityDecision("review", tuple(dict.fromkeys(review)), score)
    return QualityDecision("accept", (), score)
