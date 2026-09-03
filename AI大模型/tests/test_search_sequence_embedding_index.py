import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "search_sequence_embedding_index.py"
SPEC = importlib.util.spec_from_file_location("search_sequence_embedding_index", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class CosineTests(unittest.TestCase):
    def test_identical_vectors_have_one_similarity(self):
        self.assertAlmostEqual(MODULE.cosine([1.0, 2.0], [1.0, 2.0]), 1.0)

    def test_zero_vector_is_safe(self):
        self.assertEqual(MODULE.cosine([0.0, 0.0], [1.0, 2.0]), 0.0)

    def test_orthogonal_vectors_have_zero_similarity(self):
        self.assertAlmostEqual(MODULE.cosine([1.0, 0.0], [0.0, 1.0]), 0.0)


if __name__ == "__main__":
    unittest.main()
