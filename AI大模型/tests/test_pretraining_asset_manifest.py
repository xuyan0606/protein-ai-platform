import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_pretraining_asset_manifest.py"
SPEC = importlib.util.spec_from_file_location("build_pretraining_asset_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class PretrainingAssetManifestTests(unittest.TestCase):
    def test_manifest_paths_are_relative_to_portable_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "reports" / "asset.json"
            asset.parent.mkdir()
            asset.write_text("portable", encoding="utf-8")
            manifest = MODULE.build_manifest([asset], root=root)
            self.assertEqual(manifest["assets"][0]["path"], "reports/asset.json")
            self.assertTrue(MODULE.verify_manifest(manifest, root=root)["success"])

    def test_current_manifest_uses_continuous_checkpoint_only(self):
        manifest_path = Path(__file__).parents[1] / "reports" / "sequence_pretraining_asset_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        paths = [Path(asset["path"]).name for asset in manifest["assets"]]
        self.assertIn("sequence_mlm_continuous_full_v6.checkpoint.pt", paths)
        self.assertNotIn("sequence_mlm_continuous_full_v4.checkpoint.pt", paths)
        self.assertNotIn("sequence_mlm_continuous_full_v3.checkpoint.pt", paths)
        self.assertNotIn("sequence_mlm_continuous_full_v2.checkpoint.pt", paths)
        self.assertNotIn("sequence_mlm_continuous_full.checkpoint.pt", paths)
        self.assertFalse(any(name.startswith("sequence_mlm_batch_") and name.endswith(".checkpoint.pt") for name in paths))

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
