from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from experiments.core.configured import ConfiguredExperiment
from experiments.core.numerics import (calibration as _calibration, fit as _fit,
                                       mean as _mean, numbers as _numbers,
                                       plot as _plot, std as _std)
from experiments.schema import enrich_config


CONFIG = enrich_config(json.loads(Path(__file__).with_name("config.json").read_text(encoding="utf-8")))

CU50_R0 = 50.0            # 讲义 (27)：Cu50 在 0 °C 的阻值
CU50_ALPHA = 0.004280     # 讲义 (27)：Cu50 温度系数理论值 /°C


def _fig_bytes(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _thermistor_plot(t, r, x, y) -> str:
    """讲义【数据处理】3 要求两条曲线：R(T)~T 与 lnR(T)~1/T。"""
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.2))
    axes[0].plot(t, r, marker="o", markersize=4.5, color="#2563eb", linewidth=1.6)
    axes[0].set_xlabel("t / °C")
    axes[0].set_ylabel("R / Ω")
    axes[0].set_title("热敏电阻 R-t 特性", fontweight="bold")
    axes[0].grid(alpha=.25)
    axes[1].scatter(x, y, s=30, color="#f59e0b", edgecolors="white", linewidths=.5)
    if len(x) >= 2 and np.ptp(x) > 0:
        fitted = _fit(x, y)
        xx = np.linspace(min(x), max(x), 100)
        axes[1].plot(xx, fitted["slope"] * xx + fitted["intercept"], color="#f59e0b",
                     linewidth=1.6, label=f"线性拟合 R²={fitted['r_squared']:.4f}")
        axes[1].legend(fontsize=8)
    axes[1].set_xlabel(r"1/T / K$^{-1}$")
    axes[1].set_ylabel("ln R")
    axes[1].set_title("热敏电阻 lnR-1/T 线性化", fontweight="bold")
    axes[1].grid(alpha=.25)
    fig.tight_layout()
    return _fig_bytes(fig)


def calculate(method, rows, p):
    if method == "balanced":
        # 讲义 (2)：Rx = (Ra/Rb)·Rn；讲义【数据处理】1 要求与「室温理论值」比较
        vals = [v[0] for v in _numbers(rows, "rn")]
        ra = p.get("ra", 1000); rb = p.get("rb", 5000)
        t_room = float(p.get("t_room", 20.0))
        rx = [ra / rb * v for v in vals]
        mean = _mean(rx)
        theory = CU50_R0 * (1 + CU50_ALPHA * t_room)
        return {"rx_mean": mean, "theory": theory,
                "relative_error": abs(mean - theory) / theory * 100}, \
            [{"rn": a, "rx": b} for a, b in zip(vals, rx)], None
    if method == "cu50":
        # 讲义 (12)：卧式电桥 U0 = Us/4·(ΔR/R)/(1+½ΔR/R)，R=R1=R4=Rn（预平衡值）
        # → ΔR = 4Rn·U0/(Us-2U0)，Rx = Rn + ΔR（讲义【数据处理】2 提示）
        vals = _numbers(rows, "temperature", "u0")
        t, u_mv = map(list, zip(*vals)); us = p.get("us", 3); rn = p.get("rn", 54.3)
        u = np.asarray(u_mv) / 1000
        if np.any(us - 2 * u <= 0): raise ValueError("U0 必须满足 Us-2U0>0")
        rx = rn + 4 * rn * u / (us - 2 * u)
        f = _fit(t, rx)
        alpha = f["slope"] / f["intercept"]
        result = {"r0": f["intercept"], "r0_error": abs(f["intercept"] - CU50_R0) / CU50_R0 * 100,
                  "alpha": alpha, "r_squared": f["r_squared"],
                  "alpha_error": abs(alpha - CU50_ALPHA) / CU50_ALPHA * 100}
        derived = [{"temperature": a, "u0": b, "rx": float(c)} for a, b, c in zip(t, u_mv, rx)]
        return result, derived, _plot(t, [(rx.tolist(), "Cu50", "#dc2626")], "t / °C", "Rx / Ω", "Cu50 阻温特性", True)
    if method == "capacitor":
        vals = _numbers(rows, "cn", "rn"); ra=p.get("ra",100); rb=p.get("rb",120); f=p.get("f",1000)
        derived=[{"cn":cn,"rn":rn,"cx":rb/ra*cn,"rc":ra/rb*rn,"tan_delta":2*math.pi*f*cn*1e-6*rn} for cn,rn in vals]
        return {k:_mean([d[k] for d in derived]) for k in ("cx","rc","tan_delta")}, derived, None
    if method == "inductor":
        # 讲义 (25)(26)：Lx = Ra·Rb·Cn，rL = Ra·Rb/Rn，Q = ωLx/rL = ωCnRn
        vals = _numbers(rows, "cn", "rn"); ra=p.get("ra",100); rb=p.get("rb",100); f=p.get("f",1000)
        derived=[{"cn":cn,"rn":rn,"lx":ra*rb*cn*1e-3,"rl":ra*rb/rn,"q":2*math.pi*f*cn*1e-6*rn} for cn,rn in vals if rn]
        return {k:_mean([d[k] for d in derived]) for k in ("lx","rl","q")}, derived, None
    # 选做内容3：立式电桥（讲义 (13)）→ ΔR = U0(R+R')²/[Us·R' - U0(R+R')]
    # 阻值随升温下降（NTC），故按讲义符号约定 U0<0；若学生按绝对值记录（极性相反），
    # 则用 |U0| 反解并给出提示，两种记录方式都能得到同一组阻值。
    vals = _numbers(rows, "temperature", "u0")
    t, u_mv = map(list, zip(*vals))
    us = p.get("us", 3); rp = p.get("r_prime", 100); rn = p.get("rn", 3250)
    s = rn + rp
    u = np.asarray(u_mv) / 1000
    if np.any(us * rp - u * s <= 0):
        u = -np.abs(u)
    denom = us * rp - u * s
    if np.any(denom <= 0):
        raise ValueError("立式电桥反解要求 Us·R' > |U0|·(Rn+R')，请核对电源电压与预平衡 Rn")
    dr = u * s * s / denom
    r = rn + dr
    if np.any(r <= 0): raise ValueError("反解得到的阻值非正，请核对预平衡 Rn 与 U0 读数")
    x = 1 / (np.asarray(t) + 273.15); y = np.log(r); f = _fit(x, y)
    b = f["slope"]
    r25 = math.exp(f["intercept"] + b / 298.15)
    result = {"b_constant": b, "r25": r25, "r_squared": f["r_squared"]}
    derived = [{"temperature": a, "u0": c, "rx": float(d)} for a, c, d in zip(t, u_mv, r)]
    return result, derived, _thermistor_plot(t, r.tolist(), x.tolist(), y.tolist())


def _number(value, fallback=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _finalize(data, response):
    """把「填错量纲/填错符号」这类会整体放大误差的录入问题当场点名，而不是静默算成怪结果。"""
    cu50_params = (data.get("cu50") or {}).get("params") or {}
    bridge_rn = _number(cu50_params.get("rn"))
    if bridge_rn is not None and bridge_rn > 300:
        response.setdefault("warnings", []).append(
            f"卧式电桥：预平衡 Rn={bridge_rn:g} Ω 远大于 Cu50 室温阻值（约 54 Ω）。"
            "这里应填「预调平衡时 Rn 的实测读数」，不是桥臂 Ra/Rb 的 1000 Ω。")

    payload = data.get("thermistor") or {}
    params = payload.get("params") or {}
    us = _number(params.get("us"), 3.0)
    r_prime = _number(params.get("r_prime"), 100.0)
    rn = _number(params.get("rn"), 3250.0)
    readings = [_number((row or {}).get("u0")) for row in (payload.get("rows") or [])]
    readings = [value for value in readings if value is not None]
    if readings and any(us * r_prime - value / 1000 * (rn + r_prime) <= 0 for value in readings):
        response.setdefault("warnings", []).append(
            "热敏电阻：记为正值的 U0 已按 |U0| 反解（对应阻值随温度下降）。"
            "若你的读数是讲义 (13) 约定下的代数值，请保留负号填写。")
    derived = (response.get("derived") or {}).get("thermistor") or []
    resistances = [row.get("rx") for row in derived]
    if len(resistances) > 1 and all(isinstance(value, (int, float)) for value in resistances) \
            and resistances == sorted(resistances):
        response.setdefault("warnings", []).append(
            "热敏电阻：按记录顺序反解出的阻值在上升，请核对温度顺序与 U0 符号。")
    return response



FORMULAS = {'balanced': ['R_x=\\frac{R_a}{R_b}R_n',
                         'R_x(t)=R_0(1+\\alpha t),\\quad R_0=50.0\\,\\Omega,\\ \\alpha=0.004280\\,\\mathrm{^{o}C^{-1}}',
                         'E_r=\\frac{|R_x-R_x(t)|}{R_x(t)}\\times100\\%'],
 'cu50': ['\\Delta R_x=\\frac{4R_nU_0}{U_s-2U_0},\\quad R_x=R_n+\\Delta R_x',
          'R_x=R_0(1+\\alpha t),\\quad \\alpha=\\frac{k}{R_0}'],
 'capacitor': ['C_x=\\frac{R_b}{R_a}C_n,\\quad r_C=\\frac{R_a}{R_b}R_n', '\\tan\\delta=2\\pi fC_nR_n'],
 'inductor': ['L_x=R_aR_bC_n,\\quad r_L=\\frac{R_aR_b}{R_n}', 'Q=\\frac{\\omega L_x}{r_L}=\\omega C_nR_n'],
 'thermistor': ['\\Delta R_x=\\frac{U_0(R_n+R^\\prime)^2}{U_sR^\\prime-U_0(R_n+R^\\prime)},\\quad R_x=R_n+\\Delta R_x',
                '\\ln R=\\ln R_{25}+B\\left(\\frac{1}{T}-\\frac{1}{298.15}\\right)']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='bridge',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
    finalize_result=_finalize,
)
