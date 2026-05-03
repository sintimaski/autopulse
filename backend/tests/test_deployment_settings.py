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


def test_validate_deployment_settings_production_skips_dashboard_rules_when_auth_off() -> None:
    s = replace(
        _production_dashboard_base(),
        dashboard_auth_enabled=False,
        dashboard_enforce_origin_for_mutations=False,
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
