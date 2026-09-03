#!/usr/bin/env python3
"""Train and evaluate a dependency-free supervised mutation baseline."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table.jsonl"
STRICT_INPUT = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
DEEP_AUDIT = AI_ROOT / "datasets" / "curation" / "numbering_deep_audit_all_stability_records.jsonl"
SPLIT_REPORT = AI_ROOT / "reports" / "supervised_mutation_split_report.json"
MODEL_OUT = AI_ROOT / "prototype" / "supervised_mutation_baseline_model.json"
REPORT_OUT = AI_ROOT / "reports" / "supervised_mutation_baseline_eval.json"

LABELS = ("go", "watch", "no_go")
EXCLUDED_FEATURES = {
    "record_id",
    "source",
    "record_type",
    "uniprot_id",
    "group_key",
    "mutation",
    "wild_type",
    "mutant",
    "label_decision",
    "label_stability_delta_tm_c",
    "label_ddg",
    "label_source_db",
}


def is_truthy_marker(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return False


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def assert_strict_supervised_rows(rows: list[dict[str, Any]], path: Path) -> None:
    failures: list[str] = []
    for index, row in enumerate(rows, start=1):
        if row.get("usable_as_supervised_label") is not True:
            failures.append(f"row_{index}:usable_as_supervised_label_not_true")
        if row.get("numbering_verified_by_sequence") is not True:
            failures.append(f"row_{index}:numbering_verified_by_sequence_not_true")
        if is_truthy_marker(row.get("usable_as_weak_evidence")):
            failures.append(f"row_{index}:weak_evidence")
        if row.get("integrity_flags"):
            failures.append(f"row_{index}:integrity_flags_present")
        if row.get("label_decision") not in set(LABELS):
            failures.append(f"row_{index}:invalid_label_decision")
    if failures:
        sample = ", ".join(failures[:10])
        raise SystemExit(
            f"Refusing non-strict supervised training input {path}: "
            f"{len(failures)} guard failure(s): {sample}"
        )


def assert_no_deep_audit_rejections(rows: list[dict[str, Any]], audit_path: Path) -> None:
    if not audit_path.exists():
        return
    audit_by_record = {
        str(row.get("record_id")): row
        for row in load_jsonl(audit_path)
        if row.get("record_id")
    }
    rejected = [
        str(row.get("record_id"))
        for row in rows
        if audit_by_record.get(str(row.get("record_id")), {}).get("audit_recommended_decision") == "reject_label"
    ]
    if rejected:
        sample = ", ".join(rejected[:10])
        raise SystemExit(
            "Refusing deep-audit-rejected supervised rows: "
            f"{len(rejected)} rejected record(s): {sample}"
        )


def numeric_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return None


def feature_names(rows: list[dict[str, Any]]) -> list[str]:
    names: set[str] = set()
    for row in rows:
        for key, value in row.items():
            if key in EXCLUDED_FEATURES:
                continue
            if numeric_value(value) is not None:
                names.add(key)
    return sorted(names)


def vector(row: dict[str, Any], features: list[str]) -> list[float]:
    values = []
    for feature in features:
        value = numeric_value(row.get(feature))
        values.append(value if value is not None else 0.0)
    return values


def normalize(vectors: list[list[float]]) -> tuple[list[float], list[float]]:
    if not vectors:
        return [], []
    columns = list(zip(*vectors))
    means = [mean(col) for col in columns]
    scales = []
    for col, mu in zip(columns, means):
        variance = mean([(value - mu) ** 2 for value in col])
        scales.append(math.sqrt(variance) or 1.0)
    return means, scales


def apply_normalize(values: list[float], means: list[float], scales: list[float]) -> list[float]:
    return [(value - mu) / scale for value, mu, scale in zip(values, means, scales)]


def centroid(vectors: list[list[float]], width: int) -> list[float]:
    if not vectors:
        return [0.0] * width
    return [mean(col) for col in zip(*vectors)]


def distance(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def predict(row: dict[str, Any], model: dict[str, Any]) -> tuple[str, dict[str, float]]:
    if model.get("selected_strategy") == "majority_class":
        label = model["majority_class"]
        return label, {candidate: 1.0 if candidate == label else 0.0 for candidate in LABELS}

    features = model["features"]
    values = apply_normalize(vector(row, features), model["normalization"]["means"], model["normalization"]["scales"])
    scores = {}
    for label in LABELS:
        prior = float(model["class_priors"].get(label, 1e-9))
        dist = distance(values, model["centroids"].get(label, [0.0] * len(features)))
        scores[label] = math.log(max(prior, 1e-9)) - dist
    return max(scores, key=scores.get), scores


def accuracy(rows: list[dict[str, Any]], model: dict[str, Any]) -> float | None:
    if not rows:
        return None
    correct = sum(1 for row in rows if predict(row, model)[0] == row["label_decision"])
    return round(correct / len(rows), 3)


def evaluate(rows: list[dict[str, Any]], model: dict[str, Any], split: str) -> dict[str, Any]:
    records = []
    confusion = {actual: {predicted: 0 for predicted in LABELS} for actual in LABELS}
    correct = 0
    for row in rows:
        predicted, scores = predict(row, model)
        actual = row["label_decision"]
        if predicted == actual:
            correct += 1
        if actual in confusion and predicted in confusion[actual]:
            confusion[actual][predicted] += 1
        records.append({
            "record_id": row.get("record_id"),
            "uniprot_id": row.get("uniprot_id"),
            "mutation": row.get("mutation"),
            "actual": actual,
            "predicted": predicted,
            "scores": {key: round(value, 4) for key, value in scores.items()},
        })
    return {
        "split": split,
        "rows": len(rows),
        "accuracy": round(correct / len(rows), 3) if rows else None,
        "label_distribution": dict(Counter(row["label_decision"] for row in rows)),
        "confusion": confusion,
        "records": records[:50],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train supervised mutation baseline")
    parser.add_argument("--input", type=Path, default=STRICT_INPUT)
    parser.add_argument("--deep-audit", type=Path, default=DEEP_AUDIT)
    parser.add_argument("--split-report", type=Path, default=SPLIT_REPORT)
    parser.add_argument("--model-output", type=Path, default=MODEL_OUT)
    parser.add_argument("--report-output", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    assert_strict_supervised_rows(rows, args.input)
    assert_no_deep_audit_rejections(rows, args.deep_audit)
    split_report = json.loads(args.split_report.read_text(encoding="utf-8"))
    assignments = split_report["assignments"]
    rows_by_split = {
        split: [row for row in rows if assignments.get(row.get("group_key")) == split]
        for split in ("train", "validation", "test")
    }
    train_rows = rows_by_split["train"]
    if not train_rows:
        model = {
            "model": "KWB-EnzymeDesigner-supervised-mutation-baseline",
            "version": "0.4.0-centroid-baseline",
            "status": "blocked_empty_train_split",
            "trained_on_rows": 0,
            "training_source": str(args.input),
            "split_source": str(args.split_report),
            "features": [],
            "safe_for_model_claim": False,
            "limitations": [
                "no real-source strict supervised rows available",
                "training skipped fail-closed instead of fabricating labels",
            ],
        }
        reports = {
            "model": model["model"],
            "version": model["version"],
            "status": "blocked_empty_train_split",
            "rows": len(rows),
            "features": 0,
            "selected_strategy": None,
            "splits": {
                split: {"split": split, "rows": len(split_rows), "accuracy": None, "label_distribution": {}, "confusion": {}, "records": []}
                for split, split_rows in rows_by_split.items()
            },
            "safe_for_model_claim": False,
            "policy": "Training is skipped when no train rows exist; no synthetic fallback labels are created.",
        }
        args.model_output.parent.mkdir(parents=True, exist_ok=True)
        args.model_output.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.report_output.parent.mkdir(parents=True, exist_ok=True)
        args.report_output.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "rows": len(rows),
            "train_rows": 0,
            "features": 0,
            "status": "blocked_empty_train_split",
            "model_output": str(args.model_output),
            "report_output": str(args.report_output),
        }, ensure_ascii=False))
        return 0

    features = feature_names(train_rows)
    raw_train_vectors = [vector(row, features) for row in train_rows]
    means, scales = normalize(raw_train_vectors)
    train_vectors = [apply_normalize(values, means, scales) for values in raw_train_vectors]
    labels = [row["label_decision"] for row in train_rows]
    class_counts = Counter(labels)
    centroids = {
        label: centroid([vec for vec, row in zip(train_vectors, train_rows) if row["label_decision"] == label], len(features))
        for label in LABELS
    }
    priors = {label: class_counts.get(label, 0) / len(train_rows) for label in LABELS}
    model = {
        "model": "KWB-EnzymeDesigner-supervised-mutation-baseline",
        "version": "0.4.0-centroid-baseline",
        "trained_on_rows": len(train_rows),
        "training_source": str(args.input),
        "split_source": str(args.split_report),
        "features": features,
        "excluded_features": sorted(EXCLUDED_FEATURES),
        "normalization": {"means": means, "scales": scales},
        "class_priors": priors,
        "centroids": centroids,
        "majority_class": class_counts.most_common(1)[0][0],
        "selected_strategy": "centroid",
        "label_distribution": dict(class_counts),
        "limitations": [
            "dependency-free centroid classifier, not a neural network",
            "no structure-derived features yet",
            "labels are public/local DB derived and need wet-lab feedback calibration",
            "dTm and ddG are excluded from input features to avoid direct label leakage",
        ],
    }
    centroid_validation_accuracy = accuracy(rows_by_split["validation"], model)
    majority_model = dict(model)
    majority_model["selected_strategy"] = "majority_class"
    majority_validation_accuracy = accuracy(rows_by_split["validation"], majority_model)
    if majority_validation_accuracy is not None and centroid_validation_accuracy is not None:
        if majority_validation_accuracy >= centroid_validation_accuracy:
            model["selected_strategy"] = "majority_class"

    reports = {
        "model": model["model"],
        "version": model["version"],
        "rows": len(rows),
        "features": len(features),
        "selected_strategy": model["selected_strategy"],
        "candidate_validation_accuracy": {
            "centroid": centroid_validation_accuracy,
            "majority_class": majority_validation_accuracy,
        },
        "splits": {
            split: evaluate(split_rows, model, split)
            for split, split_rows in rows_by_split.items()
        },
        "leakage_guard": "label_stability_delta_tm_c and label_ddg excluded from training features",
    }
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    args.model_output.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "rows": len(rows),
        "train_rows": len(train_rows),
        "features": len(features),
        "validation_accuracy": reports["splits"]["validation"]["accuracy"],
        "test_accuracy": reports["splits"]["test"]["accuracy"],
        "model_output": str(args.model_output),
        "report_output": str(args.report_output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
