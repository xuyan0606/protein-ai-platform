import importlib.util
import hashlib
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_five_head_training_input_manifest.py"
SPEC = importlib.util.spec_from_file_location("build_five_head_training_input_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_manifest_joins_features_only_on_exact_protein_identity(tmp_path):
    labels = tmp_path / "labels.jsonl"
    features = tmp_path / "features.jsonl"
    labels.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "head": "activity_risk",
                        "label_value": "low",
                        "training_label_source": True,
                        "ready_for_training_import": True,
                        "safe_for_training_import": True,
                        "uniprot_id": "P12345",
                        "mutation": "D105N",
                    }
                ),
                json.dumps(
                    {
                        "head": "activity_risk",
                        "label_value": "watch",
                        "training_label_source": True,
                        "ready_for_training_import": True,
                        "safe_for_training_import": True,
                        "uniprot_id": None,
                        "mutation": "S265T",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    features.write_text(
        json.dumps(
            {
                "feature_index_id": "msa:P12345",
                "feature_family": "msa_conservation",
                "uniprot_id": "P12345",
                "model_consumable": True,
                "training_label_source": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = MODULE.build_manifest([labels], features)

    assert manifest["label_rows"] == 2
    assert manifest["exact_feature_join_rows"] == 1
    assert manifest["rows_without_exact_feature_join"] == 1
    assert manifest["feature_rows_counted_as_labels"] == 0
    assert manifest["dataset_sha256"] == hashlib.sha256(labels.read_bytes()).hexdigest()
    assert manifest["ready_for_training_execution"] is False
    assert manifest["head_stats"]["activity_risk"]["label_rows"] == 2


def test_manifest_rejects_candidate_rows_without_formal_import_markers(tmp_path):
    labels = tmp_path / "labels.jsonl"
    features = tmp_path / "features.jsonl"
    labels.write_text(
        json.dumps(
            {
                "head": "stability",
                "label_value": 1.2,
                "training_label_source": False,
                "ready_for_training_import": False,
                "uniprot_id": "P12345",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    features.write_text("", encoding="utf-8")

    manifest = MODULE.build_manifest([labels], features)

    assert manifest["label_rows"] == 0
    assert manifest["rejected_rows"] == 1
    assert manifest["ready_for_training_execution"] is False
    assert manifest["safe_for_model_claim"] is False


def test_safe_pipeline_builds_manifest_after_labels_and_features():
    runner = (Path(__file__).parents[1] / "scripts" / "run_safe_training_pipeline.py").read_text(
        encoding="utf-8"
    )
    feature_index = runner.index('["scripts/build_validated_feature_index.py"]')
    label_import = runner.index('["scripts/build_activity_risk_training_import_labels.py"]')
    manifest = runner.index('["scripts/build_five_head_training_input_manifest.py"]')

    assert manifest > feature_index
    assert manifest > label_import
