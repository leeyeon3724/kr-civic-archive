#!/usr/bin/env python3
"""Check liveness/readiness endpoints for deployment guardrails."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterable
from urllib.parse import urlparse

import requests


def _http_get_json(url: str, timeout: float) -> tuple[int, dict | str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return 0, f"unsupported URL scheme: {parsed.scheme}"
    try:
        response = requests.get(url, timeout=timeout)
        status = int(response.status_code)
        body_raw = response.text
        try:
            body = json.loads(body_raw) if body_raw else {}
        except json.JSONDecodeError:
            body = body_raw
        return status, body
    except requests.RequestException as exc:
        return 0, f"connection error: {exc}"


def _check_with_retry(
    *,
    name: str,
    url: str,
    expected: int,
    timeout: float,
    retries: int,
    retry_delay_seconds: float,
    allow_ready_degraded: bool = False,
) -> bool:
    expected_statuses = {int(expected)}
    if name == "ready" and allow_ready_degraded:
        expected_statuses.add(503)

    attempts = max(1, retries + 1)
    for attempt in range(1, attempts + 1):
        status, body = _http_get_json(url, timeout)
        if status in expected_statuses:
            payload_ok, payload_error = _validate_health_payload(name=name, status=status, body=body)
            if payload_ok:
                print(f"[OK] {name}: {status} ({url}) [attempt {attempt}/{attempts}]")
                return True
            status = int(status)
            body = {"validation_error": payload_error, "body": body}

        if attempt < attempts:
            time.sleep(max(0.0, retry_delay_seconds))
            continue

        expected_label = _format_expected_statuses(expected_statuses)
        print(f"[FAIL] {name}: expected {expected_label}, got {status} ({url}) [attempt {attempt}/{attempts}]")
        print(f"       body={body}")
        return False
    return False


def _format_expected_statuses(statuses: Iterable[int]) -> str:
    return "|".join(str(item) for item in sorted(set(int(value) for value in statuses)))


def _validate_health_payload(*, name: str, status: int, body: dict | str) -> tuple[bool, str | None]:
    if not isinstance(body, dict):
        return False, "health response body must be a JSON object"

    response_status = body.get("status")
    if name == "live":
        if status != 200:
            return False, "live endpoint must return 200"
        if response_status != "ok":
            return False, "live endpoint must include status=ok"
        return True, None

    if name == "ready":
        if status == 200 and response_status != "ok":
            return False, "ready endpoint must include status=ok for 200 responses"
        if status == 503 and response_status != "degraded":
            return False, "ready endpoint must include status=degraded for 503 responses"
        checks = body.get("checks")
        if not isinstance(checks, dict):
            return False, "ready endpoint must include checks object"
        return True, None

    return True, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime health checks for deployment guardrails")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Target base URL")
    parser.add_argument("--timeout-seconds", type=float, default=3.0, help="HTTP timeout seconds")
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retry count per check (total attempts = retries + 1)",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=1.0,
        help="Delay between retries in seconds",
    )
    parser.add_argument(
        "--allow-ready-degraded",
        action="store_true",
        help="Allow readiness 503(degraded) during incident/degraded-mode checks.",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    timeout = max(0.5, float(args.timeout_seconds))
    retries = max(0, int(args.retries))
    retry_delay_seconds = max(0.0, float(args.retry_delay_seconds))

    checks = [
        ("live", f"{base}/health/live", 200),
        ("ready", f"{base}/health/ready", 200),
    ]

    failed = False
    for name, url, expected in checks:
        ok = _check_with_retry(
            name=name,
            url=url,
            expected=expected,
            timeout=timeout,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
            allow_ready_degraded=bool(args.allow_ready_degraded),
        )
        failed = failed or (not ok)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
