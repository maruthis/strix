# Strix SaaS backend

FastAPI control-plane API for the multi-tenant dashboard. See
`../README.md` and `../TASKS.md` for the overall SaaS build context, and
`../CONFIG.md` for environment variables (mock vs. real GitHub/Stripe/scan
providers).

## Run locally

```
cd saas/backend
uv sync
uv run python -m app.seed        # seeds a demo org + repo (idempotent)
uv run uvicorn app.main:app --reload --port 8000
```

`GET http://localhost:8000/api/health` should return `{"status": "ok"}`.

Data is stored in `saas/backend/strix_saas.db` (SQLite) by default. Delete
that file to reset all local data.
