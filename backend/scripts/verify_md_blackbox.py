#!/usr/bin/env python3
"""End-to-end black-box verifier for the live MD workflow.

Runs against the externally exposed HTTP service, not the in-process test app.
The verifier can either:

1. Create a fresh user, upload a PDB, analyze it, submit a new MD task, poll
   to terminal state, and verify artifact download behavior.
2. Resume an already-submitted task for a known user and only validate polling
   and artifact download behavior.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PDB = PROJECT_ROOT / "deploy_data" / "smoke" / "query.pdb"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-only", action="store_true", help="Validate required inputs without making HTTP requests or submitting a task")
    parser.add_argument("--require-inputs", action="store_true", help="With --plan-only, exit non-zero when live inputs are incomplete")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--base-url", default=os.getenv("FRONTEND_BASE_URL", "http://localhost:4200"), help="Externally reachable service base URL")
    parser.add_argument("--pdb-file", default=str(DEFAULT_PDB), help="PDB file used for upload when submitting a new task")
    parser.add_argument("--email", default=os.getenv("MD_BLACKBOX_EMAIL") or os.getenv("LIVE_AI_EMAIL"), help="Existing account email. Required with --task-id.")
    parser.add_argument(
        "--password",
        default=os.getenv("MD_BLACKBOX_PASSWORD") or os.getenv("LIVE_AI_PASSWORD") or "",
        help="Account password; must be supplied explicitly for live verification",
    )
    parser.add_argument("--name", default="MD Blackbox", help="Display name used when auto-registering")
    parser.add_argument("--task-id", default=os.getenv("MD_BLACKBOX_TASK_ID"), help="Resume an existing MD task instead of submitting a new one")
    parser.add_argument("--allow-submit", action="store_true", default=os.getenv("ALLOW_MD_BLACKBOX_SUBMIT", "").strip().lower() in {"1", "true", "yes", "on"}, help="Allow submitting a fresh MD task when task-id is not supplied")
    parser.add_argument("--poll-interval", type=float, default=10.0, help="Polling interval in seconds")
    parser.add_argument("--timeout-seconds", type=int, default=1800, help="Terminal-state wait timeout for MD polling")
    parser.add_argument("--output", help="Optional path to write JSON summary")
    return parser


def _plan_only(args: argparse.Namespace) -> int:
    missing = []
    if args.task_id:
        if not args.email:
            missing.append("--email or MD_BLACKBOX_EMAIL/LIVE_AI_EMAIL")
        if not (args.password or "").strip():
            missing.append("--password or MD_BLACKBOX_PASSWORD/LIVE_AI_PASSWORD")
    else:
        if not args.allow_submit:
            missing.append("--allow-submit or ALLOW_MD_BLACKBOX_SUBMIT=true")
        if not (args.password or "").strip():
            missing.append("--password or MD_BLACKBOX_PASSWORD/LIVE_AI_PASSWORD")
        if not Path(args.pdb_file).expanduser().exists():
            missing.append(f"PDB file: {args.pdb_file}")

    payload = {
        "summary": {
            "status": "blocked" if missing else "planned",
            "mode": "resume" if args.task_id else "submit",
            "missing_inputs": missing,
        },
        "base_url": args.base_url,
        "task_id": args.task_id,
        "pdb_file": args.pdb_file if not args.task_id else None,
        "planned_action": "poll existing task and verify artifact ownership" if args.task_id else "register/upload/submit/poll a fresh MD task",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
    }
    _write_output(payload, args.output)
    return 1 if args.require_inputs and missing else 0


def _make_fresh_credentials(name: str, password: str) -> Tuple[str, str, str]:
    email = f"md-blackbox-{uuid.uuid4().hex[:10]}@example.com"
    return email, password, name


def _write_output(summary: Dict[str, Any], output: Optional[str]) -> None:
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


def _register_or_login(
    client: Any,
    *,
    email: str,
    password: str,
    name: str,
    allow_login_fallback: bool,
) -> Dict[str, Any]:
    response = client.post("/api/auth/register", json={"email": email, "password": password, "name": name})
    if response.status_code == 201:
        payload = response.json()
        return {"mode": "register", "status": response.status_code, "user": payload.get("user")}
    if allow_login_fallback and response.status_code in {400, 409}:
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        response.raise_for_status()
        payload = response.json()
        return {"mode": "login", "status": response.status_code, "user": payload.get("user")}
    response.raise_for_status()
    raise AssertionError("Unreachable register/login branch")


def _upload_and_submit(
    client: Any,
    *,
    pdb_path: Path,
) -> Dict[str, Any]:
    if not pdb_path.exists():
        raise FileNotFoundError(f"PDB file not found: {pdb_path}")

    with pdb_path.open("rb") as handle:
        upload_response = client.post(
            "/api/files/upload",
            files={"file": (pdb_path.name, handle, "chemical/x-pdb")},
        )
    upload_response.raise_for_status()
    upload = upload_response.json()

    analyze_response = client.post("/api/pdb/analyze-by-name", json={"object_name": upload["object_name"]})
    analyze_response.raise_for_status()
    analysis = analyze_response.json()

    submit_response = client.post(
        "/api/tools/gromacs_md/submit",
        json={
            "params": {
                "pdb_object_name": upload["object_name"],
                "simulation_time_ns": 0.01,
                "equilibration_ps": 10.0,
                "ensemble": "nvt",
                "mdrun_threads": 1,
                "upload_artifacts": True,
            }
        },
    )
    submit_response.raise_for_status()
    submitted = submit_response.json()

    return {
        "upload": {
            "status": upload_response.status_code,
            "object_name": upload.get("object_name"),
            "download_url": upload.get("download_url"),
            "size": upload.get("size"),
        },
        "analysis": {
            "status": analyze_response.status_code,
            "total_residues": analysis.get("total_residues"),
            "total_atoms": analysis.get("total_atoms"),
            "chain_count": len(analysis.get("chains") or []),
        },
        "submit": {
            "status": submit_response.status_code,
            "task_id": submitted.get("task_id"),
            "tool": submitted.get("tool"),
        },
    }


def _poll_task(
    client: Any,
    *,
    task_id: str,
    poll_interval: float,
    timeout_seconds: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    deadline = time.time() + timeout_seconds
    history = []  # type: List[Dict[str, Any]]

    while time.time() < deadline:
        response = client.get(f"/api/tools/tasks/{task_id}")
        response.raise_for_status()
        body = response.json()
        entry = {
            "status": body.get("status"),
            "progress": body.get("progress"),
            "terminal_status": body.get("terminal_status"),
            "cancel_requested": body.get("cancel_requested"),
        }
        history.append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        if body.get("status") in {"completed", "failed", "canceled"}:
            return body, history
        time.sleep(poll_interval)

    raise TimeoutError(f"MD task {task_id} did not reach terminal state within {timeout_seconds}s")


def _extract_md_payload(task_body: Dict[str, Any]) -> Dict[str, Any]:
    result = task_body.get("result")
    if not isinstance(result, dict):
        return {}
    nested = result.get("result")
    if isinstance(nested, dict):
        return nested
    return result


def _select_downloadable_artifact(payload: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError("Completed MD task did not return artifacts")

    target = next(
        (
            artifact
            for artifact in artifacts
            if isinstance(artifact, dict) and artifact.get("name") == "rmsd.xvg"
        ),
        None,
    ) or next(
        (artifact for artifact in artifacts if isinstance(artifact, dict) and artifact.get("download_url")),
        None,
    )
    if not isinstance(target, dict):
        raise RuntimeError("No downloadable artifact found")
    return target


def _verify_artifact_download(client: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    target = _select_downloadable_artifact(payload)

    download_url = target.get("download_url")
    if not isinstance(download_url, str) or not download_url:
        raise RuntimeError("Artifact download_url missing")
    if "filename=" not in download_url:
        raise RuntimeError(f"Artifact download_url missing filename query: {download_url}")

    response = client.get(download_url)
    response.raise_for_status()

    return {
        "name": target.get("name"),
        "url": download_url,
        "status": response.status_code,
        "bytes": len(response.content),
        "content_type": response.headers.get("content-type"),
        "content_disposition": response.headers.get("content-disposition"),
        "body_prefix": response.text[:80],
    }


def _verify_artifact_access_denied(
    *,
    base_url: str,
    owner_download_url: str,
    password: str,
) -> Dict[str, Any]:
    intruder_email, intruder_password, intruder_name = _make_fresh_credentials("MD Intruder", password)
    with httpx.Client(base_url=base_url, timeout=120.0, follow_redirects=True) as intruder_client:
        auth = _register_or_login(
            intruder_client,
            email=intruder_email,
            password=intruder_password,
            name=intruder_name,
            allow_login_fallback=False,
        )
        response = intruder_client.get(owner_download_url)
    if response.status_code != 403:
        raise RuntimeError(
            f"Expected intruder artifact download to be rejected with 403, got {response.status_code}: {response.text[:200]}"
        )
    return {
        "email": intruder_email,
        "auth_mode": auth["mode"],
        "status": response.status_code,
        "detail": response.json().get("detail"),
    }


def main() -> int:
    args = _build_parser().parse_args()

    if args.plan_only:
        return _plan_only(args)

    if args.task_id and not args.email:
        print("--email is required with --task-id", file=sys.stderr)
        return 2
    if not args.task_id and not args.allow_submit:
        print("--allow-submit is required when submitting a fresh MD task", file=sys.stderr)
        return 2

    global httpx
    import httpx

    email = args.email
    password = args.password
    name = args.name
    allow_login_fallback = bool(args.task_id)
    if not email:
        email, password, name = _make_fresh_credentials(name, password)

    summary = {  # type: Dict[str, Any]
        "base_url": args.base_url,
        "email": email,
        "mode": "resume" if args.task_id else "submit",
        "pdb_file": args.pdb_file if not args.task_id else None,
    }

    with httpx.Client(base_url=args.base_url, timeout=120.0, follow_redirects=True) as client:
        summary["auth"] = _register_or_login(
            client,
            email=email,
            password=password,
            name=name,
            allow_login_fallback=allow_login_fallback,
        )

        task_id = args.task_id
        if not task_id:
            submission = _upload_and_submit(client, pdb_path=Path(args.pdb_file).expanduser())
            summary.update(submission)
            task_id = submission["submit"]["task_id"]

        assert task_id is not None
        summary["task_id"] = task_id

        try:
            terminal, history = _poll_task(
                client,
                task_id=task_id,
                poll_interval=args.poll_interval,
                timeout_seconds=args.timeout_seconds,
            )
        except TimeoutError as exc:
            summary["poll_history_tail"] = history[-10:] if "history" in locals() else []
            summary["terminal"] = {
                "status": "timeout_waiting_for_terminal_state",
                "error": str(exc),
                "terminal_status": None,
                "queue": None,
                "poll_count": len(history) if "history" in locals() else 0,
            }
            summary["resume_command"] = (
                "backend/.venv/bin/python backend/scripts/verify_md_blackbox.py "
                f"--base-url {args.base_url} --task-id {task_id} "
                f"--email {email} --password <redacted> --json"
            )
            summary["passwords_printed"] = False
            _write_output(summary, args.output)
            return 1
        summary["poll_history_tail"] = history[-10:]
        summary["terminal"] = {
            "status": terminal.get("status"),
            "error": terminal.get("error"),
            "terminal_status": terminal.get("terminal_status"),
            "queue": terminal.get("queue"),
            "poll_count": len(history),
        }

        payload = _extract_md_payload(terminal)
        summary["artifact_count"] = len(payload.get("artifacts") or []) if isinstance(payload.get("artifacts"), list) else 0
        summary["artifact_manifest_counts"] = payload.get("artifact_manifest", {}).get("counts") if isinstance(payload, dict) else None

        if terminal.get("status") != "completed":
            _write_output(summary, args.output)
            return 1

        summary["artifact_download"] = _verify_artifact_download(client, payload)
        summary["artifact_download_intruder"] = _verify_artifact_access_denied(
            base_url=args.base_url,
            owner_download_url=summary["artifact_download"]["url"],
            password=password,
        )

    _write_output(summary, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
