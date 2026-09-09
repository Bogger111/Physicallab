#!/usr/bin/env python3
"""mimo-style clean landscape record sheets (exp01 polarization, exp02 sound-light).

Mirrors C:/Users/Bogger/OneDrive/Desktop/Hermes File/PhysicsLab_Output/01_record_tables/
gen_clean_tables.py: experiment title (h2) is followed directly by its tables,
no page header/footer, no explanatory note paragraphs, no cell fills. Tables
flow naturally across landscape A4 pages (no forced page breaks); reference
values (cos²θ, sequence numbers, offsets, angles, sample/group labels) are
prefilled cells, the rest is blank for handwriting.

Rendering contract:
  record_bytes('polarization'|'sound-light', 'docx'|'pdf')
docx -> render_docx(landscape=True, cn='宋体', cn_en='宋体')
pdf  -> render_pdf(landscape=True, cn_pref='simsun')
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
    b.append(_tbl([2.7, 3.0, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5], rows1))

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
    b.append(_tbl([3.0, 4.5, 4.8, 4.8, 4.8, 4.8], rows2b))

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
    b.append(_tbl([4.45, 4.45, 4.45, 4.45, 4.45, 4.45], rows3b))

    # ── 实验四：双折射（选做）──
    b.append(_h2("实验四（选做）：双折射现象观察"))
    b.append(_sp(0.1))
    rows4a = [[_cell(h) for h in ("观察内容", "记录")],
              [_cell("看到几个像？"), {}],
              [_cell("像的位置关系？"), {}],
              [_cell("移动冰洲石时像如何变化？"), {}],
              [_cell("出射几个光斑？"), {}],
              [_cell("光斑偏振方向关系"), {}]]
    b.append(_tbl([8.0, 12.0], rows4a))              # 80/120 mm
    b.append(_sp(0.15))
    rows4b = [[_cell(h) for h in ("光斑", "P2消光(度)", "P2消光(分)", "备注")],
              [_cell("光斑A（不偏折）"), {}, {}, {}],
              [_cell("光斑B（偏折）"), {}, {}, {}],
              [_cell("角度差"), {}, {}, {}]]
    b.append(_tbl([8.7, 6.0, 6.0, 6.0], rows4b))

    # ── 实验五：波片鉴别（选做）──
    b.append(_h2("实验五（选做）：判别 λ/4 与 λ/2 波片"))
    b.append(_sp(0.1))
    head5 = [_cell(h) for h in
             ("样品", "消光(度)", "消光(分)", "转45°后(度)", "转45°后(分)",
              "光强行为", "有无消光", "判别结果")]
    rows5 = [head5] + [[_cell(f"样品{i}", True)] + _empty_row(7)
                       for i in range(1, 4)]
    b.append(_tbl([4.2, 3.3, 3.3, 3.5, 3.5, 3.6, 2.7, 2.6], rows5))

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
    b.append(_tbl([4.45] * 6, rows6))
    return b


# ---------------------------------------------------------------- exp02 sound & light

def _sl_measure_table(row_labels: list) -> dict:
    head = [_cell("测量次数")] + [_cell(str(i)) for i in range(1, 13)]
    rows = [head] + [[_cell(lab)] + _empty_row(12) for lab in row_labels]
    return _tbl([4.5] + [1.85] * 12, rows)


def _sl_group_rows(headers: tuple, n: int = 3) -> list:
    rows = [[_cell(h) for h in headers]]
    for i in range(1, n + 1):
        rows.append([_cell(f"第{i}组", True)] + _empty_row(len(headers) - 1))
    return rows


def _sound_light_blocks() -> list[dict]:
    b: list[dict] = []

    # ── 实验一：空气共振法 ──
    b.append(_h2("实验一：空气中共振法测声速"))
    b.append(_sp(0.1))
    b.append(_sl_measure_table(["lᵢ / mm"]))
    b.append(_sp(0.1))
    b.append(_para("f = ________ Hz    室温 t = ________ °C"))
    b.append(_sp(0.2))

    # ── 实验二：水中相位法 ──
    b.append(_h2("实验二：水中相位法测声速"))
    b.append(_sp(0.1))
    b.append(_sl_measure_table(["lᵢ / mm"]))
    b.append(_sp(0.1))
    b.append(_para("f = ________ Hz"))
    b.append(_sp(0.2))

    # ── 实验三：飞行时间法（选做）──
    b.append(_h2("实验三（选做）：飞行时间法测声速"))
    b.append(_sp(0.1))
    b.append(_sl_measure_table(["Lᵢ / mm", "Tᵢ / μs"]))
    b.append(_sp(0.2))

    # ── 实验四：光速正弦法 — 周期 ──
    b.append(_h2("实验四：光速正弦法 — 周期 T"))
    b.append(_sp(0.1))
    b.append(_tbl([3.0, 4.0, 4.0],                   # 30/40/40 mm
                  _sl_group_rows(("组别", "间距(格)", "T / μs"))))
    b.append(_sp(0.2))

    # ── 实验五：光速正弦法 — 相移 ──
    b.append(_h2("实验五：光速正弦法 — 相位移动 Δt"))
    b.append(_sp(0.1))
    b.append(_tbl([4.2, 4.5, 4.5, 4.5, 4.5, 4.5],
                  _sl_group_rows(("组别", "移动格数", "Δt/μs",
                                  "x₁/mm", "x₂/mm", "Δx/mm"))))
    b.append(_sp(0.2))

    # ── 实验六：李萨如法 ──
    b.append(_h2("实验六：李萨如图形法测光速"))
    b.append(_sp(0.1))
    b.append(_tbl([6.6, 6.7, 6.7, 6.7],
                  _sl_group_rows(("组别", "x₁ / mm", "x₂ / mm", "Δx / mm"))))
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
    if fmt == "pdf":
        # Word substitutes missing ᵢ/₁/₂ glyphs automatically; reportlab with a
        # single face would print blanks, so swap those to ASCII beforehand.
        # ² (cos²θ) is kept: Microsoft YaHei contains it.
        return docbuild.render_pdf(_pdf_safe(blocks), landscape=True,
                                   cn_pref="msyh")
    return docbuild.render_docx(blocks, landscape=True, cn="宋体", cn_en="宋体")
