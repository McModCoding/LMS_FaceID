"""Regression checks for delivery contract (no public student self-signup)."""

from app.main import app


def test_login_exists_but_public_registration_is_absent():
    routes = app.openapi()["paths"]
    assert "/api/v1/auth/login" in routes
    assert "/api/v1/auth/register" not in routes


def test_health_endpoint_returns_ok(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
