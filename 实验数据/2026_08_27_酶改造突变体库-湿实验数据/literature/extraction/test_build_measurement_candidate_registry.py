import csv,importlib.util,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load_builder():
 s=importlib.util.spec_from_file_location('b',HERE/'build_measurement_candidate_registry.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
    def test_registry(self):
        b=load_builder();rows=b.build_registry(HERE);self.assertEqual(870,len(rows));self.assertEqual(870,len({x['measurement_id'] for x in rows}));self.assertEqual('batch001',rows[0]['candidate_batch']);self.assertTrue(all(x['training_eligible']=='false' for x in rows))
    def test_write(self):
        b=load_builder()
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'r.csv';manifest=Path(d)/'m.json';b.write_outputs(b.build_registry(HERE),out,manifest)
            with out.open(encoding='utf-8') as f:r=list(csv.DictReader(f))
            self.assertEqual(870,len(r));self.assertTrue(manifest.is_file())
if __name__=='__main__':unittest.main()
