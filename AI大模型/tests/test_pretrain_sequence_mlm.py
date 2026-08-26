import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "pretrain_sequence_mlm.py"
SPEC = importlib.util.spec_from_file_location("pretrain_sequence_mlm", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class SequenceSplitTests(unittest.TestCase):
    def test_split_is_deterministic_and_preserves_rows(self):
        rows = [f"SEQ{index}" for index in range(10)]
        train_a, validation_a = MODULE.split_sequences(rows, 0.2, 7)
        train_b, validation_b = MODULE.split_sequences(rows, 0.2, 7)
        self.assertEqual((train_a, validation_a), (train_b, validation_b))
        self.assertEqual(sorted(train_a + validation_a), sorted(rows))
        self.assertEqual(len(validation_a), 2)

    def test_split_keeps_one_training_row(self):
        train, validation = MODULE.split_sequences(["A", "B"], 0.99, 1)
        self.assertEqual(len(train), 1)
        self.assertEqual(len(validation), 1)

    def test_split_rejects_invalid_fraction(self):
        with self.assertRaises(ValueError):
            MODULE.split_sequences(["A"], 1.0, 1)

    def test_encoder_is_position_sensitive(self):
        import torch
        model = MODULE.build_encoder(22)
        model.eval()
        with torch.no_grad():
            first = model.encode(torch.tensor([1, 2, 3], dtype=torch.long))
            reordered = model.encode(torch.tensor([3, 2, 1], dtype=torch.long))
        self.assertFalse(torch.allclose(first, reordered))


if __name__ == "__main__":
    unittest.main()
