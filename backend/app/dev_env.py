"""Load local development switches without adding a dependency.

The backend reads configuration with ``os.getenv``; this module lets a developer
put switches in ``backend/.env.local`` (git-ignored) and have them applied on
startup:

    ENABLE_DATA_COLLECTION=true
    PHYSICSLAB_COLLECTION_ROOT=D:/AI/physicslab-private/collection

Precedence: a variable already present in the process environment always wins,
so a real deployment (Cloud Run env vars, exported shell variables, CI) is never
overridden by a file that happens to sit in the working tree.  Only two files are
read, in order, and only for keys that are still unset.
"""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENV_FILES = (BACKEND_ROOT / ".env.local", BACKEND_ROOT / ".env")


def _parse(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export "):].strip()
    key, separator, value = stripped.partition("=")
    key = key.strip()
    if not separator or not key:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return key, value


def load_local_env(paths: tuple[Path, ...] = ENV_FILES) -> dict[str, str]:
    """Apply unset keys from the local env files; returns what was applied."""
    applied: dict[str, str] = {}
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            parsed = _parse(line)
            if parsed is None:
                continue
            key, value = parsed
            if key in os.environ:
                continue
            os.environ[key] = value
            applied[key] = value
    return applied
