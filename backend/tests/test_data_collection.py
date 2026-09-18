"""Consent, privacy, schema, revision, and failure-isolation tests."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app


CLIENT = TestClient(app)
PUBLIC_IDS = [
    "polarization", "sound-light", "multimeter", "bridge", "solar-cell", "gmr",
    "nmr", "viscosity", "surface-tension", "thermal-conductivity", "michelson",
    "photoelectric-franck-hertz",
]


def _image_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (80, 60), "white").save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def collection_root(monkeypatch, tmp_path):
    root = tmp_path / "collection"
    monkeypatch.setenv("ENABLE_DATA_COLLECTION", "true")
    monkeypatch.setenv("PHYSICSLAB_COLLECTION_ROOT", str(root))
    return root


def _create_session(experiment_id: str = "multimeter") -> str:
    response = CLIENT.post(
        "/api/data-collection/sessions",
        data={
            "experiment_id": experiment_id,
            "template_version": "2.0",
            "consent": "true",
        },
        files={"image": ("sheet.png", _image_bytes(), "image/png")},
    )
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _commit(session_id: str, data: dict, experiment_id: str = "multimeter"):
    return CLIENT.post(
        f"/api/data-collection/sessions/{session_id}/commit",
        json={
            "experiment_id": experiment_id,
            "template_version": "2.0",
            "consent": True,
            "confirmed_data": data,
        },
    )


def test_feature_is_disabled_by_default_and_writes_nothing(monkeypatch, tmp_path):
    root = tmp_path / "disabled"
    monkeypatch.delenv("ENABLE_DATA_COLLECTION", raising=False)
    monkeypatch.setenv("PHYSICSLAB_COLLECTION_ROOT", str(root))
    assert CLIENT.get("/api/data-collection/status").json()["enabled"] is False
    response = CLIENT.post(
        "/api/data-collection/sessions",
        data={"experiment_id": "multimeter", "consent": "true"},
        files={"image": ("sheet.png", _image_bytes(), "image/png")},
    )
    assert response.status_code == 404
    assert not root.exists()


def test_consent_false_creates_no_files(collection_root):
    response = CLIENT.post(
        "/api/data-collection/sessions",
        data={"experiment_id": "multimeter", "consent": "false"},
        files={"image": ("sheet.png", _image_bytes(), "image/png")},
    )
    assert response.status_code == 400
    assert not collection_root.exists()


def test_consent_true_saves_sanitized_image_and_pending_metadata(collection_root):
    session_id = _create_session()
    raw = collection_root / "sessions" / session_id / "raw.jpg"
    metadata_path = collection_root / "sessions" / session_id / "metadata.json"
    assert raw.read_bytes().startswith(b"\xff\xd8\xff")
    with Image.open(raw) as saved:
        assert not saved.getexif()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["consent"] is True
    assert metadata["status"] == "pending_confirmation"
    assert metadata["fields"] == {}
    assert metadata["revision"] == 0


def test_missing_image_creates_no_files(collection_root):
    response = CLIENT.post(
        "/api/data-collection/sessions",
        data={"experiment_id": "multimeter", "consent": "true"},
    )
    assert response.status_code == 422
    assert not collection_root.exists()


def test_invalid_experiment_creates_no_files(collection_root):
    response = CLIENT.post(
        "/api/data-collection/sessions",
        data={"experiment_id": "not-public", "consent": "true"},
        files={"image": ("sheet.png", _image_bytes(), "image/png")},
    )
    assert response.status_code == 400
    assert not collection_root.exists()


def test_invalid_field_is_rejected_before_confirmation(collection_root):
    session_id = _create_session()
    response = _commit(session_id, {
        "voltage": {"rows": [{"invented_dom_column": 1}], "params": {}},
    })
    assert response.status_code == 400
    metadata = json.loads((collection_root / "sessions" / session_id / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "pending_confirmation"
    assert metadata["fields"] == {}


def test_empty_confirmed_data_is_not_a_training_sample(collection_root):
    session_id = _create_session()
    response = _commit(session_id, {"voltage": {"rows": [], "params": {}}})
    assert response.status_code == 400
    metadata = json.loads((collection_root / "sessions" / session_id / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "pending_confirmation"


@pytest.mark.parametrize("experiment_id", PUBLIC_IDS)
def test_typical_fixture_maps_to_config_derived_stable_field_ids(experiment_id):
    from app.data_collection import _method_specs, normalize_confirmed_fields, valid_stable_field_id

    path = Path(__file__).with_name("fixtures") / experiment_id / "typical.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    data = fixture["data"]
    if experiment_id == "polarization":
        data = {**fixture.get("setup", {}), **data}
    specs, setup_fields = _method_specs(experiment_id)
    frontend_data = {key: value for key, value in data.items() if key in setup_fields}
    for method_id, spec in specs.items():
        payload = data.get(method_id)
        if not isinstance(payload, dict):
            continue
        normalized = {
            "params": {
                key: value for key, value in (payload.get("params") or {}).items()
                if key in spec["params"]
            },
            "initial": {
                key: value for key, value in (payload.get("initial") or {}).items()
                if key in spec["initial"]
            },
        }
        rows = payload.get("rows") or ([] if experiment_id != "sound-light" else {})
        if experiment_id == "sound-light":
            normalized["rows"] = {
                key: value for key, value in rows.items() if key in spec["rows"]
            }
        else:
            normalized["rows"] = [
                {key: value for key, value in row.items() if key in spec["rows"]}
                for row in rows
            ]
        frontend_data[method_id] = normalized
    fields = normalize_confirmed_fields(experiment_id, frontend_data)
    assert fields
    assert all(valid_stable_field_id(experiment_id, field_id) for field_id in fields)


def test_final_modification_overwrites_labels_and_increments_revision(collection_root):
    session_id = _create_session()
    first = _commit(session_id, {
        "voltage": {"rows": [{"set": 20, "measured": 19.8}], "params": {}},
    })
    second = _commit(session_id, {
        "voltage": {"rows": [{"set": 20, "measured": 20.1}], "params": {}},
    })
    assert first.status_code == second.status_code == 200
    assert first.json()["revision"] == 1
    assert second.json()["revision"] == 2
    metadata = json.loads((collection_root / "sessions" / session_id / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["fields"]["voltage.rows.row_01.measured"] == 20.1
    assert metadata["revision"] == 2


def test_metadata_has_no_identity_or_request_fingerprint(collection_root):
    session_id = _create_session()
    response = _commit(session_id, {
        "voltage": {"rows": [{"set": 20, "measured": 20.1}], "params": {}},
    })
    assert response.status_code == 200
    metadata = json.loads((collection_root / "sessions" / session_id / "metadata.json").read_text(encoding="utf-8"))
    forbidden = {
        "name", "student_id", "phone", "wechat", "email", "ip", "ip_address",
        "user_agent", "browser_fingerprint", "account", "headers",
    }
    assert forbidden.isdisjoint({str(key).lower() for key in metadata})
    assert set(metadata) == {
        "session_id", "experiment_id", "template_version", "collection_mode", "consent",
        "status", "revision", "created_at", "confirmed_at", "updated_at", "image_path", "fields",
    }


def test_confirmed_session_exports_uncropped_image_and_stable_field_csv(collection_root, tmp_path):
    session_id = _create_session()
    response = _commit(session_id, {
        "voltage": {"rows": [{"set": 20, "measured": 20.1}], "params": {}},
    })
    assert response.status_code == 200

    script_path = Path(__file__).resolve().parents[2] / "scripts" / "export_ocr_dataset.py"
    spec = importlib.util.spec_from_file_location("export_ocr_dataset", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "dataset"
    assert module.export_collection_dataset(collection_root, output) == 2
    with (output / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert reader.fieldnames == ["session_id", "experiment_id", "field_id", "value", "image_path"]
    assert {row["field_id"] for row in rows} == {
        "voltage.rows.row_01.set", "voltage.rows.row_01.measured",
    }
    assert {row["session_id"] for row in rows} == {session_id}
    # The manifest references the page inside private storage; no source page is
    # ever copied into a dataset directory.
    assert {row["image_path"] for row in rows} == {f"sessions/{session_id}/raw.jpg"}
    assert not (output / "images").exists()
    private = collection_root / "sessions" / session_id / "raw.jpg"
    assert private.read_bytes().startswith(b"\xff\xd8\xff")


@pytest.mark.document
def test_collection_storage_failure_does_not_break_validate_process_or_report(collection_root, monkeypatch):
    from app import data_collection

    session_id = _create_session("michelson")
    monkeypatch.setattr(
        data_collection.LocalCollectionStorage,
        "commit_session",
        lambda self, **kwargs: (_ for _ in ()).throw(OSError("disk unavailable")),
    )
    fixture = json.loads(
        (Path(__file__).with_name("fixtures") / "michelson" / "typical.json").read_text(encoding="utf-8")
    )
    data = fixture["data"]
    failed_collection = _commit(session_id, data, "michelson")
    assert failed_collection.status_code == 503

    validation = CLIENT.post("/api/experiments/michelson/validate", json={"data": data})
    process = CLIENT.post("/api/experiments/michelson/process", json={"data": data})
    report = CLIENT.post("/api/experiments/michelson/report?fmt=docx", json={"data": data})
    assert validation.status_code == 200 and validation.json()["valid"] is True
    assert process.status_code == 200 and process.json()["status"] == "success"
    assert report.status_code == 200 and report.content.startswith(b"PK")
