# Tier 3: Deterministic Baseline Scanning

Status: proposed, not yet implemented.
Owner: TBD.
Depends on: Tier 1 (mandatory-agent skill guidance) and Tier 2 (`finish_scan`
coverage checklist gate), both already shipped in `strix/skills/coordination/root_agent.md`
and `strix/tools/finish/tool.py`.

## Purpose

Tiers 1 and 2 make the orchestrating LLM agent more *likely* to cover every
required category (dependencies, secrets, access control, authentication,
injection, extension points, infrastructure) before finishing a scan — but
they are both, ultimately, instructions to a model that can still choose to
under-invest. We have direct evidence of this: three separate real scans
against the **exact same commit** of the same repository (`0cf66bd...` in
the OyeNotes target used to validate this pipeline) produced 22, 10, and 9
findings respectively, with almost no overlap between runs, and the
sparsest of the three skipped four of the five most severe findings an
external audit of the same commit identified.

Some of the categories a pentest needs to cover are not actually
judgment calls. A dependency either matches a published CVE at its pinned
version or it doesn't. A credential either appears in the git history or it
doesn't. A Kubernetes manifest either sets `allowPrivilegeEscalation: true`
or it doesn't. None of that requires an LLM to reason about business logic
or exploit chains — it requires running the right tool and reading its
output. Tier 3 moves exactly those categories out of agent discretion and
into the scan harness itself, so they run on **every** scan, unconditionally,
regardless of what the root agent decides to spawn.

## Benefits

- **Determinism.** The same commit produces the same dependency/secret/IaC
  findings every time, independent of how the LLM decomposed the task that
  run. This is the property the last three OyeNotes runs demonstrably
  lacked.
- **Speed and cost.** `trivy fs`, `gitleaks`, and a K8s/IaC linter run in
  seconds against a cloned repository. Getting the same coverage from an LLM
  agent costs an entire child agent's worth of turns (and, per the same
  evidence, is not guaranteed to happen at all).
- **Frees agent budget for genuine judgment work.** Once dependency/secret/
  IaC enumeration is handled deterministically, agents can spend their turns
  on what actually needs reasoning: reachability analysis, business-logic
  flaws, auth-flow testing, and chaining findings together — the things an
  LLM is actually good at and a static tool is not.
- **A verifiable baseline for agents to build on, not just a fallback.**
  Baseline findings are surfaced to agents (via the existing `list_reports`/
  `get_report` tools and a short summary injected into the root prompt), so
  an agent can spend a turn deepening a baseline finding — confirming
  reachability, demonstrating exploitability, chaining it with something
  else — instead of spending turns rediscovering it from scratch.
- **Closes the Tier 2 gaming gap for the categories it covers.** Right now
  `finish_scan`'s checklist only forces an agent to *say* something about
  dependencies/secrets/infrastructure; it can't tell if the statement is
  true. Once a baseline artifact exists, the checklist can be validated
  against it — an agent claiming "no vulnerable packages found" when the
  baseline scan found 14 becomes a rejected `finish_scan` call, not a
  plausible-sounding lie that gets through.
- **Reproducibility for the product's own re-scan/diff use case.** Since the
  commit-pinning feature (`Pentest.ref`/`resolved_commit_sha` in
  `saas/backend`) already lets a user re-run "the same" scan later to
  compare results, deterministic baseline categories make that comparison
  mean something — right now, re-running against an unchanged commit can
  legitimately show a completely different finding set for reasons that
  have nothing to do with the code.

## Design changes

At a high level: add a **baseline scan phase** that runs before the agent
loop starts, using tools invoked directly by the harness (not by an agent
tool call), and feed its output into the same `ReportState` /
`vulnerabilities.json` pipeline agent-filed findings already use, so nothing
downstream (saas/backend's `_run_real_scan`, the SARIF writer, the PDF/HTML
report) needs to special-case where a finding came from.

- **New module `strix/scan/baseline.py`** — one function per deterministic
  category, each taking the already-resolved local source path(s) (the same
  `local_sources` `_build_scan_targets`/`collect_local_sources` already
  produce) and returning a normalized list of findings:
  - `run_dependency_baseline(source_paths) -> list[BaselineFinding]` — wraps
    `trivy fs` (or `yarn audit`/`npm audit`/`pip-audit` per-ecosystem,
    whichever proves more reliable in practice — see Phase 0), run **once
    per workspace** in a monorepo, not once at the root.
  - `run_secret_baseline(source_paths) -> list[BaselineFinding]` — wraps
    `gitleaks detect` in git-history mode (`--log-opts="--all"`), not just a
    working-tree scan.
  - `run_iac_baseline(source_paths) -> list[BaselineFinding]` — wraps a
    Kubernetes/Docker/CI linter (candidate: `checkov` or `kube-linter`;
    decide in Phase 0) against any manifests found in the tree.

- **Execution location: host, not sandbox, for the initial version.** The
  cloned repository already exists on the host filesystem before the
  sandbox is even brought up (`_build_scan_targets` clones via
  `strix.interface.utils.clone_repository`, then `local_sources` is handed
  to `session_manager.create_or_reuse` to mount into the sandbox). Running
  baseline tools directly against that host path avoids needing any new
  sandbox-exec plumbing, and keeps failures/timeouts isolated from the
  sandbox lifecycle entirely. Running the same tools *inside* the sandbox
  instead (so results reflect exactly what the agent's own environment
  would see) is a reasonable v2 refinement, not a blocker for v1 — see
  Phase 0 for what would be needed to do that.

- **Wiring point: `strix/core/runner.py`'s `run_strix_scan()`**, immediately
  after local sources are resolved and before `build_root_task`/agent
  construction, so results exist before the root agent's first turn.

- **Findings land in `ReportState` through the existing pipeline.** Reuse
  `ReportState.add_vulnerability_report()` (the same call
  `create_vulnerability_report`/`create_dependency_report` already make),
  tagged with a new optional field (e.g. `"source": "baseline_scan"`) so
  downstream consumers can distinguish provenance without changing the
  finding shape every existing reader already expects.

- **Root agent gets a baseline summary in its prompt context.** A short,
  pre-formatted block ("Baseline scan found: 14 dependency CVEs, 2
  git-history secrets, 0 IaC issues — see `list_reports` for detail") merged
  into `scope_context`/`extra_system_prompt_context`, so the agent knows
  from turn one what's already covered.

- **New settings section.** `strix.config` gains a `baseline` section
  mirroring the existing `runtime`/`llm` sections — per-tool enable/disable,
  timeout, and binary-path override, plus a top-level
  `STRIX_BASELINE_SCAN` env toggle (default on) consistent with the existing
  `STRIX_TELEMETRY` pattern.

- **`finish_scan` validation gets stricter for the categories baseline
  covers.** For `dependencies`, `secrets`, and `infrastructure`
  specifically, cross-check the submitted `coverage_checklist` note against
  whether a baseline artifact exists and whether its findings were
  acknowledged. Exact validation rule to work out in Phase 3 (see below) —
  the direction is "the harness now knows the true answer for these three
  categories, so it can catch a false claim," not just "the agent said
  something."

- **saas/backend changes: none required for correctness.** The
  `vulnerabilities.json` contract stays the same, so `_run_real_scan`'s
  `_translate_real_finding` keeps working unmodified. Surfacing the new
  `source` tag in the UI (Phase 4) is optional polish, not a dependency.

- **Upstream-sync consideration.** Everything above lives in `strix/`, which
  this fork tracks from `usestrix/strix` (see `saas/SYNC.md`). This is a
  net-new module and additive changes to `runner.py`/`finish/tool.py`/
  `config`, not a modification of unrelated upstream logic, so it should
  merge cleanly on `git merge upstream/main` in the common case — but any
  future upstream refactor of `run_strix_scan()`'s target-resolution order
  is the most likely source of conflict, since this plan's wiring point
  depends on `local_sources` being resolved before agent construction.

## Detailed plan

### Phase 0 — Spike (small, resolve before committing to the full build)

1. Confirm `trivy`, `gitleaks`, and a candidate IaC linter are installable
   in the environment `run_strix_scan()` actually executes in (the SaaS
   backend's Python process, per `saas/backend/app/jobs.py`'s
   "isolation rule: we never fork engine code" comment) — not just assumed
   present, the way `source_aware_whitebox.md` currently assumes they're
   available to agents inside the sandbox image. If they're not already a
   dependency of `saas/backend` or the `strix` package's `real-scan` extra,
   scope adding them.
2. Decide the IaC linter: `checkov` (broad, Terraform/CFN/K8s/Docker, more
   opinionated/noisier) vs `kube-linter` (K8s-only, narrower, fewer false
   positives). Given the concrete IaC finding we're targeting
   (`allowPrivilegeEscalation`/`capabilities.add` misconfig in a K8s
   manifest) is squarely in `kube-linter`'s scope and it has a much smaller
   noise footprint, default to `kube-linter` for v1 and revisit if
   Terraform/CFN coverage is needed later.
3. Prototype one `trivy fs` run and one `gitleaks detect --log-opts="--all"`
   run against a real cloned OyeNotes checkout, by hand, and diff the output
   against the external VAPT report's V-06 through V-42 (dependency
   findings) and V-05/V-07 (secrets) to sanity-check the tool choice before
   writing any integration code.
4. Confirm expected wall-clock cost per tool on a realistic monorepo (the
   OyeNotes checkout: 4 workspaces) — this sets the timeout defaults in
   Phase 1 and informs whether host-side execution (the v1 plan) is
   actually fast enough, or whether it needs to run concurrently with
   sandbox bring-up rather than serially before it.

### Phase 1 — Baseline scan module

1. `strix/scan/baseline.py`: implement the three functions described above.
   Each:
   - Discovers every relevant manifest root under the source path(s) (every
     `package.json`/`requirements.txt`/lockfile for dependencies; the whole
     tree for secrets/IaC — no per-workspace split needed there).
   - Invokes the underlying tool via `subprocess.run` with a bounded
     timeout, `--format json`/equivalent, capturing stdout.
   - Parses tool-specific JSON into one common internal shape:
     `{title, severity, package/path, cve_ids, evidence, workspace}`.
   - **Never raises out of the module.** A missing binary, a tool crash, or
     a timeout logs a warning and returns `[]` for that category — baseline
     scanning must degrade gracefully, the same way `RequestLogMiddleware`
     in `saas/backend` already treats logging as strictly best-effort and
     never lets a logging failure break the actual request.
2. Add a thin normalization layer that maps each tool's severity scale onto
   the same four-tier (critical/high/medium/low) scale the rest of the
   product already uses, so a baseline finding is indistinguishable in
   shape from an agent-filed one by the time it reaches `ReportState`.

### Phase 2 — Wire into `run_strix_scan`

1. In `strix/core/runner.py`, after `local_sources` is resolved (existing
   code, no change to that resolution logic) and before `build_root_task`:
   call the three baseline functions (in parallel via `asyncio.gather` +
   `asyncio.to_thread`, since they're independent and each shells out).
2. Persist raw tool output to `run_dir/baseline/{trivy,gitleaks,iac}.json`
   for debugging/audit, alongside the existing `strix.log`/`vulnerabilities.json`
   artifacts a run directory already contains.
3. File each normalized finding into `ReportState` via
   `add_vulnerability_report(..., source="baseline_scan")` (or a thin
   wrapper if the extra field needs special handling — check whether
   `add_vulnerability_report`'s existing signature can take an opaque extra
   field without disrupting its dedup logic in `strix/report/dedupe.py`,
   since a baseline-filed CVE and an agent-filed one for the *same* package
   should still deduplicate against each other).
4. Build the prompt-context summary block and merge it into
   `extra_system_prompt_context` before `render_system_prompt` is called for
   the root agent.

### Phase 3 — Close the Tier 2 gaming gap

1. In `strix/tools/finish/tool.py`, extend `_validate_coverage_checklist`
   (or a new sibling function) to accept an optional baseline-findings
   count per category, sourced from `ReportState` (which now knows how many
   `source="baseline_scan"` findings exist per category after Phase 2).
2. Validation rule (exact wording to refine during implementation, but the
   shape): if baseline found N ≥ 1 findings in a category and the
   checklist's note doesn't reference having reviewed/acknowledged them
   (e.g. doesn't mention a count, a package name, or an explicit
   "reviewed and filed/rejected" statement), reject the `finish_scan` call
   with the specific discrepancy ("baseline found 14 dependency findings;
   your checklist entry doesn't account for them").
3. This only tightens the three categories baseline actually covers
   (`dependencies`, `secrets`, `infrastructure`); `access_control`,
   `authentication`, `injection`, and `extension_points` remain exactly as
   strict as Tier 2 left them, since those genuinely require judgment a
   static tool can't provide.

### Phase 4 — saas/backend + frontend surfacing (optional polish, not required for the core guarantee)

1. `saas/backend/app/jobs.py`'s `_translate_real_finding`: pass through the
   new `source` field.
2. `saas/backend/app/reports.py` (PDF/HTML report) and the frontend's Issue
   list/detail views: a small badge distinguishing "Automatically detected"
   (baseline) from "Agent-validated" (LLM-filed or LLM-deepened baseline
   finding) — improves report trust without changing report structure.
3. Pentest run-log viewer (`PentestLogViewer.tsx`, already built): surface
   the baseline phase as its own visible step so a user watching a running
   scan sees baseline results appear before agent activity starts, the same
   way the log viewer already renders `strix.log` lines live.

### Phase 5 — Testing

1. Unit tests per baseline function against small fixture repos (mirror the
   local-git-repo fixture pattern already established in
   `tests/test_clone_repository.py`): a repo with a known-vulnerable
   `package.json` pin, a repo with a secret committed then removed in a
   later commit (must still be found via history mode), a repo with a K8s
   manifest setting `allowPrivilegeEscalation: true`.
2. Integration test: run `run_strix_scan` with a mocked/no-op agent loop
   (same monkeypatching pattern as `tests/test_runner_report_state.py`) and
   assert baseline findings land in `vulnerabilities.json` even though the
   agent never calls `create_dependency_report`.
3. Regression test: baseline tool binaries missing/erroring does not fail
   the overall scan (`run_strix_scan` still completes; findings for that
   category are simply absent, with a warning in `strix.log`).
4. Regression test for Phase 3: `finish_scan` rejects a checklist that
   contradicts a known baseline finding count; accepts one that
   acknowledges it.

### Phase 6 — Rollout

1. Ship behind `STRIX_BASELINE_SCAN` (default on for the SaaS deployment;
   self-hosted users of the open-source engine get the same default but can
   opt out if they don't have the tool binaries available and don't want
   scans to warn/skip silently).
2. Document the new settings section and the three tool dependencies in
   `docs/strix-engine-architecture.md` and `saas/CONFIG.md`.
3. Re-run the OyeNotes commit (`0cf66bd...`) that was used to validate Tiers
   1 and 2, and diff the resulting `vulnerabilities.json` against the three
   prior runs (`aa3f895e`, `e1db3a9e`, `be9533141`) to confirm the
   previously-inconsistent dependency/secret/IaC findings are now identical
   across a fresh run — this is the concrete acceptance test for the whole
   plan.

## Risks and open questions

- **Tool-output noise, especially from the IaC linter.** Trivy and gitleaks
  are generally low-noise; K8s/IaC linters can flag a long tail of
  best-practice deviations that aren't real findings for this product's
  threat model. May need a severity floor (only surface high/critical from
  the linter) or an explicit allow-list of rule IDs, tuned against real
  targets, rather than surfacing everything the tool emits.
- **Performance.** Adding real subprocess scanning to every run adds
  wall-clock time before the agent even starts. Needs bounded timeouts per
  tool (Phase 0 measures realistic cost) and should not become the
  long pole for "quick" scan mode — consider skipping the IaC linter (the
  slowest/noisiest of the three) in `quick` mode and keeping it for `deep`
  only.
- **Host vs. sandbox execution drift.** Running baseline tools on the host
  means they see exactly the cloned checkout, not whatever the sandbox
  environment might additionally mutate before an agent looks at it. This
  is very unlikely to matter for read-only scanning tools, but is the
  reason Phase 0 leaves sandbox-side execution as a documented v2 option
  rather than ruling it out.
- **Dedup between baseline and agent findings.** An agent that
  independently discovers and files the same CVE the baseline scan already
  found needs to collapse into one report entry, not two — depends on
  `strix/report/dedupe.py`'s existing matching logic correctly treating a
  baseline-sourced and agent-sourced finding for the same package/CVE as
  duplicates. Needs explicit verification in Phase 1/2, not an assumption.
- **This does not close the gap for the other four categories.** Access
  control, authentication, injection, and extension-point findings — the
  majority of what the last three OyeNotes runs actually missed (the
  `/env-dump` endpoint, the Keycloak `redirect_uri` misconfig, CORS,
  MCP command execution, K8s privilege escalation is the one exception that
  *is* covered by this plan) — still depend entirely on the LLM agent
  choosing to investigate them. Tier 3 makes three of seven categories
  deterministic; the rest remain Tier 1/2's responsibility. A future tier
  for those would look less like "run a tool" and more like "make the
  root agent's minimum agent count non-negotiable," which is a different
  and harder problem than this document scopes.
