import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_draft_namespace_isolation.py"
SPEC = importlib.util.spec_from_file_location("draft_namespace", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class DraftNamespaceTests(unittest.TestCase):
    def test_review_template_is_an_allowed_draft_namespace(self):
        self.assertTrue(module.is_allowed_namespace("datasets/curation/batches/p0/p0_batch_001.decision_review_template.jsonl"))


if __name__ == "__main__":
    unittest.main()
