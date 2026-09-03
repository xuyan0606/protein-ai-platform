import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE.parents[1]


def load_builder():
    spec = importlib.util.spec_from_file_location("batch020", HERE / "build_measurement_batch020.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Batch020Test(unittest.TestCase):
    def test_extracts_baqa_table_one(self):
        rows = load_builder().build_rows(DATA_ROOT)
        self.assertEqual(3, len(rows))
        self.assertEqual(3, len({row["measurement_id"] for row in rows}))
        self.assertEqual({"BaqA∆C N185D"}, {row["variant"] for row in rows})
        self.assertEqual({"Km", "kcat", "kcat_per_Km"}, {row["metric"] for row in rows})
        self.assertEqual({"mg/mL", "s−1", "mL mg−1 s−1"}, {row["unit"] for row in rows})

    def test_preserves_evidence_only_and_assay_context(self):
        rows = load_builder().build_rows(DATA_ROOT)
        self.assertTrue(all(row["training_eligible"] == "false" for row in rows))
        self.assertTrue(all(row["formal_decision_written"] == "false" for row in rows))
        self.assertTrue(all(row["safe_for_model_claim"] == "false" for row in rows))
        self.assertTrue(all(row["assay_ph"] == "6.5" for row in rows))
        self.assertTrue(all(row["assay_temperature_c"] == "50" for row in rows))
        self.assertTrue(all(row["assay_substrate"] == "soluble starch" for row in rows))


if __name__ == "__main__":
    unittest.main()
