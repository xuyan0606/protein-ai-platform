import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE.parents[1]
MODULE_PATH = HERE / "build_measurement_batch005.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_measurement_batch005", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildMeasurementBatch005Test(unittest.TestCase):
    def test_builds_expected_fail_closed_rows(self):
        rows = load_builder().build_rows(DATA_ROOT)

        self.assertEqual(87, len(rows))
        self.assertEqual(87, len({row["measurement_id"] for row in rows}))
        self.assertEqual(
            {"PMC9105970": 16, "PMC8487158": 39, "PMC8313266": 32},
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

    def test_preserves_engineered_backgrounds_and_source_conflicts(self):
        rows = load_builder().build_rows(DATA_ROOT)

        mfaps = next(row for row in rows if row["variant"] == "A211C-S214C" and row["metric"] == "half_life")
        self.assertEqual("A211C/S214C", mfaps["mutation_composition"])
        self.assertEqual("60", mfaps["assay_temperature_c"])
        mfaps_tm = next(row for row in rows if row["variant"] == "A211C-S214C" and row["metric"] == "Tm")
        self.assertEqual("7.5", mfaps_tm["assay_ph"])

        xyl = next(
            row for row in rows
            if row["variant"] == "M53S/F54L/N207G"
            and row["metric"] == "specific_activity"
            and row["assay_substrate"] == "corncob xylan"
        )
        self.assertEqual("XYL10C_∆N", xyl["parent_variant"])
        self.assertIn("N-terminal-truncated engineered parent", xyl["assay_note"])

        man = next(row for row in rows if row["variant"] == "S268Q" and row["metric"] == "kcat_per_Km")
        self.assertEqual("255.7", man["mutant_value"])
        self.assertIn("S268Q/S286Q", man["assay_note"])
        self.assertIn("license_scope", man["human_review_status"])
        self.assertIn("CC BY-NC-ND 4.0", man["assay_note"])

    def test_rejects_table_header_drift(self):
        builder = load_builder()
        root = builder.ET.fromstring(
            "<article><table-wrap id='T'><table><thead><tr><th>B</th><th>A</th></tr></thead>"
            "<tbody><tr><td>2</td><td>1</td></tr></tbody></table></table-wrap></article>"
        )
        with self.assertRaisesRegex(ValueError, "unexpected headers"):
            builder.require_headers(root, "T", [["A", "B"]])

    def test_rejects_empty_key_row_that_contains_data(self):
        builder = load_builder()
        with self.assertRaisesRegex(ValueError, "empty key with non-empty data"):
            builder.unique_index([["", "75", "40.9"]], 3, "test table", skip_empty_key=True)
        self.assertEqual({}, builder.unique_index([["", "", ""]], 3, "test table", skip_empty_key=True))

    def test_writes_28_column_csv(self):
        builder = load_builder()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "batch005.csv"
            builder.write_csv(builder.build_rows(DATA_ROOT), output)
            with output.open(newline="", encoding="utf-8") as handle:
                parsed = list(csv.DictReader(handle))

        self.assertEqual(87, len(parsed))
        self.assertTrue(all(None not in row and len(row) == 28 for row in parsed))


if __name__ == "__main__":
    unittest.main()
