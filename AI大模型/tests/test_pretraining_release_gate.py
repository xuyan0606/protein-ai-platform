import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_pretraining_release_gate.py"
SPEC = importlib.util.spec_from_file_location("validate_pretraining_release_gate", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class PretrainingReleaseGateTests(unittest.TestCase):
    def test_complete_pretraining_asset_remains_blocked_for_release(self):
        decision = MODULE.evaluate_gate({
            "integrity_pass": True,
            "safe_for_supervised_training": False,
            "safe_for_model_claim": False,
            "release_status": "pretraining_only_not_for_production",
        })
        self.assertTrue(decision["success"])
        self.assertFalse(decision["release_ready"])
        self.assertEqual(decision["decision"], "blocked_pretraining_only")

    def test_inconsistent_claim_flag_fails_validation(self):
        decision = MODULE.evaluate_gate({
            "integrity_pass": True,
            "safe_for_supervised_training": False,
            "safe_for_model_claim": True,
            "release_status": "pretraining_only_not_for_production",
        })
        self.assertFalse(decision["success"])
        self.assertIn("safe_for_model_claim_must_be_false", decision["failures"])


if __name__ == "__main__":
    unittest.main()
