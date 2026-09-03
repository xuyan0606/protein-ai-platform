#!/usr/bin/env python3
"""Build a production model manifest only from real, complete artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


EVIDENCE = ("feature_contract", "training", "evaluation", "release")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(base: Path, model_dir: Path | None = None) -> dict[str, Any]:
    gate = {}
    for name in ("production_model_gate.json", "production_model_gate_20260829.json"):
        path = base / "reports" / name
        if path.is_file():
            try:
                gate = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                gate = {}
            break
    if gate.get("production_ready") is not True:
        return {"status": "blocked_pending_production_gate", "production_model_artifact": False, "artifacts": [], "blockers": gate.get("blockers") or ["production gate missing or not ready"]}
    model_dir = model_dir or (base / "reports" / "production_model")
    weights = sorted(model_dir.glob("*.safetensors")) + sorted(model_dir.glob("*.pt"))
    entrypoint = model_dir / "inference.py"
    if not weights or not entrypoint.is_file():
        result = {"status": "blocked_missing_training_artifacts", "production_model_artifact": False, "artifacts": []}
    else:
        missing = [name for name in EVIDENCE if not (base / "reports" / f"{name}_evidence.json").is_file()]
        if missing:
            result = {"status": "blocked_missing_evidence", "production_model_artifact": False, "missing_evidence": missing}
        else:
            result = {
                "status": "validated",
                "schema_version": "production_model_package_v1",
                "model": {"name": "KWB-EnzymeDesigner", "version": "1.0.0"},
                "production_model_artifact": True,
                "weights": [{"artifact_type": "neural_weights", "path": str(p.relative_to(base)), "sha256": _sha(p), "size_bytes": p.stat().st_size} for p in weights],
                "inference_entrypoint": {"path": str(entrypoint.relative_to(base)), "sha256": _sha(entrypoint), "symbol": "predict"},
                **{name: {"path": str((base / "reports" / f"{name}_evidence.json").relative_to(base)), "sha256": _sha(base / "reports" / f"{name}_evidence.json")} for name in EVIDENCE},
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--base", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = build_manifest(args.base); args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print(json.dumps(result, ensure_ascii=False)); return 0 if result.get("status") == "validated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
