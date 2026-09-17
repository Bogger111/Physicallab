"""Anonymous, best-effort usage analytics routes."""

from fastapi import APIRouter

from app.models import AnalyticsEventRequest


router = APIRouter()


@router.post("/api/analytics/events")
async def submit_analytics_event(req: AnalyticsEventRequest):
    from app.telemetry import record_event
    accepted = record_event(req.event_name, req.anonymous_session_id,
                            experiment_id=req.experiment_id,
                            metadata=req.metadata, app_version=req.app_version)
    return {"accepted": accepted}


@router.get("/api/analytics/summary")
async def get_analytics_summary():
    from app.telemetry import analytics_summary
    return analytics_summary()
