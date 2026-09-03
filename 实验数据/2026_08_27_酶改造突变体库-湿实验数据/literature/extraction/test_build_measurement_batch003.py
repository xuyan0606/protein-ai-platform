import csv
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE.parents[1]
MODULE_PATH = HERE / "build_measurement_batch003.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_measurement_batch003", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildMeasurementBatch003Test(unittest.TestCase):
    def test_rejects_ambiguous_or_malformed_numeric_values(self):
        builder = load_builder()

        with self.assertRaisesRegex(ValueError, "unsupported comma"):
            builder.split_value("1,033")
        self.assertEqual(("1033.78", "38.91"), builder.split_value("1033,78 ± 38.91", allow_decimal_comma=True))
        for raw in ("1 ± 2 ± 3", "not reported", ""):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                builder.split_value(raw)

    def test_unique_index_rejects_duplicate_or_wrong_width_rows(self):
        builder = load_builder()

        with self.assertRaisesRegex(ValueError, "duplicate key"):
            builder.unique_index([["A", "1"], ["A", "2"]], 2, "test table")
        with self.assertRaisesRegex(ValueError, "expected 2 cells"):
            builder.unique_index([["A"]], 2, "test table")

    def test_rejects_changed_table_headers(self):
        builder = load_builder()
        root = builder.ET.fromstring(
            "<article><table-wrap id='T'><table><thead><tr><th>Metric B</th><th>Metric A</th></tr></thead>"
            "<tbody><tr><td>2</td><td>1</td></tr></tbody></table></table-wrap></article>"
        )
        with self.assertRaisesRegex(ValueError, "unexpected headers"):
            builder.require_headers(root, "T", [["Metric A", "Metric B"]])

    def test_builds_expected_fail_closed_rows(self):
        builder = load_builder()
        rows = builder.build_rows(DATA_ROOT)

        self.assertEqual(132, len(rows))
        self.assertEqual(132, len({row["measurement_id"] for row in rows}))
        self.assertEqual(
            {"PMC5478988": 88, "PMC11180912": 16, "PMC7287683": 28},
            {
                pmcid: sum(row["pmcid"] == pmcid for row in rows)
                for pmcid in {row["pmcid"] for row in rows}
            },
        )
        self.assertFalse(any(row["variant"] == "EcAmy" for row in rows))
        self.assertTrue(
            all(
                row[field] == "false"
                for row in rows
                for field in (
                    "training_eligible",
                    "formal_decision_written",
                    "safe_for_model_claim",
                )
            )
        )

    def test_preserves_constructs_and_normalizes_source_number(self):
        builder = load_builder()
        rows = builder.build_rows(DATA_ROOT)

        e166p = next(
            row
            for row in rows
            if row["variant"] == "E166P"
            and row["metric"] == "kcat"
            and row["assay_temperature_c"] == "35"
        )
        self.assertEqual("1033.78", e166p["mutant_value"])

        md2 = next(row for row in rows if row["variant"] == "TmPhyMD2")
        self.assertIn("NtermDeletionLength=10", md2["mutation_composition"])
        self.assertIn("deleted_sequence=unverified", md2["mutation_composition"])
        md3 = next(row for row in rows if row["variant"] == "TmPhyMD3")
        self.assertIn("NtermReplacement=LNSSVPGA", md3["mutation_composition"])
        self.assertIn("replaced_span=unresolved", md3["mutation_composition"])

        tmphy_parents = {
            variant: next(row for row in rows if row["variant"] == variant)["parent_variant"]
            for variant in ("TmPhyM", "TmPhyMD1", "TmPhyMD2", "TmPhyMD3")
        }
        self.assertEqual(
            {
                "TmPhyM": "TmPhy",
                "TmPhyMD1": "TmPhyM",
                "TmPhyMD2": "TmPhyMD1",
                "TmPhyMD3": "TmPhyMD1",
            },
            tmphy_parents,
        )

        a2 = next(row for row in rows if row["variant"] == "A2")
        self.assertEqual("GOx-Parent", a2["parent_variant"])
        self.assertEqual("T30V/I94V/A162T/R537K/M556V", a2["mutation_composition"])
        self.assertEqual("", a2["assay_ph"])
        self.assertIn("pH 5.5 and 7.4 unresolved", a2["assay_note"])
        self.assertIn("triplicate ABTS", a2["assay_note"])

    def test_writes_28_column_csv(self):
        builder = load_builder()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "batch003.csv"
            builder.write_csv(builder.build_rows(DATA_ROOT), output)
            content = output.read_text(encoding="utf-8")
            parsed = list(csv.DictReader(io.StringIO(content)))

        self.assertEqual(132, len(parsed))
        self.assertTrue(all(None not in row for row in parsed))
        self.assertTrue(all(len(row) == 28 for row in parsed))


if __name__ == "__main__":
    unittest.main()
