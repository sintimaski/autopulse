# CLAUDE.md — `backend/`

Authoritative rules: **`.cursor/rules/backend-python.mdc`** (apply whenever editing `backend/**/*.py`).

Headline constraints (read the rule file for the full text):

- Dashboard static UI is served by mounting **`LUMONOX_FRONTEND_STATIC_DIR`** at **`/lumonox/ui/`** — see `.cursor/rules/dashboard-static-export.mdc` and `backend/src/lumonox_backend/dashboard/static_export_mount.py`. Do not assume a separate Next server for default full-stack flows.
- Keep `POST /ingest` fast; move expensive work off the request path.
- Authenticate API keys and scope every data operation to project boundaries.
- Validate / normalize payloads with Pydantic; attach server metadata per `DEVELOPMENT.md`.
- Prefer focused fixes over broad refactors; preserve naming/patterns unless the task requires change.
- Run targeted backend tests for touched behavior and report exact commands and results in the final response.

Related rules:

- `.cursor/rules/lumonox-engineering.mdc` — always-on engineering constraints (incl. backend hot-path rules).
- `.cursor/rules/lumonox-data-dir-testing.mdc` — `LUMONOX_DATA_DIR=/tmp/lx-test` is for tests/debug only; normal runs use the repo `.lumonox/`.
- `.cursor/rules/synthetic-stack-duckdb.mdc` — keep the synthetic stack DuckDB-first; do not silently switch to SQLite.
- `.cursor/rules/tests-validation.mdc` — when editing `backend/tests/**`.
