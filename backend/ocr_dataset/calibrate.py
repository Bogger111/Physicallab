"""Derive per-experiment numeric-cell ROIs from the record sheet this app renders.

Students print the blank record sheet, fill it by hand and photograph it.  That
sheet is therefore the layout template, and this module turns it into a
coordinate contract: it renders the sheet with reportlab, captures the exact
rectangle of every table cell reportlab draws, and maps those rectangles onto
stable field IDs from the same config that produces the confirmed values.

The mapping never depends on the order a student wrote things.  It is derived
once, offline, and frozen into ``layouts/<experiment_id>.json``; at build time
``segment.py`` reads those coordinates and verifies them with a registration
check before trusting them.

Usage::

    python -m backend.ocr_dataset.calibrate --experiment multimeter --write
    python -m backend.ocr_dataset.calibrate --all --write --overlay artifacts/_calib
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

#: Canonical table coordinate system: A4 portrait (210 x 297 mm) at ~193 dpi.
#: The ratio must match the paper ratio, otherwise perspective correction would
#: skew every calibrated relative coordinate.
REFERENCE_SIZE = (1600, 2263)

CALIBRATION_CONFIDENCE = 0.9

#: A literal field ID, or ``(prefix, suffix)`` describing a per-row family such
#: as ``("voltage.rows.row_", "measured")`` -> ``voltage.rows.row_07.measured``.
ColumnRef = str | tuple[str, str]


def _materialize(ref: ColumnRef, data_row: int) -> str:
    if isinstance(ref, str):
        return ref
    prefix, suffix = ref
    return f"{prefix}{data_row:02d}.{suffix}"


@dataclass(frozen=True)
class CapturedTable:
    """Geometry of one reportlab table drawn on a page, in PDF points."""

    page: int
    origin: tuple[float, float]
    col_positions: tuple[float, ...]
    row_positions: tuple[float, ...]
    col_widths: tuple[float, ...]
    row_heights: tuple[float, ...]

    def cell_px(
        self,
        row: int,
        column: int,
        reference_size: tuple[int, int],
        page_size: tuple[float, float],
        offset: tuple[float, float] = (0.0, 0.0),
    ) -> tuple[int, int, int, int]:
        """Cell rectangle in canonical image pixels as (x1, y1, x2, y2).

        reportlab puts the table origin at the bottom-left and accumulates
        ``_rowpositions`` *downward* from the table top, so visual row 0 has the
        largest offset.  ``offset`` carries the correction measured against the
        page actually rasterised by reportlab, because ``Flowable.drawOn`` does
        not report the same origin the canvas paints at.
        """
        width, height = reference_size
        page_width, page_height = page_size
        scale_x, scale_y = width / page_width, height / page_height
        shift_x, shift_y = offset
        x1 = (self.origin[0] + self.col_positions[column]) * scale_x + shift_x
        x2 = x1 + self.col_widths[column] * scale_x
        y_top = (page_height - (self.origin[1] + self.row_positions[row])) * scale_y + shift_y
        y_bottom = (page_height - (self.origin[1] + self.row_positions[row + 1])) * scale_y + shift_y
        return (
            int(round(x1)), int(round(min(y_top, y_bottom))),
            int(round(x2)), int(round(max(y_top, y_bottom))),
        )

    def frame_px(self, reference_size: tuple[int, int], page_size: tuple[float, float],
                 offset: tuple[float, float] = (0.0, 0.0)):
        top_left = self.cell_px(0, 0, reference_size, page_size, offset)
        bottom_right = self.cell_px(
            len(self.row_positions) - 2, len(self.col_positions) - 2, reference_size, page_size, offset
        )
        return [top_left[0], top_left[1], bottom_right[2], bottom_right[3]]


@dataclass(frozen=True)
class TableIdentity:
    """How the cells of one record-sheet table map onto stable field IDs.

    ``grid`` states the displayed body grid explicitly (used for the hand-built
    record sheets); ``groups`` says how many copies of the logical column group
    that grid holds side by side.  ``base_columns`` + ``rows_total`` describe
    the config-driven sheets, including tables that ``documents._fold_rows``
    splits into repeated column groups.
    """

    label: str = ""
    grid: tuple[tuple[ColumnRef | None, ...], ...] | None = None
    groups: int = 1
    base_columns: tuple[ColumnRef | None, ...] | None = None
    rows_total: int | None = None
    wrap_rows: int | None = None


@dataclass(frozen=True)
class AdaptedTable:
    """A table identity that has been validated against a rendered shape."""

    label: str
    grid: tuple[tuple[ColumnRef | None, ...], ...]
    groups: int = 1

    def field_id(self, body_row: int, column: int) -> str | None:
        rows = len(self.grid)
        if not 0 <= body_row < rows or not 0 <= column < len(self.grid[body_row]):
            return None
        ref = self.grid[body_row][column]
        if ref is None:
            return None
        if self.groups > 1:
            base_width = len(self.grid[0]) // self.groups
            data_row = (column // base_width) * rows + body_row + 1
        else:
            data_row = body_row + 1
        return _materialize(ref, data_row)


def _adapt(identity: TableIdentity | None, cell_rows: list[list[Any]]) -> AdaptedTable | None:
    """Validate an identity against a rendered table, or reject it.

    A shape the identity cannot explain is dropped rather than guessed: a cell
    whose field is uncertain must never reach the training set.
    """
    if identity is None or not cell_rows or not cell_rows[0]:
        return None
    rendered_columns = len(cell_rows[0])
    body_rows = len(cell_rows) - 1
    if any(len(row) != rendered_columns for row in cell_rows):
        return None

    if identity.grid is not None:
        if body_rows != len(identity.grid) or any(len(row) != rendered_columns for row in identity.grid):
            return None
        return AdaptedTable(identity.label, identity.grid, groups=identity.groups)

    base = identity.base_columns
    if not base or rendered_columns % len(base):
        return None
    groups = rendered_columns // len(base)
    if identity.rows_total is None:
        return None
    if groups == 1:
        if body_rows != identity.rows_total:
            return None
        grid = tuple(tuple(base[column] for column in range(rendered_columns)) for _ in range(body_rows))
        return AdaptedTable(identity.label, grid)
    if identity.wrap_rows is not None:
        if body_rows != identity.wrap_rows:
            return None
        grid = tuple(
            tuple(base[column % len(base)] for column in range(rendered_columns))
            for _ in range(body_rows)
        )
        return AdaptedTable(identity.label, grid, groups=groups)
    # Auto-folded template: mirror documents._fold_rows exactly.
    expected_groups = -(-identity.rows_total // 30)
    per_group = -(-identity.rows_total // expected_groups)
    if groups != expected_groups or body_rows != per_group:
        return None
    grid = tuple(
        tuple(tuple(base[column % len(base)] for column in range(rendered_columns)))
        for _ in range(body_rows)
    )
    return AdaptedTable(identity.label, grid, groups=groups)


def _render_blocks(experiment, blocks: list[dict]) -> list[dict]:
    if experiment.id in ("polarization", "sound-light"):
        from experiments import record_clean

        return record_clean._pdf_safe(blocks)
    return blocks


def record_sheet_blocks(experiment) -> list[dict]:
    """The exact block list the record-sheet endpoint renders for this experiment."""
    if experiment.id in ("polarization", "sound-light"):
        from experiments import record_clean

        return record_clean.clean_record_blocks(experiment.id)
    from experiments.core.documents import record_blocks

    return record_blocks(experiment)


def capture_tables(blocks: list[dict]) -> tuple[bytes, list[CapturedTable], tuple[float, float]]:
    """Render ``blocks`` and record every table cell rectangle reportlab draws."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus.flowables import Flowable
    from reportlab.platypus.tables import Table

    from experiments.polarization import docbuild

    captured: list[CapturedTable] = []
    origins: list[tuple[float, float]] = []
    page = [0]

    original_draw = Table.draw
    original_draw_on = Flowable.drawOn
    original_show_page = rl_canvas.Canvas.showPage

    def draw(self):
        result = original_draw(self)
        if origins:
            captured.append(CapturedTable(
                page=page[0],
                origin=(float(origins[-1][0]), float(origins[-1][1])),
                col_positions=tuple(float(v) for v in self._colpositions),
                row_positions=tuple(float(v) for v in self._rowpositions),
                col_widths=tuple(float(v) for v in self._colWidths),
                row_heights=tuple(float(v) for v in self._rowHeights),
            ))
        return result

    def draw_on(self, canv, x, y, _sW=0):
        origins.append((x, y))
        try:
            return original_draw_on(self, canv, x, y, _sW)
        finally:
            origins.pop()

    def show_page(self):
        page[0] += 1
        return original_show_page(self)

    Table.draw = draw
    Flowable.drawOn = draw_on
    rl_canvas.Canvas.showPage = show_page
    try:
        pdf = docbuild.render_pdf(blocks, landscape=False, cn_pref="msyh")
    finally:
        Table.draw = original_draw
        Flowable.drawOn = original_draw_on
        rl_canvas.Canvas.showPage = original_show_page
    return pdf, captured, (float(A4[0]), float(A4[1]))


def generic_identities(experiment) -> list[TableIdentity | None]:
    """Identities for config-driven sheets, in record-sheet block order."""
    queue: list[TableIdentity | None] = []
    for method in experiment.config["methods"]:
        method_id = method["id"]
        if method.get("params"):
            queue.append(TableIdentity(
                label=f"{method_id}.params",
                grid=(tuple(f"{method_id}.params.{p['key']}" for p in method["params"]),),
            ))
        queue.append(TableIdentity(
            label=f"{method_id}.rows",
            base_columns=tuple((f"{method_id}.rows.row_", c["key"]) for c in method["columns"]),
            rows_total=method.get("rowCount"),
        ))
    return queue


# The two hand-built record sheets (record_clean.py) are calibrated with
# explicit displayed grids.  ``None`` entries are cells that carry no confirmed
# value: 序号/次数 prefills, derived columns such as Δx or Δx/Δt, and narrative
# observation cells.
_POLARIZATION_TABLES: list[TableIdentity | None] = [
    # 实验一 马吕斯定律：θ 与 cos²θ 预填，手写列为 P2 左旋(度/分)、右旋(度/分)、I左旋、I右旋
    TableIdentity(
        label="malus.rows",
        grid=tuple(
            (None, None, None, None, None, None,
             ("malus.rows.row_", "i_left"), ("malus.rows.row_", "i_right"))
            for _ in range(10)
        ),
    ),
    # 实验二 λ/2 波片：初始消光位置（C 度/分、P2 度/分）
    TableIdentity(
        label="halfwave.initial",
        grid=(
            (None, "halfwave.initial.c_deg", "halfwave.initial.c_min"),
            (None, "halfwave.initial.p2_deg", "halfwave.initial.p2_min"),
        ),
    ),
    # 实验二 λ/2 波片：逐次读数（序号与 C偏移 预填）
    TableIdentity(
        label="halfwave.rows",
        grid=tuple(
            (None, None, ("halfwave.rows.row_", "c_deg"), ("halfwave.rows.row_", "c_min"),
             ("halfwave.rows.row_", "p2_deg"), ("halfwave.rows.row_", "p2_min"))
            for _ in range(6)
        ),
    ),
    # 实验三 λ/4 波片：P2/C′ 消光位置等为定性记录，不对应确认字段
    None,
    # 实验三 λ/4 波片：36 组 φ-I 以 3 组并排印出，6 行 × 3 组
    TableIdentity(
        label="quarterwave.rows",
        groups=3,
        grid=tuple(
            (("quarterwave.rows.row_", "phi"), ("quarterwave.rows.row_", "i_raw"),
             ("quarterwave.rows.row_", "phi"), ("quarterwave.rows.row_", "i_raw"),
             ("quarterwave.rows.row_", "phi"), ("quarterwave.rows.row_", "i_raw"))
            for _ in range(12)
        ),
    ),
    None,   # 实验四（选做）：双折射观察记录
    None,   # 实验四（选做）：光斑偏振方向检验
    None,   # 实验五（选做）：波片鉴别
    # 实验六（选做）：圆偏振光，P2/I_raw/I_corr 两组并排，6 行 × 2 组
    TableIdentity(
        label="circular.rows",
        groups=2,
        grid=tuple(
            (("circular.rows.row_", "angle"), ("circular.rows.row_", "i_raw"),
             ("circular.rows.row_", "angle"), ("circular.rows.row_", "i_raw"))
            for _ in range(6)
        ),
    ),
]

_SOUNDLIGHT_TABLES: list[TableIdentity | None] = [
    # 表 1-1：同一张 12 行表，左列空气共振法、右列水中相位法
    TableIdentity(
        label="air_resonance+water_phase",
        grid=tuple((None, ("air_resonance.rows.row_", "l"), ("water_phase.rows.row_", "l"))
                   for _ in range(12)),
    ),
    # 实验二 时差法表（次数预填）
    TableIdentity(
        label="tof.rows",
        grid=tuple((None, ("tof.rows.row_", "L"), ("tof.rows.row_", "T")) for _ in range(12)),
    ),
    # 表 2-1：差频周期测量（次数预填，格子数为中间量）
    TableIdentity(
        label="light_sine.T",
        grid=tuple((None, None, ("light_sine.rows.row_", "T")) for _ in range(3)),
    ),
    # 表 2-2：相位移动 Δt 与滑块位移 Δx（方格数、Δx、Δx/Δt 为派生/中间量）
    TableIdentity(
        label="light_sine.dt",
        grid=tuple(
            (None, None, ("light_sine.rows.row_", "dt"), ("light_sine.rows.row_", "x1"),
             ("light_sine.rows.row_", "x2"), None, None)
            for _ in range(3)
        ),
    ),
    # 表 2-3：李萨如图形法（Δx 为派生量）
    TableIdentity(
        label="light_lissajous.rows",
        grid=tuple((None, ("light_lissajous.rows.row_", "x1"), ("light_lissajous.rows.row_", "x2"), None)
                   for _ in range(3)),
    ),
    None,   # 方波选做（第 2 页，单张上传图片无法覆盖）
    None,   # 方波选做相位表（第 2 页）
]


def identities_for(experiment, table_count: int) -> list[TableIdentity | None]:
    if experiment.id == "sound-light":
        base: list[TableIdentity | None] = _SOUNDLIGHT_TABLES
    elif experiment.id == "polarization":
        base = _POLARIZATION_TABLES
    else:
        return generic_identities(experiment)
    return base[:table_count] + [None] * max(0, table_count - len(base))


def _cell_has_text(cell: Any) -> bool:
    if isinstance(cell, dict):
        return bool(str(cell.get("text", "")).strip())
    return bool(str(cell).strip())


def render_page_image(pdf: bytes, page_index: int = 0) -> "np.ndarray":
    """Rasterise one PDF page into the canonical table coordinate system."""
    import cv2
    import numpy as np
    import pymupdf

    document = pymupdf.open(stream=pdf, filetype="pdf")
    page = document[page_index]
    zoom = REFERENCE_SIZE[0] / page.rect.width
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width).copy()
    return cv2.resize(image, REFERENCE_SIZE, interpolation=cv2.INTER_AREA)


def _best_offset(expected: list[float], detected: list[int], tolerance: float = 4.0,
                 limit: int = 40) -> tuple[float, float]:
    """Shift that best aligns captured line positions with the painted lines."""
    if not expected or not detected:
        return 0.0, 0.0
    best = (0.0, -1)
    for shift in range(-limit, limit + 1):
        hits = sum(any(abs(value + shift - line) <= tolerance for line in detected) for value in expected)
        if hits > best[1] or (hits == best[1] and abs(shift) < abs(best[0])):
            best = (float(shift), hits)
    return best


def measure_offset(
    captured: list[CapturedTable],
    page_size: tuple[float, float],
    image: np.ndarray,
) -> tuple[tuple[float, float], float, int, int]:
    """Align the captured table geometry with the rasterised template page.

    ``Flowable.drawOn`` hands out a frame-relative origin while the canvas paints
    at absolute coordinates, so the raw capture can sit a few points away from
    the printed rules.  Measuring that shift against the raster keeps the frozen
    layout honest: the residual match ratio is reported, and calibration refuses
    to write a layout whose geometry cannot be reproduced on the page.
    """
    from .segment import grid_lines

    width, height = REFERENCE_SIZE
    page_width, page_height = page_size
    scale_x, scale_y = width / page_width, height / page_height
    captured_x: list[float] = []
    captured_y: list[float] = []
    for table in captured:
        if table.page != 0:
            continue
        captured_x.extend((table.origin[0] + position) * scale_x for position in table.col_positions)
        captured_y.extend((page_height - (table.origin[1] + position)) * scale_y
                          for position in table.row_positions)
    detected_x, detected_y = grid_lines(image)
    shift_x, hit_x = _best_offset(captured_x, detected_x)
    shift_y, hit_y = _best_offset(captured_y, detected_y)
    total = len(captured_x) + len(captured_y)
    residual = (hit_x + hit_y) / total if total else 0.0
    return (shift_x, shift_y), residual, total, hit_x + hit_y


def calibrate(experiment) -> tuple[dict[str, Any], dict[str, Any]]:
    """Calibrate one experiment into a layout document plus coverage statistics."""
    from app.data_collection import valid_stable_field_id

    blocks = record_sheet_blocks(experiment)
    pdf, captured, page_size = capture_tables(_render_blocks(experiment, blocks))
    table_blocks = [block for block in blocks if block.get("kind") == "table"]
    if len(table_blocks) != len(captured):
        raise RuntimeError(
            f"{experiment.id}: rendered {len(captured)} tables for {len(table_blocks)} table blocks"
        )
    identities = identities_for(experiment, len(table_blocks))
    offset, residual, total_lines, matched_lines = measure_offset(captured, page_size, render_page_image(pdf))
    if residual < 0.75:
        raise RuntimeError(
            f"{experiment.id}: captured geometry only matches {residual:.2f} of the rendered lines"
        )

    fields: dict[str, dict[str, Any]] = {}
    anchors: list[list[float]] = []
    scale_x = REFERENCE_SIZE[0] / page_size[0]
    scale_y = REFERENCE_SIZE[1] / page_size[1]
    lattice_x: set[float] = set()
    lattice_y: set[float] = set()
    unmapped_pages: list[int] = []
    stats: dict[str, Any] = {
        "tables": len(captured), "calibrated_tables": 0, "unmapped_tables": 0,
        "calibrated_fields": 0, "prefilled_cells": 0, "unmapped_cells": 0,
        "invalid_field_ids": 0, "tiny_cells": 0, "unreachable_pages": [],
    }

    for block, table, identity in zip(table_blocks, captured, identities):
        adapted = _adapt(identity, block["rows"])
        cells = block["rows"]
        if table.page != 0:
            # One collection session stores a single image, so a field drawn on
            # a later page can never be traced back to the uploaded page.
            stats["unmapped_tables"] += 1
            unmapped_pages.append(table.page + 1)
            stats["unmapped_cells"] += sum(len(row) for row in cells[1:])
            continue
        # Registration reference: every printed line of this page.  An upload
        # whose lines cannot be explained by this lattice, or which the 180°
        # rotation explains better, never reaches the training set.
        for position in table.col_positions:
            lattice_x.add(round(((table.origin[0] + position) * scale_x + offset[0])
                                 / REFERENCE_SIZE[0], 5))
        for position in table.row_positions:
            lattice_y.add(round(((page_size[1] - (table.origin[1] + position)) * scale_y + offset[1])
                                 / REFERENCE_SIZE[1], 5))
        if adapted is None:
            stats["unmapped_tables"] += 1
            stats["unmapped_cells"] += sum(len(row) for row in cells[1:])
            continue
        stats["calibrated_tables"] += 1
        anchors.append(_relative(table.frame_px(REFERENCE_SIZE, page_size, offset)))
        for row_index in range(1, len(cells)):
            for column_index in range(len(cells[row_index])):
                if _cell_has_text(cells[row_index][column_index]):
                    # The blank sheet already prints this value, so the cell is
                    # not a handwriting target and must not become a label crop.
                    stats["prefilled_cells"] += 1
                    continue
                field_id = adapted.field_id(row_index - 1, column_index)
                if field_id is None:
                    stats["unmapped_cells"] += 1
                    continue
                if not valid_stable_field_id(experiment.id, field_id):
                    stats["invalid_field_ids"] += 1
                    continue
                x1, y1, x2, y2 = table.cell_px(row_index, column_index, REFERENCE_SIZE, page_size, offset)
                if x2 - x1 < 14 or y2 - y1 < 14:
                    stats["tiny_cells"] += 1
                    continue
                if field_id in fields:
                    raise RuntimeError(f"{experiment.id}: duplicate calibrated ROI for {field_id}")
                fields[field_id] = {
                    "x1": round(x1 / REFERENCE_SIZE[0], 5),
                    "y1": round(y1 / REFERENCE_SIZE[1], 5),
                    "x2": round(x2 / REFERENCE_SIZE[0], 5),
                    "y2": round(y2 / REFERENCE_SIZE[1], 5),
                    "page": 1,
                    "confidence": CALIBRATION_CONFIDENCE,
                }
                stats["calibrated_fields"] += 1

    stats["unreachable_pages"] = sorted(set(unmapped_pages))
    stats["raster_match_ratio"] = round(residual, 4)
    stats["raster_offset_px"] = [round(offset[0], 1), round(offset[1], 1)]
    stats["matched_lines"] = f"{matched_lines}/{total_lines}"
    existing = load_existing_layout(experiment.id)
    layout = {
        "schema_version": "2.0",
        "experiment_id": experiment.id,
        "template_version": existing.get("template_version", "2.0"),
        "reference_size": list(REFERENCE_SIZE),
        "capture_scope": "calibrated_page_1",
        "source": {
            "kind": "record_sheet_pdf",
            "page": 1,
            "page_size_pt": [round(page_size[0], 2), round(page_size[1], 2)],
            "renderer": "docbuild.render_pdf(landscape=False, cn_pref='msyh')",
            "raster_match_ratio": round(residual, 4),
            "raster_offset_px": [round(offset[0], 1), round(offset[1], 1)],
        },
        "fields": {key: fields[key] for key in sorted(fields)},
        "anchors": [list(anchor) for anchor in anchors],
        "lattice": {"x": sorted(lattice_x), "y": sorted(lattice_y)},
        "tables": existing.get("tables", []),
    }
    return layout, stats


def layouts_root() -> Path:
    return Path(__file__).with_name("layouts")


def load_existing_layout(experiment_id: str, root: Path | None = None) -> dict[str, Any]:
    path = (root or layouts_root()) / f"{experiment_id}.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_layout(layout: dict[str, Any], root: Path | None = None) -> Path:
    path = (root or layouts_root()) / f"{layout['experiment_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def public_experiment_ids() -> list[str]:
    from experiments.core.registry import PUBLIC_EXPERIMENT_IDS

    return list(PUBLIC_EXPERIMENT_IDS)


def _relative(box: Iterable[float]) -> list[float]:
    x1, y1, x2, y2 = box
    return [round(x1 / REFERENCE_SIZE[0], 5), round(y1 / REFERENCE_SIZE[1], 5),
            round(x2 / REFERENCE_SIZE[0], 5), round(y2 / REFERENCE_SIZE[1], 5)]


def _pixels(box: Iterable[float], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    if x2 <= 1.0 and y2 <= 1.0 and x1 < 1.0 and y1 < 1.0:
        return (int(round(x1 * width)), int(round(y1 * height)),
                int(round(x2 * width)), int(round(y2 * height)))
    return int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))


def overlay_png(layout: dict[str, Any], pdf: bytes, *, limit: int = 500) -> bytes:
    """Draw the calibrated ROIs on page 1 so a human can review the alignment."""
    import cv2
    import numpy as np
    import pymupdf

    document = pymupdf.open(stream=pdf, filetype="pdf")
    page = document[0]
    zoom = REFERENCE_SIZE[0] / page.rect.width
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width).copy()
    canvas = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    height, width = image.shape[:2]
    for anchor in layout["anchors"]:
        x1, y1, x2, y2 = _pixels(anchor, width, height)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (200, 120, 0), 2)
    for spec in list(layout["fields"].values())[:limit]:
        x1, y1, x2, y2 = _pixels((spec["x1"], spec["y1"], spec["x2"], spec["y2"]), width, height)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 0, 255), 1)
    ok, buffer = cv2.imencode(".png", canvas)
    if not ok:
        raise RuntimeError("failed to encode overlay")
    return buffer.tobytes()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--overlay", type=Path, default=None)
    parser.add_argument("--layouts-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    from experiments.core.registry import registry

    ids = args.experiment or (public_experiment_ids() if args.all else [])
    if not ids:
        parser.error("pass --experiment <id> or --all")

    report: dict[str, Any] = {}
    for experiment_id in ids:
        experiment = registry.get(experiment_id)
        layout, stats = calibrate(experiment)
        report[experiment_id] = stats
        if args.write:
            write_layout(layout, args.layouts_dir)
        if args.overlay:
            blocks = record_sheet_blocks(experiment)
            pdf, _, _ = capture_tables(_render_blocks(experiment, blocks))
            args.overlay.mkdir(parents=True, exist_ok=True)
            (args.overlay / f"{experiment_id}_page1.png").write_bytes(overlay_png(layout, pdf))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
