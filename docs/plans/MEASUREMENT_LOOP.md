# Weekly measurement loop (activation & reliability)

Disposable ops notes for maintainers — not governed product spec.

## Server counters (via internal metrics)

When `INTERNAL_METRICS_BEARER_TOKEN` is configured, scrape `GET /internal/metrics` (or the dashboard JSON snapshot if exposed) and track week-over-week:

| Counter | Meaning |
|--------|---------|
| `dashboard.workspace.onboarding_completed_total` | Users completed onboarding after first ingest |
| `dashboard.query.correlation_scope_total` | Requests/diagnosis loads filtered by `correlation_request_id` (lineage usage) |

## Client session hints (optional)

The dashboard records **sessionStorage** timestamps (`lx_activation_*`) when onboarding steps render — inspect in browser devtools for qualitative funnel timing (no PII).

## Manual review checklist (15 min / week)

1. New project cold start: onboarding → first event &lt; 10 minutes?
2. Correlation: trigger a failing job with default SDK — confirm `X-Request-ID` response header and matching rows under Requests with `correlation` query.
3. Reliability: Settings → System diagnostics — scheduler running, pending SQL tail repairs near zero.
