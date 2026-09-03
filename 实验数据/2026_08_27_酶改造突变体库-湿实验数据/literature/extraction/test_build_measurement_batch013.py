import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;DATA_ROOT=HERE.parents[1]
def load_builder():
 s=importlib.util.spec_from_file_location('b',HERE/'build_measurement_batch013.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
 def test_rows(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertEqual(12,len(r));self.assertEqual({'HAT','HET','HAE','HDE'},{x['variant'] for x in r});self.assertTrue(all(x['training_eligible']=='false' for x in r))
 def test_compositions(self):
  r=load_builder().build_rows(DATA_ROOT);self.assertEqual('D304A/T305E',next(x for x in r if x['variant']=='HAE')['mutation_composition']);self.assertEqual('161',next(x for x in r if x['variant']=='HAT' and x['metric']=='Km')['wt_value'])
if __name__=='__main__':unittest.main()
