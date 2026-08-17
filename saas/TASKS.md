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
- [ ] `P0-4` Choose frontend routing/state stack (React Router + React Query/Zustand) and scaffold `saas/frontend/`
- [x] `P0-5` Data model implemented in `saas/backend/app/models.py`: `Organization`, `User`, `Membership`, `Session_`, `OtpCode`, `Invitation`, `Repository`, `Domain`, `PentestSchedule`, `Pentest`, `Issue`, `PRReview`, `PRReviewSettings`, `KnowledgeEntry`, `ChatSession`/`ChatMessage`, `ApiToken`, `Webhook`, `AuditLogEntry`, `Subscription`
- [x] `P0-6` In-process async job queue (`saas/backend/app/jobs.py`) — no Redis/Celery; started from the FastAPI lifespan in `app/main.py`
- [x] `P0-7` Invocation contract defined and implemented in `jobs.py`'s `_run_real_scan`/`_run_mock_scan`: mock scanner by default, real `strix.core.runner.run_strix_scan` behind `SAAS_ENABLE_REAL_SCAN=1` with fallback-to-mock on failure. Real-scan finding translation back into `Issue` rows is a follow-up once Docker/LLM creds are available to exercise it.
- [ ] `P0-8` Set up CI (in `saas/`, namespaced workflow file), staging env, secrets management (GitHub App key, Stripe keys, LLM keys)

## Phase 1 — Auth, Organizations, Members

- [ ] `P1-1` User auth — backend done (`app/routers/auth.py`: OTP start/verify, session cookie, dev-mode code passthrough per `CONFIG.md`); frontend login screen pending
- [ ] `P1-2` Org creation + org switcher — backend done (`app/routers/orgs.py`, `auth.py`'s `switch-org`); frontend dropdown pending
- [x] `P1-3` Roles/permissions model — `Membership.role`, `require_admin` dependency gates destructive actions (`app/deps.py`)
- [ ] `P1-4` `/settings/members` — backend done (`app/routers/members.py`: list, invite, revoke, accept, role update, remove); frontend table/modal pending
- [ ] `P1-5` `/settings` (General) — org rename/delete backend done (`app/routers/orgs.py`); 2FA toggle field exists on `User` model but has no verification flow yet; frontend page pending

## Phase 2 — App shell, navigation, dashboard

- [ ] `P2-1` Left sidebar nav (Dashboard, Pentests, Issues, PR Reviews, Supply Chain [locked], Chat, Repositories, Domains, Networks [locked], Knowledge, Integrations, Settings)
- [ ] `P2-2` Trial banner wired to subscription state; dismiss once card added
- [ ] `P2-3` User footer block + account menu; "Refer & earn" entry point
- [ ] `P2-4` Dashboard empty/get-started state: 3 onboarding cards (Run first pentest / Schedule pentests / Enable PR reviews) as a reusable component
- [ ] `P2-5` Plan-gating pattern: disable/grey nav items not in current plan tier

## Phase 3 — Repositories + GitHub App integration

- [ ] `P3-1` `/repositories` list — backend done (`app/routers/repositories.py`, includes `open_issues_count`/`last_tested_at`); frontend table pending
- [ ] `P3-2` "Add Repository" flow — backend done against `GitHubProvider.installable_repositories()` (mock catalog by default, see `CONFIG.md`); frontend picker pending
- [ ] `P3-3` GitHub App integration: `app/providers/github.py` defines the interface + working `MockGitHubProvider`; `RealGitHubProvider` is a scaffold (JWT/installation-token exchange, webhook signature verification stubbed) — needs a registered GitHub App to finish, see `CONFIG.md`
- [ ] `P3-4` Per-repo settings — backend done (toggle auto-review, `POST /{id}/scan` manual trigger); frontend pending

## Phase 4 — PR Reviews

- [ ] `P4-1` `/pr-reviews` list with tabs — backend done (`app/routers/pr_reviews.py` `list_pr_reviews`, status counts per tab); frontend pending
- [ ] `P4-2` Filters — backend supports `status`, `repository_id`, `search`; date range and List/Board toggle are frontend-only, pending
- [ ] `P4-3` Empty state + tip / actions — backend done (`POST /api/pr-reviews` manual trigger); frontend pending
- [ ] `P4-4` PR Review Settings — backend done (`GET`/`PATCH /api/pr-reviews/settings`, `PRReviewSettings` model has every field from the screenshot); frontend modal pending
- [ ] `P4-5` GitHub webhook receiver scaffolded (`POST /api/webhooks/github` in `app/routers/pr_reviews.py`, signature verification wired to the provider) but does not yet parse `X-GitHub-Event`/`@strix` mentions or call `trigger_pr_review` — noted inline in the handler
- [ ] `P4-6` Board (kanban) view — frontend-only, pending

## Phase 5 — Domains & APIs

- [ ] `P5-1` `/domains` list — backend done (`app/routers/domains.py`); frontend pending
- [ ] `P5-2` Add Domain flow — backend done; `verify_domain` is currently a mock (marks verified immediately, see docstring) rather than a real DNS TXT/file check — swap in an actual resolver call when ready
- [ ] `P5-3` Domain detail — backend has scan history via `/api/pentests?target_type=domain`; frontend detail page pending
- [x] `P5-4` Scans are gated on `domain.verified` — `POST /api/domains/{id}/scan` returns 400 `domain_not_verified` otherwise (tested)

## Phase 6 — Pentests

- [ ] `P6-1` `/pentests` list — backend done (`app/routers/pentests.py`, filters by status/target_type); frontend pending
- [ ] `P6-2` "New Pentest" flow — backend done (`POST /api/pentests`, enqueues onto the job worker); knowledge-context selection is automatic (all scoped entries injected, see `P8-4`), not yet user-selectable; frontend form pending
- [ ] `P6-3` Pentest run detail view — backend serves `GET /api/pentests/{id}` + `/issues`; live agent-graph/transcript view (reusing `RunDetails.tsx`/`live/*`) is frontend-only work, pending
- [ ] `P6-4` Scheduling — backend CRUD done (`schedules_router` in `pentests.py`: create/list/toggle/delete `PentestSchedule` rows); **no cron trigger loop yet** — rows are stored but nothing currently fires them on schedule; frontend pending
- [x] `P6-5` Pentest completion → Issues generation + Repository/Domain `last_tested_at` update — implemented and tested end-to-end in `app/jobs.py` (dedup against existing open issues is not yet implemented — every completed scan currently creates fresh `Issue` rows)

## Phase 7 — Issues

- [ ] `P7-1` `/issues` list — backend done (`app/routers/issues.py`: severity counts, status counts, filters); frontend list/tabs pending
- [ ] `P7-2` Issue detail view — backend serves full finding fields (cvss_breakdown, technical_analysis, poc, code diff fields); frontend detail page (reusing `vulnerability/*`) pending
- [x] `P7-3` Issue state transitions — `PATCH /api/issues/{id}/status` (validated against `VALID_STATUSES`) + audit log entry; no reassignment field/flow yet (no "assignee" concept in the model)
- [x] `P7-4` Cross-linking — `Issue` rows carry `pentest_id`/`pr_review_id`/`repository_id`/`domain_id` foreign keys

## Phase 8 — Knowledge & Context

- [ ] `P8-1` `/knowledge` list — backend done (`app/routers/knowledge.py`); frontend pending
- [ ] `P8-2` "Add Knowledge" modal — backend done (type/description/scope validated); frontend modal pending
- [ ] `P8-3` Search/scope filter — backend supports `search`/`scope_type` query params; frontend "Internal Knowledge" toggle pending
- [x] `P8-4` `relevant_entries()` in `knowledge.py` resolves global + repo/domain-scoped entries; wired into `chat.py`'s mock reply. **Not yet wired into `jobs.py`'s scan path** — real-scan findings won't see knowledge context until `_run_real_scan` is filled in (see `P0-7`)

## Phase 9 — Chat

- [ ] `P9-1` `/chat` landing — backend done (`GET /api/chat/suggestions` returns the 7 categories); frontend UI pending
- [x] `P9-2` Per-category suggestion cards — `SUGGESTIONS` dict in `app/routers/chat.py`, matches the screenshot's Web-tab cards; other categories have placeholder cards, expand as needed
- [ ] `P9-3` Chat session view — backend done (session/message CRUD, `app/routers/chat.py`); frontend pending. No streaming yet (mock reply returns synchronously, not token-by-token)
- [ ] `P9-4` Real conversational orchestration over the `strix` engine is **not implemented** — `_mock_agent_reply()` returns a canned response; wiring a real LLM/agent reply requires the same Docker/LLM setup as `P0-7`

## Phase 10 — Settings: API Access, Billing, Audit Logs

- [ ] `P10-1` Tokens — backend done (`app/routers/tokens.py`: create returns raw token once, list shows prefix only, revoke); frontend table/modal pending
- [ ] `P10-2` Webhooks — backend done (`app/routers/webhooks.py`: org-owned outbound webhook config, separate from the inbound `/api/webhooks/github` receiver); frontend pending. Nothing currently *delivers* to these webhook URLs yet (no dispatcher on pentest/issue/PR-review events) — config-only for now
- [ ] `P10-3` Billing — backend done against `BillingProvider` (mock by default, see `CONFIG.md`); `list_invoices` always returns `[]` in mock mode; frontend pending
- [ ] `P10-4` Audit logs — backend done (`app/routers/audit.py`, entries recorded from orgs/members/issues/tokens routers); frontend page + plan-gating pending
- [ ] `P10-5` Help & Support — no backend needed (static links); frontend pending

## Cross-cutting

- [ ] `PX-1` Design system: dark theme tokens, table, empty-state, filter-bar, modal, status-pill components
- [ ] `PX-2` Shared List/Board toggle component
- [ ] `PX-3` Toast/notification system (reuse `TrustToast.tsx` pattern)
- [ ] `PX-4` Plan-gating/upgrade components (reuse `UpgradeModal.tsx`, `ProCta.tsx`)
- [ ] `PX-5` E2E tests for critical flows (invite member, add repo, connect PR reviews, run pentest, resolve issue)
- [ ] `PX-6` Decide & document open-source boundary: `saas/` vs. upstream-shared `strix/`
