from __future__ import annotations

from dataclasses import replace

import pytest

from autopulse_backend.core.config import Settings, validate_deployment_settings


def _production_dashboard_base() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///./x.db",
        event_store="duckdb",
        event_store_duckdb_path="./.autopulse/e.duckdb",
        cors_allow_origins=("http://localhost:3000",),
        autopulse_env="production",
        jobs_enable_scheduler=True,
        dev_scenarios_enabled=False,
        dashboard_auth_enabled=True,
        dashboard_auth_allowed_email=None,
        dashboard_allowed_email_domains=(),
        dashboard_oidc_enabled=False,
        dashboard_oidc_issuer_url=None,
        dashboard_oidc_client_id=None,
        dashboard_oidc_client_secret=None,
        dashboard_oidc_redirect_uri=None,
        dashboard_oidc_state_secret=None,
        dashboard_enforce_origin_for_mutations=True,
        internal_metrics_bearer_token="prod-metrics-token",
    )


def test_validate_deployment_settings_allows_development_with_dev_scenarios() -> None:
    s = Settings(
        database_url="sqlite+aiosqlite:///./x.db",
        event_store="duckdb",
        event_store_duckdb_path="./.autopulse/e.duckdb",
        cors_allow_origins=("http://localhost:3000",),
        autopulse_env="development",
        dev_scenarios_enabled=True,
    )
    validate_deployment_settings(s)


def test_validate_deployment_settings_rejects_dev_scenarios_in_production() -> None:
    s = Settings(
        database_url="sqlite+aiosqlite:///./x.db",
        event_store="duckdb",
        event_store_duckdb_path="./.autopulse/e.duckdb",
        cors_allow_origins=("http://localhost:3000",),
        autopulse_env="production",
        jobs_enable_scheduler=True,
        dev_scenarios_enabled=True,
    )
    with pytest.raises(ValueError, match="DEV_SCENARIOS_ENABLED"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_production_dashboard_requires_identity_gate() -> None:
    s = _production_dashboard_base()
    with pytest.raises(ValueError, match="Production dashboard auth requires"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_production_accepts_allowlist_email() -> None:
    s = replace(_production_dashboard_base(), dashboard_auth_allowed_email="ops@example.com")
    validate_deployment_settings(s)


def test_validate_deployment_settings_production_accepts_email_domains() -> None:
    s = replace(_production_dashboard_base(), dashboard_allowed_email_domains=("example.com",))
    validate_deployment_settings(s)


def test_validate_deployment_settings_production_accepts_full_oidc() -> None:
    s = replace(
        _production_dashboard_base(),
        dashboard_oidc_enabled=True,
        dashboard_oidc_issuer_url="https://idp.example.com",
        dashboard_oidc_client_id="client",
        dashboard_oidc_client_secret="secret",
        dashboard_oidc_redirect_uri="https://app.example.com/callback",
        dashboard_oidc_state_secret="state-secret",
    )
    validate_deployment_settings(s)


def test_validate_deployment_settings_production_requires_origin_enforcement_when_auth_on() -> None:
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_allowed_email="ops@example.com",
        dashboard_enforce_origin_for_mutations=False,
    )
    with pytest.raises(ValueError, match="DASHBOARD_ENFORCE_ORIGIN_FOR_MUTATIONS"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_production_rejects_api_key_fallback_when_auth_on() -> None:
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_allowed_email="ops@example.com",
        dashboard_auth_allow_api_key_fallback=True,
    )
    with pytest.raises(ValueError, match="DASHBOARD_AUTH_ALLOW_API_KEY_FALLBACK"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_production_rejects_wildcard_cors_when_auth_on() -> None:
    s = replace(
        _production_dashboard_base(),
        cors_allow_origins=("*",),
        dashboard_auth_allowed_email="ops@example.com",
    )
    with pytest.raises(ValueError, match="CORS_ALLOW_ORIGINS"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_production_rejects_short_session_ttl_when_auth_on() -> None:
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_allowed_email="ops@example.com",
        dashboard_auth_session_ttl_minutes=15,
    )
    with pytest.raises(ValueError, match="DASHBOARD_AUTH_SESSION_TTL_MINUTES"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_production_rejects_short_magic_link_ttl_when_auth_on() -> (
    None
):
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_allowed_email="ops@example.com",
        dashboard_auth_magic_link_ttl_minutes=3,
    )
    with pytest.raises(ValueError, match="DASHBOARD_AUTH_MAGIC_LINK_TTL_MINUTES"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_production_rejects_long_magic_link_ttl_when_auth_on() -> None:
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_allowed_email="ops@example.com",
        dashboard_auth_magic_link_ttl_minutes=45,
    )
    with pytest.raises(ValueError, match="DASHBOARD_AUTH_MAGIC_LINK_TTL_MINUTES"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_production_rejects_ingest_https_off() -> None:
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_allowed_email="ops@example.com",
        ingest_require_https=False,
    )
    with pytest.raises(ValueError, match="INGEST_REQUIRE_HTTPS"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_production_requires_internal_metrics_token() -> None:
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_allowed_email="ops@example.com",
        internal_metrics_bearer_token=None,
    )
    with pytest.raises(ValueError, match="INTERNAL_METRICS_BEARER_TOKEN"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_production_skips_dashboard_rules_when_auth_off() -> None:
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_enabled=False,
        dashboard_enforce_origin_for_mutations=False,
    )
    validate_deployment_settings(s)


def test_validate_deployment_settings_staging_allows_api_key_fallback() -> None:
    s = replace(
        _production_dashboard_base(),
        autopulse_env="staging",
        dashboard_auth_allowed_email="ops@example.com",
        dashboard_auth_allow_api_key_fallback=True,
    )
    validate_deployment_settings(s)


def test_validate_deployment_settings_staging_allows_short_session_ttl() -> None:
    s = replace(
        _production_dashboard_base(),
        autopulse_env="staging",
        dashboard_auth_allowed_email="ops@example.com",
        dashboard_auth_session_ttl_minutes=15,
    )
    validate_deployment_settings(s)


def test_validate_deployment_settings_staging_allows_short_magic_link_ttl() -> None:
    s = replace(
        _production_dashboard_base(),
        autopulse_env="staging",
        dashboard_auth_allowed_email="ops@example.com",
        dashboard_auth_magic_link_ttl_minutes=3,
    )
    validate_deployment_settings(s)


def test_validate_deployment_settings_staging_allows_ingest_https_off() -> None:
    s = replace(
        _production_dashboard_base(),
        autopulse_env="staging",
        dashboard_auth_allowed_email="ops@example.com",
        ingest_require_https=False,
    )
    validate_deployment_settings(s)


def test_validate_deployment_settings_rejects_magic_link_dev_token_in_production() -> None:
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_allowed_email="ops@example.com",
        dashboard_auth_magic_link_dev_expose_token=True,
    )
    with pytest.raises(ValueError, match="DASHBOARD_AUTH_MAGIC_LINK_DEV_EXPOSE_TOKEN"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_rejects_production_without_scheduler_or_external_cron() -> (
    None
):
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_allowed_email="ops@example.com",
        jobs_enable_scheduler=False,
        jobs_external_cron_ownership=False,
    )
    with pytest.raises(ValueError, match="JOBS_ENABLE_SCHEDULER"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_allows_external_cron_ownership_in_production() -> None:
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_allowed_email="ops@example.com",
        jobs_enable_scheduler=False,
        jobs_external_cron_ownership=True,
    )
    validate_deployment_settings(s)


def test_validate_deployment_settings_rejects_staging_without_scheduler_or_external_cron() -> None:
    s = replace(
        _production_dashboard_base(),
        autopulse_env="staging",
        jobs_enable_scheduler=False,
        jobs_external_cron_ownership=False,
    )
    with pytest.raises(ValueError, match="JOBS_ENABLE_SCHEDULER"):
        validate_deployment_settings(s)


def test_validate_deployment_settings_allows_staging_with_external_cron_ownership() -> None:
    s = replace(
        _production_dashboard_base(),
        autopulse_env="staging",
        jobs_enable_scheduler=False,
        jobs_external_cron_ownership=True,
    )
    validate_deployment_settings(s)
