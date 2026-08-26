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
    def test_model_evaluation_is_repeatable_with_fixed_masks(self):
        import torch
        from pretrain_sequence_mlm import build_encoder
        torch.manual_seed(3)
        model = build_encoder(22).eval()
        vocab = sorted(MODULE.AMINO_ACIDS) + ["<mask>", "<pad>"]
        token_to_id = {token: index for index, token in enumerate(vocab)}
        records = [("held_out", "ACDEFG")]
        first = MODULE.evaluate_model(model, records, token_to_id, repeats=2, seed=11, mask_probability=0.2)
        second = MODULE.evaluate_model(model, records, token_to_id, repeats=2, seed=11, mask_probability=0.2)
        self.assertEqual(first, second)

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
