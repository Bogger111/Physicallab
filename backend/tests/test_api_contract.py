"""In-process API contract checks; no server process is started."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


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
