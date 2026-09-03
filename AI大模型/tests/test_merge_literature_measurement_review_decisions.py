import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "merge_literature_measurement_review_decisions.py"
SPEC = importlib.util.spec_from_file_location("lit_merge", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class LiteratureDecisionMergeTests(unittest.TestCase):
    def test_merges_different_tasks_without_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "decisions.jsonl"
            a = {"review_task_id": "a", "decision": "rejected"}
            b = {"review_task_id": "b", "decision": "approved_for_intake"}
            barrier = threading.Barrier(2)
            def submit(row):
                barrier.wait()
                module.merge_rows(target, [row])
            threads = [threading.Thread(target=submit, args=(row,)) for row in (a, b)]
            [t.start() for t in threads]; [t.join() for t in threads]
            self.assertEqual({"a", "b"}, {json_row["review_task_id"] for json_row in module.load_jsonl(target)})

    def test_conflicting_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "decisions.jsonl"
            module.merge_rows(target, [{"review_task_id": "a", "decision": "rejected"}])
            with self.assertRaisesRegex(ValueError, "decision_conflict"):
                module.merge_rows(target, [{"review_task_id": "a", "decision": "approved_for_intake"}])

    def test_completed_decision_replaces_pending_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "decisions.jsonl"
            module.merge_rows(target, [{"review_task_id": "a", "decision": "pending"}])
            rows = module.merge_rows(target, [{"review_task_id": "a", "decision": "rejected", "reviewer": "reviewer"}])
            self.assertEqual("rejected", rows[0]["decision"])

    def test_validated_merge_rejects_incomplete_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "decisions.jsonl"
            queue = [{"review_task_id": "a", "measurement_ids": "m1"}]
            with self.assertRaisesRegex(ValueError, "invalid_decision"):
                module.merge_validated_rows(target, [{"review_task_id": "a", "decision": "approved_for_intake"}], queue)

    def test_validated_merge_normalizes_frontend_measurement_id_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "decisions.jsonl"
            queue = [{"review_task_id": "a", "measurement_ids": "m1"}]
            row = {"review_task_id": "a", "measurement_ids": ["m1"], "decision": "rejected", "reviewer": "r", "reviewed_at": "2026-09-02T00:00:00+00:00", "review_basis": "x", "authorization_receipt": "not_applicable"}
            merged = module.merge_validated_rows(target, [row], queue)
            self.assertEqual("m1", merged[0]["measurement_ids"])

    def test_validated_merge_normalizes_complete_frontend_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "decisions.jsonl"
            queue = [{"review_task_id": "a", "measurement_ids": "m1"}]
            draft = {"review_task_id": "a", "measurement_ids": ["m1"], "decision": "evidence_verified", "reviewer": "r", "reviewed_at": "2026-09-02T00:00:00+00:00", "notes": "source and construct verified", "authorization_receipt": "receipt-1"}
            merged = module.merge_validated_rows(target, [draft], queue)
            self.assertEqual("approved_for_intake", merged[0]["decision"])
            self.assertEqual("source and construct verified", merged[0]["review_basis"])

    def test_validated_merge_rejects_keep_pending_frontend_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "decisions.jsonl"
            queue = [{"review_task_id": "a", "measurement_ids": "m1"}]
            with self.assertRaisesRegex(ValueError, "invalid_decision"):
                module.merge_validated_rows(target, [{"review_task_id": "a", "measurement_ids": ["m1"], "decision": "keep_pending"}], queue)


if __name__ == "__main__":
    unittest.main()
