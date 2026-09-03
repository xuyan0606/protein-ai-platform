import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_ROOT = HERE.parents[1]

def load_builder():
    spec = importlib.util.spec_from_file_location('batch008', HERE / 'build_measurement_batch008.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

class Batch008Test(unittest.TestCase):
    def test_only_wet_table_and_governance(self):
        rows = load_builder().build_rows(DATA_ROOT)
        self.assertEqual(9, len(rows)); self.assertEqual(9, len({r['measurement_id'] for r in rows}))
        self.assertEqual({'XynLC9','N8Y','W6F/Q7H'}, {r['variant'] for r in rows})
        self.assertTrue(all(r['source_locator'] == 'Table 1' for r in rows))
        self.assertTrue(all(r[f] == 'false' for r in rows for f in ('training_eligible','formal_decision_written','safe_for_model_claim')))

    def test_constructs_and_values(self):
        rows = load_builder().build_rows(DATA_ROOT)
        combo = next(r for r in rows if r['variant'] == 'W6F/Q7H' and r['metric'] == 'kcat')
        self.assertEqual('W6F/Q7H', combo['mutation_composition'])
        self.assertEqual('133.1', combo['mutant_value']); self.assertEqual('11.7', combo['mutant_error'])
        self.assertEqual('55.9', next(r for r in rows if r['variant']=='XynLC9' and r['metric']=='kcat')['mutant_value'])

    def test_csv_shape(self):
        b = load_builder()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'batch008.csv'; b.write_csv(b.build_rows(DATA_ROOT), out)
            with out.open(encoding='utf-8') as f: rows = list(csv.DictReader(f))
        self.assertEqual(9, len(rows)); self.assertTrue(all(len(r) == 28 for r in rows))

if __name__ == '__main__': unittest.main()
