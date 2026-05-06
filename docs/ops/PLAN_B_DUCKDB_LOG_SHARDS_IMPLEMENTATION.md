# Plan B implementation: log-shard ingest + DuckDB compaction (no third-party store)

Status: in progress.

This plan is a full execution path for scaling beyond a single DuckDB writer **without** managed third-party analytics infrastructure. It preserves the MVP default (simple diagnosis-first setup) while adding an operator-controlled scale tier.

## 1) Why this plan

Plan B keeps AutoPulse on self-hosted primitives:

- Ingest path writes append-only event log shards (durable, write-friendly).
- A compactor service converts shards into query-optimized DuckDB partitions.
- Dashboard/query reads continue to use DuckDB.
- Metadata/auth/aggregates remain on existing SQL metadata store (`DATABASE_URL`).

This removes multi-writer pressure on a single DuckDB file while avoiding ClickHouse/managed vendors.

## 2) Scope and non-goals

### In scope

- New event-log shard writer on ingest path.
- Compaction pipeline from shards -> DuckDB read partitions.
- Project-scoped rollout, metrics, runbooks, and rollback controls.
- Compatibility with existing ingest API contract.

### Out of scope

- Distributed tracing/APM scope expansion.
- Mandatory external queue or managed stream.
- Rewriting dashboard UX/query contract.

## 3) Architecture (target state)

### Components

1. **Ingest API**
   - Validates/authenticates payloads as today.
   - Appends normalized event rows to append-only shard files.
   - Returns success after durability threshold is met (fsync policy; see corner cases).
2. **Shard manifest/index**
   - Tracks shard lifecycle (`open`, `sealed`, `compacting`, `compacted`, `failed`).
   - Stores ownership and idempotency metadata for safe retries.
3. **Compactor worker**
   - Seals eligible shards, builds partitioned DuckDB segments, atomically publishes new snapshot pointers.
4. **Query read path**
   - Reads from current published DuckDB snapshot/partition set.
   - Never reads half-written compaction outputs.

### Data layout (example)

- `events-log/{project_id}/{yyyy}/{mm}/{dd}/{hour}/shard-<ulid>.parquet`
- `events-index/{project_id}/manifest.sqlite` (or SQL metadata table)
- `events-duckdb/{project_id}/snapshot-<version>/events.duckdb`
- `events-duckdb/{project_id}/CURRENT` pointer file (atomic replace)

## 4) Invariants (must always hold)

1. **Ingest durability before ack**: accepted events are durable in shard storage before `200`.
2. **Immutable shards**: sealed shard contents never mutate.
3. **Atomic publish**: readers only see fully built DuckDB snapshots.
4. **Idempotent compaction**: retrying compaction cannot duplicate events in published snapshot.
5. **Bounded backpressure**: ingest cannot block indefinitely on compactor lag.
6. **Safe degradation**: compactor failure degrades freshness, not ingest correctness.

## 5) Migration path from current single-writer DuckDB

1. **Phase 0: instrumentation first**
   - Add metrics for ingest throughput, shard queue depth, compaction lag, and snapshot age.
2. **Phase 1: dual-write (guarded)**
   - Keep current DuckDB write path authoritative.
   - Also write shards; validate row-count and checksum parity per time window.
3. **Phase 2: compaction shadow**
   - Build DuckDB snapshots from shards but keep dashboard reads on current path.
   - Run parity checks for representative dashboard queries.
4. **Phase 3: project-scoped read cutover**
   - Enable reads from compacted snapshots for selected projects.
5. **Phase 4: generalized Plan B mode**
   - Default high-scale projects to Plan B; preserve rollback switch.

## 6) Corner cases and failure modes

### Ingest and durability

- **Process crash after validation, before append commit**
  - Expected: request fails/retries; no false ack.
  - Control: ack only after append + fsync policy success.
- **Crash after append, before response**
  - Expected: possible client retry duplicates.
  - Control: preserve idempotency key path; dedupe at ingest/service layer.
- **Disk full on shard volume**
  - Expected: reject with backpressure/5xx and clear metrics/log signal.
  - Control: reserve watermark thresholds and proactive alerting.

### Shard lifecycle

- **Open shard never seals (stuck writer)**
  - Control: max shard age + size policy; forced seal timer.
- **Corrupted shard file**
  - Control: checksums per shard; quarantine + replay from source if possible.
- **Out-of-order timestamps**
  - Control: partition by receive time; keep event timestamp as data field.

### Compaction

- **Compactor dies mid-build**
  - Control: build in temp snapshot dir; publish only after completion marker.
- **Duplicate compaction job execution**
  - Control: shard lease/lock in manifest + idempotent publish by snapshot version.
- **Compaction backlog growth**
  - Control: bounded lag SLO and autoscaling/manual scaling runbook.

### Read path

- **Reader sees stale snapshot**
  - Control: expose snapshot age metric; alert when above threshold.
- **Snapshot publish race**
  - Control: atomic pointer replacement (`rename`) and version monotonicity checks.

### Multi-project isolation

- **Noisy project starves others**
  - Control: per-project shard queues and compactor fairness quotas.

### Privacy/security

- **Raw payload over-capture**
  - Control: reuse existing scrub defaults before shard write; never store plaintext API keys/tokens.
- **Sensitive debug logging**
  - Control: no full event payload logs; include only counts, ids, and error codes.

## 7) Operational knobs (minimum set)

- `AUTOPULSE_EVENT_PLANE_MODE=duckdb_single_writer|duckdb_log_shards`
- `AUTOPULSE_SHARD_MAX_BYTES` (for example 128MB)
- `AUTOPULSE_SHARD_MAX_AGE_SECONDS` (for example 300)
- `AUTOPULSE_COMPACTOR_INTERVAL_SECONDS`
- `AUTOPULSE_COMPACTOR_MAX_CONCURRENCY`
- `AUTOPULSE_COMPACTOR_PUBLISH_TIMEOUT_SECONDS`
- `AUTOPULSE_SNAPSHOT_RETENTION_COUNT`

Keep defaults conservative and low-friction; advanced tuning remains optional.

## 8) Metrics and SLO guardrails

Required metrics:

- `event_plane.shards.appended_total`
- `event_plane.shards.append_failed_total`
- `event_plane.shards.open_count`
- `event_plane.shards.sealed_total`
- `event_plane.compaction.duration_ms`
- `event_plane.compaction.failed_total`
- `event_plane.compaction.lag_seconds`
- `event_plane.snapshot.age_seconds`
- `event_plane.snapshot.publish_failed_total`

Alert examples:

- Compaction lag > 10 minutes for 15 minutes.
- Snapshot age > 20 minutes for 15 minutes.
- Append failures > 0.5% in 5 minutes.

## 9) Rollback strategy

- Feature flag to return reads to legacy DuckDB writer mode per project.
- Keep latest N snapshots + shard backlog until rollback window closes.
- If compactor quality/parity fails, freeze publish and continue ingest to shards.

Rollback must be executable without data loss and without changing SDK behavior.

## 10) Task backlog (with acceptance criteria)

### TSK-B0-01 — Event-plane mode flag and config surface [DONE]

- **Description:** Add Plan B mode flag and validated config schema.
- **Acceptance criteria:**
  - Backend starts with either mode.
  - Invalid combinations fail fast at startup with clear errors.
  - Docs/env template updated.
- **Implementation notes (2026-05-05):**
   - Added validated config surface in backend settings for `AUTOPULSE_EVENT_PLANE_MODE` and related Plan B shard/compactor knobs.
   - Added startup validation: `duckdb_log_shards` mode now fails fast unless `AUTOPULSE_EVENT_STORE=duckdb`.
   - Updated `backend/.env.example` and production deployment docs with new env variables.
   - Added targeted backend tests for mode defaults, invalid values, and invalid mode/store combinations.

### TSK-B0-02 — Shard writer abstraction [DONE]

- **Description:** Introduce append-only shard writer interface and local filesystem implementation.
- **Acceptance criteria:**
  - Writes are append-only and durable per configured policy.
  - Writer supports rotation by size and age.
  - Unit tests cover crash-safe flush/close semantics.
- **Implementation notes (2026-05-05):**
  - Added `LocalAppendOnlyShardWriter` and `EventShardWriter` protocol in `backend/src/autopulse_backend/services/event_plane_shards.py`.
  - Local writer now appends newline-delimited JSON rows to immutable shard files under project/hour buckets.
  - Added durability modes (`always`, `interval`, `none`) with explicit `fsync` behavior and forced `fsync` on close.
  - Implemented automatic shard rotation based on configured max bytes and max shard age.
  - Added unit tests for append durability, size rotation, age rotation, and close-time flush semantics.

### TSK-B0-03 — Manifest/index schema [DONE]

- **Description:** Add shard manifest schema and lifecycle states.
- **Acceptance criteria:**
  - State transitions are validated (`open -> sealed -> compacting -> compacted`).
  - Duplicate transition attempts are idempotent.
  - Recovery on restart resumes from persisted state.
- **Implementation notes (2026-05-05):**
  - Added persisted shard manifest service `SqliteShardManifest` in `backend/src/autopulse_backend/services/event_plane_manifest.py`.
  - Created lifecycle states (`open`, `sealed`, `compacting`, `compacted`, `failed`) with strict transition validation.
  - Implemented idempotent duplicate transitions (same target state returns existing record without error).
  - Added idempotent shard registration for duplicate `open` records and conflict detection for mismatched duplicates.
  - Added restart recovery coverage via manifest reopen tests against persisted SQLite rows.

### TSK-B1-01 — Ingest dual-write (shadow) [IN PROGRESS]

- **Description:** Add optional shard write in ingest while legacy DuckDB remains authoritative.
- **Acceptance criteria:**
  - Ingest latency increase stays within agreed budget (for example p95 delta <= 10%).
  - Per-window row counts match legacy path within tolerance.
  - Failure metrics/logs are emitted without exposing sensitive payloads.
- **Implementation notes (2026-05-05):**
  - Added shadow-write path in `persist_ingest_batch` for `AUTOPULSE_EVENT_PLANE_MODE=duckdb_log_shards` while DuckDB remains authoritative.
  - Shadow writes are fail-open: shard append errors increment `event_plane.shards.append_failed_total` and emit sanitized warning logs (no payload data).
  - Successful shadow appends increment `event_plane.shards.appended_total` by appended record count.
  - Added shadow instrumentation counters for operator checks: `event_plane.shards.shadow_write_batches_total`, `event_plane.shards.shadow_write_ms_total`, and `event_plane.shards.shadow_count_mismatch_total`.
  - Note: `shadow_write_ms_total` intentionally floors sub-millisecond shadow work to **1ms** per batch (otherwise fast local writes round to `0ms` and look like broken instrumentation).
  - Added per-minute parity tracking counters: `event_plane.shards.shadow_window_match_total` and `event_plane.shards.shadow_window_mismatch_total`.
  - Added lifecycle cleanup in app shutdown to close shard writer file descriptors.
  - Added tests for shadow write success, fail-open behavior, and mode-gated no-op behavior.

### TSK-B1-02 — Compactor MVP (single worker) [DONE]

- **Description:** Build sealed shards into versioned DuckDB snapshots.
- **Acceptance criteria:**
  - Compactor is restart-safe and idempotent.
  - Publishes only fully built snapshots.
  - Failed builds never become visible to readers.
- **Implementation notes (2026-05-06):**
  - Added `EventPlaneCompactor` in `backend/src/autopulse_backend/services/event_plane_compactor.py`.
  - Compactor now reserves `sealed` shards (`sealed -> compacting`), resumes pre-existing `compacting` shards after restart, and marks shards `compacted` only after successful snapshot publish.
  - Snapshot build writes to a temp directory first, then publishes by directory rename and `COMPLETE` marker creation.
  - Failed builds are cleaned up from temp output and remain unpublished (no `COMPLETE` snapshot visible).
  - Added `AUTOPULSE_EVENT_PLANE_SNAPSHOTS_PATH` config/env surface for snapshot output root.
  - Added compactor tests for restart safety, idempotence, successful publish, and failed-build invisibility.

### TSK-B1-03 — Snapshot publish protocol

- **Description:** Implement atomic `CURRENT` pointer update and reader consistency checks.
- **Acceptance criteria:**
  - Readers never observe partial snapshots.
  - Pointer updates are atomic on supported deployment filesystem.
  - Integration test validates concurrent read during publish.

### TSK-B2-01 — Parity harness

- **Description:** Build automated parity checks for core dashboard query families.
- **Acceptance criteria:**
  - Requests/errors/latency views compared across old vs Plan B outputs.
  - Mismatch report includes project/window/query signature.
  - Cutover blocked automatically on parity regression.

### TSK-B2-02 — Project-scoped cutover control

- **Description:** Add per-project toggle for Plan B read path.
- **Acceptance criteria:**
  - Operators can enable/disable without deploy.
  - Toggle is audited and visible in internal logs.
  - Rollback to legacy read path validated in staging.

### TSK-B2-03 — Backpressure and safeguards

- **Description:** Add disk watermarks, append reject policy, and operator alerts.
- **Acceptance criteria:**
  - Predictable behavior under low disk and high backlog.
  - Rejects are metered and visible in `/internal/metrics`.
  - Runbook documents remediation steps.

### TSK-B3-01 — Multi-worker compaction and fairness

- **Description:** Scale compactor workers with per-project fairness controls.
- **Acceptance criteria:**
  - No single project can starve others beyond configured fairness budget.
  - Throughput improves with concurrency in load tests.
  - No increase in correctness failures vs single-worker baseline.

### TSK-B3-02 — Disaster recovery drills

- **Description:** Add restore and replay procedure for shards + snapshots.
- **Acceptance criteria:**
  - Quarterly drill script exists and is repeatable.
  - Recovery meets declared RTO/RPO.
  - Evidence of latest successful drill is documented.

## 11) Test matrix (must pass before broad rollout)

- **Unit:** shard writer rotation, manifest transitions, idempotent compaction.
- **Integration:** ingest->shard->compaction->read parity for core queries.
- **Failure injection:** kill compactor mid-build, disk-full simulation, manifest lock contention.
- **Load:** sustained ingest with compactor lag objectives and query freshness SLO.
- **Security/privacy:** scrub invariants preserved; no secret leakage in logs/metrics.

## 12) Go/no-go gates for Plan B production use

Go only when all are true:

- Parity harness stable for representative workloads.
- Snapshot age and compaction lag remain inside SLO for 7 consecutive days.
- Rollback exercised successfully in staging.
- Backup/restore drill evidence exists for shard + snapshot assets.
- No unresolved Sev2+ incidents linked to Plan B core invariants.

No-go triggers:

- Repeated snapshot publish corruption/partial visibility.
- Compaction lag repeatedly violating SLO with no mitigation.
- Data parity regressions in diagnosis-critical views.

## 13) Important implementation notes

- Keep hot ingest path asynchronous and bounded; never block indefinitely on compaction.
- Preserve existing API contracts and error semantics for SDKs.
- Treat compactor as replaceable internal worker; do not couple business logic to one process.
- Prefer small incremental milestones with feature flags over one-shot migration.
