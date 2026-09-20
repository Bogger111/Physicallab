"""In-process API contract checks; no server process is started."""

import json

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_table_ocr_endpoint_keeps_candidates_separate_from_experiment_payload(monkeypatch):
    from app import ocr_service

    monkeypatch.setattr(ocr_service, "recognize_numeric_candidates", lambda content: {
        "candidates": [{
            "raw_text": "12.5", "value": "12.5", "confidence": 0.96,
            "bbox": [[0, 0], [10, 0], [10, 10], [0, 10]],
        }],
        "detected_text_count": 1,
    })
    response = client.post(
        "/api/ocr/table",
        data={"experiment_id": "polarization", "table_id": "malus"},
        files={"image": ("table.png", b"fake-image", "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["candidates"][0]["value"] == "12.5"
    assert "expectedRange" not in response.text


def test_generic_schema_exposes_canonical_field_rules():
    response = client.get("/api/experiments/michelson/schema")
    assert response.status_code == 200
    assert response.json()["schemaVersion"] == "2.0"
    field = response.json()["definition"]["methods"][0]["columns"][0]
    assert field["type"] in {"integer", "float"}
    assert field["expected_range"][0] < field["expected_range"][1]


def test_expected_range_is_a_warning_not_a_blocking_error():
    response = client.post("/api/experiments/michelson/validate", json={"data": {
        "wavelength": {"rows": [{"fringe_count": 50, "position": 999999}], "params": {}}
    }})
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert any(item["code"] == "expected_range" for item in body["warnings"])


def test_health_reports_the_deployed_build_identity():
    """部署后必须能从 /health 看出「哪一份代码在应答」，而不是只信 URL。"""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "physicslab-api"
    assert isinstance(body["commit"], str) and body["commit"]
    assert isinstance(body["revision"], str) and body["revision"]
    assert body["experiments"] == 12


def _bridge_data(**cu50_params):
    return {"data": {
        "balanced": {"rows": [{"rn": 271.4}] * 3,
                     "params": {"ra": 1000, "rb": 5000, "us": 3.0, "t_room": 20.9}},
        "cu50": {"rows": [{"temperature": 20 + 3 * index, "u0": 8.8 * index} for index in range(10)],
                 "params": {"us": 3, **cu50_params}},
        "capacitor": {"rows": [{"cn": 0.833, "rn": 14.4}] * 3,
                      "params": {"ra": 100, "rb": 120, "f": 1000}},
        "inductor": {"rows": [{"cn": 0.5, "rn": 1250}] * 3,
                     "params": {"ra": 100, "rb": 100, "f": 1000}},
    }}


def test_report_gate_requires_the_measured_pre_balance_reading():
    """预平衡 Rn 是现场实测值：绕过前端直接调 API 也不能缺（否则公式无法反解）。"""
    blocked = client.post("/api/experiments/bridge/report", json=_bridge_data(), params={"fmt": "pdf"})
    assert blocked.status_code == 400
    assert "卧式电桥测 Cu50" in blocked.json()["detail"]

    allowed = client.post("/api/experiments/bridge/report",
                          json=_bridge_data(rn=54.6), params={"fmt": "pdf"})
    assert allowed.status_code == 200
    assert allowed.content[:4] == b"%PDF"


def test_merged_modern_physics_entry_and_legacy_routes_coexist():
    listing = client.get("/api/experiments").json()["experiments"]
    ids = {item["id"] for item in listing}
    assert "photoelectric-franck-hertz" in ids
    assert "photoelectric" not in ids
    assert len(ids) == 12
    legacy_listing = client.get("/api/experiments?include_legacy=true").json()["experiments"]
    assert any(item["id"] == "photoelectric" and item.get("legacy")
               for item in legacy_listing)
    assert client.get("/api/experiments/photoelectric/config").status_code == 200
    merged = client.get("/api/experiments/photoelectric-franck-hertz/config")
    assert merged.status_code == 200
    assert {method["id"] for method in merged.json()["methods"]} >= {"planck", "curve", "peaks"}


def test_soundlight_config_exposes_all_lecture_methods():
    response = client.get("/api/experiments/sound-light/config")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        "air_resonance", "water_phase", "tof", "light_sine",
        "light_square", "light_lissajous",
    ]


def test_square_wave_process_keeps_its_public_method_contract():
    response = client.post("/api/experiments/sound-light/process", json={
        "method": "light_square",
        "rows": {
            "T": [2.19, 2.20, 2.21],
            "dt": [0.8, 1.0, 1.2],
            "x1": [100.0, 100.0, 100.0],
            "x2": [463.36, 554.20, 645.04],
        },
        "params": {"f_mhz": 150.0},
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["method"] == "light_square"
    assert body["method_name"] == "光速测量（方波）"
    assert any(item["key"] == "c_exp" for item in body["results"])


def test_missing_halfwave_degree_is_not_silently_converted_to_zero():
    response = client.post("/api/experiments/polarization/process", json={
        "halfwave": {
            "initial": {"c_deg": None, "p2_deg": None},
            "rows": [{"offset": 0, "c_deg": None, "p2_deg": None}],
        }
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validation_error"
    assert any("数据不完整" in error for error in body["errors"])


def test_blank_halfwave_baseline_is_named_not_crashed():
    """A null 初始读数 used to reach float() and surface as "float() argument must be
    a string or a real number, not 'NoneType'" in the results panel."""
    payload = {
        "bg_uw": 0.0543,
        "theta_qwp": 30.0,
        "halfwave": {
            "initial": {"c_deg": None, "c_min": 0, "p2_deg": None, "p2_min": 0},
            "rows": [{"offset": float(o), "c_deg": 70.0, "c_min": 0.0,
                      "p2_deg": 70.0, "p2_min": 0.0} for o in range(0, 60, 10)],
        },
    }
    response = client.post("/api/experiments/polarization/process", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validation_error"
    assert any("初始读数" in error for error in body["errors"])
    assert "NoneType" not in response.text


# ─── non-finite results and crash reporting ─────────────────────────────────
#
# Regression: an intensity reading at or below the background I0 makes the
# extinction ratio I_max/I_min infinite. That inf reached json.dumps, which
# raises ``ValueError: Out of range float values are not JSON compliant``, so the
# endpoint answered with a CORS-less 500. The browser could not read the response
# and told the student "网络错误，请确认后端服务已启动", losing the real error.

import pytest  # noqa: E402  (kept next to the tests it serves)


def _malus_with_reading_at_background(bg_uw: float) -> dict:
    rows = [{"theta": float(t), "i_left": 100.0 - t * 0.9, "i_right": 98.0 - t * 0.85}
            for t in range(0, 360, 30)]
    # Crossed polarizers can read 0.0 on both channels, which drives the mean of
    # that row to zero -> I_min = 0 -> extinction ratio I_max/I_min diverges.
    rows[3]["i_left"] = rows[3]["i_right"] = 0.0
    return {"bg_uw": bg_uw, "theta_qwp": 30.0, "malus": {"rows": rows}}


@pytest.mark.parametrize("bg_uw", [0.0, 40.0])
def test_nonfinite_ratio_is_reported_as_null_not_a_crash(bg_uw):
    response = client.post("/api/experiments/polarization/process",
                           json=_malus_with_reading_at_background(bg_uw))
    assert response.status_code == 200
    assert '"extinction_ratio":null' in response.text
    # Check the numbers (plots are base64 and can contain these substrings by chance).
    payload_json = response.json()
    payload_json.pop("plots", None)
    encoded = json.dumps(payload_json)
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert response.json()["status"] == "success"


@pytest.mark.parametrize("fmt", ["docx", "pdf"])
@pytest.mark.document
def test_report_renders_when_a_reading_sits_at_the_background(fmt):
    response = client.post(f"/api/experiments/polarization/report?fmt={fmt}",
                           json=_malus_with_reading_at_background(40.0))
    assert response.status_code == 200
    head = response.content[:5]
    assert head.startswith(b"%PDF") if fmt == "pdf" else head.startswith(b"PK")


def test_nonfinite_values_serialise_as_null():
    from app.main import SafeJSONResponse

    body = SafeJSONResponse({
        "inf": float("inf"), "neg": float("-inf"), "nan": float("nan"),
        "ok": 1.5, "nested": [float("inf"), 2],
    }).body.decode("utf-8")
    assert body == '{"inf":null,"neg":null,"nan":null,"ok":1.5,"nested":[null,2]}'


def test_unhandled_crash_returns_json_with_cors_headers():
    """A crash must stay readable by the browser, not surface as a network error."""
    from app.main import app

    @app.get("/__boom_probe")
    async def _boom():  # pragma: no cover - only raised, never served
        raise RuntimeError("probe")

    try:
        response = client.get("/__boom_probe",
                              headers={"Origin": "https://bogger111.github.io"})
    finally:
        app.router.routes = [route for route in app.router.routes
                             if getattr(route, "path", None) != "/__boom_probe"]

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "https://bogger111.github.io"
    assert "内部错误" in response.json()["detail"]
