import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_literature_measurement_review_batch_status.py"
SPEC = importlib.util.spec_from_file_location("lit_status_validator", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class LiteratureStatusValidationTests(unittest.TestCase):
    def test_valid_status_passes(self):
        batches = [{"batch_id": "b1", "tasks": ["a", "b"]}]
        decisions = [{"review_task_id": "a", "decision": "approved_for_intake"}, {"review_task_id": "b", "decision": "pending"}]
        statuses = [{"batch_id": "b1", "task_rows": 2, "pending_rows": 1, "approved_rows": 1, "rejected_rows": 0, "unknown_decision_rows": 0}]
        self.assertTrue(module.validate_status(batches, decisions, statuses)["success"])

    def test_mismatch_fails_closed(self):
        batches = [{"batch_id": "b1", "tasks": ["a"]}]
        decisions = [{"review_task_id": "a", "decision": "pending"}]
        statuses = [{"batch_id": "b1", "task_rows": 1, "pending_rows": 0, "approved_rows": 1, "rejected_rows": 0, "unknown_decision_rows": 0}]
        result = module.validate_status(batches, decisions, statuses)
        self.assertFalse(result["success"])
        self.assertIn("status_count_mismatch", result["failures"])
