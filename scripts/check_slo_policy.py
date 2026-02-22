#!/usr/bin/env python3
"""Validate SLO policy documentation baseline."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SLO_DOC = PROJECT_ROOT / "docs" / "SLO.md"

REQUIRED_HEADINGS = [
    "## Scope",
    "## SLI Definitions",
    "## SLO Targets",
    "## Error Budget Policy",
    "## Alert Policy",
    "## Deployment Guardrails",
]

REQUIRED_PATTERNS = [
    re.compile(r"99\.9%"),
    re.compile(r"/health/live"),
    re.compile(r"/health/ready"),
    re.compile(r"error budget", re.IGNORECASE),
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def main() -> int:
    if not SLO_DOC.exists():
        print(f"Missing required file: {SLO_DOC}")
        return 1

    content = read_text(SLO_DOC)
    errors: list[str] = []

    for heading in REQUIRED_HEADINGS:
        if heading not in content:
            errors.append(f"Missing required heading in docs/SLO.md: {heading}")

    for pattern in REQUIRED_PATTERNS:
        if not pattern.search(content):
            errors.append(f"Missing required SLO content pattern: {pattern.pattern}")

    if errors:
        print("SLO policy check failed.")
        for line in errors:
            print(f" - {line}")
        return 1

    print("SLO policy check passed: docs/SLO.md baseline requirements satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
