"""Blank record sheets and unified four-section reports for generic labs."""

from __future__ import annotations

import math

from experiments.general.engine import CONFIG_BY_ID, process_experiment
from experiments.polarization import docbuild
from experiments.report_layout import four_section_report, latex


FORMULAS = {
    "multimeter": {
        "voltage": [r"\Delta U_i=U_{{\rm meas},i}-U_{{\rm set},i}", r"U_{\rm meas}=kU_{\rm set}+b"],
        "current": [r"\Delta I_i=I_{{\rm meas},i}-I_{{\rm set},i}", r"I_{\rm meas}=kI_{\rm set}+b"],
        "resistance": [r"\Delta R_i=R_{{\rm meas},i}-R_{{\rm set},i}", r"R_{\rm meas}=kR_{\rm set}+b"],
        "unknown": [r"\varepsilon_r=\frac{|\overline{R}_{\rm meas}-\overline{R}_{\rm ref}|}{\overline{R}_{\rm ref}}\times100\%"],
        "ac_voltage": [r"\Delta U_i=U_{{\rm meas},i}-U_{{\rm set},i}", r"U_{\rm meas}=kU_{\rm set}+b"],
        "ac_current": [r"\Delta I_i=I_{{\rm meas},i}-I_{{\rm set},i}", r"I_{\rm meas}=kI_{\rm set}+b"],
    },
    "bridge": {
        "balanced": [r"R_x=\frac{R_a}{R_b}R_n"],
        "cu50": [r"\Delta R_x=\frac{4RU_0}{U_s-2U_0},\quad R_x=R_n+\Delta R_x", r"R_x=R_0(1+\alpha t),\quad \alpha=\frac{k}{R_0}"],
        "capacitor": [r"C_x=\frac{R_b}{R_a}C_n,\quad r_C=\frac{R_a}{R_b}R_n", r"\tan\delta=2\pi fC_nR_n"],
        "inductor": [r"L_x=R_aR_bC_n,\quad r_L=\frac{R_a}{R_b}R_n", r"Q=\frac{2\pi fR_b^2C_n}{R_n}"],
        "thermistor": [r"\ln R=\ln R_0+B\left(\frac{1}{T}-\frac{1}{T_0}\right)"],
    },
    "photoelectric": {
        "planck": [r"\nu=\frac{c}{\lambda},\quad U_S=k\nu+b", r"h=ek,\quad \nu_0=-\frac{b}{k},\quad W=-eb"],
        "iv_436": [r"I=I(U_{AK})"], "iv_546": [r"I=I(U_{AK})"],
        "saturation": [r"P_{\rm rel}\propto\Phi^2,\quad I_m=a\Phi^2+b"],
        "compensation": [r"\nu=\frac{c}{\lambda},\quad U_S=k\nu+b", r"h=ek,\quad \nu_0=-\frac{b}{k}"],
    },
    "franck-hertz": {
        "curve": [r"I_P=f(V_{G2K})"],
        "peaks": [r"\Delta U_i=\frac{U_{p(i+3)}-U_{pi}}{3}", r"V_0=\overline{\Delta U},\quad E_r=\frac{|V_0-4.90|}{4.90}\times100\%"],
        "parameter_curve": [r"\Delta I_i=I_{{\rm variant},i}-I_{{\rm reference},i}"],
        "higher_curve": [r"I_P=f(U_{KG1})"],
    },
    "solar-cell": {
        "iv": [r"P_i=U_iI_i,\quad P_{\max}=\max(P_i)", r"FF=\frac{P_{\max}}{U_{oc}I_{sc}}"],
        "shading": [r"r_i=\frac{I_{sc,i}}{I_{sc,0}}\times100\%"],
        "charge_direct": [r"P(t)=U(t)I(t),\quad E=\int P(t)\,dt"],
        "charge_dcdc": [r"P(t)=U(t)I(t),\quad E=\int P(t)\,dt"],
        "fan": [r"P=UI"],
        "load_dcdc": [r"P_1=U_1I_1,\quad P_2=U_2I_2,\quad \Delta P=P_2-P_1"],
        "inverter": [r"P_{\rm in}=U_{\rm dc}I_{\rm dc}"],
    },
    "gmr": {
        "transfer": [r"B({\rm Gs})=0.31416I({\rm mA}),\quad V_{out}=kB+b"],
        "resistance": [r"R=\frac{2U}{I_R}", r"GMR=\frac{R_{\max}-R_{\min}}{R_{\min}}\times100\%"],
        "current_sensor": [r"V_{out}=kI+b"],
    },
    "nmr": {
        "waveform": [r"\Delta T=|T_1-T_2|"],
        "hydrogen": [r"\nu=kB_0+b,\quad \frac{\gamma}{2\pi}=10^3k", r"g=\frac{\gamma/(2\pi)}{\mu_N/h}"],
        "fluorine": [r"\nu=kB_0+b,\quad \frac{\gamma}{2\pi}=10^3k", r"g=\frac{\gamma/(2\pi)}{\mu_N/h}"],
        "pure_water": [r"\nu=kB_0+b,\quad \frac{\gamma}{2\pi}=10^3k", r"g=\frac{\gamma/(2\pi)}{\mu_N/h}"],
    },
    "viscosity": {
        "diameter": [r"d_i=|x_{2,i}-x_{1,i}|,\quad \overline{d}=\frac{1}{n}\sum_i d_i"],
        "viscosity": [r"v_0=\frac{L}{\overline{t}}", r"\eta_0=\frac{gd^2(\rho-\rho_0)}{18v_0(1+2.4d/D)}", r"Re=\frac{\rho_0v_0d}{\eta_0},\quad \eta'=\eta_0\left(1-\frac{3}{16}Re\right)"],
        "diameter_effect": [r"v_0=\frac{L}{\overline{t}}", r"Re=\frac{\rho_0v_0d}{\eta_0}"],
    },
    "surface-tension": {
        "calibration": [r"F=mg,\quad U=KF+b"],
        "pull_off": [r"\sigma=\frac{|U_1-U_2|}{\pi(D_1+D_2)K}", r"\Delta\sigma=|\sigma-\sigma_0|,\quad E_r=\frac{|\sigma-\sigma_0|}{\sigma_0}\times100\%"],
        "capillary": [r"h=|y_1-y_2|,\quad d=|x_1-x_2|", r"\sigma=\frac{1}{4}\rho gd\left(h+\frac{d}{6}\right)", r"\Delta\sigma=|\sigma-\sigma_0|,\quad E_r=\frac{|\sigma-\sigma_0|}{\sigma_0}\times100\%"],
        "salt_pull_off": [r"\sigma=\frac{|U_1-U_2|}{\pi(D_1+D_2)K}"],
        "salt_capillary": [r"\sigma=\frac{1}{4}\rho gd\left(h+\frac{d}{6}\right)"],
    },
    "thermal-conductivity": {
        "geometry": [r"\overline{x}=\frac{1}{n}\sum_i x_i"],
        "heating": [r"T_1=\overline{T_A},\quad T_2=\overline{T_C}"],
        "cooling": [r"\xi=\frac{2R_C+h_C}{2R_C+2h_C}", r"\lambda=\frac{mc|dT/dt|_{T_2}h_B}{\pi R_B^2(T_1-T_2)}\xi"],
    },
    "michelson": {
        "wavelength": [r"\Delta d_i=|d_{i+5}-d_i|", r"\lambda=\frac{2\overline{\Delta d}}{250}=\frac{\overline{\Delta d}}{125}"],
    },
}

_TEXT_TRANSLATION = str.maketrans({"⁰":"0","¹":"1","²":"^2","³":"^3","⁴":"4",
                                   "⁵":"5","⁶":"6","⁷":"7","⁸":"8","⁹":"9","⁻":"-"})


def _safe_text(value: str) -> str:
    """Avoid code points missing from the embedded Chinese PDF fonts."""
    return value.translate(_TEXT_TRANSLATION)


def _fmt(value) -> str:
    if value is None or value == "": return ""
    if isinstance(value, str): return _safe_text(value)
    try:
        number=float(value)
        if not math.isfinite(number): return "—"
        if abs(number) >= 1e5 or (number and abs(number) < 1e-4): return f"{number:.6e}"
        return f"{number:.6f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError): return str(value)


def _table(rows: list[list], columns: int, font: float = 8.2,
           row_h: float = .52, fixed_row_height: bool = False) -> dict:
    spec = {"kind":"table","widths":[17.7/columns]*columns,"font":font,
            "row_h":row_h,"rows":[[{"text":_fmt(cell)} for cell in row] for row in rows]}
    if fixed_row_height:
        spec["fixed_row_height"] = True
    return spec


def _method_raw_table(method: dict, payload: dict, blank: bool = False) -> dict:
    columns=method["columns"]; head=[f"{c['label']} ({c['unit']})" if c.get("unit") else c["label"] for c in columns]
    source=payload.get("rows",[]) if not blank else []
    rows=[head]
    for idx in range(method["rowCount"]):
        item=source[idx] if idx<len(source) else {}
        row=[]
        for col in columns:
            value=item.get(col["key"],"")
            if blank and value=="":
                prefill=method.get("prefill",{}).get(col["key"],[])
                value=prefill[idx] if idx<len(prefill) else ""
            row.append(value)
        rows.append(row)
    if len(rows) > 31 and len(columns) <= 3:
        rows = _fold_rows(rows, target_rows=30)
    if blank:
        # Blank sheets are written on by hand.  Use visibly taller rows while
        # keeping even the longest lecture-prescribed tables on portrait A4.
        body_rows = len(rows) - 1
        row_h = .88 if body_rows <= 12 else .78 if body_rows <= 22 else .68
    else:
        row_h = .52
    return _table(rows,len(rows[0]),7.2 if len(rows[0])>6 else 8.2,
                  row_h=row_h, fixed_row_height=blank)


def _fold_rows(rows: list[list], target_rows: int = 22) -> list[list]:
    """Fold long narrow datasets into repeated horizontal column groups."""
    head, body = rows[0], rows[1:]
    groups = math.ceil(len(body) / target_rows)
    per_group = math.ceil(len(body) / groups)
    folded = [head * groups]
    for row_index in range(per_group):
        line = []
        for group in range(groups):
            source_index = group * per_group + row_index
            line.extend(body[source_index] if source_index < len(body) else [""] * len(head))
        folded.append(line)
    return folded


def record_blocks(experiment_id: str) -> list[dict]:
    config=CONFIG_BY_ID[experiment_id]; blocks=[]
    for method in config["methods"]:
        blocks.append({"kind":"h2","text":_safe_text(("选做：" if not method.get("required") else "")+method["name"])})
        if method.get("params"):
            blocks.append(_table([[f"{p['label']} ({p['unit']})" if p.get('unit') else p['label'] for p in method["params"]],
                                 [p.get("default","") for p in method["params"]]],
                                 len(method["params"]), row_h=.78,
                                 fixed_row_height=True))
        blocks.append(_method_raw_table(method,{},True)); blocks.append({"kind":"spacer","cm":.12})
    return blocks


def record_bytes(experiment_id: str, fmt: str) -> bytes:
    blocks=record_blocks(experiment_id)
    return docbuild.render_docx(blocks,landscape=False,cn="宋体",cn_en="宋体") if fmt=="docx" else docbuild.render_pdf(blocks,landscape=False,cn_pref="msyh")


def _result_table(method: dict, values: dict) -> dict:
    rows=[["结果量","数值","单位"]]
    for field in method.get("results",[]): rows.append([field["label"],values.get(field["key"]),field.get("unit","")])
    return _table(rows,3)


def _derived_table(rows: list[dict]) -> dict | None:
    if not rows: return None
    keys=list(rows[0].keys()); table_rows=[keys]+[[row.get(key,"") for key in keys] for row in rows]
    if len(table_rows)>25 and len(keys)<=3: table_rows=_fold_rows(table_rows)
    return _table(table_rows,len(table_rows[0]),7.2 if len(table_rows[0])>6 else 8)


def report_blocks(experiment_id: str, data: dict) -> list[dict]:
    config=CONFIG_BY_ID[experiment_id]; run=process_experiment(experiment_id,data)
    if run["status"]!="success": raise ValueError("；".join(run.get("errors",[])) or "没有可处理的数据")
    tables=[]; figures=[]; analysis=[]
    methods={m["id"]:m for m in config["methods"]}
    for method_id,result in run["results"].items():
        method=methods[method_id]; payload=data.get(method_id,{})
        if method.get("params"):
            tables.append((_safe_text(f"{method['name']}参数"),_table([[p["label"] for p in method["params"]],[_fmt(payload.get("params",{}).get(p["key"],p.get("default",""))) for p in method["params"]]],len(method["params"]))))
        tables.append((_safe_text(f"{method['name']}原始数据"),_method_raw_table(method,payload)))
        detail_rows=run["derived"].get(method_id,[])
        detail=_derived_table(detail_rows)
        if detail: tables.append((_safe_text(f"{method['name']}计算明细"),detail))
        tables.append((_safe_text(f"{method['name']}结果汇总"),_result_table(method,result)))
        if method_id == "iv_436" and "iv_curves" in run["plots"]:
            figures.append(("436 nm 与 546 nm 伏安特性",{"b64":run["plots"]["iv_curves"],"width_cm":12.5}))
        elif method_id in run["plots"]:
            figures.append((_safe_text(method["name"]),{"b64":run["plots"][method_id],"width_cm":12.5}))
        analysis.append({"kind":"h3","text":_safe_text(method["name"])})
        analysis.append({"kind":"para","text":_safe_text(method["description"]+"。先筛除空白行并统一到公式所示单位，再计算明细表和汇总结果。")})
        for formula in FORMULAS.get(experiment_id,{}).get(method_id,[]): analysis.append(latex(formula))
        for row_index, row in enumerate(detail_rows, start=1):
            substitutions="，".join(f"{key}={_fmt(value)}" for key,value in row.items())
            analysis.append({"kind":"note","text":_safe_text(f"第 {row_index} 组逐点代入：{substitutions}。")})
        rendered="；".join(f"{field['label']}={_fmt(result.get(field['key']))} {field.get('unit','')}" for field in method.get("results",[]))
        analysis.append({"kind":"para","text":_safe_text("本组数据代入后："+rendered+"。完整逐点中间量见第一部分对应计算明细表。")})
        if experiment_id == "surface-tension" and method_id in ("pull_off", "capillary"):
            analysis.append({"kind":"para","text":_safe_text(
                f"最终结果：σ = ({_fmt(result.get('sigma'))} ± {_fmt(result.get('absolute_error'))}) N/m；"
                f"相对误差 Er = {_fmt(result.get('relative_error'))}%。"
            )})
    discussion=config["discussion"]
    fourth=[{"kind":"h3","text":"拓展方向"},{"kind":"para","text":_safe_text(discussion["extensions"])},
            {"kind":"h3","text":"改进建议"},{"kind":"para","text":_safe_text(discussion["suggestions"])},
            {"kind":"h3","text":"误差分析"},{"kind":"para","text":_safe_text(discussion["errors"])},
            {"kind":"h3","text":"总结"},{"kind":"para","text":"以上结果来自本次提交数据的公式计算与拟合。算法单元测试与合成 fixture 可验证计算链和文档结构，但不能据此断言完整真实实验数据一定正确；真实结论仍需结合原始记录、仪器条件和讲义判据审核。"}]
    if run.get("errors"): fourth.insert(-2,{"kind":"para","text":"未纳入计算的数据："+"；".join(run["errors"])})
    return four_section_report(tables,figures,analysis,fourth)


def report_bytes(experiment_id: str, data: dict, fmt: str) -> bytes:
    blocks=report_blocks(experiment_id,data)
    return docbuild.render_docx(blocks,landscape=False) if fmt=="docx" else docbuild.render_pdf(blocks,landscape=False)
