"""PhysicsLab FastAPI backend."""

import math
import os
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from typing import Optional, List, Dict, Any

# Reliable base paths
BACKEND_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent


class SafeJSONResponse(JSONResponse):
    """JSON response that tolerates non-finite floats from the numeric engines.

    The engines legitimately produce inf/-inf/nan for degenerate-but-real student
    data (e.g. an intensity reading equal to the background I0 makes the extinction
    ratio I_max/I_min infinite). Python's json emits those as the bare tokens
    Infinity/NaN unless allow_nan=False, and Starlette's JSONResponse passes
    allow_nan=False, so the whole response blew up with
    ``ValueError: Out of range float values are not JSON compliant`` -> an
    unhandled 500. Because that 500 is produced outside the CORS layer it carried
    no Access-Control-Allow-Origin header, so the browser reported it to the user
    as a bogus "网络错误，请确认后端服务已启动". Emit null instead.
    """

    @classmethod
    def sanitize(cls, obj: Any) -> Any:
        if isinstance(obj, float):  # numpy.float64 subclasses float, so this covers it
            return obj if math.isfinite(obj) else None
        if isinstance(obj, dict):
            return {k: cls.sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [cls.sanitize(v) for v in obj]
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
    """Turn any unhandled exception into a readable JSON 500.

    ``add_middleware`` order matters: this is registered *before* CORSMiddleware so
    CORS ends up outermost and still stamps the CORS headers onto the error reply.
    Without that, the browser hides the real error behind a CORS failure.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:  # pragma: no cover - exercised by the regression test
            return SafeJSONResponse(
                status_code=500,
                content={
                    "detail": "计算服务出现内部错误，请检查输入数据后重试；若持续出现请反馈。",
                    "error": type(exc).__name__,
                    "path": request.url.path,
                },
            )


app = FastAPI(
    title="PhysicsLab API",
    version="1.0.0",
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

# CORS for Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[*_default_cors_origins, *_configured_cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve record sheet PDFs
RECORD_SHEETS_DIR = BACKEND_ROOT / "record-sheets"
if not RECORD_SHEETS_DIR.exists():
    alt = BACKEND_ROOT.parent / "frontend" / "public" / "record-sheets"
    if alt.exists():
        RECORD_SHEETS_DIR = alt


# ─── Pydantic Models ────────────────────────────────────────

class DMSAngle(BaseModel):
    deg: float
    min: float = 0.0

class MalusRow(BaseModel):
    theta: float
    i_left: Optional[float] = None
    i_right: Optional[float] = None

class MalusData(BaseModel):
    rows: List[MalusRow]

class HalfWaveInitial(BaseModel):
    c_deg: Optional[float] = None
    c_min: float = 0.0
    p2_deg: Optional[float] = None
    p2_min: float = 0.0

class HalfWaveRow(BaseModel):
    offset: float
    c_deg: Optional[float] = None
    c_min: float = 0.0
    p2_deg: Optional[float] = None
    p2_min: float = 0.0

class HalfWaveData(BaseModel):
    initial: HalfWaveInitial
    rows: List[HalfWaveRow]

class QuarterWaveRow(BaseModel):
    phi: float
    i_raw: Optional[float] = None

class QuarterWaveData(BaseModel):
    rows: List[QuarterWaveRow]

class CircularRow(BaseModel):
    angle: float
    i_raw: Optional[float] = None

class CircularData(BaseModel):
    rows: List[CircularRow]

class ProcessRequest(BaseModel):
    bg_uw: float = 0.0
    theta_qwp: float = 30.0
    malus: Optional[MalusData] = None
    halfwave: Optional[HalfWaveData] = None
    quarterwave: Optional[QuarterWaveData] = None
    circular: Optional[CircularData] = None


# ─── Routes ──────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "PhysicsLab API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "physicslab-api", "version": "1.0.0"}


@app.get("/api/experiments")
async def list_experiments():
    """List all available experiments."""
    soundlight_config_path = BACKEND_ROOT / "experiments" / "soundlight" / "config.json"
    with soundlight_config_path.open(encoding="utf-8") as config_file:
        soundlight_methods = json.load(config_file)
    experiments = [
            {
                "id": "polarization",
                "name": "偏振光与双折射",
                "category": "光学",
                "description": "马吕斯定律验证、半波片/四分之一波片特性、圆偏振光分析",
                "sub_experiments": [
                    {"id": "malus", "name": "马吕斯定律", "required": True},
                    {"id": "halfwave", "name": "半波片", "required": True},
                    {"id": "quarterwave", "name": "四分之一波片", "required": True},
                    {"id": "circular", "name": "圆偏振光", "required": False},
                ],
                "measurements": [
                    {"key": "theta", "label": "角度 θ", "unit": "°"},
                    {"key": "intensity", "label": "光强 I", "unit": "μW"},
                    {"key": "phi", "label": "方位角 φ", "unit": "°"},
                ],
                "record_sheet": "/api/record-sheets/polarization",
                "processing_time": "~30秒",
            },
            {
                "id": "sound-light",
                "name": "声速光速的测量",
                "category": "波动",
                "description": "空气共振法、水中相位法、飞行时间法测声速；正弦、方波相位法与李萨如法测光速",
                "sub_experiments": [
                    {"id": method["id"], "name": method["name"],
                     "required": method["type"] == "required"}
                    for method in soundlight_methods
                ],
                "record_sheet": "/api/record-sheets/sound-light",
                "processing_time": "~1分钟",
            }
        ]
    from experiments.general.engine import CONFIGS
    experiments.extend({
        "id": config["id"],
        "name": config["name"],
        "category": config["category"],
        "description": config["description"],
        "sub_experiments": [
            {"id": method["id"], "name": method["name"],
             "required": method.get("required", False)}
            for method in config["methods"]
        ],
        "measurements": [
            {"key": f"measurement_{index}", "label": label, "unit": ""}
            for index, label in enumerate(config["measurements"], start=1)
        ],
        "record_sheet": f"/api/record-sheets/{config['id']}",
        "processing_time": config["processingTime"],
    } for config in CONFIGS)
    return {"experiments": experiments}


@app.get("/api/record-sheets/polarization")
async def get_polarization_record_sheet():
    """Download the polarization lab record sheet PDF."""
    pdf_path = RECORD_SHEETS_DIR / "polarization_lab.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="记录表文件未找到")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename="偏振光实验数据记录表.pdf",
    )


@app.post("/api/experiments/polarization/process")
async def process_polarization(req: ProcessRequest):
    """Process polarization experiment data and return results + plots."""
    from experiments.polarization.adapter import PolarizationAdapter

    adapter = PolarizationAdapter(bg_uw=req.bg_uw, theta_qwp=req.theta_qwp)

    data = {}
    validation_errors = []

    if req.malus:
        malus_dict = {'rows': [r.model_dump() for r in req.malus.rows]}
        # Validate
        for i, row in enumerate(req.malus.rows):
            if row.theta is None:
                validation_errors.append(f"马吕斯定律: 第 {i+1} 行角度数据为空")
            if row.i_left is None and row.i_right is None:
                validation_errors.append(f"马吕斯定律: 第 {i+1} 行光强数据为空")
        data['malus'] = malus_dict

    if req.halfwave:
        hw_dict = {
            'initial': req.halfwave.initial.model_dump(),
            'rows': [r.model_dump() for r in req.halfwave.rows],
        }
        # The entry table sends null for cells the student left blank; the engine cannot
        # subtract a missing baseline, so name the empty cell instead of failing later.
        missing_baseline = []
        if req.halfwave.initial.c_deg is None:
            missing_baseline.append("检偏器刻度 C")
        if req.halfwave.initial.p2_deg is None:
            missing_baseline.append("半波片刻度 P₂")
        if missing_baseline:
            validation_errors.append(
                f"半波片: 初始读数（{'、'.join(missing_baseline)}）为空，请填写起始角度后再计算"
            )
        for i, row in enumerate(req.halfwave.rows):
            if row.c_deg is None or row.p2_deg is None:
                validation_errors.append(f"半波片: 第 {i+1} 行数据不完整")
        data['halfwave'] = hw_dict

    if req.quarterwave:
        qw_dict = {'rows': [r.model_dump() for r in req.quarterwave.rows]}
        filled = sum(1 for r in req.quarterwave.rows if r.i_raw is not None)
        if filled < 10:
            validation_errors.append(f"四分之一波片: 需要至少10个有效光强数据，当前仅有 {filled} 个")
        data['quarterwave'] = qw_dict

    if req.circular:
        circ_dict = {'rows': [r.model_dump() for r in req.circular.rows]}
        data['circular'] = circ_dict

    if validation_errors:
        return {
            "status": "validation_error",
            "errors": validation_errors,
            "results": {},
            "plots": {},
        }

    if not data:
        raise HTTPException(status_code=400, detail="未提供任何实验数据")

    try:
        result = adapter.process_all(data)
        result['status'] = 'success'
        return result
    except Exception as e:
        return {
            "status": "calculation_error",
            "error": (
                "计算过程中出现异常，请检查数据是否完整、有无空白或全零的读数，"
                f"修改后重试。（技术信息：{e}）"
            ),
            "results": {},
            "plots": {},
        }


@app.get("/api/record-sheets/polarization.docx")
async def get_polarization_record_sheet_docx():
    """Blank record sheet as an editable Word file (mimo landscape clean layout)."""
    from experiments import record_clean
    content = record_clean.record_bytes("polarization", "docx")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _attachment("偏振光与双折射实验-数据记录表.docx")},
    )


@app.get("/api/record-sheets/polarization.pdf")
async def get_polarization_record_sheet_pdf():
    """Blank record sheet as a landscape printable PDF (mimo clean layout)."""
    from experiments import record_clean
    content = record_clean.record_bytes("polarization", "pdf")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": _attachment("偏振光与双折射实验-数据记录表.pdf")},
    )


@app.post("/api/experiments/polarization/report")
async def polarization_report(req: ProcessRequest, fmt: str = "docx",
                              part: Optional[str] = None):
    """Generate the unified four-section report as Word or compact PDF.

    ``part`` remains accepted for compatibility but no longer changes output.
    """
    from experiments.polarization import docbuild

    data = _request_to_data(req)
    if not data:
        raise HTTPException(status_code=400, detail="未提供任何实验数据")
    if fmt not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="fmt 必须是 docx 或 pdf")
    try:
        content = docbuild.report_bytes(data, bg_uw=req.bg_uw,
                                        theta_qwp=req.theta_qwp, fmt=fmt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"报告生成失败: {e}")
    fname = f"偏振光与双折射实验-完整报告.{'docx' if fmt == 'docx' else 'pdf'}"
    mime = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if fmt == "docx" else "application/pdf")
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": _attachment(fname)})


def _request_to_data(req: ProcessRequest) -> dict:
    data = {}
    if req.malus:
        data["malus"] = {"rows": [r.model_dump() for r in req.malus.rows]}
    if req.halfwave:
        data["halfwave"] = {"initial": req.halfwave.initial.model_dump(),
                            "rows": [r.model_dump() for r in req.halfwave.rows]}
    if req.quarterwave:
        data["quarterwave"] = {"rows": [r.model_dump() for r in req.quarterwave.rows]}
    if req.circular:
        data["circular"] = {"rows": [r.model_dump() for r in req.circular.rows]}
    return data


def _attachment(filename: str) -> str:
    from urllib.parse import quote
    return f"attachment; filename*=UTF-8''{quote(filename)}"


@app.get("/api/experiments/polarization/config")
async def get_polarization_config():
    """Return the experiment configuration for the frontend."""
    config_path = BACKEND_ROOT / "experiments" / "polarization" / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Config not found")


# ════════════════════════════════════════════════════════════════════
#  exp02 声速光速的测量
# ════════════════════════════════════════════════════════════════════

class SoundLightProcessRequest(BaseModel):
    """Single-method processing: {method, rows, params}."""
    method: str
    rows: Dict[str, List[Optional[float]]] = Field(default_factory=dict)
    params: Dict[str, float] = Field(default_factory=dict)


class SoundLightReportRequest(BaseModel):
    """Report generation: {data: {method_id: {rows, params}, ...}}."""
    data: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


@app.get("/api/experiments/sound-light/config")
async def get_soundlight_config():
    """Return the exp02 method config array (6 methods) for the frontend."""
    config_path = BACKEND_ROOT / "experiments" / "soundlight" / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Config not found")


@app.post("/api/experiments/sound-light/process")
async def process_soundlight(req: SoundLightProcessRequest):
    """Process one sound/light-speed method: returns {status, errors, results, plots}."""
    from experiments.soundlight import engine
    return engine.process_method(req.method, req.rows or {}, req.params or {})


@app.get("/api/record-sheets/sound-light.docx")
async def get_soundlight_record_sheet_docx():
    """Blank exp02 record sheet as an editable Word file (mimo landscape clean layout)."""
    from experiments import record_clean
    content = record_clean.record_bytes("sound-light", "docx")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _attachment("声速光速的测量-数据记录表.docx")},
    )


@app.get("/api/record-sheets/sound-light.pdf")
async def get_soundlight_record_sheet_pdf():
    """Blank exp02 record sheet as a landscape printable PDF (mimo clean layout)."""
    from experiments import record_clean
    content = record_clean.record_bytes("sound-light", "pdf")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": _attachment("声速光速的测量-数据记录表.pdf")},
    )


@app.post("/api/experiments/sound-light/report")
async def soundlight_report(req: SoundLightReportRequest, fmt: str = "docx",
                            part: Optional[str] = None):
    """Generate the unified exp02 four-section report as Word or compact PDF.

    Body: {"data": {"<method_id>": {"rows": {...}, "params": {...}}, ...}}
    Only methods with submitted data are included in the report.
    ``part`` remains accepted for compatibility but no longer changes output.
    """
    if not req.data:
        raise HTTPException(status_code=400, detail="未提供任何实验数据")
    if fmt not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="fmt 必须是 docx 或 pdf")
    from experiments.soundlight import docs
    try:
        content = docs.report_bytes(req.data, fmt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"报告生成失败: {e}")
    fname = f"声速光速的测量-完整报告.{'docx' if fmt == 'docx' else 'pdf'}"
    mime = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if fmt == "docx" else "application/pdf")
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": _attachment(fname)})


# ════════════════════════════════════════════════════════════════════
#  Configuration-driven experiments (all labs after the first two)
# ════════════════════════════════════════════════════════════════════

class GenericExperimentRequest(BaseModel):
    data: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


def _generic_config(experiment_id: str) -> dict:
    from experiments.general.engine import CONFIG_BY_ID
    config = CONFIG_BY_ID.get(experiment_id)
    if not config:
        raise HTTPException(status_code=404, detail="实验配置不存在")
    return config


@app.get("/api/experiments/{experiment_id}/config")
async def get_generic_experiment_config(experiment_id: str):
    return _generic_config(experiment_id)


@app.post("/api/experiments/{experiment_id}/process")
async def process_generic_experiment(experiment_id: str,
                                     req: GenericExperimentRequest):
    _generic_config(experiment_id)
    from experiments.general.engine import process_experiment
    return process_experiment(experiment_id, req.data)


@app.get("/api/record-sheets/{experiment_id}.{fmt}")
async def get_generic_record_sheet(experiment_id: str, fmt: str):
    config = _generic_config(experiment_id)
    if fmt not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="fmt 必须是 docx 或 pdf")
    from experiments.general import docs
    content = docs.record_bytes(experiment_id, fmt)
    mime = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if fmt == "docx" else "application/pdf")
    filename = f"{config['name']}-数据记录表.{fmt}"
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": _attachment(filename)})


def _validate_required_generic_data(config: dict, data: Dict[str, Dict[str, Any]]) -> None:
    missing = []
    for method in config.get("methods", []):
        if not method.get("required"):
            continue
        submitted = data.get(method["id"])
        rows = submitted.get("rows", []) if submitted else []
        columns = [column["key"] for column in method.get("columns", [])]
        expected_rows = method.get("rowCount", 0)
        complete = (
            len(rows) >= expected_rows
            and all(
                row.get(key) not in (None, "")
                for row in rows[:expected_rows]
                for key in columns
            )
        )
        if not complete:
            missing.append(method["name"])
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"请先填写完全部必做实验：{'、'.join(missing)}",
        )


@app.post("/api/experiments/{experiment_id}/report")
async def generic_experiment_report(experiment_id: str,
                                    req: GenericExperimentRequest,
                                    fmt: str = "docx"):
    config = _generic_config(experiment_id)
    if fmt not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="fmt 必须是 docx 或 pdf")
    if not req.data:
        raise HTTPException(status_code=400, detail="未提供任何实验数据")
    _validate_required_generic_data(config, req.data)
    from experiments.general import docs
    try:
        content = docs.report_bytes(experiment_id, req.data, fmt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"报告生成失败: {exc}")
    mime = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if fmt == "docx" else "application/pdf")
    filename = f"{config['name']}-完整报告.{fmt}"
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": _attachment(filename)})
