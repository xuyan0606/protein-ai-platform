import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_literature_measurement_review_batches.py"
SPEC = importlib.util.spec_from_file_location("lit_batches", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class LiteratureBatchTests(unittest.TestCase):
    def test_batches_are_deterministic_and_bounded(self):
        rows = [{"review_task_id": f"t{i}", "review_priority": "P1", "review_lane": "construct_background", "measurement_count": "2"} for i in range(5)]
        batches = module.build_batches(rows, batch_size=2)
        self.assertEqual([2, 2, 1], [len(x["tasks"]) for x in batches])
        self.assertEqual("literature-review-P1-construct_background-001", batches[0]["batch_id"])
    def test_priority_and_lane_are_grouped(self):
        rows = [{"review_task_id": "b", "review_priority": "P1", "review_lane": "construct_background"}, {"review_task_id": "a", "review_priority": "P0", "review_lane": "numbering_conflict"}]
        batches = module.build_batches(rows, batch_size=10)
        self.assertEqual(["P0", "P1"], [x["review_priority"] for x in batches])
