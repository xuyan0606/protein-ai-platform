import importlib.util
import hashlib
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_literature_measurement_source_recovery_requests.py"
SPEC = importlib.util.spec_from_file_location("lit_recovery", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class LiteratureSourceRecoveryTests(unittest.TestCase):
    def test_groups_missing_sources_and_preserves_provenance(self):
        rows = [
            {"review_task_id":"a", "source_path":"x.xml", "source_sha256":"sha", "pmcid":"PMC1", "doi":"10/a"},
            {"review_task_id":"b", "source_path":"x.xml", "source_sha256":"sha", "pmcid":"PMC1", "doi":"10/a"},
        ]
        result = module.build_requests(rows, Path("/tmp/definitely-missing-source-root"))
        self.assertEqual(1, len(result["requests"]))
        self.assertEqual(["a", "b"], result["requests"][0]["review_task_ids"])
        self.assertEqual("blocked_missing_local_source", result["requests"][0]["status"])

    def test_recover_source_writes_only_when_sha_matches(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "recover_literature_measurement_sources.py"
        spec = importlib.util.spec_from_file_location("lit_source_recover", script)
        recover = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recover)
        payload = b"<article><body>verified</body></article>"
        digest = hashlib.sha256(payload).hexdigest()
        request = {"source_path": "literature/raw_fulltext_xml/x/PMC1.xml", "pmcids": ["PMC1"], "expected_sha256": [digest]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = recover.recover_request(request, root, lambda _: payload)
            self.assertEqual("recovered", result["status"])
            self.assertEqual(payload, (root / request["source_path"]).read_bytes())

    def test_recover_source_rejects_hash_mismatch_without_overwrite(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "recover_literature_measurement_sources.py"
        spec = importlib.util.spec_from_file_location("lit_source_recover_mismatch", script)
        recover = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recover)
        target = "literature/raw_fulltext_xml/x/PMC1.xml"
        request = {"source_path": target, "pmcids": ["PMC1"], "expected_sha256": ["0" * 64]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = recover.recover_request(request, root, lambda _: b"wrong")
            self.assertEqual("hash_mismatch", result["status"])
            self.assertFalse((root / target).exists())
