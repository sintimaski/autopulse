# Ingest API Contract (v1)

## Endpoint

- `POST /ingest`
- Auth: `Authorization: Bearer <project-api-key>`
- Content-Type: `application/json`

## Request schema

```json
{
  "sdk_version": "optional-string",
  "events": [
    {
      "type": "request | error",
      "timestamp": "RFC3339 datetime",
      "service_name": "string",
      "environment": "string",
      "method": "HTTP method",
      "path": "route path",
      "status_code": 200,
      "latency_ms": 12.3,
      "request_id": "optional string",
      "headers": {},
      "query_params": {}
    }
  ]
}
```

Unknown event fields are accepted but ignored for MVP persistence unless explicitly mapped in backend schemas.

## Response schema

`200 OK`

```json
{
  "accepted": 1
}
```

## Status semantics

- `200`: request accepted; events persisted to raw event store.
- `401`: missing/invalid API key.
- `413`: payload exceeds max request bytes.
- `429`: project rate limit exceeded (`Retry-After` header present).
- `422`: validation failure.

## First-ingest smoke check (quick)

1. Send one valid request with project API key (or run `./scripts/examples/ingest_sample_event.sh` from repo root).
2. Expect `200 OK` and JSON body containing `accepted >= 1`.
3. Confirm the accepted event is visible in dashboard diagnosis surfaces (Overview/Requests) shortly after ingest.

## Processing guarantees

- Raw event persistence is the source of truth.
- Aggregate/error-group projections may be eventually consistent when async workers are enabled.
- Retries and worker failures must not break ingest request success after raw persistence.

## Compatibility policy

- **Patch/minor backend releases**: backward compatible with v1 request schema.
- **New optional fields**: additive and non-breaking.
- **Breaking changes** (field removal/required field changes/status semantic changes): require a new contract version document (`v2`) and migration notes.

## Change management checklist

Before changing ingest behavior:

1. Update this contract document.
2. Add/adjust contract tests (`200`, `401`, `413`, `429`, `422`).
3. Verify SDK payload compatibility tests against backend.
