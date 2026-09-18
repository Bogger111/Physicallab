"""PhysLab → PhysLab_OCR dataset pipeline tests.

The uploads here are the repository's own record sheets rendered to pixels with
synthetic handwriting written into the template cells, so the label↔crop mapping
is checkable without any real user data.  Everything runs through the real
collection API and the real storage implementation, against a temporary
collection root, exactly as a development deployment would.

Compatibility with `Bogger111/PhysLab_OCR` is asserted structurally:
``datasets/sequencedatasets.py`` reads ``labels.csv`` with ``csv.DictReader`` and
looks up ``Path(image_dir) / row["image"]``, and ``datasets/charsets.py`` encodes
every character through ``"0123456789."`` — anything else raises at training time.
"""

from __future__ import annotations

import csv
import functools
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from ocr_dataset import templates
from ocr_dataset.builder import (
    BuilderError,
    build_session_dataset,
    sample_key,
    verify_export,
)
from ocr_dataset.quality import load_charset

CLIENT = TestClient(app)
OCR_REPO_CHARSET = "0123456789."
#: A page photographed at an angle on a desk, as a student would submit it.
PHOTO_CORNERS = [[150, 110], [1760, 210], [1700, 2470], [110, 2350]]


@pytest.fixture
def collection_root(monkeypatch, tmp_path):
    root = tmp_path / "collection"
    monkeypatch.setenv("ENABLE_DATA_COLLECTION", "true")
    monkeypatch.setenv("PHYSICSLAB_COLLECTION_ROOT", str(root))
    return root


# ------------------------------------------------------------------ synthetic uploads

@functools.lru_cache(maxsize=8)
def rendered_page(experiment_id: str) -> np.ndarray:
    """The blank record sheet this repository ships, rasterised at reference size."""
    from experiments.core.registry import registry
    from ocr_dataset.calibrate import (
        _render_blocks,
        capture_tables,
        record_sheet_blocks,
        render_page_image,
    )

    experiment = registry.get(experiment_id)
    pdf, _, _ = capture_tables(_render_blocks(experiment, record_sheet_blocks(experiment)))
    return render_page_image(pdf)


def cell_box(experiment_id: str, field_id: str) -> tuple[int, int, int, int]:
    template = templates.load_template(experiment_id)
    width, height = template["reference_size"]
    for cell in template["cells"]:
        if cell["field_id"] == field_id:
            x1, y1, x2, y2 = cell["bbox"]
            return int(x1 * width), int(y1 * height), int(x2 * width), int(y2 * height)
    raise AssertionError(f"{experiment_id}: no template cell for {field_id}")


def write_handwriting(image: np.ndarray, box: tuple[int, int, int, int], text: str) -> None:
    """Write one number into a cell the way a student would: centred, compact.

    The value fills about half the cell height and at most 70% of its width, with
    clear margins, so the crop quality gates see ordinary handwriting rather than
    a value scribbled edge to edge (which is what the review gate exists for).
    """
    x1, y1, x2, y2 = box
    cell_width, cell_height = x2 - x1, y2 - y1
    target_width = max(18, int(cell_width * 0.70))
    target_height = max(8, int(cell_height * 0.50))
    scale = 1.0
    for _ in range(12):
        (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        if text_height <= 0 or text_width <= 0:
            break
        if text_width > target_width or text_height > target_height:
            scale *= min(target_width / text_width, target_height / text_height)
        elif text_width >= target_width * 0.9 or text_height >= target_height * 0.9:
            break
        else:
            scale *= min(target_width / text_width, target_height / text_height) ** 0.5
    thickness = max(1, int(round(scale * 1.4)))
    (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    margin = max(3, int(cell_height * 0.25))
    origin = (x1 + max(margin, (cell_width - text_width) // 2),
              y1 + max(margin, (cell_height + text_height) // 2))
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, 35, thickness, cv2.LINE_AA)


def as_photo(page: np.ndarray, corners=PHOTO_CORNERS, canvas=(2620, 1960), desk: int = 120) -> np.ndarray:
    """Place the page on a darker desk with perspective, as a phone photo would."""
    rows, cols = canvas
    source = np.array([[0, 0], [page.shape[1] - 1, 0],
                       [page.shape[1] - 1, page.shape[0] - 1], [0, page.shape[0] - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(source, np.asarray(corners, dtype=np.float32))
    canvas_image = np.full((rows, cols), desk, dtype=np.uint8)
    warped = cv2.warpPerspective(page, matrix, (cols, rows), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=desk)
    mask = cv2.warpPerspective(np.full_like(page, 255), matrix, (cols, rows),
                               flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    canvas_image[mask > 0] = warped[mask > 0]
    noise = np.random.default_rng(7).normal(0, 3.0, canvas_image.shape)
    return np.clip(canvas_image.astype(np.float64) + noise, 0, 255).astype(np.uint8)


def upload_bytes(experiment_id: str, values: dict[str, str], *, flat: bool = False) -> bytes:
    """A submitted record sheet with `values` written into their own cells."""
    from ocr_dataset.calibrate import REFERENCE_SIZE

    assert tuple(rendered_page(experiment_id).shape[:2][::-1]) == tuple(REFERENCE_SIZE)
    image = rendered_page(experiment_id).copy()
    for field_id, text in values.items():
        write_handwriting(image, cell_box(experiment_id, field_id), text)
    if not flat:
        image = as_photo(image)
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 94])
    assert ok
    return buffer.tobytes()


def commit_payload(experiment_id: str, values: dict[str, str]) -> dict:
    """Build the flat report payload the workspace sends for `values`."""
    payload: dict[str, dict] = {}
    setups: dict[str, str] = {}
    for field_id, value in values.items():
        parts = field_id.split(".")
        if parts[0] == "setup":
            setups[field_id] = value
            continue
        method = parts[0]
        section = parts[1]
        if section == "params":
            payload.setdefault(method, {}).setdefault("params", {})[parts[2]] = value
            continue
        row_index = int(parts[2].removeprefix("row_"))
        column = parts[3]
        if experiment_id == "sound-light":
            columns = payload.setdefault(method, {}).setdefault("rows", {})
            values_list = columns.setdefault(column, [None] * row_index)
            while len(values_list) < row_index:
                values_list.append(None)
            values_list[row_index - 1] = value
        else:
            rows = payload.setdefault(method, {}).setdefault("rows", [])
            while len(rows) < row_index:
                rows.append({})
            rows[row_index - 1][column] = value
    return {**payload, **setups}


def first_rows_field(experiment_id: str, count: int = 2) -> list[str]:
    """Template cells of the first table that has real handwriting columns."""
    template = templates.load_template(experiment_id)
    ordered = [cell["field_id"] for cell in sorted(
        template["cells"], key=lambda cell: (float(cell["bbox"][1]), float(cell["bbox"][0])))]
    rows = [field for field in ordered if ".rows.row_" in field]
    return rows[:count]


def create_session(experiment_id: str, values: dict[str, str]) -> str:
    response = CLIENT.post(
        "/api/data-collection/sessions",
        files={"image": ("sheet.jpg", upload_bytes(experiment_id, values), "image/jpeg")},
        data={"experiment_id": experiment_id, "template_version": "2.0", "consent": "true",
              "collection_mode": "true"},
    )
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def commit_session(session_id: str, experiment_id: str, values: dict[str, str]) -> dict:
    response = CLIENT.post(
        f"/api/data-collection/sessions/{session_id}/commit",
        json={
            "experiment_id": experiment_id,
            "template_version": "2.0",
            "consent": True,
            "confirmed_data": commit_payload(experiment_id, values),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def read_labels(export_dir: Path) -> list[dict[str, str]]:
    with (export_dir / "labels.csv").open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


# ------------------------------------------------------------------ templates

@pytest.mark.parametrize("experiment_id", sorted(templates.calibration_root().glob("*.json")))
def test_every_public_experiment_ships_a_valid_template(experiment_id):
    experiment = experiment_id.stem
    template = templates.load_template(experiment)
    assert template["experiment"] == experiment
    assert template["cells"], experiment
    assert templates.validate_field_ids(experiment, template) == []
    for cell in template["cells"]:
        x1, y1, x2, y2 = cell["bbox"]
        assert 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1


def test_templates_match_their_calibration():
    assert templates.check_templates() == []


def test_template_cell_edges_sit_on_printed_table_lines():
    """A template cell must be a real cell of the rendered sheet, not a guess."""
    from ocr_dataset.segment import grid_lines

    page = rendered_page("multimeter")
    detected_x, detected_y = grid_lines(page)
    height, width = page.shape[:2]
    tolerance_x, tolerance_y = width * 0.006, height * 0.006
    for cell in templates.load_template("multimeter")["cells"]:
        x1, y1, x2, y2 = cell["bbox"]
        for value in (x1 * width, x2 * width):
            assert any(abs(value - line) <= tolerance_x for line in detected_x), cell["field_id"]
        for value in (y1 * height, y2 * height):
            assert any(abs(value - line) <= tolerance_y for line in detected_y), cell["field_id"]


def test_template_rejects_a_broken_cell(tmp_path):
    template = templates.load_template("multimeter")
    template["cells"][0]["bbox"] = [0.5, 0.4, 0.2, 0.6]
    path = tmp_path / "multimeter.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    with pytest.raises(ValueError):
        templates.load_template("multimeter", tmp_path)


# ------------------------------------------------------------------ end-to-end

def test_confirmed_session_becomes_a_physlab_ocr_dataset(collection_root):
    fields = first_rows_field("multimeter")
    values = {fields[0]: "22.090", fields[1]: "26.590"}
    session_id = create_session("multimeter", values)
    commit_session(session_id, "multimeter", values)

    response = CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["samples_created"] == 2
    assert payload["output"] == "ocr_export"

    export = collection_root / "datasets" / "ocr_export"
    assert (export / "labels.csv").is_file()
    labels = read_labels(export)
    assert {row["text"] for row in labels} == {"22.090", "26.590"}
    assert verify_export(export) == []
    for row in labels:
        assert (export / "images" / row["image"]).is_file()


def test_labels_preserve_trailing_zeroes_and_string_precision(collection_root):
    fields = first_rows_field("multimeter")
    values = {fields[0]: "22.090"}
    session_id = create_session("multimeter", values)
    commit_session(session_id, "multimeter", values)
    CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr")

    labels = read_labels(collection_root / "datasets" / "ocr_export")
    assert [row["text"] for row in labels] == ["22.090"]


def test_physical_samples_are_single_cells_not_pages(collection_root):
    fields = first_rows_field("multimeter")
    values = {fields[0]: "22.090"}
    session_id = create_session("multimeter", values)
    commit_session(session_id, "multimeter", values)
    CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr")

    export = collection_root / "datasets" / "ocr_export"
    page = rendered_page("multimeter")
    for image_path in (export / "images").glob("*.png"):
        crop = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        assert crop.ndim == 2, "training crops must be grayscale"
        assert crop.shape[0] < page.shape[0] * 0.3
        assert crop.shape[1] < page.shape[1]
        assert np.min(crop) < 120, "ink must survive the crop"
    # no source page, and no JPEG, ever lands in the dataset directory
    assert not list(export.rglob("*.jpg"))
    assert not list(export.rglob("raw*"))


def test_dataset_is_written_into_private_storage_not_the_repository(collection_root):
    fields = first_rows_field("multimeter")
    values = {fields[0]: "22.090"}
    session_id = create_session("multimeter", values)
    commit_session(session_id, "multimeter", values)
    payload = CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr").json()

    export = collection_root / "datasets" / payload["output"]
    assert export.is_dir()
    repository = Path(__file__).resolve().parents[2]
    assert not (repository / "backend" / "datasets").exists()
    assert not (repository / "ocr_dataset").exists()
    manifest = json.loads((export / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["last_session"]["source_image"].startswith("sessions/")


def test_labels_csv_is_exactly_the_ocr_repo_contract(collection_root):
    fields = first_rows_field("multimeter")
    values = {fields[0]: "22.090"}
    session_id = create_session("multimeter", values)
    commit_session(session_id, "multimeter", values)
    CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr")

    export = collection_root / "datasets" / "ocr_export"
    with (export / "labels.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["image", "text"], "extra columns would break the OCR loader contract"
    assert len(rows) == 2
    name, text = rows[1]
    assert Path(name).name == name, "the loader joins images_dir + row['image']"
    characters, _ = load_charset()
    assert characters == OCR_REPO_CHARSET, "must match PhysLab_OCR datasets/charsets.py"
    assert set(text) <= set(OCR_REPO_CHARSET)


def test_labels_outside_the_charset_never_reach_the_dataset(collection_root):
    """`-0.5` is a legal reading but PhysLab_OCR's encode() would raise on it."""
    fields = first_rows_field("gmr")
    values = {fields[0]: "-0.5"}
    session_id = create_session("gmr", values)
    commit_session(session_id, "gmr", values)
    payload = CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr").json()

    export = collection_root / "datasets" / "ocr_export"
    assert payload["samples_created"] == 0
    assert payload["reason_counts"].get("illegal_charset") == 1
    assert read_labels(export) == []
    with (export / "rejected.csv").open(encoding="utf-8", newline="") as handle:
        rejected = list(csv.DictReader(handle))
    assert rejected[0]["reason"] == "illegal_charset"
    assert rejected[0]["text"] == "-0.5"


def test_pending_session_cannot_be_exported(collection_root):
    session_id = create_session("multimeter", {})
    response = CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr")
    assert response.status_code == 400
    assert "确认" in response.json()["detail"]
    assert not (collection_root / "datasets").exists()


def test_tampered_session_without_consent_is_refused(collection_root):
    fields = first_rows_field("multimeter")
    values = {fields[0]: "22.090"}
    session_id = create_session("multimeter", values)
    commit_session(session_id, "multimeter", values)

    metadata_path = collection_root / "sessions" / session_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["consent"] = False
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    response = CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr")
    assert response.status_code == 400
    assert not (collection_root / "datasets").exists()


def test_unknown_session_is_not_found(collection_root):
    response = CLIENT.post("/api/data-collection/sessions/2f4a1c1e-0000-4000-8000-000000000000/build-ocr")
    assert response.status_code == 404


def test_empty_cell_is_rejected_by_the_quality_gate(collection_root):
    """A confirmed value whose cell has no ink must never become a training label."""
    fields = first_rows_field("multimeter")
    inked = {fields[0]: "22.090"}                      # handwriting only here
    confirmed = {fields[0]: "22.090", fields[1]: "26.590"}
    session_id = create_session("multimeter", inked)
    commit_session(session_id, "multimeter", confirmed)
    payload = CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr").json()

    assert payload["samples_created"] == 1
    assert set(payload["reason_counts"]) == {"blank_or_white_crop"}
    export = collection_root / "datasets" / "ocr_export"
    assert [row["text"] for row in read_labels(export)] == ["22.090"]
    with (export / "rejected.csv").open(encoding="utf-8", newline="") as handle:
        rejected = list(csv.DictReader(handle))
    assert [row["text"] for row in rejected] == ["26.590"]
    assert rejected[0]["field_id"] == fields[1]


def test_every_public_experiment_produces_samples(collection_root):
    """The template layer must actually work for all 12 published experiments."""
    experiments = sorted(path.stem for path in templates.calibration_root().glob("*.json"))
    assert len(experiments) == 12
    produced: dict[str, int] = {}
    for experiment_id in experiments:
        fields = first_rows_field(experiment_id, 2)
        values = {field: "22.090" for field in fields}
        session_id = create_session(experiment_id, values)
        commit_session(session_id, experiment_id, values)
        payload = CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr").json()
        produced[experiment_id] = payload["samples_created"]
    assert all(count >= 1 for count in produced.values()), produced


def test_exported_crops_contain_no_table_line_residue(collection_root):
    """Printed rules must not survive into a training crop."""
    from ocr_dataset.segment import _ink_mask, _rule_residue

    fields = first_rows_field("multimeter")
    values = {fields[0]: "22.090"}
    session_id = create_session("multimeter", values)
    commit_session(session_id, "multimeter", values)
    CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr")

    export = collection_root / "datasets" / "ocr_export"
    for image_path in (export / "images").glob("*.png"):
        crop = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        ink = _ink_mask(crop, sensitivity=40.0, ceiling=200.0)
        ink[0, :] = ink[-1, :] = False
        ink[:, 0] = ink[:, -1] = False
        count, labels, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), connectivity=8)
        leftovers = [
            tuple(int(value) for value in stats[index, :4])
            for index in range(1, count)
            if _rule_residue(tuple(int(value) for value in stats[index, :4]), crop.shape)
        ]
        assert not leftovers, (image_path.name, leftovers)


def test_rebuilding_the_same_session_does_not_duplicate_samples(collection_root):
    fields = first_rows_field("multimeter")
    values = {fields[0]: "22.090"}
    session_id = create_session("multimeter", values)
    commit_session(session_id, "multimeter", values)
    first = CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr").json()
    second = CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr").json()

    assert first["samples_created"] == 1
    assert second["samples_created"] == 0
    assert second["skipped_duplicates"] == 1
    labels = read_labels(collection_root / "datasets" / "ocr_export")
    assert len(labels) == 1


def test_second_session_extends_the_dataset(collection_root):
    fields = first_rows_field("multimeter")
    first_values = {fields[0]: "11.110"}
    second_values = {fields[1]: "22.220"}
    for values in (first_values, second_values):
        session_id = create_session("multimeter", values)
        commit_session(session_id, "multimeter", values)
        assert CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr").status_code == 200

    export = collection_root / "datasets" / "ocr_export"
    labels = read_labels(export)
    assert sorted(row["text"] for row in labels) == ["11.110", "22.220"]
    assert sorted(row["image"] for row in labels) == ["000001.png", "000002.png"]
    assert verify_export(export) == []


def test_dry_run_reports_without_writing(collection_root):
    fields = first_rows_field("multimeter")
    values = {fields[0]: "22.090"}
    session_id = create_session("multimeter", values)
    commit_session(session_id, "multimeter", values)

    from app.data_collection import local_storage

    outcome = build_session_dataset(session_id, storage=local_storage(), dry_run=True)
    assert outcome.samples_created == 1
    assert outcome.dry_run is True
    assert not (collection_root / "datasets").exists()


def test_overwrite_rebuilds_from_this_session_only(collection_root):
    fields = first_rows_field("multimeter")
    for values in ({fields[0]: "11.110"}, {fields[1]: "22.220"}):
        session_id = create_session("multimeter", values)
        commit_session(session_id, "multimeter", values)
        CLIENT.post(f"/api/data-collection/sessions/{session_id}/build-ocr")

    from app.data_collection import local_storage

    export = collection_root / "datasets" / "ocr_export"
    assert len(read_labels(export)) == 2
    session_id = create_session("multimeter", {fields[0]: "33.330"})
    commit_session(session_id, "multimeter", {fields[0]: "33.330"})
    outcome = build_session_dataset(session_id, storage=local_storage(), overwrite=True)
    assert outcome.samples_created == 1
    assert [row["text"] for row in read_labels(export)] == ["33.330"]


def test_builder_refuses_a_dataset_name_outside_the_storage_root(collection_root):
    from app.data_collection import CollectionValidationError, local_storage

    with pytest.raises(CollectionValidationError):
        local_storage().dataset_dir("../escape")


def test_sample_key_is_deterministic_and_revision_aware():
    one = sample_key("session", "voltage.rows.row_01.measured", 3)
    assert one == sample_key("session", "voltage.rows.row_01.measured", 3)
    assert one != sample_key("session", "voltage.rows.row_01.measured", 4)
    assert one != sample_key("session", "voltage.rows.row_02.measured", 3)
    assert len(one) == 32


def test_session_record_reads_through_the_storage_interface(collection_root):
    from app.data_collection import CollectionNotFoundError, local_storage

    fields = first_rows_field("multimeter")
    values = {fields[0]: "22.090"}
    session_id = create_session("multimeter", values)
    commit_session(session_id, "multimeter", values)

    record = local_storage().load_session(session_id)
    assert record.status == "confirmed"
    assert record.revision == 1
    assert record.consent is True
    assert record.fields[fields[0]] == "22.090"
    assert record.image_bytes.startswith(b"\xff\xd8\xff")
    with pytest.raises(CollectionNotFoundError):
        local_storage().load_session("2f4a1c1e-0000-4000-8000-000000000000")


def test_builder_gate_rejects_a_pending_record(collection_root):
    from app.data_collection import local_storage

    session_id = create_session("multimeter", {})
    with pytest.raises(BuilderError):
        build_session_dataset(session_id, storage=local_storage())
