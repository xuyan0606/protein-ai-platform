#!/usr/bin/env python3
"""Run ThermoMPNN proxy ddG smoke inference for Venus-15B candidates."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
THERMOMPNN_ROOT = AI_ROOT / "cache" / "external" / "ThermoMPNN"
PROJECT_DIR = AI_ROOT / "Venus-15B淀粉酶项目"
PDB = PROJECT_DIR / "15B-AAP-noCa.pdb"
SEQUENCE = PROJECT_DIR / "淀粉酶15B序列.txt"
OUT_DIR = AI_ROOT / "cache" / "advanced_features" / "ddg_stability" / "thermompnn_venus15b_smoke"
REPORT_OUT = AI_ROOT / "reports" / "thermompnn_venus15b_smoke_report.json"

CANDIDATE_MUTATIONS = ["S265D", "D405N", "E331Q", "M204H"]
ALPHABET = "ACDEFGHIKLMNPQRSTVWYX"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_mutation(sequence: str, mutation: str) -> dict[str, Any]:
    wt = mutation[0]
    mutant = mutation[-1]
    canonical_position = int(mutation[1:-1])
    observed = sequence[canonical_position - 1] if 1 <= canonical_position <= len(sequence) else None
    return {
        "mutation": mutation,
        "wild_type": wt,
        "mutant": mutant,
        "canonical_position": canonical_position,
        "thermompnn_position_zero_based": canonical_position - 1,
        "observed_sequence_residue": observed,
        "numbering_verified": observed == wt,
    }


def classify_ddg(ddg: float) -> str:
    if ddg < -1.0:
        return "stabilizing_hypothesis"
    if -1.0 <= ddg <= 1.0:
        return "near_neutral_manual_review"
    if 1.0 < ddg <= 2.0:
        return "destabilizing_watch"
    return "destabilizing_no_go"


def run_inference(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    sys.path.insert(0, str(THERMOMPNN_ROOT))
    sys.path.insert(0, str(THERMOMPNN_ROOT / "analysis"))

    import torch  # type: ignore
    from datasets import Mutation  # type: ignore
    from omegaconf import OmegaConf  # type: ignore
    from protein_mpnn_utils import alt_parse_PDB  # type: ignore
    from thermompnn_benchmarking import get_trained_model  # type: ignore

    sequence = SEQUENCE.read_text(encoding="utf-8").strip()
    mutation_rows = [verify_mutation(sequence, mutation) for mutation in args.mutations]
    invalid_rows = [row for row in mutation_rows if not row["numbering_verified"]]
    if invalid_rows:
        raise ValueError(f"Mutation numbering failed: {invalid_rows}")

    cfg = OmegaConf.load(THERMOMPNN_ROOT / "local.yaml")
    cfg.platform.thermompnn_dir = str(THERMOMPNN_ROOT)
    config_override = OmegaConf.create({
        "training": {
            "num_workers": 0,
            "learn_rate": 0.001,
            "epochs": 100,
            "lr_schedule": True,
        },
        "model": {
            "hidden_dims": [64, 32],
            "subtract_mut": True,
            "num_final_layers": 2,
            "freeze_weights": True,
            "load_pretrained": True,
            "lightattn": True,
            "lr_schedule": True,
        },
    })
    cfg = OmegaConf.merge(cfg, config_override)

    model_path = args.model_path or THERMOMPNN_ROOT / "models" / "thermoMPNN_default.pt"
    mut_pdb = alt_parse_PDB(str(PDB), args.chain)
    final_mutations = [
        Mutation(
            position=row["thermompnn_position_zero_based"],
            wildtype=row["wild_type"],
            mutation=row["mutant"],
            ddG=None,
            pdb=mut_pdb[0]["name"],
        )
        for row in mutation_rows
    ]
    stdout_buffer = io.StringIO()
    with contextlib.redirect_stdout(stdout_buffer):
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = get_trained_model(model_name=str(model_path), config=cfg, override_custom=True)
        model = model.eval().to(device)
        with torch.no_grad():
            pred, _ = model(mut_pdb, final_mutations)
    rows = []
    for row, out in zip(mutation_rows, pred):
        ddg = float(out["ddG"].detach().cpu().item())
        rows.append({
            **row,
            "backend": "thermompnn",
            "ddg_pred_kcal_mol": ddg,
            "negative_ddg_is_stabilizing": True,
            "threshold_class": classify_ddg(ddg),
            "manual_review_required": True,
            "evidence_level": "computational_proxy",
            "limitations": [
                "ThermoMPNN predicted ddG proxy, not Rosetta/FoldX physics ddG",
                "not a wet-lab stability label",
                "single local smoke run; no replicate model ensemble",
            ],
        })
    metadata = {
        "model_path": str(model_path),
        "chain": args.chain,
        "device": str(device),
        "thermompnn_root": str(THERMOMPNN_ROOT),
        "thermompnn_commit": args.git_commit,
        "stdout": stdout_buffer.getvalue(),
    }
    return {"rows": rows, "metadata": metadata}, stdout_buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Venus-15B ThermoMPNN smoke inference")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--chain", default="A")
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--git-commit", default=None)
    parser.add_argument("--mutations", nargs="+", default=CANDIDATE_MUTATIONS)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    parameters_path = args.output_dir / "parameters.json"
    input_sha_path = args.output_dir / "input_structure.sha256"
    mutation_list_path = args.output_dir / "mutation_list.json"
    ddg_table_path = args.output_dir / "ddg_table.json"
    runtime_log_path = args.output_dir / "runtime.log"
    result_path = args.output_dir / "result.json"

    parameters = {
        "created_at": created_at,
        "backend": "thermompnn",
        "proxy_only": True,
        "project_id": "venus-15b",
        "input_pdb": str(PDB),
        "chain": args.chain,
        "mutations": args.mutations,
        "negative_ddg_is_stabilizing": True,
        "thresholds_kcal_mol": {
            "stabilizing_hypothesis": {"max": -1.0},
            "near_neutral_manual_review": {"min": -1.0, "max": 1.0},
            "destabilizing_watch": {"min": 1.0, "max": 2.0},
            "destabilizing_no_go": {"min": 2.0},
        },
    }
    write_json(parameters_path, parameters)
    input_sha_path.write_text(f"{sha256(PDB)}  {PDB.name}\n", encoding="utf-8")

    sequence = SEQUENCE.read_text(encoding="utf-8").strip()
    mutation_rows = [verify_mutation(sequence, mutation) for mutation in args.mutations]
    write_json(mutation_list_path, mutation_rows)

    try:
        inference, stdout = run_inference(args)
        rows = inference["rows"]
        write_json(ddg_table_path, rows)
        status = "completed"
        reason = None
        runtime_log = {
            "created_at": created_at,
            "status": status,
            "stdout": stdout,
            "stderr": "",
            "metadata": inference["metadata"],
        }
    except Exception as exc:  # pragma: no cover - exercised by local runtime
        rows = []
        status = "failed"
        reason = f"{type(exc).__name__}: {exc}"
        write_json(ddg_table_path, rows)
        runtime_log = {
            "created_at": created_at,
            "status": status,
            "stdout": "",
            "stderr": traceback.format_exc(),
        }
    write_json(runtime_log_path, runtime_log)

    artifact_paths = {
        "parameters": str(parameters_path),
        "input_structure_sha256": str(input_sha_path),
        "mutation_list": str(mutation_list_path),
        "ddg_table": str(ddg_table_path),
        "runtime_log": str(runtime_log_path),
    }
    result = {
        "case_id": "venus15b-thermompnn-candidate-smoke-001",
        "backend": "thermompnn",
        "status": status,
        "negative_ddg_is_stabilizing": True,
        "inputs": {
            "pdb": str(PDB),
            "chain": args.chain,
            "mutations": args.mutations,
            "input_pdb_sha256": sha256(PDB),
            "sequence_sha256": sha256(SEQUENCE),
        },
        "outputs": {
            "mutation_rows": len(rows),
            "ddg_table": rows,
            "ready_as_proxy_ddg_artifact": status == "completed" and len(rows) == len(args.mutations),
        },
        "artifacts": artifact_paths,
        "artifact_sha256": {
            name: sha256(Path(path))
            for name, path in artifact_paths.items()
        },
        "manual_review_required": True,
        "local_only": True,
        "reason": reason,
        "limitations": [
            "ThermoMPNN is a predicted ddG proxy backend",
            "Not Rosetta/PyRosetta/FoldX physics ddG",
            "Not a wet-lab stability label",
        ],
        "safe_for_model_claim": False,
    }
    write_json(result_path, result)
    write_json(args.report, result)
    print(json.dumps({
        "status": status,
        "mutation_rows": len(rows),
        "ready_as_proxy_ddg_artifact": result["outputs"]["ready_as_proxy_ddg_artifact"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
