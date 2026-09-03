import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE.parents[1]
MODULE_PATH = HERE / "build_measurement_batch004.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_measurement_batch004", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildMeasurementBatch004Test(unittest.TestCase):
    def test_builds_expected_fail_closed_rows(self):
        rows = load_builder().build_rows(DATA_ROOT)

        self.assertEqual(197, len(rows))
        self.assertEqual(197, len({row["measurement_id"] for row in rows}))
        self.assertEqual(
            {"PMC10883975": 85, "PMC5431495": 92, "PMC3374809": 20},
            {
                pmcid: sum(row["pmcid"] == pmcid for row in rows)
                for pmcid in {row["pmcid"] for row in rows}
            },
        )
        self.assertTrue(
            all(
                row[field] == "false"
                for row in rows
                for field in ("training_eligible", "formal_decision_written", "safe_for_model_claim")
            )
        )

    def test_preserves_constructs_missing_controls_and_condition_conflicts(self):
        rows = load_builder().build_rows(DATA_ROOT)

        bla_double = next(
            row for row in rows if row["variant"] == "E271L/K319W" and row["metric"] == "kcat"
        )
        self.assertEqual("E271L/K319W", bla_double["mutation_composition"])
        self.assertIn("table/method condition conflict", bla_double["assay_note"])
        self.assertIn("results pH 6.5 and 95 C", bla_double["assay_note"])

        xylanase_80c = next(
            row for row in rows if row["variant"] == "T53C-T142C" and row["metric"] == "half_life" and row["assay_temperature_c"] == "80"
        )
        self.assertEqual("T53C/T142C", xylanase_80c["mutation_composition"])
        self.assertEqual("", xylanase_80c["wt_value"])
        self.assertIn("WT reported ND", xylanase_80c["assay_note"])

        gox_double = next(
            row for row in rows if row["variant"] == "T132S/T56V" and row["metric"] == "Km"
        )
        self.assertEqual("T132S/T56V", gox_double["mutation_composition"])
        self.assertEqual("T132S", gox_double["parent_variant"])
        self.assertEqual("", gox_double["wt_value"])
        self.assertIn("parent kinetic value absent", gox_double["assay_note"])

    def test_rejects_source_table_header_drift(self):
        builder = load_builder()
        root = builder.ET.fromstring(
            "<article><table-wrap id='T'><table><thead><tr><th>B</th><th>A</th></tr></thead>"
            "<tbody><tr><td>2</td><td>1</td></tr></tbody></table></table-wrap></article>"
        )
        with self.assertRaisesRegex(ValueError, "unexpected headers"):
            builder.require_headers(root, "T", [["A", "B"]])

    def test_writes_28_column_csv(self):
        builder = load_builder()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "batch004.csv"
            builder.write_csv(builder.build_rows(DATA_ROOT), output)
            with output.open(newline="", encoding="utf-8") as handle:
                parsed = list(csv.DictReader(handle))

        self.assertEqual(197, len(parsed))
        self.assertTrue(all(None not in row and len(row) == 28 for row in parsed))


if __name__ == "__main__":
    unittest.main()
