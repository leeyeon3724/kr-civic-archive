#!/usr/bin/env python3
"""Check liveness/readiness endpoints for deployment guardrails."""

from __future__ import annotations

import argparse
import json
import sys
import time
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
) -> bool:
    attempts = max(1, retries + 1)
    for attempt in range(1, attempts + 1):
        status, body = _http_get_json(url, timeout)
        if status == expected:
            print(f"[OK] {name}: {status} ({url}) [attempt {attempt}/{attempts}]")
            return True

        if attempt < attempts:
            time.sleep(max(0.0, retry_delay_seconds))
            continue

        print(f"[FAIL] {name}: expected {expected}, got {status} ({url}) [attempt {attempt}/{attempts}]")
        print(f"       body={body}")
        return False
    return False


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
        )
        failed = failed or (not ok)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
