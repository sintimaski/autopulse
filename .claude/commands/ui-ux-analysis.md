---
description: UI / UX review of dashboard or onboarding changes using the Lumonox playbook
---

Follow the playbook at `agents/ui-ux-analysis.md`. Read the **dashboard** section of `DEVELOPMENT.md` for product principles.

Anchor the review on the Lumonox product principles:

- Target: a user understands what's broken in **~5 seconds** on the overview.
- Optimize for **fast diagnosis**, not configurability.
- The user refuses to "design observability" — guide with defaults, not config surfaces.

Walk the heuristic checklist (first-run / onboarding, overview, tables, errors view, alerts) and flag any drift toward non-goals (custom dashboard builder, arbitrary queries, enterprise-style RBAC copy).

Output template:

1. **User story** — who benefits and in what situation
2. **Friction points** — numbered, with severity (low / med / high)
3. **Concrete changes** — wording, layout, component-level suggestions
4. **Five-second test** — pass / fail and why

Target: $ARGUMENTS
