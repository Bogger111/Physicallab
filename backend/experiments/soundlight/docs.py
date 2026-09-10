#!/usr/bin/env python3
"""声速光速的测量（exp02）— 数据记录表与处理报告的 docbuild blocks。

record_blocks()                      空白数据记录表（遗留实现，供 docs.record_bytes；主接口 /api/record-sheets/sound-light.* 现由 record_clean.record_bytes 提供）
report_blocks(part, methods_data)    基准 / 拓展部分报告（供 /api/experiments/sound-light/report）
report_bytes(methods_data, fmt) 渲染统一四部分报告的 docx/pdf 字节
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
    "font.sans-serif": ["Noto Sans CJK SC", "WenQuanYi Micro Hei", "Microsoft YaHei", "SimHei", "DejaVu Sans"],
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

ORDER = [item["id"] for item in sl._CONFIG]
METHOD_NAME = sl._METHOD_NAMES
METHOD_REQUIRED = {
    item["id"]: item["type"] == "required" for item in sl._CONFIG
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
    palette = [BLUE, GREEN, ORANGE]
    ax.bar(x, vals, width=0.45, color=palette[:len(entries)], alpha=0.85)
    ax.axhline(c_ref / 1e8, color=RED, ls="--", lw=1.6, label=f"c_ref = {c_ref/1e8:.3f}×10^8 m/s")
    for xi, (nm, c, err) in zip(x, entries):
        ax.text(xi, vals[xi] + 0.003, f"{vals[xi]:.3f}\n({err:.2f}%)",
                ha="center", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9.5)
    ax.set_ylabel("c_exp (10^8 m/s)")
    ax.set_title("光速测量：已提交方法结果对比")
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


import math

from experiments.record_clean import sl_table_spec as rc_spec
from experiments.report_layout import four_section_report, latex

# ================================================================
# 基准报告：① 原始数据表（与空白记录表逐列同构）② 数据处理
# （公式 + 逐值代入 + 结果，全篇无 LaTeX 痕迹：不用 _ { } ^ \frac，
#  不用 Unicode 下标/组合上划线字形；数学字符集限 msyh 实际含字形者）
# ================================================================

_METHOD_DISP = {
    "air_resonance": "共振干涉法测空气中声速（必做）",
    "water_phase": "相位比较法测水中声速（必做）",
    "tof": "时差法测水中声速（选做）",
    "light_sine": "相位法（正弦波）测光速（必做）",
    "light_square": "相位法（方波）测光速（选做）",
    "light_lissajous": "李萨如图形法测光速（必做）",
}
_WAVE_CN = {"light_sine": "正弦波", "light_square": "方波"}

# 所有“已提交并校验通过”的方法，含 light_square（engine 内部并入正弦法计算）
_PRESENT_ORDER = [(method, METHOD_REQUIRED[method]) for method in ORDER]

C0_MS = 2.998e8            # 真空/空气光速参考值 (m/s)，讲义口径


def _f(v, nd=2):
    """format float；None/nan -> ''。"""
    if v is None:
        return ""
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return str(v)
    if fv != fv:            # nan
        return ""
    return f"{fv:.{nd}f}"


def _h3(text: str) -> dict:
    return {"kind": "h3", "text": text}


# ------------------------------------------------------------
# ① 原始数据表：行结构与空白记录表同一 spec（record_clean.SL_TABLE_SPECS）

def _seq_filled(key: str, fillers: list):
    """按 record_clean 共享 spec 建表；fillers 与数据列（去掉次数列后）平行，
    每项为 None（该列整列留空）或与行数等长的 str 列表。"""
    headers, widths, n = rc_spec(key)
    rows = [[{"text": h} for h in headers]]
    ndata = len(headers) - 1
    for i in range(n):
        line = [{"text": str(i + 1)}]
        for c in range(ndata):
            col = fillers[c] if c < len(fillers) else None
            v = col[i] if col else None
            line.append({"text": "" if v is None else str(v)})
        rows.append(line)
    return _tab(rows, widths, font=8, row_h=0.45)


def _raw_blocks(pres) -> list[dict]:
    """pres: [(method_id, run), ...]（按讲义出现顺序）。"""
    by = dict(pres)
    b: list[dict] = []

    b.append({"kind": "h2", "text": "一、原始数据表"})
    b.append(_cap("下表与空白记录表逐列同构（表头、列数、列序一致，白底黑框）："
                  "表1-1 为空气共振法与水中相位法共用（空气值填空气列、水值填水列，"
                  "未提交方法的列留空），表2-1、表2-2、表2-3 对应讲义表号；"
                  "Δx = |x2 − x1|、Δx/Δt 为程序按行算好的派生列；"
                  "录入界面没有的读数（表2-1 的相邻参考点间距、表2-2 的参考点移动方格数）留空。"))

    # ── 表1-1 空气 + 水（共用一张表）──
    air = by.get("air_resonance")
    wat = by.get("water_phase")
    if air or wat:
        b.append(_cap("表1-1  空气中共振法与水中相位法数据记录（同一张表）"))
        air_l = air["arrays"]["l"] if air else None
        wat_l = wat["arrays"]["l"] if wat else None
        fill = [
            [rc_f2(v) for v in air_l] if air_l else None,
            [rc_f2(v) for v in wat_l] if wat_l else None,
        ]
        b.append(_seq_filled("sl_1_air_water", fill))
        toks = []
        if air:
            p = air["params_used"]
            toks.append(f"f 空气 = {int(round(p['f_khz'] * 1000))} Hz")
        if wat:
            toks.append(f"f 水 = {wat['params_used']['f_mhz']:g} MHz")
        if air:
            toks.append(f"环境室温 t = {air['params_used']['temperature_degC']:g} °C")
        if toks:
            b.append(_cap("；".join(toks) + "。"))
        b.append({"kind": "spacer", "cm": 0.05})

    # ── 实验二（选做）时差法 ──
    tof = by.get("tof")
    if tof:
        a = tof["arrays"]
        b.append(_cap("时差法数据记录（实验二，选做）：传播距离 L 与飞行时间 T"))
        b.append(_seq_filled("sl_2_tof", [
            [rc_f2(v, 1) for v in a["L"]],
            [rc_f2(v, 2) for v in a["T"]],
        ]))
        b.append({"kind": "spacer", "cm": 0.05})

    # ── 光速：表2-1 周期 + 表2-2 相位移动（正弦波/方波各自成组）──
    for mid in ("light_sine", "light_square"):
        run = by.get(mid)
        if not run:
            continue
        a = run["arrays"]
        wv = _WAVE_CN[mid]
        b.append(_cap(f"表2-1  差频后波形的周期测量（{wv}，水平偏转因子 0.5 μs/DIV）"))
        b.append(_seq_filled("sl_3_period", [
            None,
            [rc_f2(v, 3) for v in a["T"]],
        ]))
        b.append({"kind": "spacer", "cm": 0.02})
        b.append(_cap(f"表2-2  参考点水平移动时间 Δt 与滑块（反射镜）移动距离 Δx"
                      f"（{wv}，水平偏转因子 0.2 μs/DIV）"))
        b.append(_seq_filled("sl_4_phase", [
            None,
            [rc_f2(v, 2) for v in a["dt"]],
            [rc_f2(v, 2) for v in a["x1"]],
            [rc_f2(v, 2) for v in a["x2"]],
            [rc_f2(v, 2) for v in a["dx"]],
            [rc_f2(v, 3) for v in a["r"]],
        ]))
        b.append({"kind": "spacer", "cm": 0.05})

    # ── 表2-3 李萨如 ──
    lis = by.get("light_lissajous")
    if lis:
        a = lis["arrays"]
        b.append(_cap("表2-3  李萨如图形法：反射镜滑块移动的距离 Δx"))
        b.append(_seq_filled("sl_5_lissajous", [
            [rc_f2(v, 2) for v in a["x1"]],
            [rc_f2(v, 2) for v in a["x2"]],
            [rc_f2(v, 2) for v in a["dx"]],
        ]))
        b.append({"kind": "spacer", "cm": 0.05})
    return b


# 与空白记录表同构所需的取值格式化（mm 2 位小数、tof L 1 位等）
def rc_f2(v, nd=2):
    return _f(v, nd)


# ------------------------------------------------------------
# ② 数据处理区

def _diff_table(l, dl):
    """六组逐差逐行：ΔlN = (l(N+6) − lN)/6 = (数值 − 数值)/6 = 数值 mm。"""
    rows = [[{"text": "Δl 组号"},
             {"text": "逐差公式与代入（l、Δl 单位 mm）"},
             {"text": "结果（mm）"}]]
    for i in range(6):
        j = i + 6
        rows.append([
            {"text": str(i + 1)},
            {"text": f"Δl{i + 1} = |l{i + 7} − l{i + 1}|/6"
                     f" = |{_f(l[j], 2)} − {_f(l[i], 2)}|/6"
                     f" = {_f(abs(l[j] - l[i]), 2)}/6"},
            {"text": _f(dl[i], 4)},
        ])
    return _tab(rows, [1.8, 12.6, 3.4], font=8, row_h=0.42)


def _mean_line(tag, dl, mean, unit="mm"):
    """Δl 平均 = (Δl1 + … + Δl6)/6 = (六个数值之和)/6 = 结果。"""
    s6 = [_f(v, 4) for v in dl]
    return (f"{tag} = (Δl1 + Δl2 + Δl3 + Δl4 + Δl5 + Δl6)/6"
            f" = ({' + '.join(s6)})/6 ≈ {_f(mean, 4)} {unit}")


def _proc_1a(air) -> list[dict]:
    a, p = air["arrays"], air["params_used"]
    l, dl = a["l"], a["delta_l"]
    f_khz, t_c = p["f_khz"], p["temperature_degC"]
    f_hz = f_khz * 1000.0
    out = [
        _h3("处理 1a：共振干涉法测空气中声速（必做）"),
        _cap("原始数据为 表1-1 第 2 列 l1 至 l12（单位 mm）。相邻共振位置相差半个波长，"
             "用隔 6 次相减的逐差法求平均半波长：Δl1 = (l7 − l1)/6，Δl2 = (l8 − l2)/6，"
             "…，Δl6 = (l12 − l6)/6。六组逐差明细见第一部分对应表格。"),
    ]
    out.append(_diff_table(l, dl))
    mean_s = _mean_line("Δl 平均（半波长）", dl, a["dlm"])
    out.append(_cap(mean_s + "。"))
    # 展示值可以修约；最终结果直接使用 engine 保存的完整精度结果。
    mean4 = a["dlm"]
    lam_mm = a["lam_mm"]
    lam_mm_s = _f(lam_mm, 4)                      # 9.1144
    lam_m_s = _f(lam_mm / 1000.0, 7)              # 0.0091144
    v_s = _f(a["v_exp"], 2)
    out.append(_cap(f"波长与实验声速：λ = 2×Δl 平均 = 2×{_f(round(mean4, 4), 4)}"
                    f" = {lam_mm_s} mm = {lam_m_s} m；"
                    f"实验声速 v = f×λ = {_f(f_hz, 0)}×{lam_m_s} = {v_s} m/s"
                    f"（f = {f_khz:g} kHz = {_f(f_hz, 0)} Hz；"
                    f"v = 2×f×Δl 平均 代入同值）。"))
    sq = math.sqrt(1.0 + t_c / 273.15)
    v_th = a["v_theory"]
    out.append(_cap(f"理论声速（温度修正，讲义理想气体公式）："
                    f"v = 331.45×√(1 + t/273.15) = 331.45×√(1 + {t_c:g}/273.15)"
                    f" = 331.45×{_f(sq, 5)} = {_f(v_th, 2)} m/s（室温 t = {t_c:g} °C）。"))
    e_abs = a["err_abs"]
    e_rel = a["err_rel"]
    out.append(_cap(f"误差比较：绝对误差 = |实验值 − 理论值| = |{v_s} − {_f(v_th, 2)}|"
                    f" = {_f(e_abs, 2)} m/s；相对误差 = ({_f(e_abs, 2)}/{_f(v_th, 2)})×100%"
                    f" = {_f(e_rel, 2)}%。"))
    out.append({"kind": "spacer", "cm": 0.03})
    return out


def _proc_1b(wat) -> list[dict]:
    a, p = wat["arrays"], wat["params_used"]
    l, dl = a["l"], a["delta_l"]
    f_mhz = p["f_mhz"]
    f_hz = f_mhz * 1e6
    out = [
        _h3("处理 1b：相位比较法测水中声速（必做）"),
        _cap("原始数据为 表1-1 第 3 列（单位 mm）。逐差法与处理 1a 相同："
             "Δl1 = (l7 − l1)/6，…，Δl6 = (l12 − l6)/6。六组逐差明细见第一部分对应表格。"),
    ]
    out.append(_diff_table(l, dl))
    mean_s = _mean_line("Δl 平均（半波长）", dl, a["dlm"])
    out.append(_cap(mean_s + "。"))
    mean4 = a["dlm"]
    lam_mm = a["lam_mm"]
    lam_mm_s = _f(lam_mm, 4)
    lam_m_s = _f(lam_mm / 1000.0, 7)
    v_s = _f(a["v"], 1)
    out.append(_cap(f"水中声速：λ = 2×Δl 平均 = 2×{_f(mean4, 4)} = {lam_mm_s} mm"
                    f" = {lam_m_s} m；v = f×λ = {_f(f_hz, 0)}×{lam_m_s} = {v_s} m/s"
                    f"（或 v = 2×f×Δl 平均 = 2×{_f(f_hz, 0)}×{_f(mean4 / 1000.0, 7)}"
                    f" = {v_s} m/s，f = {f_mhz:g} MHz = {_f(f_hz, 0)} Hz）。"))
    # A 类不确定度（Δl 的 6 组逐差，自由度 5，t0.95(5) = 2.571）
    out.append(_cap("A 类不确定度评估（Δl 共 6 组逐差，自由度 n − 1 = 5，"
                    "置信概率 95%，t 分布临界值 t0.95(5) = 2.571）："))
    dev_rows = [[{"text": "组号"}, {"text": "偏差（mm）"}, {"text": "偏差平方（mm²）"}]]
    sq_total = 0.0
    for i, d in enumerate(dl):
        dev = d - mean4
        sq = dev * dev
        sq_total += sq
        dev_rows.append([{"text": str(i + 1)},
                         {"text": _f(dev, 5)},
                         {"text": _f(sq, 8)}])
    out.append(_tab(dev_rows, [1.8, 7.6, 8.4], font=8, row_h=0.42))
    sq_s = _f(sq_total, 8)
    s_dl = a["s"]
    out.append(_cap(f"贝塞尔公式：s(Δl) = √(偏差平方和/(n − 1))"
                    f" = √({sq_s}/5) = {_f(s_dl, 5)} mm"
                    f"（偏差平方和取自第一部分的偏差明细表）。"))
    ua_dl = a["ua_dl_mm"]
    ua_dl_mm_s = _f(ua_dl, 5)
    ua_dl_m_s = _f(a["ua_dl_m"], 8)
    ua_v_s = _f(a["u_a_v"], 1)
    out.append(_cap(f"Δl 的 A 类不确定度（记为 UA(Δl)）："
                    f"UA(Δl) = 2.571×s(Δl)/√6 = 2.571×{_f(s_dl, 5)}/2.44949"
                    f" = {ua_dl_mm_s} mm = {ua_dl_m_s} m；"
                    f"由 v = 2×f×Δl 误差传递：UA(v) = 2×f×UA(Δl)"
                    f" = 2×{_f(f_hz, 0)}×{ua_dl_m_s} = {ua_v_s} m/s。"))
    out.append(_cap(f"结果：v ± UA(v) = {v_s} ± {ua_v_s} m/s"
                    f"（与水中声速常用参考值 1480 m/s 相差"
                    f" {_f(abs(a['v'] - 1480.0) / 1480.0 * 100.0, 1)}%）。"))
    out.append({"kind": "spacer", "cm": 0.03})
    return out


def _proc_1c(tof) -> list[dict]:
    a = tof["arrays"]
    L, T, v = a["L"], a["T"], a["v"]
    out = [
        _h3("处理 1c：时差法测水中声速（选做）"),
        _cap("逐点速度：每个传播距离 L(mm) 换算为 m、对应飞行时间 T(μs) 换算为 s 后相除，"
             "即每点 v = L(mm)/T(μs)×1000（m/s）。逐点结果见第一部分对应表格。"),
    ]
    rows = [[{"text": "测量次数"}, {"text": "L (mm)"}, {"text": "T (μs)"},
             {"text": "v (m/s)"}]]
    for i in range(len(L)):
        rows.append([{"text": str(i + 1)},
                     {"text": _f(L[i], 1)},
                     {"text": _f(T[i], 2)},
                     {"text": _f(v[i], 1)}])
    out.append(_tab(rows, [2.4, 4.6, 5.0, 5.2], font=8, row_h=0.42))
    out.append(_cap(f"平均声速 v = {_f(a['v_mean'], 1)} m/s"
                    f"（12 个逐点速度的算术平均）；样本标准差 = {_f(a['v_std'], 1)} m/s。"
                    f"与水中声速常用参考值 1480 m/s 相差"
                    f" {_f(abs(a['v_mean'] - 1480.0) / 1480.0 * 100.0, 1)}%。"))
    out.append({"kind": "spacer", "cm": 0.03})
    return out


def _proc_2a(mid, run) -> list[dict]:
    a, p = run["arrays"], run["params_used"]
    wv = _WAVE_CN[mid]
    tag = "必做" if mid == "light_sine" else "选做"
    f_mhz = p["f_mhz"]
    f_hz = f_mhz * 1e6
    out = [_h3(f"处理 2a：相位差法（{wv}）测空气中光速（{tag}）")]
    # ① T 平均
    ts = [_f(v, 3) for v in a["T"]]
    t_sum = sum(a["T"])
    t_mean = a["t_mean"]
    out.append(_cap(f"差频周期平均值（表2-1 数据，单位 μs；T1、T2、T3 为三次读数）："
                    f"T = (T1 + T2 + T3)/3 = ({' + '.join(ts)})/3"
                    f" = {_f(t_sum, 3)}/3 = {_f(t_mean, 3)} μs。"))
    # ② r 平均
    rs = [_f(v, 3) for v in a["r"]]
    r_sum = sum(a["r"])
    r_mean = a["r_mean"]
    out.append(_cap(f"表2-2 的 Δx/Δt 派生列即各行读数之比（单位 mm/μs），记为 r1、r2、r3；"
                    f"其平均（讲义：计算 Δx/Δt 的平均值）：r 平均 = (r1 + r2 + r3)/3"
                    f" = ({' + '.join(rs)})/3 = {_f(r_sum, 3)}/3"
                    f" = {_f(r_mean, 3)} mm/μs。"))
    # ③ λ ④ c
    lam_mm = a["lam_mm"]
    lam_mm_s = _f(lam_mm, 2)
    lam_m_s = _f(lam_mm / 1000.0, 5)
    c_s = _f(a["c_exp"], 0)
    out.append(_cap(f"调制波长（差频法公式 λ = 2×T×r，T、r 用上面的平均值）：λ(mm) = 2×{_f(t_mean, 3)}"
                    f"×{_f(r_mean, 3)} = {lam_mm_s} mm = {lam_m_s} m。"))
    out.append(_cap(f"实验光速：c = f×λ = {_f(f_hz, 0)}×{lam_m_s}"
                    f" = {c_s} m/s ≈ {_f(a['c_exp'] / 1e8, 3)}×10⁸ m/s"
                    f"（调制频率 f = {f_mhz:g} MHz = {_f(f_hz, 0)} Hz）。"))
    # ⑤ 误差
    c0 = float(p.get("c_ref", C0_MS))
    e_abs = a["err_abs"]
    e_rel = a["err_rel"]
    out.append(_cap(f"与本次光速参考值 c0 = {_f(c0, 0)} m/s 比较："
                    f"绝对误差 = |c − c0| = |{c_s} − {_f(c0, 0)}|"
                    f" = {_f(e_abs, 0)} m/s ≈ {_f(e_abs / 1e4, 1)}×10⁴ m/s；"
                    f"相对误差 = ({_f(e_abs / 1e4, 1)}×10⁴/{_f(c0, 0)})×100%"
                    f" = {_f(e_rel, 2)}%。"))
    out.append({"kind": "spacer", "cm": 0.03})
    return out


def _proc_2b(lis) -> list[dict]:
    a, p = lis["arrays"], lis["params_used"]
    f_mhz = p["f_mhz"]
    f_hz = f_mhz * 1e6
    out = [_h3("处理 2b：李萨如图形法测空气中光速（必做）")]
    # ① Δx 平均
    dxs = [_f(v, 2) for v in a["dx"]]
    dx_sum = sum(a["dx"])
    dx_mean = a["dxm"]
    out.append(_cap(f"Δx = |x2 − x1|（表2-3 数据，单位 mm）："
                    f"Δx 平均 = (Δx1 + Δx2 + Δx3)/3 = ({' + '.join(dxs)})/3"
                    f" = {_f(dx_sum, 2)}/3 = {_f(dx_mean, 2)} mm。"))
    # ② λ ③ c
    lam_mm = a["lam_mm"]
    lam_mm_s = _f(lam_mm, 2)
    lam_m_s = _f(lam_mm / 1000.0, 5)
    c_s = _f(a["c_exp"], 0)
    out.append(_cap("李萨如图由直线变为反斜率直线时相位差改变 π，对应光程差 λ/2、"
                    "反射镜移动 Δx = λ/4："))
    out.append(_cap(f"λ = 4×Δx 平均 = 4×{_f(dx_mean, 2)} = {lam_mm_s} mm"
                    f" = {lam_m_s} m。"))
    out.append(_cap(f"实验光速 c = f×λ = {_f(f_hz, 0)}×{lam_m_s}"
                    f" = {c_s} m/s ≈ {_f(a['c_exp'] / 1e8, 3)}×10⁸ m/s"
                    f"（调制频率 f = {f_mhz:g} MHz）。"))
    c0 = float(p.get("c_ref", C0_MS))
    e_abs = a["err_abs"]
    e_rel = a["err_rel"]
    out.append(_cap(f"与本次光速参考值 c0 = {_f(c0, 0)} m/s 比较："
                    f"绝对误差 = |{c_s} − {_f(c0, 0)}|"
                    f" = {_f(e_abs, 0)} m/s ≈ {_f(e_abs / 1e4, 2)}×10⁴ m/s；"
                    f"相对误差 = ({_f(e_abs / 1e4, 2)}×10⁴/{_f(c0, 0)})×100%"
                    f" = {_f(e_rel, 2)}%。"))
    out.append({"kind": "spacer", "cm": 0.03})
    return out


def _err_sources_blocks(pres) -> list[dict]:
    by = dict(pres)
    b: list[dict] = [_h3("处理 3：误差来源分析")]
    b.append(_cap("（1）仪器类误差：示波器水平时基（0.5 μs/DIV 与 0.2 μs/DIV）的"
                  "分度、扫描与水平微调校准误差，直接影响周期 T、相位时间 Δt 的读数；"
                  "信号发生器频率显示偏差影响共振频率 f、水中频率 f 与调制频率 f；"
                  "导轨标尺与读数装置的分度、零位误差影响 l、x1、x2 读数。"
                  "减小措施：使用前校零并锁定时基微调，读数取多次平均。"))
    b.append(_cap("（2）读数与操作误差：驻波共振幅值极大点平台较宽，极大位置判定不灵敏"
                  "带来随机误差；李萨如图形直线（同斜率/反斜率）判据与同相位点对准存在"
                  "主观读数误差；示波器上参考点移动格数按 0.2 μs/DIV 判读存在量化误差。"
                  "减小措施：沿同一方向缓慢移动换能器或反射镜，极大位置往返微调取中点，"
                  "每组重复 3 次取平均。"))
    b.append(_cap("（3）方法与理论近似误差：理论声速按干燥理想气体公式"
                  " v = 331.45×√(1 + t/273.15) 计算，未计湿度、气压与 CO2 含量影响；"
                  "水中声速以 1480 m/s 常用值作参考；光速比较以真空值 c0 = 2.998×10⁸ m/s"
                  "代替空气中光速（空气折射率 n ≈ 1.0003，差异约 0.03%）；差频相位-位移"
                  "关系假定波形严格且线性良好。减小措施：注明近似前提，需要时对声速作"
                  "湿度/气压修正，光速比较口径统一用 c0。"))
    b.append(_cap("（4）环境类误差：室温波动改变空气中声速；水中温度分布不均、气泡与"
                  "液面晃动改变水中声速；换能器端面与反射镜移动方向不严格平行、导轨回程"
                  "间隙引入系统误差。减小措施：测量期间保持环境稳定、不触碰水槽，"
                  "移动一律单向进行。"))
    concl = []
    if "air_resonance" in by:
        a, p = by["air_resonance"]["arrays"], by["air_resonance"]["params_used"]
        concl.append(f"空气中声速（共振干涉法）v = {_f(a['v_exp'], 1)} m/s，与室温"
                     f" {p['temperature_degC']:g} °C 理论值 {_f(a['v_theory'], 1)} m/s"
                     f" 的相对误差 {_f(a['err_rel'], 2)}%")
    if "water_phase" in by:
        a = by["water_phase"]["arrays"]
        concl.append(f"水中声速（相位比较法）v = {_f(a['v'], 1)} ± {_f(a['u_a_v'], 1)} m/s"
                     f"（UA(v)），与常用参考值 1480 m/s 相差"
                     f" {_f(abs(a['v'] - 1480.0) / 1480.0 * 100.0, 1)}%")
    if "tof" in by:
        a = by["tof"]["arrays"]
        concl.append(f"时差法 v = {_f(a['v_mean'], 1)} m/s，与 1480 m/s 参考值相差"
                     f" {_f(abs(a['v_mean'] - 1480.0) / 1480.0 * 100.0, 1)}%")
    for mid in ("light_sine", "light_square", "light_lissajous"):
        if mid in by:
            a = by[mid]["arrays"]
            nm = {"light_sine": "光速（正弦波相位差法）",
                  "light_square": "光速（方波相位差法）",
                  "light_lissajous": "光速（李萨如法）"}[mid]
            concl.append(f"{nm} c = {_f(a['c_exp'] / 1e8, 3)}×10⁸ m/s，"
                         f"相对误差 {_f(a['err_rel'], 2)}%")
    tail = ("。以上仅为提交数据的计算结果；是否符合实验要求需结合原始记录、"
            "仪器条件与误差分析判断。")
    b.append(_cap("总体结论：" + "；".join(concl) + tail))
    b.append({"kind": "spacer", "cm": 0.03})
    return b


def _head_blocks(part_title, note):
    return [
        {"kind": "spacer", "cm": 0.2},
        {"kind": "h1", "text": f"声速光速的测量 · 数据处理报告（{part_title}）"},
        {"kind": "sub", "text": note},
        {"kind": "spacer", "cm": 0.1},
    ]


# ------------------------------------------------------------
# 基准报告主装配

def _basic_blocks(methods_data) -> list[dict]:
    b = _head_blocks(
        "基准部分",
        "依据讲义【数据处理】生成：原始数据规范作表，逐差与平均值计算、A 类不确定度评估"
        "（置信概率 95%）及误差比较；本实验讲义未要求作图（图见拓展部分）。"
        "仅包含已提交且通过校验的方法，每步给出公式、数值代入与结果。")
    pres, failed = [], []
    for mid, _need in _PRESENT_ORDER:
        item = (methods_data or {}).get(mid)
        if not item or not item.get("rows"):
            continue
        run = _run(mid, methods_data)
        if run is None:
            continue
        if run["status"] == "success":
            pres.append((mid, run))
        else:
            failed.append((mid, run))
    if not pres:
        b.append({"kind": "note", "text": "没有可处理的已提交方法数据，本报告暂无可计算内容。"})
        return b
    names = "；".join(f"{i + 1}. {_METHOD_DISP[mid]}" for i, (mid, _r) in enumerate(pres))
    intro = f"已提交方法（共 {len(pres)} 项）：{names}。"
    if failed:
        intro += (" 以下方法数据未通过校验，未参与计算："
                  + "、".join(_METHOD_DISP[m] for m, _ in failed) + "。")
    b.append({"kind": "note", "text": intro})
    for m, run in failed:
        b.append({"kind": "note",
                  "text": f"{_METHOD_DISP[m]} 校验未通过：" + "；".join(run["errors"])})
    b.append({"kind": "spacer", "cm": 0.05})

    # ① 原始数据表
    b += _raw_blocks(pres)
    # ② 数据处理
    b.append({"kind": "h2", "text": "二、数据处理"})
    b.append(_cap("以下每一步都给出公式、实测数值代入与结果；数值取自本地数据分析结果"
                  "（与在线处理接口同源同公式）。中间值为显示而修约，等式中的数值代入为"
                  "近似展示；最终结果始终使用完整精度计算。"))
    b.append({"kind": "note",
              "text": "说明：数据处理由 PhysicsLab 本地完成；声速/光速取 4 位有效数字、"
                      "相对误差保留两位小数，逐差间距保留毫米级 4 位小数；本实验讲义"
                      "未要求作图，相关图形见拓展部分。报告各数据表与空白记录表逐列同构，"
                      "留空列（表2-1 相邻参考点间距、表2-2 参考点移动方格数）为录入界面"
                      "没有的读数。"})
    by = dict(pres)
    if "air_resonance" in by:
        b += _proc_1a(by["air_resonance"])
    if "water_phase" in by:
        b += _proc_1b(by["water_phase"])
    if "tof" in by:
        b += _proc_1c(by["tof"])
    for mid in ("light_sine", "light_square"):
        if mid in by:
            b += _proc_2a(mid, by[mid])
    if "light_lissajous" in by:
        b += _proc_2b(by["light_lissajous"])
    # ③ 误差来源分析 + 结论
    b.append({"kind": "pagebreak"})
    b += _err_sources_blocks(pres)
    return b


def _advanced_blocks(methods_data) -> list[dict]:
    b = _head_blocks(
        "拓展部分",
        "各方法原始数据主图（自基准报告移入）与误差分析：逐差分布（含 ±1σ 带）、逐点速度一致性、"
        "光速各方法对比，以及结论与误差讨论留白（仅包含已提交且通过校验的方法）。")
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
            elif mid in ("light_sine", "light_square"):
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
    for mid in ("light_sine", "light_square", "light_lissajous"):
        for m2, run in present:
            if m2 == mid:
                arr = run.get("arrays", {})
                short = {"light_sine": "正弦法", "light_square": "方波法",
                         "light_lissajous": "李萨如法"}[mid]
                light_entries.append((short, arr["c_exp"], arr["err_rel"]))
    if light_entries:
        c_ref = 299800000.0
        for mid in ("light_sine", "light_square", "light_lissajous"):
            for m2, run in present:
                if m2 == mid:
                    c_ref = run.get("params_used", {}).get("c_ref", c_ref)
        n += 1
        b.append({"kind": "h2", "text": f"图 {n} · 光速测量：已提交方法结果对比"})
        b.append({"kind": "image", "b64": _adv_light_compare_fig(light_entries, c_ref),
                  "width_cm": 15.6})
        b.append({"kind": "note",
                  "text": "分析要点：各方法实验光速与 c_ref 的相对误差、方法之间的一致性；"
                          "误差主要来源（Δx 读数、ΔT/Δt 时基判读、频率标称值偏差）讨论。"})
        b.append({"kind": "spacer", "cm": 0.12})
    b.append({"kind": "h2", "text": "结论与误差讨论"})
    b.append({"kind": "note",
              "text": "请结合上述图表撰写结论（Word 中可直接编辑，PDF 留白供手写）：总结各方法测得声速/光速与理论值（c_ref）的偏差、"
                      "不确定度来源与改进建议。"})
    b.append({"kind": "lines", "n": 5})
    return b


def _successful_runs(methods_data: dict) -> tuple[list[tuple[str, dict]], list[tuple[str, dict]]]:
    present, failed = [], []
    for mid, _required in _PRESENT_ORDER:
        run = _run(mid, methods_data)
        if run is None:
            continue
        (present if run["status"] == "success" else failed).append((mid, run))
    return present, failed


def _result_table(run: dict) -> dict:
    rows = [[{"text": "结果量"}, {"text": "数值"}, {"text": "单位"}]]
    for item in run.get("results", []):
        rows.append([
            {"text": item["label"]},
            {"text": str(item["value"])},
            {"text": item.get("unit", "")},
        ])
    return _tab(rows, [8.4, 5.2, 4.2], font=8, row_h=0.44)


def _process_blocks(mid: str, run: dict) -> list[dict]:
    if mid == "air_resonance":
        return _proc_1a(run)
    if mid == "water_phase":
        return _proc_1b(run)
    if mid == "tof":
        return _proc_1c(run)
    if mid in ("light_sine", "light_square"):
        return _proc_2a(mid, run)
    return _proc_2b(run)


def _table_entries(present: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    by = dict(present)
    raw_tables = [b for b in _raw_blocks(present) if b["kind"] == "table"]
    raw_names: list[str] = []
    if by.get("air_resonance") or by.get("water_phase"):
        raw_names.append("空气共振法与水中相位法原始数据")
    if by.get("tof"):
        raw_names.append("飞行时间法原始数据")
    for mid in ("light_sine", "light_square"):
        if by.get(mid):
            wave = _WAVE_CN[mid]
            raw_names += [f"{wave}差频周期原始数据", f"{wave}相位移动原始数据"]
    if by.get("light_lissajous"):
        raw_names.append("李萨如图形法原始数据")
    entries = list(zip(raw_names, raw_tables))

    calculation_names = {
        "air_resonance": ["空气共振法逐差计算明细"],
        "water_phase": ["水中相位法逐差计算明细", "水中相位法不确定度偏差明细"],
        "tof": ["飞行时间法逐点声速明细"],
        "light_sine": [],
        "light_square": [],
        "light_lissajous": [],
    }
    for mid, run in present:
        calc_tables = [b for b in _process_blocks(mid, run) if b["kind"] == "table"]
        entries.extend(zip(calculation_names[mid], calc_tables))
        entries.append((f"{_METHOD_DISP[mid]}计算结果汇总", _result_table(run)))
    return entries


def _figure_entries(present: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    entries: list[tuple[str, dict]] = []
    for mid, run in present:
        main = run.get("plots", {}).get("main")
        if main:
            entries.append((f"{METHOD_NAME[mid]}原始数据主图",
                            {"b64": main, "width_cm": 13.0}))
        arrays = run.get("arrays", {})
        if mid in ("air_resonance", "water_phase"):
            entries.append((f"{METHOD_NAME[mid]}逐差分布",
                            {"b64": _adv_delta_l_fig(METHOD_NAME[mid], arrays),
                             "width_cm": 13.0}))
        elif mid == "tof":
            entries.append(("飞行时间法逐点声速一致性",
                            {"b64": _adv_tof_fig(arrays), "width_cm": 13.0}))
    light_entries = []
    c_ref = C0_MS
    for mid, run in present:
        if mid in ("light_sine", "light_square", "light_lissajous"):
            short = {"light_sine": "正弦法", "light_square": "方波法",
                     "light_lissajous": "李萨如法"}[mid]
            arrays = run["arrays"]
            light_entries.append((short, arrays["c_exp"], arrays["err_rel"]))
            c_ref = run.get("params_used", {}).get("c_ref", c_ref)
    if light_entries:
        entries.append(("光速测量各方法结果对比",
                        {"b64": _adv_light_compare_fig(light_entries, c_ref),
                         "width_cm": 13.0}))
    return entries


def _equations(mid: str, run: dict) -> list[dict]:
    a = run["arrays"]
    if mid == "air_resonance":
        return [
            latex(r"\Delta l_i=\frac{|l_{i+6}-l_i|}{6}"),
            latex(fr"\overline{{\Delta l}}={a['dlm']:.4f}\,\mathrm{{mm}},\quad \lambda=2\overline{{\Delta l}}={a['lam_mm']:.4f}\,\mathrm{{mm}}"),
            latex(fr"v_{{\rm exp}}=f\lambda={a['v_exp']:.2f}\,\mathrm{{m\,s^{{-1}}}}"),
            latex(fr"v_{{\rm th}}=331.45\sqrt{{1+t/273.15}}={a['v_theory']:.2f}\,\mathrm{{m\,s^{{-1}}}}"),
            latex(fr"\varepsilon_r=\frac{{|v_{{\rm exp}}-v_{{\rm th}}|}}{{v_{{\rm th}}}}\times100\%={a['err_rel']:.2f}\%"),
        ]
    if mid == "water_phase":
        return [
            latex(r"\Delta l_i=\frac{|l_{i+6}-l_i|}{6},\quad \lambda=2\overline{\Delta l}"),
            latex(fr"v=f\lambda={a['v']:.1f}\,\mathrm{{m\,s^{{-1}}}}"),
            latex(fr"s(\Delta l)=\sqrt{{\frac{{\sum_i(\Delta l_i-\overline{{\Delta l}})^2}}{{n-1}}}}={a['s']:.5f}\,\mathrm{{mm}}"),
            latex(fr"U_A(v)=2f\frac{{2.571s(\Delta l)}}{{\sqrt{{6}}}}={a['u_a_v']:.1f}\,\mathrm{{m\,s^{{-1}}}}"),
        ]
    if mid == "tof":
        return [
            latex(r"v_i=\frac{L_i\times10^{-3}}{T_i\times10^{-6}}=1000\frac{L_i}{T_i}"),
            latex(fr"\overline{{v}}={a['v_mean']:.1f}\,\mathrm{{m\,s^{{-1}}}},\quad s_v={a['v_std']:.2f}\,\mathrm{{m\,s^{{-1}}}}"),
            latex(fr"T=aL+b,\quad a={a['slope']:.6f}\,\mathrm{{\mu s\,mm^{{-1}}}},\quad v_{{\rm fit}}=\frac{{1000}}{{a}}"),
        ]
    if mid in ("light_sine", "light_square"):
        return [
            latex(r"r_i=\frac{|x_{2,i}-x_{1,i}|}{\Delta t_i},\quad \overline{r}=\frac{1}{n}\sum_{i=1}^{n}r_i"),
            latex(fr"\overline{{T}}={a['t_mean']:.5f}\,\mathrm{{\mu s}},\quad \overline{{r}}={a['r_mean']:.4f}\,\mathrm{{mm\,\mu s^{{-1}}}}"),
            latex(fr"\lambda=2\overline{{T}}\,\overline{{r}}={a['lam_mm']:.4f}\,\mathrm{{mm}}"),
            latex(fr"c=f\lambda={a['c_exp']:.0f}\,\mathrm{{m\,s^{{-1}}}},\quad \varepsilon_r={a['err_rel']:.4f}\%"),
        ]
    return [
        latex(r"\Delta x_i=|x_{2,i}-x_{1,i}|,\quad \overline{\Delta x}=\frac{1}{n}\sum_i\Delta x_i"),
        latex(fr"\lambda=4\overline{{\Delta x}}={a['lam_mm']:.2f}\,\mathrm{{mm}}"),
        latex(fr"c=f\lambda={a['c_exp']:.0f}\,\mathrm{{m\,s^{{-1}}}},\quad \varepsilon_r={a['err_rel']:.4f}\%"),
    ]


def _analysis_blocks(present: list[tuple[str, dict]], table_count: int,
                     figure_count: int) -> list[dict]:
    blocks: list[dict] = [
        _cap(f"第一部分共 {table_count} 张表，集中给出原始读数、逐差/逐点明细和结果汇总；"
             f"第二部分共 {figure_count} 张图，集中给出原始趋势、拟合与方法对比。"
             "表图区不放分析正文，便于直接打印、裁切和粘贴。"),
    ]
    for mid, run in present:
        process = [b for b in _process_blocks(mid, run)
                   if b["kind"] not in ("table", "spacer")]
        blocks.extend(process)
        blocks.extend(_equations(mid, run))
    return blocks


def _discussion_blocks(present: list[tuple[str, dict]],
                       failed: list[tuple[str, dict]]) -> list[dict]:
    blocks = [
        _h3("拓展图形解读"),
        _cap("逐差图用于观察各组 Δl 是否围绕均值随机波动；飞行时间图用于检查 T-L 线性与逐点速度一致性；"
             "光速比较图用于比较正弦波、方波和李萨如法与同一参考值的偏差。趋势性漂移通常提示移动方向、"
             "回程间隙或时基判读带来的系统误差。"),
        _h3("改进建议"),
        _cap("测量前校准示波器时基和信号频率；换能器及反射镜沿同一方向移动；共振极值和李萨如直线位置"
             "采用往返微调取中点；记录温度、湿度和水温；对每个判据重复测量并保存原始读数，必要时增加"
             "B 类不确定度并与 A 类不确定度合成。"),
    ]
    blocks.extend(_err_sources_blocks(present))
    if failed:
        blocks.append(_cap("未纳入计算的方法：" + "；".join(
            f"{_METHOD_DISP[mid]}（{'；'.join(run['errors'])}）" for mid, run in failed
        )))
    return blocks


def report_blocks(methods_data: dict, legacy_data: dict | None = None) -> list[dict]:
    """One reusable four-section report; legacy ``part`` calls map here too."""
    if isinstance(methods_data, str):
        methods_data = legacy_data or {}
    present, failed = _successful_runs(methods_data or {})
    if not present:
        return [{"kind": "note", "text": "没有可处理的已提交方法数据。"}]
    tables = _table_entries(present)
    figures = _figure_entries(present)
    return four_section_report(
        tables,
        figures,
        _analysis_blocks(present, len(tables), len(figures)),
        _discussion_blocks(present, failed),
    )


def report_bytes(methods_data, fmt="docx", legacy_fmt=None) -> bytes:
    """Render the unified report; accepts the former three-argument call."""
    if isinstance(methods_data, str):
        methods_data, fmt = fmt, legacy_fmt or "docx"
    blocks = report_blocks(methods_data)
    if fmt == "docx":
        return render_docx(blocks)
    return render_pdf(blocks)


def record_bytes(fmt: str = "docx") -> bytes:
    blocks = record_blocks()
    if fmt == "docx":
        return render_docx(blocks)
    return render_pdf(blocks)
