"""OCR recognition and explicitly consented feedback API glue."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.models import OCRFeedbackRequest


router = APIRouter()


@router.post("/api/ocr/table")
async def recognize_table_image(
    image: UploadFile = File(...),
    experiment_id: str = Form(""),
    table_id: str = Form(""),
):
    from app.ocr_service import (
        InvalidOCRImage,
        MAX_IMAGE_BYTES,
        OCRUnavailable,
        recognize_numeric_candidates,
    )
    if image.content_type and image.content_type not in {
        "image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff",
    }:
        raise HTTPException(status_code=415, detail="请上传 JPG、PNG、WebP、BMP 或 TIFF 图片")
    content = await image.read(MAX_IMAGE_BYTES + 1)
    try:
        result = await run_in_threadpool(recognize_numeric_candidates, content)
    except InvalidOCRImage as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OCRUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR 识别失败：{exc}") from exc
    return {"status": "success", "experiment_id": experiment_id,
            "table_id": table_id, **result}


@router.post("/api/ocr/feedback")
async def submit_ocr_feedback(req: OCRFeedbackRequest):
    from app.telemetry import record_ocr_feedback
    return record_ocr_feedback(req.model_dump())
