"""Local development switches and the default collection storage implementation.

The data-collection feature is off unless a switch turns it on.  In development
that switch lives in `backend/.env.local` (git-ignored); in production the same
behavior is controlled by a real environment variable, which must always win.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import data_collection, dev_env
from app.data_collection import (
    CollectionStorage,
    LocalCollectionStorage,
    LocalFileStorage,
    collection_enabled,
    collection_root,
    local_storage,
)

BACKEND = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ env loading

def test_env_file_parsing_handles_comments_quotes_and_export(tmp_path, monkeypatch):
    # Importing app.main applies backend/.env.local to this process, so start from
    # a clean environment to assert the parser itself.
    for key in ("ENABLE_DATA_COLLECTION", "PHYSICSLAB_COLLECTION_ROOT",
                "PHYSICSLAB_TELEMETRY_DB", "EMPTY_VALUE"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env.local"
    path.write_text(
        "\n".join([
            "# a comment",
            "",
            "ENABLE_DATA_COLLECTION=true",
            'PHYSICSLAB_COLLECTION_ROOT="D:/private/collection"',
            "export PHYSICSLAB_TELEMETRY_DB='D:/tmp/t.sqlite3'",
            "NOT_AN_ASSIGNMENT",
            "EMPTY_VALUE=",
        ]),
        encoding="utf-8",
    )
    applied = dev_env.load_local_env((path,))
    try:
        assert applied == {
            "ENABLE_DATA_COLLECTION": "true",
            "PHYSICSLAB_COLLECTION_ROOT": "D:/private/collection",
            "PHYSICSLAB_TELEMETRY_DB": "D:/tmp/t.sqlite3",
            "EMPTY_VALUE": "",
        }
        assert collection_enabled() is True
    finally:
        for key in applied:
            os.environ.pop(key, None)


def test_process_environment_wins_over_the_file(tmp_path, monkeypatch):
    """A real deployment variable must never be overridden by a checked-out file."""
    path = tmp_path / ".env.local"
    path.write_text("ENABLE_DATA_COLLECTION=true\n", encoding="utf-8")
    monkeypatch.setenv("ENABLE_DATA_COLLECTION", "false")
    assert dev_env.load_local_env((path,)) == {}
    assert os.environ["ENABLE_DATA_COLLECTION"] == "false"
    assert collection_enabled() is False


def test_app_reads_the_local_file_on_startup():
    """`app.main` must apply the local switches before serving requests."""
    source = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
    assert "load_local_env()" in source
    assert dev_env.ENV_FILES[0] == BACKEND / ".env.local"
    assert dev_env.ENV_FILES[1] == BACKEND / ".env"


@pytest.mark.skipif(not (BACKEND / ".env.local").is_file(), reason="dev switch file absent")
def test_development_switch_file_enables_collection():
    applied = dev_env.load_local_env((BACKEND / ".env.local",))
    try:
        assert os.environ["ENABLE_DATA_COLLECTION"].lower() == "true"
        assert collection_enabled() is True
    finally:
        for key in applied:
            os.environ.pop(key, None)


# ------------------------------------------------------------------ local storage

def test_local_file_storage_is_the_default_and_keeps_the_interface():
    assert isinstance(local_storage(), LocalFileStorage)
    assert isinstance(local_storage(), CollectionStorage)
    assert LocalCollectionStorage is LocalFileStorage
    for method in ("create_session", "commit_session", "load_session", "delete_session", "dataset_root"):
        assert hasattr(LocalFileStorage, method), method


def test_storage_root_defaults_to_the_backend_directory(monkeypatch):
    monkeypatch.delenv("PHYSICSLAB_COLLECTION_ROOT", raising=False)
    assert collection_root() == BACKEND / "data_collection"
    monkeypatch.setenv("PHYSICSLAB_COLLECTION_ROOT", "D:/outside/the/repo")
    assert collection_root() == Path("D:/outside/the/repo")


def test_collection_output_is_git_ignored():
    """User images, metadata and datasets must never reach the repository."""
    ignore = (BACKEND.parent / ".gitignore").read_text(encoding="utf-8").splitlines()
    entries = {line.strip() for line in ignore}
    assert "backend/data_collection/" in entries
    assert ".env.local" in entries or ".env" in entries


def test_local_storage_layout_matches_the_documented_structure(tmp_path):
    storage = LocalFileStorage(tmp_path)
    metadata = storage.create_session(experiment_id="multimeter", template_version="2.0",
                                      image=b"\xff\xd8\xff\xe0fake-jpeg")
    session_dir = tmp_path / "sessions" / metadata["session_id"]
    assert (session_dir / "raw.jpg").read_bytes().startswith(b"\xff\xd8\xff")
    assert (session_dir / "metadata.json").is_file()
    assert metadata["image_path"] == f"sessions/{metadata['session_id']}/raw.jpg"
    assert metadata["status"] == "pending_confirmation"
    assert storage.dataset_root() == tmp_path / "datasets"
    assert data_collection.SessionRecord.__name__ == "SessionRecord"
