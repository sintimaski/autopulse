---
description: Implement a feature or fix using the Lumonox implement-task playbook
---

Follow the playbook at `agents/implement-task.md` for this task. Read `DEVELOPMENT.md` for scope and security defaults before touching SDK / backend / dashboard surfaces, and read `docs/DOCUMENTATION_GOVERNANCE.md` before editing any governed doc.

Apply the always-on Lumonox rules summarized in `CLAUDE.md` (product, engineering, execution, debugging, post-task review, manual verification).

If the task touches:

- `backend/**` → also apply `.cursor/rules/backend-python.mdc`
- `frontend/**` → also apply `.cursor/rules/frontend-next.mdc` + `.cursor/rules/dashboard-static-export.mdc`; run `npm run build` in `frontend/` before handoff
- `sdk/**` → also apply `.cursor/rules/sdk-python.mdc`
- `scripts/**` → also apply `.cursor/rules/scripts-operations.mdc` (and `synthetic-stack-duckdb.mdc` for synthetic-stack scripts)
- `**/tests/**` → also apply `.cursor/rules/tests-validation.mdc`

Task: $ARGUMENTS
