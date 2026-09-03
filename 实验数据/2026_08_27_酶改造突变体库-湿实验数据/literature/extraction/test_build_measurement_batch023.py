import importlib.util, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent; DATA_ROOT=HERE.parents[1]
def load_builder():
 s=importlib.util.spec_from_file_location('b',HERE/'build_measurement_batch023.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
 def test_rows(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertEqual(42,len(r));self.assertEqual(42,len({x['measurement_id'] for x in r}));self.assertEqual(6,len({x['variant'] for x in r}));self.assertEqual(7,len({x['metric'] for x in r}))
 def test_governance(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertTrue(all(x['training_eligible']=='false' and x['formal_decision_written']=='false' and x['safe_for_model_claim']=='false' for x in r));self.assertTrue(all(x['assay_substrate']=='locust bean gum' for x in r))
if __name__=='__main__':unittest.main()
