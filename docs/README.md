# Docs index (production-first)

This index focuses on shipping and operating Lumonox safely. For **product scope and architecture**, use `DEVELOPMENT.md` at the repository root.

## Start here

- Product scope and constraints: `DEVELOPMENT.md`
- Repo usage and quickstart: `README.md`
- Contributor workflow and root `make` commands: `CONTRIBUTING.md`
- AI/agent playbooks and workflow index: `AGENTS.md`
- Cursor rules, @-mentions, and editor workflows: `docs/cursor/CURSOR_DEVELOPMENT.md`, `docs/cursor/WORKFLOWS.md`
- Production deployment: `docs/ops/PRODUCTION_DEPLOYMENT.md`
- Version upgrades (operator checklist): `docs/ops/DEPLOYMENT_UPGRADE.md`

## Developers and planning

- Detailed process, quality gates, MVP and release checks: `docs/DEVELOPMENT_PROCESS.md`
- Task card template for multi-step work: `docs/DEVELOPMENT_PLAN_TASK_TEMPLATE.md`
- Disposable initiative plans (not governed long-term docs): `docs/plans/README.md`
- Dashboard read-path latency expectations: `docs/DASHBOARD_QUERY_LATENCY_CONTRACT.md`

## Operations

- Backups and restore: `docs/ops/BACKUP_RESTORE.md`
- Backend lifespan responsibilities and shutdown order: `docs/ops/BACKEND_LIFECYCLE.md`
- CI reliability matrix (scheduler + async aggregate slice): `docs/ops/CI_RELIABILITY_MATRIX.md`
- Multi-instance deployment: `docs/ops/DEPLOYMENT_MULTI_INSTANCE.md`
- Event-plane scaling ADR: `docs/ops/ADR_EVENT_STORE_SCALING.md`
- Event-plane backpressure runbook: `docs/ops/RUNBOOK_EVENT_PLANE_BACKPRESSURE.md`
- Compactor load evidence: `docs/ops/EVENT_PLANE_COMPACTOR_LOAD_EVIDENCE.md`
- Disaster recovery drills: `docs/ops/EVENT_PLANE_DISASTER_RECOVERY_DRILLS.md`

## Runbooks and testing

- PyPI dual-package release (`lumonox` + `lumonox-sdk`): `docs/runbooks/LUMONOX_PYPI_RELEASE_CHECKLIST.md`
- Release checklist: `docs/runbooks/PHASE5_RELEASE_CHECKLIST.md`
- Incident drills: `docs/runbooks/PHASE5_INCIDENT_DRILLS.md`
- Drill cadence + evidence log: `docs/runbooks/PHASE5_DRILL_CYCLE.md`, `docs/runbooks/PHASE5_DRILL_EVIDENCE_LOG.md`
- SQL-tail replay recovery: `docs/ops/RUNBOOK_SQL_TAIL_REPLAY_RECOVERY.md`
- E2E core journey: `docs/testing/E2E_CORE_JOURNEY.md`

## Contracts and governance

- Ingest API contract: `docs/contracts/ingest-api.md`
- Documentation governance policy: `docs/DOCUMENTATION_GOVERNANCE.md`
