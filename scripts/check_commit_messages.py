#!/usr/bin/env python3
"""Validate commit subjects against project commit message policy."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ALLOWED_TYPES = ("feat", "fix", "docs", "refactor", "chore", "test", "ci", "build", "perf", "revert")
SCOPE_PATTERN = r"(?:p\d+|api|db|ops|security|deps|docs|ci|release|bench|infra)"
MAX_SUBJECT_LENGTH = 72
MERGE_PREFIXES = ("Merge ", "Revert \"Merge ")

COMMIT_SUBJECT_PATTERN = re.compile(
    rf"^(?P<type>{'|'.join(ALLOWED_TYPES)})\((?P<scope>{SCOPE_PATTERN})\)(?P<breaking>!)?: (?P<subject>.+)$"
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def lint_subject(subject: str) -> list[str]:
    normalized = subject.strip()
    if not normalized:
        return ["subject is empty"]
    if normalized.startswith(MERGE_PREFIXES):
        return []

    match = COMMIT_SUBJECT_PATTERN.match(normalized)
    if not match:
        return [
            "does not match required format: "
            "<type>(<scope>): <subject> "
            f"(allowed types: {', '.join(ALLOWED_TYPES)})"
        ]

    payload = match.group("subject")
    errors: list[str] = []
    if len(payload) > MAX_SUBJECT_LENGTH:
        errors.append(f"subject length must be <= {MAX_SUBJECT_LENGTH} characters")
    if payload.endswith("."):
        errors.append("subject must not end with a period")
    if not re.match(r"[a-z0-9]", payload):
        errors.append("subject must start with a lowercase letter or digit")
    return errors


def load_subjects_from_git(rev_range: str, max_count: int) -> list[tuple[str, str]]:
    command = ["git", "log", "--format=%H%x09%s"]
    if max_count > 0:
        command.extend(["-n", str(max_count)])
    command.append(rev_range)
    output = subprocess.check_output(command, text=True)
    rows: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        if "\t" not in line:
            continue
        commit_hash, subject = line.split("\t", 1)
        rows.append((commit_hash.strip(), subject.strip()))
    return rows


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate commit message subjects.")
    parser.add_argument(
        "--rev-range",
        default="HEAD~1..HEAD",
        help="Git revision range/revision expression passed to `git log`.",
    )
    parser.add_argument(
        "--max-count",
        type=int,
        default=0,
        help="Maximum number of commits to inspect when reading from git log.",
    )
    parser.add_argument(
        "--message-file",
        default=None,
        help="Commit message file path (for git commit-msg hook).",
    )
    parser.add_argument(
        "--mode",
        choices=("fail", "warn"),
        default=(str(os.environ.get("COMMIT_MESSAGE_LINT_MODE", "fail")).strip().lower() or "fail"),
        help="Validation mode. fail=exit 1 on violations, warn=print warnings only.",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    violations: list[str] = []

    if args.message_file:
        message_path = Path(args.message_file)
        if not message_path.exists():
            print(f"Commit message file not found: {message_path}")
            return 2
        lines = read_text(message_path).splitlines()
        subject = lines[0] if lines else ""
        errors = lint_subject(subject)
        if errors:
            violations.extend([f"{subject}: {error}" for error in errors])
    else:
        try:
            entries = load_subjects_from_git(args.rev_range, max(0, int(args.max_count)))
        except subprocess.CalledProcessError as exc:
            print(f"Failed to read git log for range `{args.rev_range}`: {exc}")
            return 2

        for commit_hash, subject in entries:
            errors = lint_subject(subject)
            if errors:
                short_hash = commit_hash[:8]
                violations.extend([f"{short_hash} `{subject}`: {error}" for error in errors])

    if violations:
        heading = "Commit message policy violations detected."
        print(heading)
        for line in violations:
            print(f" - {line}")
        return 0 if args.mode == "warn" else 1

    print("Commit message policy check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
