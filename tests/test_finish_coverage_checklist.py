"""Tests for finish_scan's mandatory coverage_checklist gate (Tier 2 of the
scan-coverage plan — see strix/tools/finish/tool.py's module docstring)."""

from __future__ import annotations

import pytest

from strix.tools.finish.tool import REQUIRED_COVERAGE_CATEGORIES, _do_finish


def _full_checklist(**overrides: str) -> dict[str, str]:
    base = {c: f"reviewed {c}, nothing of note found here" for c in REQUIRED_COVERAGE_CATEGORIES}
    base.update(overrides)
    return base


def _finish(**kwargs: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "parent_id": None,
        "executive_summary": "summary",
        "methodology": "methodology",
        "technical_analysis": "analysis",
        "recommendations": "recommendations",
        "coverage_checklist": _full_checklist(),
    }
    defaults.update(kwargs)
    return _do_finish(**defaults)  # type: ignore[arg-type]


def test_finish_succeeds_with_a_complete_checklist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "strix.report.state.get_global_report_state",
        lambda: None,  # exercises the "not persisted" success branch, not the checklist gate
    )
    result = _finish()
    assert result["success"] is True


def test_finish_rejects_a_missing_category() -> None:
    incomplete = _full_checklist()
    del incomplete["secrets"]
    result = _finish(coverage_checklist=incomplete)
    assert result["success"] is False
    assert any("secrets" in e for e in result["errors"])


def test_finish_rejects_an_empty_category_note() -> None:
    result = _finish(coverage_checklist=_full_checklist(injection="   "))
    assert result["success"] is False
    assert any("injection" in e and "empty" in e for e in result["errors"])


def test_finish_rejects_a_one_word_dismissal() -> None:
    result = _finish(coverage_checklist=_full_checklist(infrastructure="n/a"))
    assert result["success"] is False
    assert any("infrastructure" in e and "too short" in e for e in result["errors"])


def test_finish_rejects_an_unrecognized_category() -> None:
    result = _finish(coverage_checklist=_full_checklist(made_up_category="something"))
    assert result["success"] is False
    assert any("unrecognized" in e for e in result["errors"])


def test_finish_reports_every_missing_category_at_once() -> None:
    result = _finish(coverage_checklist={})
    assert result["success"] is False
    # One combined "missing categories" error, plus one "cannot be empty" per category.
    assert len(result["errors"]) == 1 + len(REQUIRED_COVERAGE_CATEGORIES)


def test_finish_still_enforces_the_narrative_fields_alongside_the_checklist() -> None:
    result = _finish(executive_summary="   ")
    assert result["success"] is False
    assert any("Executive summary" in e for e in result["errors"])
