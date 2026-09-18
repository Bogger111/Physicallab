"""Contribution statistics: counting rules, sample estimates and access control."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.collection_stats import collection_stats, estimate_samples, experiment_name, stats_allowed
from app.main import app
from ocr_dataset import templates

CLIENT = TestClient(app)
MULTIMETER_FIELD = "voltage.rows.row_01.measured"


def _sessions_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "collection"
    monkeypatch.setenv("ENABLE_DATA_COLLECTION", "true")
    monkeypatch.setenv("PHYSICSLAB_COLLECTION_ROOT", str(root))
    return root


def make_session(root: Path, *, experiment_id: str = "multimeter", status: str = "confirmed",
                 revision: int = 1, fields: dict | None = None, session_id: str | None = None,
                 subdir: str = "") -> str:
    session_id = session_id or str(uuid4())
    directory = root / "sessions" / session_id / subdir
    directory.mkdir(parents=True, exist_ok=True)
    (root / "sessions" / session_id / "raw.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
    (directory / "metadata.json").write_text(json.dumps({
        "session_id": session_id,
        "experiment_id": experiment_id,
        "template_version": "2.0",
        "consent": True,
        "status": status,
        "revision": revision,
        "created_at": "2026-01-01T00:00:00+00:00",
        "confirmed_at": "2026-01-01T00:01:00+00:00" if status == "confirmed" else None,
        "updated_at": "2026-01-01T00:01:00+00:00",
        "image_path": f"sessions/{session_id}/raw.jpg",
        "fields": fields or {},
    }), encoding="utf-8")
    return session_id


def make_index(root: Path, rows: list[tuple[str, str, str]]) -> None:
    """Write a dataset index (image, text, experiment_id …) without any image."""
    export = root / "datasets" / "ocr_export"
    export.mkdir(parents=True, exist_ok=True)
    with (export / "samples.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "text", "session_id", "experiment_id"],
                                lineterminator="\n")
        writer.writeheader()
        for image, text, experiment in rows:
            writer.writerow({"image": image, "text": text, "session_id": "s", "experiment_id": experiment})


# ------------------------------------------------------------------ counting

def test_stats_count_sessions_confirmed_and_samples(tmp_path, monkeypatch):
    root = _sessions_root(tmp_path, monkeypatch)
    make_session(root, status="confirmed", fields={MULTIMETER_FIELD: "20.04"})
    make_session(root, status="confirmed", fields={MULTIMETER_FIELD: "26.59"})
    make_session(root, status="pending_confirmation", revision=0)
    make_session(root, experiment_id="sound-light", status="confirmed", fields={"air_resonance.rows.row_01.l": "22.090"})
    make_index(root, [("000001.png", "20.04", "multimeter"), ("000002.png", "26.59", "multimeter"),
                      ("000003.png", "22.090", "sound-light")])

    stats = collection_stats(root)
    assert stats["total_sessions"] == 4
    assert stats["confirmed_sessions"] == 3
    assert stats["samples_created"] == 3
    assert stats["experiments"] == {"multimeter": 2, "sound-light": 1}
    assert stats["sessions_by_experiment"] == {"multimeter": 3, "sound-light": 1}
    assert stats["confirmed_by_experiment"] == {"multimeter": 2, "sound-light": 1}
    assert stats["sessions_awaiting_values"] == 1
    assert stats["dataset"]["labeled_samples"] == 3
    assert stats["dataset"]["sessions_in_dataset"] == 1


def test_archived_revision_snapshots_are_not_double_counted(tmp_path, monkeypatch):
    """A session is counted once; nested revision snapshots stay invisible."""
    root = _sessions_root(tmp_path, monkeypatch)
    session_id = make_session(root, status="confirmed", fields={MULTIMETER_FIELD: "20.04"})
    make_session(root, status="confirmed", revision=1, session_id=session_id, subdir="archive")
    assert (root / "sessions" / session_id / "archive" / "metadata.json").is_file()
    stats = collection_stats(root)
    assert stats["total_sessions"] == 1
    assert stats["confirmed_sessions"] == 1


def test_stats_survive_a_corrupt_metadata_file(tmp_path, monkeypatch):
    root = _sessions_root(tmp_path, monkeypatch)
    make_session(root, status="confirmed", fields={MULTIMETER_FIELD: "20.04"})
    broken = root / "sessions" / "broken"
    broken.mkdir(parents=True)
    (broken / "metadata.json").write_text("{not json", encoding="utf-8")
    stats = collection_stats(root)
    assert stats["total_sessions"] == 1
    assert stats["confirmed_sessions"] == 1


def test_stats_of_an_empty_deployment_are_zero(tmp_path, monkeypatch):
    root = _sessions_root(tmp_path, monkeypatch)
    stats = collection_stats(root)
    assert (stats["total_sessions"], stats["confirmed_sessions"], stats["samples_created"]) == (0, 0, 0)
    assert stats["experiments"] == {}


# ------------------------------------------------------------------ estimates

def test_estimate_without_fields_is_the_template_cell_count():
    template = templates.load_template("multimeter")
    assert estimate_samples("multimeter") == len(template["cells"])
    assert estimate_samples("multimeter") > 0


def test_estimate_with_fields_follows_the_builder_admission_rules():
    fields = {
        MULTIMETER_FIELD: "20.04",                       # countable
        "voltage.rows.row_02.measured": "26.59",          # countable
        "voltage.rows.row_03.measured": "-20.04",         # charset rejects the minus
        "voltage.rows.row_04.measured": "",               # empty
        "voltage.rows.row_05.measured": "20.04 mV",       # unit inside the label
        "voltage.rows.row_06.meased": "20.04",            # not a template cell
    }
    assert estimate_samples("multimeter", fields) == 2


def test_estimate_for_an_unknown_experiment_is_zero():
    assert estimate_samples("legacy-photoelectric", {MULTIMETER_FIELD: "1"}) == 0


def test_experiment_name_is_human_readable():
    assert experiment_name("multimeter") == "万用表的组装与校准"
    assert experiment_name("not-an-experiment") == "not-an-experiment"


# ------------------------------------------------------------------ access control

def test_stats_endpoint_is_hidden_when_collection_is_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("PHYSICSLAB_COLLECTION_ROOT", str(tmp_path / "collection"))
    monkeypatch.setenv("ENABLE_DATA_COLLECTION", "false")
    assert CLIENT.get("/api/data-collection/stats").status_code == 404


def test_stats_endpoint_is_hidden_by_default(monkeypatch, tmp_path):
    _sessions_root(tmp_path, monkeypatch)
    monkeypatch.delenv("PHYSICSLAB_DEV_MODE", raising=False)
    monkeypatch.delenv("PHYSICSLAB_ADMIN_KEY", raising=False)
    assert CLIENT.get("/api/data-collection/stats").status_code == 404
    assert stats_allowed(None) is False


def test_stats_endpoint_opens_in_development_mode(monkeypatch, tmp_path):
    root = _sessions_root(tmp_path, monkeypatch)
    make_session(root, status="confirmed", fields={MULTIMETER_FIELD: "20.04"})
    monkeypatch.setenv("PHYSICSLAB_DEV_MODE", "true")
    monkeypatch.delenv("PHYSICSLAB_ADMIN_KEY", raising=False)
    response = CLIENT.get("/api/data-collection/stats")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_sessions"] == 1
    assert body["confirmed_sessions"] == 1
    assert body["samples_created"] == 0
    assert body["experiments"] == {"multimeter": 0}


def test_admin_key_is_required_when_configured_and_wins_over_dev_mode(monkeypatch, tmp_path):
    _sessions_root(tmp_path, monkeypatch)
    monkeypatch.setenv("PHYSICSLAB_DEV_MODE", "true")          # must not be enough
    monkeypatch.setenv("PHYSICSLAB_ADMIN_KEY", "s3cret-key")
    assert CLIENT.get("/api/data-collection/stats").status_code == 404
    assert CLIENT.get("/api/data-collection/stats", headers={"X-Admin-Key": "wrong"}).status_code == 404
    response = CLIENT.get("/api/data-collection/stats", headers={"X-Admin-Key": "s3cret-key"})
    assert response.status_code == 200, response.text
    assert stats_allowed("s3cret-key") is True
    assert stats_allowed("s3cret") is False


# ------------------------------------------------------------------ API integration

def test_upload_and_commit_report_estimate_and_experiment_name(tmp_path, monkeypatch):
    from PIL import Image
    import io

    root = _sessions_root(tmp_path, monkeypatch)
    image = io.BytesIO()
    Image.new("RGB", (120, 90), "white").save(image, format="PNG")

    upload = CLIENT.post(
        "/api/data-collection/sessions",
        files={"image": ("sheet.png", image.getvalue(), "image/png")},
        data={"experiment_id": "multimeter", "template_version": "2.0", "consent": "true"},
    )
    assert upload.status_code == 200, upload.text
    body = upload.json()
    assert body["estimated_samples"] == len(templates.load_template("multimeter")["cells"])
    assert body["experiment_name"] == "万用表的组装与校准"

    commit = CLIENT.post(
        f"/api/data-collection/sessions/{body['session_id']}/commit",
        json={"experiment_id": "multimeter", "template_version": "2.0", "consent": True,
              "confirmed_data": {"voltage": {"rows": [{"measured": "20.04"}], "params": {}}}},
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["estimated_samples"] == 1
    assert commit.json()["field_count"] == 1
    assert root.exists()


def test_stats_never_touch_the_image_files(tmp_path, monkeypatch):
    """Statistics read metadata + the dataset index; an unreadable image must not matter."""
    root = _sessions_root(tmp_path, monkeypatch)
    session_id = make_session(root, status="confirmed", fields={MULTIMETER_FIELD: "20.04"})
    monkeypatch.setenv("PHYSICSLAB_DEV_MODE", "true")
    (root / "sessions" / session_id / "raw.jpg").unlink()
    response = CLIENT.get("/api/data-collection/stats")
    assert response.status_code == 200
    assert response.json()["total_sessions"] == 1
