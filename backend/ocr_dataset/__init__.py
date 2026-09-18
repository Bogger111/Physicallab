"""Consent-first OCR dataset tooling.

The modules here import runtime code as top-level packages (``app.*``), because
the backend runs with ``backend/`` on ``sys.path``.  Putting that directory on
``sys.path`` here keeps every invocation form working, including
``python -m backend.ocr_dataset.export`` from the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from .collector import CollectionCandidate, CollectionReject, collect_sessions
from .exporter import BuildResult, deterministic_sample_id

__all__ = [
    "BuildResult",
    "CollectionCandidate",
    "CollectionReject",
    "collect_sessions",
    "deterministic_sample_id",
]
