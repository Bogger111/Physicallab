"""Experiment-layout ROI segmentation with a conservative OpenCV fallback.

Two paths exist, in this order:

1. **Template registration + calibrated ROI.**  ``layouts/<experiment_id>.json``
   carries the exact rectangle of every handwriting cell of the record sheet
   this repository renders (see :mod:`ocr_dataset.calibrate`).  Before any of
   those rectangles is trusted, :func:`register_page` verifies that the uploaded
   page really is that template page: the printed table lines detected on the
   uploaded image must line up with the template's table frames.  If they do not
   line up, nothing is guessed and every field is rejected.
2. **OpenCV grid fallback.**  When an experiment has no calibrated ROIs, or the
   upload is a single table rather than a whole page, the grid is detected
   generically and mapped to a table signature.  The mapping is accepted only
   when the detected grid matches one signature uniquely.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .preprocess import PreprocessedPage


#: Every detected printed line must be explained by the template before its
#: calibrated ROIs may be used: a cropped, rescaled or rotated page leaves lines
#: the template cannot account for.
REGISTRATION_RECALL = 0.8
#: At least this share of the template's own lines must be visible on the page.
REGISTRATION_PRECISION = 0.3
#: How much better the upright template must explain the grid than the 180°
#: rotated one; below this the orientation is not trustworthy.
REGISTRATION_ORIENTATION_MARGIN = 0.05
#: Line-matching tolerance as a fraction of the page dimension.
REGISTRATION_TOLERANCE = 0.006


@dataclass(frozen=True)
class CropResult:
    image: np.ndarray | None
    method: str
    confidence: float
    touches_roi_border: bool
    reason: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Registration:
    """Whether an upload may be trusted with the calibrated template coordinates."""

    registered: bool
    score: float
    coverage: float
    coverage_mirrored: float
    detail: str = ""

    def __bool__(self) -> bool:  # pragma: no cover - convenience only
        return self.registered


@dataclass(frozen=True)
class Segmenter:
    """Crop a preprocessed page once registration has been decided."""

    page: PreprocessedPage
    layout: dict[str, Any]
    registration: Registration

    def crop(self, field_id: str) -> CropResult:
        field_spec = self.layout.get("fields", {}).get(field_id)
        if isinstance(field_spec, dict):
            if not self.registration.registered:
                return CropResult(
                    None, "template_roi", 0.0, False,
                    self.registration.detail or "page_not_registered",
                    (f"registration_score:{self.registration.score:.2f}",
                     f"grid_coverage:{self.registration.coverage:.2f}"),
                )
            return crop_template_roi(self.page, field_spec)
        return _fallback_crop(self.page, self.layout, field_id)


def layouts_root() -> Path:
    return Path(__file__).with_name("layouts")


def load_layout(experiment_id: str, root: Path | None = None) -> dict[str, Any]:
    path = (root or layouts_root()) / f"{experiment_id}.json"
    layout = json.loads(path.read_text(encoding="utf-8"))
    if layout.get("experiment_id") != experiment_id:
        raise ValueError(f"layout experiment mismatch: {path}")
    reference = layout.get("reference_size")
    if not (isinstance(reference, list) and len(reference) == 2 and all(isinstance(v, int) and v > 0 for v in reference)):
        raise ValueError(f"invalid reference_size: {path}")
    if not isinstance(layout.get("fields", {}), dict):
        raise ValueError(f"invalid fields: {path}")
    return layout


def _relative_box(spec: dict[str, Any], shape: tuple[int, int]) -> tuple[int, int, int, int]:
    height, width = shape
    values = [float(spec[name]) for name in ("x1", "y1", "x2", "y2")]
    if not (0 <= values[0] < values[2] <= 1 and 0 <= values[1] < values[3] <= 1):
        raise ValueError("invalid_relative_roi")
    return (
        int(round(values[0] * width)), int(round(values[1] * height)),
        int(round(values[2] * width)), int(round(values[3] * height)),
    )


def _remove_table_lines(image: np.ndarray) -> np.ndarray:
    """Inpaint only long straight rules; keep thin curved handwriting."""
    if min(image.shape[:2]) < 18:
        return image
    binary = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 31, 12)
    horizontal_size = max(12, image.shape[1] // 3)
    vertical_size = max(12, image.shape[0] // 2)
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                                  cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_size, 1)))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_size)))
    mask = cv2.dilate(cv2.bitwise_or(horizontal, vertical), np.ones((2, 2), np.uint8))
    if float(np.mean(mask > 0)) > 0.25:
        return image
    return cv2.inpaint(image, mask, 2, cv2.INPAINT_TELEA)


def _ink_mask(image: np.ndarray, *, sensitivity: float = 8.0, ceiling: float = 225.0) -> np.ndarray:
    """Pixels darker than the local paper level.

    Detecting *any* ink uses a loose threshold; deciding whether handwriting is
    clipped by the cell border uses a strict one, because faint residue from the
    inpainted table rules sits right where the printed line used to be.
    """
    return image < min(ceiling, float(np.mean(image)) - sensitivity)


def _border_contact(image: np.ndarray) -> bool:
    """True when strong ink reaches the very edge of the cell crop."""
    if min(image.shape[:2]) < 4:
        return True
    ink = _ink_mask(image, sensitivity=40.0, ceiling=200.0)
    border_width = max(1, min(image.shape[:2]) // 24)
    ring = np.zeros_like(ink, dtype=bool)
    ring[:border_width, :] = ring[-border_width:, :] = True
    ring[:, :border_width] = ring[:, -border_width:] = True
    total_ink = int(np.count_nonzero(ink))
    if total_ink == 0:
        return False
    return np.count_nonzero(ink & ring) / total_ink > 0.22


def _box_gap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    dx = max(0, max(a[0], b[0]) - min(a[0] + a[2], b[0] + b[2]))
    dy = max(0, max(a[1], b[1]) - min(a[1] + a[3], b[1] + b[3]))
    return max(dx, dy)


def _significant_ink(image: np.ndarray) -> tuple[np.ndarray, tuple[str, ...]]:
    """Ink of one cell, with speckle and rule residue dropped, plus review notes.

    Inpainting the printed rules leaves a few pixels behind near the cell edge.
    Those specks are tiny *and* far from any real stroke, which is what
    distinguishes them from a decimal point inside a written value.  Components
    that survive but sit far apart are reported for human review instead of
    being silently merged into one label crop.
    """
    ink = _ink_mask(image)
    # The outermost ring is where the removed rules sit.
    ink[0, :] = ink[-1, :] = False
    ink[:, 0] = ink[:, -1] = False
    if int(np.count_nonzero(ink)) < max(12, int(0.004 * ink.size)):
        return np.zeros_like(ink, dtype=bool), ()
    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), connectivity=8)
    if count <= 2:
        return ink, ()
    boxes = {index: tuple(int(v) for v in stats[index, :4]) for index in range(1, count)}
    areas = {index: int(stats[index, cv2.CC_STAT_AREA]) for index in range(1, count)}
    widest = max(box[2] for box in boxes.values())
    area_floor = max(16, 0.15 * max(areas.values()))
    significant = {index for index, area in areas.items() if area >= area_floor}
    if not significant:
        return np.zeros_like(ink, dtype=bool), ()
    threshold = max(3, int(0.6 * widest))
    keep = {index: boxes[index] for index in significant}
    # A speck is kept only when it really belongs to a stroke: JPEG ringing along
    # the removed rules also produces isolated one-pixel components, and two
    # adjacent specks must not count as neighbours of each other.
    for index, box in boxes.items():
        if index in significant:
            continue
        if any(_box_gap(box, boxes[other]) <= threshold for other in significant):
            keep[index] = box
    if not keep:
        return np.zeros_like(ink, dtype=bool), ()
    ordered = sorted(keep.values(), key=lambda box: box[0])
    largest_gap = max(
        (current[0] - (previous[0] + previous[2]) for previous, current in zip(ordered, ordered[1:])),
        default=0,
    )
    notes = ("detached_ink_mark",) if largest_gap > 1.2 * widest else ()
    return np.isin(labels, list(keep)), notes


def _tighten_ink(image: np.ndarray) -> tuple[np.ndarray, tuple[str, ...]]:
    """Shrink a cell crop onto the handwritten value, keeping a safety margin.

    A training sample should hold one handwritten number rather than the whole
    cell, but a crop that cuts strokes is worse than a generous one, so the
    bounding box keeps a margin and is left alone when no ink is trustworthy.
    """
    if image.size == 0:
        return image, ()
    ink, notes = _significant_ink(image)
    if not np.any(ink):
        return image, notes
    rows = np.nonzero(ink.any(axis=1))[0]
    columns = np.nonzero(ink.any(axis=0))[0]
    y1, y2 = int(rows[0]), int(rows[-1]) + 1
    x1, x2 = int(columns[0]), int(columns[-1]) + 1
    pad_x = max(2, int(round((x2 - x1) * 0.08)))
    pad_y = max(2, int(round((y2 - y1) * 0.15)))
    height, width = image.shape[:2]
    x1, x2 = max(0, x1 - pad_x), min(width, x2 + pad_x)
    y1, y2 = max(0, y1 - pad_y), min(height, y2 + pad_y)
    if x2 - x1 < 8 or y2 - y1 < 6:
        return image, notes
    return image[y1:y2, x1:x2].copy(), notes


def _crop_cell(
    image: np.ndarray,
    box: tuple[int, int, int, int],
    *,
    padding_ratio: float = 0.035,
    tighten: bool = True,
) -> tuple[np.ndarray, bool, tuple[str, ...]] | None:
    """Crop one cell, drop the printed rules, and optionally tighten onto the ink.

    Padding is used only as context for rule removal: the padding band is where
    the printed table rules live, so the analysis and the exported PNG stay
    inside the cell itself and rule residue cannot masquerade as handwriting.
    """
    x1, y1, x2, y2 = box
    height, width = image.shape[:2]
    pad_x = max(2, int((x2 - x1) * padding_ratio))
    pad_y = max(2, int((y2 - y1) * padding_ratio))
    px1, py1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
    px2, py2 = min(width, x2 + pad_x), min(height, y2 + pad_y)
    padded = image[py1:py2, px1:px2].copy()
    if padded.size == 0:
        return None
    cleaned = _remove_table_lines(padded)
    inner = cleaned[y1 - py1:y1 - py1 + (y2 - y1), x1 - px1:x1 - px1 + (x2 - x1)].copy()
    if inner.size == 0:
        return None
    contact = _border_contact(inner)
    notes: tuple[str, ...] = ()
    if tighten:
        inner, notes = _tighten_ink(inner)
    return inner, contact, notes


def crop_template_roi(
    page: PreprocessedPage,
    field_spec: dict[str, Any],
    *,
    padding_ratio: float = 0.035,
    tighten: bool = True,
) -> CropResult:
    try:
        box = _relative_box(field_spec, page.image.shape[:2])
    except (KeyError, TypeError, ValueError) as exc:
        return CropResult(None, "template_roi", 0.0, False, str(exc))
    result = _crop_cell(page.image, box, padding_ratio=padding_ratio, tighten=tighten)
    if result is None:
        return CropResult(None, "template_roi", 0.0, False, "empty_template_roi")
    crop, contact, notes = result
    confidence = min(float(field_spec.get("confidence", 1.0)), page.confidence)
    return CropResult(crop, "template_roi", confidence, contact, notes=notes)


def grid_lines(image: np.ndarray) -> tuple[list[int], list[int]]:
    """Printed table line positions (x, y) from ink projections.

    ``detect_table_cells`` is fine for locating cells to crop, but its contour
    boxes carry a systematic offset of about one morphological kernel, which is
    far too coarse to *verify* whether an upload matches the calibrated
    template.  Projecting long horizontal/vertical runs onto the axes gives
    unbiased line centres to compare against the template lattice.
    """
    height, width = image.shape[:2]
    binary = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 31, 11)
    horizontal = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, width // 20), 1)),
    )
    vertical = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, height // 20))),
    )
    return _profile_lines(vertical.sum(axis=0)), _profile_lines(horizontal.sum(axis=1))


def _profile_lines(profile: np.ndarray, *, min_ratio: float = 0.25, min_abs: float = 12.0) -> list[int]:
    """Centres of the runs in a line-strength profile (ink pixels per row/column)."""
    if profile.size == 0:
        return []
    peak = float(profile.max())
    if peak <= 0:
        return []
    active = np.asarray(profile) >= max(min_abs, min_ratio * peak)
    lines: list[int] = []
    start: int | None = None
    for index, flag in enumerate(active):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            lines.append((start + index - 1) // 2)
            start = None
    if start is not None:
        lines.append((start + len(active) - 1) // 2)
    return lines


def detect_table_cells(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Find a rectangular table grid using morphology and intersections."""
    threshold = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                      cv2.THRESH_BINARY_INV, 31, 11)
    horizontal = cv2.morphologyEx(
        threshold, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, image.shape[1] // 20), 1)),
    )
    vertical = cv2.morphologyEx(
        threshold, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, image.shape[0] // 20))),
    )
    grid = cv2.bitwise_or(horizontal, vertical)
    grid = cv2.morphologyEx(grid, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    minimum_area = max(80, image.shape[0] * image.shape[1] // 12000)
    boxes: list[tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width * height < minimum_area or width > image.shape[1] * 0.98 or height > image.shape[0] * 0.98:
            continue
        if width < 10 or height < 10:
            continue
        boxes.append((x, y, x + width, y + height))
    boxes.sort(key=lambda box: (box[1], box[0]))
    return boxes


def _lattice_scores(
    detected_x: list[int],
    detected_y: list[int],
    expected_x: list[float],
    expected_y: list[float],
    tolerance: tuple[float, float],
) -> tuple[float, float]:
    """(precision, recall) of the template lattice against the detected lines."""
    tol_x, tol_y = tolerance

    def axis(expected: list[float], detected: list[int], tol: float) -> tuple[float, float]:
        if not expected or not detected:
            return 0.0, 0.0
        precision = sum(any(abs(value - line) <= tol for line in detected) for value in expected) / len(expected)
        recall = sum(any(abs(line - value) <= tol for value in expected) for line in detected) / len(detected)
        return precision, recall

    px, rx = axis(expected_x, detected_x, tol_x)
    py, ry = axis(expected_y, detected_y, tol_y)
    return (px + py) / 2, min(rx, ry)


def _expected_lines(layout: dict[str, Any], width: int, height: int, *, mirrored: bool) -> tuple[list[float], list[float]]:
    lattice = layout.get("lattice") or {}
    xs = [value * width for value in lattice.get("x", [])]
    ys = [value * height for value in lattice.get("y", [])]
    if mirrored:
        xs = [width - value for value in xs]
        ys = [height - value for value in ys]
    return xs, ys


def register_page(page: PreprocessedPage, layout: dict[str, Any]) -> Registration:
    """Check that the upload really is the calibrated page, the right way up.

    The template lattice is compared with the printed lines detected on the
    upload.  A cropped, rescaled, shifted or empty page produces lines the
    template cannot explain, and an upside-down page is explained better by the
    180°-rotated template than by the upright one.  Both cases are rejected:
    a cell whose field is uncertain must never reach the training set.
    """
    if not (layout.get("lattice") or {}).get("x") or not layout.get("anchors"):
        return Registration(False, 0.0, 0.0, 0.0, "layout_not_calibrated")
    detected_x, detected_y = grid_lines(page.image)
    if not detected_x or not detected_y:
        return Registration(False, 0.0, 0.0, 0.0, "no_printed_grid_found")
    height, width = page.image.shape[:2]
    tolerance = (max(4.0, width * REGISTRATION_TOLERANCE), max(4.0, height * REGISTRATION_TOLERANCE))
    expected_x, expected_y = _expected_lines(layout, width, height, mirrored=False)
    score, coverage = _lattice_scores(detected_x, detected_y, expected_x, expected_y, tolerance)
    mirror_x, mirror_y = _expected_lines(layout, width, height, mirrored=True)
    _, mirrored_coverage = _lattice_scores(detected_x, detected_y, mirror_x, mirror_y, tolerance)
    if coverage < REGISTRATION_RECALL or score < REGISTRATION_PRECISION:
        return Registration(False, score, coverage, mirrored_coverage, "grid_mismatch")
    if coverage <= mirrored_coverage + REGISTRATION_ORIENTATION_MARGIN:
        detail = ("page_upside_down" if mirrored_coverage > coverage
                  else "page_orientation_ambiguous")
        return Registration(False, score, coverage, mirrored_coverage, detail)
    return Registration(True, score, coverage, mirrored_coverage, "template_registered")


def segmenter_for(page: PreprocessedPage, layout: dict[str, Any]) -> Segmenter:
    return Segmenter(page, layout, register_page(page, layout))


def _cluster_rows(boxes: list[tuple[int, int, int, int]]) -> list[list[tuple[int, int, int, int]]]:
    rows: list[list[tuple[int, int, int, int]]] = []
    for box in boxes:
        center_y = (box[1] + box[3]) / 2
        for row in rows:
            reference = sum((item[1] + item[3]) / 2 for item in row) / len(row)
            tolerance = max(5.0, np.median([item[3] - item[1] for item in row]) * 0.45)
            if abs(center_y - reference) <= tolerance:
                row.append(box)
                break
        else:
            rows.append([box])
    for row in rows:
        row.sort(key=lambda box: box[0])
    return rows


def _field_grid(table: dict[str, Any]) -> list[list[str | None]]:
    explicit = table.get("field_grid")
    if isinstance(explicit, list) and explicit:
        return explicit
    method_id = table.get("method_id")
    section = table.get("section", "rows")
    columns = table.get("columns")
    row_count = table.get("row_count")
    if not isinstance(method_id, str) or not isinstance(columns, list) or not columns:
        return []
    if not isinstance(row_count, int) or row_count < 1:
        return []
    grid: list[list[str | None]] = [[None for _ in columns]] if table.get("header", True) else []
    if section == "rows":
        for row_index in range(1, row_count + 1):
            grid.append([f"{method_id}.rows.row_{row_index:02d}.{column}" for column in columns])
    elif section in {"params", "initial"} and row_count == 1:
        grid.append([f"{method_id}.{section}.{column}" for column in columns])
    return grid


def _fallback_crop(page: PreprocessedPage, layout: dict[str, Any], field_id: str) -> CropResult:
    rows = _cluster_rows(detect_table_cells(page.image))
    candidates: list[tuple[tuple[int, int, int, int], float]] = []
    for table in layout.get("tables", []):
        mapping = _field_grid(table)
        if not mapping or len(rows) != len(mapping):
            continue
        if any(len(detected) != len(expected) for detected, expected in zip(rows, mapping)):
            continue
        for row_index, expected_row in enumerate(mapping):
            for column_index, expected_field_id in enumerate(expected_row):
                if expected_field_id == field_id:
                    candidates.append((rows[row_index][column_index], float(table.get("confidence", 0.62))))
    if len(candidates) != 1:
        reason = "missing_field_mapping" if not candidates else "ambiguous_field_mapping"
        return CropResult(None, "opencv_grid_fallback", 0.0, False, reason)
    x1, y1, x2, y2 = candidates[0][0]
    inset_x, inset_y = max(1, (x2 - x1) // 30), max(1, (y2 - y1) // 20)
    box = (x1 + inset_x, y1 + inset_y, x2 - inset_x, y2 - inset_y)
    result = _crop_cell(page.image, box, padding_ratio=0.0)
    if result is None:
        return CropResult(None, "opencv_grid_fallback", 0.0, False, "empty_fallback_roi")
    crop, contact, notes = result
    return CropResult(crop, "opencv_grid_fallback",
                      min(page.confidence, candidates[0][1]), contact, notes=notes)


def segment_field(page: PreprocessedPage, layout: dict[str, Any], field_id: str) -> CropResult:
    """Crop one field; registration is computed on demand for a single call."""
    return segmenter_for(page, layout).crop(field_id)
