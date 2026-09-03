import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def b():
 s=importlib.util.spec_from_file_location('b',HERE/'build_measurement_batch024.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
 def test_rows(self):
  r=b().build_rows(ROOT);self.assertEqual(30,len(r));self.assertEqual(30,len({x['measurement_id'] for x in r}));self.assertEqual(10,len({x['metric'] for x in r}))
 def test_closed(self): self.assertTrue(all(x['training_eligible']=='false' for x in b().build_rows(ROOT)))
if __name__=='__main__':unittest.main()
