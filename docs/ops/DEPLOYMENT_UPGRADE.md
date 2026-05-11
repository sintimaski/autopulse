# Operator guide: upgrading Lumonox

Use this checklist when moving between `lumonox` PyPI releases or Git revisions in production-like environments.

## Preconditions

- [ ] Read release notes / changelog for the target version.
- [ ] Staging pass with the same topology as production (`LUMONOX_EVENT_STORE`, `LUMONOX_EVENT_PLANE_MODE`, metadata DB engine).
- [ ] Backup metadata DB and DuckDB / event-plane paths per `docs/ops/BACKUP_RESTORE.md`.

## Upgrade sequence (recommended)

1. **Pin traffic / drain (optional):** scale ingest consumers or enable maintenance if your platform supports it.
2. **Database migrations (non-SQLite):** run a **one-shot** migration before new code serves traffic:
   ```bash
   uv run alembic -c backend/alembic.ini upgrade head
   ```
   Keep `DATABASE_RUN_MIGRATIONS_ON_STARTUP=false` on steady-state API replicas (see `docs/ops/PRODUCTION_DEPLOYMENT.md`).
3. **Deploy new wheel / image:** install the target `lumonox` version (or deploy container digest).
4. **Restart workers / API** so lifespan picks up settings and scheduler topology.
5. **Verify:**
   - `GET /health` → `ok`
   - `GET /ready` → `ready` (or capture intentional `degraded` reasons)
   - `GET /internal/metrics` (authenticated) → `topology_profile` matches intent
   - One dashboard overview request + one `POST /ingest` smoke (project-scoped API key)

## SDK (`lumonox-sdk`) coordination

- Application dependencies often pin `lumonox-sdk` separately from the API wheel. After API upgrades, confirm optional `[stack]` pins in `sdk/pyproject.toml` still match your deployment policy (`docs/runbooks/LUMONOX_PYPI_RELEASE_CHECKLIST.md`).

## Commercial / plan tiers

- Ingest rate scaling uses `project_ui_settings.retention_plan` via `lumonox_backend.commercial.plan_limits`. After migrations that touch UI settings defaults, confirm plans in admin or DB match commercial expectations.

## Rollback

- Re-deploy the previous **image + known-good migration revision** (downgrade Alembic only when a migration is explicitly reversible—prefer forward-fix patch release).
