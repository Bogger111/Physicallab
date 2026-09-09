"""PhysicsLab FastAPI backend."""

import os
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Reliable base paths
BACKEND_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent

app = FastAPI(title="PhysicsLab API", version="1.0.0")

# CORS for Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    c_deg: float
    c_min: float = 0.0
    p2_deg: float
    p2_min: float = 0.0

class HalfWaveRow(BaseModel):
    offset: float
    c_deg: float
    c_min: float = 0.0
    p2_deg: float
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


@app.get("/api/experiments")
async def list_experiments():
    """List all available experiments."""
    return {
        "experiments": [
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
                "description": "空气共振法、水中相位法、飞行时间法测声速；正弦法与李萨如法测光速",
                "sub_experiments": [
                    {"id": "air_resonance", "name": "空气中共振法测声速", "required": True},
                    {"id": "water_phase", "name": "水中相位法测声速", "required": True},
                    {"id": "tof", "name": "飞行时间法测声速", "required": False},
                    {"id": "light_sine", "name": "光速测量（正弦法）", "required": True},
                    {"id": "light_lissajous", "name": "光速测量（李萨如法）", "required": True},
                ],
                "record_sheet": "/api/record-sheets/sound-light",
                "processing_time": "~1分钟",
            }
        ]
    }


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
            "error": str(e),
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
async def polarization_report(req: ProcessRequest, part: str = "basic", fmt: str = "docx"):
    """Generate a part report (basic | advanced) as Word or compact PDF."""
    from experiments.polarization import docbuild

    data = _request_to_data(req)
    if not data:
        raise HTTPException(status_code=400, detail="未提供任何实验数据")
    if part not in ("basic", "advanced"):
        raise HTTPException(status_code=400, detail="part 必须是 basic 或 advanced")
    if fmt not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="fmt 必须是 docx 或 pdf")
    try:
        content = docbuild.part_bytes(part, data, bg_uw=req.bg_uw,
                                      theta_qwp=req.theta_qwp, fmt=fmt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"报告生成失败: {e}")
    label = "基准部分" if part == "basic" else "拓展部分"
    fname = f"偏振光与双折射实验-报告-{label}.{'docx' if fmt == 'docx' else 'pdf'}"
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
    rows: Dict[str, List[Any]] = {}
    params: Dict[str, Any] = {}


class SoundLightReportRequest(BaseModel):
    """Report generation: {data: {method_id: {rows, params}, ...}}."""
    data: Dict[str, Dict[str, Any]] = {}


@app.get("/api/experiments/sound-light/config")
async def get_soundlight_config():
    """Return the exp02 method config array (5 methods) for the frontend."""
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
async def soundlight_report(req: SoundLightReportRequest, part: str = "basic", fmt: str = "docx"):
    """Generate an exp02 part report (basic | advanced) as Word or compact PDF.

    Body: {"data": {"<method_id>": {"rows": {...}, "params": {...}}, ...}}
    Only methods with submitted data are included in the report.
    """
    if not req.data:
        raise HTTPException(status_code=400, detail="未提供任何实验数据")
    if part not in ("basic", "advanced"):
        raise HTTPException(status_code=400, detail="part 必须是 basic 或 advanced")
    if fmt not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="fmt 必须是 docx 或 pdf")
    from experiments.soundlight import docs
    try:
        content = docs.report_bytes(part, req.data, fmt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"报告生成失败: {e}")
    label = "基准部分" if part == "basic" else "拓展部分"
    fname = f"声速光速的测量-报告-{label}.{'docx' if fmt == 'docx' else 'pdf'}"
    mime = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if fmt == "docx" else "application/pdf")
    return Response(content=content, media_type=mime,
                    headers={"Content-Disposition": _attachment(fname)})
