"""Shared pytest classification for fast and full regression runs."""

import pytest


def pytest_collection_modifyitems(items):
    """Every non-document test belongs to the fast development layer."""
    for item in items:
        if "document" not in item.keywords:
            item.add_marker(pytest.mark.fast)

