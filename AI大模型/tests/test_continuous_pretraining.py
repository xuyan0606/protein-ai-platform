import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "continuous_pretrain_sequence_mlm.py"
SPEC = importlib.util.spec_from_file_location("continuous_pretrain_sequence_mlm", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ContinuousPretrainingTests(unittest.TestCase):
    def test_batch_plan_covers_all_sequences_once(self):
        plan = MODULE.build_epoch_plan(10, seed=7)
        self.assertEqual(sorted(plan), list(range(10)))
        self.assertEqual(len(plan), 10)

    def test_empty_plan_is_supported(self):
        self.assertEqual(MODULE.build_epoch_plan(0, seed=7), [])


if __name__ == "__main__":
    unittest.main()
