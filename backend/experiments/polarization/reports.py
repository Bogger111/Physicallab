#!/usr/bin/env python3
"""PhysicsLab report pipeline.

Produces, for the polarization experiment:
  1. 数据记录表 (printable blank record sheet)      -> .docx / .pdf
  2. 基准部分报告 (Part 1: the 4 baseline figures)  -> .docx / .pdf
  3. 拓展部分报告 (Part 2: error-analysis figures)  -> .docx / .pdf

Design rules (user requirements):
  - every table is border-only: NO background fills anywhere
  - compact A4 layout (narrow margins, small fonts) to save print cost
  - Chinese font: Microsoft YaHei (msyh.ttc), bold via msyhbd.ttc
  - Word output is editable; PDF mirrors it, flow-kept, no color bands
"""

from __future__ import annotations

import io
import math
import base64

import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table as RLTable,
    TableStyle,
)

EXPERIMENT_TITLE = "偏振光与双折射实验"
CN_BODY = "微软雅黑"

# matplotlib styling shared with adapter figures
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 150,
    "savefig.dpi": 200,
})

_BLUE = "#2563eb"
_ORANGE = "#f59e0b"
_RED = "#dc2626"
_GREEN = "#10b981"
_GRAY = "#6b7280"

FONT_CANDIDATES = [
    ("CN", r"C:\Windows\Fonts\msyh.ttc"),
    ("CN-BOLD", r"C:\Windows\Fonts\msyhbd.ttc"),
]


# ────────────────────────────────────────────────────────────
# fonts
# ────────────────────────────────────────────────────────────

def register_pdf_fonts() -> dict:
    """Register Chinese TTFs for reportlab; return name map with Helvetica fallback."""
    names = {"CN": "Helvetica", "CN-B": "Helvetica"}
    for key, path in FONT_CANDIDATES:
        try:
            pdfmetrics.registerFont(TTFont(key, path, subfontIndex=0))
            names["CN" if key == "CN" else "CN-B"] = key
        except Exception:
            pass
    return names


def _set_east_asia(style_or_run, cn: str = CN_BODY):
    """Force East-Asian font on a python-docx style or run."""
    rpr = style_or_run.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), cn)


def _fig_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _fig_b64(fig) -> str:
    return base64.b64encode(_fig_bytes(fig)).decode("utf-8")


# ────────────────────────────────────────────────────────────
# advanced (Part 2) figures — input: per-sub processed dicts
# ────────────────────────────────────────────────────────────

def fig_malus_theory_compare(r: dict) -> bytes:
    """I vs θ raw points (both channels) overlaid on the cos² curve."""
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    thetas = np.array(r["thetas"])
    order = np.argsort(thetas)
    t = thetas[order]
    c2 = np.cos(np.radians(t)) ** 2
    theory = r["slope"] * c2 + r["intercept"]
    valid = np.isfinite(r["I_left_corr"]) & np.isfinite(r["I_right_corr"])
    ax.scatter(thetas, r["I_left_corr"], c=_BLUE, marker="o", s=30,
               label="I 左旋（实验）", edgecolors="white", linewidths=0.5, zorder=5)
    ax.scatter(thetas, r["I_right_corr"], c=_ORANGE, marker="s", s=26,
               label="I 右旋（实验）", edgecolors="white", linewidths=0.5, zorder=5)
    ax.plot(t, theory, color=_RED, linewidth=2, zorder=4,
            label=f"理论曲线 I = I0cos²θ（I0 = {r['slope']:.2f} μW）")
    ax.set_xlabel("θ / °")
    ax.set_ylabel("I / μW")
    ax.set_title("马吕斯定律：实验数据与理论曲线对比", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8.5, framealpha=0.9)
    ax.grid(alpha=0.4)
    fig.tight_layout()
    return _fig_bytes(fig)


def fig_malus_residuals(r: dict) -> bytes:
    """Per-channel linear-fit residuals vs cos²θ with ±1σ band of the mean fit."""
    cos2 = r["cos2"]
    series = {"I 左旋": r["I_left_corr"], "I 右旋": r["I_right_corr"]}
    colors_map = {"I 左旋": _BLUE, "I 右旋": _ORANGE}
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    mean_res = []
    for name, y in series.items():
        m = np.isfinite(cos2) & np.isfinite(y)
        if m.sum() < 2:
            continue
        sl, ic, *_ = stats.linregress(cos2[m], y[m])
        res = y[m] - (sl * cos2[m] + ic)
        mean_res.append(res)
        ax.scatter(cos2[m], res, c=colors_map[name], marker="o" if name == "I 左旋" else "s",
                   s=34, label=f"{name} 残差", edgecolors="white", linewidths=0.5, zorder=5)
    ax.axhline(0, color=_RED, linewidth=1.4, zorder=4)
    if mean_res:
        allr = np.concatenate(mean_res)
        sd = np.nanstd(allr)
        ax.axhspan(-sd, sd, color=_RED, alpha=0.08)
        ax.text(0.02, 0.95, f"残差 σ ≈ {sd:.3f} μW（±1σ 阴影带）", transform=ax.transAxes,
                fontsize=9, va="top", color=_GRAY)
    ax.set_xlabel(r"$\cos^2\theta$")
    ax.set_ylabel("残差 / μW")
    ax.set_title("马吕斯定律：线性拟合残差分布（双通道）", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8.5, framealpha=0.9, loc="lower left")
    ax.grid(alpha=0.4)
    fig.tight_layout()
    return _fig_bytes(fig)


def fig_halfwave_residuals(r: dict) -> bytes:
    """Two panels: absolute residual ΔP2−2ΔC and relative error vs ΔC."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 3.9))
    dc = r["delta_c"]
    errs = r["errors"]
    rel = np.abs(r["rel_errors"])
    ax1.scatter(dc, errs, c=_BLUE, s=38, edgecolors="white", linewidths=0.5, zorder=5)
    ax1.axhline(0, color=_RED, linewidth=1.3)
    ax1.axhline(np.nanmax(np.abs(errs)), color=_GRAY, linestyle="--", linewidth=1)
    ax1.axhline(-np.nanmax(np.abs(errs)), color=_GRAY, linestyle="--", linewidth=1)
    ax1.set_xlabel("ΔC / °")
    ax1.set_ylabel("ΔP2 − 2ΔC / °")
    ax1.set_title("残差", fontsize=11, fontweight="bold")
    ax1.grid(alpha=0.4)
    ax2.scatter(dc, rel, c=_ORANGE, s=38, edgecolors="white", linewidths=0.5, zorder=5)
    ax2.set_xlabel("ΔC / °")
    ax2.set_ylabel("相对偏差 / %")
    ax2.set_title("相对偏差 |ΔP2−2ΔC|/2ΔC", fontsize=11, fontweight="bold")
    ax2.grid(alpha=0.4)
    fig.suptitle("半波片：转角测量误差分析", fontsize=12, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _fig_bytes(fig)


def fig_quarterwave_cartesian(r: dict) -> bytes:
    """Cartesian I(φ): data + theory(A_avg) + non-linear fit; residual sub-panel."""
    fig = plt.figure(figsize=(7.6, 6.4))
    gs = fig.add_gridspec(2, 1, height_ratios=[2.2, 1], hspace=0.42)
    ax = fig.add_subplot(gs[0])
    axr = fig.add_subplot(gs[1])
    phis = np.array(r["phis"])
    I_use = np.array(r["I_use"])
    valid = np.isfinite(I_use)
    ax.scatter(phis[valid], I_use[valid], c=_BLUE, s=26, label="实验数据",
               edgecolors="white", linewidths=0.5, zorder=5)
    ax.plot(r["phi_fine"], r["I_theory_fine"], color=_RED, linewidth=1.8,
            label=f"理论曲线（A = {r['A_avg']:.3f}, θ_qwp = {r['summary'].get('theta_qwp', '?')}°）")
    resid = I_use - r["I_theory_at_exp"]
    axr.scatter(phis, resid, c=_ORANGE, s=20, edgecolors="white", linewidths=0.4, zorder=5)
    axr.axhline(0, color=_RED, linewidth=1.2)
    axr.set_xlabel("φ / °")
    axr.set_ylabel("残差 / μW")
    ax.set_ylabel("I / μW")
    ax.set_title("λ/4 波片：I(φ) 实验与理论对比", fontsize=12, fontweight="bold")
    axr.set_title("残差（实验 − 理论）", fontsize=10, fontweight="bold")
    ax.legend(fontsize=8.5, framealpha=0.9)
    ax.grid(alpha=0.4)
    axr.grid(alpha=0.4)
    return _fig_bytes(fig)


def fig_circular_band(r: dict) -> bytes:
    """Circular: I(φ) points, mean line and ±1σ band — constancy visual check."""
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    angles = np.array(r["angles"])
    I_use = np.array(r["I_use"])
    valid = np.isfinite(I_use)
    sd = r["summary"].get("std_dev", 0.0)
    mean = r["I_mean"]
    ax.scatter(angles[valid], I_use[valid], c=_BLUE, s=22,
               edgecolors="white", linewidths=0.4, zorder=5)
    ax.plot([0, 350], [mean, mean], color=_RED, linewidth=2, zorder=4,
            label=f"均值 = {mean:.3f} μW")
    ax.fill_between([0, 350], mean - sd, mean + sd, color=_RED, alpha=0.10,
                    label=f"±1σ 带（σ = {sd:.3f} μW）")
    ax.set_xlabel("P2 转角 / °")
    ax.set_ylabel("I / μW")
    ax.set_title("圆偏振光：检偏器旋转时光强恒定性检验", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8.5, framealpha=0.9, loc="upper right")
    ax.grid(alpha=0.4)
    ax.set_xticks(range(0, 361, 30))
    fig.tight_layout()
    return _fig_bytes(fig)


def fig_params_compare(r_malus, r_hw, r_qw) -> bytes:
    """Bar summary of fitted/derived parameters with valid reference values only."""
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.6))
    # Malus I0 is fitted from this data set; no universal theoretical 100 μW.
    a1 = axes[0]
    a1.bar(["斜率 I0", "截距"], [r_malus["slope"], r_malus["intercept"]],
           color=[_BLUE, _ORANGE], width=0.5)
    a1.set_title(f"马吕斯拟合参数（R² = {r_malus['r_squared']:.5f}）",
                 fontsize=10.5, fontweight="bold")
    # halfwave slope
    a2 = axes[1]
    a2.bar(["实验斜率", "理论 2"], [r_hw["slope"], 2.0], color=[_BLUE, _GRAY], width=0.5)
    a2.set_title(f"半波片斜率（偏差 {r_hw['summary']['slope_deviation_pct']:.2f}%）", fontsize=10.5, fontweight="bold")
    # quarterwave A estimators
    a3 = axes[2]
    qw = r_qw["summary"]
    a3.bar(["A(Imax)", "A(Imin)", "A 平均"], [qw.get("A_from_max", 0), qw.get("A_from_min", 0), qw.get("A_avg", 0)],
           color=[_ORANGE, _ORANGE, _BLUE], width=0.5)
    a3.set_title("λ/4 波片 A 参数估计对比", fontsize=10.5, fontweight="bold")
    for ax in axes:
        ax.grid(axis="y", alpha=0.35)
        ax.tick_params(labelsize=8.5)
    fig.suptitle("关键参数汇总", fontsize=12, fontweight="bold", y=1.03)
    fig.tight_layout()
    return _fig_bytes(fig)


ADVANCED_SPEC = [
    ("理论对比", "马吕斯定律：实验数据与理论曲线对比", fig_malus_theory_compare, "malus"),
    ("残差分析", "马吕斯定律：双通道线性拟合残差分布", fig_malus_residuals, "malus"),
    ("残差分析", "半波片：转角测量误差分析（残差 + 相对偏差）", fig_halfwave_residuals, "halfwave"),
    ("理论对比", "λ/4 波片：I(φ) 直角坐标对比与残差", fig_quarterwave_cartesian, "quarterwave"),
    ("恒定性检验", "圆偏振光：检偏器旋转时光强恒定性检验", fig_circular_band, "circular"),
    ("参数汇总", "关键参数汇总", fig_params_compare, "all"),
]

ADVANCED_CAPTIONS = [c for _, c, _, _ in ADVANCED_SPEC]
