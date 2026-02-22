import importlib.util
from pathlib import Path


def _load_slo_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_slo_policy.py"
    spec = importlib.util.spec_from_file_location("check_slo_policy", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_slo_policy_main_passes_with_minimal_valid_doc(tmp_path, capsys):
    module = _load_slo_module()
    slo_file = tmp_path / "SLO.md"
    slo_file.write_text(
        "\n".join(
            [
                "## Scope",
                "## SLI Definitions",
                "## SLO Targets",
                "99.9%",
                "/health/live",
                "/health/ready",
                "## Error Budget Policy",
                "error budget",
                "## Alert Policy",
                "## Deployment Guardrails",
            ]
        ),
        encoding="utf-8",
    )
    module.SLO_DOC = slo_file

    assert module.main() == 0
    captured = capsys.readouterr()
    assert "SLO policy check passed" in captured.out


def test_slo_policy_main_fails_with_missing_required_content(tmp_path, capsys):
    module = _load_slo_module()
    slo_file = tmp_path / "SLO.md"
    slo_file.write_text("## Scope\n", encoding="utf-8")
    module.SLO_DOC = slo_file

    assert module.main() == 1
    captured = capsys.readouterr()
    assert "SLO policy check failed" in captured.out
