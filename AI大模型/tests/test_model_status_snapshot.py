import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_model_status_snapshot.py"
SPEC = importlib.util.spec_from_file_location("build_model_status_snapshot", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class ModelStatusSnapshotTests(unittest.TestCase):
    def build_fixture(self, root: Path) -> None:
        reports = root / "reports"
        write_json(
            reports / "multitask_training_readiness_report.json",
            {
                "heads": {
                    "mutation_rank": {"rows": 0, "minimum_rows": 100, "ready": False},
                    "stability": {"rows": 0, "minimum_rows": 100, "ready": False},
                    "activity_risk": {"rows": 6, "minimum_rows": 100, "ready": False},
                    "substrate_fit": {"rows": 0, "minimum_rows": 100, "ready": False},
                    "assay_success": {"rows": 0, "minimum_rows": 100, "ready": False},
                },
                "ready_head_count": 0,
                "training_execution_allowed": False,
            },
        )
        write_json(
            reports / "five_head_training_execution_contract_report.json",
            {
                "head_rows": {"activity_risk": {"label_rows": 6}},
                "ready_head_count": 0,
                "training_execution_allowed": False,
            },
        )
        write_json(
            reports / "advanced_model_feature_contract_validation_report.json",
            {
                "feature_contract": {
                    "ready_family_counts": {
                        "msa_conservation": 158,
                        "structure_graph": 34,
                        "structure_site": 7,
                    }
                },
                "safe_for_model_claim": False,
            },
        )
        write_json(
            reports / "sequence_pretraining_continuous_selection.json",
            {
                "selected_batch": "continuous_full_v6",
                "sequence_count": 12830,
                "integrity_pass": True,
                "safe_for_model_claim": False,
            },
        )
        write_json(
            reports / "ddg_backend_readiness_report.json",
            {
                "reviewed_structure_rows": 34,
                "backends": [
                    {
                        "backend": "thermompnn",
                        "install_ready": True,
                        "runtime_ready": True,
                        "data_ready": True,
                        "model_weight_ready": True,
                        "ready_for_execution": True,
                        "commercial_status": "commercial_evaluation_allowed",
                    }
                ],
            },
        )
        write_json(
            reports / "model_quality_unlock_requirements_report.json",
            {
                "requirements": [
                    {
                        "requirement_id": "MQ-U003",
                        "current_state": {"thermompnn_ready": False},
                    }
                ]
            },
        )
        write_json(
            reports / "production_model_gate_20260829.json",
            {"production_ready": False, "evidence": {"strict_supervised_rows": 0}},
        )

    def test_snapshot_separates_model_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_fixture(root)
            snapshot = MODULE.build_snapshot(root)
            self.assertEqual(snapshot["stages"]["rule_mvp"]["status"], "baseline_only")
            self.assertEqual(snapshot["stages"]["pretraining"]["status"], "completed_pretraining_only")
            self.assertFalse(snapshot["stages"]["pretraining"]["safe_for_model_claim"])
            self.assertFalse(snapshot["stages"]["production"]["ready"])

    def test_snapshot_uses_current_feature_count_and_reports_stale_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_fixture(root)
            snapshot = MODULE.build_snapshot(root)
            self.assertEqual(snapshot["features"]["structure_graph"]["ready_rows"], 34)
            conflict_keys = {item["key"] for item in snapshot["consistency"]["conflicts"]}
            self.assertIn("thermompnn_ready", conflict_keys)

    def test_snapshot_reports_thermompnn_dimensions_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_fixture(root)
            tool = MODULE.build_snapshot(root)["tools"]["thermompnn"]
            self.assertEqual(
                set(tool),
                {
                    "installed",
                    "runtime_ready",
                    "data_ready",
                    "model_weight_ready",
                    "execution_ready",
                    "claim_eligible",
                    "commercial_status",
                },
            )
            self.assertTrue(tool["execution_ready"])
            self.assertFalse(tool["claim_eligible"])


if __name__ == "__main__":
    unittest.main()
