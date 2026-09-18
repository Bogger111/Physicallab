"""Release-readiness checks for what a student actually sees.

These are guard rails for the polish work: the suggested range next to every
input must be meaningful (grounded in the printed record sheet), and the user
facing copy must stay free of internal detail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from experiments.core.registry import PUBLIC_EXPERIMENT_IDS, registry
from experiments.schema import enrich_config
from app.main import app
from fastapi.testclient import TestClient

CLIENT = TestClient(app)
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def _methods(experiment_id: str) -> list[dict]:
    config = registry.get(experiment_id).config
    if isinstance(config, list):
        return config
    return config.get("methods") or []


def _fields(experiment_id: str) -> list[tuple[str, dict]]:
    for method in _methods(experiment_id):
        for column in method.get("columns") or []:
            yield method["id"], column


def test_suggested_ranges_are_grounded_in_the_printed_scale():
    """A hint must not be absurdly wider than the sheet's own printed values.

    The unit-based fallback in `_infer_range` is a safety net, not a hint: it
    produced "建议 -10000~10000 kΩ" for a 0–2 kΩ calibration row.
    """
    problems: list[str] = []
    for experiment_id in PUBLIC_EXPERIMENT_IDS:
        for method in _methods(experiment_id):
            prefill = method.get("prefill") or {}
            for column in method.get("columns") or []:
                printed = prefill.get(column["key"])
                if not printed:
                    continue
                low, high = column["expected_range"]
                span = max(printed) - min(printed)
                if span <= 0:
                    continue
                if (high - low) / span > 20:
                    problems.append(f"{experiment_id}/{method['id']}.{column['key']}: "
                                    f"hint {low}~{high} for printed {min(printed)}~{max(printed)}")
                if not (low <= min(printed) and max(printed) <= high):
                    problems.append(f"{experiment_id}/{method['id']}.{column['key']}: "
                                    f"hint {low}~{high} excludes a printed value")
    assert problems == [], problems


def test_calibration_methods_show_the_scale_they_measure():
    """The multimeter's 200 mV / 20 mA / 2 kΩ scales must say so."""
    cases = {
        ("voltage", "set"): (0, 220),
        ("voltage", "measured"): (0, 220),
        ("current", "set"): (0, 22),
        ("resistance", "set"): (0, 2.2),
    }
    for experiment_id in ("multimeter",):
        enriched = enrich_config(registry.get(experiment_id).config)
        for method in enriched["methods"]:
            for column in method["columns"]:
                expected = cases.get((method["id"], column["key"]))
                if expected:
                    assert tuple(column["expected_range"]) == expected, (method["id"], column["key"])


def test_ranges_are_still_warnings_not_blocks():
    """The polish must not turn a hint into a validation error."""
    response = CLIENT.post("/api/experiments/multimeter/validate", json={
        "data": {"voltage": {"rows": [{"set": 9999, "measured": 9999}], "params": {}}},
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("errors") == []
    assert any(item["code"] == "expected_range" for item in body.get("warnings", []))


@pytest.mark.parametrize("relative", ["src/components/workspace/DataContributionPanel.tsx",
                                      "src/components/workspace/CoBuildIntroCard.tsx",
                                      "src/components/workspace/ContributionThanksDialog.tsx"])
def test_user_facing_copy_avoids_jargon_and_internal_ids(relative):
    source = (FRONTEND / relative).read_text(encoding="utf-8")
    for banned in ("EXIF", "session_id", "UUID", "collection_mode", "metadata.json"):
        assert banned not in source, f"{relative} leaks {banned}"
    assert "sessions/" not in source, f"{relative} leaks a storage path"


def test_home_page_shows_both_entries_side_by_side():
    source = (FRONTEND / "src/app/page.tsx").read_text(encoding="utf-8")
    assert 'href="/experiments"' in source
    assert 'href="/experiments?mode=collection"' in source
    assert "普通实验" in source and "AI 实验共建" in source
