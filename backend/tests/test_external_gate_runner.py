from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_makefile_exposes_external_gate_commands():
    content = (PROJECT_ROOT / "Makefile").read_text()
    assert "external-gates-plan:" in content
    assert "external-gate:" in content
    assert "external-gates-execute:" in content
