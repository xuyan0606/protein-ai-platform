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

    def test_encoder_respects_hidden_dimension(self):
        import torch
        model = MODULE.build_encoder(22, hidden_dim=64)
        vector = model.encode(torch.tensor([1, 2, 3], dtype=torch.long))
        self.assertEqual(tuple(vector.shape), (64,))

    def test_encoder_respects_context_kernel_size(self):
        model = MODULE.build_encoder(22, kernel_size=5)
        self.assertEqual(model.context.kernel_size, (5,))

    def test_encoder_residual_mode_is_explicit(self):
        model = MODULE.build_encoder(22, residual=True)
        self.assertTrue(model.residual)

    def test_residual_context_is_gelu_of_hidden_plus_convolution(self):
        import torch

        residual_model = MODULE.build_encoder(4, hidden_dim=2, kernel_size=3, residual=True).eval()
        legacy_model = MODULE.build_encoder(4, hidden_dim=2, kernel_size=3, residual=False).eval()
        with torch.no_grad():
            residual_model.embedding.weight.fill_(0.5)
            residual_model.position.weight.fill_(0.25)
            residual_model.context.weight.fill_(0.2)
            residual_model.context.bias.fill_(0.1)
            legacy_model.load_state_dict(residual_model.state_dict())

            ids = torch.tensor([0, 1, 2], dtype=torch.long)
            positions = torch.arange(len(ids))
            hidden = residual_model.embedding(ids) + residual_model.position(positions)
            context = residual_model.context(hidden.transpose(0, 1).unsqueeze(0)).squeeze(0).transpose(0, 1)
            expected_residual = torch.nn.functional.gelu(hidden + context)

            actual_residual = residual_model.contextualize(ids)
            actual_legacy = legacy_model.contextualize(ids)

        self.assertTrue(torch.allclose(actual_residual, expected_residual))
        self.assertTrue(torch.allclose(actual_legacy, context))
        self.assertFalse(torch.allclose(actual_residual, actual_legacy))


if __name__ == "__main__":
    unittest.main()
