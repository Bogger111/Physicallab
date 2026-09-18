"""Calibration and registration regression tests.

These tests render the real record sheets this repository ships and use them as
synthetic uploads: no real user data is involved, but the field mapping,
perspective correction, registration, orientation check and quality gates are
exercised end to end through JPEG round-trips, exactly as the collection store
does.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
import pymupdf
import pytest

from app.data_collection import valid_stable_field_id
from ocr_dataset.build import build_dataset
from ocr_dataset.calibrate import (
    REFERENCE_SIZE,
    _render_blocks,
    capture_tables,
    record_sheet_blocks,
)
from ocr_dataset.preprocess import PreprocessedPage, preprocess_page
from ocr_dataset.segment import load_layout, register_page, segment_field, segmenter_for

EXPERIMENTS = ("multimeter", "sound-light", "polarization")
#: A page photographed at an angle on a desk, as a student would submit it.
PHOTO_CORNERS = [[150, 110], [1760, 210], [1700, 2470], [110, 2350]]


@functools.lru_cache(maxsize=8)
def rendered_pdf(experiment_id: str) -> bytes:
    from experiments.core.registry import registry

    experiment = registry.get(experiment_id)
    blocks = record_sheet_blocks(experiment)
    pdf, _, _ = capture_tables(_render_blocks(experiment, blocks))
    return pdf


@functools.lru_cache(maxsize=8)
def rendered_page(experiment_id: str) -> np.ndarray:
    from ocr_dataset.calibrate import render_page_image

    return render_page_image(rendered_pdf(experiment_id))


def photo(image: np.ndarray, corners=PHOTO_CORNERS, canvas: tuple[int, int] = (2620, 1960),
          desk: int = 120) -> np.ndarray:
    """Page on a darker desk, with sensor noise, so the paper edge is usable."""
    rows, cols = canvas
    source = np.array([[0, 0], [image.shape[1] - 1, 0],
                       [image.shape[1] - 1, image.shape[0] - 1], [0, image.shape[0] - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(source, np.asarray(corners, dtype=np.float32))
    canvas_image = np.full((rows, cols), desk, dtype=np.uint8)
    warped = cv2.warpPerspective(image, matrix, (cols, rows), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=desk)
    mask = cv2.warpPerspective(np.full_like(image, 255), matrix, (cols, rows),
                               flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    canvas_image[mask > 0] = warped[mask > 0]
    noise = np.random.default_rng(7).normal(0, 3.0, canvas_image.shape)
    return np.clip(canvas_image.astype(np.float64) + noise, 0, 255).astype(np.uint8)


def page_of(experiment_id: str, image: np.ndarray, confidence: float = 0.9) -> PreprocessedPage:
    return PreprocessedPage(image, confidence, "test", REFERENCE_SIZE, ((0, 0),) * 4)


def field_box(layout: dict, field_id: str) -> tuple[int, int, int, int]:
    spec = layout["fields"][field_id]
    return (int(spec["x1"] * REFERENCE_SIZE[0]), int(spec["y1"] * REFERENCE_SIZE[1]),
            int(spec["x2"] * REFERENCE_SIZE[0]), int(spec["y2"] * REFERENCE_SIZE[1]))


def write_ink(image: np.ndarray, box: tuple[int, int, int, int], text: str) -> None:
    x1, y1, x2, y2 = box
    scale = max(0.4, (y2 - y1) / 46.0)
    thickness = max(1, int(round(scale * 1.6)))
    (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    origin = (x1 + max(4, (x2 - x1 - text_width) // 2), y1 + (y2 - y1 + text_height) // 2)
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, 30, thickness, cv2.LINE_AA)


def make_collection(root: Path, experiment_id: str, image: np.ndarray, fields: dict[str, str],
                    *, revision: int = 1, collection_mode: bool = True) -> str:
    session_id = str(uuid4())
    session_dir = root / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(session_dir / "raw.jpg"), image,
                [int(cv2.IMWRITE_JPEG_QUALITY), 94])
    (session_dir / "metadata.json").write_text(json.dumps({
        "session_id": session_id, "experiment_id": experiment_id, "template_version": "2.0",
        "consent": True, "status": "confirmed", "revision": revision,
        "collection_mode": collection_mode,
        "created_at": "2026-01-01T00:00:00+00:00", "confirmed_at": "2026-01-01T00:01:00+00:00",
        "updated_at": "2026-01-01T00:01:00+00:00",
        "image_path": f"sessions/{session_id}/raw.jpg", "fields": fields,
    }, ensure_ascii=False), encoding="utf-8")
    return session_id


# ------------------------------------------------------------------ calibration

def test_every_public_experiment_has_a_calibrated_layout():
    from experiments.core.registry import PUBLIC_EXPERIMENT_IDS

    for experiment_id in PUBLIC_EXPERIMENT_IDS:
        layout = load_layout(experiment_id)
        assert layout["reference_size"] == list(REFERENCE_SIZE)
        assert layout["fields"], f"{experiment_id} has no calibrated ROI"
        assert layout["anchors"], f"{experiment_id} has no registration anchors"
        assert layout["lattice"]["x"] and layout["lattice"]["y"]
        assert layout["source"]["raster_match_ratio"] > 0.8
        for field_id, spec in layout["fields"].items():
            assert valid_stable_field_id(experiment_id, field_id), field_id
            assert 0 <= spec["x1"] < spec["x2"] <= 1 and 0 <= spec["y1"] < spec["y2"] <= 1


def test_cell_rectangle_matches_the_rendered_pdf_text():
    """Guard the coordinate convention: row 0 must be the visual top row."""
    from experiments.core.registry import registry

    experiment = registry.get("multimeter")
    blocks = record_sheet_blocks(experiment)
    pdf, captured, page_size = capture_tables(_render_blocks(experiment, blocks))
    from ocr_dataset.calibrate import measure_offset, render_page_image

    offset, residual, _, _ = measure_offset(captured, page_size, render_page_image(pdf))
    assert residual > 0.9
    table = captured[0]
    header = table.cell_px(0, 0, REFERENCE_SIZE, page_size, offset)
    body = table.cell_px(1, 0, REFERENCE_SIZE, page_size, offset)

    document = pymupdf.open(stream=pdf, filetype="pdf")
    page = document[0]
    hit = page.search_for("U设")[0]
    centre_y = (hit.y0 + hit.y1) / 2 * REFERENCE_SIZE[1] / page.rect.height
    assert header[1] <= centre_y <= header[3]
    assert not body[1] <= centre_y <= body[3]


def test_calibrated_rois_land_on_printed_cells_of_the_rendered_sheet():
    """Every ROI must sit exactly on a cell of the rendered template."""
    from ocr_dataset.preprocess import PreprocessedPage
    from ocr_dataset.segment import grid_lines

    layout = load_layout("multimeter")
    image = rendered_page("multimeter")
    detected_x, detected_y = grid_lines(image)
    height, width = image.shape[:2]
    tolerance_x, tolerance_y = width * 0.006, height * 0.006
    for field_id, spec in layout["fields"].items():
        for value in (spec["x1"] * width, spec["x2"] * width):
            assert any(abs(value - line) <= tolerance_x for line in detected_x), field_id
        for value in (spec["y1"] * height, spec["y2"] * height):
            assert any(abs(value - line) <= tolerance_y for line in detected_y), field_id


def test_calibrated_fields_never_land_on_prefilled_cells():
    """Cells the blank sheet already prints are not handwriting targets."""
    from experiments.core.registry import registry

    for experiment_id in ("multimeter", "nmr", "viscosity"):
        experiment = registry.get(experiment_id)
        prefilled = {
            f"{method['id']}.rows.row_{row:02d}.{key}"
            for method in experiment.config["methods"]
            for key, values in (method.get("prefill") or {}).items()
            for row in range(1, min(len(values), method["rowCount"]) + 1)
        }
        assert not (set(load_layout(experiment_id)["fields"]) & prefilled), experiment_id


# ------------------------------------------------------------------ registration

@pytest.mark.parametrize("experiment_id", EXPERIMENTS)
def test_registration_accepts_a_photographed_sheet(tmp_path, experiment_id):
    layout = load_layout(experiment_id)
    path = tmp_path / "photo.jpg"
    cv2.imwrite(str(path), photo(rendered_page(experiment_id)),
                [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    page = preprocess_page(path, tuple(layout["reference_size"]))
    assert page.method == "page_quadrilateral"
    registration = register_page(page, layout)
    assert registration.registered, registration
    assert registration.coverage >= 0.8


@pytest.mark.parametrize("experiment_id", EXPERIMENTS)
def test_registration_rejects_pages_that_are_not_this_template(experiment_id):
    layout = load_layout(experiment_id)
    image = rendered_page(experiment_id)
    wrong = {
        # upside down: the mirrored lattice explains the grid better
        "upside_down": cv2.rotate(image, cv2.ROTATE_180),
        # only part of the sheet was photographed or cropped
        "cropped": cv2.resize(np.ascontiguousarray(image[1100:, :]), (image.shape[1], image.shape[0])),
        # content moved inside the frame
        "shifted": np.roll(image, 60, axis=1),
        # the frame is not the sheet
        "padded": cv2.resize(cv2.copyMakeBorder(image, 40, 60, 50, 70, cv2.BORDER_CONSTANT, value=235),
                             REFERENCE_SIZE),
        "blank": np.full_like(image, 250),
    }
    for name, candidate in wrong.items():
        page = page_of(experiment_id, candidate)
        registration = register_page(page, layout)
        assert not registration.registered, f"{experiment_id}/{name} was registered: {registration}"


def test_unregistered_page_is_rejected_instead_of_guessed(tmp_path):
    layout = load_layout("multimeter")
    field_id = "voltage.rows.row_01.measured"
    image = rendered_page("multimeter")
    write_ink(image, field_box(layout, field_id), "1.234")
    cropped = np.ascontiguousarray(image[1100:, :])
    root = tmp_path / "collection"
    make_collection(root, "multimeter", cv2.resize(cropped, REFERENCE_SIZE), {field_id: "1.234"})

    result, _, _ = build_dataset(root)
    assert not result.accepted
    assert result.registration_failures == 1
    assert all(item.disposition == "reject" for item in result.rejected)
    assert {reason for item in result.rejected for reason in item.reasons} <= {
        "grid_mismatch", "page_upside_down", "page_orientation_ambiguous",
        "no_printed_grid_found", "layout_not_calibrated",
    }


# ------------------------------------------------------------------ crops

@pytest.mark.parametrize("experiment_id", EXPERIMENTS)
def test_calibrated_crop_holds_only_the_handwritten_value(experiment_id):
    layout = load_layout(experiment_id)
    field_id = sorted(layout["fields"])[0]
    image = rendered_page(experiment_id)
    box = field_box(layout, field_id)
    write_ink(image, box, "22.090")
    result = segmenter_for(page_of(experiment_id, image), layout).crop(field_id)
    assert result.image is not None, result.reason
    assert result.method == "template_roi"
    assert result.image.shape[0] < box[3] - box[1] + 1
    assert result.image.shape[1] < box[2] - box[0] + 1
    assert int(result.image.min()) < 120


def test_perspective_corrected_photo_maps_to_the_same_field(tmp_path):
    layout = load_layout("multimeter")
    field_id = "voltage.rows.row_01.measured"
    image = rendered_page("multimeter")
    write_ink(image, field_box(layout, field_id), "1.234")
    path = tmp_path / "photo.jpg"
    cv2.imwrite(str(path), photo(image), [int(cv2.IMWRITE_JPEG_QUALITY), 92])

    page = preprocess_page(path, tuple(layout["reference_size"]))
    registration = register_page(page, layout)
    assert registration.registered, registration
    result = segmenter_for(page, layout).crop(field_id)
    assert result.image is not None, result.reason
    assert int(result.image.min()) < 120
    assert result.image.shape[0] < int(0.08 * REFERENCE_SIZE[1])
    assert result.image.shape[1] < int(0.5 * REFERENCE_SIZE[0])


def test_segmentation_without_calibration_reports_missing_mapping():
    layout = load_layout("michelson")
    field_id = sorted(layout["fields"])[0]
    empty = {**layout, "fields": {}, "anchors": [], "lattice": {}}
    result = segment_field(page_of("michelson", rendered_page("michelson")), empty, field_id)
    assert result.image is None
    assert result.reason == "missing_field_mapping"


# ------------------------------------------------------------------ pipeline

@pytest.mark.parametrize("experiment_id", EXPERIMENTS)
def test_committed_string_label_survives_the_whole_pipeline(tmp_path, experiment_id):
    layout = load_layout(experiment_id)
    field_ids = sorted(layout["fields"])[:3]
    image = rendered_page(experiment_id)
    labels = {field_id: "22.090" for field_id in field_ids}
    for field_id, text in labels.items():
        write_ink(image, field_box(layout, field_id), text)
    root = tmp_path / "collection"
    make_collection(root, experiment_id, image, labels)

    result, _, _ = build_dataset(root)
    assert len(result.accepted) == len(field_ids)
    assert {sample.text for sample in result.accepted} == {"22.090"}
    assert all(sample.segmentation_method == "template_roi" for sample in result.accepted)
    assert result.reason_counts == {}


def test_latest_revision_replaces_the_previous_export(tmp_path):
    layout = load_layout("multimeter")
    field_id = "voltage.rows.row_01.measured"
    image = rendered_page("multimeter")
    write_ink(image, field_box(layout, field_id), "1.100")
    root = tmp_path / "collection"
    session_id = make_collection(root, "multimeter", image, {field_id: "1.100"}, revision=1)
    metadata_path = root / "sessions" / session_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update({"revision": 2, "fields": {field_id: "9.900"}})
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

    result, _, _ = build_dataset(root)
    assert len(result.accepted) == 1
    assert result.accepted[0].revision == 2
    assert result.accepted[0].text == "9.900"
