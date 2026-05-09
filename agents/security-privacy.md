# Playbook: security and privacy

## Purpose

Review changes that touch **ingestion**, **authentication**, **storage**, **SDK capture**, or **data scrubbing** against `DEVELOPMENT.md` security section.

## Threat framing ( proportionate to MVP )

- Untrusted input: SDK payloads, HTTP headers, query strings, optional bodies.
- Multi-tenant data: strict project scoping on every read/write.
- Operator assets: API keys, SMTP credentials, connection strings.

## Checklist

### Transport and secrets

- HTTPS for production-facing endpoints.
- API keys: hashed at rest; compare using constant-time primitives where applicable.
- No secrets in logs, metrics labels, or client-visible error messages.

### SDK capture defaults

- Default scrub keys honored: `authorization`, `cookie`, `set-cookie`, passwords, tokens, etc. (full list in `DEVELOPMENT.md`).
- Request/response bodies off by default for MVP unless explicitly enabled.
- Custom scrub hooks cannot accidentally **disable** scrubbing of mandated keys without an explicit product decision.

### Backend validation

- Schema validation rejects unknown or oversized fields where appropriate.
- Limits on batch size, event size, stack depth to protect the service.

### Production configuration (MVP guardrails)

When reviewing deployment or env changes for production: `validate_deployment_settings` in `backend/src/lumonox_backend/core/config.py` rejects unsafe combinations (for example HTTPS ingest, internal metrics token, dashboard auth URL schemes, CORS, session/magic-link TTL bounds). Canonical operator guidance and the full constraint list live in `docs/ops/PRODUCTION_DEPLOYMENT.md`. Regression coverage: `backend/tests/test_deployment_settings.py`.

API key lifecycle actions (`issue` / `rotate` / `revoke`) emit rows in `governance_audit_events` and must not persist raw key material in audit detail—see dashboard auth routes and `backend/tests/test_dashboard_auth.py` (set `BACKEND_TEST_DATABASE_URL` to run integration tests locally; see `backend/tests/conftest.py`).

### Data retention and access

- Retention behavior matches stated product intent; no silent extension of raw log life.
- Admin or support paths (if any) are authenticated and audited at a level appropriate to stage.

## Deliverable format

- **Scope**: what changed and trust boundaries affected
- **Risks**: ranked list
- **Mitigations**: already in diff vs recommended follow-ups
- **Residual risk**: explicit acceptance or need for maintainer decision
