"""The typical-data reference must be formula-consistent and handwriting-sized.

Every published experiment ships `data_reference.json` next to its config.  This
test re-derives the values from the experiment's own formulas and standard
constants, so a wrong digit cannot silently reach the "数据特征参考" card, and it
enforces handwriting precision instead of machine precision.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from app.data_collection import valid_stable_field_id

BACKEND = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = BACKEND / "experiments"

#: public catalogue id -> directory holding its config and reference data
FOLDERS = {
    "polarization": "polarization",
    "sound-light": "soundlight",
    "multimeter": "multimeter",
    "bridge": "bridge",
    "solar-cell": "solar_cell",
    "gmr": "gmr",
    "nmr": "nmr",
    "viscosity": "viscosity",
    "surface-tension": "surface_tension",
    "thermal-conductivity": "thermal_conductivity",
    "michelson": "michelson",
    "photoelectric-franck-hertz": "photoelectric_franck_hertz",
}

NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def reference(experiment_id: str) -> dict:
    path = EXPERIMENTS_DIR / FOLDERS[experiment_id] / "data_reference.json"
    assert path.is_file(), f"{experiment_id}: missing {path.name}"
    return json.loads(path.read_text(encoding="utf-8"))


def config(experiment_id: str) -> dict | list:
    return json.loads((EXPERIMENTS_DIR / FOLDERS[experiment_id] / "config.json").read_text(encoding="utf-8"))


def entry(experiment_id: str, name_fragment: str) -> dict:
    for item in reference(experiment_id)["data_reference"]:
        if name_fragment in item["name"]:
            return item
    raise AssertionError(f"{experiment_id}: no entry matching {name_fragment!r}")


def numbers(text: str) -> list[float]:
    return [float(token) for token in NUMBER.findall(text.replace("−", "-"))]


def single(text: str) -> float:
    values = numbers(text)
    assert len(values) == 1, text
    return values[0]


def params(experiment_id: str, method_id: str) -> dict:
    cfg = config(experiment_id)
    for method in (cfg if isinstance(cfg, list) else cfg.get("methods", [])):
        if method["id"] == method_id:
            return {p["key"]: p["default"] for p in method.get("params", []) or []}
    raise AssertionError(f"{experiment_id}: unknown method {method_id}")


# ------------------------------------------------------------------ structure

@pytest.mark.parametrize("experiment_id", sorted(FOLDERS))
def test_reference_structure(experiment_id):
    document = reference(experiment_id)
    assert document["experiment_id"] == experiment_id
    assert document["note"], "the card must carry a disclaimer"
    assert "参考" in document["note"], "the card must be framed as a reference"
    assert ("不是标准答案" in document["note"]) or ("仅用于" in document["note"]), document["note"]
    entries = document["data_reference"]
    assert 3 <= len(entries) <= 6, f"{experiment_id}: {len(entries)} entries"
    for item in entries:
        assert item["name"], experiment_id
        assert 3 <= len(item["example"]) <= 6, (experiment_id, item["name"], item["example"])
        assert 1 <= len(item["pattern"]) <= 3, (experiment_id, item["name"], item["pattern"])
        for value in item["example"]:
            assert NUMBER.search(value), (experiment_id, value)


@pytest.mark.parametrize("experiment_id", sorted(FOLDERS))
def test_examples_use_handwriting_precision(experiment_id):
    for item in reference(experiment_id)["data_reference"]:
        for value in item["example"]:
            assert "e-" not in value.lower() and "×10" not in value, (experiment_id, value)
            for token in NUMBER.findall(value):
                decimals = len(token.split(".")[1]) if "." in token else 0
                assert decimals <= 4, f"{experiment_id}: {value!r} is not handwriting precision"
                assert len(token.replace("-", "").replace(".", "")) <= 6, \
                    f"{experiment_id}: {value!r} carries too many digits"


@pytest.mark.parametrize("experiment_id", sorted(FOLDERS))
def test_field_references_match_the_collection_schema(experiment_id):
    for item in reference(experiment_id)["data_reference"]:
        field = item["field"]
        if field is None:
            continue
        assert re.fullmatch(r"[a-z0-9_]+\.rows\.\*\.\w+", field), (experiment_id, field)
        method, _, _, key = field.split(".")
        assert valid_stable_field_id(experiment_id, f"{method}.rows.row_01.{key}"), \
            f"{experiment_id}: {field} is not a stable field id"


# ------------------------------------------------------- formula re-derivation

def test_multimeter_reads_back_the_set_value():
    example = entry("multimeter", "被检表读数")["example"]
    listed = [single(value) for value in example]
    assert listed == sorted(listed)
    # 20.04 mV measured against 20 mV set -> slope within 5% of 1
    assert abs(single(example[0]) / 20 - 1) < 0.05


def test_polarization_obeys_malus_law():
    example = entry("polarization", "透射光强 I（马吕斯定律）")["example"]
    angles = [0, 30, 45, 60, 90]
    intensities = [single(value) for value in example]
    assert len(example) == len(angles), example
    assert intensities == sorted(intensities, reverse=True)
    for angle, intensity in zip(angles, intensities):
        theory = 100.0 * math.cos(math.radians(angle)) ** 2 + 0.1
        assert abs(intensity - theory) <= max(0.3, 0.02 * theory), (angle, intensity, theory)


def test_half_wave_plate_rotates_by_twice_the_offset():
    example = entry("polarization", "P2 消光位置")["example"]
    offsets = [0, 10, 20, 30]
    positions = [single(value) for value in example]
    for offset, position in zip(offsets, positions):
        assert abs(position - (20 + 2 * offset)) < 0.5


def test_sound_speed_air_series_gives_the_standard_value():
    example = entry("sound-light", "共振位置 l（空气中共振法）")["example"]
    positions = [single(value) for value in example]
    spacing = (positions[-1] - positions[0]) / (len(positions) - 1)
    assert abs(spacing - 4.5) < 0.05
    frequency_khz = params("sound-light", "air_resonance")["f_khz"]
    speed = 2 * frequency_khz * 1e3 * spacing * 1e-3
    assert 330 <= speed <= 350, speed


def test_sound_speed_water_series_gives_the_standard_value():
    example = entry("sound-light", "同相位位置 l（水中相位法）")["example"]
    positions = [single(value) for value in example]
    spacing = (positions[-1] - positions[0]) / (len(positions) - 1)
    frequency_mhz = params("sound-light", "water_phase")["f_mhz"]
    speed = 2 * frequency_mhz * 1e6 * spacing * 1e-3
    assert 1450 <= speed <= 1520, speed


def test_time_of_flight_pairs_are_linear():
    example = entry("sound-light", "传播距离 L 与飞行时间 T")["example"]
    points = [numbers(value) for value in example]
    slopes = [(length) / (time) for length, time in points]
    speeds = [slope * 1e3 for slope in slopes]
    for speed in speeds:
        assert 330 <= speed <= 350, speed


def test_light_speed_from_delta_x_over_delta_t():
    example = entry("sound-light", "反射镜位移 Δx")["example"]
    delta_x = [single(value) for value in example[:3]]
    delta_t = [0.80, 1.00, 1.20]
    ratios = [dx / dt for dx, dt in zip(delta_x, delta_t)]
    assert max(ratios) - min(ratios) < 1.0, ratios
    # c = 2 f T (dx/dt) with f = 150 MHz and T = 2.20 us
    frequency_mhz = params("sound-light", "light_sine")["f_mhz"]
    speed = 2 * frequency_mhz * 1e6 * 2.20e-6 * (ratios[0] * 1e3)
    assert 2.9e8 <= speed <= 3.1e8, speed


def test_bridge_cu50_series_rises_with_temperature():
    example = entry("bridge", "温度 t 与输出 U0（Cu50）")["example"]
    values = [numbers(value) for value in example]
    for (temperature, u0), (next_temperature, next_u0) in zip(values, values[1:]):
        assert next_temperature > temperature and next_u0 > u0, example
        assert (next_u0 - u0) / (next_temperature - temperature) == pytest.approx(0.16, abs=0.05)


def test_bridge_thermistor_falls_with_temperature():
    example = entry("bridge", "热敏电阻阻值 R")["example"]
    values = [numbers(value) for value in example]
    resistances = [value[-1] for value in values]
    assert resistances == sorted(resistances, reverse=True), example
    assert 2000 >= resistances[0] >= 500, example


def test_solar_cell_operating_point_and_fill_factor():
    iv = entry("solar-cell", "电压 U 与电流 I（伏安曲线）")["example"]
    points = [numbers(value) for value in iv]
    power = [voltage * current for voltage, current in points]
    peak = max(power)
    isc = params("solar-cell", "iv")["isc"]
    uoc = params("solar-cell", "iv")["uoc"]
    fill_factor = peak / (uoc * isc)
    assert peak == pytest.approx(615, rel=0.05), power
    assert 0.5 <= fill_factor <= 0.9, fill_factor
    assert points[-1][1] == 0, iv


def test_solar_cell_charge_stays_within_the_safety_limit():
    for name in ("直接充电", "DC-DC"):
        example = entry("solar-cell", f"{name}")["example"]
        voltages = [numbers(value)[1] for value in example]
        assert voltages == sorted(voltages), example
        assert voltages[-1] <= 11.0, example
        assert voltages[0] == 0, example
    direct = entry("solar-cell", "直接充电")["example"]
    dcdc = entry("solar-cell", "DC-DC")["example"]
    assert numbers(dcdc[-1])[1] == numbers(direct[-1])[1], "both branches charge to the same cutoff"


def test_gmr_single_branch_sensitivity_is_physical():
    example = entry("gmr", "励磁电流与输出电压")["example"]
    zero = next(value for value in example if value.startswith("0 mA"))
    positive = next(value for value in example if value.startswith("200 mA"))
    output_zero = numbers(zero)[-1]
    excitation, output_positive = numbers(positive)[:2]
    field_gs = 0.31416 * excitation
    sensitivity = (output_positive - output_zero) / field_gs
    assert 0.1 <= sensitivity <= 0.5, sensitivity


def test_nmr_gyromagnetic_ratio():
    hydrogen = entry("nmr", "射频频率 ν")["example"]
    fields = [single(value) for value in entry("nmr", "共振磁场 B0")["example"][:3]]
    frequencies = [single(value) for value in hydrogen[:3]]
    gamma = (frequencies[-1] - frequencies[0]) / (fields[-1] - fields[0]) * 1e3
    assert gamma == pytest.approx(42.58, rel=0.02), gamma
    g_factor = gamma / 7.6225914
    assert g_factor == pytest.approx(5.5857, rel=0.03), g_factor


def test_viscosity_is_physical_and_decreasing():
    timing = entry("viscosity", "同温度四次落球计时")["example"]
    temperatures = [single(value) for value in entry("viscosity", "温度 T")["example"]]
    assert temperatures == sorted(temperatures) and len(temperatures) == 5
    times = [numbers(value)[1] for value in timing]
    assert times == sorted(times, reverse=True), timing
    eta = [numbers(value)[-1] for value in entry("viscosity", "粘滞系数 η")["example"]]
    assert eta == sorted(eta, reverse=True), eta
    for value in eta:
        assert 0.1 <= value <= 2.0, eta


def test_surface_tension_examples_reproduce_the_standard_value():
    d1, d2 = params("surface-tension", "pull_off")["d1"] / 100, params("surface-tension", "pull_off")["d2"] / 100
    sensitivity = params("surface-tension", "salt_pull_off")["sensitivity"]
    pull_off = entry("surface-tension", "拉脱法")["example"]
    up, down = (numbers(value)[-1] for value in pull_off[:2])
    delta_u = abs(up - down)
    sigma = delta_u / sensitivity / (math.pi * (d1 + d2))
    assert sigma == pytest.approx(0.07275, rel=0.05), sigma

    capillary_params = params("surface-tension", "capillary")
    weight = entry("surface-tension", "毛细管法")["example"]
    heights = [single(value) for value in weight if value.startswith("h")]
    diameter = [single(value) for value in weight if "内径" in value][0] / 1000
    height = heights[0] / 1000
    sigma_capillary = 0.25 * capillary_params["density"] * capillary_params["g"] * diameter * (height + diameter / 6)
    assert sigma_capillary == pytest.approx(0.07275, rel=0.05), sigma_capillary


def test_thermal_conductivity_is_an_insulator_and_drifts_slowly():
    cooling = entry("thermal-conductivity", "冷却温度 TC")["example"]
    temperatures = [numbers(value)[-1] for value in cooling]
    assert temperatures == sorted(temperatures, reverse=True), cooling
    result = entry("thermal-conductivity", "冷却参数与结果")["pattern"][0]
    assert "0.1" in result
    heating = entry("thermal-conductivity", "升温温度 TA / TC")
    assert "15" in " ".join(heating["pattern"]), "the steady-state difference should be visible"
    rows = [numbers(value) for value in heating["example"]]
    for row in rows:
        assert row[1] - row[2] == pytest.approx(15.0, abs=0.1), row
    temperatures = [row[1] for row in rows]
    assert temperatures == sorted(temperatures), heating["example"]


def test_michelson_wavelength():
    positions = [single(value) for value in entry("michelson", "反射镜位置 d")["example"]]
    step = positions[1] - positions[0]
    fringes = params("michelson", "wavelength")["fringes_per_step"]
    wavelength_nm = 2 * step / fringes * 1e6
    assert wavelength_nm == pytest.approx(632.8, rel=0.02), wavelength_nm
    delta_d = single(next(value for value in entry("michelson", "逐差位移与波长")["example"] if "Δd" in value))
    assert 2 * delta_d / (5 * fringes) * 1e6 == pytest.approx(632.8, rel=0.02)


def test_photoelectric_planck_constant():
    pairs = [numbers(value) for value in entry("photoelectric-franck-hertz", "零电流法")["example"]]
    wavelengths = [pair[0] for pair in pairs]
    stopping = [pair[1] for pair in pairs]
    assert wavelengths == sorted(wavelengths) and stopping == sorted(stopping, reverse=True)
    planck = 6.62607015e-34
    electron = 1.602176634e-19
    light = 2.99792458e8
    planck_measured = electron * (stopping[-1] - stopping[0]) / (light / (wavelengths[-1] * 1e-9) - light / (wavelengths[0] * 1e-9))
    assert planck_measured == pytest.approx(planck, rel=0.1), planck_measured


def test_franck_hertz_peak_spacing():
    peaks = [single(value) for value in entry("photoelectric-franck-hertz", "峰值电压")["example"]]
    assert peaks == sorted(peaks) and len(peaks) >= 5
    spacings = [b - a for a, b in zip(peaks, peaks[1:])]
    assert max(spacings) - min(spacings) < 0.2, spacings
    assert spacings[0] == pytest.approx(4.9, abs=0.1), spacings
    assert "4.90" in " ".join(entry("photoelectric-franck-hertz", "峰值电压")["pattern"])
