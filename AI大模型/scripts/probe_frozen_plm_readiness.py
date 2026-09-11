#!/usr/bin/env python3
"""Probe local readiness for frozen ESM-2/ProtT5 research embeddings.

This script never downloads weights and never emits fake embeddings.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path

def module_version(name):
    spec = importlib.util.find_spec(name)
    if spec is None:
        return {"available": False, "version": None}
    try:
        module = __import__(name)
        return {"available": True, "version": getattr(module, "__version__", "unknown")}
    except Exception as exc:
        return {"available": False, "version": None, "error": type(exc).__name__}

def main():
    p = argparse.ArgumentParser(); p.add_argument('--input', type=Path, required=True); p.add_argument('--output', type=Path, required=True); p.add_argument('--weights', type=Path)
    a = p.parse_args()
    weights_exists = bool(a.weights and a.weights.exists())
    esm = module_version('esm'); transformers = module_version('transformers')
    if weights_exists and esm['available']:
        status, reason = 'ready_for_local_evaluation', None
    else:
        status = 'blocked_missing_local_runtime_or_weights'
        missing = []
        if not esm['available']:
            missing.append('fair-esm')
        if not transformers['available']:
            missing.append('transformers')
        if not weights_exists:
            missing.append('local_esm2_weights')
        reason = missing
    out = {
        'schema_version': 'frozen_plm_readiness.v1', 'research_only': True,
        'input_sha256': hashlib.sha256(a.input.read_bytes()).hexdigest(),
        'requested_model': 'ESM-2 (frozen sequence representation)',
        'status': status, 'blocking_requirements': reason,
        'runtime': {'torch': module_version('torch'), 'fair_esm': esm, 'transformers': transformers},
        'weights': {'path': str(a.weights) if a.weights else None, 'exists': weights_exists},
        'embedding_written': False, 'training_run_started': False,
        'production_registration': 'forbidden'
    }
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'status': status, 'embedding_written': False})); return 0
if __name__ == '__main__': raise SystemExit(main())
