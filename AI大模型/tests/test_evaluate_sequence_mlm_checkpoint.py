import importlib.util
import math
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "evaluate_sequence_mlm_checkpoint.py"
SPEC = importlib.util.spec_from_file_location("evaluate_sequence_mlm_checkpoint", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class SequenceMlmEvaluationTests(unittest.TestCase):
    def test_mask_is_deterministic_and_nonempty(self):
        import torch
        first = MODULE.build_mask(8, 0.0, torch.Generator().manual_seed(7))
        second = MODULE.build_mask(8, 0.0, torch.Generator().manual_seed(7))
        self.assertTrue(torch.equal(first, second))
        self.assertEqual(int(first.sum()), 1)

    def test_uniform_amino_acid_baseline_is_log_twenty(self):
        self.assertAlmostEqual(MODULE.uniform_amino_acid_loss(), math.log(20), places=10)


if __name__ == "__main__":
    unittest.main()
