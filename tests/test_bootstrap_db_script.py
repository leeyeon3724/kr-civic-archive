import importlib.util
import subprocess
from pathlib import Path


def _load_bootstrap_db_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_db.py"
    spec = importlib.util.spec_from_file_location("bootstrap_db", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_db_fails_when_env_file_and_required_db_env_are_missing(tmp_path, capsys):
    module = _load_bootstrap_db_module()

    exit_code = module.main(project_root=tmp_path, environ={})
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Missing .env for local bootstrap" in captured.err
    assert "Copy `.env.example` to `.env`" in captured.err


def test_bootstrap_db_runs_with_required_db_env_without_env_file(tmp_path, monkeypatch):
    module = _load_bootstrap_db_module()
    env = {
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "app_user",
        "POSTGRES_PASSWORD": "change_me",
        "POSTGRES_DB": "civic_archive",
    }

    called = {}

    def fake_run(cmd, check):
        called["cmd"] = cmd
        called["check"] = check
        return 0

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.main(project_root=tmp_path, environ=env, python_executable="python3") == 0
    assert called["cmd"][1:] == ["-m", "alembic", "upgrade", "head"]
    assert called["check"] is True


def test_bootstrap_db_returns_non_zero_when_alembic_fails(tmp_path, monkeypatch, capsys):
    module = _load_bootstrap_db_module()
    (tmp_path / ".env").write_text("POSTGRES_HOST=127.0.0.1\n", encoding="utf-8")

    def fake_run(_cmd, *, check):
        assert check is True
        raise subprocess.CalledProcessError(returncode=3, cmd="alembic upgrade head")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    exit_code = module.main(project_root=tmp_path, environ={})
    captured = capsys.readouterr()

    assert exit_code == 3
    assert "Database migration failed:" in captured.err
