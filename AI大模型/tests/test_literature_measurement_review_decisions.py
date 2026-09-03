import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_literature_measurement_review_decisions.py"
SPEC = importlib.util.spec_from_file_location("lit_decisions", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class LiteratureDecisionTests(unittest.TestCase):
    def setUp(self): self.queue = {"review_task_id": "lit-1", "measurement_ids": "m1|m2"}
    def test_approved_requires_full_evidence(self):
        errors = module.validate_decision({"review_task_id": "lit-1", "measurement_ids": "m1|m2", "decision": "approved_for_intake"}, self.queue)
        self.assertIn("reviewer_missing", errors); self.assertIn("authorization_receipt_missing", errors)
    def test_rejected_with_evidence_is_valid(self):
        row = {"review_task_id": "lit-1", "measurement_ids": "m1|m2", "decision": "rejected", "reviewer": "curator", "reviewed_at": "2026-09-01T00:00:00+00:00", "review_basis": "construct mismatch", "authorization_receipt": "not_applicable"}
        self.assertEqual([], module.validate_decision(row, self.queue))
    def test_missing_and_duplicate_tasks_are_rejected(self):
        rows = [{"review_task_id": "lit-1", "measurement_ids": "m1|m2", "decision": "rejected", "reviewer": "a", "reviewed_at": "2026-09-01T00:00:00+00:00", "review_basis": "x", "authorization_receipt": "not_applicable"}, {"review_task_id": "lit-1", "measurement_ids": "m1|m2", "decision": "rejected", "reviewer": "a", "reviewed_at": "2026-09-01T00:00:00+00:00", "review_basis": "x", "authorization_receipt": "not_applicable"}]
        report = module.build_report([self.queue, {"review_task_id": "lit-2", "measurement_ids": "m3"}], rows)
        self.assertIn("duplicate_review_task_id", report["global_errors"]); self.assertIn("missing_decision_for_queue_row", report["global_errors"])

    def test_pending_rows_counts_explicit_pending_decisions(self):
        row = {"review_task_id": "lit-1", "measurement_ids": "m1|m2", "decision": "pending", "reviewer": "", "reviewed_at": "", "review_basis": "", "authorization_receipt": ""}
        report = module.build_report([self.queue], [row])
        self.assertEqual(1, report["pending_rows"])
