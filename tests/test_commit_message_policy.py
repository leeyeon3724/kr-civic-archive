import importlib.util
from pathlib import Path


def _load_commit_policy_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_commit_messages.py"
    spec = importlib.util.spec_from_file_location("check_commit_messages", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lint_subject_accepts_required_format():
    module = _load_commit_policy_module()
    assert module.lint_subject("feat(p5): add commit message validator") == []
    assert module.lint_subject("docs(api): update error response contract") == []


def test_lint_subject_rejects_missing_scope():
    module = _load_commit_policy_module()
    errors = module.lint_subject("feat: missing scope")
    assert any("required format" in message for message in errors)


def test_lint_subject_rejects_trailing_period():
    module = _load_commit_policy_module()
    errors = module.lint_subject("chore(ci): update workflow.")
    assert "subject must not end with a period" in errors


def test_lint_subject_ignores_merge_commits():
    module = _load_commit_policy_module()
    assert module.lint_subject("Merge branch 'feature/a' into main") == []
