# CLAUDE.md — `frontend/`

Authoritative rules: **`.cursor/rules/frontend-next.mdc`** and **`.cursor/rules/dashboard-static-export.mdc`** (apply whenever editing `frontend/**/*.{ts,tsx,js,jsx}`).

Headline constraints (read the rule files for the full text):

- Canonical dashboard delivery is the **Next.js static export** (`npm run build` → `frontend/out/`) with `basePath` **`/lumonox/ui`**. Do not rely on `next start` for full-stack validation unless the task is Next-only.
- The FastAPI backend mounts the export at **`/lumonox/ui/`** via `LUMONOX_FRONTEND_STATIC_DIR`; the `lumonox` PyPI wheel bundles the last built export under `lumonox_backend/dashboard_static/`. The integration hook is `backend/src/lumonox_backend/dashboard/static_export_mount.py` — keep the rule and the module in sync when behavior changes.
- Optimize overview for **fast diagnosis in ~5 seconds**; avoid MVP scope creep into heavy configurability.
- Keep loading/refresh behavior non-disruptive after first paint (preserve prior data while refreshing).
- Prefer clear empty / error states and keyboard-accessible interactions.
- Keep API payload assumptions aligned with backend contracts in `DEVELOPMENT.md`.
- Before final handoff on frontend changes: run targeted lint and tests, **plus `npm run build`** so the static export succeeds. Mention the build in the verification section.

Related rules:

- `.cursor/rules/lumonox-product.mdc` — dashboard / MVP product principles.
- `.cursor/rules/tests-validation.mdc` — when editing `frontend/**/tests/**` or `*.test.{ts,tsx}`.
