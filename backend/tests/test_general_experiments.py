"""Synthetic coverage for every configuration-driven experiment.

These fixtures exercise formulas and document assembly.  They are not a
substitute for complete real laboratory records.
"""

import io
import math
import zipfile

import fitz
import numpy as np
import pytest

from app.main import app
from experiments.core import documents as docs
from experiments.core.registry import registry
from fastapi.testclient import TestClient


CONFIG_IDS = (
    "multimeter", "bridge", "photoelectric", "franck-hertz", "solar-cell",
    "gmr", "nmr", "viscosity", "surface-tension", "thermal-conductivity",
    "michelson",
)
CONFIGS = [registry.get(experiment_id).config for experiment_id in CONFIG_IDS]


def process_experiment(experiment_id, data):
    return registry.get(experiment_id).process(data)


LECTURE_METHODS = {
    "multimeter": {"voltage", "current", "resistance", "unknown", "ac_voltage", "ac_current"},
    "bridge": {"balanced", "cu50", "thermistor", "capacitor", "inductor"},
    "photoelectric": {"planck", "compensation", "iv_436", "iv_546", "saturation"},
    "franck-hertz": {"curve", "peaks", "parameter_curve", "higher_curve"},
    "solar-cell": {"iv", "shading", "charge_direct", "charge_dcdc", "fan", "load_dcdc", "inverter"},
    "gmr": {"transfer", "resistance", "current_sensor"},
    "nmr": {"waveform", "hydrogen", "fluorine", "pure_water"},
    "viscosity": {"diameter", "viscosity", "diameter_effect"},
    "surface-tension": {"calibration", "pull_off", "capillary", "salt_pull_off", "salt_capillary"},
    "thermal-conductivity": {"geometry", "heating", "cooling"},
    "michelson": {"wavelength", "observations"},
}


def _payload(rows, **params):
    return {"rows": rows, "params": params}


def fixtures():
    # 讲义 (12) 卧式电桥：反解式里的 R 就是预平衡 Rn（= Cu50 室温阻值），ΔR 相对预平衡温度
    bridge_rn = 50 * (1 + 0.004280 * 20)
    bridge_cu = []
    for t in range(20, 50, 3):
        dr = 50 * 0.004280 * (t - 20)
        bridge_cu.append({"temperature": t, "u0": 3 * dr / (4 * bridge_rn + 2 * dr) * 1000})
    # 讲义 (13) 立式电桥：MF51 2.7K（B≈3235 K，讲义表1），Ra=Rb=100 Ω，Rn 取室温预平衡值
    bridge_rn_thermistor = 2700 * math.exp(3235 * (1 / 293.15 - 1 / 298.15))
    bridge_thermistor = []
    for t in range(20, 50, 3):
        spread = bridge_rn_thermistor + 100
        dr = 2700 * math.exp(3235 * (1 / (t + 273.15) - 1 / 298.15)) - bridge_rn_thermistor
        bridge_thermistor.append({"temperature": t,
                                  "u0": 3 * 100 * dr / (spread * (spread + dr)) * 1000})
    photo_rows = []
    for wl in (365, 405, 436, 546, 577):
        nu = 2.99792458e8 / (wl * 1e-9)
        us = (6.62607015e-34 / 1.602176634e-19) * nu - 2.0
        photo_rows.append({"wavelength": wl, "us1": us-.002, "us2": us,
                           "us3": us+.002, "us4": us})
    gmr_res = []
    for current in np.linspace(-200, 200, 21):
        field = .31416 * current
        ra = 400 * (1 + .08 * math.exp(-(field / 30) ** 2))
        rb = 400 * (1 + .01 * math.exp(-(field / 30) ** 2))
        gmr_res.append({"excitation": current, "ir_a": 4000/ra,
                        "ir_b": 4000/rb})
    return {
        "multimeter": {
            "voltage": _payload([{"set":x,"measured":1.001*x+.02} for x in range(0,201,20)]),
            "current": _payload([{"set":x,"measured":.999*x+.01} for x in range(0,21,2)]),
            "resistance": _payload([{"set":x/10,"measured":1.002*x/10} for x in range(0,21,2)]),
            "unknown": _payload([{"reference":1.2,"measured":1.202} for _ in range(3)]),
            "ac_voltage": _payload([{"set":x,"measured":.998*x+.03} for x in range(0,201,20)]),
            "ac_current": _payload([{"set":x,"measured":1.002*x+.01} for x in range(0,21,2)]),
        },
        "bridge": {
            "balanced": _payload([{"rn": 271.4} for _ in range(3)], ra=1000, rb=5000, t_room=20),
            "cu50": _payload(bridge_cu, us=3, rn=round(bridge_rn, 2)),
            "capacitor": _payload([{"cn":.833333,"rn":14.4} for _ in range(3)],ra=100,rb=120,f=1000),
            "inductor": _payload([{"cn":.5,"rn":1250} for _ in range(3)],ra=100,rb=100,f=1000),
            "thermistor": _payload(bridge_thermistor, us=3, r_prime=100,
                                   rn=round(bridge_rn_thermistor, 1)),
        },
        "photoelectric": {
            "planck": _payload(photo_rows),
            "iv_436": _payload([{"voltage":u,"current":100*(1-math.exp(-(u+4)/5))} for u in range(-4,31,2)]),
            "iv_546": _payload([{"voltage":u,"current":70*(1-math.exp(-(u+4)/6))} for u in range(-4,31,2)]),
            "saturation": _payload([{"wavelength":wl,"diameter":d,"i1":.8*d*d,"i2":.8*d*d,"i3":.8*d*d} for wl in (436,546) for d in (2,4,8)]),
            "compensation": _payload([{**row, "us4": None} for row in photo_rows], aperture=4),
        },
        "franck-hertz": {
            "curve": _payload([{"voltage":u,"current":20+u+.5*u*math.sin(2*math.pi*u/4.9)} for u in range(61)],temperature=220,vf=.9,vg1k=1.5,vg2p=1.3),
            "peaks": _payload([{"peak_voltage":5.6+4.9*i} for i in range(6)]),
            "parameter_curve": _payload([{"voltage":u,"current_reference":20+u,"current_variant":21+1.05*u} for u in range(0,31,2)],temperature=220,vf=.9,vg1k=1.5,vg2p=1.3),
            "higher_curve": _payload([{"voltage":u,"current":8+u+.3*u*math.sin(u)} for u in range(0,31,2)],temperature=120,vf=.9,vg2p=1.3),
        },
        "solar-cell": {
            "iv": _payload([{"voltage":u,"current":80*max(0,1-(u/12)**8)} for u in (1,2,4,6,8,10,10.2,10.4,10.6,10.8,11,11.2,11.4,11.6,11.8,12)],isc=80,uoc=12),
            "shading": _payload([{"condition":i,"isc":80-8*i} for i in range(7)]),
            "charge_direct": _payload([{"time":t,"voltage":min(11,1.2*t),"current":60-3*t} for t in range(10)]),
            "charge_dcdc": _payload([{"time":t,"voltage":min(11,1.6*t),"current":50} for t in range(8)]),
            "fan": _payload([{"voltage":8,"current":70},{"voltage":10,"current":80}]),
            "load_dcdc": _payload([{"voltage_before":3,"current_before":20,"voltage_after":9,"current_after":30}]),
            "inverter": _payload([{"input_voltage":11,"input_current":400,"lit_code":1}]),
        },
        "gmr": {
            # 讲义：励磁电流递增、递减各一支；平方回线两支斜率相反，零场输出相差约 26 mV（磁滞）
            "transfer": _payload(
                [{"excitation": i, "output": 25 + .2 * (.31416 * i), "direction": 1}
                 for i in np.linspace(-200, 200, 21)]
                + [{"excitation": i, "output": 51.39 - .2 * (.31416 * i), "direction": -1}
                   for i in np.linspace(200, -200, 21)]),
            "resistance": _payload(gmr_res,supply=2),
            "current_sensor": _payload([{"current":i,"output25":25+.03*i,"output100":100+.05*i} for i in range(-1000,1001,200)]),
        },
        "nmr": {
            "waveform": _payload([{"sample_code":1,"tail_count":8,"t1":5.0,"t2":5.1},{"sample_code":2,"tail_count":1,"t1":5.0,"t2":5.0}]),
            "hydrogen": _payload([{"field":b,"frequency":5.5857*7.6225914/1000*b} for b in np.linspace(235,280,10)]),
            "fluorine": _payload([{"field":b,"frequency":5.2567*7.6225914/1000*b} for b in np.linspace(250,300,10)]),
            "pure_water": _payload([{"field":b,"frequency":5.5857*7.6225914/1000*b} for b in np.linspace(235,280,10)]),
        },
        "viscosity": {
            "diameter": _payload([{"x1":10+i,"x2":11.5+i} for i in range(3)]),
            "viscosity": _payload([{"temperature":t,"t1":18-i,"t2":18.1-i,"t3":17.9-i,"t4":18-i} for i,t in enumerate((20,25,30,35,40))],distance=20,diameter=1.5,rho_ball=7800,rho_oil=950,tube_diameter=2,g=9.794),
            "diameter_effect": _payload([{"diameter":d,"t1":t,"t2":t+.1,"t3":t-.1,"t4":t} for d,t in ((1.0,30),(1.8,14),(2.4,9))],distance=20,temperature=40,rho_ball=7800,rho_oil=950,tube_diameter=2,g=9.794),
        },
        "surface-tension": {
            "calibration": _payload([{"mass":m,"u_up":1000*(m/1000*9.79338)+.1,"u_down":1000*(m/1000*9.79338)-.1} for m in np.arange(0,4,.5)],g=9.79338),
            "pull_off": _payload([{"u1":5,"u2":.2} for _ in range(5)],sensitivity=1000,d1=3.31,d2=3.496),
            "capillary": _payload([{"y1":20,"y2":10,"x1":5,"x2":5.8} for _ in range(5)],density=998,g=9.79338),
            "salt_pull_off": _payload([{"u1":5.2,"u2":.2} for _ in range(5)],concentration=5,sensitivity=1000,d1=3.31,d2=3.496),
            "salt_capillary": _payload([{"y1":19.5,"y2":10,"x1":5,"x2":5.8} for _ in range(5)],concentration=5,density=1035,g=9.79338),
        },
        "thermal-conductivity": {
            "geometry": _payload([{"dc":100,"hc":10,"db":100,"hb":8} for _ in range(5)]),
            "heating": _payload([{"time":2*i,"ta":50-.2*math.exp(-i/3),"tc":35-.2*math.exp(-i/3)} for i in range(15)]),
            "cooling": _payload([{"time":30*i,"temperature":40-.01*30*i} for i in range(16)],mass=500,specific_heat=394,t1=50,t2=35,dc=100,hc=10,db=100,hb=8),
        },
        "michelson": {
            "wavelength": _payload([
                {"fringe_count": 50 * (i + 1), "position": 10 + .01582 * i}
                for i in range(10)
            ], fringes_per_step=50),
            "observations": _payload([
                {"setup_code": i + 1, "pattern_code": 1,
                 "motion_code": 1 if i < 2 else 0,
                 "localized_code": 1 if i else 0}
                for i in range(3)
            ]),
        },
    }


@pytest.mark.parametrize("experiment_id", [item["id"] for item in CONFIGS])
def test_every_general_experiment_processes_synthetic_fixture(experiment_id):
    result = process_experiment(experiment_id, fixtures()[experiment_id])
    assert result["status"] == "success", result["errors"]
    required = {m["id"] for m in next(c for c in CONFIGS if c["id"] == experiment_id)["methods"] if m["required"]}
    assert required <= result["results"].keys()
    assert fixtures()[experiment_id].keys() <= result["results"].keys()
    assert all(math.isfinite(value) for values in result["results"].values() for value in values.values())


def test_key_physical_results():
    data = fixtures()
    assert process_experiment("bridge", data["bridge"])["results"]["cu50"]["alpha"] == pytest.approx(.00428, rel=1e-6)
    assert process_experiment("photoelectric", data["photoelectric"])["results"]["planck"]["h"] == pytest.approx(6.62607015e-34, rel=1e-6)
    assert process_experiment("franck-hertz", data["franck-hertz"])["results"]["peaks"]["v0"] == pytest.approx(4.9)
    assert process_experiment("nmr", data["nmr"])["results"]["hydrogen"]["g_factor"] == pytest.approx(5.5857)
    assert process_experiment("michelson", data["michelson"])["results"]["wavelength"]["wavelength"] == pytest.approx(632.8)


def test_bridge_uses_the_lecture_balance_equations():
    """讲义 (2)(12)(13)(25)(26)：反解式里的 R 是预平衡阻值，交流电桥的 rL/Q 按平衡条件取。"""
    run = process_experiment("bridge", fixtures()["bridge"])

    # 内容1：与「室温理论值」比较，而不是与 0 °C 的 50 Ω 比
    balanced = run["results"]["balanced"]
    assert balanced["rx_mean"] == pytest.approx(1000 / 5000 * 271.4)
    assert balanced["theory"] == pytest.approx(50 * (1 + 0.004280 * 20))
    assert balanced["relative_error"] < 0.5, balanced

    # 内容2：ΔRx = 4Rn·U0/(Us-2U0)，R0/α 应回到讲义理论值
    cu50 = run["results"]["cu50"]
    assert cu50["r0"] == pytest.approx(50, rel=1e-3)
    assert cu50["alpha"] == pytest.approx(0.004280, rel=1e-3)
    assert cu50["r0_error"] < 0.5, cu50

    # 内容5：rL = Ra·Rb/Rn、Q = ωLx/rL = ωCnRn（不能再出现 rL = Rn）
    inductor = run["results"]["inductor"]
    assert inductor["lx"] == pytest.approx(5.0)
    assert inductor["rl"] == pytest.approx(100 * 100 / 1250)
    assert inductor["q"] == pytest.approx(2 * math.pi * 1000 * 0.5e-6 * 1250)

    # 选做内容3：立式电桥反解出来的 R25 应与讲义表1 的 2700 Ω 一致
    thermistor = run["results"]["thermistor"]
    assert thermistor["b_constant"] == pytest.approx(3235, rel=0.05)
    assert thermistor["r25"] == pytest.approx(2700, rel=0.05)


def test_row_level_validation_errors_are_grouped_into_one_message():
    """只填了一半（有预填列）时，逐行报错要合并成一条，不能刷几十条。"""
    data = fixtures()["gmr"]
    data["resistance"]["rows"] = [{"excitation": row["excitation"]} for row in data["resistance"]["rows"]]
    run = process_experiment("gmr", data)
    assert run["status"] == "validation_error"
    assert len(run["errors"]) <= 3, run["errors"]
    assert any("共 21 行" in message for message in run["errors"]), run["errors"]
    # 结构化 issues 仍保留逐行行号，供前端高亮
    rows = [issue.get("row") for issue in run["validation"]["errors"] if issue.get("code") == "required"]
    assert len(rows) == 42 and min(rows) == 0 and max(rows) == 20


def test_gmr_transfer_splits_the_hysteresis_branches():
    """讲义：增磁/减磁两支要分开看，两支的差异就是磁滞；单一直线拟合会把两支抵消掉。"""
    result = process_experiment("gmr", fixtures()["gmr"])["results"]["transfer"]
    assert result["sensitivity"] == pytest.approx(0.2, rel=0.02)
    assert result["sensitivity_up"] == pytest.approx(0.2, rel=0.02)
    assert result["sensitivity_down"] == pytest.approx(-0.2, rel=0.02)
    assert result["hysteresis"] == pytest.approx(26.39, rel=0.02)
    assert result["r_squared"] == pytest.approx(1.0, abs=1e-9)
    assert result["b_max"] == pytest.approx(0.31416 * 200, rel=1e-6)


def test_gmr_transfer_names_a_lost_field_sign_instead_of_reporting_k_zero():
    """励磁电流丢了符号就再也恢复不了 B 的符号：要点名，不能默默给出 k≈0。"""
    data = fixtures()["gmr"]
    data["transfer"]["rows"] = [dict(row, excitation=abs(row["excitation"]))
                                for row in data["transfer"]["rows"]]
    run = process_experiment("gmr", data)
    assert any("非负值" in warning and "符号" in warning for warning in run["warnings"]), run["warnings"]
    # 报告正文也要带上这条提醒，别只在网页上弹一次
    text = "\n".join(block.get("text", "") for block in docs.report_blocks(registry.get("gmr"), data))
    assert "数据合理性提醒" in text and "非负值" in text


def test_gmr_transfer_warns_when_only_one_branch_is_measured():
    data = fixtures()["gmr"]
    data["transfer"]["rows"] = [row for row in data["transfer"]["rows"] if row["direction"] == 1]
    run = process_experiment("gmr", data)
    assert any("单一支路" in warning for warning in run["warnings"]), run["warnings"]


def test_bridge_flags_a_bridge_arm_rn_in_the_pre_balance_field():
    """把桥臂 1000 Ω 误填进「预平衡 Rn」时要点名，而不是静默放大 18 倍误差。"""
    data = fixtures()["bridge"]
    data["cu50"]["params"]["rn"] = 1000
    warnings = process_experiment("bridge", data)["warnings"]
    assert any("预平衡 Rn" in warning for warning in warnings), warnings


def test_bridge_names_the_missing_pre_balance_reading():
    """预平衡 Rn 是现场实测值：没填就要点名，绝不能用任何默认值偷偷代入。"""
    for method_id in ("cu50", "thermistor"):
        data = fixtures()["bridge"]
        data[method_id]["params"].pop("rn", None)
        result = process_experiment("bridge", data)
        assert any("预平衡 Rn" in message for message in result["errors"]), (method_id, result["errors"])


def test_bridge_withholds_the_theory_error_without_a_room_temperature():
    """没有室温就不该给出「理论偏差」（讲义比的是室温理论值，不是 0 °C 的 50 Ω）。"""
    data = fixtures()["bridge"]
    data["balanced"]["params"].pop("t_room", None)
    result = process_experiment("bridge", data)
    balanced = result["results"]["balanced"]
    assert "relative_error" not in balanced and "theory" not in balanced, balanced
    assert balanced["rx_mean"] == pytest.approx(1000 / 5000 * 271.4)
    assert any("室温" in warning for warning in result["warnings"]), result["warnings"]


def test_surface_tension_uses_calibrated_sensitivity_and_reports_water_errors():
    data = fixtures()["surface-tension"]
    for row in data["calibration"]["rows"]:
        row["u_up"] = -row["u_up"]
        row["u_down"] = -row["u_down"]
    data["pull_off"]["params"]["sensitivity"] = 123.0
    data["pull_off"]["params"]["sigma_reference"] = 0.07275
    data["capillary"]["params"]["sigma_reference"] = 0.07275

    run = process_experiment("surface-tension", data)
    fitted_k = run["results"]["calibration"]["sensitivity"]
    assert fitted_k > 0
    pull_off = run["results"]["pull_off"]
    expected_sigma = 4.8 / fitted_k / (math.pi * (3.31 + 3.496) / 100)

    assert pull_off["sensitivity_used"] == pytest.approx(fitted_k)
    assert pull_off["sigma"] == pytest.approx(expected_sigma)
    assert pull_off["absolute_error"] == pytest.approx(abs(expected_sigma - 0.07275))
    assert pull_off["relative_error"] == pytest.approx(abs(expected_sigma - 0.07275) / 0.07275 * 100)
    for method_id in ("pull_off", "capillary"):
        assert math.isfinite(run["results"][method_id]["sigma"])
        assert math.isfinite(run["results"][method_id]["absolute_error"])
        assert math.isfinite(run["results"][method_id]["relative_error"])

    report_text = "\n".join(
        block.get("text", "") for block in docs.report_blocks(registry.get("surface-tension"), data)
    )
    assert "最终结果：σ =" in report_text
    assert "相对误差 Er =" in report_text


@pytest.mark.document
def test_photoelectric_iv_wavelengths_share_one_combined_plot():
    data = fixtures()["photoelectric"]
    run = process_experiment("photoelectric", data)

    assert "iv_436" in run["plots"]
    assert "iv_546" not in run["plots"]
    assert "iv_curves" not in run["plots"]

    blocks = docs.report_blocks(registry.get("photoelectric"), data)
    matching_images = [
        block for block in blocks
        if block.get("kind") == "image" and block.get("b64") == run["plots"]["iv_436"]
    ]
    assert len(matching_images) == 1


@pytest.mark.document
def test_report_raw_table_trims_only_trailing_blank_template_rows():
    config = next(item for item in CONFIGS if item["id"] == "franck-hertz")
    method = next(item for item in config["methods"] if item["id"] == "higher_curve")
    payload = fixtures()["franck-hertz"]["higher_curve"]
    payload["rows"].insert(3, {"voltage": None, "current": None})
    payload["rows"].extend({"voltage": None, "current": ""} for _ in range(14))

    report_table = docs._method_raw_table(method, payload)
    blank_table = docs._method_raw_table(method, {}, blank=True)

    assert len(report_table["rows"]) == 18  # header + 16 values + one internal gap
    assert report_table["rows"][4] == [{"text": ""}, {"text": ""}]
    assert len(blank_table["rows"]) == method["rowCount"] + 1


def test_catalogue_and_generic_api_contract():
    client = TestClient(app)
    listing = client.get("/api/experiments")
    assert listing.status_code == 200
    assert len(listing.json()["experiments"]) == 12
    response = client.post("/api/experiments/michelson/process", json={"data": fixtures()["michelson"]})
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.document
@pytest.mark.parametrize("experiment_id", [item["id"] for item in CONFIGS])
def test_general_report_rejects_data_when_required_methods_are_missing(experiment_id):
    client = TestClient(app)
    config = next(item for item in CONFIGS if item["id"] == experiment_id)
    first_required = next(method for method in config["methods"] if method["required"])
    data = dict(fixtures()[experiment_id])
    data.pop(first_required["id"])
    response = client.post(
        f"/api/experiments/{experiment_id}/report?fmt=pdf",
        json={"data": data},
    )
    assert response.status_code == 400
    assert "必做实验" in response.json()["detail"]
    assert first_required["name"] in response.json()["detail"]


@pytest.mark.document
def test_general_report_rejects_an_incomplete_required_table():
    client = TestClient(app)
    data = fixtures()["multimeter"]
    data["voltage"]["rows"][-1]["measured"] = None
    response = client.post(
        "/api/experiments/multimeter/report?fmt=pdf",
        json={"data": data},
    )
    assert response.status_code == 400
    assert "直流电压" in response.json()["detail"]


def test_lecture_required_and_optional_content_is_represented():
    configs = {config["id"]: config for config in CONFIGS}
    assert configs.keys() == LECTURE_METHODS.keys()
    for experiment_id, expected in LECTURE_METHODS.items():
        assert {method["id"] for method in configs[experiment_id]["methods"]} == expected
    assert next(m for m in configs["photoelectric"]["methods"] if m["id"] == "iv_436")["rowCount"] == 34
    assert next(m for m in configs["franck-hertz"]["methods"] if m["id"] == "curve")["rowCount"] == 117
    assert next(m for m in configs["gmr"]["methods"] if m["id"] == "transfer")["rowCount"] == 42


@pytest.mark.document
def test_blank_record_rows_are_writable_and_tables_fit_portrait_a4():
    for config in CONFIGS:
        blocks = docs.record_blocks(registry.get(config["id"]))
        raw_tables = [block for block in blocks if block["kind"] == "table" and len(block["rows"]) > 2]
        assert raw_tables
        for table in raw_tables:
            assert table["fixed_row_height"] is True
            assert table["row_h"] >= .68
            assert len(table["rows"][0]) <= 8
            assert len(table["rows"]) * table["row_h"] <= 24


@pytest.mark.document
def test_all_general_report_structures_and_record_sheets():
    for config in CONFIGS:
        experiment_id=config["id"]
        blocks=docs.report_blocks(registry.get(experiment_id),fixtures()[experiment_id])
        assert sum(block["kind"]=="pagebreak" for block in blocks)==3
        breaks=[i for i,block in enumerate(blocks) if block["kind"]=="pagebreak"]
        assert all(block["kind"] in ("h3","table","spacer") for block in blocks[:breaks[0]])
        assert all(block["kind"] in ("h3","image","spacer") for block in blocks[breaks[0]+1:breaks[1]])
        assert blocks[breaks[1]+1]["text"].startswith("第三部分")
        record=registry.get(experiment_id).build_record_sheet("docx")
        with zipfile.ZipFile(io.BytesIO(record)) as archive:
            assert archive.testzip() is None


@pytest.mark.document
def test_michelson_report_renders_word_and_pdf():
    data=fixtures()["michelson"]
    docx=registry.get("michelson").build_report(data,"docx")
    with zipfile.ZipFile(io.BytesIO(docx)) as archive:
        assert archive.testzip() is None
        assert archive.read("word/document.xml").count(b'w:type="page"') >= 3
    pdf=fitz.open(stream=registry.get("michelson").build_report(data,"pdf"),filetype="pdf")
    assert len(pdf)>=4
    assert all(page.rect.width == pytest.approx(595.28,abs=.2) for page in pdf)


@pytest.mark.document
@pytest.mark.parametrize("experiment_id", [item["id"] for item in CONFIGS])
def test_every_general_report_renders_printable_pdf(experiment_id):
    pdf=fitz.open(stream=registry.get(experiment_id).build_report(fixtures()[experiment_id],"pdf"),filetype="pdf")
    assert len(pdf)>=4
    for page in pdf:
        text=page.get_text()
        assert text.strip() or page.get_images(full=True)
        assert "�" not in text and "\x00" not in text
        assert page.rect.width == pytest.approx(595.28,abs=.2)
        assert page.rect.height == pytest.approx(841.89,abs=.2)
