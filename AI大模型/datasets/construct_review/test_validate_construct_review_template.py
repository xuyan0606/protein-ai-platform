import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "scripts" / "validate_construct_review_template.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConstructReviewTemplateTest(unittest.TestCase):
    def test_empty_template_is_valid_but_not_trainable(self):
        result = load_module().validate(HERE / "construct_sequence_numbering_review_template.csv")
        self.assertTrue(result["success"])
        self.assertEqual(0, result["training_import_allowed_rows"])

    def test_incomplete_review_is_blocked(self):
        path = Path(tempfile.mkdtemp()) / "review.csv"
        fields = load_module().FIELDS
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow({"measurement_id": "m1", "numbering_verified": "true"})
        result = load_module().validate(path)
        self.assertFalse(result["success"])
        self.assertEqual(0, result["training_import_allowed_rows"])


if __name__ == "__main__":
    unittest.main()
