#!/usr/bin/env python3
"""Validate single-source app version and changelog consistency."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = PROJECT_ROOT / "app" / "version.py"
APP_INIT_FILE = PROJECT_ROOT / "app" / "__init__.py"
CHANGELOG_FILE = PROJECT_ROOT / "docs" / "CHANGELOG.md"
RELEASE_WORKFLOW_FILE = PROJECT_ROOT / ".github" / "workflows" / "release-tag.yml"

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
VERSION_ASSIGN_RE = re.compile(r'^\s*APP_VERSION\s*=\s*"([^"]+)"\s*$', re.MULTILINE)
HARDCODED_FASTAPI_VERSION_RE = re.compile(r'version\s*=\s*"[^"]+"')
CHANGELOG_RELEASE_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def load_app_version() -> str:
    if not VERSION_FILE.exists():
        raise RuntimeError(f"Missing version file: {VERSION_FILE}")
    content = read_text(VERSION_FILE)
    match = VERSION_ASSIGN_RE.search(content)
    if not match:
        raise RuntimeError("app/version.py must define APP_VERSION = \"X.Y.Z\".")
    return match.group(1)


def main() -> int:
    try:
        version = load_app_version()
    except RuntimeError as exc:
        print(f"Version consistency check failed: {exc}")
        return 1

    errors: list[str] = []
    expected_version = (os.getenv("EXPECTED_VERSION") or "").strip()
    if not SEMVER_RE.match(version):
        errors.append(f"APP_VERSION must be SemVer (X.Y.Z): {version}")
    if expected_version:
        if not SEMVER_RE.match(expected_version):
            errors.append(f"EXPECTED_VERSION must be SemVer (X.Y.Z): {expected_version}")
        elif expected_version != version:
            errors.append(f"APP_VERSION ({version}) must match EXPECTED_VERSION ({expected_version})")

    if not APP_INIT_FILE.exists():
        errors.append(f"Missing app init file: {APP_INIT_FILE}")
    else:
        app_init = read_text(APP_INIT_FILE)
        if "from app.version import APP_VERSION" not in app_init:
            errors.append("app/__init__.py must import APP_VERSION from app/version.py")
        if "version=APP_VERSION" not in app_init:
            errors.append("FastAPI version must use APP_VERSION (version=APP_VERSION)")
        if HARDCODED_FASTAPI_VERSION_RE.search(app_init):
            errors.append("Hardcoded FastAPI version detected in app/__init__.py")

    if not CHANGELOG_FILE.exists():
        errors.append(f"Missing changelog file: {CHANGELOG_FILE}")
    else:
        changelog = read_text(CHANGELOG_FILE)
        if "## [Unreleased]" not in changelog:
            errors.append("docs/CHANGELOG.md must contain section: ## [Unreleased]")
        if f"## [{version}]" not in changelog:
            errors.append(f"docs/CHANGELOG.md must contain section: ## [{version}]")
        released_versions = CHANGELOG_RELEASE_RE.findall(changelog)
        if released_versions:
            latest_released = released_versions[0]
            if latest_released != version:
                errors.append(
                    f"Latest released changelog section must match APP_VERSION. "
                    f"Found [{latest_released}], expected [{version}]"
                )
        else:
            errors.append("docs/CHANGELOG.md must contain at least one released section: ## [X.Y.Z]")

    if not RELEASE_WORKFLOW_FILE.exists():
        errors.append(f"Missing release workflow file: {RELEASE_WORKFLOW_FILE}")
    else:
        release_workflow = read_text(RELEASE_WORKFLOW_FILE)
        if "check_version_consistency.py" not in release_workflow:
            errors.append(
                ".github/workflows/release-tag.yml must run scripts/check_version_consistency.py"
            )

    if errors:
        print("Version consistency check failed.")
        for line in errors:
            print(f" - {line}")
        return 1

    print(f"Version consistency check passed: APP_VERSION={version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
