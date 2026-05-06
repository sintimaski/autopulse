# Contributing

Thanks for contributing to AutoPulse.

## First read

- `DEVELOPMENT.md` (product + engineering source of truth)
- `docs/DEVELOPMENT_PROCESS.md` (execution and release gates)
- `docs/DOCUMENTATION_GOVERNANCE.md` (governed docs policy)
- `AGENTS.md` (workflow pointers)

## Local setup

From repository root:

```bash
make setup
```

## Validation before PR

```bash
make check
```

Release candidate validation:

```bash
make release-gates
```

## PR expectations

- Keep changes small and focused.
- Include tests (or explicit manual verification notes) for behavior changes.
- Call out security-sensitive changes (auth, keys, scrubbing, ingestion limits) in PR description.
- Do not expand scope beyond requested task without explicit approval.

## Ownership and dependency hygiene

- Sensitive paths are protected by `.github/CODEOWNERS`; expect maintainer review on auth, ingest, ops/runbook, and release gate changes.
- Dependabot creates weekly update PRs for Python, frontend npm, and GitHub Actions dependencies via `.github/dependabot.yml`.
- Treat dependency PRs like normal code changes: CI must pass before merge.

## Scope guardrails

AutoPulse MVP is diagnosis-first and low-config. If a change adds observability-engineering complexity, discuss it before implementation.
