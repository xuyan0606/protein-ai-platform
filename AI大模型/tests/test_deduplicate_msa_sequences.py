import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "deduplicate_msa_sequences.py"
SPEC = importlib.util.spec_from_file_location("deduplicate_msa_sequences", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class DeduplicationContractTests(unittest.TestCase):
    def test_script_exposes_main(self):
        self.assertTrue(callable(MODULE.main))


if __name__ == "__main__":
    unittest.main()
