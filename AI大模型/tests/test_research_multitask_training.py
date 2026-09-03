import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "train_research_multitask.py"
SPEC = importlib.util.spec_from_file_location("train_research_multitask", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def rows_for(
    head: str,
    count: int,
    *,
    groups: int = 2,
    replicates: int = 1,
) -> list[dict]:
    rows = []
    for index in range(count):
        rows.append(
            {
                "head": head,
                "label_value": f"class_{index % 2}",
                "group_id": f"group_{index % groups}",
                "replicate_id": f"rep_{index % replicates}",
                "features": {
                    "position": float(index + 1),
                    "relative_activity": float(index % 3) / 2.0,
                    "ph": float(4 + index % 4),
                },
            }
        )
    return rows


class ResearchMultitaskTrainingTests(unittest.TestCase):
    def test_empty_labels_block_training(self):
        result = MODULE.run_training([])
        self.assertEqual(result["status"], "blocked_no_trainable_heads")
        self.assertFalse(result["training_executed"])

    def test_default_mode_rejects_below_threshold_head(self):
        result = MODULE.run_training(rows_for("activity_risk", 6))
        self.assertEqual(result["status"], "blocked_head_thresholds_not_met")
        self.assertFalse(result["training_executed"])

    def test_smoke_mode_trains_only_observed_head_without_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = MODULE.run_training(
                rows_for("activity_risk", 6),
                mode="smoke",
                checkpoint_path=Path(tmp) / "smoke.pt",
                epochs=1,
            )
            self.assertEqual(result["trained_heads"], ["activity_risk"])
            self.assertTrue(result["training_executed"])
            self.assertEqual(result["artifact_kind"], "research_multitask_smoke_only")
            self.assertFalse(result["safe_for_model_claim"])
            self.assertFalse(result["release_ready"])
            self.assertEqual(len(result["checkpoint_sha256"]), 64)
            self.assertTrue((Path(tmp) / "smoke.pt").is_file())

    def test_research_mode_trains_five_heads_after_thresholds(self):
        rows = []
        for head in MODULE.EXPECTED_HEADS:
            rows.extend(rows_for(head, 12, groups=3, replicates=2))
        with tempfile.TemporaryDirectory() as tmp:
            result = MODULE.run_training(
                rows,
                mode="research",
                minimum_samples=10,
                minimum_groups=3,
                minimum_replicates=2,
                checkpoint_path=Path(tmp) / "research.pt",
                epochs=1,
            )
            self.assertEqual(set(result["trained_heads"]), set(MODULE.EXPECTED_HEADS))
            self.assertEqual(result["split"]["group_overlap_count"], 0)
            self.assertFalse(result["safe_for_model_claim"])

    def test_unknown_heads_are_not_silently_trained(self):
        result = MODULE.run_training(rows_for("made_up_head", 20), mode="smoke")
        self.assertEqual(result["status"], "blocked_no_trainable_heads")
        self.assertEqual(result["unknown_heads"], ["made_up_head"])

    def test_label_and_near_label_fields_never_enter_numeric_features(self):
        forbidden = {
            "activity_relative_to_wt",
            "activity_risk_label",
            "label_value",
            "label_decision",
            "label_ddg",
            "label_stability_delta_tm_c",
            "substrate_fit_label",
            "assay_success",
        }
        self.assertTrue(forbidden.issubset(set(MODULE.LABEL_OR_NEAR_LABEL_FEATURE_FIELDS)))

        row = {
            "head": "activity_risk",
            "label_value": "low_activity_risk",
            "activity_risk_label": "low_activity_risk",
            "activity_relative_to_wt": 1.25,
            "label_decision": "go",
            "label_ddg": -1.2,
            "label_stability_delta_tm_c": 3.5,
            "substrate_fit_label": "fit",
            "assay_success": "pass",
            "canonical_position": 105,
            "ph": 4.8,
            "enzyme_id": "enzyme-a",
            "mutation": "D105N",
            "metric": "activity",
        }
        values, schema = MODULE.numeric_features(row)
        self.assertEqual(len(values), len(schema))
        self.assertTrue(set(schema).isdisjoint(forbidden))
        for field in forbidden:
            self.assertNotIn(field, schema)
            self.assertNotIn(MODULE.as_float(row[field]), values)

        nested = {
            **row,
            "features": {
                "position": 105.0,
                "ph": 4.8,
                "activity_relative_to_wt": 9.9,
                "label_value": 1.0,
                "activity_risk_label": 2.0,
                "label_decision": 3.0,
                "label_ddg": 4.0,
                "label_stability_delta_tm_c": 5.0,
                "substrate_fit_label": 6.0,
                "assay_success": 7.0,
                "safe_structure_score": 0.4,
            },
        }
        nested_values, nested_schema = MODULE.numeric_features(nested)
        self.assertEqual(nested_schema, ["ph", "position", "safe_structure_score"])
        self.assertEqual(nested_values, [4.8, 105.0, 0.4])
        self.assertTrue(set(nested_schema).isdisjoint(forbidden))

    def test_training_receipt_and_checkpoint_record_feature_exclusion_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "smoke.pt"
            result = MODULE.run_training(
                rows_for("activity_risk", 6),
                mode="smoke",
                checkpoint_path=checkpoint,
                epochs=1,
            )
            self.assertIn("feature_schema", result)
            self.assertIn("excluded_feature_fields", result)
            self.assertEqual(len(result["feature_schema_sha256"]), 64)
            self.assertTrue(
                set(MODULE.LABEL_OR_NEAR_LABEL_FEATURE_FIELDS).issubset(
                    set(result["excluded_feature_fields"])
                )
            )
            self.assertTrue(
                set(result["feature_schema"]).isdisjoint(
                    set(MODULE.LABEL_OR_NEAR_LABEL_FEATURE_FIELDS)
                )
            )

            import torch

            payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
            self.assertEqual(payload["feature_schema"], result["feature_schema"])
            self.assertEqual(
                payload["excluded_feature_fields"],
                result["excluded_feature_fields"],
            )
            self.assertEqual(
                payload["feature_schema_sha256"],
                result["feature_schema_sha256"],
            )
            self.assertFalse(payload["safe_for_model_claim"])

    def test_heterogeneous_explicit_features_align_by_field_name(self):
        source_rows = [
            {
                "head": "activity_risk",
                "label_value": "low",
                "group_id": "g1",
                "features": {"position": 105.0, "ph": 4.8},
            },
            {
                "head": "activity_risk",
                "label_value": "watch",
                "group_id": "g2",
                "features": {"ph": 6.0, "safe_structure_score": 0.4},
            },
        ]
        normalized, _unknown = MODULE.normalize_rows(source_rows)
        schema = MODULE.align_feature_rows(normalized)

        self.assertEqual(schema, ["ph", "position", "safe_structure_score"])
        self.assertEqual(normalized[0]["features"], [4.8, 105.0, 0.0])
        self.assertEqual(normalized[1]["features"], [6.0, 0.0, 0.4])
        self.assertTrue(all(row["feature_schema"] == schema for row in normalized))

    def test_default_group_identity_does_not_merge_same_mutation_across_proteins(self):
        first = {
            "project_id": "project-a",
            "enzyme_id": "enzyme-a",
            "mutation": "D105N",
        }
        second = {
            "project_id": "project-b",
            "enzyme_id": "enzyme-b",
            "mutation": "D105N",
        }
        self.assertNotEqual(MODULE.row_group(first), MODULE.row_group(second))
        self.assertEqual(
            MODULE.row_group({**first, "group_id": "reviewed-group"}),
            "reviewed-group",
        )

    def test_receipt_and_checkpoint_bind_training_input_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "smoke.pt"
            result = MODULE.run_training(
                rows_for("activity_risk", 6),
                mode="smoke",
                checkpoint_path=checkpoint,
                epochs=1,
            )

            manifest = result["training_input_manifest"]
            self.assertEqual(manifest["schema_version"], "kwb_five_head_training_input_v1")
            self.assertEqual(manifest["normalized_label_row_count"], 6)
            self.assertEqual(manifest["head_label_rows"]["activity_risk"], 6)
            self.assertEqual(len(manifest["canonical_rows_sha256"]), 64)
            self.assertEqual(len(result["training_input_manifest_sha256"]), 64)
            self.assertEqual(result["checkpoint_receipt"]["sha256"], result["checkpoint_sha256"])
            self.assertGreater(result["checkpoint_receipt"]["size_bytes"], 0)

            import torch

            payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
            self.assertEqual(
                payload["training_input_manifest_sha256"],
                result["training_input_manifest_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
