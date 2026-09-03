import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent; DATA_ROOT=HERE.parents[1]
def load_builder():
 s=importlib.util.spec_from_file_location('b',HERE/'build_measurement_batch012.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
 def test_rows(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertEqual(8,len(r));self.assertEqual(8,len({x['measurement_id'] for x in r}));self.assertTrue(all(x['mutation_composition']=='Y233H/K264M/N343S' for x in r));self.assertTrue(all(x['training_eligible']=='false' for x in r))
if __name__=='__main__':unittest.main()
