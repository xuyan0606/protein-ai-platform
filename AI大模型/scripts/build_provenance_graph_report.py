#!/usr/bin/env python3
"""Build a lightweight local provenance graph from manifest and pipeline reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "provenance_graph_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build provenance graph report")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    manifest = load_json(AI_ROOT / "reports" / "data_lake_manifest.json")
    pipeline = load_json(AI_ROOT / "reports" / "safe_training_pipeline_run.json")
    artifacts = manifest.get("artifacts", [])
    entities = [
        {
            "entity_id": artifact.get("path"),
            "type": "file",
            "exists": artifact.get("exists"),
            "sha256": artifact.get("sha256"),
            "rows": artifact.get("rows"),
        }
        for artifact in artifacts
    ]
    activities = [
        {
            "activity_id": f"safe_pipeline_step_{index + 1:03d}",
            "command": step.get("command"),
            "returncode": step.get("returncode"),
        }
        for index, step in enumerate(pipeline.get("steps", []))
    ]
    edges = [
        {
            "activity_id": activity["activity_id"],
            "relation": "wasAssociatedWith",
            "agent_id": "local_python_runner",
        }
        for activity in activities
    ]
    report = {
        "local_only": True,
        "entity_count": len(entities),
        "activity_count": len(activities),
        "edge_count": len(edges),
        "entities": entities,
        "activities": activities,
        "agents": [{"agent_id": "local_python_runner", "type": "software", "local_only": True}],
        "edges": edges,
        "ready_for_release_traceability": bool(entities and activities),
        "policy": "This is a local provenance scaffold, not a signed SLSA attestation.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"entities": len(entities), "activities": len(activities), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
