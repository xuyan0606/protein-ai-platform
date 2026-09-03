import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_literature_measurement_review_queue.py"
SPEC = importlib.util.spec_from_file_location("lit_queue_validator", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class LiteratureQueueValidatorTests(unittest.TestCase):
    def test_valid_pending_task(self):
        row = {"review_task_id": "lit-1", "measurement_ids": "m1|m2", "human_review_status": "pending_human_review", "training_eligible": False, "formal_decision_written": False, "safe_for_model_claim": False}
        result = module.validate_row(row)
        self.assertEqual([], result)

    def test_rejects_duplicate_or_empty_measurements_and_open_flags(self):
        row = {"review_task_id": "lit-1", "measurement_ids": "m1|m1", "human_review_status": "approved", "training_eligible": True, "formal_decision_written": True, "safe_for_model_claim": True}
        errors = module.validate_row(row)
        self.assertIn("duplicate_measurement_id", errors)
        self.assertIn("review_status_not_pending", errors)
        self.assertIn("training_or_claim_flag_open", errors)

    def test_report_detects_duplicate_task_ids(self):
        rows = [{"review_task_id": "lit-1", "measurement_ids": "m1", "human_review_status": "pending_human_review", "training_eligible": False, "formal_decision_written": False, "safe_for_model_claim": False}, {"review_task_id": "lit-1", "measurement_ids": "m2", "human_review_status": "pending_human_review", "training_eligible": False, "formal_decision_written": False, "safe_for_model_claim": False}]
        report = module.build_report(rows)
        self.assertIn("duplicate_review_task_id", report["global_errors"])

