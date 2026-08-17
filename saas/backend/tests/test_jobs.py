import asyncio
import os
import sys
import types
import uuid

import pytest

from app import jobs, models
from app.db import SessionLocal


def _make_org_and_repo(db):
    org = models.Organization(name="JobsCo")
    db.add(org)
    db.flush()
    repo = models.Repository(org_id=org.id, full_name="jobsco/widgets")
    db.add(repo)
    db.commit()
    return org, repo


def _make_pentest(db, org, repo):
    pentest = models.Pentest(org_id=org.id, target_type="repository", target_id=repo.id, target_label=repo.full_name)
    db.add(pentest)
    db.commit()
    db.refresh(pentest)
    return pentest


async def test_enqueue_without_worker_raises():
    # Module-level _queue is reset to None on every lifespan shutdown (see
    # jobs.stop_worker) and starts as None on import, so as long as no
    # TestClient fixture is active in this test, it should still be unset.
    assert jobs._queue is None
    with pytest.raises(RuntimeError, match="job queue not started"):
        await jobs.enqueue_pentest("some-id")


async def test_run_pentest_missing_row_is_a_noop():
    # Covers `_run_pentest`'s early-return branch when the pentest row
    # doesn't exist (e.g. deleted between enqueue and dequeue).
    await jobs._run_pentest("does-not-exist")  # must not raise


async def test_run_pentest_marks_failed_on_scan_exception(monkeypatch):
    db = SessionLocal()
    try:
        org, repo = _make_org_and_repo(db)
        pentest = _make_pentest(db, org, repo)
        pentest_id = pentest.id
    finally:
        db.close()

    async def _boom(_pentest):
        raise RuntimeError("scanner exploded")

    monkeypatch.setattr(jobs, "_scan", _boom)
    await jobs._run_pentest(pentest_id)

    db = SessionLocal()
    try:
        reloaded = db.get(models.Pentest, pentest_id)
        assert reloaded.status == "failed"
        assert reloaded.finished_at is not None
    finally:
        db.close()


async def test_run_pentest_success_updates_repo_last_tested():
    db = SessionLocal()
    try:
        org, repo = _make_org_and_repo(db)
        pentest = _make_pentest(db, org, repo)
        pentest_id, repo_id = pentest.id, repo.id
    finally:
        db.close()

    await jobs._run_pentest(pentest_id)

    db = SessionLocal()
    try:
        reloaded = db.get(models.Pentest, pentest_id)
        assert reloaded.status == "completed"
        reloaded_repo = db.get(models.Repository, repo_id)
        assert reloaded_repo.last_tested_at is not None
    finally:
        db.close()


async def test_scan_falls_back_to_mock_when_real_scan_unavailable(monkeypatch):
    monkeypatch.setattr(jobs.settings, "enable_real_scan", True)
    db = SessionLocal()
    try:
        org, repo = _make_org_and_repo(db)
        pentest = _make_pentest(db, org, repo)
    finally:
        db.close()

    # `strix` (the real-scan extra) isn't installed in this venv, so
    # _run_real_scan's import fails and _scan should fall back to the mock
    # scanner rather than propagating the ImportError.
    findings = await jobs._scan(pentest, None)
    assert isinstance(findings, list)


def _install_fake_strix_module(monkeypatch, run_strix_scan):
    fake_strix = types.ModuleType("strix")
    fake_core = types.ModuleType("strix.core")
    fake_runner = types.ModuleType("strix.core.runner")
    fake_runner.run_strix_scan = run_strix_scan
    fake_core.runner = fake_runner
    fake_strix.core = fake_core

    fake_config = types.ModuleType("strix.config")
    fake_loader = types.ModuleType("strix.config.loader")
    fake_loader._cached = "some-cached-settings-object"
    fake_config.loader = fake_loader
    fake_strix.config = fake_config

    monkeypatch.setitem(sys.modules, "strix", fake_strix)
    monkeypatch.setitem(sys.modules, "strix.core", fake_core)
    monkeypatch.setitem(sys.modules, "strix.core.runner", fake_runner)
    monkeypatch.setitem(sys.modules, "strix.config", fake_config)
    monkeypatch.setitem(sys.modules, "strix.config.loader", fake_loader)
    return fake_loader


async def test_run_real_scan_success_path(monkeypatch):
    """Injects a fake `strix.core.runner` module so _run_real_scan's import
    succeeds, covering the path that isn't reachable without the optional
    real-scan dependency actually installed."""
    calls = {}

    async def fake_run_strix_scan(*, scan_config, scan_id):
        calls["scan_config"] = scan_config
        calls["scan_id"] = scan_id

    _install_fake_strix_module(monkeypatch, fake_run_strix_scan)

    db = SessionLocal()
    try:
        org, repo = _make_org_and_repo(db)
        pentest = _make_pentest(db, org, repo)
    finally:
        db.close()

    result = await jobs._run_real_scan(pentest, None)
    assert result == []
    assert calls["scan_id"] == pentest.id
    assert calls["scan_config"]["run_name"] == f"saas-{pentest.id}"


async def test_run_real_scan_applies_and_restores_org_llm_env(monkeypatch):
    """With an OrgLlmSettings row configured, the org's model/key/base
    should be visible as env vars *during* the call, strix's settings
    cache should be invalidated, and everything should be restored
    afterward so the next scan doesn't inherit stale values."""
    seen_env = {}

    async def fake_run_strix_scan(*, scan_config, scan_id):
        seen_env["STRIX_LLM"] = os.environ.get("STRIX_LLM")
        seen_env["LLM_API_KEY"] = os.environ.get("LLM_API_KEY")
        seen_env["LLM_API_BASE"] = os.environ.get("LLM_API_BASE")

    fake_loader = _install_fake_strix_module(monkeypatch, fake_run_strix_scan)

    monkeypatch.setenv("STRIX_LLM", "openai/previous-model")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_BASE", raising=False)

    db = SessionLocal()
    try:
        org, repo = _make_org_and_repo(db)
        pentest = _make_pentest(db, org, repo)
        llm_settings = models.OrgLlmSettings(org_id=org.id, model="openai/gpt-5.4", api_key="sk-test-123", api_base="https://gateway.example.com/v1")
        db.add(llm_settings)
        db.commit()
        db.refresh(llm_settings)
        db.refresh(pentest)
    finally:
        db.close()

    result = await jobs._run_real_scan(pentest, llm_settings)

    assert result == []
    assert seen_env == {
        "STRIX_LLM": "openai/gpt-5.4",
        "LLM_API_KEY": "sk-test-123",
        "LLM_API_BASE": "https://gateway.example.com/v1",
    }
    # Cache was invalidated at least once during the override.
    assert fake_loader._cached is None
    # Previous process env is restored afterward.
    assert os.environ.get("STRIX_LLM") == "openai/previous-model"
    assert os.environ.get("LLM_API_KEY") is None
    assert os.environ.get("LLM_API_BASE") is None


async def test_run_real_scan_without_org_api_base_clears_inherited_process_value(monkeypatch):
    """If the org configures a model but no api_base, and the process
    happens to have LLM_API_BASE set (e.g. a previous org's scan, or a
    global default), it must not leak into this org's scan."""
    seen_env = {}

    async def fake_run_strix_scan(*, scan_config, scan_id):
        seen_env["LLM_API_BASE"] = os.environ.get("LLM_API_BASE")

    _install_fake_strix_module(monkeypatch, fake_run_strix_scan)
    monkeypatch.setenv("LLM_API_BASE", "http://leftover-from-someone-else:1234/v1")

    db = SessionLocal()
    try:
        org, repo = _make_org_and_repo(db)
        pentest = _make_pentest(db, org, repo)
        llm_settings = models.OrgLlmSettings(org_id=org.id, model="openai/gpt-5.4")
        db.add(llm_settings)
        db.commit()
        db.refresh(llm_settings)
        db.refresh(pentest)
    finally:
        db.close()

    await jobs._run_real_scan(pentest, llm_settings)
    assert seen_env["LLM_API_BASE"] is None
    # Restored afterward (it existed before, so it comes back).
    assert os.environ.get("LLM_API_BASE") == "http://leftover-from-someone-else:1234/v1"


async def test_run_real_scan_without_org_settings_leaves_env_untouched(monkeypatch):
    async def fake_run_strix_scan(*, scan_config, scan_id):
        return None

    _install_fake_strix_module(monkeypatch, fake_run_strix_scan)
    monkeypatch.setenv("STRIX_LLM", "openai/process-default")

    db = SessionLocal()
    try:
        org, repo = _make_org_and_repo(db)
        pentest = _make_pentest(db, org, repo)
    finally:
        db.close()

    await jobs._run_real_scan(pentest, None)
    assert os.environ.get("STRIX_LLM") == "openai/process-default"


async def test_worker_loop_logs_and_continues_after_a_bad_job(monkeypatch):
    """Covers the outer try/except in _worker_loop: a job that raises must
    not kill the worker task, and subsequent jobs still get processed."""
    await jobs.start_worker()
    try:
        seen = []

        async def _flaky(pentest_id):
            if not seen:
                seen.append(pentest_id)
                raise RuntimeError("boom")
            seen.append(pentest_id)

        monkeypatch.setattr(jobs, "_run_pentest", _flaky)

        await jobs.enqueue_pentest(str(uuid.uuid4()))
        await jobs.enqueue_pentest(str(uuid.uuid4()))

        for _ in range(50):
            if len(seen) == 2:
                break
            await asyncio.sleep(0.01)
        assert len(seen) == 2
    finally:
        await jobs.stop_worker()
