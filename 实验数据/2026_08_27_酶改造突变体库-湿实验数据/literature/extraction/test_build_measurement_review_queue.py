import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load_builder():
 s=importlib.util.spec_from_file_location('b',HERE/'build_measurement_review_queue.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class T(unittest.TestCase):
    def test_queue_is_empty_of_decisions(self):
        r=load_builder().build_queue(HERE/'measurement_candidate_registry.csv');self.assertEqual(150,len(r));self.assertEqual(870,sum(int(x['measurement_count']) for x in r));self.assertEqual(870,len({mid for x in r for mid in x['measurement_ids'].split('|')}));self.assertTrue(all(not x['reviewer'] and not x['review_decision'] and not x['authorization_receipt'] for x in r));self.assertEqual(1,sum(x['review_lane']=='numbering_conflict' for x in r));self.assertTrue(all(x['training_eligible']=='false' for x in r))
if __name__=='__main__':unittest.main()
