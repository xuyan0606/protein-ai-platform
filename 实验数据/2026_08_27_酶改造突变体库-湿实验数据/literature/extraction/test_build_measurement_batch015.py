import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;DATA_ROOT=HERE.parents[1]
def load_builder():
 s=importlib.util.spec_from_file_location('b',HERE/'build_measurement_batch015.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
 def test_rows(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertEqual(22,len(r));self.assertEqual(22,len({x['measurement_id'] for x in r}));self.assertTrue(all(x['training_eligible']=='false' for x in r))
 def test_composition_and_missing(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertEqual('C75W/A84T/N176D',next(x for x in r if x['variant']=='F9')['mutation_composition']);self.assertFalse(any(x['variant'] in {'F9','G10'} and x['source_locator']=='Table 3' for x in r))
if __name__=='__main__':unittest.main()
