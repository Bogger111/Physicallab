from app.telemetry import analytics_summary, record_event, record_ocr_feedback


def test_analytics_is_anonymous_and_best_effort(monkeypatch, tmp_path):
    monkeypatch.setenv("PHYSICSLAB_TELEMETRY_DB", str(tmp_path / "telemetry.sqlite3"))
    assert record_event("experiment_open", "session-1", experiment_id="polarization", metadata={"rows": [1]})
    assert not record_event("not-an-event", "session-1")
    summary = analytics_summary()
    assert summary["events"]["experiment_open"] == 1


def test_feedback_requires_explicit_consent_and_verification(monkeypatch, tmp_path):
    monkeypatch.setenv("PHYSICSLAB_TELEMETRY_DB", str(tmp_path / "telemetry.sqlite3"))
    base = {
        "sample_id": "sample-1", "experiment_id": "michelson", "field_id": "position[0]",
        "prediction": "24.220", "confidence": .8, "confirmed_value": "24.270",
        "was_corrected": True, "ocr_provider": "rapidocr",
        "ocr_model_version": "RapidOCR-3.9.2/PP-OCRv6-small",
        "anonymous_session_id": "session-1",
    }
    assert record_ocr_feedback({**base, "consent": False, "verified": True})["stored"] is False
    assert record_ocr_feedback({**base, "consent": True, "verified": True})["stored"] is True
    assert analytics_summary()["ocr"]["correction_rate"] == 1.0
