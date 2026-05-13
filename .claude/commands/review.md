---
description: Review the current diff / PR using the Lumonox review playbook (lanes + corner cases)
---

Follow the playbook at `agents/review.md` for this review. Read `DEVELOPMENT.md` for expected behavior and security defaults.

For milestone or release-bound changes, also pair with `docs/DEVELOPMENT_PROCESS.md` section 7 (Risk and Release Readiness Checks).

Apply the lanes (Product/Scope, Correctness/API, Security/Privacy, Performance/Reliability, Observability/Ops) and explicitly work through the corner-case table — note **N/A** with reason when not applicable.

Output the **Verdict** in the playbook format:

- Summary (2–4 sentences)
- Blockers (must-fix before merge)
- Suggestions (non-blocking)
- Testing gaps (what still ought to be run)

If you want a clean second-pass review in an isolated context, delegate to the `code-reviewer` subagent (`.claude/agents/code-reviewer.md`) via the Agent tool.

Target: $ARGUMENTS
