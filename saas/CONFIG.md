# SaaS backend configuration

All settings are environment variables with an `SAAS_` prefix (see
`saas/backend/app/settings.py`). Defaults are chosen so the whole app runs
locally with **zero configuration** — every setting below is optional.

| Variable | Default | Effect |
|---|---|---|
| `SAAS_DATABASE_URL` | `sqlite:///./strix_saas.db` | SQLAlchemy connection string. Point at Postgres in production, e.g. `postgresql+psycopg://user:pass@host/db` |
| `SAAS_DEV_MODE` | `true` | When true: OTP codes and invitation tokens are returned directly in API responses instead of emailed; cookies aren't marked `Secure`. Set to `false` once a real email provider is wired up. |
| `SAAS_SESSION_SECRET` | insecure dev value | Change this for any non-local deployment. |
| `SAAS_FRONTEND_ORIGIN` | `http://localhost:5173` | CORS allow-origin for the frontend dev server / deployed frontend. |
| `SAAS_ENABLE_REAL_SCAN` | `false` | When true, pentests invoke the real `strix.core.runner.run_strix_scan` engine (Docker + LLM credentials required) instead of the mock scanner. Falls back to mock on any failure. |
| `SAAS_GITHUB_APP_ID`, `SAAS_GITHUB_APP_PRIVATE_KEY`, `SAAS_GITHUB_WEBHOOK_SECRET` | unset | Set all three to activate `RealGitHubProvider` (see `app/providers/github.py`) instead of the mock. Requires registering a GitHub App. |
| `SAAS_STRIPE_SECRET_KEY`, `SAAS_STRIPE_WEBHOOK_SECRET` | unset | Set to activate `RealStripeProvider` (see `app/providers/billing.py`) instead of the mock. Requires a Stripe account. |

## What's mocked by default, and why

Three things need credentials only you can provide, so they run against a
mock provider until configured:

1. **GitHub App install/OAuth + webhooks** — `MockGitHubProvider` returns a
   fixed catalog of "installable" repos and fakes check-runs/comments.
   Real version needs a registered GitHub App (App ID, private key,
   webhook secret from https://github.com/settings/apps).
2. **Stripe billing** — `MockBillingProvider` flips `card_added` locally
   with no payment processor involved. Real version needs a Stripe account
   and product/price IDs.
3. **Outbound email for OTP codes / invitations** — dev mode returns the
   code/token directly in the API response (see `SAAS_DEV_MODE`). Wiring a
   real provider (Postmark/SES/etc.) means adding a `send_email()` call in
   `app/routers/auth.py`'s `otp_start` and `app/routers/members.py`'s
   `create_invitation`, then setting `SAAS_DEV_MODE=false`.

Everything else (orgs, repos, domains, pentests, issues, PR review
settings, knowledge base, chat, tokens, audit log) is real — backed by the
actual database, no mocking involved.

## Per-org LLM configuration

Each org can set its own model/API base/API key from **Settings → LLM
Provider** in the UI (`GET`/`PATCH /api/settings/llm`, backed by the
`OrgLlmSettings` table) instead of relying on process-wide env vars. When
`SAAS_ENABLE_REAL_SCAN=1`, `app/jobs.py`'s `_run_real_scan` applies that
org's `model`/`api_key`/`api_base` as `STRIX_LLM`/`LLM_API_KEY`/
`LLM_API_BASE` immediately before calling into the strix engine, and
restores the previous env afterward. If an org hasn't configured anything,
the scan falls back to whatever process-wide `STRIX_LLM`/`LLM_API_KEY`/
`LLM_API_BASE` are set (see the root README/`docs/llm-providers/` for those).

**Why this is safe only under today's architecture, and what would break
it:** strix's LLM configuration is a process-global singleton
(`strix/config/loader.py`'s `load_settings()` memoizes once per process)
with no per-call override parameter anywhere in `run_strix_scan`,
`build_strix_agent`, or `RunConfig` — `configure_sdk_model_defaults()`
mutates `os.environ`, litellm's module globals, and the OpenAI-Agents SDK's
global defaults directly. Swapping env vars per-org is only safe because
`app/jobs.py`'s worker processes **one scan at a time** (a single
`asyncio.Queue` consumed by one loop — see its module docstring). If the
worker is ever parallelized to run multiple scans concurrently, this
approach breaks: two orgs' credentials would race. Don't do that without
also isolating each scan (e.g. one subprocess/container per scan) so each
gets its own process-global state.

**Two things flagged for hardening, not yet done:**
- `OrgLlmSettings.api_key` is stored in plaintext in the database. Encrypt
  at rest (KMS-backed field, `cryptography`'s Fernet, etc.) before any
  shared or production deployment.
- `ApiToken.expires_at` is stored and shown in the UI but **not enforced**
  — there's no bearer-token authentication path in this scaffold at all
  yet (only the session cookie is checked; see `app/deps.py`). Wire actual
  token-based auth before relying on expiration for anything.
