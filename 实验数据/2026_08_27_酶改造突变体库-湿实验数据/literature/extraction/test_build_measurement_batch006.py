import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE.parents[1]

def load_builder():
    spec = importlib.util.spec_from_file_location("batch006", HERE / "build_measurement_batch006.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

class Batch006Test(unittest.TestCase):
    def test_rows_and_governance(self):
        b = load_builder(); rows = b.build_rows(DATA_ROOT)
        self.assertEqual(98, len(rows)); self.assertEqual(98, len({r["measurement_id"] for r in rows}))
        self.assertEqual({"Q24A", "K104A", "K143A", "XynA-VT", "XynA-NT", "XynA-SN", "XynA-Spy"}, {r["variant"] for r in rows})
        self.assertTrue(all(r[f] == "false" for r in rows for f in ("training_eligible", "formal_decision_written", "safe_for_model_claim")))
        self.assertTrue(all(r["wt_value"] for r in rows))

    def test_constructs_and_nd(self):
        b = load_builder(); rows = b.build_rows(DATA_ROOT)
        spy = next(r for r in rows if r["variant"] == "XynA-Spy")
        self.assertIn("SpyTag", spy["mutation_composition"])
        nd = next(r for r in rows if r["variant"] == "XynA-SN" and r["metric"] == "half_life_60C")
        self.assertEqual("nd", nd["mutant_value"])

    def test_csv_shape(self):
        b = load_builder()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "x.csv"; b.write_csv(b.build_rows(DATA_ROOT), out)
            with out.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(98, len(rows)); self.assertTrue(all(len(r) == 28 for r in rows))

if __name__ == "__main__": unittest.main()
