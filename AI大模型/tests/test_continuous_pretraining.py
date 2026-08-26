import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "continuous_pretrain_sequence_mlm.py"
SPEC = importlib.util.spec_from_file_location("continuous_pretrain_sequence_mlm", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ContinuousPretrainingTests(unittest.TestCase):
    def test_learning_rate_must_be_positive(self):
        self.assertEqual(MODULE.validate_learning_rate(0.001), 0.001)
        with self.assertRaises(ValueError):
            MODULE.validate_learning_rate(0.0)

    def test_learning_rate_cli_parser_accepts_decimal(self):
        self.assertEqual(MODULE.parse_learning_rate("0.0003"), 0.0003)

    def test_hidden_dimension_must_be_positive(self):
        self.assertEqual(MODULE.validate_hidden_dim(64), 64)
        with self.assertRaises(ValueError):
            MODULE.validate_hidden_dim(0)

    def test_hidden_dimension_cli_parser_accepts_integer(self):
        self.assertEqual(MODULE.parse_hidden_dim("64"), 64)

    def test_context_kernel_size_must_be_positive_odd(self):
        self.assertEqual(MODULE.parse_kernel_size("5"), 5)
        with self.assertRaises(ValueError):
            MODULE.parse_kernel_size("4")

    def test_residual_cli_parser_accepts_boolean(self):
        self.assertTrue(MODULE.parse_residual("true"))
        self.assertFalse(MODULE.parse_residual("false"))

    def test_grouped_split_has_no_source_overlap(self):
        records = [("group_a", "AAAA"), ("group_a", "AAAC"), ("group_b", "CCCC"), ("group_c", "DDDD")]
        train, validation = MODULE.split_grouped_records(records, validation_fraction=0.25, seed=7)
        self.assertFalse({group for group, _ in train} & {group for group, _ in validation})
        self.assertEqual(sorted(train + validation), sorted(records))

    def test_fasta_records_preserve_source_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.fasta"
            path.write_text(">a|source=one.aln.fasta|source_index=0\nAAAA\n>b|source=one.aln.fasta|source_index=1\nAAAC\n", encoding="utf-8")
            self.assertEqual(MODULE.load_fasta_records(path), [("one.aln.fasta", "AAAA"), ("one.aln.fasta", "AAAC")])

    def test_masked_inputs_replace_selected_tokens(self):
        import torch
        ids = torch.tensor([1, 2, 3], dtype=torch.long)
        masked, mask = MODULE.apply_mask(ids, mask_id=9, mask_positions=torch.tensor([True, False, True]))
        self.assertEqual(mask.tolist(), [True, False, True])
        self.assertEqual(masked.tolist(), [9, 2, 9])

    def test_batch_plan_covers_all_sequences_once(self):
        plan = MODULE.build_epoch_plan(10, seed=7)
        self.assertEqual(sorted(plan), list(range(10)))
        self.assertEqual(len(plan), 10)

    def test_empty_plan_is_supported(self):
        self.assertEqual(MODULE.build_epoch_plan(0, seed=7), [])


if __name__ == "__main__":
    unittest.main()
