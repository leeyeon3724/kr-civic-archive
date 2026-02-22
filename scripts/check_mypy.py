#!/usr/bin/env python3
"""Run mypy for project typed scope."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS = [
    "app/__init__.py",
    "app/bootstrap",
    "app/config.py",
    "app/security.py",
    "app/observability.py",
    "app/routes",
    "app/services",
    "app/ports",
    "app/repositories",
    "scripts/check_commit_messages.py",
    "scripts/check_docs_routes.py",
    "scripts/check_mypy.py",
    "scripts/check_runtime_health.py",
    "scripts/check_schema_policy.py",
    "scripts/check_slo_policy.py",
    "scripts/check_quality_metrics.py",
    "scripts/check_version_consistency.py",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run mypy with project defaults.")
    parser.add_argument(
        "--mode",
        choices=("fail", "warn"),
        default=(str(os.environ.get("MYPY_MODE", "fail")).strip().lower() or "fail"),
        help="Validation mode. fail=exit 1 on mypy errors, warn=print warnings only.",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        default=None,
        help="Optional explicit targets. Defaults to project target set.",
    )
    return parser


def parse_targets(raw_targets: list[str] | None) -> list[str]:
    if raw_targets:
        return [target.strip() for target in raw_targets if target.strip()]

    env_targets = str(os.environ.get("MYPY_TARGETS", "")).strip()
    if env_targets:
        return [target.strip() for target in env_targets.split(",") if target.strip()]

    return list(DEFAULT_TARGETS)


def main() -> int:
    args = build_parser().parse_args()
    targets = parse_targets(args.targets)
    if not targets:
        print("No mypy targets resolved.")
        return 2

    command = [
        sys.executable,
        "-m",
        "mypy",
        "--config-file",
        str(PROJECT_ROOT / "mypy.ini"),
        *targets,
    ]

    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if stdout:
        print(stdout)
    if stderr:
        print(stderr)

    if completed.returncode == 0:
        print("Mypy check passed.")
        return 0

    print("Mypy check found issues.")
    return 0 if args.mode == "warn" else int(completed.returncode)


if __name__ == "__main__":
    sys.exit(main())
