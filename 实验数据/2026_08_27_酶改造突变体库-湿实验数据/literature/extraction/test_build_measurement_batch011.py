import csv,importlib.util,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent; DATA_ROOT=HERE.parents[1]
def load_builder():
 s=importlib.util.spec_from_file_location('batch011',HERE/'build_measurement_batch011.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
class Batch011Test(unittest.TestCase):
 def test_rows(self):
  rs=load_builder().build_rows(DATA_ROOT); self.assertEqual(12,len(rs)); self.assertEqual(12,len({r['measurement_id'] for r in rs})); self.assertEqual({'DS153','DS241','DS428'},{r['variant'] for r in rs}); self.assertTrue(all(r[f]=='false' for r in rs for f in ('training_eligible','formal_decision_written','safe_for_model_claim')))
 def test_composition(self):
  rs=load_builder().build_rows(DATA_ROOT); self.assertEqual('N29S',next(r for r in rs if r['variant']=='DS153')['mutation_composition']); self.assertEqual('69.44',next(r for r in rs if r['variant']=='DS153' and r['metric']=='Vmax')['mutant_value']); self.assertEqual('45.66',next(r for r in rs if r['variant']=='DS153' and r['metric']=='Vmax')['wt_value'])
 def test_csv(self):
  b=load_builder()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.csv'; b.write_csv(b.build_rows(DATA_ROOT),p)
   with p.open(encoding='utf-8') as f: rs=list(csv.DictReader(f))
  self.assertTrue(all(len(r)==28 for r in rs))
if __name__=='__main__': unittest.main()
