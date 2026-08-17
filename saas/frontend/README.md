# Strix SaaS frontend

React 19 + Vite + React Router + React Query + Zustand SPA for the
multi-tenant dashboard. See `../README.md` and `../TASKS.md` for the
overall SaaS build context.

Separate app from `strix/interface/viewer/frontend` (the existing local
single-run results viewer) — this one talks to `saas/backend`'s real
multi-tenant API instead of a single local run directory. A handful of
component *patterns* (severity pills, vulnerability detail layout, agent
graph/transcript) are worth porting over from that viewer as this app's
Pentest/Issue detail views grow; nothing is imported directly across the
two apps, to keep both independently buildable and upstream-sync-safe.

## Run locally

Backend must be running first (see `../backend/README.md`):

```
cd saas/frontend
npm install
npm run dev
```

Opens on `http://localhost:5173` (note: `localhost`, not `127.0.0.1` —
Vite's dev server binds IPv6 `::1` by default). `/api/*` is proxied to the
backend on `:8000` (see `vite.config.ts`).

Sign in with any email — dev mode (`SAAS_DEV_MODE=1`, the backend's
default) returns the OTP code directly in the response and displays it on
the login screen, since no email provider is configured (see
`../CONFIG.md`).
