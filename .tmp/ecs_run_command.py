#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import shlex
import sys
import time
import urllib.parse
import urllib.request
import uuid


ECS_ENDPOINT = "https://ecs.aliyuncs.com/"
ECS_VERSION = "2014-05-26"


def _read_env(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _percent_encode(value: str) -> str:
    return urllib.parse.quote(value, safe="~")


def _signed_url(params: dict[str, str], access_key_id: str, access_key_secret: str) -> str:
    common = {
        "Format": "JSON",
        "Version": ECS_VERSION,
        "AccessKeyId": access_key_id,
        "SignatureMethod": "HMAC-SHA1",
        "Timestamp": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "SignatureVersion": "1.0",
        "SignatureNonce": str(uuid.uuid4()),
    }
    all_params = {**common, **params}
    canonicalized = "&".join(
        f"{_percent_encode(str(key))}={_percent_encode(str(all_params[key]))}"
        for key in sorted(all_params)
    )
    string_to_sign = "GET&%2F&" + _percent_encode(canonicalized)
    digest = hmac.new(
        (access_key_secret + "&").encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    signature = base64.b64encode(digest).decode("ascii")
    return ECS_ENDPOINT + "?" + canonicalized + "&Signature=" + _percent_encode(signature)


def _request(params: dict[str, str], access_key_id: str, access_key_secret: str) -> dict:
    url = _signed_url(params, access_key_id, access_key_secret)
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default="docker/.env.aliyun.app")
    parser.add_argument("--region", default="cn-qingdao")
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--poll-seconds", type=int, default=180)
    parser.add_argument("--command", default="")
    parser.add_argument("--append-public-key", default="")
    args = parser.parse_args()

    env_values = _read_env(args.env_file)
    access_key_id = env_values.get("ALIYUN_OSS_ACCESS_KEY_ID") or os.getenv("ALIYUN_OSS_ACCESS_KEY_ID", "")
    access_key_secret = env_values.get("ALIYUN_OSS_ACCESS_KEY_SECRET") or os.getenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "")
    if not access_key_id or not access_key_secret:
        print(json.dumps({"status": "blocked", "reason": "missing_access_key_env"}))
        return 2

    command = args.command or sys.stdin.read()
    if args.append_public_key:
        with open(os.path.expanduser(args.append_public_key), "r", encoding="utf-8") as handle:
            public_key = handle.read().strip()
        quoted_key = shlex.quote(public_key)
        command = f"""
set -eu
umask 077
mkdir -p /root/.ssh
touch /root/.ssh/authorized_keys
backup="/root/.ssh/authorized_keys.bak.codex-$(date -u +%Y%m%dT%H%M%SZ)"
cp -p /root/.ssh/authorized_keys "$backup"
key={quoted_key}
if grep -qxF "$key" /root/.ssh/authorized_keys; then
  changed=0
else
  printf '%s\\n' "$key" >> /root/.ssh/authorized_keys
  changed=1
fi
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
echo "changed=$changed"
echo "backup=$backup"
echo "authorized_keys_count=$(wc -l < /root/.ssh/authorized_keys | tr -d ' ')"
""".strip()
    if not command.strip():
        print(json.dumps({"status": "blocked", "reason": "empty_command"}))
        return 2

    encoded = base64.b64encode(command.encode("utf-8")).decode("ascii")
    run_result = _request(
        {
            "Action": "RunCommand",
            "RegionId": args.region,
            "Type": "RunShellScript",
            "CommandContent": encoded,
            "ContentEncoding": "Base64",
            "Timeout": str(args.timeout),
            "InstanceId.1": args.instance_id,
        },
        access_key_id,
        access_key_secret,
    )
    invoke_id = run_result.get("InvokeId")
    command_id = run_result.get("CommandId")
    if not invoke_id and not command_id:
        print(json.dumps({"status": "failed", "response": run_result}, ensure_ascii=False))
        return 1

    deadline = time.time() + args.poll_seconds
    last_payload: dict | None = None
    while time.time() < deadline:
        params = {
            "Action": "DescribeInvocationResults",
            "RegionId": args.region,
            "InstanceId": args.instance_id,
            "ContentEncoding": "PlainText",
        }
        if invoke_id:
            params["InvokeId"] = invoke_id
        elif command_id:
            params["CommandId"] = command_id
        last_payload = _request(params, access_key_id, access_key_secret)
        results = (((last_payload.get("Invocation") or {}).get("InvocationResults") or {}).get("InvocationResult") or [])
        if results:
            item = results[0]
            status = item.get("InvocationStatus") or item.get("Status")
            exit_code = item.get("ExitCode")
            if status in {"Finished", "Failed", "Stopped"} or exit_code not in (None, ""):
                print(json.dumps({
                    "status": "passed" if str(exit_code) == "0" else "failed",
                    "invocation_status": status,
                    "exit_code": exit_code,
                    "output": item.get("Output", ""),
                    "error_info": item.get("ErrorInfo", ""),
                }, ensure_ascii=False))
                return 0 if str(exit_code) == "0" else 1
        time.sleep(3)

    print(json.dumps({"status": "timeout", "last_response": last_payload}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
