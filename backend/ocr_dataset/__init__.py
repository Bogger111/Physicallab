"""Consent-first OCR training dataset builder.

The package is intentionally offline and read-only with respect to collection
sessions.  It exports only cropped numeric cells and minimal provenance.
"""

from .collector import CollectionCandidate, CollectionReject, collect_sessions
from .exporter import BuildResult, deterministic_sample_id

__all__ = [
    "BuildResult",
    "CollectionCandidate",
    "CollectionReject",
    "collect_sessions",
    "deterministic_sample_id",
]
