import importlib


def test_health_live_endpoint(client):
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
    assert resp.headers.get("X-Request-Id")


def test_health_ready_endpoint(client):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"]["ok"] is True
    assert payload["checks"]["rate_limit_backend"]["ok"] is True


def test_health_ready_returns_503_when_any_check_fails(client, monkeypatch, use_stub_connection_provider):
    app_module = importlib.import_module("app")

    def failing_db_handler(_statement, _params):
        raise RuntimeError("db unavailable")

    use_stub_connection_provider(failing_db_handler)
    monkeypatch.setattr(app_module, "check_rate_limit_backend_health", lambda _config: (False, "redis down"))

    resp = client.get("/health/ready")
    assert resp.status_code == 503
    payload = resp.get_json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["database"]["ok"] is False
    assert payload["checks"]["rate_limit_backend"]["ok"] is False
