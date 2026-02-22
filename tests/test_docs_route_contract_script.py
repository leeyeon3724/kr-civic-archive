import importlib.util
from pathlib import Path


def _load_docs_contract_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_docs_routes.py"
    spec = importlib.util.spec_from_file_location("check_docs_routes", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_discover_route_files_finds_app_routes():
    module = _load_docs_contract_module()
    route_files = module.discover_route_files(module.APP_ROOT)
    relative_paths = {path.relative_to(module.PROJECT_ROOT).as_posix() for path in route_files}
    assert "app/routes/news.py" in relative_paths
    assert "app/bootstrap/system_routes.py" in relative_paths
    assert "app/observability.py" in relative_paths


def test_extract_code_routes_contains_core_endpoints():
    module = _load_docs_contract_module()
    route_files = module.discover_route_files(module.APP_ROOT)
    code_routes = module.extract_code_routes(route_files)
    assert ("GET", "/api/news") in code_routes
    assert ("POST", "/api/news") in code_routes
    assert ("GET", "/health/ready") in code_routes
    assert ("GET", "/metrics") in code_routes


def test_check_backlog_policy_accepts_future_only_backlog():
    module = _load_docs_contract_module()
    backlog_text = """# Backlog
- 완료 이력은 기본적으로 `git log`로 관리합니다.
- 상태: `Planned`
"""
    assert module.check_backlog_policy(backlog_text) == []


def test_check_backlog_policy_rejects_completed_markers():
    module = _load_docs_contract_module()
    backlog_text = """# Backlog
- 완료 이력은 기본적으로 `git log`로 관리합니다.
- [x] remove legacy item
- 상태: `Completed`
"""
    errors = module.check_backlog_policy(backlog_text)
    assert any("checklist markers" in error for error in errors)
    assert any("Completed status entries" in error for error in errors)


def test_check_env_doc_requires_core_variables():
    module = _load_docs_contract_module()
    env_lines = [f"| `{var}` | `value` | description |" for var in module.REQUIRED_ENV_VARS if var != "JWT_SECRET"]
    env_text = "\n".join(env_lines)
    errors = module.check_env_doc(env_text)
    assert any("`JWT_SECRET`" in error for error in errors)


def test_check_env_example_requires_required_variables():
    module = _load_docs_contract_module()
    env_doc_defaults = {var: "`value`" for var in module.REQUIRED_ENV_VARS}
    env_example_lines = [f"{var}=value" for var in module.REQUIRED_ENV_VARS if var != "JWT_SECRET"]
    env_example_text = "\n".join(env_example_lines)
    errors = module.check_env_example(env_example_text, env_doc_defaults)
    assert any("`JWT_SECRET`" in error for error in errors)


def test_check_env_example_detects_default_mismatch():
    module = _load_docs_contract_module()
    errors = module.check_env_example("APP_ENV=production", {"APP_ENV": "`development`"})
    assert any("Default mismatch for `APP_ENV`" in error for error in errors)


def test_check_security_gate_alignment_detects_missing_command():
    module = _load_docs_contract_module()
    quality = "pip-audit -r requirements.txt -r requirements-dev.txt"
    contributing = quality
    errors = module.check_security_gate_alignment(quality, contributing)
    assert any("cyclonedx-py requirements" in error for error in errors)
    assert any("bandit -q -r app scripts -ll" in error for error in errors)


def test_check_debug_mode_doc_alignment_requires_reload_guidance():
    module = _load_docs_contract_module()
    errors = module.check_debug_mode_doc_alignment(
        env_text="DEBUG mode guide",
        api_text="DEBUG mention",
        architecture_text="DEBUG mention",
    )
    assert any("uvicorn --reload" in error for error in errors)
