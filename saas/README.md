# saas/

This directory holds all code for the multi-tenant `app.strix.ai`-style SaaS
control plane (orgs, billing, GitHub App integration, PR-review bot,
scheduling, chat, knowledge base, issue tracker, dashboard UI, etc.).

It is deliberately kept as a **new top-level directory, isolated from the
upstream `strix/` engine** (`strix/agents`, `strix/tools`, `strix/core`,
`strix/interface`, ...). Upstream (`usestrix/strix`) will never add files
here, so pulling upstream changes should never produce merge conflicts
against this work. See [`SYNC.md`](./SYNC.md) for the upstream-sync workflow,
and [`TASKS.md`](./TASKS.md) for the tracked build task list.

## Rules for keeping this sync-safe

1. Do not edit files under `strix/` (the upstream engine) as part of SaaS
   work. If the SaaS backend needs to invoke the agent engine, treat
   `strix/` as a dependency/library and call into it — don't fork its logic.
2. If a change to `strix/` genuinely is required (e.g. a new hook the
   backend needs), keep it minimal, isolated to its own commit, and flag it
   in the relevant task so it's tracked as a deliberate upstream-facing diff.
3. New shared config at the repo root (CI, lockfiles, etc.) should be
   additive and namespaced (e.g. `saas-ci.yml`) rather than editing
   upstream's existing root config files where avoidable.
