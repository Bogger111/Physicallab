#!/usr/bin/env python3
"""PhysicsLab docx/pdf builders (no table fills, compact A4).

Content blocks are described once as Python dicts, then rendered by either
the Word (python-docx) or PDF (reportlab) backend.
"""

from __future__ import annotations

import io
import base64
from datetime import datetime

import numpy as np

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE
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

from experiments.polarization.adapter import PolarizationAdapter
from experiments.polarization import reports as R

CN = "微软雅黑"
CN_EN = "Microsoft YaHei"
PREVIEW_COLOR_DOCX = RGBColor(0x64, 0x6D, 0x7B)

# ---------------------------------------------------------------- fonts

_PDF_FONTS = {"CN": "Helvetica", "CN-B": "Helvetica"}


def _pdf_fonts():
    if _PDF_FONTS["CN"] != "Helvetica":
        return _PDF_FONTS
    candidates = [
        ("CN", "C:/Windows/Fonts/msyh.ttc"),
        ("CN-B", "C:/Windows/Fonts/msyhbd.ttc"),
        ("CN", "C:/Windows/Fonts/simhei.ttf"),
        ("CN-B", "C:/Windows/Fonts/simhei.ttf"),
        ("CN", "C:/Windows/Fonts/simsun.ttc"),
    ]
    for key, path in candidates:
        if key in _PDF_FONTS and _PDF_FONTS[key] != "Helvetica":
            continue
        try:
            pdfmetrics.registerFont(TTFont(key, path))
            _PDF_FONTS[key] = key
        except Exception:
            pass
    return _PDF_FONTS


def _set_east_asia(style_or_run, name=CN_EN):
    rpr = style_or_run.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), name)


# ---------------------------------------------------------------- shared specs

def _fmt(v) -> str:
    if v is None:
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f) and abs(f) < 1e12:
        return str(int(f))
    s = f"{f:.4f}".rstrip("0").rstrip(".")
    return s if s else "0"


def setup_blocks() -> list[dict]:
    """Cover page: title + student/setup info (same for record sheet and parts)."""
    blocks = [
        {"kind": "spacer", "cm": 0.6},
        {"kind": "h1", "text": "偏振光与双折射实验"},
        {"kind": "sub", "text": "实验数据记录表 / 处理报告"},
        {"kind": "spacer", "cm": 0.5},
        {
            "kind": "table",
            "widths": [4.6, 12.4],
            "font": 9.5,
            "row_h": 0.72,
            "rows": [
                [{"text": "实验日期"}, {"text": ""}],
                [{"text": "姓名"}, {"text": ""}],
                [{"text": "学号"}, {"text": ""}],
                [{"text": "班级 / 组号"}, {"text": ""}],
                [{"text": "P1 目标光强 / μW"}, {"text": ""}],
                [{"text": "背景光强 I0 / μW"}, {"text": "0.0543（按当次实测填写）"}],
                [{"text": "θ_qwp / °"}, {"text": "30 或 60（以老师要求为准）"}],
                [{"text": "教师备注"}, {"text": ""}],
            ],
        },
        {"kind": "note", "text": "填写说明：空白格为需手写的原始数据；单位已标注在表头，填写时只写数字。"},
        {"kind": "note", "text": "角度格式：度° + 分′（如 271°28′ 写 271 与 28）；光强单位统一为 μW。"},
        {"kind": "note", "text": "刻度盘读数：① 看 0 刻度位置 ② 看对齐刻度 ③ 两者相加。例：271°28′ = 270° + 1°28′。"},
        {"kind": "note", "text": "重要：只能用同一器件自身的读数差求转角，不同器件的读数差没有物理意义。"},
        {"kind": "spacer", "cm": 0.4},
    ]
    return blocks


def record_sheet_blocks() -> list[dict]:
    b: list[dict] = []
    b += setup_blocks()

    # ---------- Exp 1 malus ----------
    b += [
        {"kind": "pagebreak"},
        {"kind": "h2", "text": "实验 1 · 马吕斯定律 — I 与 cos²θ 的关系"},
        {"kind": "note", "text": "步骤：P2 从消光位置（θ = 90°）开始，每次改变 10°，分别左旋、右旋测量光强。"},
        {"kind": "note", "text": "P1 消光位置：度＿＿＿ 分＿＿＿     P1 目标光强设定：＿＿＿ μW"},
        {"kind": "note", "text": "P2 消光位置读数（θ = 90° 起点）：度＿＿＿ 分＿＿＿"},
        {
            "kind": "table",
            "widths": [1.6, 2.6, 2.6, 2.6, 2.6, 2.6, 2.6, 2.6],
            "font": 8.5,
            "row_h": 0.62,
            "rows": [
                [{"text": "θ (°)"}, {"text": "P2 左旋 (度)"}, {"text": "P2 左旋 (分)"},
                 {"text": "P2 右旋 (度)"}, {"text": "P2 右旋 (分)"},
                 {"text": "I 左旋 (μW)"}, {"text": "I 右旋 (μW)"}, {"text": "I 均值 (μW)"}],
            ] + [
                [{"text": str(t), "prefill": True}, {}, {}, {}, {}, {}, {}, {}]
                for t in range(90, -1, -10)
            ],
        },
        {"kind": "note", "text": "I 均值 = (I左 + I右) / 2，为辅助处理列。cos²θ 由程序按角度自动精确计算。"},
        {"kind": "note", "text": "cos²θ 参考值（θ = 90°→0°）：0.00 0.03 0.12 0.25 0.41 0.59 0.75 0.88 0.97 1.00"},
    ]

    # ---------- Exp 2 halfwave ----------
    b += [
        {"kind": "pagebreak"},
        {"kind": "h2", "text": "实验 2 · λ/2 波片 — 验证偏振方向变化规律"},
        {"kind": "note", "text": "步骤：C 从消光位置开始依次转 10°，每次重新找 P2 消光位置并记录度分读数。"},
        {"kind": "note", "text": "关键：P2 旋转方向与 C 保持一致；只能用同一器件自身读数差求转角。"},
        {
            "kind": "table",
            "widths": [9.4, 4.3, 4.3],
            "font": 9,
            "row_h": 0.7,
            "rows": [
                [{"text": "项目"}, {"text": "度"}, {"text": "分"}],
                [{"text": "C 初始消光位置 φ_C0"}, {}, {}],
                [{"text": "P2 初始消光位置"}, {}, {}],
            ],
        },
        {"kind": "spacer", "cm": 0.25},
        {
            "kind": "table",
            "widths": [2.0, 3.4, 4.2, 4.2, 4.2, 4.2],
            "font": 8.5,
            "row_h": 0.62,
            "rows": [
                [{"text": "序号"}, {"text": "C 偏移 (°)"}, {"text": "C 读数 (度)"},
                 {"text": "C 读数 (分)"}, {"text": "P2 消光 (度)"}, {"text": "P2 消光 (分)"}],
            ] + [
                [{"text": str(i + 1), "prefill": True}, {"text": str(off), "prefill": True},
                 {}, {}, {}, {}]
                for i, off in enumerate([0, 10, 20, 30, 40, 50])
            ],
        },
        {"kind": "note", "text": "理论预期：ΔP2 ≈ 2 × ΔC（半波片使偏振方向转过 2θ）。"},
    ]

    # ---------- Exp 3 quarterwave ----------
    b += [
        {"kind": "pagebreak"},
        {"kind": "h2", "text": "实验 3 · λ/4 波片 — 椭圆偏振光强分布 I(φ)"},
        {"kind": "note", "text": "步骤：P1⊥P2 消光 → 插入 C′ 并转至再次消光 → C′ 转 θ_qwp → P2 每转 10° 记录光强（共 36 点）。"},
        {
            "kind": "table",
            "widths": [6.0, 4.0, 4.0],
            "font": 9,
            "row_h": 0.68,
            "rows": [
                [{"text": "项目"}, {"text": "度"}, {"text": "分"}],
                [{"text": "P2 消光位置"}, {}, {}],
                [{"text": "C′ 消光位置"}, {}, {}],
                [{"text": "θ_qwp (°)"}, {"text": "30 或 60", "prefill": True}, {}],
                [{"text": "C′ 转动方向"}, {"text": "CW / CCW", "prefill": True}, {}],
                [{"text": "转后首次光强 (μW)"}, {}, {}],
                [{"text": "P2 转动方向"}, {"text": "CW / CCW", "prefill": True}, {}],
                [{"text": "首次 10° 后光强变化"}, {"text": "增大 / 减小", "prefill": True}, {}],
            ],
        },
        {"kind": "note", "text": "数据映射：θ_qwp = 30° → 首读数填入 φ = 60° 格；θ_qwp = 60° → 首读数填入 φ = 30° 格。"},
        {"kind": "note", "text": "光强减小 → 正序（φ 递增）；光强增大 → 倒序（φ 递减）。直接填最终光强到对应 φ 行。"},
        {"kind": "spacer", "cm": 0.2},
        {
            "kind": "table",
            "widths": [3.0, 3.0, 3.0, 3.0, 3.0, 3.0],
            "font": 8,
            "row_h": 0.5,
            "rows": _phi3_rows("φ (°)", "I (μW)", 12),
        },
        {"kind": "note", "text": "共 36 个数据点（φ = 0° ~ 350°，每 10° 一个）。"},
    ]

    # ---------- Exp 4 birefringence (选做) ----------
    b += [
        {"kind": "pagebreak"},
        {"kind": "h2", "text": "实验 4（选做）· 双折射现象观察"},
        {"kind": "h3", "text": "4.1 裸眼观察：将冰洲石放在文字上"},
        {
            "kind": "table",
            "widths": [6.2, 11.8],
            "font": 9,
            "row_h": 0.75,
            "rows": [
                [{"text": "观察内容"}, {"text": "记录"}],
                [{"text": "看到几个像？"}, {}],
                [{"text": "像的位置关系？"}, {}],
                [{"text": "移动冰洲石时像如何变化？"}, {}],
                [{"text": "其他现象"}, {}],
            ],
        },
        {"kind": "spacer", "cm": 0.3},
        {"kind": "h3", "text": "4.2 激光通过冰洲石"},
        {
            "kind": "table",
            "widths": [6.2, 11.8],
            "font": 9,
            "row_h": 0.75,
            "rows": [
                [{"text": "观察内容"}, {"text": "记录"}],
                [{"text": "出射几个光斑？"}, {}],
                [{"text": "光斑亮度比较"}, {}],
                [{"text": "光斑偏振方向关系"}, {}],
            ],
        },
        {"kind": "spacer", "cm": 0.3},
        {"kind": "h3", "text": "4.3 偏振方向检验（用检偏器 P2 分别检测两个光斑）"},
        {
            "kind": "table",
            "widths": [5.4, 4.2, 4.2, 4.2],
            "font": 9,
            "row_h": 0.75,
            "rows": [
                [{"text": "光斑"}, {"text": "P2 消光位置 (度)"}, {"text": "P2 消光位置 (分)"}, {"text": "备注"}],
                [{"text": "光斑 A（不偏折）"}, {}, {}, {}],
                [{"text": "光斑 B（偏折）"}, {}, {}, {}],
                [{"text": "角度差"}, {}, {}, {"text": "自动计算"}],
            ],
        },
        {"kind": "note", "text": "结论（根据实际观察填写，不要预判）："},
        {"kind": "lines", "n": 3},
    ]

    # ---------- Exp 5 waveplate ID (选做) ----------
    b += [
        {"kind": "pagebreak"},
        {"kind": "h2", "text": "实验 5（选做）· 判别 λ/4 波片与 λ/2 波片"},
        {"kind": "note", "text": "步骤：正交偏振片间插入待测波片 → 转至消光 → 再转 45° → 观察光强变化。"},
        {
            "kind": "table",
            "widths": [2.0, 2.3, 2.3, 2.3, 2.3, 3.6, 2.3, 2.6],
            "font": 8.5,
            "row_h": 0.72,
            "rows": [
                [{"text": "样品编号"}, {"text": "消光位置 (度)"}, {"text": "消光位置 (分)"},
                 {"text": "转 45° 后 (度)"}, {"text": "转 45° 后 (分)"},
                 {"text": "光强行为描述"}, {"text": "有无消光 (Y/N)"}, {"text": "判别结果"}],
            ] + [
                [{"text": f"样品 {i + 1}"}, {}, {}, {}, {}, {}, {}, {}]
                for i in range(3)
            ],
        },
        {"kind": "note", "text": "判断依据：λ/4 + 45° → 圆偏振光 → 转 P2 光强近似不变、无消光；λ/2 + 45° → 线偏振（转过 90°）→ 有消光位置。"},
        {"kind": "spacer", "cm": 0.25},
        {"kind": "h3", "text": "可选：P2 扫描记录（每 10° 一档，辅助判断）"},
        {
            "kind": "table",
            "widths": [3.0, 3.0, 3.0, 3.0, 3.0, 3.0],
            "font": 8,
            "row_h": 0.5,
            "rows": _phi3_rows("P2 (°)", "I (μW)", 6),
        },
    ]

    # ---------- Exp 6 circular (选做) ----------
    b += [
        {"kind": "pagebreak"},
        {"kind": "h2", "text": "实验 6（选做）· 圆偏振光通过检偏器的光强"},
        {"kind": "note", "text": "条件：λ/4 波片 θ = 45° 形成圆偏振光；转 P2 每 10° 记录一次光强（共 36 点）。"},
        {"kind": "note", "text": "P2 起始位置：度＿＿＿ 分＿＿＿    λ/4 波片位置确认为 45°：是 / 否"},
        {
            "kind": "table",
            "widths": [3.0, 3.0, 3.0, 3.0, 3.0, 3.0],
            "font": 8,
            "row_h": 0.5,
            "rows": _phi3_rows("P2 (°)", "I (μW)", 12),
        },
        {"kind": "note", "text": "理想圆偏振光：通过检偏器后光强应与 P2 方向无关（近似恒定）。共 36 点（0° ~ 350°）。"},
    ]
    return b


def _phi3_rows(xlab: str, ylab: str, groups: int) -> list[list[dict]]:
    rows = [[{"text": xlab}, {"text": ylab}] * 3]
    for i in range(groups):
        row = []
        for j in range(3):
            deg = (i + j * groups) * 10
            row.append({"text": str(deg), "prefill": True})
            row.append({})
        rows.append(row)
    return rows


# ---------------------------------------------------------------- Word renderer

def _doc_base() -> Document:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Mm(210)
    sec.page_height = Mm(297)
    sec.top_margin = Cm(1.1)
    sec.bottom_margin = Cm(1.1)
    sec.left_margin = Cm(1.4)
    sec.right_margin = Cm(1.4)
    normal = doc.styles["Normal"]
    normal.font.name = CN_EN
    normal.font.size = Pt(10)
    _set_east_asia(normal)
    return doc


def _doc_borders(table) -> None:
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tblPr.append(borders)
    margins = OxmlElement("w:tblCellMar")
    for side, w in (("top", 20), ("start", 40), ("bottom", 20), ("end", 40)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(w))
        el.set(qn("w:type"), "dxa")
        margins.append(el)
    tblPr.append(margins)


def _doc_table(doc, spec) -> None:
    rows = spec["rows"]
    if not rows:
        return
    n_cols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=n_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _doc_borders(table)
    widths = spec.get("widths")
    font_pt = spec.get("font", 8.5)
    row_h = spec.get("row_h", 0.6)
    for ri, row in enumerate(rows):
        table.rows[ri].height = Cm(row_h)
        table.rows[ri].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        for ci in range(n_cols):
            cell = table.cell(ri, ci)
            cell.vertical_alignment = 1  # center
            val = row[ci] if ci < len(row) else {}
            text = (val or {}).get("text", "") if isinstance(val, dict) else str(val)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if ri == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(str(text))
            run.font.size = Pt(font_pt)
            run.font.name = CN_EN
            _set_east_asia(run)
            if ri == 0:
                run.font.bold = True
            if isinstance(val, dict) and val.get("prefill"):
                run.font.color.rgb = PREVIEW_COLOR_DOCX
                run.font.italic = True
    if widths:
        for ci, w in enumerate(widths):
            for row in table.rows:
                row.cells[ci].width = Cm(w)


def _doc_p(doc, text, size=10, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT,
           space_after=4, space_before=0, color=None):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    run = p.add_run(str(text))
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = CN_EN
    _set_east_asia(run)
    if color:
        run.font.color.rgb = color
    return p


def _doc_img(doc, b64, width_cm=17.0, caption=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(io.BytesIO(base64.b64decode(b64)), width=Cm(width_cm))
    if caption:
        _doc_p(doc, caption, size=9, align=WD_ALIGN_PARAGRAPH.CENTER,
               color=RGBColor(0x64, 0x6D, 0x7B), space_before=0)


def render_docx(blocks) -> bytes:
    doc = _doc_base()
    for blk in blocks:
        kind = blk["kind"]
        if kind == "h1":
            _doc_p(doc, blk["text"], size=17, bold=True,
                   align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2, space_before=2)
        elif kind == "sub":
            _doc_p(doc, blk["text"], size=11.5,
                   align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
        elif kind == "h2":
            _doc_p(doc, blk["text"], size=12.5, bold=True, space_after=4, space_before=8)
        elif kind == "h3":
            _doc_p(doc, blk["text"], size=10.5, bold=True, space_after=3, space_before=5)
        elif kind == "note":
            _doc_p(doc, blk["text"], size=8.5, space_after=3,
                   color=RGBColor(0x4A, 0x55, 0x60))
        elif kind == "para":
            _doc_p(doc, blk["text"], size=blk.get("size", 10), space_after=4)
        elif kind == "table":
            _doc_table(doc, blk)
        elif kind == "image":
            _doc_img(doc, blk["b64"], blk.get("width_cm", 17.0), blk.get("caption"))
        elif kind == "lines":
            for _ in range(blk.get("n", 1)):
                _doc_p(doc, "＿" * 92, size=9, space_after=8)
        elif kind == "spacer":
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(int(blk.get("cm", 0.3) * 28))
        elif kind == "pagebreak":
            doc.add_page_break()
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- PDF renderer

def _pdf_styles():
    F = _pdf_fonts()
    cn = F["CN"]
    cnb = F["CN-B"]
    return {
        "h1": ParagraphStyle("h1", fontName=cnb, fontSize=16, leading=20,
                             alignment=1, spaceAfter=2),
        "sub": ParagraphStyle("sub", fontName=cn, fontSize=10.5, leading=13,
                              alignment=1, spaceAfter=8),
        "h2": ParagraphStyle("h2", fontName=cnb, fontSize=12, leading=15,
                             spaceBefore=6, spaceAfter=4),
        "h3": ParagraphStyle("h3", fontName=cnb, fontSize=10, leading=13,
                             spaceBefore=4, spaceAfter=3),
        "note": ParagraphStyle("note", fontName=cn, fontSize=8, leading=10.5,
                               spaceAfter=2, textColor=colors.HexColor("#454f5a")),
        "para": ParagraphStyle("para", fontName=cn, fontSize=9.5, leading=13,
                               spaceAfter=4),
        "cell": ParagraphStyle("cell", fontName=cn, fontSize=8, leading=9.6,
                               alignment=1),
        "cellb": ParagraphStyle("cellb", fontName=cnb, fontSize=8, leading=9.6,
                                alignment=1),
        "caption": ParagraphStyle("caption", fontName=cn, fontSize=8, leading=10,
                                  alignment=1, textColor=colors.HexColor("#646d7b")),
    }


def _pdf_table(story, spec, styles, usable):
    rows = spec["rows"]
    F = _pdf_fonts()
    cnb = F["CN-B"]
    widths = spec.get("widths") or [usable / max(len(r) for r in rows)] * max(len(r) for r in rows)
    scale = usable / (sum(widths) * 10.0)  # usable(mm) vs widths(cm)
    col_w = [w * 10.0 * scale for w in widths]  # cm -> mm
    font_pt = spec.get("font", 8.5)
    row_h = spec.get("row_h", 0.62) * 26 * 0.95  # approx
    data = []
    for ri, row in enumerate(rows):
        line = []
        for val in row:
            text = val.get("text", "") if isinstance(val, dict) else str(val)
            style = styles["cellb"] if ri == 0 else styles["cell"]
            if isinstance(val, dict) and val.get("prefill"):
                ps = ParagraphStyle("pf", parent=style, textColor=colors.HexColor("#646d7b"))
                line.append(Paragraph(str(text), ps))
            else:
                line.append(Paragraph(str(text), style))
        data.append(line)
    t = RLTable(data, colWidths=col_w, repeatRows=1)
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]
    if row_h:
        style_cmds.append(("ROWHEIGHTS", (0, 0), (-1, -1), row_h))
    t.setStyle(TableStyle(style_cmds))
    story.append(t)


def render_pdf(blocks, out=None) -> bytes:
    if out is None:
        out = io.BytesIO()
    styles = _pdf_styles()
    doc = SimpleDocTemplate(
        out, pagesize=A4,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    usable = A4[0] - 24 * mm

    def flowable_of(blk):
        kind = blk["kind"]
        if kind in ("h1", "h2", "h3", "sub", "para", "note"):
            return Paragraph(blk["text"], styles[kind])
        if kind == "table":
            holder = []
            _pdf_table(holder, blk, styles, usable)
            return holder[0]
        if kind == "image":
            from PIL import Image as PILImage
            raw = base64.b64decode(blk["b64"])
            with PILImage.open(io.BytesIO(raw)) as im:
                px_w, px_h = im.size
            w_pt = blk.get("width_cm", 17.0) * 28.35
            h_pt = w_pt * (px_h / px_w)
            img = RLImage(io.BytesIO(raw), width=w_pt, height=h_pt)
            return [Spacer(1, 2 * mm), img] + (
                [Paragraph(blk["caption"], styles["caption"])] if blk.get("caption") else [])
        if kind == "lines":
            els = []
            for _ in range(blk.get("n", 1)):
                els.append(Paragraph("＿" * 92, styles["note"]))
                els.append(Spacer(1, 1 * mm))
            return els
        if kind == "spacer":
            return Spacer(1, blk.get("cm", 0.3) * 14 * mm)
        if kind == "pagebreak":
            return PageBreak()
        return []

    story = []
    idx = 0
    n = len(blocks)
    pending_head = None
    while idx < n:
        blk = blocks[idx]
        if blk["kind"] in ("h2", "h3") and idx + 1 < n and blocks[idx + 1]["kind"] == "image":
            # hold the heading back; it travels with its figure
            pending_head = blk
            idx += 1
            continue
        if blk["kind"] == "image":
            cluster = []
            if pending_head is not None:
                ph = flowable_of(pending_head)
                cluster += ph if isinstance(ph, list) else [ph]
                pending_head = None
            img_flow = flowable_of(blk)
            cluster += img_flow if isinstance(img_flow, list) else [img_flow]
            idx += 1
            while idx < n and blocks[idx]["kind"] in ("note",):
                f = flowable_of(blocks[idx])
                cluster += f if isinstance(f, list) else [f]
                idx += 1
            story.append(KeepTogether(cluster))
            continue
        f = flowable_of(blk)
        if isinstance(f, list):
            story.extend(f)
        else:
            story.append(f)
        idx += 1
    doc.build(story)
    return out.getvalue() if isinstance(out, io.BytesIO) else out


# ---------------------------------------------------------------- analysis glue

def analyze(data: dict, bg_uw: float = 0.0, theta_qwp: float = 30.0) -> dict:
    """Recompute processed dicts (arrays kept) for reports."""
    adapter = PolarizationAdapter(bg_uw=bg_uw, theta_qwp=theta_qwp)
    r = {}
    for key in ("malus", "halfwave", "quarterwave", "circular"):
        if data.get(key):
            fn = getattr(adapter, "_process_" + key)
            rd = fn(data[key])
            if rd is not None:
                r[key] = rd
    basic = {}
    for key, rd in r.items():
        basic[key] = getattr(adapter, "_plot_" + key)(rd)
    advanced = []
    for group, caption, fn, need in R.ADVANCED_SPEC:
        if need == "all":
            if not all(k in r for k in ("malus", "halfwave", "quarterwave")):
                continue
            try:
                fig_bytes = fn(r["malus"], r["halfwave"], r["quarterwave"])
            except Exception:
                continue
        else:
            if need not in r:
                continue
            try:
                fig_bytes = fn(r[need])
            except Exception:
                continue
        advanced.append({"group": group, "caption": caption,
                         "b64": base64.b64encode(fig_bytes).decode("utf-8")})
    return {
        "meta": {"bg_uw": bg_uw, "theta_qwp": theta_qwp,
                 "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")},
        "r": r,
        "basic": basic,
        "advanced": advanced,
        "summaries": {k: rd["summary"] for k, rd in r.items()},
    }


def _raw_input_tables(data: dict) -> dict:
    """Original submitted numbers, for the raw-data tables in part reports."""
    out = {}
    if data.get("malus"):
        out["malus"] = [[{"text": str(row.get("theta", ""))},
                         {"text": _fmt(row.get("i_left"))},
                         {"text": _fmt(row.get("i_right"))}] for row in data["malus"].get("rows", [])]
    if data.get("halfwave"):
        init = data["halfwave"].get("initial", {})
        out["halfwave_init"] = [
            [{"text": "C 初始消光位置"}, {"text": _fmt(init.get("c_deg"))}, {"text": _fmt(init.get("c_min"))}],
            [{"text": "P2 初始消光位置"}, {"text": _fmt(init.get("p2_deg"))}, {"text": _fmt(init.get("p2_min"))}],
        ]
        out["halfwave"] = [[{"text": str(i + 1)}, {"text": _fmt(row.get("offset", ""))},
                            {"text": _fmt(row.get("c_deg"))}, {"text": _fmt(row.get("c_min"))},
                            {"text": _fmt(row.get("p2_deg"))}, {"text": _fmt(row.get("p2_min"))}]
                           for i, row in enumerate(data["halfwave"].get("rows", []))]
    if data.get("quarterwave"):
        rows = data["quarterwave"].get("rows", [])
        pairs = []
        for i in range(0, len(rows), 3):
            line = []
            for j in range(3):
                if i + j < len(rows):
                    line += [{"text": str(rows[i + j].get("phi", ""))},
                             {"text": _fmt(rows[i + j].get("i_raw"))}]
                else:
                    line += [{}, {}]
            pairs.append(line)
        out["quarterwave"] = pairs
    if data.get("circular"):
        rows = data["circular"].get("rows", [])
        pairs = []
        for i in range(0, len(rows), 3):
            line = []
            for j in range(3):
                if i + j < len(rows):
                    line += [{"text": str(rows[i + j].get("angle", ""))},
                             {"text": _fmt(rows[i + j].get("i_raw"))}]
                else:
                    line += [{}, {}]
            pairs.append(line)
        out["circular"] = pairs
    return out


def _summary_pairs(summary: dict, order: list[str]) -> list[list[dict]]:
    rows = []
    for k in order:
        if k in summary:
            rows.append([{"text": _SUMMARY_LABELS.get(k, k)}, {"text": _fmt(summary[k])}])
    pairs = []
    for i in range(0, len(rows), 2):
        pair = rows[i]
        if i + 1 < len(rows):
            pair += rows[i + 1]
        else:
            pair += [{"text": ""}, {"text": ""}]
        pairs.append(pair)
    return pairs


_SUMMARY_LABELS = {
    "slope": "斜率 / 截距", "intercept": "", "r_squared": "R²",
    "extinction_ratio": "消光比", "degree_of_polarization": "偏振度",
    "theory_slope": "理论斜率", "slope_deviation_pct": "斜率偏差 %",
    "I_max_exp": "Imax (实验)", "I_min_exp": "Imin (实验)",
    "ratio_exp": "Imax/Imin (实验)", "ratio_theory": "Imax/Imin (理论)",
    "A_avg": "振幅参数 A（平均）", "relative_diff_pct": "相对偏差 %",
    "I_mean": "平均光强", "ratio": "Imax/Imin", "cv_pct": "变异系数 CV %",
    "I_max": "Imax (实验)", "I_min": "Imin (实验)", "std_dev": "标准差 σ",
    "A_from_max": "A (由 Imax)", "A_from_min": "A (由 Imin)",
    "theta_qwp": "θ_qwp", "data_points": "数据点数",
    "A_nl_fit": "A（非线性拟合）", "theta_nl_fit": "θ（非线性拟合）",
}

_SUB_TITLES = {
    "malus": ("实验 1 · 马吕斯定律", "测量不同偏振角下的透射光强，验证 I = I0cos²θ。第一张图为 I 左旋 / I 右旋双通道同图对比。"),
    "halfwave": ("实验 2 · λ/2 波片", "验证半波片使偏振方向旋转 2θ：ΔP2 与 ΔC 应满足 2 倍关系。"),
    "quarterwave": ("实验 3 · λ/4 波片", "测量椭圆偏振光 I(φ) 分布，确定振幅参数 A 并验证 Imax/Imin 理论比。"),
    "circular": ("实验 4 · 圆偏振光（选做）", "验证圆偏振光通过检偏器后光强近似恒定。"),
}

_SUB_NAME = {
    "malus": "马吕斯定律", "halfwave": "λ/2 半波片",
    "quarterwave": "λ/4 波片", "circular": "圆偏振光",
}

_RAW_HEADERS = {
    "malus": [{"text": "θ (°)"}, {"text": "I 左旋 (μW)"}, {"text": "I 右旋 (μW)"}],
    "halfwave": [{"text": "序号"}, {"text": "C 偏移 (°)"}, {"text": "C (度)"},
                 {"text": "C (分)"}, {"text": "P2 (度)"}, {"text": "P2 (分)"}],
    "quarterwave": [{"text": "φ (°)"}, {"text": "I (μW)"}] * 3,
    "circular": [{"text": "P2 (°)"}, {"text": "I (μW)"}] * 3,
}

_RAW_WIDTHS = {
    "malus": [3.4, 7.2, 7.2],
    "halfwave": [2.0, 3.4, 4.1, 4.1, 4.1, 4.1],
    "quarterwave": [2.96, 2.96, 2.96, 2.96, 2.96, 2.96],
    "circular": [2.96, 2.96, 2.96, 2.96, 2.96, 2.96],
}

_SUM_WIDTHS = [4.45, 4.45, 4.45, 4.45]


def _meta_intro(title: str, run: dict, note: str) -> list[dict]:
    """Report head: title + run parameters (no student blanks in part reports)."""
    m = run["meta"]
    total = sum(s.get("data_points", 0) for s in run["summaries"].values())
    blocks = [
        {"kind": "spacer", "cm": 0.2},
        {"kind": "h1", "text": f"偏振光与双折射实验 · 数据处理报告（{title}）"},
        {"kind": "sub", "text": note},
        {
            "kind": "table",
            "widths": [4.2, 6.8, 4.2, 2.6],
            "font": 9,
            "row_h": 0.62,
            "rows": [
                [{"text": "背景光强 I0 (μW)"}, {"text": _fmt(m["bg_uw"])},
                 {"text": "θ_qwp (°)"}, {"text": _fmt(m["theta_qwp"])}],
                [{"text": "数据点数"}, {"text": str(total)},
                 {"text": "生成时间"}, {"text": m["generated_at"]}],
            ],
        },
    ]
    return blocks


def _raw_table_block(key: str, raw: dict, present: bool) -> list[dict]:
    if not present or key not in raw:
        return []
    if key == "halfwave":
        b = [{
            "kind": "table", "widths": [9.0, 4.4, 4.4], "font": 8.5, "row_h": 0.6,
            "rows": [[{"text": "项目"}, {"text": "度"}, {"text": "分"}]] + raw["halfwave_init"],
        }]
        b.append({"kind": "spacer", "cm": 0.15})
    else:
        b = []
    rows = [[h for h in _RAW_HEADERS[key]]] + raw[key]
    b.append({"kind": "table", "widths": _RAW_WIDTHS[key], "font": 8, "row_h": 0.48,
              "rows": rows})
    return b


def _summary_table_block(key: str, run: dict) -> list[dict]:
    s = run["summaries"].get(key)
    if not s:
        return []
    if key == "malus":
        order = ["slope", "intercept", "r_squared", "extinction_ratio",
                 "degree_of_polarization", "data_points"]
    elif key == "halfwave":
        order = ["slope", "theory_slope", "slope_deviation_pct", "r_squared", "data_points"]
    elif key == "quarterwave":
        order = ["I_max_exp", "I_min_exp", "ratio_exp", "ratio_theory",
                 "A_avg", "A_nl_fit", "relative_diff_pct", "data_points"]
    else:
        order = ["I_mean", "I_max", "I_min", "ratio", "cv_pct", "std_dev", "data_points"]
    rows = []
    for k in order:
        if k in s:
            v = s[k]
            rows.append([{"text": _SUMMARY_LABELS.get(k, k)}, {"text": _fmt(v)}])
    pairs = []
    for i in range(0, len(rows), 2):
        pair = rows[i] + (rows[i + 1] if i + 1 < len(rows) else [{"text": ""}, {"text": ""}])
        pairs.append(pair)
    return [{"kind": "table", "widths": _SUM_WIDTHS, "font": 8.5, "row_h": 0.55, "rows": pairs}]


def part1_blocks(run: dict, data: dict) -> list[dict]:
    blocks = _meta_intro(
        "基准部分", run,
        "包含四个子实验的原始数据表、计算结果与基准图像（Word 可编辑；PDF 紧凑排版用于打印）。")
    raw = _raw_input_tables(data)
    order = ["malus", "halfwave", "quarterwave", "circular"]
    for n, key in enumerate(order, 1):
        if key not in run["r"]:
            continue
        title, desc = _SUB_TITLES[key]
        blocks.append({"kind": "h2", "text": f"{n}. {title}"})
        blocks.append({"kind": "note", "text": desc})
        blocks += _raw_table_block(key, raw, True)
        blocks.append({"kind": "note", "text": "计算结果："})
        blocks += _summary_table_block(key, run)
        fig = run["basic"].get(key)
        if fig:
            blocks.append({"kind": "image", "b64": fig,
                           "width_cm": 15.8,
                           "caption": f"图 {n} · {_SUB_NAME[key]}"})
        blocks.append({"kind": "spacer", "cm": 0.2})
    blocks.append({"kind": "note",
                   "text": "说明：数据处理由 PhysicsLab 本地服务完成；拟合采用最小二乘线性回归，λ/4 波片附加非线性拟合。"})
    return blocks


def part2_blocks(run: dict, data: dict) -> list[dict]:
    blocks = _meta_intro(
        "拓展部分", run,
        "误差分析与拓展可视化：残差分布、实验-理论对比、恒定性与关键参数汇总。")
    for n, item in enumerate(run["advanced"], 1):
        blocks.append({"kind": "h2", "text": f"图 {n} · {item['caption']}"})
        blocks.append({"kind": "image", "b64": item["b64"], "width_cm": 15.8})
        blocks.append({"kind": "note",
                       "text": "分析要点：观察实验数据与理论/拟合线的偏离幅度与趋势，判断随机误差与系统误差的可能来源。"})
        blocks.append({"kind": "spacer", "cm": 0.15})
    blocks.append({"kind": "h2", "text": "结论与误差讨论"})
    blocks.append({"kind": "note", "text": "请结合上述图表撰写结论；Word 中可直接编辑，PDF 留白供手写打印。"})
    blocks.append({"kind": "lines", "n": 5})
    return blocks


# ---------------------------------------------------------------- public API

def record_sheet_bytes(fmt: str) -> bytes:
    blocks = record_sheet_blocks()
    if fmt == "docx":
        return render_docx(blocks)
    return render_pdf(blocks)


def part_bytes(part: str, data: dict, bg_uw: float = 0.0,
               theta_qwp: float = 30.0, fmt: str = "docx") -> bytes:
    run = analyze(data, bg_uw=bg_uw, theta_qwp=theta_qwp)
    if part == "advanced":
        blocks = part2_blocks(run, data)
    else:
        blocks = part1_blocks(run, data)
    if fmt == "docx":
        return render_docx(blocks)
    return render_pdf(blocks)
