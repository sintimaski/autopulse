# Backup and restore

AutoPulse durable state may include:

- **SQL metadata** (`DATABASE_URL`): projects, API key hashes, dashboard sessions, aggregate tables, idempotency keys, dead-letter rows, etc.
- **DuckDB event store** (`AUTOPULSE_EVENT_STORE=duckdb`, path from `AUTOPULSE_DUCKDB_PATH` / settings): raw request/error payloads used by dashboard queries. Relative paths resolve under the **data root** (`AUTOPULSE_DATA_DIR`, `AUTOPULSE_PROJECT_ROOT`, or monorepo parent of `backend/`—see `resolve_autopulse_data_root` in `backend/src/autopulse_backend/core/config.py`), never raw process cwd.

### Migrating from cwd-relative DuckDB files

If you previously ran the API or tools from different directories, you may have **multiple** `.autopulse/events.duckdb` files (for example under `backend/.autopulse/` and repo root `.autopulse/`). After upgrading:

1. Pick the file that contains the events you care about (inspect size / `mtime` / row counts).
2. Set `AUTOPULSE_DUCKDB_PATH` to an **absolute** path pointing at that file, **or** move/copy it to `{data_root}/.autopulse/events.duckdb` where `data_root` is your chosen `AUTOPULSE_DATA_DIR` / monorepo root.
3. Remove or archive stale copies to avoid confusion.
- **SQLite files** when used for metadata (including WAL/SHM sidecars).

## Backup

1. **Pause writes** (stop app workers or put the service in maintenance) for a crash-consistent snapshot, **or** use engine-native backup tools while accepting best-effort consistency for dev environments.
2. Copy the **SQL database file(s)** and the **DuckDB file** together; label the pair with a timestamp and schema revision (`alembic_version` / migration id).
3. Export any **email outbox** directory if you rely on file-based alert delivery (`ALERT_EMAIL_FILE_OUTBOX_DIR`).

## Restore

1. Restore SQL + DuckDB files to the configured paths.
2. Run migrations to the expected head if restoring onto a newer binary (`uv run alembic upgrade head` for Postgres-oriented flows; SQLite file-backed dev DBs often use `create_all`—match how the environment was created).
3. Verify `/ready`, send a synthetic ingest batch, and replay aggregate dead letters if operators used that path during the incident (`uv run python -m autopulse_backend.jobs replay-aggregate-dead-letters-once`).

## Testing restores

Quarterly: restore to a scratch host, run smoke ingest + dashboard overview, and discard the environment.

**GA / production gate:** follow the restore + smoke sequence in **[PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)** §8 together with incident drills that match your topology (`docs/runbooks/PHASE5_INCIDENT_DRILLS.md` as a menu). Treat a failed dry-run restore as a release blocker.
