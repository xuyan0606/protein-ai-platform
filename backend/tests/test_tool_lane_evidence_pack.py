from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "AI大模型" / "scripts"


def run_script(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT_DIR / script), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_tool_lane_evidence_pack_roundtrip(tmp_path: Path) -> None:
    report = tmp_path / "tool_lane_evidence_pack.json"
    receipts = tmp_path / "tool_lane_evidence_receipts.jsonl"
    validation = tmp_path / "tool_lane_evidence_pack_validation_report.json"

    build = run_script("build_tool_lane_evidence_pack.py", "--output", str(report), "--receipts", str(receipts))
    assert build.returncode == 0, build.stderr

    validate = run_script("validate_tool_lane_evidence_pack.py", "--report", str(report), "--receipts", str(receipts), "--output", str(validation))
    assert validate.returncode == 0, validate.stderr

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["local_only"] is True
    assert payload["summary"]["total_lanes"] == 8
    lanes = {row["lane_id"]: row for row in payload["lanes"]}
    assert lanes["proteinmpnn_design"]["status"] == "blocked"
    assert lanes["rfdiffusion_design"]["status"] == "blocked"
    assert lanes["alphafold2_folding"]["status"] == "blocked"

