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
