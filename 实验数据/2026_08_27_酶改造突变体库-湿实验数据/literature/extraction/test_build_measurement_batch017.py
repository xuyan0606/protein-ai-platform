import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;DATA_ROOT=HERE.parents[1]
def load_builder():
 s=importlib.util.spec_from_file_location('b',HERE/'build_measurement_batch017.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
 def test_rows(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertEqual(18,len(r));self.assertEqual({'TlGA-M4','TlGA-M6','TlGA-M7'},{x['variant'] for x in r});self.assertTrue(all(x['training_eligible']=='false' for x in r))
 def test_compositions(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertEqual(8,len(next(x for x in r if x['variant']=='TlGA-M4')['mutation_composition'].split('/')));self.assertFalse(any(x['variant'] in {'TlGA-M1','TlGA-M2','TlGA-M3','TlGA-M5'} for x in r))
if __name__=='__main__':unittest.main()
