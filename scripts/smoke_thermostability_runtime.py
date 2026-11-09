#!/usr/bin/env python3
"""Execute a real request through an existing backend container and strict adapter.

Only public validation inputs may be used without a target-specific authorization.
No token or sequence is printed. Full private request/result are retained on host.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path("/opt/protein-ai-platform/model-services/thermostability")
CODE = r'''
import asyncio, json, os, pathlib, sys, tempfile, types
data=json.load(sys.stdin)
limits=types.ModuleType("app.services.thermostability_limits")
sys.modules[limits.__name__]=limits
exec(compile(data["limits_source"], "<reviewed-model-limits>", "exec"), limits.__dict__)
module=types.ModuleType("thermostability_runtime_smoke_adapters")
sys.modules[module.__name__]=module
exec(compile(data["adapter_source"], "<reviewed-model-adapter>", "exec"), module.__dict__)
model,payload=data["model"],data["payload"]
prefix=model.upper()
os.environ[prefix+"_SERVICE_URL"]="http://172.18.0.1:4270/"+model
os.environ[prefix+"_SERVICE_TOKEN"]=data["token"]
os.environ[prefix+"_SERVICE_TIMEOUT_SECONDS"]="7260"
async def main():
 with tempfile.TemporaryDirectory(prefix="public-model-smoke-") as temp:
  if model=="ddgun":
   result=await module.ddgun_predict(payload["sequence"],payload["mutations"],payload.get("pdb_data",""),payload.get("chain_id","A"))
  elif model=="colabfold":
   msa=pathlib.Path(temp)/"query.a3m"
   msa.write_text(payload["alignment"])
   os.environ["COLABFOLD_LOCAL_MSA_PATH"]=str(msa)
   result=await module.colabfold_predict(payload["sequence"],"local")
  else:
   result=await module.evcouplings_analyze(payload["sequence"],payload["msa_quality"],payload["alignment"])
  print(json.dumps(result,ensure_ascii=False,allow_nan=False))
asyncio.run(main())
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("ddgun", "colabfold", "evcouplings"), required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--adapter-source", type=Path, required=True)
    parser.add_argument("--limits-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--container", default="docker-backend-1")
    args = parser.parse_args()
    values = dict(line.split("=", 1) for line in (BASE / "service.env").read_text().splitlines()
                  if "=" in line and not line.startswith("#"))
    payload = json.loads(args.request.read_text())
    data = {"model": args.model, "payload": payload, "token": values["MODEL_SERVICE_TOKEN"],
            "adapter_source": args.adapter_source.read_text(), "limits_source": args.limits_source.read_text()}
    process = subprocess.run(["docker", "exec", "-i", args.container, "python", "-c", CODE],
                             input=json.dumps(data), capture_output=True, text=True, timeout=7320)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    (args.output / "stderr.log").write_text(process.stderr)
    if process.returncode:
        raise SystemExit("Smoke failed; inspect private stderr.log")
    result = json.loads(process.stdout)
    output = args.output / "result.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    receipt = {"model": args.model, "status": result.get("status"),
               "verified_at": datetime.now(timezone.utc).isoformat(),
               "result_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
               "adapter_sha256": hashlib.sha256(args.adapter_source.read_bytes()).hexdigest(),
               "limits_sha256": hashlib.sha256(args.limits_source.read_bytes()).hexdigest(),
               "validation_scope": "public_input_engineering_smoke_only; no target-enzyme efficacy claim",
               "algorithm_commit": result.get("algorithm_commit"),
               "database_version": result.get("database_version")}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2))
    if result.get("status") != "completed":
        print(json.dumps(receipt))
        raise SystemExit(1)
    readiness = BASE / "runs/readiness"
    readiness.mkdir(mode=0o755, exist_ok=True)
    path = readiness / (args.model + ".json")
    path.write_text(json.dumps(receipt, indent=2))
    path.chmod(0o644)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
