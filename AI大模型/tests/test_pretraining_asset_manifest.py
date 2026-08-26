import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_pretraining_asset_manifest.py"
SPEC = importlib.util.spec_from_file_location("build_pretraining_asset_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class PretrainingAssetManifestTests(unittest.TestCase):
    def test_manifest_verifies_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "asset.json"
            path.write_text("original", encoding="utf-8")
            manifest = MODULE.build_manifest([path])
            self.assertTrue(MODULE.verify_manifest(manifest)["success"])
            path.write_text("tampered", encoding="utf-8")
            result = MODULE.verify_manifest(manifest)
            self.assertFalse(result["success"])
            self.assertEqual(result["hash_mismatch_count"], 1)

    def test_missing_asset_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.json"
            manifest = MODULE.build_manifest([missing])
            self.assertFalse(MODULE.verify_manifest(manifest)["success"])


if __name__ == "__main__":
    unittest.main()
