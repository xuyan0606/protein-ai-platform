import importlib.util
import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_literature_measurement_source_availability.py"
SPEC = importlib.util.spec_from_file_location("lit_source_audit", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class LiteratureSourceAvailabilityTests(unittest.TestCase):
    def test_marks_missing_and_present_source_paths(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "present.xml").write_text("x", encoding="utf-8")
            digest = hashlib.sha256(b"x").hexdigest()
            report = module.build_report([{"review_task_id":"a", "source_path":"present.xml", "source_sha256": digest}, {"review_task_id":"b", "source_path":"missing.xml", "source_sha256": digest}], root)
        self.assertEqual(1, report["source_available_rows"])
        self.assertEqual(1, report["source_missing_rows"])
        self.assertFalse(report["source_complete"])

    def test_marks_present_file_with_wrong_hash_as_blocked(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "present.xml").write_text("x", encoding="utf-8")
            report = module.build_report([{"review_task_id":"a", "source_path":"present.xml", "source_sha256": "0" * 64}], root)
        self.assertEqual("blocked_hash_mismatch", report["records"][0]["status"])
        self.assertEqual(0, report["source_available_rows"])
