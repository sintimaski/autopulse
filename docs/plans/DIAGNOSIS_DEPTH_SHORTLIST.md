# Diagnosis depth shortlist (implemented)

Disposable plan per `docs/DOCUMENTATION_GOVERNANCE.md`. Two diagnosis-adjacent improvements shipped in-repo:

## 1) Smarter synthetic error grouping (no `error_hash`)

**Problem:** Legacy or partial payloads omit `error_hash`; synthetic keys used raw `exception_message`, so volatile UUIDs/numeric IDs split one logical failure into many groups.

**Change:** `normalize_exception_message_for_synthetic_grouping()` in `backend/src/lumonox_backend/dashboard/error_grouping.py` collapses UUIDs and long digit runs before hashing. SDK-provided `error_hash` paths are unchanged.

## 2) Requests table preset: `focus=errors`

**Problem:** Operators often want 5xx-only request rows; today they must remember `status_class=5`.

**Change:** `GET /dashboard/requests?focus=errors` applies HTTP 5xx class filtering when `status_class` is **not** set. Explicit `status_class` always wins.

**API:** `focus` enum `errors` — see `DashboardRequestsFocus` in `backend/src/lumonox_backend/dashboard/params.py`.
