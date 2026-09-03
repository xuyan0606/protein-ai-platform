import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_msa_gap_cache.py"
SPEC = importlib.util.spec_from_file_location("msa_gap_validation", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class MsaGapCacheValidationTests(unittest.TestCase):
    def test_valid_artifacts_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            msa = root / "P12345.aln.fasta"
            conservation = root / "P12345.conservation.json"
            msa.write_text(">P12345|query\nACD\n>hit\nACD\n", encoding="utf-8")
            conservation.write_text('{"uniprot_id":"P12345","sequence_length":3,"position_conservation":[1, 0.5, 0]}', encoding="utf-8")
            row = {"uniprot_id": "P12345", "sequence_length": 3, "msa_path": str(msa), "conservation_feature_path": str(conservation)}
            self.assertEqual([], module.validate_row(row))

    def test_query_length_and_conservation_bounds_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            msa = root / "P12345.aln.fasta"
            conservation = root / "P12345.conservation.json"
            msa.write_text(">P12345|query\nAC\n", encoding="utf-8")
            conservation.write_text('{"uniprot_id":"P12345","sequence_length":3,"position_conservation":[1, 1.2, 0]}', encoding="utf-8")
            row = {"uniprot_id": "P12345", "sequence_length": 3, "msa_path": str(msa), "conservation_feature_path": str(conservation)}
            errors = module.validate_row(row)
            self.assertIn("msa_query_length_mismatch", errors)
            self.assertIn("conservation_value_invalid", errors)

