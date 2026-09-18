"""Export archive: PhysLab_OCR compatibility, ZIP layout and CLI behaviour."""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import pytest

from ocr_dataset import templates
from ocr_dataset.builder import verify_export
from ocr_dataset.export import DEFAULT_ZIP_NAME, export_dataset, extract_dataset, main
from ocr_dataset.quality import load_charset
from test_calibration import make_collection, rendered_page, write_ink

MULTIMETER_FIELDS = ["voltage.rows.row_01.measured", "voltage.rows.row_02.measured"]


def field_box(experiment_id: str, field_id: str) -> tuple[int, int, int, int]:
    template = templates.load_template(experiment_id)
    width, height = template["reference_size"]
    for cell in template["cells"]:
        if cell["field_id"] == field_id:
            x1, y1, x2, y2 = cell["bbox"]
            return int(x1 * width), int(y1 * height), int(x2 * width), int(y2 * height)
    raise AssertionError(field_id)


def confirmed_session(root: Path, experiment_id: str, values: dict[str, str], *, revision: int = 1) -> str:
    """A realistic confirmed collection session: rendered sheet + written values."""
    image = rendered_page(experiment_id).copy()
    for field_id, text in values.items():
        write_ink(image, field_box(experiment_id, field_id), text)
    return make_collection(root, experiment_id, image, values, revision=revision)


@pytest.fixture
def collection(tmp_path: Path) -> Path:
    root = tmp_path / "collection"
    confirmed_session(root, "multimeter", {MULTIMETER_FIELDS[0]: "20.04", MULTIMETER_FIELDS[1]: "26.59"})
    return root


# ------------------------------------------------------------------ archive

def test_export_builds_a_physlab_ocr_archive(collection, tmp_path):
    archive = tmp_path / "physlab_ocr_dataset.zip"
    outcome = export_dataset(archive, collection_root=collection)

    assert outcome.sample_count >= 1
    assert outcome.experiment_count == 1
    assert outcome.problems == []
    assert archive.is_file()

    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert "dataset/labels.csv" in names
        assert "dataset/manifest.json" in names
        images = [name for name in names if name.startswith("dataset/images/")]
        assert images, names
        assert all(name.endswith(".png") for name in images)

        with bundle.open("dataset/labels.csv") as handle:
            rows = list(csv.reader(line.decode("utf-8").rstrip("\n") for line in handle))
        assert rows[0] == ["image", "text"]
        assert len(rows) - 1 == outcome.sample_count
        characters, _ = load_charset()
        for name, text in rows[1:]:
            assert Path(name).name == name, name
            assert set(text) <= set(characters), text

        manifest = json.loads(bundle.read("dataset/manifest.json").decode("utf-8"))
        for key in ("version", "created_at", "experiment_count", "sample_count"):
            assert key in manifest, key
        assert manifest["sample_count"] == outcome.sample_count
        assert manifest["experiment_count"] == 1
        assert manifest["experiments"] == {"multimeter": outcome.sample_count}


def test_extracted_archive_is_ready_for_the_training_repo(collection, tmp_path):
    archive = tmp_path / "physlab_ocr_dataset.zip"
    export_dataset(archive, collection_root=collection)

    destination = tmp_path / "PhysLab_OCR_data"
    dataset = extract_dataset(archive, destination)
    assert dataset == destination / "dataset"
    assert (dataset / "images").is_dir()
    assert verify_export(dataset) == []
    # exactly the two things SequenceDataset() reads, plus the manifest
    assert sorted(path.name for path in dataset.iterdir()) == ["images", "labels.csv", "manifest.json"]


def test_export_filters_by_experiment(collection, tmp_path):
    root = collection
    confirmed_session(root, "sound-light", {"air_resonance.rows.row_01.l": "22.090"})

    everything = export_dataset(tmp_path / "all.zip", collection_root=root)
    assert everything.experiment_count == 2

    only_sound = export_dataset(tmp_path / "sound.zip", collection_root=root, experiment_id="sound-light")
    assert set(only_sound.experiments) == {"sound-light"}
    with zipfile.ZipFile(tmp_path / "sound.zip") as bundle:
        manifest = json.loads(bundle.read("dataset/manifest.json").decode("utf-8"))
    assert manifest["experiments"] == {"sound-light": only_sound.sample_count}
    assert only_sound.experiment_count == 1


def test_export_ignores_ordinary_sessions(tmp_path):
    """Only AI co-build sessions are contributions; ordinary runs are not data."""
    root = tmp_path / "collection"
    image = rendered_page("multimeter").copy()
    write_ink(image, field_box("multimeter", MULTIMETER_FIELDS[0]), "20.04")
    make_collection(root, "multimeter", image, {MULTIMETER_FIELDS[0]: "20.04"}, collection_mode=False)
    outcome = export_dataset(tmp_path / "ordinary.zip", collection_root=root)
    assert outcome.sessions_seen == 0
    assert outcome.sample_count == 0
    assert outcome.problems == ["no AI co-build sessions to export"]
    assert (tmp_path / "ordinary.zip").is_file(), "an empty archive is still produced"
    with zipfile.ZipFile(tmp_path / "ordinary.zip") as bundle:
        assert bundle.read("dataset/labels.csv").decode("utf-8").strip() == "image,text"


def test_export_ignores_pending_and_unconsented_sessions(collection, tmp_path):
    root = collection
    confirmed_session(root, "multimeter", {MULTIMETER_FIELDS[0]: "20.04"}, revision=0)   # never confirmed
    outcome = export_dataset(tmp_path / "pending.zip", collection_root=root)
    assert outcome.sessions_seen == 1                    # only the confirmed one
    assert set(outcome.experiments) == {"multimeter"}


def test_dry_run_writes_nothing(collection, tmp_path):
    archive = tmp_path / "dry.zip"
    outcome = export_dataset(archive, collection_root=collection, dry_run=True)
    assert outcome.sample_count >= 1
    assert outcome.dry_run is True
    assert not archive.exists()


def test_export_neutralizes_an_illegal_charset_label(tmp_path):
    """A negative reading is a legal entry but unencodable: it must not be exported."""
    root = tmp_path / "collection"
    confirmed_session(root, "gmr", {"transfer.rows.row_01.output": "-0.5"})
    outcome = export_dataset(tmp_path / "gmr.zip", collection_root=root)
    assert outcome.sample_count == 0
    with zipfile.ZipFile(tmp_path / "gmr.zip") as bundle:
        rows = bundle.read("dataset/labels.csv").decode("utf-8").splitlines()
    assert rows == ["image,text"]


# ------------------------------------------------------------------ CLI

def test_cli_reports_the_documented_summary(collection, tmp_path, capsys):
    archive = tmp_path / "cli.zip"
    assert main(["--collection-root", str(collection), "--output", str(archive)]) == 0
    printed = capsys.readouterr().out
    assert "Export completed" in printed
    assert "samples:" in printed
    assert f"output: {archive}" in printed
    assert archive.is_file()


def test_cli_dry_run_and_default_archive_name(collection, tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["--collection-root", str(collection), "--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert "dry-run: nothing written" in printed
    assert not (tmp_path / DEFAULT_ZIP_NAME).exists()
    assert not list(tmp_path.glob("*.zip")), "dry-run must not write an archive"
    assert not list(tmp_path.glob("physlab_ocr_export_*")), "staging must be cleaned up"
