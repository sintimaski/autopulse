# Diagnosis depth shortlist (implemented)

Disposable plan per `docs/DOCUMENTATION_GOVERNANCE.md`. Two diagnosis-adjacent improvements shipped in-repo:

## 1) Smarter synthetic error grouping (no `error_hash`)

**Problem:** Legacy or partial payloads omit `error_hash`; synthetic keys used raw `exception_message`, so volatile UUIDs/numeric IDs split one logical failure into many groups.

**Change:** `normalize_exception_message_for_synthetic_grouping()` in `backend/src/lumonox_backend/dashboard/error_grouping.py` collapses UUIDs and long digit runs before hashing. SDK-provided `error_hash` paths are unchanged.

## 2) Requests table preset: `focus=errors` — REMOVED (audit gap R2)

**Original idea:** `GET /dashboard/requests?focus=errors` applied HTTP 5xx class filtering when `status_class` was unset, as a shorthand for `status_class=5`.

**Outcome:** The frontend never sent `focus` — it recomputes error/slow views client-side over the loaded sample. Per audit gap R2 the unused `focus` query param and the `DashboardRequestsFocus` enum were dropped from `GET /dashboard/requests` and `GET /dashboard/requests/export`. Callers wanting 5xx-only rows use `status_class=5` directly.
