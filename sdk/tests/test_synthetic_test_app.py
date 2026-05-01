from fastapi.testclient import TestClient

from autopulse.fixtures.synthetic_test_app import create_app
from autopulse.widgets import serialize_dashboard_widgets


def test_synthetic_app_health_endpoint_starts_cleanly() -> None:
    app = create_app(enable_monitor=False)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["service"] == "synthetic-test-api"
    assert response.headers.get("x-request-id")


def test_synthetic_app_boom_endpoint_returns_500() -> None:
    app = create_app(enable_monitor=False)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.get("/boom", headers={"x-auth-token": "demo:admin:test-admin"})
    finally:
        client.close()
    assert response.status_code == 500


def test_synthetic_app_registers_all_demo_widget_types() -> None:
    app = create_app(enable_monitor=True)
    widgets = getattr(app.state, "_autopulse_config", None).dashboard_widgets
    payload = serialize_dashboard_widgets(list(widgets))
    widget_types = {item["type"] for item in payload["definitions"]}
    assert widget_types == {"card", "line", "bar", "donut", "histogram", "scatter", "stacked_area"}
    assert len(payload["points"]) > 0


def test_synthetic_app_payment_intent_validation() -> None:
    app = create_app(enable_monitor=False)
    with TestClient(app) as client:
        response = client.post(
            "/payments/intents",
            headers={"x-auth-token": "demo:editor:ed"},
            json={"amount_cents": 25, "currency": "usd"},
        )
    assert response.status_code == 400


def test_synthetic_app_inventory_unknown_sku() -> None:
    app = create_app(enable_monitor=False)
    with TestClient(app) as client:
        response = client.get(
            "/inventory/SKU-NOT-REAL",
            headers={"x-auth-token": "demo:viewer:vu"},
        )
    assert response.status_code == 404
