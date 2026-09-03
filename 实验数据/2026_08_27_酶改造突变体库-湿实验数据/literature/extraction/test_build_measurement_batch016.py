import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;DATA_ROOT=HERE.parents[1]
def load_builder():
 s=importlib.util.spec_from_file_location('b',HERE/'build_measurement_batch016.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
 def test_rows(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertEqual(3,len(r));self.assertTrue(all(x['variant']=='MutMCAP-8' and x['mutation_composition']=='N331Q' for x in r));self.assertFalse(any('SyMCAP' in x['variant'] for x in r));self.assertTrue(all(x['training_eligible']=='false' for x in r))
if __name__=='__main__':unittest.main()
