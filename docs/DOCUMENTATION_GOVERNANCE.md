# Documentation governance

This repository treats several documents as **canonical product and engineering truth**. Changing them changes what contributors and automation assume about scope, security, and behavior.

## Documents under governance

Unless otherwise agreed, treat updates to the following as **governed**:

- `DEVELOPMENT.md` — product scope, MVP definition, architecture, event model, security defaults.
- `INIT.md` — historical or extended context that still informs decisions (prefer aligning with `DEVELOPMENT.md` when they conflict).
- `docs/DOCUMENTATION_GOVERNANCE.md` — this file.
- `docs/cursor/**` — Cursor and agent workflow conventions for this repo.
- `agents/**` — task, review, and analysis playbooks.
- `.cursor/rules/**` — persistent agent and editor guidance.

## Approval requirement

**Do not materially update, replace, or “upgrade” governed documents without explicit maintainer approval.**

What counts as material:

- Changing MVP scope, non-goals, security defaults, or definitions of done.
- Rewriting workflow steps or acceptance criteria in agent playbooks.
- Altering always-on rules in `.cursor/rules/` in ways that change product or security expectations.

What does **not** require pre-approval (use judgment; ask if unsure):

- Obvious typos, broken links, or formatting that does not change meaning.
- Adding a short cross-link to an existing section when the link target is already approved content.

## How to request a change

1. Propose the change in a PR or issue with a short rationale and any impact on SDK, backend, or dashboard behavior.
2. Wait for explicit maintainer approval on the proposal or PR.
3. Merge only after approval is recorded in the thread.

Agents and contributors should **surface** documentation drift (code contradicting `DEVELOPMENT.md`) as an issue or PR comment rather than silently rewriting the canonical doc.
