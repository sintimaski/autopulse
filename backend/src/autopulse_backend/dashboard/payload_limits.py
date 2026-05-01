"""Upper bounds for dashboard API payloads (defense in depth vs oversized JSON)."""

# Widget time-series can grow without bound as the SDK flushes; cap rows returned per query.
MAX_DASHBOARD_WIDGET_POINTS_RETURNED = 8_000

# Truncate long exception text / stacks in grouped views (still useful for triage).
MAX_ERROR_GROUP_MESSAGE_CHARS = 4_000
MAX_ERROR_GROUP_STACK_CHARS = 8_000
MAX_DIAGNOSIS_EVENT_MESSAGE_CHARS = 4_000
MAX_DIAGNOSIS_EVENT_STACK_CHARS = 12_000
