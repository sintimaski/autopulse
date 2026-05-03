from __future__ import annotations

from autopulse_backend.commercial.plan_limits import retention_plan_ingest_rate_multiplier


def test_retention_plan_ingest_rate_multiplier_starter() -> None:
    assert retention_plan_ingest_rate_multiplier("starter") == 0.35


def test_retention_plan_ingest_rate_multiplier_unknown_defaults() -> None:
    assert retention_plan_ingest_rate_multiplier("unknown-tier") == 1.0
