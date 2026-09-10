"""Generate the complete synthetic report set for print-layout QA.

The generated numbers are fixtures only.  They exercise the report pipeline
and do not establish correctness for complete real experimental records.
"""

from __future__ import annotations

import io
import json
import math
import re
import sys
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from tests.test_documents import _polarization_fixture, _sound_fixture
from tests.test_general_experiments import fixtures as general_fixtures
from experiments.general import docs as general_docs
from experiments.general.engine import process_experiment
from experiments.polarization import docbuild as polarization_docs
from experiments.soundlight import docs as sound_docs
from experiments.soundlight import engine as sound_engine


def main() -> None:
    out = ROOT / "artifacts" / "simulation-reports"
    out.mkdir(parents=True, exist_ok=True)
    reports = {}

    polarization, bg = _polarization_fixture()
    reports["polarization"] = {
        "docx": polarization_docs.report_bytes(polarization, bg_uw=bg, theta_qwp=30.0, fmt="docx"),
        "pdf": polarization_docs.report_bytes(polarization, bg_uw=bg, theta_qwp=30.0, fmt="pdf"),
    }
    sound = _sound_fixture()
    reports["sound-light"] = {
        "docx": sound_docs.report_bytes(sound, "docx"),
        "pdf": sound_docs.report_bytes(sound, "pdf"),
    }
    result_summary = {
        "polarization": polarization_docs.analyze(polarization, bg_uw=bg, theta_qwp=30.0)["r"],
        "sound-light": {method_id: sound_engine.analyze(method_id, payload["rows"], payload["params"])
                        for method_id, payload in sound.items()},
    }
    for experiment_id, data in general_fixtures().items():
        result_summary[experiment_id] = process_experiment(experiment_id, data)
        reports[experiment_id] = {
            "docx": general_docs.report_bytes(experiment_id, data, "docx"),
            "pdf": general_docs.report_bytes(experiment_id, data, "pdf"),
        }

    manifest = {"validation_boundary": "synthetic fixtures and unit tests only; not complete real-data validation", "reports": {}}
    thumbnails = []
    for experiment_id, artifacts in reports.items():
        paths = {}
        pdf = fitz.open(stream=artifacts["pdf"], filetype="pdf")
        pdf_path = out / f"{experiment_id}.pdf"
        docx_path = out / f"{experiment_id}.docx"
        pdf_path.write_bytes(artifacts["pdf"])
        docx_path.write_bytes(artifacts["docx"])
        section_pages = {}
        for page_no, page in enumerate(pdf, start=1):
            text = page.get_text()
            for marker in ("第三部分", "第四部分"):
                if marker in text:
                    section_pages[marker] = page_no
            assert "�" not in text and "\x00" not in text
            assert approx(page.rect.width, 595.28, 0.2)
            assert approx(page.rect.height, 841.89, 0.2)
            pix = page.get_pixmap(matrix=fitz.Matrix(0.42, 0.42), alpha=False)
            thumbnails.append((experiment_id, page_no, Image.frombytes("RGB", [pix.width, pix.height], pix.samples).resize((250, 354))))
        assert section_pages.get("第三部分") and section_pages.get("第四部分")
        first_section_end = section_pages["第三部分"] - 1
        second_section_end = section_pages["第三部分"] - 1
        for page_no, page in enumerate(pdf, start=1):
            text = page.get_text()
            if page_no <= first_section_end and page.get_drawings():
                assert re.search(r"表\s+\d+", text), f"table continuation or missing caption: {experiment_id} p{page_no}"
            if first_section_end < page_no <= second_section_end and page.get_images(full=True):
                assert re.search(r"图\s+\d+", text), f"figure missing caption: {experiment_id} p{page_no}"
        manifest["reports"][experiment_id] = {
            "pdf": str(pdf_path), "docx": str(docx_path),
            "pdf_pages": len(pdf), "section_start_pages": section_pages,
        }

    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "results.json").write_text(
        json.dumps(result_summary, ensure_ascii=False, indent=2,
                   default=lambda value: value.tolist() if hasattr(value, "tolist") else str(value)),
        encoding="utf-8",
    )
    columns = 5
    sheet = Image.new("RGB", (columns * 250, ((len(thumbnails) + columns - 1) // columns) * 380), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (experiment_id, page_no, image) in enumerate(thumbnails):
        x = (index % columns) * 250
        y = (index // columns) * 380
        draw.text((x + 4, y + 4), f"{experiment_id} p{page_no}", fill="black")
        sheet.paste(image, (x, y + 24))
    sheet.save(out / "contact-sheet.png")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def approx(value: float, expected: float, tolerance: float) -> bool:
    return abs(value - expected) <= tolerance


if __name__ == "__main__":
    main()
