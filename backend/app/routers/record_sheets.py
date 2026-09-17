"""Blank record-sheet endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from app.http import attachment
from app.routers._helpers import experiment_or_404
from experiments.core.registry import registry


router = APIRouter()
BACKEND_ROOT = Path(__file__).resolve().parents[2]
RECORD_SHEETS_DIR = BACKEND_ROOT / "record-sheets"
if not RECORD_SHEETS_DIR.exists():
    alternative = BACKEND_ROOT.parent / "frontend" / "public" / "record-sheets"
    if alternative.exists():
        RECORD_SHEETS_DIR = alternative


def _response(content: bytes, filename: str, fmt: str) -> Response:
    mime = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if fmt == "docx" else "application/pdf")
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": attachment(filename)})


@router.get("/api/record-sheets/polarization")
async def get_polarization_record_sheet():
    pdf_path = RECORD_SHEETS_DIR / "polarization_lab.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="记录表文件未找到")
    return FileResponse(path=str(pdf_path), media_type="application/pdf",
                        filename="偏振光实验数据记录表.pdf")


@router.get("/api/record-sheets/polarization.docx")
async def get_polarization_record_sheet_docx():
    content = registry.get("polarization").build_record_sheet("docx")
    return _response(content, "偏振光与双折射实验-数据记录表.docx", "docx")


@router.get("/api/record-sheets/polarization.pdf")
async def get_polarization_record_sheet_pdf():
    content = registry.get("polarization").build_record_sheet("pdf")
    return _response(content, "偏振光与双折射实验-数据记录表.pdf", "pdf")


@router.get("/api/record-sheets/sound-light.docx")
async def get_soundlight_record_sheet_docx():
    content = registry.get("sound-light").build_record_sheet("docx")
    return _response(content, "声速光速的测量-数据记录表.docx", "docx")


@router.get("/api/record-sheets/sound-light.pdf")
async def get_soundlight_record_sheet_pdf():
    content = registry.get("sound-light").build_record_sheet("pdf")
    return _response(content, "声速光速的测量-数据记录表.pdf", "pdf")


@router.get("/api/record-sheets/{experiment_id}.{fmt}")
async def get_experiment_record_sheet(experiment_id: str, fmt: str):
    experiment = experiment_or_404(experiment_id)
    if fmt not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="fmt 必须是 docx 或 pdf")
    content = experiment.build_record_sheet(fmt)
    return _response(content, f"{experiment.config['name']}-数据记录表.{fmt}", fmt)
