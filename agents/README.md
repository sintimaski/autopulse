# Agent playbooks

These files are **procedures**, not code. Use them to structure analysis and execution before touching large areas of the repo.

## How to use

1. Open the playbook that matches the work.
2. Attach `DEVELOPMENT.md` in Cursor when scope, security, or UX expectations matter.
3. Follow the phases in order unless the task is trivially local (e.g. typo fix).
4. For governed documentation edits, read `docs/DOCUMENTATION_GOVERNANCE.md` first.

## Index

| Playbook | Use when |
|----------|----------|
| [implement-task.md](./implement-task.md) | Building or fixing behavior; need task decomposition and acceptance checks. |
| [review.md](./review.md) | Reviewing a PR or diff; want explicit lanes and corner cases. |
| [ui-ux-analysis.md](./ui-ux-analysis.md) | Changing dashboard, onboarding, or any user-visible flow. |
| [security-privacy.md](./security-privacy.md) | Touching ingest, keys, storage, SDK capture, or scrubbing. |

## Relationship to CI

Playbooks complement automated checks (Ruff, Mypy, Bandit, tests). They catch **intent drift** and **product fit**; CI catches **mechanical** issues.
