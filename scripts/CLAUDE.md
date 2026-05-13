# CLAUDE.md — `scripts/`

Authoritative rules: **`.cursor/rules/scripts-operations.mdc`** and **`.cursor/rules/synthetic-stack-duckdb.mdc`** (apply whenever editing `scripts/**/*.sh`).

Headline constraints (read the rule files for the full text):

- Keep scripts idempotent where practical and explicit about required env vars.
- Use safe shell defaults (`set -euo pipefail`) and quote variable expansions unless intentionally unquoted.
- Prefer deterministic local paths under the repo workspace; no hidden side effects outside project directories.
- Document non-obvious prerequisites inline.
- After edits, run the script path or closest dry-run / check command when feasible.

Synthetic-stack specifics:

- `scripts/run_synthetic_stack.sh` (backend :8000 + synthetic app :8001 + default Next sidecar :3000) and `scripts/run_remote_stack.sh` are **DuckDB-first** local integration paths — keep `LUMONOX_EVENT_STORE=duckdb` explicit in defaults.
- `run_synthetic_stack.sh` always runs `npm --prefix frontend run build`; `LUMONOX_FRONTEND_MODE=static` vs sidecar only affects how the UI is served afterward.
- Export `LUMONOX_DATA_DIR` (repo root) plus an absolute `LUMONOX_DUCKDB_PATH`. Do not silently switch these scripts to SQLite or `/tmp` for "convenience" (see `.cursor/rules/lumonox-data-dir-testing.mdc`).
