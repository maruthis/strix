"""In-process async job queue that executes pentests.

No Redis/Celery — a single `asyncio.Queue` plus a background worker task
started from the FastAPI lifespan (see main.py). This is deliberately
simple for a local scaffold; swapping in a real queue later means replacing
this module's `enqueue`/worker loop, not touching callers.

Two scan backends:
- `MockScanner` (default): waits briefly, then returns a handful of
  canned, realistic-looking findings (not derived from the target at
  all — same fixed list regardless of what repo/domain is picked), so the
  full pentest -> issues UI flow works without Docker or LLM credentials.
- Real scan: when `SAAS_ENABLE_REAL_SCAN=1`, invokes the upstream
  `strix.core.runner.run_strix_scan` engine (imported lazily, as a library
  call — see saas/README.md's isolation rule: we never fork engine code)
  for genuine source-aware analysis. A repository target is cloned locally
  first — via the org's connected GitHub/GitLab credential when there is
  one (`_repo_clone_url`, reusing `Integration.credential_encrypted` from
  Settings > Integrations), else a plain unauthenticated clone that only
  works for public repos — and mounted into the sandbox as a whitebox
  target; a domain target is scanned as a live web application URL. Real
  findings are read back from that run's `vulnerabilities.json` and
  translated into the same shape `MOCK_FINDINGS` already uses, so the rest
  of the pipeline (Issue creation, severity counting) doesn't need a
  real-vs-mock branch. Falls back to the mock scanner with a logged
  warning if the real engine raises (e.g. Docker/LLM credentials missing,
  or cloning fails), so the job queue never gets stuck. Uses the target
  org's `OrgLlmSettings` (model/key/base) if configured, applied via
  process env vars right before the call — see `_run_real_scan`'s
  docstring for why that's only safe as long as this module's worker loop
  stays single-scan-at-a-time (it is: `_worker_loop` below awaits each job
  before dequeuing the next).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import uuid
from . import crypto, models
from .audit import record_audit
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
        record_audit(db, pentest.org_id, pentest.created_by, "pentest.started", pentest.target_label, {"scan_mode": pentest.scan_mode})

        llm_settings = db.get(models.OrgLlmSettings, pentest.org_id)

        # Everything from here on — running the scan itself, *and* turning
        # its findings into Issue rows — is wrapped in one try/except. It
        # used to only wrap the _scan() call, so a bad finding (e.g. an
        # unexpected `severity` value hitting the dict-indexed counter
        # below) raised past this function uncaught, leaving the pentest
        # stuck in "running" forever with no finished_at — contradicting
        # this module's "the job queue never gets stuck" guarantee. Nothing
        # from a failed run gets committed: db.add() below only stages
        # rows, so a mid-loop exception discards them along with the
        # attempt, which is what we want (no partial finding sets).
        try:
            findings = await _scan(db, pentest, llm_settings)

            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for finding in findings:
                severity_counts[finding["severity"]] = severity_counts.get(finding["severity"], 0) + 1
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
            record_audit(
                db, pentest.org_id, pentest.created_by, "pentest.completed", pentest.target_label, {"severity_counts": severity_counts}
            )
        except Exception:  # noqa: BLE001 - a scan/processing bug must not strand the pentest in "running" forever
            logger.exception("scan failed for pentest %s", pentest.id)
            db.rollback()
            pentest.status = "failed"
            pentest.finished_at = utcnow()
            db.commit()
            record_audit(db, pentest.org_id, pentest.created_by, "pentest.failed", pentest.target_label)
    finally:
        db.close()


async def _scan(db, pentest: models.Pentest, llm_settings: models.OrgLlmSettings | None) -> list[dict]:
    if settings.enable_real_scan:
        try:
            return await _run_real_scan(db, pentest, llm_settings)
        except Exception:  # noqa: BLE001
            logger.exception("real scan failed for pentest %s, falling back to mock scanner", pentest.id)
    return await _run_mock_scan(pentest)


_LLM_ENV_KEYS = ("STRIX_LLM", "LLM_API_KEY", "LLM_API_BASE")


def _repo_clone_url(db, org_id: str, repo: models.Repository) -> str:
    """The URL to `git clone`, authenticated with the org's connected
    GitHub/GitLab credential when there is one (see integrations.py —
    same `Integration.credential_encrypted` used to list real repos).
    Falls back to a plain, unauthenticated HTTPS URL when the repo's
    provider isn't connected (or was connected without a credential, like
    the seeded demo integration) — that only works for public repos, same
    limitation `list_installable`'s mock-catalog fallback already has.
    """
    integration = db.query(models.Integration).filter_by(org_id=org_id, provider=repo.provider).first()
    host = "github.com" if repo.provider == "github" else "gitlab.com"
    if integration and integration.base_url:
        host = integration.base_url.removeprefix("https://").removeprefix("http://").rstrip("/")
    if integration and integration.credential_encrypted:
        token = crypto.decrypt(integration.credential_encrypted)
        auth = f"x-access-token:{token}" if repo.provider == "github" else f"oauth2:{token}"
        return f"https://{auth}@{host}/{repo.full_name}.git"
    return f"https://{host}/{repo.full_name}.git"


async def _build_scan_targets(db, pentest: models.Pentest) -> tuple[list[dict], list[dict]]:
    """Builds `run_strix_scan`'s `targets`/`local_sources` arguments for
    this pentest's target — matching the exact shape
    `strix.interface.utils.collect_local_sources`/`build_root_task` expect
    (see strix/core/inputs.py). A repository target is cloned locally
    first (source-aware/whitebox scanning — the engine reads the actual
    checked-out code, not just a URL); a domain target is a live web
    application URL, no local checkout needed.

    A repository target may also carry `extra_domain_id` (see
    models.Pentest) — a verified live domain to test *in the same run*
    alongside the source checkout. strix's `targets` is always a list, so
    this is just a second entry: the engine gets both a local source tree
    (whitebox skill loads) and a live URL (auth-flow/CORS/cookie/etc.
    findings that only exist on a deployed instance), matching what a
    combined source-review-plus-dynamic-testing engagement covers.

    It may also carry `ref` (branch/tag/commit) — passed through to the
    clone so the scan targets that exact ref instead of whatever the
    remote's default branch's HEAD happens to be right now, and falling
    back to the repository's own `default_branch` when unset. Either way,
    the commit that was *actually* cloned is recorded on the pentest as
    `resolved_commit_sha` — a bare ref name like a branch is a moving
    target, so this is what makes "what did this scan test" reproducible
    and comparable across runs.
    """
    if pentest.target_type == "repository":
        repo = db.get(models.Repository, pentest.target_id)
        if repo is None:
            raise RuntimeError(f"repository {pentest.target_id} not found")

        from strix.interface.utils import clone_repository  # lazy import: optional dependency

        clone_url = _repo_clone_url(db, pentest.org_id, repo)
        requested_ref = pentest.ref or repo.default_branch
        # git clone shells out and blocks; run off the event loop so the
        # single-scan-at-a-time worker doesn't stall other request handling.
        cloned_path, resolved_sha = await asyncio.to_thread(
            clone_repository, clone_url, pentest.id, None, requested_ref
        )
        pentest.resolved_commit_sha = resolved_sha
        db.commit()
        targets = [
            {
                "type": "repository",
                "details": {
                    "target_repo": repo.full_name,
                    "cloned_repo_path": cloned_path,
                    "workspace_subdir": repo.full_name.split("/")[-1],
                },
            }
        ]
        local_sources = [
            {"source_path": cloned_path, "workspace_subdir": repo.full_name.split("/")[-1], "protect_metadata": False}
        ]

        if pentest.extra_domain_id:
            extra_domain = db.get(models.Domain, pentest.extra_domain_id)
            if extra_domain is not None:
                targets.append(
                    {
                        "type": "web_application",
                        "details": {"target_url": f"https://{extra_domain.hostname}"},
                    }
                )

        return targets, local_sources

    if pentest.target_type == "domain":
        domain = db.get(models.Domain, pentest.target_id)
        if domain is None:
            raise RuntimeError(f"domain {pentest.target_id} not found")
        targets = [{"type": "web_application", "details": {"target_url": f"https://{domain.hostname}"}}]
        return targets, []

    raise RuntimeError(f"unsupported target_type {pentest.target_type!r}")


def _translate_real_finding(raw: dict) -> dict:
    """Normalizes one of `ReportState`'s vulnerability-report dicts (see
    strix/report/state.py's `add_vulnerability_report` — most fields are
    only added when truthy, so many are simply absent) into the fully
    populated shape `_run_pentest` expects, matching `MOCK_FINDINGS`'
    shape below so the rest of the pipeline needs no real-vs-mock branch."""
    return {
        "title": raw.get("title") or "Untitled finding",
        "description": raw.get("description") or "",
        "severity": (raw.get("severity") or "low").lower(),
        "cvss": raw.get("cvss"),
        "cvss_breakdown": raw.get("cvss_breakdown") or {},
        "technical_analysis": raw.get("technical_analysis") or "",
        "remediation_steps": raw.get("remediation_steps") or "",
        "poc_description": raw.get("poc_description") or "",
        "target": raw.get("target") or "",
        "endpoint": raw.get("endpoint") or "",
        "fix_effort": raw.get("fix_effort") or "medium",
    }


async def _run_real_scan(db, pentest: models.Pentest, llm_settings: models.OrgLlmSettings | None) -> list[dict]:
    """Invoke the upstream strix engine as a library. Requires Docker + LLM credentials.

    If `llm_settings` has a model configured, this org's model/key/base
    override the process defaults for the duration of the call, via env
    vars (the only override surface strix's engine exposes — see
    strix/config/loader.py's `load_settings()` memoization and
    strix/config/models.py's `configure_sdk_model_defaults()`; there is no
    per-call api_key/api_base parameter anywhere in `run_strix_scan`,
    `build_strix_agent`, or `RunConfig`). The previous env is restored
    afterward and strix's settings cache is invalidated both times so the
    next scan (this org's or another's) re-reads fresh values.

    This is safe ONLY because jobs.py's worker processes one scan at a
    time (`_worker_loop` awaits each job before dequeuing the next) — two
    concurrent `run_strix_scan()` calls in this process would race on this
    same global state. Don't parallelize the worker without also isolating
    each scan (e.g. one subprocess per scan) if per-org credentials matter.
    """
    from strix.config import load_settings
    from strix.config import loader as strix_config_loader
    from strix.core.paths import run_dir_for
    from strix.core.runner import run_strix_scan  # lazy import: optional dependency

    override_active = bool(llm_settings and llm_settings.model)
    previous_env = {k: os.environ.get(k) for k in _LLM_ENV_KEYS} if override_active else None

    if override_active:
        os.environ["STRIX_LLM"] = llm_settings.model
        if llm_settings.api_key:
            os.environ["LLM_API_KEY"] = llm_settings.api_key
        if llm_settings.api_base:
            os.environ["LLM_API_BASE"] = llm_settings.api_base
        elif "LLM_API_BASE" in os.environ:
            del os.environ["LLM_API_BASE"]
        strix_config_loader._cached = None

    try:
        targets, local_sources = await _build_scan_targets(db, pentest)
        scan_config = {
            "scan_id": pentest.id,
            "targets": targets,
            "run_name": pentest.id,
            "scan_mode": pentest.scan_mode,
        }
        await run_strix_scan(
            scan_config=scan_config,
            scan_id=pentest.id,
            image=load_settings().runtime.image,
            local_sources=local_sources,
        )

        vulnerabilities_path = run_dir_for(pentest.id) / "vulnerabilities.json"
        if not vulnerabilities_path.exists():
            return []
        raw_findings = json.loads(vulnerabilities_path.read_text(encoding="utf-8"))
        if not isinstance(raw_findings, list):
            return []
        return [_translate_real_finding(f) for f in raw_findings if isinstance(f, dict)]
    finally:
        if override_active and previous_env is not None:
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            strix_config_loader._cached = None


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
