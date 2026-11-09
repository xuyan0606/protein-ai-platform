"""Runner contract tests; numeric fixtures are parser inputs, not inference."""
import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).parents[1] / "model_services/thermostability/ddgun_runner.py"
spec = importlib.util.spec_from_file_location("ddgun_runner", MODULE)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def payload(**overrides):
    return {"sequence": "ACDE", "mutations": ["A1V"], "pdb_data": "", "chain_id": "A", "mode": "sequence", **overrides}


def test_parser_preserves_raw_sign_and_independent_wt():
    raw = "#SEQFILE VARIANT S_DDG[SEQ] T_DDG[SEQ] STABILITY[SEQ]\nq A1A 0.0 0.0 Neutral\nq A1V -0.4 -0.4 Decrease\n"
    assert runner._parse_output(raw, "sequence", ["A1V", "A1A"]) == {"A1A": 0., "A1V": -.4}


@pytest.mark.parametrize("rows", [
    "q A1V -0.4 -0.4 Increase\nq A1A 0 0 Neutral\n",
    "q A1V nan nan Neutral\nq A1A 0 0 Neutral\n",
    "q A1V -0.4 -0.4 Decrease\n",
    "q A1V -0.4 -0.4 Decrease\nq A1V -0.4 -0.4 Decrease\nq A1A 0 0 Neutral\n",
])
def test_rejects_untrustworthy_algorithm_output(rows):
    with pytest.raises(ValueError):
        runner._parse_output("#SEQFILE VARIANT S_DDG[SEQ] T_DDG[SEQ] STABILITY[SEQ]\n" + rows, "sequence", ["A1V", "A1A"])


@pytest.mark.parametrize("overrides", [
    {"mutations": ["C1V"]}, {"mutations": ["A1A"]}, {"mutations": ["A1V", "A1V"]},
    {"sequence": "ACXE"}, {"mode": "3d"}, {"chain_id": "A;exit"},
])
def test_invalid_request_blocks_without_scoring(tmp_path, overrides):
    result = runner.run_ddgun(payload(**overrides), tmp_path / "new")
    assert result["status"] == "blocked"
    assert result["predictions"] == []
    assert result["evidence"] is None


def test_missing_runtime_never_falls_back(tmp_path, monkeypatch):
    monkeypatch.delenv("DDGUN_SOURCE_DIR", raising=False)
    result = runner.run_ddgun(payload(), tmp_path / "new")
    assert result["status"] == "blocked"
    assert result["predictions"] == []
    assert result["algorithm_commit"] is None


def test_runtime_paths_reject_upstream_shell_injection():
    with pytest.raises(ValueError):
        runner._safe_path("/tmp/query;touch-injected")


def test_validation_database_requires_explicit_test_opt_in(tmp_path, monkeypatch):
    for key in ("DDGUN_SOURCE_DIR", "DDGUN_PYTHON", "DDGUN_HHBLITS", "DDGUN_DB_PREFIX"):
        monkeypatch.setenv(key, "/tmp/missing-ddgun-test-resource")
    monkeypatch.setenv("DDGUN_DATABASE_VERSION", "validation_only:fixture")
    monkeypatch.delenv("DDGUN_ALLOW_VALIDATION_DATABASE", raising=False)
    result = runner.run_ddgun(payload(), tmp_path / "new")
    assert "disabled for production" in result["blocked_reason"]
    assert result["predictions"] == []


def test_3d_rejects_wrong_chain_sequence(tmp_path):
    line = "ATOM      1  CA  ALA A   2      11.000  12.000  13.000  1.00 80.00           C\n"
    result = runner.run_ddgun(payload(pdb_data=line, mode="3d"), tmp_path / "new")
    assert result["status"] == "blocked"
    assert "1..L" in result["blocked_reason"]


def test_actual_pdb_input_uses_only_the_validated_first_model():
    pdb = "HEADER test\nMODEL        1\nATOM first\nENDMDL\nMODEL        2\nATOM second\nENDMDL\nEND\n"
    assert runner._first_model_pdb(pdb) == "HEADER test\nATOM first\nEND\n"
