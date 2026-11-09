#!/usr/bin/env python3
"""Read auth privately and verify host + existing backend connectivity."""
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base = Path("/opt/protein-ai-platform/model-services/thermostability")
values = dict(line.split("=", 1) for line in (base / "service.env").read_text().splitlines()
              if "=" in line and not line.startswith("#"))
url = "http://172.18.0.1:4270/health"
try:
    urlopen(url, timeout=5)
    raise RuntimeError("Unauthenticated model access must be rejected")
except HTTPError as exc:
    assert exc.code == 401
with urlopen(Request(url, headers={"Authorization": "Bearer " + values["MODEL_SERVICE_TOKEN"]}), timeout=5) as response:
    health = json.load(response)
code = """import json,sys,urllib.request
payload=json.load(sys.stdin)
request=urllib.request.Request(payload['url'],headers={'Authorization':'Bearer '+payload['token']})
with urllib.request.urlopen(request,timeout=5) as response:
 print(json.dumps({'status_code':response.status,'health':json.load(response)}))
"""
process = subprocess.run(["docker", "exec", "-i", "docker-backend-1", "python", "-c", code],
                         input=json.dumps({"url": url, "token": values["MODEL_SERVICE_TOKEN"]}),
                         capture_output=True, text=True, check=True)
print(json.dumps({"unauthenticated_status": 401, "host_health": health,
                  "backend_connectivity": json.loads(process.stdout)}, sort_keys=True))
