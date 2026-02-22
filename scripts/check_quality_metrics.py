#!/usr/bin/env python3
"""Validate quality metrics policy documentation baseline."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUALITY_METRICS_DOC = PROJECT_ROOT / "docs" / "QUALITY_METRICS.md"

REQUIRED_HEADINGS = [
    "## 범위",
    "## 성능 지표",
    "## 안정성 지표",
    "## 신뢰성 지표",
    "## 유지보수성 지표",
    "## 검토 주기",
    "## 릴리스 게이트",
]

REQUIRED_PATTERNS = [
    re.compile(r"p95", re.IGNORECASE),
    re.compile(r"ingest", re.IGNORECASE),
    re.compile(r"throughput", re.IGNORECASE),
    re.compile(r"query count", re.IGNORECASE),
    re.compile(r"4xx", re.IGNORECASE),
    re.compile(r"5xx", re.IGNORECASE),
    re.compile(r"mttr", re.IGNORECASE),
    re.compile(r"sla", re.IGNORECASE),
    re.compile(r"/health/live"),
    re.compile(r"/health/ready"),
    re.compile(r"rate_limit_backend", re.IGNORECASE),
    re.compile(r"fallback", re.IGNORECASE),
    re.compile(r"request_id", re.IGNORECASE),
    re.compile(r"policy regression", re.IGNORECASE),
    re.compile(r"coverage", re.IGNORECASE),
    re.compile(r"mypy", re.IGNORECASE),
    re.compile(r"check_docs_routes\.py"),
    re.compile(r"check_quality_metrics\.py"),
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def validate_quality_metrics_content(content: str) -> list[str]:
    errors: list[str] = []

    for heading in REQUIRED_HEADINGS:
        if heading not in content:
            errors.append(f"Missing required heading in docs/QUALITY_METRICS.md: {heading}")

    for pattern in REQUIRED_PATTERNS:
        if not pattern.search(content):
            errors.append(f"Missing required quality-metric content pattern: {pattern.pattern}")

    return errors


def main() -> int:
    if not QUALITY_METRICS_DOC.exists():
        print(f"Missing required file: {QUALITY_METRICS_DOC}")
        return 1

    content = read_text(QUALITY_METRICS_DOC)
    errors = validate_quality_metrics_content(content)
    if errors:
        print("Quality metrics policy check failed.")
        for line in errors:
            print(f" - {line}")
        return 1

    print("Quality metrics policy check passed: docs/QUALITY_METRICS.md baseline requirements satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
