"""Shared numeric and plotting infrastructure for experiment adapters."""

from __future__ import annotations

import base64
import io
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Noto Sans CJK SC", "Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 130,
    "savefig.dpi": 180,
})


def numbers(rows: list[dict], *keys: str) -> list[tuple[float, ...]]:
    out = []
    for row in rows:
        try:
            values = tuple(float(row[key]) for key in keys)
        except (KeyError, TypeError, ValueError):
            continue
        if all(math.isfinite(value) for value in values):
            out.append(values)
    return out


def mean(values) -> float:
    return float(np.mean(values))


def std(values) -> float:
    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def fit(x, y) -> dict:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2 or np.ptp(x) == 0:
        raise ValueError("线性拟合至少需要两个不同的横坐标数据点")
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {"slope": float(slope), "intercept": float(intercept),
            "r_squared": float(r2), "fitted": fitted.tolist()}


def plot(x, series: list[tuple[list[float], str, str]], xlabel: str,
         ylabel: str, title: str, fit_lines: bool = False,
         connect_points: bool = False,
         fit_indices: list[int] | None = None) -> str:
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    for y, label, color in series:
        if connect_points:
            ax.plot(x, y, marker="o", markersize=4.5, color=color,
                    linewidth=1.6, label=label, zorder=3)
        else:
            ax.scatter(x, y, s=30, color=color, edgecolors="white", linewidths=.5,
                       label=label, zorder=3)
        if fit_lines and len(x) >= 2 and np.ptp(x) > 0:
            fitted = fit(x, y)
            xx = np.linspace(min(x), max(x), 100)
            ax.plot(xx, fitted["slope"] * xx + fitted["intercept"], color=color,
                    linewidth=1.6, label=f"{label} 线性拟合")
        if fit_indices:
            valid = [index for index in fit_indices if 0 <= index < len(x) and index < len(y)]
            if len(valid) >= 2:
                local_x = np.asarray([x[index] for index in valid], dtype=float)
                local_y = np.asarray([y[index] for index in valid], dtype=float)
                fitted = fit(local_x, local_y)
                xx = np.linspace(float(local_x.min()), float(local_x.max()), 100)
                ax.scatter(local_x, local_y, s=58, facecolors="none", edgecolors=color,
                           linewidths=1.4, label=f"{label} 局部拟合点", zorder=4)
                ax.plot(xx, fitted["slope"] * xx + fitted["intercept"], color=color,
                        linestyle="--", linewidth=1.8,
                        label=f"{label} 局部线性拟合", zorder=4)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.grid(alpha=.25)
    if len(series) > 1 or series[0][1]:
        ax.legend(fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def calibration(rows, unit):
    vals = numbers(rows, "set", "measured")
    x, y = map(list, zip(*vals))
    fitted = fit(x, y)
    errors = [b - a for a, b in vals]
    return ({"slope": fitted["slope"], "intercept": fitted["intercept"],
             "r_squared": fitted["r_squared"], "max_abs_error": max(map(abs, errors))},
            [{"set": a, "measured": b, "error": e} for (a, b), e in zip(vals, errors)],
            plot(x, [(y, "实验读数", "#2563eb")], f"标准值 / {unit}",
                 f"组装表读数 / {unit}", "校准曲线", True))
