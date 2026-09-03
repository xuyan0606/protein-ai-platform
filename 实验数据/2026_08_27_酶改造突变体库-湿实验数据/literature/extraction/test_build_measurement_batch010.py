import csv,importlib.util,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent; DATA_ROOT=HERE.parents[1]
def load_builder():
 s=importlib.util.spec_from_file_location('batch010',HERE/'build_measurement_batch010.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
class Batch010Test(unittest.TestCase):
 def test_rows(self):
  rs=load_builder().build_rows(DATA_ROOT); self.assertEqual(8,len(rs)); self.assertEqual(8,len({r['measurement_id'] for r in rs})); self.assertEqual({'AnP-M1','AnP-M2'},{r['variant'] for r in rs}); self.assertTrue(all(r[f]=='false' for r in rs for f in ('training_eligible','formal_decision_written','safe_for_model_claim')))
 def test_background(self):
  rs=load_builder().build_rows(DATA_ROOT); self.assertEqual('18 substitutions from AfP analogs',next(r for r in rs if r['variant']=='AnP-M1')['mutation_composition']); self.assertEqual('9 substitutions selected from M1',next(r for r in rs if r['variant']=='AnP-M2')['mutation_composition']); self.assertEqual('289.8',next(r for r in rs if r['variant']=='AnP-M1' and r['metric']=='Km')['wt_value'])
 def test_csv(self):
  b=load_builder()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.csv'; b.write_csv(b.build_rows(DATA_ROOT),p)
   with p.open(encoding='utf-8') as f: rs=list(csv.DictReader(f))
  self.assertTrue(all(len(r)==28 for r in rs))
if __name__=='__main__': unittest.main()
