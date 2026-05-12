"""Tests for outbound alert webhook URL validation (SSRF guardrails)."""

import pytest

from lumonox_backend.services.alert_webhook_security import (
    AlertWebhookUrlError,
    validate_alert_outbound_webhook_url,
)


def test_https_public_ip_literal_allowed_in_production() -> None:
    validate_alert_outbound_webhook_url(
        "https://1.1.1.1/notify",
        lumonox_env="production",
    )


def test_private_ip_rejected_in_production() -> None:
    with pytest.raises(AlertWebhookUrlError):
        validate_alert_outbound_webhook_url(
            "https://10.0.0.1/hook",
            lumonox_env="production",
        )


def test_http_rejected_in_production_even_for_public_host() -> None:
    with pytest.raises(AlertWebhookUrlError):
        validate_alert_outbound_webhook_url(
            "http://1.1.1.1/hook",
            lumonox_env="production",
        )


def test_http_localhost_allowed_in_development() -> None:
    validate_alert_outbound_webhook_url(
        "http://127.0.0.1:8089/alerts",
        lumonox_env="development",
    )


def test_http_non_loopback_rejected_in_development() -> None:
    with pytest.raises(AlertWebhookUrlError):
        validate_alert_outbound_webhook_url(
            "http://1.1.1.1/hook",
            lumonox_env="development",
        )


def test_embedded_credentials_rejected() -> None:
    with pytest.raises(AlertWebhookUrlError):
        validate_alert_outbound_webhook_url(
            "https://user:pass@1.1.1.1/hook",
            lumonox_env="production",
        )
