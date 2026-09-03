import unittest
from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "ui" / "numbering_review" / "app.js"


class NumberingReviewValidationPolicyTests(unittest.TestCase):
    def test_map_draft_is_not_blocked_by_incomplete_optional_checklist(self):
        source = APP.read_text(encoding="utf-8")

        self.assertNotIn('if (checked < CHECKS.length) errors.push("map 需要全部人工核实项打勾")', source)
        self.assertIn('if (row.title_flag === "title_mismatch_risk"', source)
        self.assertIn('if (row.audit_recommended_decision === "reject_label"', source)


if __name__ == "__main__":
    unittest.main()
