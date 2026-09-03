import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_literature_measurement_review_batches.py"
SPEC = importlib.util.spec_from_file_location("lit_batch_validator", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class LiteratureBatchValidationTests(unittest.TestCase):
    def setUp(self):
        self.queue = [
            {"review_task_id": "a", "review_priority": "P0", "review_lane": "numbering"},
            {"review_task_id": "b", "review_priority": "P1", "review_lane": "construct"},
        ]

    def test_valid_batches_cover_queue_once(self):
        batches = [
            {"batch_id": "b1", "review_priority": "P0", "review_lane": "numbering", "task_count": 1, "tasks": ["a"]},
            {"batch_id": "b2", "review_priority": "P1", "review_lane": "construct", "task_count": 1, "tasks": ["b"]},
        ]
        self.assertTrue(module.build_report(self.queue, batches, batch_size=10)["success"])

    def test_duplicate_or_wrong_lane_task_fails(self):
        batches = [{"batch_id": "b1", "review_priority": "P0", "review_lane": "construct", "task_count": 2, "tasks": ["a", "a"]}]
        report = module.build_report(self.queue, batches, batch_size=10)
        self.assertFalse(report["success"])
        self.assertIn("duplicate_task_assignment", report["failures"])
        self.assertIn("task_priority_or_lane_mismatch", report["failures"])
