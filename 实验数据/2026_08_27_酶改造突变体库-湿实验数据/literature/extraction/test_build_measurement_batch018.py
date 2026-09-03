import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;DATA_ROOT=HERE.parents[1]
def load_builder():
 s=importlib.util.spec_from_file_location('b',HERE/'build_measurement_batch018.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
 def test_rows(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertEqual(28,len(r));self.assertEqual(28,len({x['measurement_id'] for x in r}));self.assertTrue(all(x['variant']=='M-60(5)' for x in r));self.assertTrue(all(x['training_eligible']=='false' for x in r))
 def test_conflict_and_temperature(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertTrue(all(x['mutation_composition']=='unresolved:L203I_vs_L103I' for x in r));self.assertEqual({'45','50','55','60'},{x['assay_temperature_c'] for x in r if x['source_locator']=='Table 2'})
if __name__=='__main__':unittest.main()
