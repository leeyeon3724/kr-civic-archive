from __future__ import annotations

import scripts.check_runtime_health as runtime_health


def test_check_with_retry_succeeds_after_transient_failures(monkeypatch):
    responses = [
        (0, "connection error"),
        (200, {"status": "ok"}),
    ]
    sleeps: list[float] = []

    def fake_http_get_json(_url: str, _timeout: float):
        return responses.pop(0)

    monkeypatch.setattr(runtime_health, "_http_get_json", fake_http_get_json)
    monkeypatch.setattr(runtime_health.time, "sleep", lambda value: sleeps.append(value))

    ok = runtime_health._check_with_retry(
        name="live",
        url="http://localhost:8000/health/live",
        expected=200,
        timeout=0.5,
        retries=3,
        retry_delay_seconds=0.1,
    )

    assert ok is True
    assert sleeps == [0.1]


def test_check_with_retry_fails_after_exhausting_retries(monkeypatch):
    sleeps: list[float] = []

    def fake_http_get_json(_url: str, _timeout: float):
        return 0, "connection error"

    monkeypatch.setattr(runtime_health, "_http_get_json", fake_http_get_json)
    monkeypatch.setattr(runtime_health.time, "sleep", lambda value: sleeps.append(value))

    ok = runtime_health._check_with_retry(
        name="ready",
        url="http://localhost:8000/health/ready",
        expected=200,
        timeout=0.5,
        retries=2,
        retry_delay_seconds=0.2,
    )

    assert ok is False
    assert sleeps == [0.2, 0.2]


def test_check_with_retry_accepts_ready_degraded_when_enabled(monkeypatch):
    responses = [
        (503, {"status": "degraded", "checks": {"database": {"ok": False}}}),
    ]

    def fake_http_get_json(_url: str, _timeout: float):
        return responses.pop(0)

    monkeypatch.setattr(runtime_health, "_http_get_json", fake_http_get_json)
    monkeypatch.setattr(runtime_health.time, "sleep", lambda _value: None)

    ok = runtime_health._check_with_retry(
        name="ready",
        url="http://localhost:8000/health/ready",
        expected=200,
        timeout=0.5,
        retries=0,
        retry_delay_seconds=0.1,
        allow_ready_degraded=True,
    )

    assert ok is True


def test_check_with_retry_rejects_invalid_ready_payload(monkeypatch):
    responses = [
        (200, {"status": "ok"}),
    ]

    def fake_http_get_json(_url: str, _timeout: float):
        return responses.pop(0)

    monkeypatch.setattr(runtime_health, "_http_get_json", fake_http_get_json)
    monkeypatch.setattr(runtime_health.time, "sleep", lambda _value: None)

    ok = runtime_health._check_with_retry(
        name="ready",
        url="http://localhost:8000/health/ready",
        expected=200,
        timeout=0.5,
        retries=0,
        retry_delay_seconds=0.1,
    )

    assert ok is False


def test_validate_health_payload_for_live_non_json_body():
    ok, reason = runtime_health._validate_health_payload(name="live", status=200, body="plain-text")
    assert ok is False
    assert "JSON object" in str(reason)
