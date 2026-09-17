"""Structural regression tests for editable Word and printable PDF output.

Fixtures are synthetic and only validate the document pipeline and formulas.
They are not evidence that complete real experimental data has passed.
"""

import io
import math
import zipfile

import fitz
import pytest

from experiments import record_clean
from experiments.polarization import docbuild
from experiments.soundlight import docs


pytestmark = pytest.mark.document


def _sound_fixture():
    phase = {
        "T": [2.19, 2.20, 2.21],
        "dt": [0.8, 1.0, 1.2],
        "x1": [100.0, 100.0, 100.0],
        "x2": [463.36, 554.20, 645.04],
    }
    return {
        "air_resonance": {
            "rows": {"l": [10.0 + i * 4.5 for i in range(12)]},
            "params": {"temperature_degC": 25.0, "f_khz": 38.0},
        },
        "water_phase": {
            "rows": {"l": [20.0 + i * 0.75 for i in range(12)]},
            "params": {"f_mhz": 1.0},
        },
        "light_sine": {"rows": phase, "params": {"f_mhz": 150.0}},
        "light_square": {"rows": phase, "params": {"f_mhz": 150.0}},
        "light_lissajous": {
            "rows": {"x1": [100.0, 120.0, 140.0],
                     "x2": [599.67, 619.67, 639.67]},
            "params": {"f_mhz": 150.0},
        },
    }


def _polarization_fixture():
    bg = 0.05
    malus = []
    for theta in range(90, -1, -10):
        intensity = 100.0 * math.cos(math.radians(theta)) ** 2 + bg
        malus.append({"theta": theta, "i_left": intensity,
                      "i_right": intensity + 0.2})
    halfwave = {
        "initial": {"c_deg": 10, "c_min": 0, "p2_deg": 20, "p2_min": 0},
        "rows": [{"offset": i * 10, "c_deg": 10 + i * 10, "c_min": 0,
                  "p2_deg": 20 + i * 20, "p2_min": 0} for i in range(6)],
    }
    quarterwave = []
    for phi in range(0, 360, 10):
        intensity = 144 * (0.25 * math.sin(math.radians(phi)) ** 2
                           + 0.75 * math.cos(math.radians(phi)) ** 2) + bg
        quarterwave.append({"phi": phi, "i_raw": intensity})
    circular = [{"angle": phi, "i_raw": 72.0 + 0.2 * math.sin(math.radians(phi))}
                for phi in range(0, 360, 10)]
    return {
        "malus": {"rows": malus},
        "halfwave": halfwave,
        "quarterwave": {"rows": quarterwave},
        "circular": {"rows": circular},
    }, bg


def _assert_docx(data, minimum_tables):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        xml = archive.read("word/document.xml").decode("utf-8")
    assert xml.count("<w:tbl>") >= minimum_tables
    assert "w:cantSplit" in xml
    assert "w:keepNext" in xml
    assert "�" not in xml


def _assert_pdf(data, minimum_pages=1):
    pdf = fitz.open(stream=data, filetype="pdf")
    assert len(pdf) >= minimum_pages
    for page in pdf:
        assert math.isclose(page.rect.width, 595.28, abs_tol=0.2)
        assert math.isclose(page.rect.height, 841.89, abs_tol=0.2)
        text = page.get_text()
        # Display equations are deliberately rendered as high-resolution images.
        # An equation-only continuation page is therefore valid PDF content even
        # though its text extraction is empty.
        assert len(text.strip()) >= 20 or page.get_images(full=True)
        assert "�" not in text and "\x00" not in text
    font_names = {font[3] for page in pdf for font in page.get_fonts(full=True)}
    # Windows embeds 微软雅黑/宋体; the Linux image falls back to WenQuanYi
    # (Noto CJK is CFF-outline, which reportlab cannot embed).
    assert any("MicrosoftYaHei" in name or "SimSun" in name
               or "WenQuanYi" in name
               for name in font_names)


@pytest.mark.parametrize(("experiment", "minimum_tables"), [
    ("polarization", 9),
    ("sound-light", 7),
])
def test_blank_record_sheets_are_editable_and_printable(experiment, minimum_tables):
    _assert_docx(record_clean.record_bytes(experiment, "docx"), minimum_tables)
    _assert_pdf(record_clean.record_bytes(experiment, "pdf"), minimum_pages=2)


def _assert_four_section_blocks(blocks):
    assert not any(block["kind"] in ("h1", "sub") for block in blocks)
    breaks = [i for i, block in enumerate(blocks) if block["kind"] == "pagebreak"]
    assert len(breaks) == 3
    first = blocks[:breaks[0]]
    second = blocks[breaks[0] + 1:breaks[1]]
    third = blocks[breaks[1] + 1:breaks[2]]
    fourth = blocks[breaks[2] + 1:]
    assert first and all(block["kind"] in ("h3", "table", "spacer") for block in first)
    assert second and all(block["kind"] in ("h3", "image", "spacer") for block in second)
    assert third[0]["text"].startswith("第三部分")
    assert fourth[0]["text"].startswith("第四部分")
    assert any(block["kind"] == "equation" for block in third)
    assert not any(block["kind"] in ("table", "image") for block in third + fourth)
    for index, block in enumerate(first):
        if block["kind"] == "table":
            assert first[index - 1]["kind"] == "h3"
            assert first[index - 1]["text"].startswith("表 ")
    for index, block in enumerate(second):
        if block["kind"] == "image":
            assert second[index - 1]["kind"] == "h3"
            assert second[index - 1]["text"].startswith("图 ")


def _assert_report_docx(data):
    _assert_docx(data, minimum_tables=8)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    assert xml.count('w:type="page"') >= 3
    assert "数据处理报告（基准部分）" not in xml
    assert "数据处理报告（拓展部分）" not in xml


def test_sound_unified_report_has_four_isolated_sections_and_square_method():
    fixture = _sound_fixture()
    blocks = docs.report_blocks(fixture)
    _assert_four_section_blocks(blocks)
    docx = docs.report_bytes(fixture, "docx")
    pdf = docs.report_bytes(fixture, "pdf")
    _assert_report_docx(docx)
    _assert_pdf(pdf, minimum_pages=8)
    text = "".join(page.get_text() for page in fitz.open(stream=pdf, filetype="pdf"))
    assert "相位差法（方波）" in text
    assert "测量与数据处理正确" not in text
    assert "结果可信" not in text
    assert "是否符合实验要求需结合原始记录" in text


def test_polarization_unified_report_has_four_isolated_sections():
    fixture, bg = _polarization_fixture()
    run = docbuild.analyze(fixture, bg_uw=bg, theta_qwp=30.0)
    blocks = docbuild.report_blocks(run, fixture)
    _assert_four_section_blocks(blocks)
    docx = docbuild.report_bytes(fixture, bg_uw=bg, theta_qwp=30.0, fmt="docx")
    pdf = docbuild.report_bytes(fixture, bg_uw=bg, theta_qwp=30.0, fmt="pdf")
    _assert_report_docx(docx)
    _assert_pdf(pdf, minimum_pages=8)
    text = "".join(page.get_text() for page in fitz.open(stream=pdf, filetype="pdf"))
    assert "第三部分" in text and "第四部分" in text
    assert "理论 100" not in text
    assert "是否满足真实实验要求" in text
