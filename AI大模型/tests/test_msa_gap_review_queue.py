import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_msa_gap_review_queue.py"
SPEC = importlib.util.spec_from_file_location("msa_gap_review_queue", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class MsaGapReviewQueueTests(unittest.TestCase):
    def test_build_review_row_is_pending_and_fail_closed(self):
        row = module.build_review_row(
            {"uniprot_id": "P12345", "sequence_length": 10, "msa_path": "msa.fa", "conservation_feature_path": "cons.json", "msa_sha256": "a" * 64, "conservation_sha256": "b" * 64},
            {"hit_count": 4, "raw_hit_count": 7, "summary": {"positions_with_homolog_coverage": 9, "mean_homolog_depth": 3.2}},
        )
        self.assertEqual("pending_human_review", row["review_status"])
        self.assertEqual(0.9, row["coverage_fraction"])
        self.assertFalse(row["training_import_allowed"])
        self.assertFalse(row["release_ready"])

