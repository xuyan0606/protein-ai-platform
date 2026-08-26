import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_pretraining_quality_report import main


class PretrainingQualityReportTest(unittest.TestCase):
    def test_report_aggregates_completed_rows_and_keeps_fail_closed_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "summary.json").write_text(json.dumps({"rows": [
                {"batch": "0001", "status": "completed_pretraining_only", "sequence_count": 2, "steps": 3, "final_loss": 2.0, "validation_loss": 2.5},
                {"batch": "0002", "status": "blocked", "sequence_count": 4, "steps": 1, "final_loss": 9, "validation_loss": 9},
            ]}))
            (root / "validation.json").write_text(json.dumps({"success": True, "record_count": 2, "duplicate_embedding_records": 0, "failures": []}))
            (root / "collisions.json").write_text(json.dumps({"collision_group_count": 0, "collision_record_count": 0}))
            out = root / "out.json"
            import sys
            old = sys.argv
            sys.argv = ["report", "--summary", str(root / "summary.json"), "--index-validation", str(root / "validation.json"), "--collision-report", str(root / "collisions.json"), "--output", str(out)]
            try:
                self.assertEqual(main(), 0)
            finally:
                sys.argv = old
            report = json.loads(out.read_text())
            self.assertEqual(report["batch_count"], 1)
            self.assertEqual(report["total_sequence_count"], 2)
            self.assertFalse(report["safe_for_model_claim"])


if __name__ == "__main__":
    unittest.main()
