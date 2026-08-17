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

- [ ] `P0-1` Add `upstream` remote (usestrix/strix), disable its push URL — **done**
- [ ] `P0-2` Create `saas/` isolation directory + `README.md` + `SYNC.md` — **done**
- [ ] `P0-3` Choose backend stack (FastAPI + Postgres + SQLAlchemy/Alembic, or equivalent) and scaffold `saas/backend/`
- [ ] `P0-4` Choose frontend routing/state stack (React Router + React Query/Zustand) and scaffold `saas/frontend/`
- [ ] `P0-5` Define multi-tenant data model: `Organization`, `User`, `Membership(role)`, `Repository`, `Domain`, `Pentest`, `Issue`, `PRReview`, `KnowledgeEntry`, `ApiToken`, `Webhook`, `AuditLogEntry`, `Subscription`
- [ ] `P0-6` Set up background job runner/queue for scheduled pentests, PR-review scans, chat agent runs
- [ ] `P0-7` Define the invocation contract between `saas/backend` and the upstream `strix` agent engine (inputs: repo/domain/scope/knowledge context → outputs: findings/issues) — treat `strix/` as a library dependency, never fork its code
- [ ] `P0-8` Set up CI (in `saas/`, namespaced workflow file), staging env, secrets management (GitHub App key, Stripe keys, LLM keys)

## Phase 1 — Auth, Organizations, Members

- [ ] `P1-1` User auth (email/OTP or OAuth) — reuse patterns from `strix/interface/viewer/auth.py`, extend to full account/session model
- [ ] `P1-2` Org creation + org switcher (top-left dropdown)
- [ ] `P1-3` Roles/permissions model (Admin role); gate destructive actions
- [ ] `P1-4` `/settings/members`: team members table, role badge, invite flow, pending invitations, remove/change-role
- [ ] `P1-5` `/settings` (General): profile block, 2FA toggle, org name edit+save, Organization ID display, Danger Zone (delete org + confirmation), Sign Out

## Phase 2 — App shell, navigation, dashboard

- [ ] `P2-1` Left sidebar nav (Dashboard, Pentests, Issues, PR Reviews, Supply Chain [locked], Chat, Repositories, Domains, Networks [locked], Knowledge, Integrations, Settings)
- [ ] `P2-2` Trial banner wired to subscription state; dismiss once card added
- [ ] `P2-3` User footer block + account menu; "Refer & earn" entry point
- [ ] `P2-4` Dashboard empty/get-started state: 3 onboarding cards (Run first pentest / Schedule pentests / Enable PR reviews) as a reusable component
- [ ] `P2-5` Plan-gating pattern: disable/grey nav items not in current plan tier

## Phase 3 — Repositories + GitHub App integration

- [ ] `P3-1` `/repositories` list: repo name, Issues count, Auto-Review pill, Last Tested
- [ ] `P3-2` "Add Repository" flow via GitHub App install/OAuth
- [ ] `P3-3` Backend: GitHub App manifest, install callback, store installation token per org, list accessible repos
- [ ] `P3-4` Per-repo settings: toggle auto-review, trigger manual scan, link to Pentests/Issues

## Phase 4 — PR Reviews

- [ ] `P4-1` `/pr-reviews` list with tabs (All/Awaiting Merge/Needs Attention/Merged with Open Findings/Passed) + counts
- [ ] `P4-2` Filters: search, repo dropdown, date range, List/Board toggle
- [ ] `P4-3` Empty state + "@strix" tip; "Connect Repository" / "Review a Pull Request" actions
- [ ] `P4-4` PR Review Settings modal: re-review on push, target branches, approve clean PRs, block PRs on findings + blocking severities, exclude bot accounts + usernames, allow overage reviews, review cap per developer
- [ ] `P4-5` Backend: GitHub webhook receiver, `@strix` mention parsing, check-run/status API for blocking merges, finding comments
- [ ] `P4-6` Board (kanban) view

## Phase 5 — Domains & APIs

- [ ] `P5-1` `/domains` list + empty state
- [ ] `P5-2` Add Domain flow + ownership verification (DNS TXT or file)
- [ ] `P5-3` Domain detail: discovered APIs, last scan status, linked pentests/issues
- [ ] `P5-4` Backend: verification job gating scans against unverified targets

## Phase 6 — Pentests

- [ ] `P6-1` `/pentests` list: search, status/type filters, date range, Schedules button, empty state
- [ ] `P6-2` "New Pentest" flow: target selection, scan mode, knowledge context selection
- [ ] `P6-3` Pentest run detail view (extend `RunDetails.tsx`, `PastRunsView.tsx`, `IssueSeveritySummary.tsx`, `live/` components to fetch from `saas/backend` instead of local run dir)
- [ ] `P6-4` Scheduling: recurring pentest config + Schedules management view
- [ ] `P6-5` Wire pentest completion → generate/dedup Issues, update Repository/Domain "Last Tested"

## Phase 7 — Issues

- [ ] `P7-1` `/issues` list: severity summary strip, status tabs + counts, filters, List/Board toggle
- [ ] `P7-2` Issue detail view (reuse `vulnerability/` components — CVSS, reasoning, source-to-sink trace)
- [ ] `P7-3` Issue state transitions (fixed/ignored/snoozed/reassign) + audit trail
- [ ] `P7-4` Cross-linking: issue → pentest/PR review, issue → repo/domain

## Phase 8 — Knowledge & Context

- [ ] `P8-1` `/knowledge` list + empty state
- [ ] `P8-2` "Add Knowledge" modal: Type, Description, Scope (global / repo / domain)
- [ ] `P8-3` Internal Knowledge toggle, search, scope filter
- [ ] `P8-4` Backend: store entries, feed scoped entries into agent context at run time

## Phase 9 — Chat

- [ ] `P9-1` `/chat` landing: prompt input, attachment, "Add repositories", category tabs (Web/Code/Cloud/Recon/Network/Threat Intel/Compliance)
- [ ] `P9-2` Per-category suggestion cards (data-driven prompt templates)
- [ ] `P9-3` Chat session view: streaming responses, repo context attachment, inline tool/finding rendering
- [ ] `P9-4` Backend: conversational orchestration over the `strix` agent engine, session persistence, context injection

## Phase 10 — Settings: API Access, Billing, Audit Logs

- [ ] `P10-1` `/settings/api-access` Tokens tab: table, New Token modal, type filter
- [ ] `P10-2` `/settings/api-access` Webhooks tab: endpoint URL, event subscriptions, signing secret
- [ ] `P10-3` `/settings/billing`: plan display, card management, invoice history
- [ ] `P10-4` `/settings/audit-logs`: org activity feed (plan-gated)
- [ ] `P10-5` `/settings/help-support`: contact/docs links

## Cross-cutting

- [ ] `PX-1` Design system: dark theme tokens, table, empty-state, filter-bar, modal, status-pill components
- [ ] `PX-2` Shared List/Board toggle component
- [ ] `PX-3` Toast/notification system (reuse `TrustToast.tsx` pattern)
- [ ] `PX-4` Plan-gating/upgrade components (reuse `UpgradeModal.tsx`, `ProCta.tsx`)
- [ ] `PX-5` E2E tests for critical flows (invite member, add repo, connect PR reviews, run pentest, resolve issue)
- [ ] `PX-6` Decide & document open-source boundary: `saas/` vs. upstream-shared `strix/`
