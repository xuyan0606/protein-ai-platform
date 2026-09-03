import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE.parents[1]


def load_builder():
    spec = importlib.util.spec_from_file_location("batch021", HERE / "build_measurement_batch021.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Batch021Test(unittest.TestCase):
    def test_extracts_mutant_stability_rows(self):
        rows = load_builder().build_rows(DATA_ROOT)
        self.assertEqual(14, len(rows))
        self.assertEqual(14, len({row["measurement_id"] for row in rows}))
        self.assertEqual({"D408W", "D408T", "D408K", "D408C", "E476T", "E476K", "S100A"}, {row["variant"] for row in rows})
        self.assertEqual({"half_life", "Tm"}, {row["metric"] for row in rows})

    def test_preserves_context_and_fail_closed_fields(self):
        rows = load_builder().build_rows(DATA_ROOT)
        self.assertTrue(all(row["assay_temperature_c"] == "55" for row in rows))
        self.assertTrue(all(row["assay_substrate"] == "thermal inactivation" for row in rows))
        self.assertTrue(all(row["training_eligible"] == "false" for row in rows))
        self.assertTrue(all(row["formal_decision_written"] == "false" for row in rows))
        self.assertTrue(all(row["safe_for_model_claim"] == "false" for row in rows))


if __name__ == "__main__":
    unittest.main()
