import importlib.util
from pathlib import Path


def _load_version_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_version_consistency.py"
    spec = importlib.util.spec_from_file_location("check_version_consistency", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_version_consistency_main_passes_for_valid_inputs(tmp_path, monkeypatch, capsys):
    module = _load_version_module()

    version_file = tmp_path / "version.py"
    app_init_file = tmp_path / "__init__.py"
    changelog_file = tmp_path / "CHANGELOG.md"
    workflow_file = tmp_path / "release-tag.yml"

    version_file.write_text('APP_VERSION = "1.2.3"\n', encoding="utf-8")
    app_init_file.write_text(
        "from app.version import APP_VERSION\napp = FastAPI(version=APP_VERSION)\n",
        encoding="utf-8",
    )
    changelog_file.write_text(
        "## [Unreleased]\n\n## [1.2.3]\n- release notes\n",
        encoding="utf-8",
    )
    workflow_file.write_text(
        "python scripts/check_version_consistency.py\n",
        encoding="utf-8",
    )

    module.VERSION_FILE = version_file
    module.APP_INIT_FILE = app_init_file
    module.CHANGELOG_FILE = changelog_file
    module.RELEASE_WORKFLOW_FILE = workflow_file
    monkeypatch.delenv("EXPECTED_VERSION", raising=False)

    assert module.main() == 0
    captured = capsys.readouterr()
    assert "Version consistency check passed" in captured.out


def test_version_consistency_main_fails_on_expected_version_mismatch(tmp_path, monkeypatch, capsys):
    module = _load_version_module()

    version_file = tmp_path / "version.py"
    app_init_file = tmp_path / "__init__.py"
    changelog_file = tmp_path / "CHANGELOG.md"
    workflow_file = tmp_path / "release-tag.yml"

    version_file.write_text('APP_VERSION = "1.2.3"\n', encoding="utf-8")
    app_init_file.write_text(
        "from app.version import APP_VERSION\napp = FastAPI(version=APP_VERSION)\n",
        encoding="utf-8",
    )
    changelog_file.write_text(
        "## [Unreleased]\n\n## [1.2.3]\n- release notes\n",
        encoding="utf-8",
    )
    workflow_file.write_text(
        "python scripts/check_version_consistency.py\n",
        encoding="utf-8",
    )

    module.VERSION_FILE = version_file
    module.APP_INIT_FILE = app_init_file
    module.CHANGELOG_FILE = changelog_file
    module.RELEASE_WORKFLOW_FILE = workflow_file
    monkeypatch.setenv("EXPECTED_VERSION", "1.2.4")

    assert module.main() == 1
    captured = capsys.readouterr()
    assert "must match EXPECTED_VERSION" in captured.out
