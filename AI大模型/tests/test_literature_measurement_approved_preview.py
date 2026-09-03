import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_literature_measurement_approved_preview.py"
SPEC = importlib.util.spec_from_file_location("lit_preview", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class LiteratureApprovedPreviewTests(unittest.TestCase):
    def test_keeps_only_valid_approved_tasks(self):
        queue = [{"review_task_id": "a", "measurement_ids": "m1", "pmcid": "PMC1"}]
        decisions = [
            {"review_task_id": "a", "measurement_ids": "m1", "decision": "approved_for_intake", "reviewer": "curator", "reviewed_at": "2026-09-01T00:00:00+00:00", "review_basis": "verified", "authorization_receipt": "receipt-1"},
            {"review_task_id": "missing", "measurement_ids": "m2", "decision": "approved_for_intake", "reviewer": "curator", "reviewed_at": "2026-09-01T00:00:00+00:00", "review_basis": "x", "authorization_receipt": "receipt-2"},
        ]
        result = module.build_preview(queue, decisions)
        self.assertEqual(["a"], [x["review_task_id"] for x in result["rows"]])
        self.assertFalse(result["formal_intake_authorized"])
