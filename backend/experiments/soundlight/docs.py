#!/usr/bin/env python3
"""声速光速的测量（exp02）— 数据记录表与处理报告的 docbuild blocks。

record_blocks()                      空白数据记录表（遗留实现，供 docs.record_bytes；主接口 /api/record-sheets/sound-light.* 现由 record_clean.record_bytes 提供）
report_blocks(part, methods_data)    基准 / 拓展部分报告（供 /api/experiments/sound-light/report）
report_bytes(part, methods_data, fmt) 渲染为 docx/pdf 字节
"""

from __future__ import annotations

import base64
import io

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

from experiments.polarization.docbuild import render_docx, render_pdf
from experiments.soundlight import engine as sl

BLUE = "#2563eb"
ORANGE = "#f59e0b"
RED = "#dc2626"
GREEN = "#10b981"
GRAY = "#6b7280"

ORDER = ["air_resonance", "water_phase", "tof", "light_sine", "light_lissajous"]
METHOD_NAME = sl._METHOD_NAMES
METHOD_REQUIRED = {
    "air_resonance": True, "water_phase": True, "tof": False,
    "light_sine": True, "light_lissajous": True,
}

# ──────────────────────────────────────────────── formatting helpers

def _fx(v, nd=2):
    if v is None:
        return ""
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def _fmt(v):
    """Compact float formatting for result tables."""
    if v is None:
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    s = f"{f:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _fig_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _seq_rows(header, n_rows, extra_empty=0, prefill=True):
    """header: list[str]; returns rows [[序号cell, ...empty], ...]."""
    head = [{"text": h} for h in header]
    body = []
    for i in range(1, n_rows + 1):
        row = [{"text": str(i), "prefill": prefill}]
        row += [{} for _ in range(len(header) - 1 + extra_empty)]
        body.append(row)
    return [head] + body


# ──────────────────────────────────────────────── record sheet

def record_blocks() -> list[dict]:
    b: list[dict] = []
    b += [
        {"kind": "spacer", "cm": 0.05},
        {"kind": "h1", "text": "声速光速的测量 · 数据记录表"},
        {"kind": "para", "size": 9,
         "text": "姓名：＿＿＿＿　　学号：＿＿＿＿　　组号：＿＿＿＿　　实验日期：＿＿＿＿"},
        {"kind": "note", "text": "填写说明：空白格为手写原始数据，单位已标注在表头，只填数字；灰色序号为预填。逐差、均值与拟合由本地程序处理，可先手算核对。"},
        {"kind": "note", "text": "主要仪器与参数（在下方填写）：信号发生器 ______，示波器 ______，导轨/游标卡尺 ______，空气柱/水槽 ______。"},
        {"kind": "note", "text": "环境温度（读温度计）t = ______ °C；大气压 p = ______ Pa（可选记录）。"},
        {"kind": "spacer", "cm": 0.2},
    ]

    # ---------- 1 air ----------
    b += [
        {"kind": "h2", "text": "方法一（必做）· 空气中共振法测声速"},
        {"kind": "note", "text": "步骤：信号发生器驱动超声换能器 S1（约 38 kHz）；沿导轨同一方向缓慢移动 S2，在示波器上观察接收信号，驻波共振（幅值最大）时记录 S2 位置 l（mm）。连续记录 12 个共振位置。"},
        {"kind": "note", "text": "逐差法：Δl_i = (l(i+6) - l(i)) / 6（i = 1 到 6）；相邻共振位置相距 λ/2，λ = 2·Δl 平均值；v = f·λ。理论声速 v_t = 331.45×√(1 + t/273.15) m/s（t 为室温 °C）。"},
        {"kind": "note", "text": "环境温度 t = ______ °C　　共振频率 f = ______ kHz（约 38 kHz）"},
        {
            "kind": "table",
            "widths": [4.4, 12.0],
            "font": 8,
            "row_h": 0.5,
            "rows": _seq_rows(["序号", "共振位置 l (mm)"], 12),
        },
        {"kind": "note", "text": "提示：测量过程中 S2 只能沿一个方向移动，避免回程间隙引入系统误差。"},
        {"kind": "spacer", "cm": 0.9},
    ]

    # ---------- 2 water ----------
    b += [
        {"kind": "h2", "text": "方法二（必做）· 水中相位法测声速"},
        {"kind": "note", "text": "步骤：两只换能器浸入水中（超声频率约 1 MHz），示波器置于 X-Y 模式观察李萨如图形；移动 S2，图形为直线（相位差 0 或 π）时记录位置 l（mm）。连续记录 12 个匹配位置（相邻约 λ/2）。"},
        {"kind": "note", "text": "处理：逐差 Δl_i = (l(i+6) - l(i)) / 6，λ = 2·Δl 平均值，v = f·λ；并计算 Δl 标准差 s 与 A 类不确定度 U_A = 2.571·s/√6（t 分布，自由度 5，再按 v = f·2Δl 换算为 m/s）。"},
        {"kind": "note", "text": "水中超声频率 f = ______ MHz（约 1 MHz）"},
        {
            "kind": "table",
            "widths": [4.4, 12.0],
            "font": 8,
            "row_h": 0.5,
            "rows": _seq_rows(["序号", "匹配位置 l (mm)"], 12),
        },
        {"kind": "note", "text": "提示：记录时应选择图形为同一判据（如同向直线），并沿同一方向移动。"},
        {"kind": "spacer", "cm": 0.9},
    ]

    # ---------- 3 tof ----------
    b += [
        {"kind": "h2", "text": "方法三（选做）· 飞行时间法测声速"},
        {"kind": "note", "text": "步骤：信号发生器置脉冲/猝发模式，S1 固定；S2 从 L 约 40 mm 起每次移动 20 mm，在示波器上读出发射脉冲与接收脉冲的时间间隔 T（μs）。共 12 组 (L, T)。"},
        {"kind": "note", "text": "处理：每点速度 v_i = (L 换算为 m)/(T 换算为 s) = L(mm)/T(μs) × 1000 (m/s)，取平均；图中对 L-T 线性拟合得斜率 a（μs/mm），v = 1000/a (m/s)。"},
        {"kind": "note", "text": "起始读数 L 起点：______ mm；本方法为选做，可结合前两法结果对比空气中声速的一致性。"},
        {
            "kind": "table",
            "widths": [3.0, 6.7, 6.7],
            "font": 8,
            "row_h": 0.5,
            "rows": _seq_rows(["序号", "传播距离 L (mm)", "飞行时间 T (μs)"], 12),
        },
        {"kind": "spacer", "cm": 0.9},
    ]

    # ---------- 4 light sine ----------
    b += [
        {"kind": "h2", "text": "方法四（必做）· 光速测量（正弦法）"},
        {"kind": "note", "text": "步骤：光速测量仪差频信号接示波器。周期 T：水平时基 0.5 μs/DIV 读一周格数换算（μs），重复 3 次；相位差 Δt：0.2 μs/DIV 读两路信号同相位点时间差（μs），并记录此时反射镜位置 x1、x2（导轨 mm 刻度），共 3 组。调制频率约 150 MHz。"},
        {"kind": "note", "text": "处理：Δx = |x2 - x1|，逐点 r_i = Δx_i/Δt_i (mm/μs) 取平均 r_mean；λ(mm) = 2×T平均(μs)×r_mean(mm/μs)；c = f·λ（mm 换算 m），与 c0 = 2.998×10^8 m/s 比较。"},
        {
            "kind": "table",
            "widths": [4.4, 12.0],
            "font": 8,
            "row_h": 0.5,
            "rows": _seq_rows(["序号", "差频周期 T (μs)"], 3),
        },
        {"kind": "note", "text": "下表：每次调出相同相位差（同相位点）时记录 Δt 与反射镜两位置。"},
        {
            "kind": "table",
            "widths": [2.4, 3.5, 3.5, 3.5, 3.5],
            "font": 8,
            "row_h": 0.5,
            "rows": _seq_rows(["序号", "相位差 Δt (μs)", "位置 x1 (mm)", "位置 x2 (mm)", "Δx (mm)"], 3),
        },
        {"kind": "note", "text": "提示：Δx = |x2 - x1| 可手算核对；Δx 与 Δt 应近似同步增大/减小（每点 2Δx/Δt 一致）。"},
        {"kind": "spacer", "cm": 0.9},
    ]

    # ---------- 5 light lissajous ----------
    b += [
        {"kind": "h2", "text": "方法五（必做）· 光速测量（李萨如法）"},
        {"kind": "note", "text": "步骤：X-Y 模式观察差频李萨如图。缓慢移动反射镜，图形为直线（斜率 +k）时记 x1；继续同向移动至反斜率直线（-k，相位差 π，对应光程差 λ/2、位置移动 λ/4）时记 x2。重复 3 组。"},
        {"kind": "note", "text": "处理：Δx = |x2 - x1|，λ = 4·Δx 平均；c = f·λ（f 约 150 MHz），与 c_ref 比较。"},
        {
            "kind": "table",
            "widths": [2.4, 3.5, 3.5, 3.5, 3.5],
            "font": 8,
            "row_h": 0.5,
            "rows": _seq_rows(["序号", "直线位置 x1 (mm)", "反斜率位置 x2 (mm)", "Δx (mm)", "Δx 手算核对"], 3),
        },
        {"kind": "note", "text": "提示：保持 S2 移动方向不变；若波形不是直线说明未对准同相位点，需微调重测。"},
        {"kind": "spacer", "cm": 0.9},
    ]
    # ---------- teacher comment area ----------
    b += [
        {"kind": "h2", "text": "教师批注与成绩评定"},
        {"kind": "note", "text": "以下留白，供教师批注、评分与签名："},
        {"kind": "lines", "n": 8},
        {"kind": "spacer", "cm": 0.4},
    ]
    return b


# ──────────────────────────────────────────────── advanced figures

def _adv_delta_l_fig(name, arrays):
    dl = arrays["delta_l"]
    dlm = arrays.get("dlm", float(np.mean(dl)))
    s = arrays.get("s", float(np.std(dl, ddof=1)) if len(dl) > 1 else 0.0)
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.grid(True, axis="y", ls=":", lw=0.6, alpha=0.7)
    idx = list(range(1, len(dl) + 1))
    ax.bar(idx, dl, width=0.62, color=BLUE, alpha=0.85, label="Δl_i")
    ax.axhline(dlm, color=RED, ls="--", lw=1.5, label=f"均值 {dlm:.4f} mm")
    if s > 0:
        ax.axhspan(dlm - s, dlm + s, color=GRAY, alpha=0.16, label=f"±1σ（σ = {s:.4f} mm）")
    ax.text(0.02, 0.96, f"Δl 均值 = {dlm:.4f} mm，标准差 s = {s:.4f} mm",
            transform=ax.transAxes, fontsize=9, va="top",
            bbox=dict(boxstyle="round,pad=0.3", fc="#f1f5f9", ec=BLUE, alpha=0.9))
    ax.set_xlabel("逐差序号 i")
    ax.set_ylabel("Δl_i (mm)")
    ax.set_xticks(idx)
    ax.set_title(f"{name}：逐差 Δl_i 分布")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return _fig_b64(fig)


def _adv_tof_fig(arrays):
    v = arrays["v"]
    v_mean = arrays["v_mean"]
    v_std = arrays.get("v_std", float(np.std(v, ddof=1)) if len(v) > 1 else 0.0)
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.grid(True, ls=":", lw=0.6, alpha=0.7)
    idx = list(range(1, len(v) + 1))
    ax.plot(idx, v, "-o", color=ORANGE, ms=5, lw=1.4, label="逐点声速 v_i")
    ax.axhline(v_mean, color=RED, ls="--", lw=1.5, label=f"均值 {v_mean:.1f} m/s")
    ax.text(0.02, 0.96, f"v 平均 = {v_mean:.1f} m/s，标准差 = {v_std:.1f} m/s",
            transform=ax.transAxes, fontsize=9, va="top",
            bbox=dict(boxstyle="round,pad=0.3", fc="#f1f5f9", ec=ORANGE, alpha=0.9))
    ax.set_xlabel("测量序号 i")
    ax.set_ylabel("v_i (m/s)")
    ax.set_xticks(idx)
    ax.set_title("飞行时间法：逐点声速 v_i")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return _fig_b64(fig)


def _adv_light_compare_fig(entries, c_ref):
    """entries: list[(中文方法名, c_exp, err_rel)]（一或两个方法）。"""
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    ax.grid(True, axis="y", ls=":", lw=0.6, alpha=0.7)
    names = [e[0] for e in entries]
    vals = [e[1] / 1e8 for e in entries]
    x = np.arange(len(entries))
    bars = ax.bar(x, vals, width=0.45, color=[BLUE, GREEN][:len(entries)], alpha=0.85)
    ax.axhline(c_ref / 1e8, color=RED, ls="--", lw=1.6, label=f"c_ref = {c_ref/1e8:.3f}×10^8 m/s")
    for xi, (nm, c, err) in zip(x, entries):
        ax.text(xi, vals[xi] + 0.003, f"{vals[xi]:.3f}\n({err:.2f}%)",
                ha="center", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9.5)
    ax.set_ylabel("c_exp (10^8 m/s)")
    ax.set_title("光速测量：正弦法与李萨如法结果对比")
    ax.legend(fontsize=8.5)
    fig.tight_layout()
    return _fig_b64(fig)


# ──────────────────────────────────────────────── report helpers

def _run(mid, methods_data):
    item = (methods_data or {}).get(mid)
    if not item or not item.get("rows"):
        return None
    return sl.analyze(mid, item.get("rows", {}), item.get("params", {}))


def _hdr(cells):
    return [{"text": c} for c in cells]


def _tab(rows, widths, font=8, row_h=0.45):
    return {"kind": "table", "widths": widths, "font": font,
            "row_h": row_h, "rows": rows}


def _cap(text):
    return {"kind": "note", "text": text}


def _res(run, key):
    """run 的 results 中按 key 取结果项。"""
    for item in run.get("results", []):
        if item.get("key") == key:
            return item
    return None


def _res_txt(run, key):
    item = _res(run, key)
    if item is None:
        return "-"
    return f"{_fmt(item.get('value'))} {item.get('unit', '')}".strip()


def _results_block_keys(run, keys):
    """按 key 顺序取结果的 2 列小表（数值来自 engine.analyze，勿重算）。"""
    rows = []
    for k in keys:
        item = _res(run, k)
        if item is not None:
            rows.append([{"text": item["label"]},
                         {"text": f"{_fmt(item.get('value'))} {item.get('unit', '')}".strip()}])
    return _tab([_hdr(["结果项", "数值"])] + rows, [8.6, 8.8], font=8.5, row_h=0.5)


def _dl_table(dl):
    """逐差 Δl_i 小表（i = 1..6）。"""
    rows = [_hdr(["逐差序号 i", "Δl_i (mm)"])] + \
           [[{"text": str(i + 1)}, {"text": _fx(v, 4)}] for i, v in enumerate(dl)]
    return _tab(rows, [4.2, 12.8], font=8, row_h=0.42)


# ──────────────────────────────────────────────── part reports

def _head_blocks(part_title, note):
    return [
        {"kind": "spacer", "cm": 0.2},
        {"kind": "h1", "text": f"声速光速的测量 · 数据处理报告（{part_title}）"},
        {"kind": "sub", "text": note},
        {"kind": "spacer", "cm": 0.1},
    ]


def _basic_blocks(methods_data) -> list[dict]:
    b = _head_blocks(
        "基准部分",
        "依据讲义【数据处理】生成：原始数据规范作表，逐差与平均值计算、A 类不确定度评估"
        "（置信概率 95%）及误差比较；本实验讲义未要求作图（图见拓展部分）。"
        "仅包含已提交且通过校验的方法。")
    present, failed = [], []
    for mid in ORDER:
        item = (methods_data or {}).get(mid)
        if not item or not item.get("rows"):
            continue
        run = _run(mid, methods_data)
        if run is None:
            continue
        if run["status"] == "success":
            present.append((mid, run))
        else:
            failed.append((mid, run))
    if not present:
        b.append({"kind": "note", "text": "没有可处理的已提交方法数据，本报告暂无可计算内容。"})
        return b
    names = "；".join(f"{i + 1}. {METHOD_NAME[mid]}"
                      f"（{'必做' if METHOD_REQUIRED[mid] else '选做'}）"
                      for i, (mid, run) in enumerate(present))
    intro = f"已提交方法（共 {len(present)} 项）：{names}。"
    if failed:
        intro += " 以下方法数据未通过校验，未参与计算：" + "、".join(METHOD_NAME[m] for m, _ in failed) + "。"
    b.append({"kind": "note", "text": intro})
    for m, run in failed:
        b.append({"kind": "note", "text": f"{METHOD_NAME[m]} 校验未通过：" + "；".join(run["errors"])})
    b.append({"kind": "spacer", "cm": 0.05})

    air_run = next((r for m, r in present if m == "air_resonance"), None)
    wat_run = next((r for m, r in present if m == "water_phase"), None)
    tof_run = next((r for m, r in present if m == "tof"), None)
    sin_run = next((r for m, r in present if m == "light_sine"), None)
    lis_run = next((r for m, r in present if m == "light_lissajous"), None)

    # ════════════ 一、原始数据表 ════════════
    b.append({"kind": "h2", "text": "一、原始数据表"})
    b.append({"kind": "note",
              "text": "下表与讲义记录表同构（空气中共振法与水中相位法共讲义表1-1，未提交方法的列留空，便于补齐）；"
                      "表2-1 至表2-3 与讲义表2-1 至表2-3 对应。Δx = |x2 - x1|；Δx/Δt 为按行计算的派生列。"})
    if air_run or wat_run:
        b.append(_cap("表1-1  共振干涉法、相位比较法数据记录"))
        a_l = air_run.get("arrays", {}).get("l", []) if air_run else []
        w_l = wat_run.get("arrays", {}).get("l", []) if wat_run else []
        rows = [_hdr(["测量次数", "空气中共振法 l (mm)", "水中相位法 l (mm)"])]
        for i in range(12):
            rows.append([{"text": str(i + 1)},
                         {"text": _fx(a_l[i], 2) if i < len(a_l) and a_l[i] is not None else ""},
                         {"text": _fx(w_l[i], 2) if i < len(w_l) and w_l[i] is not None else ""}])
        b.append(_tab(rows, [3.2, 6.9, 6.9], font=8, row_h=0.45))
        pa = (air_run or {}).get("params_used", {})
        pw = (wat_run or {}).get("params_used", {})
        tok_air = f"f空气 = {pa['f_khz']:g} kHz" if air_run else "f空气 = -"
        tok_wat = f"f水 = {pw['f_mhz']:g} MHz" if wat_run else "f水 = -"
        tok_t = f"环境室温 t = {pa['temperature_degC']:g} °C" if air_run else "环境室温 t = -"
        b.append({"kind": "note", "text": f"{tok_air}；{tok_wat}；{tok_t}（参数按各自提交值）"})
        b.append({"kind": "spacer", "cm": 0.1})
    if tof_run:
        b.append(_cap("表（选做）时差法数据记录：飞行时间法测水中声速"))
        a = tof_run["arrays"]
        L, T = a["L"], a["T"]
        rows = [_hdr(["测量次数", "传播距离 L (mm)", "飞行时间 T (μs)"])]
        for i in range(12):
            rows.append([{"text": str(i + 1)}, {"text": _fx(L[i], 1)}, {"text": _fx(T[i], 2)}])
        b.append(_tab(rows, [3.4, 6.8, 6.8], font=8, row_h=0.45))
        b.append({"kind": "spacer", "cm": 0.1})
    if sin_run:
        a = sin_run["arrays"]
        T = a.get("T", [])
        b.append(_cap("表2-1  差频后波形的周期测量（水平偏转因子 0.5 μs/DIV）"))
        rows = [_hdr(["测量次数", "周期 T (μs)"])] + \
               [[{"text": str(i + 1)}, {"text": _fx(v, 3)}] for i, v in enumerate(T)]
        b.append(_tab(rows, [4.4, 12.6], font=8, row_h=0.45))
        b.append({"kind": "spacer", "cm": 0.08})
        b.append(_cap("表2-2  参考点在水平时间轴移动距离 Δt 与滑块移动距离 Δx（水平偏转因子 0.2 μs/DIV）"))
        dt, x1, x2, dx, r = a.get("dt", []), a.get("x1", []), a.get("x2", []), a.get("dx", []), a.get("r", [])
        rows = [_hdr(["测量次数", "Δt (μs)", "x1 (mm)", "x2 (mm)", "Δx (mm)", "Δx/Δt (mm/μs)"])]
        for i in range(len(dt)):
            rows.append([{"text": str(i + 1)},
                         {"text": _fx(dt[i], 2)}, {"text": _fx(x1[i], 2)},
                         {"text": _fx(x2[i], 2)}, {"text": _fx(dx[i], 2)},
                         {"text": _fx(r[i], 3) if i < len(r) else ""}])
        b.append(_tab(rows, [1.7, 2.9, 2.9, 2.9, 3.0, 3.6], font=8, row_h=0.45))
        b.append({"kind": "spacer", "cm": 0.1})
    if lis_run:
        a = lis_run["arrays"]
        x1, x2, dx = a.get("x1", []), a.get("x2", []), a.get("dx", [])
        b.append(_cap("表2-3  反射镜滑块移动的距离 Δx（李萨如图形法）"))
        rows = [_hdr(["测量次数", "x1 (mm)", "x2 (mm)", "Δx (mm)"])]
        for i in range(len(x1)):
            rows.append([{"text": str(i + 1)},
                         {"text": _fx(x1[i], 2)}, {"text": _fx(x2[i], 2)},
                         {"text": _fx(dx[i], 2)}])
        b.append(_tab(rows, [3.0, 4.6, 4.6, 4.6], font=8, row_h=0.45))
        b.append({"kind": "spacer", "cm": 0.1})

    # ════════════ 二、数据处理 ════════════
    b.append({"kind": "h2", "text": "二、数据处理"})
    b.append({"kind": "note", "text": "以下数值全部取自本地数据分析结果（与处理接口同源同公式），不另做手算。"})
    if air_run or wat_run or tof_run:
        b.append({"kind": "h3", "text": "处理 1：超声声速测量"})
        b.append({"kind": "spacer", "cm": 0.02})
    if air_run:
        b.append({"kind": "h3", "text": "处理 1a：共振干涉法测空气中声速（必做）"})
        a = air_run["arrays"]
        pa = air_run["params_used"]
        b.append(_cap("逐差法（讲义附1）：Δl_i = (l(i+6) - l(i))/6，i = 1 到 6；l(1) 至 l(12) 为表1-1 中"
                      "第 1 至第 12 次共振位置读数（mm），逐差平均间距即半波长 Δl。"))
        b.append(_cap("逐差结果 Δl_i（i = 1 到 6）："))
        b.append(_dl_table(a.get("delta_l", [])))
        lam_mm = a.get("lam_mm", 0.0)
        b.append(_cap(f"Δl 平均值（半波长 Δl） = {_res_txt(air_run, 'delta_l_mean')}，波长 λ = 2×Δl ≈ {_fx(lam_mm, 3)} mm；"
                      f"mm 换算 m 后 v_exp = f×λ = 2×f×Δl（f = {pa['f_khz']:g} kHz）→ {_res_txt(air_run, 'v_exp')}。"))
        b.append(_cap(f"理论声速（室温 t = {pa['temperature_degC']:g} °C）：v_theory = 331.45×√(1 + t/273.15) m/s"
                      f"（0 °C 时 v0 = 331.45 m/s）→ {_res_txt(air_run, 'v_theory')}。"))
        b.append(_cap(f"误差比较：绝对误差 = |v_exp - v_theory| = {_res_txt(air_run, 'error_abs')}；"
                      f"相对误差 = {_res_txt(air_run, 'error_rel')}。"))
        b.append(_results_block_keys(air_run, ["delta_l_mean", "v_exp", "v_theory",
                                               "error_abs", "error_rel"]))
        b.append({"kind": "spacer", "cm": 0.04})
    if wat_run:
        b.append({"kind": "h3", "text": "处理 1b：相位比较法测水中声速（必做）"})
        a = wat_run["arrays"]
        pw = wat_run["params_used"]
        b.append(_cap("逐差法同处理 1a：Δl_i = (l(i+6) - l(i))/6，i = 1 到 6；逐差平均间距即半波长 Δl。"))
        b.append(_cap("逐差结果 Δl_i（i = 1 到 6）："))
        b.append(_dl_table(a.get("delta_l", [])))
        b.append(_cap(f"Δl 平均值（半波长 Δl） = {_res_txt(wat_run, 'delta_l_mean')}；水中声速"
                      f" v = 2×f×Δl（f = {pw['f_mhz']:g} MHz，mm 换算 m）→ {_res_txt(wat_run, 'v')}。"))
        ua_m = a.get("ua_dl_m", 0.0) * 1e6
        b.append(_cap(f"A 类不确定度评估（讲义附2：半波长 Δl 由 12 组数据逐差得出，测量次数 n = 6，置信概率 95%）："
                      f"Δl 标准差 s(Δl) = {_fx(a.get('s', 0.0), 5)} mm（贝塞尔公式）；t 分布临界值 t0.95（自由度 5）= 2.571；"
                      f"U_A(Δl) = 2.571×s(Δl)/√6 = {_fx(a.get('ua_dl_mm', 0.0), 5)} mm = {_fx(ua_m, 3)}×10^-6 m（换算 m）；"
                      f"由 v = 2×f×Δl 误差传递：U_A(v) = 2×f×U_A(Δl) = {_res_txt(wat_run, 'u_a')}。"))
        b.append(_results_block_keys(wat_run, ["delta_l_mean", "v", "s_delta_l", "u_a"]))
        b.append({"kind": "spacer", "cm": 0.04})
    if tof_run:
        b.append({"kind": "h3", "text": "处理 1c：时差法测水中声速（选做）"})
        a = tof_run["arrays"]
        L, T, v = a["L"], a["T"], a["v"]
        b.append(_cap("每点速度 v_i = L_i/T_i：L_i(mm) 换算 m、T_i(μs) 换算 s，即 v_i = L_i(mm)/T_i(μs)×1000 (m/s)。"))
        rows = [_hdr(["测量次数", "L (mm)", "T (μs)", "v_i (m/s)"])] + \
               [[{"text": str(i + 1)}, {"text": _fx(L[i], 1)}, {"text": _fx(T[i], 2)},
                 {"text": _fx(v[i], 1)}] for i in range(len(L))]
        b.append(_tab(rows, [2.0, 4.6, 5.0, 5.2], font=8, row_h=0.42))
        b.append(_cap(f"平均声速 = {_res_txt(tof_run, 'v_mean')}；标准差 = {_res_txt(tof_run, 'v_std')}"
                      f"（本方法讲义未细述处理过程，给出平均值与标准差即可）。"))
        b.append({"kind": "spacer", "cm": 0.04})
    if sin_run or lis_run:
        b.append({"kind": "h3", "text": "处理 2：光速测量"})
        b.append({"kind": "spacer", "cm": 0.02})
    if sin_run:
        b.append({"kind": "h3", "text": "处理 2a：相位差法（正弦波）测空气中光速（必做）"})
        a = sin_run["arrays"]
        pa = sin_run["params_used"]
        r_items = "、".join(_fx(vv, 3) for vv in a.get("r", []))
        lam_mm = a.get("lam_mm", 0.0)
        lam_m = lam_mm * 1e-3
        b.append(_cap(f"差频后波形周期测量结果的平均值（表2-1 数据）：T = (T1 + T2 + T3)/3 = {_res_txt(sin_run, 't_mean')}。"))
        b.append(_cap(f"逐点比值 r_i = Δx_i/Δt_i（表2-2 派生列，单位 mm/μs）：{r_items}；"
                      f"Δx/Δt 的平均值 = {_res_txt(sin_run, 'r_mean')}。"))
        b.append(_cap(f"调制波频率 f_t = {pa['f_mhz']:g} MHz = {pa['f_mhz']:g}×10^6 Hz；"
                      f"调制波长 λ(mm) = 2×T(μs)×r_mean(mm/μs) = {_fx(lam_mm, 1)} mm ≈ {_fx(lam_m, 4)} m；"
                      f"c_exp = f_t×λ = {_res_txt(sin_run, 'c_exp')}。"))
        b.append(_cap(f"与空气中光速理论值 c0 = 2.998×10^8 m/s（可用真空光速近似）比较："
                      f"绝对误差 = {_res_txt(sin_run, 'error_abs')}；相对误差 = {_res_txt(sin_run, 'error_rel')}。"))
        b.append(_results_block_keys(sin_run, ["t_mean", "r_mean", "c_exp", "error_abs", "error_rel"]))
        b.append({"kind": "spacer", "cm": 0.04})
    if lis_run:
        b.append({"kind": "h3", "text": "处理 2b：李萨如图形法测空气中光速（必做）"})
        a = lis_run["arrays"]
        pa = lis_run["params_used"]
        dx_items = "、".join(_fx(vv, 2) for vv in a.get("dx", []))
        lam_mm = a.get("lam_mm", 0.0)
        lam_m = lam_mm * 1e-3
        b.append(_cap(f"Δx = |x2 - x1|（表2-3）三次测量：{dx_items} mm；Δx 的平均值 = {_res_txt(lis_run, 'delta_x_mean')}。"))
        b.append(_cap(f"李萨如图形由直线变为反斜率直线时相位差改变 π，对应光程差 λ/2、反射镜移动 Δx = λ/4："
                      f"λ = 4×Δx = {_fx(lam_mm, 2)} mm = {_fx(lam_m, 4)} m；c_exp = f_t×λ"
                      f"（f_t = {pa['f_mhz']:g} MHz）= {_res_txt(lis_run, 'c_exp')}。"))
        b.append(_cap(f"与空气中光速理论值 c0 = 2.998×10^8 m/s 比较："
                      f"绝对误差 = {_res_txt(lis_run, 'error_abs')}；相对误差 = {_res_txt(lis_run, 'error_rel')}。"))
        b.append(_results_block_keys(lis_run, ["delta_x_mean", "c_exp", "error_abs", "error_rel"]))
        b.append({"kind": "spacer", "cm": 0.04})

    b.append({"kind": "h3", "text": "处理 3：误差来源分析"})
    b.append({"kind": "note",
              "text": "（1）仪器类：示波器水平时基分度值标称误差与水平微调校准误差；信号源频率标称偏差"
                      "（共振频率 f、水中频率 f 与调制频率 f_t 均以仪器显示为准）；导轨标尺与读数装置的刻度、零位误差。"
                      "（2）读数类：驻波共振幅值极大点平台较宽，极大位置判定不灵敏带来随机误差；李萨如图形直线判据"
                      "（同斜率/反斜率直线与相位对准）存在主观读数误差；示波器上参考点水平移动格数按 0.2 μs/DIV 判读存在量化误差。"
                      "（3）方法/理论近似：声速理论值按干燥理想气体公式计算，未计湿度、气压与 CO2 含量影响；"
                      "光速测量以真空光速 c0 近似空气中光速（空气折射率 n ≈ 1）；差频相位-位移关系假定波形严格正弦、线性良好。"
                      "（4）环境类：室温波动改变空气声速，水中温度不均与液面晃动影响水声速；换能器端面与反射镜移动方向"
                      "不严格平行、回程间隙引入系统误差。改进方向：多次测量取平均、单方向匀速移动、提高时基分辨并统一判据。"})
    b.append({"kind": "spacer", "cm": 0.05})
    b.append({"kind": "note",
              "text": "说明：数据处理由 PhysicsLab 本地服务完成；声速/光速取 4 位有效数字，相对误差保留两位小数，"
                      "逐差间距保留毫米级 4-5 位小数。讲义实验内容未要求作图，相关图形见拓展部分。"})
    return b


def _advanced_blocks(methods_data) -> list[dict]:
    b = _head_blocks(
        "拓展部分",
        "各方法原始数据主图（自基准报告移入）与误差分析：逐差分布（含 ±1σ 带）、逐点速度一致性、"
        "光速两法对比，以及结论与误差讨论留白（仅包含已提交且通过校验的方法）。")
    present = []
    for mid in ORDER:
        run = _run(mid, methods_data)
        if run is not None and run["status"] == "success":
            present.append((mid, run))
    n = 0
    for mid, run in present:
        arrays = run.get("arrays", {})
        main_b64 = run.get("plots", {}).get("main")
        if main_b64:
            n += 1
            b.append({"kind": "h2", "text": f"图 {n} · {METHOD_NAME[mid]}：原始数据主图"})
            b.append({"kind": "image", "b64": main_b64, "width_cm": 15.6,
                      "caption": f"原图 · {METHOD_NAME[mid]}（基准报告主图，移入拓展部分）"})
            if mid == "tof":
                note = "此图即原基准主图：T 随 L 线性拟合，斜率 a 单位 μs/mm，换算声速 v = 1000/a。"
            elif mid == "light_sine":
                note = "此图即原基准主图：往返光程 2Δx 随相位差 Δt 变化；逐点比值 Δx/Δt 见基准报告表2-2。"
            elif mid == "light_lissajous":
                note = "此图即原基准主图：各次测量 Δx 与均值线（λ = 4×Δx_mean）。"
            else:
                note = "此图即原基准主图：测量位置 l 随测量序号变化。"
            b.append({"kind": "note", "text": note})
            b.append({"kind": "spacer", "cm": 0.1})
        if mid in ("air_resonance", "water_phase"):
            n += 1
            b.append({"kind": "h2", "text": f"图 {n} · {METHOD_NAME[mid]}：逐差 Δl_i 分布"})
            b.append({"kind": "image", "b64": _adv_delta_l_fig(METHOD_NAME[mid], arrays),
                      "width_cm": 15.6})
            note = ("分析要点：Δl_i 应围绕均值随机涨落。柱体落入 ±1σ 带的比例反映随机误差水平；"
                    "若出现趋势性漂移，提示 S2 移动方向/回程间隙引入系统误差。")
            if mid == "water_phase":
                note += f" 由 Δl 标准差换算的 A 类不确定度 U_A ≈ {arrays.get('u_a_v', 0):.2f} m/s。"
            b.append({"kind": "note", "text": note})
            b.append({"kind": "spacer", "cm": 0.12})
        elif mid == "tof":
            n += 1
            b.append({"kind": "h2", "text": f"图 {n} · 飞行时间法：逐点声速 v_i"})
            b.append({"kind": "image", "b64": _adv_tof_fig(arrays), "width_cm": 15.6})
            b.append({"kind": "note",
                      "text": "分析要点：各点 v_i 应围绕均值随机涨落；观察首末点偏差可判断 L 起点读数与触发时刻的系统误差。"})
            b.append({"kind": "spacer", "cm": 0.12})
    light_entries = []
    for mid in ("light_sine", "light_lissajous"):
        for m2, run in present:
            if m2 == mid:
                arr = run.get("arrays", {})
                short = "正弦法" if mid == "light_sine" else "李萨如法"
                light_entries.append((short, arr["c_exp"], arr["err_rel"]))
    if light_entries:
        c_ref = 299800000.0
        for mid in ("light_sine", "light_lissajous"):
            for m2, run in present:
                if m2 == mid:
                    c_ref = run.get("params_used", {}).get("c_ref", c_ref)
        n += 1
        b.append({"kind": "h2", "text": f"图 {n} · 光速测量：正弦法与李萨如法结果对比"})
        b.append({"kind": "image", "b64": _adv_light_compare_fig(light_entries, c_ref),
                  "width_cm": 15.6})
        b.append({"kind": "note",
                  "text": "分析要点：两法实验光速与 c_ref 的相对误差、两法之间的一致性；"
                          "误差主要来源（Δx 读数、ΔT/Δt 时基判读、频率标称值偏差）讨论。"})
        b.append({"kind": "spacer", "cm": 0.12})
    b.append({"kind": "h2", "text": "结论与误差讨论"})
    b.append({"kind": "note",
              "text": "请结合上述图表撰写结论（Word 中可直接编辑，PDF 留白供手写）：总结各方法测得声速/光速与理论值（c_ref）的偏差、"
                      "不确定度来源与改进建议。"})
    b.append({"kind": "lines", "n": 5})
    return b


def report_blocks(part: str, methods_data: dict) -> list[dict]:
    if part == "advanced":
        return _advanced_blocks(methods_data or {})
    return _basic_blocks(methods_data or {})


def report_bytes(part: str, methods_data: dict, fmt: str = "docx") -> bytes:
    blocks = report_blocks(part, methods_data)
    if fmt == "docx":
        return render_docx(blocks)
    return render_pdf(blocks)


def record_bytes(fmt: str = "docx") -> bytes:
    blocks = record_blocks()
    if fmt == "docx":
        return render_docx(blocks)
    return render_pdf(blocks)
