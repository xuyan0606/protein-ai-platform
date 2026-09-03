import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE.parents[1]


def load_builder():
    spec = importlib.util.spec_from_file_location("batch007", HERE / "build_measurement_batch007.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Batch007Test(unittest.TestCase):
    def test_rows_and_governance(self):
        rows = load_builder().build_rows(DATA_ROOT)
        self.assertEqual(16, len(rows))
        self.assertEqual(16, len({r["measurement_id"] for r in rows}))
        self.assertTrue(all(r["variant"] == "EH-CC-E204G" for r in rows))
        self.assertTrue(all(r[f] == "false" for r in rows for f in (
            "training_eligible", "formal_decision_written", "safe_for_model_claim")))

    def test_engineered_background_and_table1(self):
        rows = load_builder().build_rows(DATA_ROOT)
        tm = [r for r in rows if r["source_locator"] == "Table 1"]
        self.assertEqual(4, len(tm))
        self.assertTrue(all(r["parent_variant"] == "EH-CC" for r in tm))
        self.assertTrue(all(r["mutation_composition"] == "engineered_EH-CC_background/E204G" for r in tm))
        self.assertEqual({"60.5", "61.1", "61.3", "61.5"}, {r["wt_value"] for r in tm})
        self.assertEqual({"62.7", "63.1", "63.3", "63.4"}, {r["mutant_value"] for r in tm})

    def test_table2_rowspan_and_blank_comparator(self):
        rows = load_builder().build_rows(DATA_ROOT)
        kd4 = next(r for r in rows if r["metric"] == "binding_Kd" and r["assay_note"].endswith("Site 4"))
        self.assertEqual("Zn2+", kd4["assay_substrate"])
        self.assertEqual("", kd4["wt_value"])
        self.assertEqual("1422.5", kd4["mutant_value"])
        self.assertEqual("Site 4", kd4["assay_note"].split("; ")[-1])

    def test_csv_shape(self):
        b = load_builder()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "batch007.csv"
            b.write_csv(b.build_rows(DATA_ROOT), out)
            with out.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(16, len(rows))
        self.assertTrue(all(len(r) == 28 for r in rows))


if __name__ == "__main__":
    unittest.main()
