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

#: 讲义：B = μ0·N·I/L，螺线管 N = 3250 匝、L = 130 mm ⇒ 0.31416 Gs/mA
FIELD_PER_MA = 0.31416

_BRANCH_LABEL = {1.0: "增磁支", -1.0: "减磁支"}
_BRANCH_COLOR = {1.0: "#2563eb", -1.0: "#f59e0b"}


def _fig_bytes(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _transfer_points(rows) -> tuple[list[tuple[float, float, float]], bool]:
    """归一化成 (励磁电流代数值, 输出电压, 支路)，并回报「符号可能丢失」的可疑情况。

    记录表预填的是**带符号**的励磁电流（−200…200 再 200…−200），学生只填 Vout。
    若学生把励磁电流改成了幅值（负电流靠切换电源极性实现），B 的符号就无从恢复——
    此时两支会被压在同一半轴、斜率互相抵消，必须点名而不是硬凑一个灵敏度。
    """
    points: list[tuple[float, float, float]] = []
    for row in rows:
        try:
            current = float(row["excitation"])
            output = float(row["output"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            direction = float(row.get("direction"))
        except (TypeError, ValueError):
            direction = None
        if direction not in (1.0, -1.0):
            direction = 1.0 if current >= 0 else -1.0
        points.append((current, output, direction))
    if not points:
        raise ValueError("磁电转换特性：没有可用的（励磁电流，输出电压）数据")
    sign_lost = all(current >= 0 for current, _, _ in points) \
        and any(direction < 0 for _, _, direction in points)
    return points, sign_lost


def _branch_r2(branches: dict, fits: dict) -> float:
    """两支模型（每支一条直线）的 R²：单一直线拟合会把磁滞当成噪声，这个数才反映回线质量。"""
    values = [y for pairs in branches.values() for _, y in pairs]
    mean_y = float(np.mean(values))
    ss_tot = float(np.sum((np.asarray(values) - mean_y) ** 2))
    ss_res = 0.0
    for direction, pairs in branches.items():
        fit = fits.get(direction)
        for x, y in pairs:
            predicted = fit["slope"] * x + fit["intercept"] if fit else mean_y
            ss_res += (y - predicted) ** 2
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0


def _transfer_plot(branches: dict, fits: dict) -> str:
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for direction in (1.0, -1.0):
        pairs = branches.get(direction)
        if not pairs:
            continue
        x = [point[0] for point in pairs]
        y = [point[1] for point in pairs]
        color = _BRANCH_COLOR[direction]
        label = _BRANCH_LABEL[direction]
        ax.plot(x, y, marker="o", markersize=4.5, linewidth=1.6, color=color,
                label=f"{label}读数", zorder=3)
        fit = fits.get(direction)
        if fit:
            xx = np.linspace(min(x), max(x), 100)
            ax.plot(xx, fit["slope"] * xx + fit["intercept"], linestyle="--", color=color,
                    linewidth=1.7, zorder=4,
                    label=f"{label}拟合 k={fit['slope']:.3f} mV/Gs")
    ax.set_xlabel("B / Gs")
    ax.set_ylabel("Vout / mV")
    ax.set_title("GMR 磁电转换特性（两支差异＝磁滞）", fontweight="bold")
    ax.grid(alpha=.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return _fig_bytes(fig)


def calculate(method, rows, p):
    if method == "transfer":
        points, _sign_lost = _transfer_points(rows)
        fields = [FIELD_PER_MA * current for current, _, _ in points]
        branches: dict[float, list[tuple[float, float]]] = {}
        for (_, output, direction), field in zip(points, fields):
            branches.setdefault(direction, []).append((field, output))
        fits = {}
        for direction, pairs in branches.items():
            xs = [x for x, _ in pairs]
            if len(xs) >= 2 and float(np.ptp(xs)) > 0:
                fits[direction] = _fit(xs, [y for _, y in pairs])
        if not fits:
            raise ValueError("磁电转换特性：每一支至少需要 2 个不同磁场的读数才能拟合")
        slopes = {direction: fit["slope"] for direction, fit in fits.items()}
        result = {
            "sensitivity": float(np.mean([abs(value) for value in slopes.values()])),
            "sensitivity_up": slopes.get(1.0),
            "sensitivity_down": slopes.get(-1.0),
            "hysteresis": (abs(fits[1.0]["intercept"] - fits[-1.0]["intercept"])
                           if 1.0 in fits and -1.0 in fits else None),
            "r_squared": _branch_r2(branches, fits),
            "b_max": float(np.max(np.abs(fields))),
        }
        derived = [{"field": field, "output": output, "branch": _BRANCH_LABEL[direction]}
                   for field, (_, output, direction) in zip(fields, points)]
        return result, derived, _transfer_plot(branches, fits)
    if method == "resistance":
        vals=_numbers(rows,"excitation","ir_a","ir_b"); supply=p.get("supply",2); b=[.31416*v[0] for v in vals]; ra=[2*supply/(v[1]/1000) for v in vals]; rb=[2*supply/(v[2]/1000) for v in vals]
        g=lambda r:(max(r)-min(r))/min(r)*100
        ga,gb=g(ra),g(rb)
        return {"gmr_a":ga,"gmr_b":gb,"sensitive_state":1 if ga>=gb else 2},[{"field":x,"ra":a,"rb":bb} for x,a,bb in zip(b,ra,rb)],_plot(b,[(ra,"状态 A","#2563eb"),(rb,"状态 B","#f59e0b")],"B / Gs","R / Ω","内部磁阻特性",connect_points=True)
    vals=_numbers(rows,"current","output25","output100"); i,o25,o100=map(list,zip(*vals)); f25=_fit([v/1000 for v in i],o25); f100=_fit([v/1000 for v in i],o100)
    return {"sensitivity25":f25["slope"],"sensitivity100":f100["slope"]},[],_plot(i,[(o25,"25 mV 偏置","#2563eb"),(o100,"100 mV 偏置","#f59e0b")],"I / mA","Vout / mV","无接触电流标定",True)


def _row_number(value, fallback=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _finalize(data, response):
    """把「只测一支」「丢了励磁电流符号」「方向列与电流符号打架」这些会让结论失真的录入问题点名。"""
    payload = data.get("transfer") or {}
    rows = [row for row in (payload.get("rows") or []) if isinstance(row, dict)]
    currents = [_row_number(row.get("excitation")) for row in rows]
    currents = [value for value in currents if value is not None]
    directions = {_row_number(row.get("direction")) for row in rows}
    if not currents:
        return response

    measured = {value for value in directions if value in (1.0, -1.0)}
    if len(measured) == 1:
        response.setdefault("warnings", []).append(
            f"磁电转换特性：只记录了单一支路（方向列全为 {int(next(iter(measured)))}）。"
            "讲义要求励磁电流递增、递减各测 20 点以上，两支的差异才体现磁滞。")
    elif not measured:
        response.setdefault("warnings", []).append(
            "磁电转换特性：方向列未填 1/-1，已按励磁电流符号自动分两支，请核对原始记录。")

    if all(value >= 0 for value in currents) and -1.0 in measured:
        response.setdefault("warnings", []).append(
            "磁电转换特性：励磁电流全为非负值，但方向列含 -1。若负电流是切换电源极性得到的、"
            "记录时丢了负号，磁场符号无法恢复，两支会压在同一半轴互相抵消（灵敏度会算成 ≈0）——"
            "请按记录表填写带符号的励磁电流。")
    else:
        mismatched = [index + 1 for index, row in enumerate(rows)
                      if (_row_number(row.get("excitation")) or 0) < 0
                      and _row_number(row.get("direction")) == 1.0]
        if measured and mismatched:
            response.setdefault("warnings", []).append(
                f"磁电转换特性：第 {mismatched[:3]} 行励磁电流为负但方向列记 +1，请核对方向列。")
    return response



FORMULAS = {'transfer': ['B({\\rm Gs})=0.31416I({\\rm mA})',
                         'V_{out}=k_\\pm B+b_\\pm',
                         'k=\\frac{|k_+|+|k_-|}{2},\\quad \\Delta V_{hys}=|b_+-b_-|'],
 'resistance': ['R=\\frac{2U}{I_R}', 'GMR=\\frac{R_{\\max}-R_{\\min}}{R_{\\min}}\\times100\\%'],
 'current_sensor': ['V_{out}=kI+b']}



EXPERIMENT = ConfiguredExperiment(
    experiment_id='gmr',
    config=CONFIG,
    calculator=calculate,
    formulas=FORMULAS,
    finalize_result=_finalize,
)
