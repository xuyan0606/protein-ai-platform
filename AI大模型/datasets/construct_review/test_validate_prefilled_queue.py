import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

def load():
    s=importlib.util.spec_from_file_location('v', HERE.parent.parent/'scripts'/'validate_prefilled_construct_queue.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class T(unittest.TestCase):
    def test_prefilled_rows_are_queued_not_corrupt(self):
        r=load().validate(HERE/'construct_review_queue_prefilled.csv')
        self.assertTrue(r['success']); self.assertEqual(870,r['rows']); self.assertEqual(0,r['ready_rows']); self.assertEqual('queued_blocked',r['status'])

if __name__=='__main__': unittest.main()
