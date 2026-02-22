from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DB_ENV_VARS: tuple[str, ...] = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
)


def has_required_db_env(environ: Mapping[str, str]) -> bool:
    return all(str(environ.get(name, "")).strip() for name in REQUIRED_DB_ENV_VARS)


def ensure_bootstrap_env_ready(*, project_root: Path, environ: Mapping[str, str]) -> None:
    env_file = project_root / ".env"
    if env_file.exists():
        return
    if has_required_db_env(environ):
        return
    raise RuntimeError(
        "Missing .env for local bootstrap. Copy `.env.example` to `.env` "
        "or set all required DB env vars: "
        + ", ".join(REQUIRED_DB_ENV_VARS)
    )


def run_alembic_upgrade_head(*, python_executable: str) -> None:
    cmd = [python_executable, "-m", "alembic", "upgrade", "head"]
    subprocess.run(cmd, check=True)


def main(
    *,
    project_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    python_executable: str | None = None,
) -> int:
    active_project_root = project_root or PROJECT_ROOT
    active_environ = environ or os.environ
    active_python_executable = python_executable or sys.executable

    try:
        ensure_bootstrap_env_ready(project_root=active_project_root, environ=active_environ)
        run_alembic_upgrade_head(python_executable=active_python_executable)
    except RuntimeError as exc:
        print(f"Bootstrap check failed: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"Database migration failed: {exc}", file=sys.stderr)
        return int(exc.returncode or 1)

    print("Database migration to head completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
