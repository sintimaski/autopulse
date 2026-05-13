---
description: Security / privacy review using the Lumonox security-privacy playbook
---

Follow the playbook at `agents/security-privacy.md`. Read the **Security And Privacy** section of `DEVELOPMENT.md` for expected defaults.

Cover the checklist:

- **Transport and secrets** — HTTPS, hashed API keys (constant-time compare), no secrets in logs/metrics/error messages.
- **SDK capture defaults** — default scrub keys honored; bodies off by default for MVP; custom scrub hooks cannot disable mandated keys silently.
- **Backend validation** — schema rejects unknown / oversized fields; batch / event / stack-depth limits.
- **Production configuration** — `validate_deployment_settings` in `backend/src/lumonox_backend/core/config.py` rejects unsafe combinations (HTTPS ingest, internal metrics token, dashboard auth URL schemes, CORS, session / magic-link TTL bounds). Canonical operator guidance: `docs/ops/PRODUCTION_DEPLOYMENT.md`. Regression coverage: `backend/tests/test_deployment_settings.py`.
- **API key lifecycle** — `issue` / `rotate` / `revoke` emit rows in `governance_audit_events` and must not persist raw key material in audit detail (see `backend/tests/test_dashboard_auth.py`).
- **Data retention and access** — retention matches stated intent; admin paths authenticated and audited.

Deliverable: **Scope**, **Risks** (ranked), **Mitigations** (in-diff vs follow-up), **Residual risk**.

Target: $ARGUMENTS
