import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_five_head_training_hard_block_operator_packet.py"
SPEC = importlib.util.spec_from_file_location("build_five_head_training_hard_block_operator_packet", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class FiveHeadTrainingHardBlockOperatorPacketTests(unittest.TestCase):
    def test_packet_is_blocked_and_does_not_unlock_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "reports" / "model_status.json",
                {
                    "heads": {
                        "mutation_rank": {"label_rows": 0, "minimum_rows": 100, "ready": False},
                        "stability": {"label_rows": 0, "minimum_rows": 100, "ready": False},
                        "activity_risk": {"label_rows": 6, "minimum_rows": 100, "ready": False},
                        "substrate_fit": {"label_rows": 0, "minimum_rows": 100, "ready": False},
                        "assay_success": {"label_rows": 0, "minimum_rows": 100, "ready": False},
                    },
                    "stages": {
                        "research_training": {"training_execution_allowed": False},
                        "production": {"ready": False},
                    },
                },
            )
            write_json(
                root / "reports" / "wet_lab_mutant_library_unlock_status_report.json",
                {
                    "hard_blockers": [
                        "reviewed_16b_parent_sequence_missing",
                        "reviewed_4g_parent_sequence_missing",
                    ],
                    "wet_lab_summary": {
                        "authorized_rows": 8,
                        "numeric_training_candidate_rows": 12,
                    },
                },
            )
            write_json(
                root / "reports" / "wet_lab_mutant_library_feedback_authorization_worklist_report.json",
                {
                    "blocked_waiting_for_authorization_rows": 4,
                    "critical_tradeoff_feedback_candidate_ids": ["wetlab-mutlib-399056b37800644f9a7b"],
                },
            )
            write_json(
                root / "reports" / "numbering_review_operator_queue.json",
                {"open_numbering_rows": 471, "decision_rows": 4},
            )
            packet = MODULE.build_packet(root)
            self.assertEqual(packet["status"], "blocked_waiting_for_human_or_external_input")
            self.assertFalse(packet["training_execution_allowed"])
            self.assertFalse(packet["safe_for_model_claim"])
            self.assertEqual(packet["heads"]["activity_risk"]["missing_to_minimum"], 94)
            self.assertIn("reviewed_16b_parent_sequence", " ".join(packet["required_human_inputs"]))


if __name__ == "__main__":
    unittest.main()
