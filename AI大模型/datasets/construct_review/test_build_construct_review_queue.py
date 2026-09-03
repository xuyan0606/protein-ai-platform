import csv, tempfile, unittest
from pathlib import Path
import importlib.util
HERE=Path(__file__).resolve().parent
def m():
 s=importlib.util.spec_from_file_location('q',HERE.parent.parent/'scripts'/'build_construct_review_queue.py');x=importlib.util.module_from_spec(s);s.loader.exec_module(x);return x
class T(unittest.TestCase):
 def test_projection_is_fail_closed(self):
  p=Path(tempfile.mkdtemp())/'r.csv';p.write_text('measurement_id,variant\nm1,D408C\nm2,N185D\n',encoding='utf-8'); rows=m().build(p);self.assertEqual(2,len(rows));self.assertEqual('D408C',rows[0]['mutation_notation']);self.assertEqual('pending',rows[0]['review_status']);self.assertEqual('',rows[0]['authorization_receipt'])
if __name__=='__main__':unittest.main()
