#!/usr/bin/env python3
"""声速光速的测量（exp02）— 数据分析引擎。

对外接口：
    process_method(method, rows, params) -> dict
        返回 {status, errors, results, plots} 供前端展示。
    analyze(method, rows, params) -> dict
        返回 {status, errors, results, plots, arrays, params_used} 供报告生成使用。

rows: dict[str, list]，每列为 list[float | None]（长度须与方法输入列一致）。
params: dict[str, float]，未给出的参数使用默认值。

计算规则与单位换算（严格执行）：
  A. air_resonance  空气中共振法：输入 l(mm) 12 个 + {temperature_degC=25.0, f_khz=38}。
       逐差 Δl_i=(l[i+6]-l[i])/6 (mm, i=0..5)；波长 λ=2*mean(Δl) 由 mm 换算为 m；
       实验声速 v_exp = f_khz*1000 * λ_m；理论声速 v_theory = 331.45*(1+t/273.15)。
  B. water_phase    水中相位法：输入 l(mm) 12 个 + {f_mhz=1.0}，同上逐差；
       v = f_mhz*1e6 * λ_m。A 类不确定度：s=std(Δl,ddof=1)，
       U_A_Δl_m = 2.571*s/√6 再换算为米；U_A(m/s) = 2*f_Hz*U_A_Δl_m（因 v=f*2*Δl_m）。
  C. tof            飞行时间法：输入 L(mm) 12 个 + T(μs) 12 个（讲义：连续 12 组，
       每点 v_i = (L_i*1e-3)/(T_i*1e-6) m/s，取平均与标准差。
  D. light_sine     光速正弦法：输入 T(μs)、Δt(μs)、x1(mm)、x2(mm) 各 3 个 + {f_mhz=150, c_ref=2.998e8}。
       Δx_i=|x2-x1|；调制波长 λ = (T_mean/Δt_mean)*2*Δx_mean（mm→m）；
       c_exp = f_mhz*1e6 * λ_m。
  E. light_lissajous 光速李萨如法：输入 x1(mm)、x2(mm) 各 3 个；λ = 4*Δx_mean（mm→m）；
       c_exp = f_mhz*1e6 * λ_m。
"""

from __future__ import annotations

import base64
import io
import math

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.dpi": 150,
    "savefig.dpi": 200,
})

BLUE = "#2563eb"
ORANGE = "#f59e0b"
RED = "#dc2626"
GREEN = "#10b981"
GRAY = "#6b7280"

_METHOD_NAMES = {
    "air_resonance": "空气中共振法测声速",
    "water_phase": "水中相位法测声速",
    "tof": "飞行时间法测声速",
    "light_sine": "光速测量（正弦法）",
    "light_lissajous": "光速测量（李萨如法）",
}

# method -> [(column key, required length, 中文列描述), ...]
_COLUMNS = {
    "air_resonance": [("l", 12, "共振位置 l (mm)")],
    "water_phase": [("l", 12, "同相位位置 l (mm)")],
    "tof": [("L", 12, "传播距离 L (mm)"), ("T", 12, "飞行时间 T (μs)")],
    "light_sine": [
        ("T", 3, "差频周期 T (μs)"),
        ("dt", 3, "相位差 Δt (μs)"),
        ("x1", 3, "反射镜位置 x1 (mm)"),
        ("x2", 3, "反射镜位置 x2 (mm)"),
    ],
    "light_lissajous": [
        ("x1", 3, "直线位置 x1 (mm)"),
        ("x2", 3, "反斜率直线位置 x2 (mm)"),
    ],
}

_PARAM_DEFAULTS = {
    "air_resonance": {"temperature_degC": 25.0, "f_khz": 38.0},
    "water_phase": {"f_mhz": 1.0},
    "tof": {},
    "light_sine": {"f_mhz": 150.0, "c_ref": 299800000.0},
    "light_lissajous": {"f_mhz": 150.0, "c_ref": 299800000.0},
}

V0 = 331.45   # 0 °C 空气中声速参考值 (m/s)
T0 = 273.15   # 绝对零度参考 (K)
T95_5DOF = 2.571  # Student t, 置信 95%, 自由度 5


# ──────────────────────────────────────────────── rounding helpers

def _sig(x, n=4):
    """Round to n significant figures."""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if x == 0 or not math.isfinite(x):
        return x
    digits = n - 1 - int(math.floor(math.log10(abs(x))))
    return round(x, digits)


def _mean(vals):
    return sum(vals) / len(vals)


# ──────────────────────────────────────────────── validation

def _parse_col(rows, key, need_len, label, errors):
    """Extract numeric column; return list[float|None] or None on structural error."""
    raw = rows.get(key)
    if not isinstance(raw, list):
        errors.append(f"{label}：缺少该数据列，请检查输入")
        return None
    if len(raw) != need_len:
        errors.append(f"{label}：应有 {need_len} 个数据，实际收到 {len(raw)} 个")
        return None
    out = [None] * need_len
    n_valid = 0
    for i, v in enumerate(raw):
        if v is None:
            continue
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                continue
        try:
            out[i] = float(v)
            n_valid += 1
        except (TypeError, ValueError):
            errors.append(f"{label}：第 {i + 1} 个数据无法识别为数字")
    if n_valid == 0:
        errors.append(f"{label}：该列数据为空，请填写完整")
    return out


def _parse_params(method, params):
    used = {}
    defaults = _PARAM_DEFAULTS[method]
    params = params or {}
    for key, dflt in defaults.items():
        try:
            used[key] = float(params.get(key, dflt))
        except (TypeError, ValueError):
            used[key] = dflt
    return used


# ──────────────────────────────────────────────── figures

def _fig_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _positions_fig(xs, ls, title, dlm, lam_mm, extra):
    """air / water 通用主图：测量序号 vs 位置 l(mm)。"""
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    ax.grid(True, ls=":", lw=0.6, alpha=0.7)
    ax.plot(xs, ls, "-o", color=BLUE, ms=5, lw=1.4, label="测量点")
    txt = f"逐差平均间距 Δl ≈ {dlm:.4f} mm（≈ λ/2，λ ≈ {lam_mm:.4f} mm）"
    if extra:
        txt += "\n" + extra
    ax.text(0.02, 0.97, txt, transform=ax.transAxes, fontsize=9.5, va="top",
            bbox=dict(boxstyle="round,pad=0.35", fc="#f1f5f9", ec=BLUE, alpha=0.92))
    ax.set_xlabel("测量序号 i")
    ax.set_ylabel("l (mm)")
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    return _fig_b64(fig)


def _tof_fig(L, T, slope, r2, v_mean):
    """L(mm) 横轴 vs T(μs) 纵轴；拟合斜率单位为 μs/mm（= 1/(mm/μs)），
    声速 v = 1/斜率 mm/μs × 1000 = 1000/斜率 (m/s)。"""
    v_fit = 1000.0 / slope if slope else float("nan")
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    ax.grid(True, ls=":", lw=0.6, alpha=0.7)
    ax.scatter(L, T, s=42, color=ORANGE, zorder=3, label="测量点")
    xs = np.linspace(min(L), max(L), 50)
    ax.plot(xs, slope * xs, color=RED, lw=1.6, label="线性拟合 T = a·L")
    txt = (f"拟合斜率 a = {slope:.4f} μs/mm\n"
           f"换算 v = 1000/a ≈ {v_fit:.1f} m/s；R² = {r2:.4f}\n"
           f"逐点平均速度 v = {v_mean:.1f} m/s")
    ax.text(0.03, 0.95, txt, transform=ax.transAxes, fontsize=9.5, va="top",
            bbox=dict(boxstyle="round,pad=0.35", fc="#f1f5f9", ec=RED, alpha=0.92))
    ax.set_xlabel("传播距离 L (mm)")
    ax.set_ylabel("飞行时间 T (μs)")
    ax.set_title("飞行时间法：T 随 L 变化（v = 1/斜率 换算）")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    return _fig_b64(fig)


def _light_sine_fig(dt, dx2, slope, c_exp, err_rel, c_ref):
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    ax.grid(True, ls=":", lw=0.6, alpha=0.7)
    ax.scatter(dt, dx2, s=42, color=BLUE, zorder=3, label="测量点")
    if slope is not None:
        xs = np.linspace(min(dt), max(dt), 20)
        ax.plot(xs, slope * xs, color=RED, lw=1.6, label="线性拟合")
    txt = (f"c_exp ≈ {c_exp:.3e} m/s\n"
           f"相对误差 ≈ {err_rel:.2f} %（c_ref = {c_ref:.3e} m/s）")
    ax.text(0.03, 0.95, txt, transform=ax.transAxes, fontsize=9.5, va="top",
            bbox=dict(boxstyle="round,pad=0.35", fc="#f1f5f9", ec=BLUE, alpha=0.92))
    ax.set_xlabel("相位差 Δt (μs)")
    ax.set_ylabel("往返光程 2Δx (mm)")
    ax.set_title("光速正弦法：2Δx 随 Δt 变化")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    return _fig_b64(fig)


def _light_lissajous_fig(dx, dxm):
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    ax.grid(True, ls=":", lw=0.6, alpha=0.7)
    idx = list(range(1, len(dx) + 1))
    ax.scatter(idx, dx, s=60, color=BLUE, zorder=3, label="Δx 测量值")
    ax.axhline(dxm, color=RED, ls="--", lw=1.5, label="均值线")
    txt = (f"Δx 均值 ≈ {dxm:.2f} mm（对应 λ/4）\n"
           f"λ = 4·Δx_mean ≈ {4 * dxm / 1000:.4f} m")
    ax.text(0.03, 0.95, txt, transform=ax.transAxes, fontsize=9.5, va="top",
            bbox=dict(boxstyle="round,pad=0.35", fc="#f1f5f9", ec=BLUE, alpha=0.92))
    ax.set_xlabel("测量序号 i")
    ax.set_ylabel("Δx (mm)")
    ax.set_title("光速李萨如法：Δx 各次测量（π 相位差对应 λ/2 光程，位置移动 λ/4）")
    ax.set_xticks(idx)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    return _fig_b64(fig)


# ──────────────────────────────────────────────── per-method computation

def _calc_air_resonance(cols, p):
    l = cols["l"]
    n = len(l)
    dl = [(l[i + 6] - l[i]) / 6.0 for i in range(n - 6)]
    dlm = _mean(dl)
    lam_m = 2.0 * dlm * 1e-3          # mm -> m
    f_hz = p["f_khz"] * 1000.0
    v_exp = f_hz * lam_m
    v_theory = V0 * (1.0 + p["temperature_degC"] / T0)
    err_abs = abs(v_exp - v_theory)
    err_rel = err_abs / v_theory * 100.0
    results = [
        {"key": "v_exp", "label": "实验声速 v_exp", "value": _sig(v_exp), "unit": "m/s"},
        {"key": "v_theory", "label": "理论声速（温度修正）", "value": _sig(v_theory), "unit": "m/s"},
        {"key": "error_abs", "label": "绝对误差", "value": _sig(err_abs), "unit": "m/s"},
        {"key": "error_rel", "label": "相对误差", "value": round(err_rel, 2), "unit": "%"},
        {"key": "delta_l_mean", "label": "逐差平均间距 Δl", "value": round(dlm, 4), "unit": "mm"},
        {"key": "data_points", "label": "数据点数", "value": n, "unit": ""},
    ]
    s_dl = float(np.std(dl, ddof=1)) if len(dl) > 1 else 0.0
    b64 = _positions_fig(list(range(1, n + 1)), l, "空气中共振法：共振位置 l 随序号变化",
                         dlm, 2.0 * dlm,
                         f"v_exp ≈ {v_exp:.1f} m/s；v_theory ≈ {v_theory:.1f} m/s（t = {p['temperature_degC']:g} °C）")
    arrays = {"l": l, "delta_l": dl, "dlm": dlm, "s": s_dl,
              "v_exp": v_exp, "v_theory": v_theory, "err_rel": err_rel}
    return results, b64, arrays


def _calc_water_phase(cols, p):
    l = cols["l"]
    n = len(l)
    dl = [(l[i + 6] - l[i]) / 6.0 for i in range(n - 6)]
    dlm = _mean(dl)
    f_hz = p["f_mhz"] * 1e6
    lam_m = 2.0 * dlm * 1e-3
    v = f_hz * lam_m
    s_dl = float(np.std(dl, ddof=1)) if len(dl) > 1 else 0.0
    ua_dl_m = T95_5DOF * s_dl * 1e-3 / math.sqrt(6)   # 2.571*s/sqrt(6), mm -> m
    ua_v = 2.0 * f_hz * ua_dl_m                       # v = f*(2*Δl_m)
    results = [
        {"key": "v", "label": "水中声速 v", "value": _sig(v), "unit": "m/s"},
        {"key": "delta_l_mean", "label": "逐差平均间距 Δl", "value": round(dlm, 4), "unit": "mm"},
        {"key": "s_delta_l", "label": "Δl 标准差 s", "value": round(s_dl, 5), "unit": "mm"},
        {"key": "u_a", "label": "A 类不确定度 U_A", "value": _sig(ua_v), "unit": "m/s"},
    ]
    b64 = _positions_fig(list(range(1, n + 1)), l, "水中相位法：匹配位置 l 随序号变化",
                         dlm, 2.0 * dlm,
                         f"v ≈ {v:.1f} m/s；U_A ≈ {ua_v:.2f} m/s")
    arrays = {"l": l, "delta_l": dl, "dlm": dlm, "s": s_dl, "v": v, "u_a_v": ua_v}
    return results, b64, arrays


def _calc_tof(cols, p):
    L = cols["L"]
    T = cols["T"]
    n = len(L)
    v = [(L[i] * 1e-3) / (T[i] * 1e-6) for i in range(n)]
    v_mean = _mean(v)
    v_std = float(np.std(v, ddof=1)) if n > 1 else 0.0
    slope, intercept = np.polyfit(L, T, 1)
    yhat = slope * np.asarray(L) + intercept
    ss_res = float(np.sum((np.asarray(T) - yhat) ** 2))
    ss_tot = float(np.sum((np.asarray(T) - _mean(T)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    results = [
        {"key": "v_mean", "label": "平均声速 v", "value": _sig(v_mean), "unit": "m/s"},
        {"key": "v_std", "label": "标准差", "value": _sig(v_std), "unit": "m/s"},
    ]
    b64 = _tof_fig(L, T, float(slope), float(r2), v_mean)
    arrays = {"L": L, "T": T, "v": v, "v_mean": v_mean, "v_std": v_std,
              "slope": float(slope), "r2": float(r2)}
    return results, b64, arrays


def _calc_light_sine(cols, p):
    T = cols["T"]
    dt = cols["dt"]
    x1 = cols["x1"]
    x2 = cols["x2"]
    dx = [abs(x2[i] - x1[i]) for i in range(len(x1))]
    dxm = _mean(dx)
    tm = _mean(T)
    dtm = _mean(dt)
    lam_m = (tm / dtm) * 2.0 * dxm * 1e-3 if dtm != 0 else float("nan")
    f_hz = p["f_mhz"] * 1e6
    c_exp = f_hz * lam_m
    c_ref = p.get("c_ref", 299800000.0)
    err_rel = abs(c_exp - c_ref) / c_ref * 100.0
    results = [
        {"key": "c_exp", "label": "实验光速 c_exp", "value": _sig(c_exp), "unit": "m/s"},
        {"key": "error_rel", "label": "相对误差", "value": round(err_rel, 2), "unit": "%"},
        {"key": "t_mean", "label": "差频周期均值 T", "value": round(tm, 3), "unit": "μs"},
        {"key": "delta_t_mean", "label": "相位差均值 Δt", "value": round(dtm, 3), "unit": "μs"},
        {"key": "delta_x_mean", "label": "Δx 均值", "value": round(dxm, 1), "unit": "mm"},
    ]
    slope = None
    if np.ptp(dt) > 1e-9:
        slope, intercept = np.polyfit(dt, [2.0 * v for v in dx], 1)
    b64 = _light_sine_fig(dt, [2.0 * v for v in dx], float(slope) if slope is not None else None,
                          c_exp, err_rel, c_ref)
    arrays = {"T": T, "dt": dt, "x1": x1, "x2": x2, "dx": dx, "dxm": dxm,
              "t_mean": tm, "dt_mean": dtm, "c_exp": c_exp, "err_rel": err_rel}
    return results, b64, arrays


def _calc_light_lissajous(cols, p):
    x1 = cols["x1"]
    x2 = cols["x2"]
    dx = [abs(x2[i] - x1[i]) for i in range(len(x1))]
    dxm = _mean(dx)
    lam_m = 4.0 * dxm * 1e-3
    f_hz = p["f_mhz"] * 1e6
    c_exp = f_hz * lam_m
    c_ref = p.get("c_ref", 299800000.0)
    err_rel = abs(c_exp - c_ref) / c_ref * 100.0
    results = [
        {"key": "c_exp", "label": "实验光速 c_exp", "value": _sig(c_exp), "unit": "m/s"},
        {"key": "error_rel", "label": "相对误差", "value": round(err_rel, 2), "unit": "%"},
        {"key": "delta_x_mean", "label": "Δx 均值", "value": round(dxm, 1), "unit": "mm"},
    ]
    b64 = _light_lissajous_fig(dx, dxm)
    arrays = {"x1": x1, "x2": x2, "dx": dx, "dxm": dxm, "c_exp": c_exp, "err_rel": err_rel}
    return results, b64, arrays


_CALC = {
    "air_resonance": _calc_air_resonance,
    "water_phase": _calc_water_phase,
    "tof": _calc_tof,
    "light_sine": _calc_light_sine,
    "light_lissajous": _calc_light_lissajous,
}


# ──────────────────────────────────────────────── public API

def analyze(method, rows, params=None):
    """Full pipeline: validation + computation + main figure + arrays (for reports)."""
    if method not in _CALC:
        return {"status": "validation_error",
                "errors": [f"未知实验方法：{method}，可选 {list(_CALC.keys())}"],
                "results": [], "plots": {}, "arrays": {},
                "params_used": {}, "method": method}
    errors = []
    cols = {}
    for key, need_len, label in _COLUMNS[method]:
        parsed = _parse_col(rows or {}, key, need_len, label, errors)
        if parsed is not None:
            cols[key] = parsed
    # 逐差 / 配对计算要求完整数据
    for key, need_len, label in _COLUMNS[method]:
        parsed = cols.get(key)
        if parsed is None:
            continue
        for i, v in enumerate(parsed):
            if v is None:
                errors.append(f"{label}：第 {i + 1} 个数据缺失，请补全后再处理")
    if errors:
        return {"status": "validation_error", "errors": errors,
                "results": [], "plots": {}, "arrays": {},
                "params_used": {}, "method": method}
    try:
        params_used = _parse_params(method, params)
        results, b64, arrays = _CALC[method](cols, params_used)
    except Exception as exc:  # 除零等数值意外
        return {"status": "validation_error",
                "errors": [f"计算失败：{exc}"],
                "results": [], "plots": {}, "arrays": {},
                "params_used": {}, "method": method}
    return {"status": "success", "errors": [],
            "results": results, "plots": {"main": b64},
            "arrays": arrays, "params_used": params_used,
            "method": method, "method_name": _METHOD_NAMES[method]}


def process_method(method, rows, params=None):
    """前端处理接口：返回 {status, errors, results, plots}。"""
    full = analyze(method, rows, params)
    return {"status": full["status"], "errors": full["errors"],
            "results": full["results"], "plots": full["plots"]}
