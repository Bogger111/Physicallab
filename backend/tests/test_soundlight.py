"""Regression tests for the sound/light calculation engine and report chain.

All values below are synthetic, hand-checkable fixtures. They do not claim
validation against complete real experimental data.
"""

import json
import math
from pathlib import Path

from experiments.soundlight import docs, engine


def _light_rows():
    return {
        "T": [1.23456, 1.23456, 1.23456],
        "dt": [1.0, 1.0, 1.0],
        "x1": [0.0, 0.0, 0.0],
        "x2": [809.4321, 809.4321, 809.4321],
    }


def test_air_resonance_known_result_and_temperature_formula():
    rows = {"l": [float(i * 4.5) for i in range(12)]}
    run = engine.analyze("air_resonance", rows,
                         {"temperature_degC": 25.0, "f_khz": 38.0})
    assert run["status"] == "success"
    assert math.isclose(run["arrays"]["dlm"], 4.5)
    assert math.isclose(run["arrays"]["v_exp"], 342.0)
    expected = 331.45 * math.sqrt(1.0 + 25.0 / 273.15)
    assert math.isclose(run["arrays"]["v_theory"], expected)


def test_water_phase_uncertainty_uses_six_progressive_differences():
    first = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    delta = [0.70, 0.72, 0.74, 0.76, 0.78, 0.80]
    rows = {"l": first + [first[i] + 6 * delta[i] for i in range(6)]}
    run = engine.analyze("water_phase", rows, {"f_mhz": 1.0})
    assert run["status"] == "success"
    a = run["arrays"]
    expected_s = 0.03741657386773942
    assert math.isclose(a["dlm"], 0.75)
    assert math.isclose(a["v"], 1500.0)
    assert math.isclose(a["s"], expected_s)
    assert math.isclose(a["u_a_v"], 2e6 * 2.571 * expected_s / math.sqrt(6) * 1e-3)


def test_progressive_difference_accepts_consistent_reverse_reading_direction():
    rows = {"l": [100.0 - i * 4.5 for i in range(12)]}
    run = engine.analyze("air_resonance", rows,
                         {"temperature_degC": 25.0, "f_khz": 38.0})
    assert run["status"] == "success"
    assert math.isclose(run["arrays"]["dlm"], 4.5)


def test_light_report_uses_engine_full_precision_result():
    run = engine.analyze("light_sine", _light_rows(), {"f_mhz": 150.0})
    assert run["status"] == "success"
    expected = 150e6 * 2 * 1.23456 * 809.4321 * 1e-3
    assert math.isclose(run["arrays"]["c_exp"], expected)
    text = "\n".join(
        block.get("text", "")
        for block in docs._proc_2a("light_sine", run)
    )
    assert f"= {expected:.0f} m/s" in text
    assert "299895000 m/s" not in text


def test_square_wave_reuses_formula_but_keeps_method_identity():
    sine = engine.analyze("light_sine", _light_rows(), {"f_mhz": 150.0})
    square = engine.analyze("light_square", _light_rows(), {"f_mhz": 150.0})
    assert square["status"] == "success"
    assert square["method"] == "light_square"
    assert square["method_name"] == "光速测量（方波）"
    assert square["arrays"]["c_exp"] == sine["arrays"]["c_exp"]


def test_zero_delta_t_is_rejected_without_dropping_the_point():
    rows = _light_rows()
    rows["dt"][1] = 0.0
    run = engine.analyze("light_sine", rows, {"f_mhz": 150.0})
    assert run["status"] == "validation_error"
    assert any("必须全部大于零" in error for error in run["errors"])


def test_report_never_declares_synthetic_data_correct_or_trustworthy():
    run = engine.analyze("light_sine", _light_rows(), {"f_mhz": 150.0})
    blocks = docs._err_sources_blocks([("light_sine", run)])
    text = "\n".join(block.get("text", "") for block in blocks)
    assert "测量与数据处理正确" not in text
    assert "结果可信" not in text
    assert "是否符合实验要求需结合原始记录" in text


def test_public_config_matches_engine_columns_and_defaults():
    config_path = (Path(__file__).parents[1] / "experiments" / "soundlight"
                   / "config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert [item["id"] for item in config] == [
        "air_resonance", "water_phase", "tof", "light_sine",
        "light_square", "light_lissajous",
    ]
    for item in config:
        engine_id = "light_sine" if item["id"] == "light_square" else item["id"]
        config_columns = [(col["key"], col["count"])
                          for col in item["table_cols"]]
        engine_columns = [(key, count)
                          for key, count, _label in engine._COLUMNS[engine_id]]
        assert config_columns == engine_columns
        config_defaults = {param["key"]: param["default"]
                           for param in item["params"]}
        assert config_defaults == engine._PARAM_DEFAULTS[engine_id]
