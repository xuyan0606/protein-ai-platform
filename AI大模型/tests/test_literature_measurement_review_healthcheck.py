import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_literature_measurement_review_healthcheck.py"
SPEC = importlib.util.spec_from_file_location("lit_healthcheck", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class LiteratureReviewHealthcheckTests(unittest.TestCase):
    def test_consistent_artifacts_pass(self):
        result = module.build_report(
            {"queue_rows": 2, "valid_rows": 2},
            {"queue_rows": 2, "decision_rows": 2, "pending_rows": 2, "approved_rows": 0},
            {"success": True, "queue_rows": 2, "assigned_task_rows": 2},
            {"batch_rows": 1, "task_rows": 2, "pending_rows": 2, "approved_rows": 0},
            {"success": True, "batch_rows": 1, "status_rows": 1},
            {"approved_preview_rows": 0},
        )
        self.assertTrue(result["success"])

    def test_mismatched_approval_counts_fail(self):
        result = module.build_report(
            {"queue_rows": 1, "valid_rows": 1}, {"queue_rows": 1, "decision_rows": 1, "pending_rows": 0, "approved_rows": 1},
            {"success": True, "queue_rows": 1, "assigned_task_rows": 1}, {"batch_rows": 1, "task_rows": 1, "pending_rows": 0, "approved_rows": 0},
            {"success": True, "batch_rows": 1, "status_rows": 1}, {"approved_preview_rows": 1},
        )
        self.assertFalse(result["success"])
        self.assertIn("approved_count_mismatch", result["failures"])
