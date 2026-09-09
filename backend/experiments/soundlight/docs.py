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
METHOD_PURPOSE = {
    "air_resonance": "利用空气驻波共振位置测量声速：12 个共振位置逐差得半波长，v = f·λ，与温度修正理论值比较。",
    "water_phase": "利用相位比较法（李萨如直线判据）测量水中声速，并给出 Δl 的 A 类不确定度。",
    "tof": "测量脉冲超声波飞行时间 T（μs）与传播距离 L（mm），由 v = L/T 求声速（选做）。",
    "light_sine": "利用差频正弦波的周期 T、相位差 Δt 与反射镜位移 Δx 测量调制波长，进而得到光速。",
    "light_lissajous": "利用李萨如图 π 相位变化（直线转反斜率直线，移动 λ/4）测量光速。",
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
        {"kind": "note", "text": "逐差法：Δl_i = (l(i+6) - l(i)) / 6（i = 1 到 6）；相邻共振位置相距 λ/2，λ = 2·Δl 平均值；v = f·λ。理论声速 v_theory = 331.45 × (1 + t/273.15) m/s。"},
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
        {"kind": "note", "text": "处理：Δx = |x2 - x1|；λ = (T 平均/Δt 平均) × 2Δx 平均；c = f·λ，与 c_ref = 2.998×10^8 m/s 比较。"},
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


# ──────────────────────────────────────────────── raw-data table builders

def _run(mid, methods_data):
    item = (methods_data or {}).get(mid)
    if not item or not item.get("rows"):
        return None
    return sl.analyze(mid, item.get("rows", {}), item.get("params", {}))


def _raw_blocks(mid, rows, arrays):
    """原始数据表（含派生列）block 列表。"""
    rows = rows or {}
    if mid == "air_resonance":
        l = rows.get("l", [])
        tbl = [[{"text": "序号"}, {"text": "共振位置 l (mm)"}]] + \
              [[{"text": str(i + 1)}, {"text": _fx(l[i], 2)}] for i in range(len(l))]
        blocks = [{"kind": "table", "widths": [4.4, 12.4], "font": 8, "row_h": 0.5, "rows": tbl}]
        dl = arrays.get("delta_l", [])
        tbl2 = [[{"text": "序号"}, {"text": "逐差 Δl_i (mm)"}]] + \
               [[{"text": str(i + 1)}, {"text": _fx(dl[i], 4)}] for i in range(len(dl))]
        blocks.append({"kind": "spacer", "cm": 0.12})
        blocks.append({"kind": "table", "widths": [4.4, 12.4], "font": 8, "row_h": 0.5, "rows": tbl2})
        return blocks
    if mid == "water_phase":
        l = rows.get("l", [])
        tbl = [[{"text": "序号"}, {"text": "匹配位置 l (mm)"}]] + \
              [[{"text": str(i + 1)}, {"text": _fx(l[i], 2)}] for i in range(len(l))]
        blocks = [{"kind": "table", "widths": [4.4, 12.4], "font": 8, "row_h": 0.5, "rows": tbl}]
        dl = arrays.get("delta_l", [])
        tbl2 = [[{"text": "序号"}, {"text": "逐差 Δl_i (mm)"}]] + \
               [[{"text": str(i + 1)}, {"text": _fx(dl[i], 4)}] for i in range(len(dl))]
        blocks.append({"kind": "spacer", "cm": 0.12})
        blocks.append({"kind": "table", "widths": [4.4, 12.4], "font": 8, "row_h": 0.5, "rows": tbl2})
        return blocks
    if mid == "tof":
        L = rows.get("L", [])
        T = rows.get("T", [])
        v = arrays.get("v", [])
        hdr = [{"text": "序号"}, {"text": "L (mm)"}, {"text": "T (μs)"}, {"text": "v_i (m/s)"}]
        body = [[{"text": str(i + 1)}, {"text": _fx(L[i], 1)}, {"text": _fx(T[i], 2)}, {"text": _fx(v[i], 1)}]
                for i in range(len(L))]
        return [{"kind": "table", "widths": [2.0, 4.6, 5.0, 5.2], "font": 8, "row_h": 0.5,
                 "rows": [hdr] + body}]
    if mid == "light_sine":
        T = rows.get("T", [])
        dt = rows.get("dt", [])
        x1 = rows.get("x1", [])
        x2 = rows.get("x2", [])
        dx = arrays.get("dx", [])          # Δx_i = |x2_i - x1_i|（派生）
        ratio = [(_fx(dx[i] / dt[i], 3) if dt[i] else "")
                 for i in range(len(dt))]  # Δx/Δt (mm/μs)（派生）
        # 表 2-1：差频周期（每参考点测一次 T）
        tbl_t = [[{"text": "序号"}, {"text": "差频周期 T (μs)"}]] + \
                [[{"text": str(i + 1)}, {"text": _fx(T[i], 3)}] for i in range(len(T))]
        # 表 2-2：相移 Δt 与滑块位移（补计算列 Δx、Δx/Δt）
        tbl_p = [[{"text": "序号"}, {"text": "Δt (μs)"}, {"text": "x1 (mm)"},
                  {"text": "x2 (mm)"}, {"text": "Δx (mm)"},
                  {"text": "Δx/Δt (mm/μs)"}]] + \
                [[{"text": str(i + 1)}, {"text": _fx(dt[i], 3)},
                  {"text": _fx(x1[i], 2)}, {"text": _fx(x2[i], 2)},
                  {"text": _fx(dx[i], 2)}, {"text": ratio[i]}]
                 for i in range(len(dt))]
        return [
            {"kind": "table", "widths": [3.0, 15.0], "font": 8, "row_h": 0.5,
             "rows": tbl_t},
            {"kind": "spacer", "cm": 0.12},
            {"kind": "table", "widths": [1.8, 3.0, 3.0, 3.0, 3.2, 3.6],
             "font": 8, "row_h": 0.5, "rows": tbl_p},
        ]
    if mid == "light_lissajous":
        x1 = rows.get("x1", [])
        x2 = rows.get("x2", [])
        dx = arrays.get("dx", [])
        hdr = [{"text": "序号"}, {"text": "x1 (mm)"}, {"text": "x2 (mm)"}, {"text": "Δx (mm)"}]
        body = [[{"text": str(i + 1)}, {"text": _fx(x1[i], 2)}, {"text": _fx(x2[i], 2)},
                 {"text": _fx(dx[i], 2)}] for i in range(len(x1))]
        return [{"kind": "table", "widths": [2.4, 4.8, 4.8, 4.8], "font": 8, "row_h": 0.5,
                 "rows": [hdr] + body}]
    return []


def _results_block(results):
    rows = [[{"text": r["label"]}, {"text": f"{_fmt(r['value'])} {r['unit']}".strip()}]
            for r in results]
    return {"kind": "table", "widths": [8.6, 8.8], "font": 9, "row_h": 0.55,
            "rows": [[{"text": "结果项"}, {"text": "数值"}]] + rows}


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
        "包含五个方法（四项必做、一项选做）的原始数据表、逐差/派生列、计算结果与主图；"
        "仅包含已提交数据的方法。Word 可编辑，PDF 紧凑排版用于打印。")
    n = 0
    for mid in ORDER:
        run = _run(mid, methods_data)
        if run is None:
            continue
        n += 1
        tag = "必做" if METHOD_REQUIRED[mid] else "选做"
        b.append({"kind": "h2", "text": f"{n}. {METHOD_NAME[mid]}（{tag}）"})
        if run["status"] != "success":
            b.append({"kind": "note",
                      "text": "数据校验未通过，本节已跳过：" + "；".join(run["errors"])})
            continue
        b.append({"kind": "note", "text": "目的：" + METHOD_PURPOSE[mid]})
        b += _raw_blocks(mid, methods_data[mid].get("rows", {}), run.get("arrays", {}))
        b.append({"kind": "spacer", "cm": 0.12})
        b.append({"kind": "note", "text": "计算结果："})
        b.append(_results_block(run["results"]))
        main_fig = run.get("plots", {}).get("main")
        if main_fig:
            b.append({"kind": "image", "b64": main_fig, "width_cm": 15.6,
                      "caption": f"图 {n} · {METHOD_NAME[mid]}（主图）"})
        b.append({"kind": "spacer", "cm": 0.15})
    b.append({"kind": "note",
              "text": "说明：数据处理由 PhysicsLab 本地服务完成；声速/光速取 4 位有效数字，"
                      "相对误差保留两位小数，逐差间距保留毫米级 4-5 位小数。"})
    return b


def _advanced_blocks(methods_data) -> list[dict]:
    b = _head_blocks(
        "拓展部分",
        "误差分析与多方法对比：逐差分布（含 ±1σ 带）、逐点速度一致性、光速两法对比，"
        "以及结论与误差讨论留白（仅包含已提交数据的方法）。")
    present = []
    for mid in ORDER:
        run = _run(mid, methods_data)
        if run is not None and run["status"] == "success":
            present.append((mid, run))
    n = 0
    for mid, run in present:
        arrays = run.get("arrays", {})
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
