"""Small anonymous SQLite event and OCR feedback store.

The store is best-effort by design: a telemetry outage must never make an
experiment calculation fail.  The database path is configurable for local
development and export scripts and defaults to a temporary runtime directory.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


ALLOWED_EVENTS = frozenset({
    "page_view", "experiment_open", "workspace_start", "record_sheet_download",
    "ocr_upload", "ocr_success", "ocr_failure", "ocr_confirm", "ocr_corrected",
    "calculation_run", "report_export", "validation_warning", "frontend_error",
    "backend_error",
})


def database_path() -> Path:
    configured = os.getenv("PHYSICSLAB_TELEMETRY_DB", "").strip()
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "physicslab" / "telemetry.sqlite3"


def _connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript("""
      CREATE TABLE IF NOT EXISTS analytics_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name TEXT NOT NULL,
        timestamp REAL NOT NULL,
        anonymous_session_id TEXT NOT NULL,
        experiment_id TEXT,
        metadata_json TEXT NOT NULL,
        app_version TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS ocr_feedback (
        sample_id TEXT PRIMARY KEY,
        experiment_id TEXT NOT NULL,
        field_id TEXT NOT NULL,
        prediction TEXT NOT NULL,
        confidence REAL,
        confirmed_value TEXT,
        was_corrected INTEGER NOT NULL,
        verified INTEGER NOT NULL,
        consent INTEGER NOT NULL,
        ocr_provider TEXT NOT NULL,
        ocr_model_version TEXT NOT NULL,
        created_at REAL NOT NULL,
        anonymous_session_id TEXT NOT NULL,
        cell_image_path TEXT
      );
    """)
    return connection


def record_event(event_name: str, anonymous_session_id: str, *,
                 experiment_id: str | None = None,
                 metadata: dict[str, Any] | None = None,
                 app_version: str = "2.0") -> bool:
    if event_name not in ALLOWED_EVENTS or not anonymous_session_id:
        return False
    # Metadata is intentionally caller-supplied and bounded.  Do not accept
    # raw rows, images, names or student identifiers in this table.
    safe_metadata = metadata if isinstance(metadata, dict) else {}
    safe_metadata = {str(key): value for key, value in safe_metadata.items()
                     if key not in {"rows", "data", "image", "raw_text", "confirmed_value"}}
    try:
        with _connect() as connection:
            connection.execute(
                "INSERT INTO analytics_events(event_name,timestamp,anonymous_session_id,experiment_id,metadata_json,app_version) VALUES(?,?,?,?,?,?)",
                (event_name, time.time(), anonymous_session_id[:128], experiment_id,
                 json.dumps(safe_metadata, ensure_ascii=False, default=str)[:4000], app_version[:40]),
            )
        return True
    except Exception:
        return False


def record_ocr_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist an explicitly consented, user-verified cell correction."""
    sample_id = str(payload.get("sample_id") or uuid.uuid4())[:128]
    session_id = str(payload.get("anonymous_session_id") or "")[:128]
    consent = bool(payload.get("consent"))
    verified = bool(payload.get("verified"))
    if not session_id or not consent or not verified:
        return {"stored": False, "reason": "需要匿名采集同意和用户明确确认"}
    try:
        confidence = payload.get("confidence")
        confidence = float(confidence) if confidence is not None else None
        with _connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO ocr_feedback
                (sample_id,experiment_id,field_id,prediction,confidence,confirmed_value,
                 was_corrected,verified,consent,ocr_provider,ocr_model_version,created_at,
                 anonymous_session_id,cell_image_path)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sample_id, str(payload.get("experiment_id") or "")[:120],
                 str(payload.get("field_id") or "")[:120],
                 str(payload.get("prediction") or "")[:200], confidence,
                 str(payload.get("confirmed_value") or "")[:200],
                 int(bool(payload.get("was_corrected"))), 1, 1,
                 str(payload.get("ocr_provider") or "unknown")[:60],
                 str(payload.get("ocr_model_version") or "unknown")[:100],
                 time.time(), session_id, None),
            )
        return {"stored": True, "sample_id": sample_id}
    except Exception:
        return {"stored": False, "reason": "反馈存储暂不可用"}


def analytics_summary() -> dict[str, Any]:
    try:
        with _connect() as connection:
            totals = connection.execute(
                "SELECT event_name, COUNT(*) AS count FROM analytics_events GROUP BY event_name"
            ).fetchall()
            experiments = connection.execute(
                "SELECT experiment_id, COUNT(*) AS count FROM analytics_events WHERE event_name='experiment_open' AND experiment_id IS NOT NULL GROUP BY experiment_id ORDER BY count DESC"
            ).fetchall()
            now = time.time()
            dau = connection.execute(
                "SELECT COUNT(DISTINCT anonymous_session_id) AS count FROM analytics_events WHERE timestamp >= ?",
                (now - 86400,),
            ).fetchone()["count"]
            wau = connection.execute(
                "SELECT COUNT(DISTINCT anonymous_session_id) AS count FROM analytics_events WHERE timestamp >= ?",
                (now - 7 * 86400,),
            ).fetchone()["count"]
            funnel = connection.execute(
                "SELECT event_name, COUNT(DISTINCT anonymous_session_id) AS sessions FROM analytics_events WHERE event_name IN ('experiment_open','calculation_run','report_export') GROUP BY event_name"
            ).fetchall()
            feedback = connection.execute(
                "SELECT COUNT(*) AS confirmed, COALESCE(SUM(was_corrected),0) AS corrected FROM ocr_feedback WHERE verified=1"
            ).fetchone()
        confirmed = int(feedback["confirmed"] or 0)
        corrected = int(feedback["corrected"] or 0)
        return {
            "dau": int(dau or 0),
            "wau": int(wau or 0),
            "events": {row["event_name"]: row["count"] for row in totals},
            "experiment_open_rank": [dict(row) for row in experiments],
            "funnel_sessions": {row["event_name"]: row["sessions"] for row in funnel},
            "ocr": {
                "confirmed_cells": confirmed,
                "corrected_cells": corrected,
                "correction_rate": corrected / confirmed if confirmed else None,
            },
        }
    except Exception:
        return {"events": {}, "experiment_open_rank": [], "ocr": {"confirmed_cells": 0, "corrected_cells": 0, "correction_rate": None}}
