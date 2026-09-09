#!/usr/bin/env python3
"""mimo-style clean record sheets: exp01 polarization + exp02 sound-light, both portrait A4.

Mirrors C:/Users/Bogger/OneDrive/Desktop/Hermes File/PhysicsLab_Output/01_record_tables/
gen_clean_tables.py: experiment title (h2) is followed directly by its tables,
no page header/footer, no explanatory note paragraphs, no cell fills except
prefilled reference cells (cos²θ, 测量次数/序号 etc.); the rest is blank for
handwriting. Tables flow naturally; the PDF renderer keeps each table intact
on one page (KeepTogether). User requirement: every blank record sheet is
portrait A4 (docx 210×297 宋体 / pdf 595×842 msyh), one row per record.
Per-table total widths below stay <= 18.0 cm so Word tables never overflow the
portrait text column (usable 18.2 cm); the PDF flavour rescales to full width.

Rendering contract:
  record_bytes('polarization'|'sound-light', 'docx'|'pdf')
landscape = False for both experiments
docx -> render_docx(landscape=False, cn='宋体', cn_en='宋体')
pdf  -> render_pdf(landscape=False, cn_pref='msyh')
"""

from __future__ import annotations

import math

from experiments.polarization import docbuild

# glyphs missing from SimSun.ttc (used by the PDF flavour): Word falls back
# automatically in the docx, reportlab would drop the character, so the PDF
# flavour swaps them for printable ASCII equivalents.
_PDF_FIX_TABLE = {
    0x1D62: "i",   # ᵢ latin subscript small i
    0x2081: "1",   # ₁
    0x2082: "2",   # ₂
}


# ---------------------------------------------------------------- helpers

def _h2(text: str) -> dict:
    return {"kind": "h2", "text": text}


def _sp(cm: float) -> dict:
    return {"kind": "spacer", "cm": cm}


def _para(text: str) -> dict:
    return {"kind": "para", "size": 9, "text": text}


def _cell(text: str, prefill: bool = False) -> dict:
    return {"text": text, "prefill": True} if prefill else {"text": text}


def _tbl(widths: list, rows: list, font: float = 9.0, row_h: float = 0.6) -> dict:
    return {"kind": "table", "widths": widths, "font": font,
            "row_h": row_h, "rows": rows}


def _empty_row(n: int) -> list:
    return [{} for _ in range(n)]


# ---------------------------------------------------------------- exp01 polarization

def _polarization_blocks() -> list[dict]:
    b: list[dict] = []

    # ── 实验一：马吕斯定律 ──
    b.append(_h2("实验一：马吕斯定律验证 — I 与 cos²θ 的关系"))
    b.append(_sp(0.1))
    head1 = [_cell(h) for h in
             ("θ (°)", "cos²θ", "P2左旋(度)", "P2左旋(分)",
              "P2右旋(度)", "P2右旋(分)", "I左旋(μW)", "I右旋(μW)")]
    rows1 = [head1]
    for a in (90, 80, 70, 60, 50, 40, 30, 20, 10, 0):
        ca = math.cos(math.radians(a))
        rows1.append([_cell(str(a), True), _cell(f"{ca * ca:.4f}", True)]
                     + _empty_row(6))
    # portrait: 8 列合计 17.8 cm（原横向 26.7 cm × 2/3），列宽比不变
    b.append(_tbl([1.8, 2.0, 2.33, 2.33, 2.33, 2.33, 2.33, 2.33], rows1))

    # ── 实验二：λ/2 波片 ──
    b.append(_h2("实验二：λ/2 波片验证 — 偏振方向旋转 2θ"))
    b.append(_sp(0.1))
    rows2a = [[_cell(h) for h in ("项目", "度", "分")],
              [_cell("C 初始消光位置 φ_C0"), {}, {}],
              [_cell("P2 初始消光位置"), {}, {}]]
    b.append(_tbl([6.0, 3.0, 3.0], rows2a))          # 60/30/30 mm
    b.append(_sp(0.15))
    head2b = [_cell(h) for h in
              ("序号", "C偏移(°)", "C读数(度)", "C读数(分)",
               "P2消光(度)", "P2消光(分)")]
    rows2b = [head2b] + [
        [_cell(str(i), True), _cell(str((i - 1) * 10), True)] + _empty_row(4)
        for i in range(1, 7)]
    b.append(_tbl([2.0, 3.0, 3.2, 3.2, 3.2, 3.2], rows2b))

    # ── 实验三：λ/4 波片 ──
    b.append(_h2("实验三：λ/4 波片椭圆偏振光强分布 I(φ)"))
    b.append(_sp(0.1))
    rows3a = [[_cell(h) for h in ("项目", "值")],
              [_cell("P2 消光位置"), {}],
              [_cell("C′ 消光位置"), {}],
              [_cell("θ_qwp (°)"), _cell("30 或 60", True)],
              [_cell("P2 转动方向"), _cell("CW / CCW", True)],
              [_cell("首次10°后光强变化"), _cell("增大 / 减小", True)]]
    b.append(_tbl([7.0, 5.0], rows3a))               # 70/50 mm
    b.append(_sp(0.15))
    head3b = [_cell(h) for h in ("φ(°)", "I(μW)", "φ(°)", "I(μW)",
                                 "φ(°)", "I(μW)")]
    rows3b = [head3b]
    for i in range(12):
        row = []
        for j in range(3):
            deg = i * 10 + j * 120
            row += [_cell(str(deg), True), {}]
        rows3b.append(row)
    b.append(_tbl([2.97, 2.97, 2.97, 2.97, 2.97, 2.97], rows3b))

    # ── 实验四：双折射（选做）──
    b.append(_h2("实验四（选做）：双折射现象观察"))
    b.append(_sp(0.1))
    rows4a = [[_cell(h) for h in ("观察内容", "记录")],
              [_cell("看到几个像？"), {}],
              [_cell("像的位置关系？"), {}],
              [_cell("移动冰洲石时像如何变化？"), {}],
              [_cell("出射几个光斑？"), {}],
              [_cell("光斑偏振方向关系"), {}]]
    b.append(_tbl([7.2, 10.8], rows4a))               # 80/120 mm → 竖版 72/108 mm
    b.append(_sp(0.15))
    rows4b = [[_cell(h) for h in ("光斑", "P2消光(度)", "P2消光(分)", "备注")],
              [_cell("光斑A（不偏折）"), {}, {}, {}],
              [_cell("光斑B（偏折）"), {}, {}, {}],
              [_cell("角度差"), {}, {}, {}]]
    b.append(_tbl([5.8, 4.0, 4.0, 4.0], rows4b))

    # ── 实验五：波片鉴别（选做）──
    b.append(_h2("实验五（选做）：判别 λ/4 与 λ/2 波片"))
    b.append(_sp(0.1))
    head5 = [_cell(h) for h in
             ("样品", "消光(度)", "消光(分)", "转45°后(度)", "转45°后(分)",
              "光强行为", "有无消光", "判别结果")]
    rows5 = [head5] + [[_cell(f"样品{i}", True)] + _empty_row(7)
                       for i in range(1, 4)]
    b.append(_tbl([2.8, 2.2, 2.2, 2.33, 2.33, 2.4, 1.8, 1.73], rows5))

    # ── 实验六：圆偏振光（选做）──
    b.append(_h2("实验六（选做）：圆偏振光光强分布"))
    b.append(_sp(0.1))
    head6 = [_cell(h) for h in
             ("P2(°)", "I_raw(μW)", "I_corr(μW)",
              "P2(°)", "I_raw(μW)", "I_corr(μW)")]
    rows6 = [head6]
    for i in range(6):
        row = []
        for j in range(2):
            deg = (i + j * 6) * 10
            row += [_cell(str(deg), True), {}, {}]
        rows6.append(row)
    b.append(_tbl([2.97, 2.97, 2.97, 2.97, 2.97, 2.97], rows6))
    return b


# ---------------------------------------------------------------- exp02 sound & light (portrait per lecture)

def _sl_num_rows(n: int, headers: list, widths: list) -> dict:
    """空白记录表：表头 + 测量次数 1..n 预填，其余格留空（白底黑框）。

    与讲义表结构一致（表1-1 / 表2-1 ~ 2-3）：次数列排在最左逐行下行，
    数据列留白手写；仅次数列使用 prefill。
    """
    rows = [[_cell(h) for h in headers]]
    for i in range(1, n + 1):
        rows.append([_cell(str(i), True)] + _empty_row(len(headers) - 1))
    return _tbl(widths, rows)


# 实验四 / 实验六（方波选做）共用表头与列宽（讲义表 2-2 结构）
_PHASE_HEADERS = ["测量次数", "参考点移动（方格数）", "参考点移动距离 Δt (μs)",
                  "x1 (mm)", "x2 (mm)", "Δx (mm)", "Δx/Δt (mm/μs)"]
_PHASE_WIDTHS = [2.2, 2.9, 3.1, 2.3, 2.3, 2.4, 2.6]        # 合计 17.8 cm


def _sound_light_blocks() -> list[dict]:
    b: list[dict] = []

    # ── 实验一：表 1-1 空气共振法 + 水中相位法（同一张表，12 行）──
    b.append(_h2("实验一：超声声速测量 — 共振干涉法与相位比较法"))
    b.append(_sl_num_rows(12, ["测量次数", "空气中共振法 l (mm)", "水中相位法 l (mm)"],
                          [2.6, 7.6, 7.6]))
    b.append(_para("f 空气 = ________ Hz；f 水 = ________ Hz；环境室温 t = ________ °C"))

    # ── 实验二（选做）：时差法测水中声速（讲义：连续 12 组，每次 20 mm）──
    b.append(_h2("实验二（选做）：时差法测水中声速"))
    b.append(_sl_num_rows(12, ["测量次数", "L (mm)", "T (μs)"], [2.6, 7.6, 7.6]))

    # ── 实验三：表 2-1 差频周期测量 ──
    b.append(_h2("实验三：光速测量 — 相位法（正弦波）· 周期"))
    b.append(_sl_num_rows(3, ["测量次数", "相邻参考点间距（格子数）", "周期 T (μs)"],
                          [2.6, 7.6, 7.6]))

    # ── 实验四：表 2-2 相位移动 Δt 与滑块位移 Δx ──
    b.append(_h2("实验四：光速测量 — 相位法（正弦波）· 相位移动 Δt"))
    b.append(_sl_num_rows(3, _PHASE_HEADERS, _PHASE_WIDTHS))

    # ── 实验五：表 2-3 李萨如图形法 ──
    b.append(_h2("实验五：光速测量 — 李萨如图形法"))
    b.append(_sl_num_rows(3, ["测量次数", "x1 (mm)", "x2 (mm)", "Δx (mm)"],
                          [2.6, 5.0, 5.0, 5.2]))

    # ── 实验六（选做）：方波相位法，复用实验四表结构 ──
    b.append(_h2("实验六（选做）：相位法测光速（方波）"))
    b.append(_sl_num_rows(3, _PHASE_HEADERS, _PHASE_WIDTHS))
    return b


# ---------------------------------------------------------------- public API

def clean_record_blocks(exp_id: str) -> list[dict]:
    if exp_id == "polarization":
        return _polarization_blocks()
    if exp_id == "sound-light":
        return _sound_light_blocks()
    raise ValueError(f"unknown record sheet id: {exp_id!r}")


def _pdf_safe(blocks: list[dict]) -> list[dict]:
    """Deep-ish copy swapping glyphs missing from SimSun for the PDF flavour."""
    out = []
    for blk in blocks:
        b = dict(blk)
        kind = b.get("kind")
        if kind == "table":
            b["rows"] = [
                [{**c, "text": c.get("text", "").translate(_PDF_FIX_TABLE)}
                 if isinstance(c, dict) else c for c in row]
                for row in b["rows"]
            ]
        elif kind in ("h1", "h2", "h3", "sub", "para", "note"):
            b["text"] = b.get("text", "").translate(_PDF_FIX_TABLE)
        out.append(b)
    return out


def record_bytes(exp_id: str, fmt: str = "docx") -> bytes:
    blocks = clean_record_blocks(exp_id)
    # Both blank record sheets are portrait A4 (user requirement: 空白表一律竖版 A4).
    if fmt == "pdf":
        # Word substitutes missing ᵢ/₁/₂ glyphs automatically; reportlab with a
        # single face would print blanks, so swap those to ASCII beforehand.
        # ² (cos²θ) is kept: Microsoft YaHei contains it.
        return docbuild.render_pdf(_pdf_safe(blocks), landscape=False,
                                   cn_pref="msyh")
    return docbuild.render_docx(blocks, landscape=False, cn="宋体", cn_en="宋体")
