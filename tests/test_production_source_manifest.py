"""Failure cases for the production source provenance check; no external calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify_production_source.py'
spec = importlib.util.spec_from_file_location('production_source_verifier', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / 'backend/app/example.py'
        self.file.parent.mkdir(parents=True)
        self.file.write_text('print("production")\n')
        docs = self.root / 'docs/baselines'
        docs.mkdir(parents=True)
        self.record = {'source_commit': 'original-runtime',
                       'git_source_management': {'original_runtime_commit': 'original-runtime'}}
        self.manifest = {'original_source_commit': 'original-runtime', 'files': [{
            'path': 'backend/app/example.py',
            'sha256': hashlib.sha256(self.file.read_bytes()).hexdigest()}]}
        self.save()

    def save(self):
        (self.root / module.RECORD).write_text(json.dumps(self.record))
        (self.root / module.MANIFEST).write_text(json.dumps(self.manifest))

    def test_matching_runtime_snapshot_passes(self):
        self.assertTrue(module.verify(self.root)['passed'])

    def test_old_workspace_source_is_rejected(self):
        self.file.write_text('print("old-workspace")\n')
        result = module.verify(self.root)
        self.assertFalse(result['passed'])
        self.assertIn('differs from original runtime', result['errors'][0])

    def test_missing_runtime_module_is_rejected(self):
        self.file.unlink()
        self.assertFalse(module.verify(self.root)['passed'])

    def test_stale_production_record_is_rejected(self):
        self.record['source_commit'] = 'old-release'
        self.save()
        self.assertFalse(module.verify(self.root)['passed'])

    def test_path_outside_repository_is_rejected(self):
        self.manifest['files'][0]['path'] = '../outside.py'
        self.save()
        self.assertFalse(module.verify(self.root)['passed'])


if __name__ == '__main__':
    unittest.main()
