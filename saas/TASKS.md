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
- [ ] `P0-8` Set up CI (in `saas/`, namespaced workflow file), staging env, secrets management (GitHub App key, Stripe keys, LLM keys)

## Phase 1 — Auth, Organizations, Members

- [x] `P1-1` User auth — `pages/Auth/Login.tsx` (email → OTP flow, shows the dev-mode code inline since no email provider is wired up) against `app/routers/auth.py`; session state in `store/session.ts`
- [x] `P1-2` Org creation + org switcher — `pages/Auth/Onboarding.tsx` (create-org, shown when a logged-in user has no active org) + org switcher dropdown in `layout/Sidebar.tsx`
- [x] `P1-3` Roles/permissions model — `Membership.role`, `require_admin` dependency gates destructive actions (`app/deps.py`); frontend disables admin-only fields for non-admins (`GeneralSettings.tsx`)
- [x] `P1-4` `/settings/members` — `pages/Settings/MembersSettings.tsx`: team table, invite modal, pending invitations with revoke
- [x] `P1-5` `/settings` (General) — `pages/Settings/GeneralSettings.tsx`: profile block, org rename, Organization ID/Role display, Danger Zone (delete with type-to-confirm), Sign Out. 2FA toggle is rendered disabled — no verification flow behind it yet

## Phase 2 — App shell, navigation, dashboard

- [x] `P2-1` `layout/Sidebar.tsx` — matches the screenshot's nav grouping/order; Supply Chain/Networks/Integrations rendered locked (see `P2-5`)
- [x] `P2-2` `layout/TrialBanner.tsx` — reads `/api/settings/billing`, renders nothing once `card_added` or off trial
- [x] `P2-3` User footer block + org switcher in `Sidebar.tsx`; "Refer & earn" button present (no destination page — not in scope of the screenshots)
- [x] `P2-4` `pages/Dashboard/Dashboard.tsx` — 3 cards, each a plain data-driven config array, no separate component library entry (kept inline given only one caller)
- [x] `P2-5` Locked nav items render disabled with a lock icon in `Sidebar.tsx` (Supply Chain, Networks, Integrations); no actual plan-tier check yet — everything else is unconditionally unlocked, unlike the real product's plan gating

## Phase 3 — Repositories + GitHub App integration

- [x] `P3-1` `pages/Repositories/RepositoriesList.tsx` — repo name, open issues count, auto-review pill+toggle, last tested
- [x] `P3-2` "Add Repository" modal lists `GitHubProvider.installable_repositories()` (mock catalog by default, see `CONFIG.md`)
- [ ] `P3-3` GitHub App integration: `app/providers/github.py` defines the interface + working `MockGitHubProvider`; `RealGitHubProvider` is a scaffold (JWT/installation-token exchange, webhook signature verification stubbed) — needs a registered GitHub App to finish, see `CONFIG.md`
- [x] `P3-4` Per-repo settings — auto-review toggle + "Run scan" button (navigates to the new pentest's detail page) in `RepositoriesList.tsx`

## Phase 4 — PR Reviews

- [x] `P4-1` `pages/PRReviews/PRReviewsList.tsx` — status tabs with counts, matching the screenshot's 5 tabs
- [x] `P4-2` Search + status filter wired; repo dropdown/date range filters not added to the UI yet (backend supports `repository_id`); **List/Board toggle not built — list view only**
- [x] `P4-3` Empty state + "@strix" tip banner; "Connect Repository" links to `/repositories`, "Review a Pull Request" opens a manual-trigger modal
- [x] `P4-4` PR Review Settings modal — every field from the screenshot: re-review on push, target branches (add/remove chip list), approve clean PRs, block on findings + severity chips, exclude bots + excluded usernames (add/remove chip list), allow overage reviews, review cap per developer
- [ ] `P4-5` GitHub webhook receiver scaffolded (`POST /api/webhooks/github` in `app/routers/pr_reviews.py`, signature verification wired to the provider) but does not yet parse `X-GitHub-Event`/`@strix` mentions or call `trigger_pr_review` — noted inline in the handler
- [ ] `P4-6` Board (kanban) view — not built, list view only

## Phase 5 — Domains & APIs

- [x] `P5-1` `pages/Domains/DomainsList.tsx` — list + empty state
- [x] `P5-2` Add Domain modal + "Verify" button; `verify_domain` is currently a mock (marks verified immediately, see docstring) rather than a real DNS TXT/file check — swap in an actual resolver call when ready
- [ ] `P5-3` Domain detail — backend has scan history via `/api/pentests?target_type=domain`; no dedicated detail page yet, just the list + "Run scan" action
- [x] `P5-4` Scans are gated on `domain.verified` — `POST /api/domains/{id}/scan` returns 400 `domain_not_verified` otherwise (tested); frontend only shows "Run scan" once verified

## Phase 6 — Pentests

- [x] `P6-1` `pages/Pentests/PentestsList.tsx` — search, polls while any pentest is running/queued, empty state, Schedules button
- [x] `P6-2` "New Pentest" modal — target type/target/scan mode; knowledge-context selection is automatic (all scoped entries injected, see `P8-4`), not yet user-selectable
- [x] `P6-3` `pages/Pentests/PentestDetail.tsx` — status, live polling while running, severity summary, findings list linking to Issue detail. **Does not reuse the viewer's `live/` agent-graph/transcript components** — those visualize a single local run's event stream, which this backend doesn't produce (mock scanner has no step-by-step transcript); revisit once `P0-7`'s real-scan path is wired up and emits one
- [x] `P6-4` Scheduling — `SchedulesModal` in `PentestsList.tsx` (create/pause/resume/remove). Backend CRUD only — **no cron trigger loop yet**, rows are stored but nothing currently fires them on schedule
- [x] `P6-5` Pentest completion → Issues generation + Repository/Domain `last_tested_at` update — implemented and tested end-to-end in `app/jobs.py` (dedup against existing open issues is not yet implemented — every completed scan currently creates fresh `Issue` rows)

## Phase 7 — Issues

- [x] `P7-1` `pages/Issues/IssuesList.tsx` — severity summary strip, status tabs with counts, search; **List/Board toggle not built — list view only**
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

- [x] `P10-1` `pages/Settings/ApiAccessSettings.tsx` Tokens tab — table, New Token modal (shows the raw token once), revoke. No type filter dropdown built (only one token_type exists in practice so far)
- [x] `P10-2` `ApiAccessSettings.tsx` Webhooks tab — endpoint URL + event list, create/delete. Nothing currently *delivers* to these webhook URLs yet (no dispatcher on pentest/issue/PR-review events) — config-only for now
- [x] `P10-3` `pages/Settings/BillingSettings.tsx` — plan/status display, add-card button, invoices section (always empty in mock mode, `list_invoices` returns `[]`)
- [x] `P10-4` `pages/Settings/AuditLogsSettings.tsx` — activity feed. **Not plan-gated in the frontend** — accessible regardless of plan, unlike the screenshot's greyed-out state (see `P2-5`)
- [x] `P10-5` `pages/Settings/HelpSupportSettings.tsx` — static doc/support links

## Cross-cutting

- [x] `PX-1` `components/shared/`: `EmptyState`, `Modal`, `Form.tsx` (`Button`/`TextInput`/`TextArea`/`Select`/`Toggle`/`Field`), `FilterBar.tsx` (`FilterBar`/`Tabs`), `StatusPill` — reused across every list/settings page; theme tokens in `index.css` adapted from the existing viewer's palette
- [ ] `PX-2` Shared List/Board toggle component — **not built**; Issues and PR Reviews are list-view only (see `P4-6`/`P7-1`)
- [ ] `PX-3` Toast/notification system — **not built**; mutations currently show no success/error toast, only inline states (disabled buttons, error text on the login form). Worth adding once there's real async failure surface to report (webhook delivery, real-scan errors)
- [ ] `PX-4` Plan-gating/upgrade components — locked nav items exist (`P2-5`) but there's no upgrade modal/CTA behind them yet, and no actual entitlement check gating any route
- [ ] `PX-5` E2E tests for critical flows — **not built**. Verified manually end-to-end instead: backend flows via curl (OTP login → org → repo → pentest → issues → PR review → knowledge → chat → members → tokens → billing → domain-verification-gating, all passing), frontend build/typecheck clean (`tsc --noEmit`, `vite build`), and the full OTP login flow re-verified through the actual Vite dev proxy with cookies. No headless-browser tool was available in this environment to click through the rendered UI — that's the one verification step still owed before calling this production-ready.
- [x] `PX-6` Open-source boundary: everything under `saas/` is fork-only SaaS control-plane code; `strix/` stays the untouched upstream engine, invoked as a library dependency (see `saas/README.md`, `app/jobs.py`'s `_run_real_scan`)
