#!/usr/bin/env python3
"""Check API endpoint docs against auto-discovered route declarations."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Iterable, Optional

METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "app"
ENV_ASSIGNMENT_RE = re.compile(r"^([A-Z0-9_]+)\s*=\s*(.*)$")
REQUIRED_README_LINKS = [
    "docs/API.md",
    "docs/ARCHITECTURE.md",
    "docs/ENV.md",
    "docs/QUALITY_GATES.md",
    "docs/GUARDRAILS.md",
    "docs/QUALITY_METRICS.md",
    "docs/BACKLOG.md",
]
REQUIRED_ENV_VARS = [
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "APP_ENV",
    "SECURITY_STRICT_MODE",
    "REQUIRE_API_KEY",
    "API_KEY",
    "REQUIRE_JWT",
    "JWT_SECRET",
    "RATE_LIMIT_PER_MINUTE",
    "RATE_LIMIT_BACKEND",
    "REDIS_URL",
    "INGEST_MAX_BATCH_ITEMS",
    "MAX_REQUEST_BODY_BYTES",
]
REQUIRED_SECURITY_COMMANDS = [
    "cyclonedx-py requirements --output-reproducible --of JSON -o sbom-runtime.cdx.json requirements.txt",
    "pip-audit -r requirements.txt -r requirements-dev.txt",
    "bandit -q -r app scripts -ll",
]
REQUIRED_PR_TEMPLATE_LINES = [
    "## 품질 지표 (docs/QUALITY_METRICS.md)",
    "- [ ] 성능 영향",
    "- [ ] 안정성 영향",
    "- [ ] 신뢰성 영향",
    "- [ ] 유지보수성 영향",
    "- [ ] 리팩토링 우선순위 근거(P0-P3) 및 지금 수행하는 이유",
    "## 정책 정합성 (docs/GUARDRAILS.md)",
    "- [ ] 보안/런타임 정책 문서 동기화",
    "- [ ] 문맥별 가드 명령 세트 검토 (로컬/PR/릴리스/인시던트)",
]
REQUIRED_GUARDRAILS_HEADINGS = [
    "## 로컬/CI 기본선",
    "## PR 문맥",
    "## 릴리스 문맥",
    "## 인시던트/강등 문맥",
]
REQUIRED_GUARDRAILS_PATTERNS = [
    re.compile(r"check_commit_messages\.py"),
    re.compile(r"check_runtime_health\.py"),
    re.compile(r"benchmark_queries\.py"),
    re.compile(r"check_quality_metrics\.py"),
    re.compile(r"allow-ready-degraded"),
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def normalize_path(path: str) -> str:
    normalized = path.strip()
    normalized = re.sub(r"<[^>]+>", "{param}", normalized)
    normalized = re.sub(r"\{[^}]+\}", "{param}", normalized)
    normalized = re.sub(r"/{2,}", "/", normalized)
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def _extract_methods(call: ast.Call) -> set[str]:
    methods: set[str] = {"GET"}
    for kw in call.keywords:
        if kw.arg != "methods":
            continue
        methods = set()
        if isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
            for elt in kw.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    method = elt.value.upper()
                    if method in METHODS:
                        methods.add(method)
        if not methods:
            methods = {"GET"}
    return methods


def _extract_fastapi_method(func: ast.AST) -> Optional[str]:
    if not isinstance(func, ast.Attribute):
        return None
    candidate = func.attr.upper()
    if candidate in METHODS:
        return candidate
    return None


def discover_route_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for file_path in sorted(root.rglob("*.py")):
        if "__pycache__" in file_path.parts:
            continue
        if file_path.name.startswith("_"):
            continue
        files.append(file_path)
    return files


def extract_code_routes(files: Iterable[Path]) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()

    for file_path in files:
        tree = ast.parse(read_text(file_path), filename=str(file_path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                func = dec.func
                method_from_fastapi = _extract_fastapi_method(func)

                if method_from_fastapi is None and (not isinstance(func, ast.Attribute) or func.attr != "route"):
                    continue
                if not dec.args:
                    continue
                first_arg = dec.args[0]
                if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
                    continue

                path = normalize_path(first_arg.value)
                if method_from_fastapi is not None:
                    methods = {method_from_fastapi}
                else:
                    methods = _extract_methods(dec)
                for method in methods:
                    routes.add((method, path))

    return routes


def extract_doc_routes(file_path: Path) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()

    for raw_line in read_text(file_path).splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue

        columns = [c.strip() for c in line.strip("|").split("|")]
        if len(columns) < 2:
            continue

        method = columns[0].upper()
        path = columns[1].strip("`")

        if method not in METHODS:
            continue
        if not path.startswith("/"):
            continue

        routes.add((method, normalize_path(path)))

    return routes


def report_diff(name: str, expected: set[tuple[str, str]], actual: set[tuple[str, str]]) -> list[str]:
    lines: list[str] = []

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)

    if missing:
        lines.append(f"[{name}] Missing endpoints:")
        lines.extend(f"  - {method} {path}" for method, path in missing)

    if extra:
        lines.append(f"[{name}] Unknown endpoints (not in code):")
        lines.extend(f"  - {method} {path}" for method, path in extra)

    return lines


def check_readme_links(readme_text: str) -> list[str]:
    errors: list[str] = []
    for link in REQUIRED_README_LINKS:
        if link not in readme_text:
            errors.append(f"[README.md] Missing required link: {link}")
    return errors


def _normalize_default_value(raw: str) -> str:
    value = raw.strip()
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        value = value[1:-1]
    if (
        value.startswith('"')
        and value.endswith('"')
        or value.startswith("'")
        and value.endswith("'")
    ) and len(value) >= 2:
        value = value[1:-1]
    return value


def extract_env_doc_defaults(env_text: str) -> dict[str, str]:
    defaults_by_var: dict[str, str] = {}

    for raw_line in env_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        columns = [c.strip() for c in line.strip("|").split("|")]
        if len(columns) < 3:
            continue

        var_column = columns[0]
        default_column = columns[1]
        if not (var_column.startswith("`") and var_column.endswith("`")):
            continue

        variable = var_column.strip("`").strip()
        if not re.fullmatch(r"[A-Z0-9_]+", variable):
            continue

        defaults_by_var[variable] = default_column
    return defaults_by_var


def check_env_doc(env_text: str) -> list[str]:
    errors: list[str] = []
    defaults_by_var = extract_env_doc_defaults(env_text)

    for required_var in REQUIRED_ENV_VARS:
        if required_var not in defaults_by_var:
            errors.append(f"[docs/ENV.md] Missing required variable row: `{required_var}`")

    for variable, default in defaults_by_var.items():
        if default == "":
            errors.append(f"[docs/ENV.md] Missing default column value for `{variable}`")

    return errors


def check_env_example(env_example_text: str, env_doc_defaults: dict[str, str]) -> list[str]:
    errors: list[str] = []
    defaults_by_var: dict[str, str] = {}
    duplicates: set[str] = set()

    for line_no, raw_line in enumerate(env_example_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = ENV_ASSIGNMENT_RE.fullmatch(line)
        if not match:
            errors.append(f"[.env.example] Invalid line format (line {line_no}): {line}")
            continue

        variable = match.group(1).strip()
        default_value = match.group(2).strip()
        if variable in defaults_by_var:
            duplicates.add(variable)
        defaults_by_var[variable] = default_value

    for variable in sorted(duplicates):
        errors.append(f"[.env.example] Duplicate variable assignment: `{variable}`")

    for required_var in REQUIRED_ENV_VARS:
        if required_var not in defaults_by_var:
            errors.append(f"[.env.example] Missing required variable: `{required_var}`")

    for variable in env_doc_defaults:
        if variable not in defaults_by_var:
            errors.append(f"[.env.example] Missing docs/ENV.md variable: `{variable}`")

    for variable, doc_default in env_doc_defaults.items():
        if variable not in defaults_by_var:
            continue
        doc_value = _normalize_default_value(doc_default)
        env_value = _normalize_default_value(defaults_by_var[variable])
        if doc_value != env_value:
            errors.append(
                f"[.env.example] Default mismatch for `{variable}`: "
                f"docs/ENV.md=`{doc_value}` vs .env.example=`{env_value}`"
            )

    return errors


def check_backlog_policy(backlog_text: str) -> list[str]:
    errors: list[str] = []

    if "# 백로그" not in backlog_text:
        errors.append("[docs/BACKLOG.md] Title must include `# 백로그`.")
    if "git log" not in backlog_text:
        errors.append("[docs/BACKLOG.md] Missing policy text for completed-history tracking via `git log`.")
    if "[x]" in backlog_text.lower():
        errors.append("[docs/BACKLOG.md] Completed checklist markers (`[x]`) are not allowed.")
    if re.search(r"(?im)^\s*-\s*status\s*:\s*`?completed`?\s*$", backlog_text):
        errors.append("[docs/BACKLOG.md] Completed status entries are not allowed.")
    if re.search(r"(?im)^\s*-\s*상태\s*:\s*`?completed`?\s*$", backlog_text):
        errors.append("[docs/BACKLOG.md] Completed status entries are not allowed.")

    return errors


def check_security_gate_alignment(quality_gates_text: str, contributing_text: str) -> list[str]:
    errors: list[str] = []
    for command in REQUIRED_SECURITY_COMMANDS:
        if command not in quality_gates_text:
            errors.append(f"[docs/QUALITY_GATES.md] Missing security command: `{command}`")
        if command not in contributing_text:
            errors.append(f"[docs/CONTRIBUTING.md] Missing security command: `{command}`")
    return errors


def check_debug_mode_doc_alignment(*, env_text: str, api_text: str, architecture_text: str) -> list[str]:
    errors: list[str] = []
    required_hint = "uvicorn --reload"
    required_terms = ["SECURITY_STRICT_MODE", "APP_ENV=production"]
    documents = [
        ("docs/ENV.md", env_text),
        ("docs/API.md", api_text),
        ("docs/ARCHITECTURE.md", architecture_text),
    ]
    for doc_name, text in documents:
        if "DEBUG" not in text:
            errors.append(f"[{doc_name}] Missing DEBUG guidance.")
        if required_hint not in text:
            errors.append(f"[{doc_name}] Missing DEBUG reload guidance: `{required_hint}`.")
        for term in required_terms:
            if term not in text:
                errors.append(f"[{doc_name}] Missing strict-mode guidance keyword: `{term}`.")
    return errors


def check_pr_template_quality_alignment(pr_template_text: str) -> list[str]:
    errors: list[str] = []
    for required_line in REQUIRED_PR_TEMPLATE_LINES:
        if required_line not in pr_template_text:
            errors.append(f"[.github/pull_request_template.md] Missing required line: `{required_line}`")
    return errors


def check_guardrails_doc(guardrails_text: str) -> list[str]:
    errors: list[str] = []
    for heading in REQUIRED_GUARDRAILS_HEADINGS:
        if heading not in guardrails_text:
            errors.append(f"[docs/GUARDRAILS.md] Missing required heading: `{heading}`")
    for pattern in REQUIRED_GUARDRAILS_PATTERNS:
        if not pattern.search(guardrails_text):
            errors.append(f"[docs/GUARDRAILS.md] Missing required guardrail pattern: `{pattern.pattern}`")
    return errors


def main() -> int:
    route_files = discover_route_files(APP_ROOT)
    if not route_files:
        print(f"No route source files discovered under: {APP_ROOT}")
        return 2

    readme_file = PROJECT_ROOT / "README.md"
    api_file = PROJECT_ROOT / "docs" / "API.md"
    env_file = PROJECT_ROOT / "docs" / "ENV.md"
    backlog_file = PROJECT_ROOT / "docs" / "BACKLOG.md"
    env_example_file = PROJECT_ROOT / ".env.example"
    quality_gates_file = PROJECT_ROOT / "docs" / "QUALITY_GATES.md"
    guardrails_file = PROJECT_ROOT / "docs" / "GUARDRAILS.md"
    contributing_file = PROJECT_ROOT / "docs" / "CONTRIBUTING.md"
    architecture_file = PROJECT_ROOT / "docs" / "ARCHITECTURE.md"
    pr_template_file = PROJECT_ROOT / ".github" / "pull_request_template.md"

    for file_path in [
        readme_file,
        api_file,
        env_file,
        backlog_file,
        env_example_file,
        quality_gates_file,
        guardrails_file,
        contributing_file,
        architecture_file,
        pr_template_file,
    ]:
        if not file_path.exists():
            print(f"Required file not found: {file_path}")
            return 2

    code_routes = extract_code_routes(route_files)
    api_routes = extract_doc_routes(api_file)
    readme_text = read_text(readme_file)
    env_text = read_text(env_file)
    env_example_text = read_text(env_example_file)
    backlog_text = read_text(backlog_file)
    quality_gates_text = read_text(quality_gates_file)
    guardrails_text = read_text(guardrails_file)
    contributing_text = read_text(contributing_file)
    architecture_text = read_text(architecture_file)
    pr_template_text = read_text(pr_template_file)
    env_doc_defaults = extract_env_doc_defaults(env_text)

    errors: list[str] = []
    errors.extend(report_diff("docs/API.md", code_routes, api_routes))
    errors.extend(check_readme_links(readme_text))
    errors.extend(check_env_doc(env_text))
    errors.extend(check_env_example(env_example_text, env_doc_defaults))
    errors.extend(check_backlog_policy(backlog_text))
    errors.extend(check_security_gate_alignment(quality_gates_text, contributing_text))
    errors.extend(check_guardrails_doc(guardrails_text))
    errors.extend(check_pr_template_quality_alignment(pr_template_text))
    errors.extend(
        check_debug_mode_doc_alignment(
            env_text=env_text,
            api_text=read_text(api_file),
            architecture_text=architecture_text,
        )
    )

    if errors:
        print("Route-documentation contract check failed.\n")
        print("\n".join(errors))
        return 1

    print(
        "Route-documentation contract check passed: "
        f"{len(code_routes)} endpoints verified in docs/API.md "
        f"(route files auto-discovered: {len(route_files)}), "
        "README links, ENV/.env.example docs, security gates, DEBUG docs, and BACKLOG policy verified."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
