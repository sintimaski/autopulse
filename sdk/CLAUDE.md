# CLAUDE.md — `sdk/`

Authoritative rule: **`.cursor/rules/sdk-python.mdc`** (apply whenever editing `sdk/**/*.py`).

Headline constraints (read the rule for the full text — and the always-on `.cursor/rules/lumonox-engineering.mdc` SDK section):

- **Never break user applications** if the backend is misconfigured, unavailable, or slow. This is the SDK's most important contract.
- Keep the hot path async / non-blocking and dependency-light; preserve bounded-queue + drop-when-full behavior.
- Preserve **silent-failure defaults** (except explicit debug modes) and scrub sensitive data before send.
- On middleware exceptions, capture the data then **re-raise the original exception** — do not swallow user-facing errors.
- Keep the public API stable and typed; align names and behavior with `DEVELOPMENT.md`.
- Framework adapters (`lumonox.fastapi`, `lumonox.django`) are thin glue over the shared `lumonox.core.*` send path — never fork the dispatcher / scrubbing / event-shape / config-builder logic per adapter. FastAPI ships in the default install; Django ships behind the `[django]` extra. See `sdk/docs/adapters.md`.
- Run deterministic targeted SDK tests under `sdk/tests/` for touched behavior; report exact commands and results.

Related rules:

- `.cursor/rules/lumonox-engineering.mdc` — always-on SDK / backend / security constraints.
- `.cursor/rules/tests-validation.mdc` — when editing `sdk/tests/**`.
