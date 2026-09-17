"""API request models shared by route modules."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class SoundLightProcessRequest(BaseModel):
    method: str
    rows: Dict[str, List[Optional[float]]] = Field(default_factory=dict)
    params: Dict[str, float] = Field(default_factory=dict)


class SoundLightReportRequest(BaseModel):
    data: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class GenericExperimentRequest(BaseModel):
    data: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class AnalyticsEventRequest(BaseModel):
    event_name: str
    anonymous_session_id: str
    experiment_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    app_version: str = "2.0"


class OCRFeedbackRequest(BaseModel):
    sample_id: Optional[str] = None
    experiment_id: str
    field_id: str
    prediction: str
    confidence: Optional[float] = None
    confirmed_value: str
    was_corrected: bool
    verified: bool = False
    consent: bool = False
    ocr_provider: str = "unknown"
    ocr_model_version: str = "unknown"
    anonymous_session_id: str


class CollectionCommitRequest(BaseModel):
    experiment_id: str
    template_version: str = "2.0"
    consent: bool = False
    confirmed_data: Dict[str, Any]
