# Playbook: code review

## Purpose

Review diffs for **correctness**, **product fit**, **security**, and **operational** risk using explicit lanes so nothing important is skipped.

## Inputs

- The diff or PR.
- `DEVELOPMENT.md` for expected behavior and security defaults.

## Lane A — Product and scope

- Does the change serve the MVP question: *what broke, when, which requests*?
- Any new configuration or UI that violates “refuses to configure observability”?
- Non-goals accidentally introduced (tracing builder, complex alert language, etc.)?

## Lane B — Correctness and API stability

- Types and contracts: request/response shapes, event schema fields, public SDK surface.
- Error paths: what happens on `None`, empty batch, clock skew, duplicate delivery?
- Idempotency for ingestion or workers where relevant.

## Lane C — Security and privacy

- Secrets: API keys never logged or stored plaintext; headers scrubbed per defaults.
- New fields: could they contain PII or secrets? Default-off for bodies unless explicitly enabled.
- AuthZ: project isolation on queries and writes.

## Lane D — Performance and reliability

- Hot path: async, bounded queues, no unbounded memory growth.
- Retries: capped; backoff; drop-after policy documented where behavior changes.
- Database queries: N+1, missing indexes for new access patterns.

## Lane E — Observability and ops (internal)

- Logs/metrics for the service itself: actionable, not noisy.
- Feature flags or migrations: safe deploy order.

## Corner cases (explicit pass)

Work through applicable items; note **N/A** with reason when not applicable.

| Corner case | Question |
|-------------|----------|
| Partial failure | If half a batch succeeds, is state consistent? |
| Empty input | Empty event list, zero rows, blank path template |
| Extreme volume | Queue full, rate limit, very large stack trace |
| Time | Timezone normalization, out-of-order events |
| Auth | Invalid key, revoked key, wrong project |
| Dependency down | Postgres, SMTP, object store unavailable |
| Concurrent requests | Double submit, race on counters or grouping |
| Unicode / encoding | Non-ASCII paths, exception messages |
| Version skew | Older SDK with newer API or vice versa |

## Verdict template

- **Summary** (2–4 sentences)
- **Blockers** (must fix before merge)
- **Suggestions** (non-blocking)
- **Testing gaps** (what still ought to be run)
