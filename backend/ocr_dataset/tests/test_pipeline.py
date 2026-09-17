from __future__ import annotations

import csv
import json
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image

from app.data_collection import normalize_confirmed_fields
from ocr_dataset.build import build_dataset, main
from ocr_dataset.collector import collect_sessions
from ocr_dataset.exporter import (
    AcceptedSample,
    deterministic_sample_id,
    export_dataset,
    write_contact_sheet,
)
from ocr_dataset.preprocess import PreprocessedPage, perspective_correct
from ocr_dataset.quality import evaluate_crop, validate_label
from ocr_dataset.segment import crop_template_roi, segment_field


FIELD_ID = "voltage.rows.row_01.measured"


def _sheet(path: Path, *, text: str = "22.090") -> None:
    """A tiny stand-in record sheet: two columns, asymmetric on purpose.

    The layout below is calibrated against exactly these printed lines, so the
    file also exercises registration (a symmetric grid would look the same the
    wrong way up and must not be trusted).
    """
    image = np.full((600, 800), 245, dtype=np.uint8)
    cv2.rectangle(image, (150, 230), (490, 370), 0, 3)
    cv2.line(image, (320, 230), (320, 370), 0, 3)
    cv2.putText(image, text, (352, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.85, 35, 2, cv2.LINE_AA)
    Image.fromarray(image).save(path, format="JPEG", quality=95)


def _layout(path: Path, *, mapped: bool = True) -> None:
    path.mkdir(parents=True, exist_ok=True)
    value = {
        "schema_version": "2.0",
        "experiment_id": "multimeter",
        "reference_size": [800, 600],
        "fields": {FIELD_ID: {"x1": .40, "y1": .38333, "x2": .6125, "y2": .61667,
                              "page": 1, "confidence": .9}} if mapped else {},
        "anchors": [[.1875, .38333, .6125, .61667]],
        "lattice": {"x": [.1875, .40, .6125], "y": [.38333, .61667]},
        "tables": [],
    }
    (path / "multimeter.json").write_text(json.dumps(value), encoding="utf-8")


def _metadata(root: Path, *, revision: int = 1, label: str = "22.090", subdir: str = "") -> str:
    session_id = str(uuid4())
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    _sheet(raw / f"{session_id}.jpg")
    metadata_dir = root / "metadata" / subdir
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "session_id": session_id,
        "experiment_id": "multimeter",
        "template_version": "2.0",
        "consent": True,
        "status": "confirmed",
        "revision": revision,
        "created_at": "2026-01-01T00:00:00+00:00",
        "confirmed_at": "2026-01-01T00:01:00+00:00",
        "updated_at": "2026-01-01T00:01:00+00:00",
        "image_path": f"raw/{session_id}.jpg",
        "fields": {FIELD_ID: label},
    }
    (metadata_dir / f"{session_id}.json").write_text(json.dumps(metadata), encoding="utf-8")
    return session_id


def test_confirmed_string_label_keeps_trailing_zeroes():
    fields = normalize_confirmed_fields(
        "multimeter",
        {"voltage": {"rows": [{"measured": "22.090"}], "params": {}}},
    )
    assert fields[FIELD_ID] == "22.090"


def test_template_roi_crop_contains_only_target_area():
    image = np.full((200, 300), 255, dtype=np.uint8)
    cv2.putText(image, "22.090", (95, 115), cv2.FONT_HERSHEY_SIMPLEX, .7, 0, 2)
    page = PreprocessedPage(image, .95, "test", (300, 200), ((0, 0),) * 4)
    result = crop_template_roi(page, {"x1": .28, "y1": .35, "x2": .76, "y2": .65})
    assert result.image is not None
    assert result.image.shape[0] < image.shape[0]
    assert result.image.shape[1] < image.shape[1]
    assert np.min(result.image) < 100
    # The crop is tightened onto the ink, so it is smaller than the cell itself.
    assert result.image.shape[1] < int(.52 * 300) and result.image.shape[0] < int(.35 * 200)


def test_perspective_corrected_crop_has_canonical_shape():
    image = np.full((260, 360), 255, dtype=np.uint8)
    cv2.putText(image, "7.50", (125, 145), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 0, 2)
    corners = np.array([[35, 20], [330, 35], [345, 235], [18, 245]], dtype=np.float32)
    corrected = perspective_correct(image, corners, (300, 200))
    assert corrected.shape == (200, 300)
    assert np.min(corrected) < 100


def test_invalid_blank_crop_is_rejected():
    decision = evaluate_crop(
        np.full((40, 100), 255, dtype=np.uint8), label="22.090",
        charset="0123456789.", segmentation_confidence=.95,
        touches_roi_border=False,
    )
    assert decision.disposition == "reject"
    assert "blank_or_white_crop" in decision.reasons


def test_deterministic_sample_id():
    one = deterministic_sample_id("session", FIELD_ID, 7)
    assert one == deterministic_sample_id("session", FIELD_ID, 7)
    assert one != deterministic_sample_id("session", FIELD_ID, 8)
    assert len(one) == 64


def test_collector_uses_latest_revision_only(tmp_path):
    root = tmp_path / "collection"
    session_id = _metadata(root, revision=1, label="22.090", subdir="old")
    original = json.loads((root / "metadata" / "old" / f"{session_id}.json").read_text())
    latest = {**original, "revision": 2, "fields": {FIELD_ID: "22.100"}}
    latest_dir = root / "metadata" / "latest"
    latest_dir.mkdir(parents=True)
    (latest_dir / f"{session_id}.json").write_text(json.dumps(latest), encoding="utf-8")
    sessions, _ = collect_sessions(root)
    assert len(sessions) == 1
    assert sessions[0].revision == 2
    assert sessions[0].fields[FIELD_ID] == "22.100"


def test_missing_field_mapping_is_rejected(tmp_path):
    root, layouts = tmp_path / "collection", tmp_path / "layouts"
    _metadata(root)
    _layout(layouts, mapped=False)
    result, _, _ = build_dataset(root, layouts_dir=layouts)
    assert not result.accepted
    assert any("missing_field_mapping" in item.reasons for item in result.rejected)


def test_illegal_charset_is_rejected_before_segmentation(tmp_path):
    root, layouts = tmp_path / "collection", tmp_path / "layouts"
    _metadata(root, label="-22.090")
    _layout(layouts)
    result, _, _ = build_dataset(root, layouts_dir=layouts)
    assert not result.accepted
    assert any("illegal_charset" in item.reasons for item in result.rejected)
    assert validate_label("22.090", "0123456789.") == ()


def test_duplicate_session_sample_is_not_duplicated(tmp_path):
    root = tmp_path / "collection"
    session_id = _metadata(root, subdir="a")
    duplicate_dir = root / "metadata" / "b"
    duplicate_dir.mkdir(parents=True)
    source = root / "metadata" / "a" / f"{session_id}.json"
    (duplicate_dir / f"{session_id}.json").write_bytes(source.read_bytes())
    sessions, _ = collect_sessions(root)
    assert [item.session_id for item in sessions] == [session_id]


def test_contact_sheet_and_csv_generation(tmp_path):
    sample = AcceptedSample(
        deterministic_sample_id("s", "f", 1),
        np.full((45, 120), 210, dtype=np.uint8), "22.090", "multimeter",
        FIELD_ID, "s", "raw/s.jpg", 1, "template_roi", .91,
    )
    sheet = tmp_path / "contact.png"
    write_contact_sheet([sample], sheet)
    assert sheet.is_file() and sheet.stat().st_size > 0

    from ocr_dataset.exporter import BuildResult
    output = tmp_path / "dataset"
    export_dataset(BuildResult(accepted=[sample], sessions_seen=1), output,
                   charset="0123456789.", charset_version="test")
    with (output / "labels.csv").open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["text"] == "22.090"
    assert not any(path.suffix.lower() in {".jpg", ".jpeg"} for path in output.rglob("*"))
    assert json.loads((output / "manifest.json").read_text())["privacy"]["contains_full_source_pages"] is False


def test_end_to_end_build_and_dry_run_writes_nothing(tmp_path):
    root, layouts = tmp_path / "collection", tmp_path / "layouts"
    _metadata(root)
    _layout(layouts)
    result, charset, version = build_dataset(root, layouts_dir=layouts)
    assert len(result.accepted) == 1
    assert result.accepted[0].text == "22.090"
    output = tmp_path / "dataset"
    assert main([
        "--collection-root", str(root), "--layouts-dir", str(layouts),
        "--output", str(output), "--dry-run",
    ]) == 0
    assert not output.exists()
    export_dataset(result, output, charset=charset, charset_version=version)
    assert (output / "preview" / "contact_sheet.png").stat().st_size > 0
