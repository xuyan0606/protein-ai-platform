import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_literature_measurement_review_batch_status.py"
SPEC = importlib.util.spec_from_file_location("lit_batch_status", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class LiteratureBatchStatusTests(unittest.TestCase):
    def test_aggregates_decisions_per_batch(self):
        batches = [{"batch_id": "b1", "tasks": ["a", "b"]}]
        decisions = [{"review_task_id": "a", "decision": "approved_for_intake"}, {"review_task_id": "b", "decision": "pending"}]
        rows = module.build_status(batches, decisions)
        self.assertEqual(1, rows[0]["approved_rows"])
        self.assertEqual(1, rows[0]["pending_rows"])
        self.assertFalse(rows[0]["formal_intake_authorized"])
