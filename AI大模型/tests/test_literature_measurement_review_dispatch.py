import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_literature_measurement_review_dispatch.py"
SPEC = importlib.util.spec_from_file_location("lit_dispatch", SCRIPT)
module = importlib.util.module_from_spec(SPEC)


class LiteratureReviewDispatchTests(unittest.TestCase):
    def test_build_dispatch_packets_is_complete_and_non_authorizing(self):
        SPEC.loader.exec_module(module)
        batches = [{"batch_id": "b1", "tasks": ["t1", "t2"], "review_priority": "P0", "review_lane": "lane"}]
        queue = [{"review_task_id": "t1", "source_path": "x.xml", "source_sha256": "a" * 64}, {"review_task_id": "t2", "source_path": "y.xml", "source_sha256": "b" * 64}]
        result = module.build_dispatch(batches, queue)
        self.assertEqual(1, len(result["packets"]))
        self.assertEqual(["t1", "t2"], result["packets"][0]["task_ids"])
        self.assertFalse(result["packets"][0]["formal_intake_authorized"])

    def test_dispatch_rejects_unknown_task(self):
        SPEC.loader.exec_module(module)
        with self.assertRaises(ValueError):
            module.build_dispatch([{"batch_id": "b1", "tasks": ["missing"]}], [])


if __name__ == "__main__":
    unittest.main()
