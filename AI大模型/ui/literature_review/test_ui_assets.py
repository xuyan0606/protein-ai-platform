import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


class LiteratureReviewAssetsTest(unittest.TestCase):
    def test_index_references_existing_favicon(self):
        html = (HERE / "index.html").read_text(encoding="utf-8")
        self.assertIn('rel="icon"', html)
        self.assertTrue((HERE / "favicon.svg").is_file())


if __name__ == "__main__":
    unittest.main()
