import importlib.util,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;DATA_ROOT=HERE.parents[1]
def load_module():
 s=importlib.util.spec_from_file_location('v',HERE/'validate_measurement_candidates.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
 def test_current_batches(self):
        r=load_module().validate(DATA_ROOT,HERE);self.assertEqual(24,r['batch_count']);self.assertEqual(870,r['row_count']);self.assertEqual(870,r['unique_measurement_ids']);self.assertEqual(0,r['failure_count'])
 def test_duplicate_is_rejected(self):
  v=load_module()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);src=HERE/'measurement_candidates_batch019.csv';(p/src.name).write_bytes(src.read_bytes());(p/'measurement_candidates_batch020.csv').write_bytes(src.read_bytes())
   self.assertGreater(v.validate(DATA_ROOT,p)['failure_count'],0)
if __name__=='__main__':unittest.main()
