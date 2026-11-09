"""Run one validated request in a model-specific interpreter."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def digest(value):
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(value.encode()).hexdigest()


def run(model: str, payload: dict, workdir: Path) -> dict:
    if model == "ddgun":
        from .ddgun_runner import run_ddgun
        return run_ddgun(payload, workdir)
    if model == "esm":
        from .esm_runner import run_esm
        output = run_esm(payload, workdir)
        name = "ESM-2"
    elif model == "colabfold":
        from .colabfold_runner import run_colabfold
        output = run_colabfold(payload, workdir)
        name = "ColabFold"
    elif model == "evcouplings":
        from .evcouplings_runner import run_evcouplings
        output = run_evcouplings(payload, workdir)
        name = "EVcouplings"
    else:
        raise ValueError("Unknown scientific model")
    result = output["result"]
    if result.get("status") in ("skipped", "blocked"):
        return {**result, "model": name, "sequence_sha256": digest(payload["sequence"]),
                "input_sha256": digest(payload)}
    return {**result, "status": "completed", "model": name,
            **{k: output[k] for k in ("model_version", "algorithm_commit", "database_version")},
            "sequence_sha256": digest(payload["sequence"]), "input_sha256": digest(payload),
            "evidence": {"raw_result": output["raw_result"],
                         "raw_result_sha256": digest(output["raw_result"])}}


def main():
    model, request_path, result_path = sys.argv[1:]
    destination = Path(result_path)
    payload = json.loads(Path(request_path).read_text())
    try:
        result = run(model, payload, destination.parent / "work")
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        # Details remain in private job logs; HTTP callers receive a bounded message.
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        result = {"status": "blocked", "model": model, "blocked_reason": str(exc)[:1000]}
    destination.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
