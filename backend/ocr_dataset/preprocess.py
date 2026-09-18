"""Conservative record-sheet rectification without aggressive binarization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class PreprocessedPage:
    image: np.ndarray
    confidence: float
    method: str
    source_size: tuple[int, int]
    corners: tuple[tuple[float, float], ...]


def grayscale_from_image(source: Image.Image, *, denoise: bool = False) -> np.ndarray:
    """EXIF-corrected grayscale array from an already decoded image."""
    oriented = ImageOps.exif_transpose(source).convert("L")
    image = np.asarray(oriented).copy()
    if denoise:
        image = cv2.fastNlMeansDenoising(image, None, 5, 7, 21)
    return image


def load_grayscale(path: Path, *, denoise: bool = False) -> np.ndarray:
    with Image.open(path) as source:
        return grayscale_from_image(source, denoise=denoise)


def preprocess_content(
    content: bytes,
    reference_size: tuple[int, int],
    *,
    denoise: bool = False,
) -> PreprocessedPage:
    """Same pipeline as ``preprocess_page`` but from in-memory bytes.

    Collection storage hands out bytes (local file or downloaded object), so the
    dataset builder never needs a path on disk.
    """
    import io

    with Image.open(io.BytesIO(content)) as source:
        image = grayscale_from_image(source, denoise=denoise)
    return _page_from_grayscale(image, reference_size)


def _order_corners(points: np.ndarray) -> np.ndarray:
    points = points.astype(np.float32)
    total = points.sum(axis=1)
    diff = np.diff(points, axis=1).reshape(-1)
    return np.array([
        points[np.argmin(total)], points[np.argmin(diff)],
        points[np.argmax(total)], points[np.argmax(diff)],
    ], dtype=np.float32)


def detect_page_boundary(image: np.ndarray) -> tuple[np.ndarray | None, float]:
    height, width = image.shape[:2]
    scale = min(1.0, 1600.0 / max(height, width))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    blurred = cv2.GaussianBlur(small, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    page_area = float(small.shape[0] * small.shape[1])
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:20]:
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        area_ratio = cv2.contourArea(contour) / page_area
        if len(polygon) == 4 and area_ratio >= 0.35:
            points = polygon.reshape(4, 2) / scale
            return _order_corners(points), min(0.99, 0.65 + area_ratio * 0.3)
    return None, 0.0


def perspective_correct(
    image: np.ndarray,
    corners: np.ndarray,
    reference_size: tuple[int, int],
) -> np.ndarray:
    width, height = reference_size
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(_order_corners(corners), target)
    return cv2.warpPerspective(image, matrix, (width, height), flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)


def _page_from_grayscale(image: np.ndarray, reference_size: tuple[int, int]) -> PreprocessedPage:
    height, width = image.shape
    corners, confidence = detect_page_boundary(image)
    if corners is not None:
        corrected = perspective_correct(image, corners, reference_size)
        return PreprocessedPage(
            corrected, confidence, "page_quadrilateral", (width, height),
            tuple((float(x), float(y)) for x, y in corners),
        )
    target_width, target_height = reference_size
    corrected = cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)
    source_ratio = width / max(height, 1)
    target_ratio = target_width / max(target_height, 1)
    ratio_error = abs(source_ratio - target_ratio) / max(target_ratio, 1e-6)
    fallback_confidence = 0.60 if ratio_error <= 0.08 else 0.35
    full = ((0.0, 0.0), (float(width - 1), 0.0),
            (float(width - 1), float(height - 1)), (0.0, float(height - 1)))
    return PreprocessedPage(corrected, fallback_confidence, "full_frame_resize", (width, height), full)


def preprocess_page(
    path: Path,
    reference_size: tuple[int, int],
    *,
    denoise: bool = False,
) -> PreprocessedPage:
    return _page_from_grayscale(load_grayscale(path, denoise=denoise), reference_size)
