#!/usr/bin/env python3
"""Enforce schema-change policy: no manual DDL in app runtime code."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"

FORBIDDEN_PATTERNS = [
    re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bALTER\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bbootstrap_tables\s*\(", re.IGNORECASE),
]


def iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def main() -> int:
    violations: list[str] = []
    for path in iter_python_files(APP_DIR):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                rel = path.relative_to(PROJECT_ROOT)
                violations.append(f"{rel}: forbidden pattern '{pattern.pattern}'")

    if violations:
        print("Schema policy check failed. Manual DDL is forbidden in app runtime code.")
        for line in violations:
            print(f" - {line}")
        return 1

    print("Schema policy check passed: no manual DDL patterns found in app runtime code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

