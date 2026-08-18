# SaaS build tasks

Tracks the build-out of the `app.strix.ai`-style multi-tenant dashboard
described in the product screenshots. All work lives under `saas/` to stay
conflict-free with upstream (`usestrix/strix`) — see `saas/README.md` and
`saas/SYNC.md`.

Conventions:
- Check off tasks (`[x]`) as they land; leave a short note (commit sha / PR
  link) inline when useful.
- Each phase starts with an upstream-sync checkpoint.
- Task IDs (`P0-1`, `P1-3`, ...) are stable — reference them in commit
  messages/PR titles, e.g. `P4-3: PR review blocking-severities selector`.

---

## Phase 0 — Foundations & architecture decisions

- [x] `P0-1` Add `upstream` remote (usestrix/strix), disable its push URL — **done**
- [x] `P0-2` Create `saas/` isolation directory + `README.md` + `SYNC.md` — **done**
- [x] `P0-3` Backend stack: FastAPI + SQLAlchemy, SQLite by default (`DATABASE_URL` swaps to Postgres) — scaffolded in `saas/backend/`. Alembic migrations deferred (currently `Base.metadata.create_all`); add before this touches a shared environment.
- [x] `P0-4` Frontend stack: React 19 + Vite + React Router + React Query + Zustand — scaffolded in `saas/frontend/`, separate app from `strix/interface/viewer/frontend` (not imported across, kept independently buildable)
- [x] `P0-5` Data model implemented in `saas/backend/app/models.py`: `Organization`, `User`, `Membership`, `Session_`, `OtpCode`, `Invitation`, `Repository`, `Domain`, `PentestSchedule`, `Pentest`, `Issue`, `PRReview`, `PRReviewSettings`, `KnowledgeEntry`, `ChatSession`/`ChatMessage`, `ApiToken`, `Webhook`, `AuditLogEntry`, `Subscription`
- [x] `P0-6` In-process async job queue (`saas/backend/app/jobs.py`) — no Redis/Celery; started from the FastAPI lifespan in `app/main.py`
- [x] `P0-7` Invocation contract defined and implemented in `jobs.py`'s `_run_real_scan`/`_run_mock_scan`: mock scanner by default, real `strix.core.runner.run_strix_scan` behind `SAAS_ENABLE_REAL_SCAN=1` with fallback-to-mock on failure. Real-scan finding translation back into `Issue` rows is a follow-up once Docker/LLM creds are available to exercise it.
- [ ] `P0-8` CI done: `.github/workflows/saas-tests.yml` (new, namespaced, path-filtered to `saas/**` so it never touches/affects upstream's existing `build-release.yml`) runs backend pytest+coverage and frontend typecheck+vitest+coverage+build on every push/PR touching `saas/`. Staging env and secrets management (GitHub App key, Stripe keys, LLM keys) still not set up — needs real infra/accounts decisions only the operator can make

## Phase 1 — Auth, Organizations, Members

- [x] `P1-1` User auth — `pages/Auth/Login.tsx` (email → OTP flow, shows the dev-mode code inline since no email provider is wired up) against `app/routers/auth.py`; session state in `store/session.ts`
- [x] `P1-2` Org creation + org switcher — `pages/Auth/Onboarding.tsx` (create-org, shown when a logged-in user has no active org) + org switcher dropdown in `layout/Sidebar.tsx`
- [x] `P1-3` Roles/permissions model — `Membership.role`, `require_admin` dependency gates destructive actions (`app/deps.py`); frontend disables admin-only fields for non-admins (`GeneralSettings.tsx`)
- [x] `P1-4` `/settings/members` — `pages/Settings/MembersSettings.tsx`: team table, invite modal, pending invitations with revoke
- [x] `P1-5` `/settings` (General) — `pages/Settings/GeneralSettings.tsx`: profile block, org rename, Organization ID/Role display, Danger Zone (delete with type-to-confirm), Sign Out. 2FA toggle is rendered disabled — no verification flow behind it yet

## Phase 2 — App shell, navigation, dashboard

- [x] `P2-1` `layout/Sidebar.tsx` — matches the screenshot's nav grouping/order; Supply Chain/Networks rendered locked, Integrations unlocked (see `P2-5`/`P10-7`)
- [x] `P2-2` `layout/TrialBanner.tsx` — reads `/api/settings/billing`, renders nothing once `card_added` or off trial
- [x] `P2-3` User footer block + org switcher in `Sidebar.tsx`; "Refer & earn" button present (no destination page — not in scope of the screenshots)
- [x] `P2-4` `pages/Dashboard/Dashboard.tsx` — 3 cards, each a plain data-driven config array, no separate component library entry (kept inline given only one caller)
- [x] `P2-5` Locked nav items render disabled with a lock icon in `Sidebar.tsx` (Supply Chain, Networks); no actual plan-tier check yet — everything else is unconditionally unlocked, unlike the real product's plan gating

## Phase 3 — Repositories + GitHub App integration

- [x] `P3-1` `pages/Repositories/RepositoriesList.tsx` — repo name, open issues count, auto-review pill+toggle, last tested
- [x] `P3-2` "Add Repository" modal lists `GitHubProvider.installable_repositories()` (mock catalog by default, see `CONFIG.md`)
- [ ] `P3-3` GitHub App integration: `app/providers/github.py` defines the interface + working `MockGitHubProvider`; `RealGitHubProvider` is a scaffold (JWT/installation-token exchange, webhook signature verification stubbed) — needs a registered GitHub App to finish, see `CONFIG.md`
- [x] `P3-4` Per-repo settings — auto-review toggle + "Run scan" button (navigates to the new pentest's detail page) in `RepositoriesList.tsx`

## Phase 4 — PR Reviews

- [x] `P4-1` `pages/PRReviews/PRReviewsList.tsx` — status tabs with counts, matching the screenshot's 5 tabs
- [x] `P4-2` Search + status filter wired; repo dropdown/date range filters not added to the UI yet (backend supports `repository_id`); List/Board toggle now built (see `PX-2`)
- [x] `P4-3` Empty state + "@strix" tip banner; "Connect Repository" links to `/repositories`, "Review a Pull Request" opens a manual-trigger modal
- [x] `P4-4` PR Review Settings modal — every field from the screenshot: re-review on push, target branches (add/remove chip list), approve clean PRs, block on findings + severity chips, exclude bots + excluded usernames (add/remove chip list), allow overage reviews, review cap per developer
- [x] `P4-5` GitHub webhook receiver (`POST /api/webhooks/github` in `app/routers/pr_reviews.py`) now parses `X-GitHub-Event` for `pull_request` (opened/reopened/synchronize) and `issue_comment` with an `@strix` mention, resolves the target org/repo by `full_name`, applies `rereview_on_push`/`target_branches`/`exclude_bot_accounts`/`excluded_usernames` from settings before running, and calls the same `_run_pr_review()` the manual trigger uses (refactored out of `trigger_pr_review` so both paths share one implementation). Tested via curl against all branches (unregistered repo, opened, synchronize with re-review-on-push off, comment without/with `@strix`, unrelated event)
- [x] `P4-6` Board (kanban) view — `components/shared/Board.tsx` + `ViewToggle.tsx`, columns by status

## Phase 5 — Domains & APIs

- [x] `P5-1` `pages/Domains/DomainsList.tsx` — list + empty state
- [x] `P5-2` Add Domain modal + "Verify" button; `verify_domain` is currently a mock (marks verified immediately, see docstring) rather than a real DNS TXT/file check — swap in an actual resolver call when ready
- [x] `P5-3` `pages/Domains/DomainDetail.tsx` — verification instructions (token + method), verify/scan actions, scan history (`GET /api/pentests?target_type=domain&target_id=`, added `target_id` filter), open findings (`GET /api/issues?domain_id=`, added that filter). Also added `GET /api/domains/{id}` backend endpoint this page needed
- [x] `P5-4` Scans are gated on `domain.verified` — `POST /api/domains/{id}/scan` returns 400 `domain_not_verified` otherwise (tested); frontend only shows "Run scan" once verified

## Phase 6 — Pentests

- [x] `P6-1` `pages/Pentests/PentestsList.tsx` — search, polls while any pentest is running/queued, empty state, Schedules button
- [x] `P6-2` "New Pentest" modal — target type/target/scan mode; knowledge-context selection is automatic (all scoped entries injected, see `P8-4`), not yet user-selectable
- [x] `P6-3` `pages/Pentests/PentestDetail.tsx` — status, live polling while running, severity summary, findings list linking to Issue detail. **Does not reuse the viewer's `live/` agent-graph/transcript components** — those visualize a single local run's event stream, which this backend doesn't produce (mock scanner has no step-by-step transcript); revisit once `P0-7`'s real-scan path is wired up and emits one
- [x] `P6-4` Scheduling — `SchedulesModal` in `PentestsList.tsx` (create/pause/resume/remove). Backend CRUD only — **no cron trigger loop yet**, rows are stored but nothing currently fires them on schedule
- [x] `P6-5` Pentest completion → Issues generation + Repository/Domain `last_tested_at` update — implemented and tested end-to-end in `app/jobs.py` (dedup against existing open issues is not yet implemented — every completed scan currently creates fresh `Issue` rows)

## Phase 7 — Issues

- [x] `P7-1` `pages/Issues/IssuesList.tsx` — severity summary strip, status tabs with counts, search, List/Board toggle (board groups by status, ignores the tab filter)
- [x] `P7-2` `pages/Issues/IssueDetail.tsx` — description/technical analysis/PoC/remediation, CVSS, status changer. Simpler than the viewer's `vulnerability/*` set (no code diff rendering, no markdown/syntax highlighting) — those components render fields (`code_before`/`code_after`, `poc_script_code`) the mock scanner doesn't populate yet; port `CodeDiffBlock`/`MdCodeBlock`/`PocBlock` in once real findings carry that data
- [x] `P7-3` Issue state transitions — `PATCH /api/issues/{id}/status` (validated against `VALID_STATUSES`) + audit log entry; no reassignment field/flow yet (no "assignee" concept in the model)
- [x] `P7-4` Cross-linking — `Issue` rows carry `pentest_id`/`pr_review_id`/`repository_id`/`domain_id` foreign keys

## Phase 8 — Knowledge & Context

- [x] `P8-1` `pages/Knowledge/KnowledgeList.tsx` — list + empty state
- [x] `P8-2` "Add Knowledge" modal — type, description, scope (global/repository/domain with a target picker)
- [x] `P8-3` Search wired to the backend `search` param. **"Internal Knowledge" toggle from the screenshot not built** — unclear what distinct dataset it should filter to vs. org knowledge; left out rather than guessing
- [x] `P8-4` `relevant_entries()` in `knowledge.py` resolves global + repo/domain-scoped entries; wired into `chat.py`'s mock reply. **Not yet wired into `jobs.py`'s scan path** — real-scan findings won't see knowledge context until `_run_real_scan` is filled in (see `P0-7`)

## Phase 9 — Chat

- [x] `P9-1` `pages/Chat/Chat.tsx` — prompt input, category chips (all 7), "Add repositories" affordance is a static button (doesn't yet attach a repo_id to the request — `NewMessageIn.repository_ids` exists on the backend but nothing in the UI sets it)
- [x] `P9-2` Per-category suggestion cards — `SUGGESTIONS` dict in `app/routers/chat.py`, matches the screenshot's Web-tab cards; other categories have placeholder cards, expand as needed
- [x] `P9-3` Chat session view — message thread, session created lazily on first send. No streaming (mock reply returns synchronously, not token-by-token); no inline tool/finding rendering (nothing for the mock reply to render yet)
- [ ] `P9-4` Real conversational orchestration over the `strix` engine is **not implemented** — `_mock_agent_reply()` returns a canned response; wiring a real LLM/agent reply requires the same Docker/LLM setup as `P0-7`

## Phase 10 — Settings: API Access, Billing, Audit Logs

- [x] `P10-1` `pages/Settings/ApiAccessSettings.tsx` Tokens tab — table (name/scopes/expiry/status/actions), Create API Token modal matching the app.strix.ai screenshots: Name, Token Type (personal/service), full grouped **Scopes** checklist (scans, vulnerabilities, dependencies, supply chain, schedules, assets, pr_reviews, organization, invitations, api access, audit — 24 scopes total), **Expiration** dropdown (90/30/60/365 days or none), revoke. Backend: `ApiToken.expires_at` added and returned; **still not enforced** — there's no bearer-token auth path at all in this scaffold, only the session cookie is checked (see `app/deps.py`), so expiration is stored/displayed only until that's built. No token-type filter dropdown on the list view itself.
- [x] `P10-2` `ApiAccessSettings.tsx` Webhooks tab — endpoint URL + full **Events** checklist matching the screenshots (scan.created/completed/failed/cancelled, vulnerability.created/status_changed/severity_changed, plus "All events" `*` which clears other selections and vice versa), create/delete. Nothing currently *delivers* to these webhook URLs yet (no dispatcher on pentest/issue/PR-review events) — config-only for now
- [x] `P10-3` `pages/Settings/BillingSettings.tsx` — plan/status display, add-card button, invoices section (always empty in mock mode, `list_invoices` returns `[]`)
- [x] `P10-4` `pages/Settings/AuditLogsSettings.tsx` — activity feed. **Not plan-gated in the frontend** — accessible regardless of plan, unlike the screenshot's greyed-out state (see `P2-5`)
- [x] `P10-5` `pages/Settings/HelpSupportSettings.tsx` — static doc/support links
- [x] `P10-6` **Per-org LLM configuration** — new `Settings → LLM Provider` page (`pages/Settings/LlmProviderSettings.tsx`) lets each org set its own model/API base/API key instead of relying on the server's process-wide `STRIX_LLM`/`LLM_API_KEY`/`LLM_API_BASE`. Backend: `OrgLlmSettings` table, `GET`/`PATCH /api/settings/llm` (admin-only to write; key is never round-tripped to the browser, only `api_key_set`/`api_key_last4`). `app/jobs.py`'s `_run_real_scan` applies the target org's model/key/base as env vars immediately before calling the strix engine and restores the previous env afterward, invalidating strix's `load_settings()` cache both times.
  **Important constraint, documented in `saas/CONFIG.md`:** strix's LLM config is a process-global singleton with no per-call override anywhere in `run_strix_scan`/`build_strix_agent`/`RunConfig` (confirmed by reading `strix/config/loader.py` and `strix/config/models.py`). Swapping env vars per-org is safe *only* because `jobs.py`'s worker processes one scan at a time. If the worker is ever parallelized to run concurrent scans, this breaks — two orgs' credentials would race — and would need per-scan process/container isolation instead. `OrgLlmSettings.api_key` is also stored in plaintext (flagged for encryption-at-rest before any shared/production deployment).
- [x] `P10-7` **Integrations page** (`pages/Integrations/IntegrationsList.tsx`) — previously a locked nav placeholder, now fully built and unlocked, matching the app.strix.ai screenshots: three sections (Code Providers: GitHub/GitLab/Bitbucket, Communication: Slack/Microsoft Teams, Issue Tracking: Jira/Linear), each row showing Connected status + account label or a Connect button; Microsoft Teams stays a static "Coming soon" row (matching the screenshot), rejected server-side too if POSTed directly. Backend: new `Integration` model/table (`org_id`, `provider`, `account_label`, `connected_at`, unique per org+provider) and `app/routers/integrations.py` (`GET/POST /api/integrations/{provider}/connect`, `DELETE /api/integrations/{provider}`, all writes admin-gated). Like the GitHub App/Stripe integrations, there's no real OAuth handshake behind "Connect" — it's a real per-org DB row, but `account_label` is a mock value derived from the org's name rather than a token exchange, since that requires a registered app with each provider that only the deployment operator can create. The demo org seed now includes a connected GitHub integration (`account_label="maruthis"`) matching the screenshots. "Connect more"/"Configure" on the GitHub row link to the Repositories page (the real place installed repos are managed); other providers only expose Connect/Disconnect since there's no per-provider management surface built yet.
- [x] `P10-8` **PR Reviews page gets a "Connect Repository" button** (matching the screenshot) that opens the same repo-connect modal as the Repositories page — extracted to `components/shared/AddRepositoryModal.tsx` and reused by both. The "Review a Pull Request" modal's repository picker was also redesigned from a `<select>` dropdown to a searchable list of connected repos with a GitHub icon per row (matching the screenshot's "Select a connected repository…" step), with a "Change" link to go back and re-pick before entering the PR number/title.

## Cross-cutting

- [x] `PX-1` `components/shared/`: `EmptyState`, `Modal`, `Form.tsx` (`Button`/`TextInput`/`TextArea`/`Select`/`Toggle`/`Field`), `FilterBar.tsx` (`FilterBar`/`Tabs`), `StatusPill`, `ViewToggle`, `Board`, `Toast` — reused across every list/settings page; theme tokens in `index.css` adapted from the existing viewer's palette
- [x] `PX-2` `components/shared/ViewToggle.tsx` + `Board.tsx` — used by Issues and PR Reviews (`P7-1`/`P4-6`); board mode always fetches/groups by the full status set regardless of the active list-mode tab filter
- [x] `PX-3` `components/shared/Toast.tsx` — zustand-backed toast store + `<Toaster/>` mounted once in `main.tsx`. Errors are wired globally via `QueryClient`'s `MutationCache.onError` (every failed mutation across the app surfaces a toast automatically, no per-call wiring needed); success toasts added explicitly to the key confirmable actions (add repo/domain, verify domain, invite member, create/revoke token, create/delete webhook, add/remove knowledge, trigger PR review, change issue status, add card, rename/delete org, add/remove pentest schedule)
- [ ] `PX-4` Plan-gating/upgrade components — locked nav items exist for Supply Chain/Networks (`P2-5`) but there's no upgrade modal/CTA behind them yet, and no actual entitlement check gating any route
- [x] `PX-5` Automated test suites, not end-to-end browser tests specifically (still no headless-browser tool in this environment — see below). Backend: `saas/backend/tests/` — 163 pytest tests against a real per-test SQLite DB and a real FastAPI lifespan (job queue actually runs), **100% line coverage**, `fail_under=95` enforced in `pyproject.toml`. Frontend: `saas/frontend/src/**/*.test.tsx` — 194 Vitest + React Testing Library tests against every component/page with mocked `fetch`, **99.79% statement/line, 97.5% branch, 93.54% function coverage**, thresholds enforced in `vite.config.ts`. Writing these surfaced and fixed two real backend bugs: a cross-event-loop bug in the job queue's module-global `asyncio.Queue` (broke under multiple app lifespans in one process, e.g. tests), and pentests getting stuck in `"running"` forever on an unhandled scan exception instead of being marked `"failed"`. What's still not covered: true end-to-end browser tests (Playwright/Cypress) clicking through the real rendered UI against the real backend — see `saas/README.md`'s "Running locally" flow for manual verification steps instead.
- [x] `PX-6` Open-source boundary: everything under `saas/` is fork-only SaaS control-plane code; `strix/` stays the untouched upstream engine, invoked as a library dependency (see `saas/README.md`, `app/jobs.py`'s `_run_real_scan`)
- [x] `PX-7` Code-review pass (6-angle multi-agent review of `upstream/main...HEAD -- saas/`) and fixes:
  - **Admin-vs-member gating was inconsistent** across routers — several "security posture" endpoints (API token create/revoke, webhook create/delete, PR-review settings PATCH, repository update/remove, domain remove, pentest-schedule create/toggle/delete) had no `require_admin` dependency, letting any member silently change org-wide security config or disable scheduled scans. Fixed by applying `require_admin` consistently to posture-changing endpoints while keeping day-to-day actions (run scan, add repo/domain, verify domain) member-open. Verified live via `dev.sh`-equivalent: a real member gets 403 on every gated endpoint and still succeeds on the open ones.
  - **N+1 queries** in `repositories.py` (`open_issues_count` per repo), `pr_reviews.py` (`repository_full_name` per review), and `issues.py` (3 full-table scans for severity/status counts) replaced with batched/grouped aggregate queries.
  - **Webhook signing secret** was returned on every `GET`/list call, not just at creation. Fixed to the same "shown once" pattern already used for API tokens.
  - **`jobs.py`'s exception handling** only wrapped the `_scan()` call, not the findings→`Issue` processing loop — a malformed finding (or any error while writing results) left the pentest stuck in `"running"` forever. Widened the try/except to cover the whole post-scan body, with a `db.rollback()` before marking `"failed"` so nothing partial gets committed.
  - **OTP brute-force**: `otp_verify` had no attempt limit — added a per-code `attempts` counter (max 5) that locks that code out with `429`, without needing global rate-limiting middleware.
  - **Invitations never expired.** Added `Invitation.expires_at` (7-day default); `accept_invitation` now rejects expired invites with `410`.
  - **`create_org` didn't set the new org as the session's active org** unless the caller separately called `switch-org`; fixed so a fresh org is immediately usable.
  - **Billing/GitHub "real provider" paths silently 500'd** when only partially configured (e.g. a Stripe key set but no real provider wired in). Now return `501 billing_provider_not_fully_configured` / `github_app_not_fully_configured`.
  - **Frontend**: `BillingSettings.tsx`'s trial-end date used a local `toLocaleDateString()` call instead of the shared `formatDate` helper; `PRReviewsList.tsx` and `KnowledgeList.tsx` fired a network request on every search keystroke instead of debouncing — both fixed, with a new `lib/useDebouncedValue.ts` hook.
  - Explicitly declined as out-of-scope for this pass (tracked, not silently dropped): a get-or-404/ownership-check helper to dedupe ~20 near-identical call sites (real duplication, but refactoring it now risks regressions without a corresponding ask); building real bearer-token auth to enforce `ApiToken.expires_at` (already a documented gap, see `P10-1`).
  - Backend: 155 tests, 100% coverage. Frontend: 187 tests, 99.78% statement coverage. Both re-verified after every fix.
