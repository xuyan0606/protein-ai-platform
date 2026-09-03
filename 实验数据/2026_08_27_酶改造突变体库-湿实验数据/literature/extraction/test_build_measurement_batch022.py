import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE.parents[1]


def load_builder():
    spec = importlib.util.spec_from_file_location("batch022", HERE / "build_measurement_batch022.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Batch022Test(unittest.TestCase):
    def test_extracts_two_tables(self):
        rows = load_builder().build_rows(DATA_ROOT)
        self.assertEqual(18, len(rows))
        self.assertEqual(18, len({row["measurement_id"] for row in rows}))
        self.assertEqual({"half_life", "Tm", "kcat", "Km", "kcat_per_Km"}, {row["metric"] for row in rows})

    def test_keeps_engineered_background_and_fail_closed(self):
        rows = load_builder().build_rows(DATA_ROOT)
        self.assertTrue(all(row["training_eligible"] == "false" for row in rows))
        self.assertTrue(all(row["formal_decision_written"] == "false" for row in rows))
        self.assertTrue(all(row["safe_for_model_claim"] == "false" for row in rows))
        self.assertIn("T2C/T29C", {row["mutation_composition"] for row in rows})


if __name__ == "__main__":
    unittest.main()
