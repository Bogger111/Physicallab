"""Optional consent-first record-sheet collection API glue."""

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.models import CollectionCommitRequest
from experiments.core.registry import PUBLIC_EXPERIMENT_IDS


router = APIRouter()


@router.get("/api/data-collection/status")
async def data_collection_status():
    from app.data_collection import TEMPLATE_VERSION, collection_enabled
    return {"enabled": collection_enabled(), "template_version": TEMPLATE_VERSION}


@router.post("/api/data-collection/sessions")
async def create_data_collection_session(
    image: UploadFile = File(...),
    experiment_id: str = Form(...),
    template_version: str = Form("2.0"),
    consent: bool = Form(False),
):
    from app.data_collection import (
        ALLOWED_IMAGE_TYPES,
        MAX_COLLECTION_IMAGE_BYTES,
        CollectionValidationError,
        collection_enabled,
        local_storage,
        sanitize_record_image,
        validate_template_version,
    )
    if not collection_enabled():
        raise HTTPException(status_code=404, detail="数据贡献功能未启用")
    if consent is not True:
        raise HTTPException(status_code=400, detail="只有明确同意后才会保存记录表")
    if experiment_id not in PUBLIC_EXPERIMENT_IDS:
        raise HTTPException(status_code=400, detail="实验不存在或未公开")
    if image.content_type and image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="请上传 JPG、PNG、WebP、BMP 或 TIFF 图片")
    content = await image.read(MAX_COLLECTION_IMAGE_BYTES + 1)
    try:
        version = validate_template_version(template_version)
        sanitized = await run_in_threadpool(sanitize_record_image, content)
        metadata = await run_in_threadpool(
            local_storage().create_session,
            experiment_id=experiment_id,
            template_version=version,
            image=sanitized,
        )
    except CollectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="记录表贡献暂时不可用，不影响报告生成") from exc
    from app.collection_stats import estimate_samples, experiment_name

    return {"status": "pending_confirmation", "session_id": metadata["session_id"],
            "revision": metadata["revision"],
            "experiment_id": experiment_id,
            "experiment_name": experiment_name(experiment_id),
            # Upper bound: every cell of this experiment's record sheet the
            # template knows about. The exact number follows the confirmed values.
            "estimated_samples": estimate_samples(experiment_id)}


@router.post("/api/data-collection/sessions/{session_id}/commit")
async def commit_data_collection_session(session_id: str, req: CollectionCommitRequest):
    from app.data_collection import (
        CollectionNotFoundError,
        CollectionValidationError,
        collection_enabled,
        local_storage,
        normalize_confirmed_fields,
        validate_template_version,
    )
    if not collection_enabled():
        raise HTTPException(status_code=404, detail="数据贡献功能未启用")
    if req.consent is not True:
        raise HTTPException(status_code=400, detail="只有明确同意后才会保存确认数据")
    if req.experiment_id not in PUBLIC_EXPERIMENT_IDS:
        raise HTTPException(status_code=400, detail="实验不存在或未公开")
    try:
        version = validate_template_version(req.template_version)
        fields = normalize_confirmed_fields(req.experiment_id, req.confirmed_data)
        metadata = await run_in_threadpool(
            local_storage().commit_session,
            session_id=session_id,
            experiment_id=req.experiment_id,
            template_version=version,
            fields=fields,
        )
    except CollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CollectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="确认数据暂时无法保存，不影响报告生成") from exc
    from app.collection_stats import estimate_samples, experiment_name

    return {"status": metadata["status"], "session_id": metadata["session_id"],
            "revision": metadata["revision"], "field_count": len(metadata["fields"]),
            "experiment_id": req.experiment_id,
            "experiment_name": experiment_name(req.experiment_id),
            "estimated_samples": estimate_samples(req.experiment_id, metadata["fields"])}


@router.post("/api/data-collection/sessions/{session_id}/build-ocr")
async def build_ocr_dataset(session_id: str):
    """Turn one confirmed session into a PhysLab_OCR compatible dataset.

    Template-driven OpenCV cropping only: no generic text detection, no model
    training here.  Samples that cannot be mapped to a stable field id with high
    confidence are rejected (or queued for review) instead of entering the set.
    """
    from app.data_collection import (
        CollectionNotFoundError,
        CollectionValidationError,
        collection_enabled,
        local_storage,
    )
    from ocr_dataset.builder import BuilderError, build_session_dataset

    if not collection_enabled():
        raise HTTPException(status_code=404, detail="数据贡献功能未启用")
    try:
        outcome = await run_in_threadpool(
            build_session_dataset, session_id, storage=local_storage(),
        )
    except CollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BuilderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CollectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"实验模板不可用：{exc}") from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="数据集导出暂时不可用") from exc
    return outcome.as_api_payload()


@router.get("/api/data-collection/stats")
async def data_collection_stats(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    """Contributor statistics for the developer dashboard.

    Never public: a configured ``PHYSICSLAB_ADMIN_KEY`` must be presented in the
    ``X-Admin-Key`` header, and only when no key is configured does
    ``PHYSICSLAB_DEV_MODE=true`` open it for local development.  Otherwise the
    endpoint behaves as if it did not exist.
    """
    from app.collection_stats import collection_stats, stats_allowed
    from app.data_collection import collection_enabled, collection_root

    if not collection_enabled() or not stats_allowed(x_admin_key):
        raise HTTPException(status_code=404, detail="Not Found")
    try:
        return await run_in_threadpool(collection_stats, collection_root())
    except OSError as exc:
        raise HTTPException(status_code=503, detail="统计数据暂时不可用") from exc


@router.delete("/api/data-collection/sessions/{session_id}")
async def delete_data_collection_session(session_id: str):
    from app.data_collection import (
        CollectionNotFoundError,
        CollectionValidationError,
        collection_enabled,
        local_storage,
    )
    if not collection_enabled():
        raise HTTPException(status_code=404, detail="数据贡献功能未启用")
    try:
        await run_in_threadpool(local_storage().delete_session, session_id)
    except CollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CollectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="暂时无法删除数据贡献会话") from exc
    return {"status": "deleted"}
