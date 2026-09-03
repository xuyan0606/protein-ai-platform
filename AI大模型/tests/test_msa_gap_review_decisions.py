import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_msa_gap_review_decisions.py"
SPEC = importlib.util.spec_from_file_location("msa_gap_decisions", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class MsaGapReviewDecisionTests(unittest.TestCase):
    def setUp(self):
        self.queue = {"review_id": "msa-gap-review::P12345", "uniprot_id": "P12345"}

    def test_approved_decision_requires_reviewer_and_time(self):
        errors = module.validate_decision(
            {"review_id": self.queue["review_id"], "uniprot_id": "P12345", "decision": "approved"},
            self.queue,
        )
        self.assertIn("reviewer_missing", errors)
        self.assertIn("reviewed_at_missing", errors)

    def test_rejected_decision_is_valid_but_not_approved(self):
        decision = {"review_id": self.queue["review_id"], "uniprot_id": "P12345", "decision": "rejected", "reviewer": "curator", "reviewed_at": "2026-09-01T00:00:00+00:00"}
        self.assertEqual([], module.validate_decision(decision, self.queue))

    def test_reviewed_at_must_be_rfc3339(self):
        decision = {"review_id": self.queue["review_id"], "uniprot_id": "P12345", "decision": "rejected", "reviewer": "curator", "reviewed_at": "yesterday"}
        self.assertIn("reviewed_at_invalid_format", module.validate_decision(decision, self.queue))

    def test_duplicate_and_missing_queue_rows_are_reported(self):
        queue = [self.queue, {"review_id": "msa-gap-review::P67890", "uniprot_id": "P67890"}]
        decisions = [
            {"review_id": self.queue["review_id"], "uniprot_id": "P12345", "decision": "rejected", "reviewer": "a", "reviewed_at": "2026-09-01T00:00:00+00:00"},
            {"review_id": self.queue["review_id"], "uniprot_id": "P12345", "decision": "rejected", "reviewer": "b", "reviewed_at": "2026-09-01T00:00:00+00:00"},
        ]
        report = module.build_validation_report(queue, decisions)
        self.assertIn("duplicate_review_id", report["global_errors"])
        self.assertIn("missing_decision_for_queue_row", report["global_errors"])

    def test_preview_contains_only_valid_approved_rows(self):
        decisions = [{"review_id": self.queue["review_id"], "uniprot_id": "P12345", "decision": "approved", "reviewer": "a", "reviewed_at": "2026-09-01T00:00:00+00:00"}]
        preview = module.build_approved_preview([self.queue], decisions)
        self.assertEqual(1, len(preview["rows"]))
        self.assertFalse(preview["formal_intake_authorized"])
