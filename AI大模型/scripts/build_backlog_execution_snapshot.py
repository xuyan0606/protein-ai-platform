import argparse
import json
from pathlib import Path


def build_snapshot(base: Path):
    readiness = json.loads((base / "reports/training_readiness_report.json").read_text())
    master = json.loads((base / "reports/master_readiness_board.json").read_text())
    return {
        "generated_from": "reports/training_readiness_report.json",
        "local_executable": [
            {"item": "rerun_consistency_and_regression", "status": "available"},
            {"item": "review_2_unresolved_domain_intervals", "status": "human_required"},
        ],
        "human_required": [
            {"item": "mutation_numbering_and_provenance", "rows": 475},
            {"item": "structure_chain_mapping", "rows": readiness["feature_streams"]["structure_chain_mapping"]["remaining_unreviewed_rows"]},
            {"item": "training_authorization", "rows": readiness["feature_streams"]["experiment_feedback"]["reviewed_numbered_rows"]},
        ],
        "external_input_required": [
            {"item": "msa_conservation_features", "missing": readiness["feature_streams"]["msa_conservation"]["missing"], "status": "trusted_cache_ready", "strict_join_blocked": not readiness["ready_for_supervised_small_model_claim"]},
            {"item": "construct_fasta_and_accessions"},
            {"item": "gpu_or_long_md_runtime"},
        ],
        "gates": {"strict_ready_streams": master.get("ready_streams", 0), "claim_ready": readiness["ready_for_supervised_small_model_claim"], "training_execution_allowed": False, "release_ready": False},
    }


def main():
    p = argparse.ArgumentParser(); p.add_argument("--base", type=Path, required=True); p.add_argument("--output", type=Path, required=True); a = p.parse_args()
    out = build_snapshot(a.base); a.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n"); print(json.dumps(out, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
