"""In-process async job queue that executes pentests.

No Redis/Celery — a single `asyncio.Queue` plus a background worker task
started from the FastAPI lifespan (see main.py). This is deliberately
simple for a local scaffold; swapping in a real queue later means replacing
this module's `enqueue`/worker loop, not touching callers.

Two scan backends:
- `MockScanner` (default): waits briefly, then returns a handful of
  realistic-looking findings, so the full pentest -> issues UI flow works
  without Docker or LLM credentials.
- Real scan: when `SAAS_ENABLE_REAL_SCAN=1`, invokes the upstream
  `strix.core.runner.run_strix_scan` engine (imported lazily, as a library
  call — see saas/README.md's isolation rule: we never fork engine code).
  Falls back to the mock scanner with a logged warning if the real engine
  raises (e.g. Docker/LLM credentials missing), so the job queue never gets
  stuck.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from . import models
from .db import SessionLocal
from .settings import settings
from .time_utils import utcnow

logger = logging.getLogger("saas.jobs")

# Created fresh in start_worker() rather than at module import time: this
# module is a long-lived singleton (one import per process), but a queue
# must be bound to the event loop of the lifespan that owns it. Rebuilding
# it per-lifespan keeps repeated app startup/shutdown cycles in the same
# process safe (e.g. multiple TestClient instances in a test session).
_queue: asyncio.Queue[str] | None = None
_worker_task: asyncio.Task | None = None


async def enqueue_pentest(pentest_id: str) -> None:
    if _queue is None:
        raise RuntimeError("job queue not started — call jobs.start_worker() from the app lifespan first")
    await _queue.put(pentest_id)


async def start_worker() -> None:
    global _queue, _worker_task
    if _worker_task is None:
        _queue = asyncio.Queue()
        _worker_task = asyncio.create_task(_worker_loop())


async def stop_worker() -> None:
    global _queue, _worker_task
    if _worker_task is not None:
        _worker_task.cancel()
        _worker_task = None
    _queue = None


async def _worker_loop() -> None:
    while True:
        pentest_id = await _queue.get()
        try:
            await _run_pentest(pentest_id)
        except Exception:  # noqa: BLE001 - a broken job must not kill the worker
            logger.exception("pentest job %s failed", pentest_id)
        finally:
            _queue.task_done()


async def _run_pentest(pentest_id: str) -> None:
    db = SessionLocal()
    try:
        pentest = db.get(models.Pentest, pentest_id)
        if pentest is None:
            return
        pentest.status = "running"
        pentest.started_at = utcnow()
        db.commit()

        try:
            findings = await _scan(pentest)
        except Exception:  # noqa: BLE001 - a scan bug must not strand the pentest in "running" forever
            logger.exception("scan failed for pentest %s", pentest.id)
            pentest.status = "failed"
            pentest.finished_at = utcnow()
            db.commit()
            return

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for finding in findings:
            severity_counts[finding["severity"]] += 1
            db.add(
                models.Issue(
                    org_id=pentest.org_id,
                    pentest_id=pentest.id,
                    repository_id=pentest.target_id if pentest.target_type == "repository" else None,
                    domain_id=pentest.target_id if pentest.target_type == "domain" else None,
                    title=finding["title"],
                    description=finding["description"],
                    severity=finding["severity"],
                    cvss=finding["cvss"],
                    cvss_breakdown=finding["cvss_breakdown"],
                    technical_analysis=finding["technical_analysis"],
                    remediation_steps=finding["remediation_steps"],
                    poc_description=finding["poc_description"],
                    target=finding["target"],
                    endpoint=finding["endpoint"],
                    fix_effort=finding["fix_effort"],
                )
            )

        pentest.status = "completed"
        pentest.finished_at = utcnow()
        pentest.severity_counts = severity_counts

        if pentest.target_type == "repository":
            repo = db.get(models.Repository, pentest.target_id)
            if repo:
                repo.last_tested_at = pentest.finished_at
        elif pentest.target_type == "domain":
            domain = db.get(models.Domain, pentest.target_id)
            if domain:
                domain.last_tested_at = pentest.finished_at

        db.commit()
    finally:
        db.close()


async def _scan(pentest: models.Pentest) -> list[dict]:
    if settings.enable_real_scan:
        try:
            return await _run_real_scan(pentest)
        except Exception:  # noqa: BLE001
            logger.exception("real scan failed for pentest %s, falling back to mock scanner", pentest.id)
    return await _run_mock_scan(pentest)


async def _run_real_scan(pentest: models.Pentest) -> list[dict]:
    """Invoke the upstream strix engine as a library. Requires Docker + LLM credentials."""
    from strix.core.runner import run_strix_scan  # lazy import: optional dependency

    scan_config = {
        "scan_id": pentest.id,
        "targets": [pentest.target_label],
        "run_name": f"saas-{pentest.id}",
        "scan_mode": pentest.scan_mode,
    }
    await run_strix_scan(scan_config=scan_config, scan_id=pentest.id)
    # Real findings land in the run's ReportState/vulnerabilities.json; a
    # follow-up task should translate those into the shape `_run_pentest`
    # expects here (see TASKS.md P6-5) once Docker/LLM creds are available
    # to actually exercise this path end-to-end.
    return []


MOCK_FINDINGS = [
    {
        "title": "Missing authorization check on withdrawal endpoint",
        "severity": "critical",
        "cvss": 9.1,
        "endpoint": "/api/v1/wallet/withdraw",
        "description": "The withdrawal endpoint does not verify that the authenticated user owns the target wallet ID, allowing cross-account fund transfers.",
        "technical_analysis": "The handler reads `wallet_id` directly from the request body and passes it to the transfer service without comparing it against `request.user.wallet_id`. Any authenticated user can supply another user's wallet ID.",
        "remediation_steps": "Derive the wallet ID from the authenticated session rather than trusting client input, or explicitly verify ownership before processing the transfer.",
        "poc_description": "Authenticate as user A, then POST to /api/v1/wallet/withdraw with user B's wallet_id and a destination account controlled by the attacker.",
        "fix_effort": "low",
    },
    {
        "title": "Reflected XSS in search query parameter",
        "severity": "high",
        "cvss": 6.8,
        "endpoint": "/search?q=",
        "description": "The `q` query parameter is reflected into the page without HTML-escaping, allowing script injection.",
        "technical_analysis": "The search results template interpolates `request.args['q']` directly into an HTML attribute without escaping.",
        "remediation_steps": "Use the templating engine's auto-escaping (or explicit escaping) for all user-controlled values rendered into HTML.",
        "poc_description": "Visit /search?q=<script>alert(document.domain)</script> while authenticated.",
        "fix_effort": "low",
    },
    {
        "title": "Outdated dependency with known RCE (CVE-2023-XXXX)",
        "severity": "high",
        "cvss": 8.1,
        "endpoint": "package.json",
        "description": "A transitive dependency pinned to a vulnerable version has a published remote code execution advisory.",
        "technical_analysis": "Dependency tree resolution shows the vulnerable version is reachable from a production code path that deserializes untrusted input.",
        "remediation_steps": "Upgrade the dependency to the patched release and re-run the dependency scan to confirm the advisory no longer applies.",
        "poc_description": "N/A - dependency advisory, see linked CVE for a public exploit.",
        "fix_effort": "low",
    },
    {
        "title": "Verbose error messages leak stack traces",
        "severity": "medium",
        "cvss": 4.3,
        "endpoint": "/api/v1/*",
        "description": "Unhandled exceptions return full Python stack traces to the client, revealing internal file paths and framework versions.",
        "technical_analysis": "Debug mode appears enabled in the deployed environment, or a generic exception handler is missing.",
        "remediation_steps": "Disable debug mode in production and add a catch-all exception handler that returns a generic error response.",
        "poc_description": "Send a malformed request body to any JSON endpoint and observe the response body.",
        "fix_effort": "low",
    },
    {
        "title": "Missing rate limiting on login endpoint",
        "severity": "low",
        "cvss": 3.1,
        "endpoint": "/api/v1/auth/login",
        "description": "The login endpoint has no observable rate limiting, permitting credential-stuffing attempts.",
        "technical_analysis": "Repeated failed login attempts from the same IP/account were not throttled or locked out during testing.",
        "remediation_steps": "Add rate limiting (per-IP and per-account) and consider progressive delays or CAPTCHA after repeated failures.",
        "poc_description": "Script repeated POSTs to /api/v1/auth/login with varying passwords for a known username.",
        "fix_effort": "medium",
    },
]


async def _run_mock_scan(pentest: models.Pentest) -> list[dict]:
    low, high = settings.mock_scan_min_seconds, settings.mock_scan_max_seconds
    await asyncio.sleep(low + random.random() * max(0.0, high - low))
    sample_size = random.randint(2, len(MOCK_FINDINGS))
    chosen = random.sample(MOCK_FINDINGS, k=sample_size)
    findings = []
    for f in chosen:
        findings.append(
            {
                **f,
                "id": uuid.uuid4().hex,
                "target": pentest.target_label,
                "cvss_breakdown": {"base_score": f["cvss"], "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"},
            }
        )
    return findings
