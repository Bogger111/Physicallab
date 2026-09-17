"""Offline API regression coverage for every public PhysKiller experiment.

The corpus is synthetic and structure-derived. It protects the current API,
calculation and document paths, but is not complete real-data validation.
"""

from __future__ import annotations

import base64
import copy
import io
import json
import math
import zipfile
from pathlib import Path
from typing import Any

import fitz
import pytest
from fastapi.testclient import TestClient

from app.main import app


FIXTURE_ROOT = Path(__file__).with_name("fixtures")
MANIFEST = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
PUBLIC_EXPERIMENTS = MANIFEST["public_experiments"]
PUBLIC_IDS = [item["id"] for item in PUBLIC_EXPERIMENTS]
CLIENT = TestClient(app)
pytestmark = pytest.mark.real_usability


def _resolve_index(container: list[Any], token: int) -> int:
    return token if token >= 0 else len(container) + token


def _apply_patch(document: dict[str, Any], patch: dict[str, Any]) -> None:
    assert patch["op"] == "replace"
    target: Any = document
    for token in patch["path"][:-1]:
        target = target[_resolve_index(target, token) if isinstance(target, list) else token]
    final = patch["path"][-1]
    if isinstance(target, list):
        target[_resolve_index(target, final)] = patch["value"]
    else:
        target[final] = patch["value"]


def load_fixture(experiment_id: str, case: str) -> dict[str, Any]:
    path = FIXTURE_ROOT / experiment_id / f"{case}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    if "extends" in document:
        base = json.loads((path.parent / document["extends"]).read_text(encoding="utf-8"))
        merged = copy.deepcopy(base)
        merged.update({key: value for key, value in document.items()
                       if key not in {"extends", "patches"}})
        for patch in document.get("patches", []):
            _apply_patch(merged, patch)
        document = merged
    return document


def _polarization_body(fixture: dict[str, Any]) -> dict[str, Any]:
    return {**fixture.get("setup", {}), **fixture["data"]}


def validation_responses(fixture: dict[str, Any]):
    experiment_id = fixture["experiment_id"]
    if fixture["kind"] == "polarization":
        return [CLIENT.post(f"/api/experiments/{experiment_id}/validate",
                            json=_polarization_body(fixture))]
    if fixture["kind"] == "sound-light":
        return [CLIENT.post(f"/api/experiments/{experiment_id}/validate",
                            json={"method": method_id, **payload})
                for method_id, payload in fixture["data"].items()]
    return [CLIENT.post(f"/api/experiments/{experiment_id}/validate",
                        json={"data": fixture["data"]})]


def process_responses(fixture: dict[str, Any]):
    experiment_id = fixture["experiment_id"]
    if fixture["kind"] == "polarization":
        return [(None, CLIENT.post(f"/api/experiments/{experiment_id}/process",
                                   json=_polarization_body(fixture)))]
    if fixture["kind"] == "sound-light":
        return [(method_id, CLIENT.post(f"/api/experiments/{experiment_id}/process",
                                        json={"method": method_id, **payload}))
                for method_id, payload in fixture["data"].items()]
    return [(None, CLIENT.post(f"/api/experiments/{experiment_id}/process",
                               json={"data": fixture["data"]}))]


def report_body(fixture: dict[str, Any]) -> dict[str, Any]:
    if fixture["kind"] == "polarization":
        return _polarization_body(fixture)
    return {"data": fixture["data"]}


def assert_finite_numbers(value: Any, path: str = "result") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        assert math.isfinite(value), f"non-finite number at {path}: {value}"
        return
    if isinstance(value, dict):
        for key, child in value.items():
            assert_finite_numbers(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            assert_finite_numbers(child, f"{path}[{index}]")


def assert_png_plots(plots: dict[str, Any]) -> None:
    assert plots, "fixture should exercise at least one chart"
    for name, encoded in plots.items():
        assert isinstance(encoded, str) and encoded, f"empty plot: {name}"
        assert base64.b64decode(encoded).startswith(b"\x89PNG\r\n\x1a\n"), name


def assert_expected_fields(fixture: dict[str, Any], method_id: str | None,
                           payload: dict[str, Any]) -> None:
    expected = fixture["expected_result_fields"]
    if fixture["kind"] == "sound-light":
        actual = {item["key"]: item["value"] for item in payload["results"]}
        assert set(expected[method_id]) <= actual.keys()
        for key in expected[method_id]:
            assert isinstance(actual[key], (int, float)) and math.isfinite(actual[key])
        return
    for current_method, fields in expected.items():
        assert current_method in payload["results"]
        actual = payload["results"][current_method]
        assert set(fields) <= actual.keys()
        for key in fields:
            assert isinstance(actual[key], (int, float)) and math.isfinite(actual[key]), (
                current_method, key, actual.get(key))


def test_fixture_manifest_matches_the_12_public_catalogue_entries():
    response = CLIENT.get("/api/experiments")
    assert response.status_code == 200
    published = [item["id"] for item in response.json()["experiments"]]
    assert published == PUBLIC_IDS
    assert len(PUBLIC_IDS) == 12
    assert len(set(PUBLIC_IDS)) == 12
    assert all(not item.get("legacy") for item in response.json()["experiments"])
    for entry in PUBLIC_EXPERIMENTS:
        assert entry["process_endpoint"].endswith(f"/{entry['id']}/process")
        assert entry["calculation_entry"]


@pytest.mark.parametrize("experiment_id", PUBLIC_IDS)
def test_fixture_corpus_has_typical_boundary_and_invalid_cases(experiment_id):
    for case in ("typical", "boundary", "invalid"):
        fixture = load_fixture(experiment_id, case)
        assert fixture["experiment_id"] == experiment_id
        assert fixture["case"] == case
        assert fixture["fixture_type"] == case
        assert fixture["source"] in {"synthetic", "structure-derived", "real"}
        assert fixture["verified"] is False
        assert fixture["notes"].strip()
    boundary = load_fixture(experiment_id, "boundary")
    assert boundary["boundary_targets"]
    assert "real laboratory" in MANIFEST["validation_boundary"]


@pytest.mark.parametrize("experiment_id", PUBLIC_IDS)
def test_config_and_schema_are_available_for_every_public_experiment(experiment_id):
    config = CLIENT.get(f"/api/experiments/{experiment_id}/config")
    schema = CLIENT.get(f"/api/experiments/{experiment_id}/schema")
    assert config.status_code == 200
    assert schema.status_code == 200
    definition = schema.json()["definition"]
    assert definition["id"] == experiment_id
    assert definition["methods"]
    if experiment_id == "sound-light":
        assert isinstance(config.json(), list) and config.json()
    else:
        assert isinstance(config.json(), dict)


@pytest.mark.parametrize("experiment_id", PUBLIC_IDS)
def test_typical_fixture_validates_and_processes_through_the_real_api(experiment_id):
    fixture = load_fixture(experiment_id, "typical")
    for response in validation_responses(fixture):
        assert response.status_code == 200, response.text
        assert response.json()["valid"] is True, response.json()
        assert response.json()["errors"] == []
    for method_id, response in process_responses(fixture):
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "success", payload
        assert not payload.get("errors"), payload.get("errors")
        assert_expected_fields(fixture, method_id, payload)
        assert_finite_numbers(payload["results"])
        assert_png_plots(payload["plots"])


@pytest.mark.parametrize("experiment_id", PUBLIC_IDS)
def test_boundary_fixture_remains_finite_and_processable(experiment_id):
    fixture = load_fixture(experiment_id, "boundary")
    for response in validation_responses(fixture):
        assert response.status_code == 200, response.text
        assert response.json()["valid"] is True, response.json()
    for method_id, response in process_responses(fixture):
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "success", (method_id, payload)
        assert_expected_fields(fixture, method_id, payload)
        assert_finite_numbers(payload["results"])


@pytest.mark.parametrize("experiment_id", PUBLIC_IDS)
def test_invalid_fixture_is_rejected_by_validation_and_processing(experiment_id):
    fixture = load_fixture(experiment_id, "invalid")
    validations = validation_responses(fixture)
    assert validations
    assert any(response.status_code == 422 or (
        response.status_code == 200 and response.json()["valid"] is False
    ) for response in validations), [response.text for response in validations]
    processes = process_responses(fixture)
    assert any(response.status_code == 422 or (
        response.status_code == 200 and response.json()["status"] != "success"
    ) for _method_id, response in processes), [response.text for _method_id, response in processes]


@pytest.mark.parametrize("experiment_id", PUBLIC_IDS)
@pytest.mark.parametrize("fmt", ["docx", "pdf"])
@pytest.mark.document
def test_typical_fixture_generates_nonempty_reports_through_the_real_api(experiment_id, fmt):
    fixture = load_fixture(experiment_id, "typical")
    response = CLIENT.post(f"/api/experiments/{experiment_id}/report?fmt={fmt}",
                           json=report_body(fixture))
    assert response.status_code == 200, response.text
    assert len(response.content) > 1000
    if fmt == "docx":
        assert response.content.startswith(b"PK")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.testzip() is None
            assert "word/document.xml" in archive.namelist()
    else:
        assert response.content.startswith(b"%PDF")
        pdf = fitz.open(stream=response.content, filetype="pdf")
        assert len(pdf) >= 4
        assert all(page.rect.width == pytest.approx(595.28, abs=0.2) for page in pdf)
