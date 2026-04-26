# Playbook: UI and UX analysis

## Purpose

Evaluate dashboard and onboarding changes against **fast diagnosis** and **low configuration burden** from `DEVELOPMENT.md`.

## Principles (from product brief)

- Target: understand what is broken in **~five seconds** on the overview.
- Optimize for **fast diagnosis**, not configurability.
- The user refuses to “design observability”; guide with defaults.

## Heuristic checklist

### First-run / onboarding

- Time-to-value: how many steps until real data appears?
- Copy: short, imperative, no internal jargon without explanation.
- Failure states: wrong key, no traffic, clock issues — each has a clear next action.

### Overview

- At a glance: error rate, latency, throughput visible without scrolling on typical laptop.
- Visual hierarchy: newest severe issues more prominent than noise.
- Color: accessible contrast; do not rely on color alone for severity.

### Tables and lists (requests, errors)

- Columns match MVP: time, method, path, status, latency, service, environment where promised.
- Loading, empty, and error states are explicit.
- Pagination or virtual scroll does not hide totals misleadingly.

### Errors view

- Grouped errors show type, message, route, counts, first/last seen, sample stack.
- Stack traces readable (monospace, wrap or horizontal scroll with care).

### Alerts (when present)

- Minimal configuration: on/off, destination, simple thresholds.
- No “query builder” framing for MVP.

### Non-goals guardrails

- Flag any drift toward custom dashboards, arbitrary queries, or enterprise-style RBMS copy for MVP.

## Output template

1. **User story** — who benefits and in what situation
2. **Friction points** — numbered, with severity (low/med/high)
3. **Concrete changes** — wording, layout, component-level suggestions
4. **Five-second test** — pass/fail and why
