"""PhysicsLab FastAPI application composition root."""

from __future__ import annotations

import json
import math
import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.dev_env import load_local_env
from app.routers import analytics, data_collection, experiments, ocr, record_sheets, reports
from experiments.core.registry import PUBLIC_EXPERIMENT_IDS

#: Local development switches (backend/.env.local).  Existing environment
#: variables win, so production configuration is untouched.
load_local_env()


class SafeJSONResponse(JSONResponse):
    """Render non-finite numeric engine output as JSON null."""

    @classmethod
    def sanitize(cls, obj: Any) -> Any:
        if isinstance(obj, float):
            return obj if math.isfinite(obj) else None
        if isinstance(obj, dict):
            return {key: cls.sanitize(value) for key, value in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [cls.sanitize(value) for value in obj]
        return obj

    def render(self, content: Any) -> bytes:
        return json.dumps(
            self.sanitize(content),
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


class ErrorGuardMiddleware(BaseHTTPMiddleware):
    """Return readable JSON for unhandled errors while preserving CORS."""

    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:  # pragma: no cover - exercised by regression test
            return SafeJSONResponse(
                status_code=500,
                content={
                    "detail": "计算服务出现内部错误，请检查输入数据后重试；若持续出现请反馈。",
                    "error": type(exc).__name__,
                    "path": request.url.path,
                },
            )


APP_VERSION = "2.0.0-beta.1"

#: Deployed build identity: `GIT_COMMIT` is passed at deploy time and Cloud Run
#: injects `K_REVISION`; `/health` echoes both so a smoke test can prove which
#: code is answering instead of trusting a URL.
BUILD_COMMIT = os.environ.get("GIT_COMMIT", "unknown")
BUILD_REVISION = os.environ.get("K_REVISION", "local")

app = FastAPI(
    title="PhysicsLab API",
    version=APP_VERSION,
    default_response_class=SafeJSONResponse,
)
app.add_middleware(ErrorGuardMiddleware)

_default_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://bogger111.github.io",
]
_configured_cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[*_default_cors_origins, *_configured_cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data_collection.router)
app.include_router(ocr.router)
app.include_router(analytics.router)
app.include_router(experiments.router)
app.include_router(record_sheets.router)
app.include_router(reports.router)


@app.get("/")
async def root():
    return {"message": "PhysicsLab API", "version": APP_VERSION}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "physicslab-api", "version": APP_VERSION,
            "commit": BUILD_COMMIT, "revision": BUILD_REVISION,
            "experiments": len(PUBLIC_EXPERIMENT_IDS)}
