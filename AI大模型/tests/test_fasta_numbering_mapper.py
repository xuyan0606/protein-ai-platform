import importlib.util
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[1] / 'scripts' / 'fasta_numbering_mapper.py'
spec = importlib.util.spec_from_file_location('mapper', P)
mapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mapper)

class T(unittest.TestCase):
    def test_exact_match_and_mutation(self):
        r=mapper.map_mutation('ACDEFG','ACDEFG','E4K')
        self.assertEqual('verified',r['status']); self.assertEqual(4,r['position']); self.assertEqual('E',r['parent_residue'])
    def test_length_mismatch_blocks(self):
        self.assertEqual('blocked_sequence_mismatch',mapper.map_mutation('ACDEFG','ACDXXG','E5K')['status'])
    def test_bad_notation_blocks(self):
        self.assertEqual('blocked_numbering_conflict',mapper.map_mutation('ACDEFG','ACDEFG','E5K')['status'])
if __name__=='__main__': unittest.main()
