"""Shared four-section layout for all experiment reports.

The first two sections intentionally have no report title or narrative: only
numbered table/figure captions and their objects.  The explicit page breaks
prevent content from adjacent sections sharing a page.
"""

from __future__ import annotations

from collections.abc import Iterable


def latex(formula: str, width_cm: float | None = None) -> dict:
    """A display equation rendered from Matplotlib's LaTeX-style mathtext."""
    block = {"kind": "equation", "latex": formula}
    if width_cm is not None:
        block["width_cm"] = width_cm
    return block


def _numbered_objects(kind: str, entries: Iterable[tuple[str, dict]]) -> list[dict]:
    prefix = "表" if kind == "table" else "图"
    blocks: list[dict] = []
    for number, (name, obj) in enumerate(entries, start=1):
        blocks.append({"kind": "h3", "text": f"{prefix} {number}　{name}"})
        item = dict(obj)
        item["kind"] = kind
        item.pop("caption", None)
        blocks.append(item)
        blocks.append({"kind": "spacer", "cm": 0.08})
    return blocks


def four_section_report(
    tables: Iterable[tuple[str, dict]],
    figures: Iterable[tuple[str, dict]],
    analysis: Iterable[dict],
    discussion: Iterable[dict],
) -> list[dict]:
    """Assemble one portrait report with four page-isolated sections."""
    blocks = _numbered_objects("table", tables)
    blocks.append({"kind": "pagebreak"})
    blocks.extend(_numbered_objects("image", figures))
    blocks.append({"kind": "pagebreak"})
    blocks.append({"kind": "h2", "text": "第三部分　数据分析与处理"})
    blocks.extend(analysis)
    blocks.append({"kind": "pagebreak"})
    blocks.append({"kind": "h2", "text": "第四部分　拓展、建议、误差分析与总结"})
    blocks.extend(discussion)
    return blocks
