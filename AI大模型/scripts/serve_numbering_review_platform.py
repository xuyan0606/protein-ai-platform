#!/usr/bin/env python3
"""Serve the local numbering review platform with button-driven actions.

This server is intentionally narrow: it can save a reviewed numbering decision
row and run a small allowlist of local validation/apply pipeline commands.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


AI_ROOT = Path(__file__).resolve().parents[1]
DECISIONS = AI_ROOT / "datasets" / "curation" / "numbering_curation_decisions.jsonl"
SEMANTIC_CONFLICTS = AI_ROOT / "datasets" / "curation" / "numbering_decision_semantic_conflict_queue.jsonl"
OPERATOR_QUEUE_REPORT = AI_ROOT / "reports" / "numbering_review_operator_queue.json"
PIPELINE_JOB_LEDGER = AI_ROOT / "reports" / "numbering_review_pipeline_jobs.jsonl"
WET_LAB_WORKLIST = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorization_worklist.jsonl"
WET_LAB_AUTHORIZATIONS = AI_ROOT / "datasets" / "feedback" / "wet_lab_mutant_library_feedback_authorizations.jsonl"
STRICT_REVIEW_PACKETS = AI_ROOT / "datasets" / "curation" / "kwb_venus15b_strict_holdout_review_packets.jsonl"
STRICT_REVIEW_DECISIONS = AI_ROOT / "datasets" / "curation" / "kwb_venus15b_strict_holdout_review_decisions.jsonl"
SUBSTRATE_REVIEW_PACKETS = AI_ROOT / "datasets" / "curation" / "substrate_identity_review_packets.jsonl"
SUBSTRATE_REVIEW_DECISIONS = AI_ROOT / "datasets" / "curation" / "substrate_identity_review_decisions.jsonl"
ASYNC_STEPS = {"safe_pipeline"}
RUNS: dict[str, dict[str, Any]] = {}
RUN_LOCK = threading.Lock()
DECISION_LOCK = threading.Lock()
PIPELINE_QUEUE: queue.Queue[str] = queue.Queue()
PIPELINE_WORKER: threading.Thread | None = None
PIPELINE_LEDGER_LOCK = threading.Lock()

COMMANDS = {
    "build_hard_gate_review_packets": ["python3", "scripts/build_hard_gate_review_packets.py"],
    "build_semantic_conflicts": ["python3", "scripts/build_numbering_decision_semantic_conflict_queue.py"],
    "build_operator_queue": ["python3", "scripts/build_numbering_review_operator_queue.py"],
    "refresh_numbering_review_data": ["python3", "scripts/refresh_numbering_review_data.py"],
    "validate_numbering": ["python3", "scripts/validate_numbering_curation_decisions.py"],
    "apply_numbering": ["python3", "scripts/apply_numbering_curation.py"],
    "safe_pipeline": ["python3", "scripts/run_safe_training_pipeline.py"],
    "validate_hard_gate_reviews": ["python3", "scripts/validate_hard_gate_review_packets.py"],
    "build_hard_gate_bridge": ["python3", "scripts/build_hard_gate_decision_benchmark_bridge.py"],
    "validate_hard_gate_bridge": ["python3", "scripts/validate_hard_gate_decision_benchmark_bridge.py"],
    "apply_benchmark_score_cache": ["python3", "scripts/apply_benchmark_score_cache_intake.py"],
    "validate_benchmark_score_cache": ["python3", "scripts/validate_benchmark_score_cache.py"],
}

WET_LAB_COMMANDS = {
    "validate_wet_lab_authorizations": [
        "python3",
        "scripts/validate_wet_lab_mutant_library_feedback_authorizations.py",
    ],
    "build_wet_lab_preflight": [
        "python3",
        "scripts/build_wet_lab_mutant_library_feedback_preflight.py",
    ],
    "build_wet_lab_apply_plan": [
        "python3",
        "scripts/build_wet_lab_mutant_library_feedback_intake_apply_plan.py",
    ],
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def json_response(handler: SimpleHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    try:
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except BrokenPipeError:
        # Browsers may cancel a request while switching records; do not log a traceback.
        return


def read_json_body(handler: SimpleHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    return json.loads(raw or "{}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def get_run_status(run_id: str) -> dict[str, Any] | None:
    with RUN_LOCK:
        run = RUNS.get(run_id)
        return dict(run) if run else None


def persist_pipeline_run(run: dict[str, Any]) -> None:
    with PIPELINE_LEDGER_LOCK:
        rows = [row for row in load_jsonl(PIPELINE_JOB_LEDGER) if row.get("run_id") != run.get("run_id")]
        rows.append(dict(run))
        write_jsonl(PIPELINE_JOB_LEDGER, rows)


def restore_pipeline_runs() -> None:
    pending: list[str] = []
    for run in load_jsonl(PIPELINE_JOB_LEDGER):
        if run.get("status") == "running":
            run = {**run, "status": "queued", "started_at": None, "finished_at": None}
        run_id = str(run.get("run_id") or "")
        if not run_id:
            continue
        with RUN_LOCK:
            RUNS[run_id] = run
        if run.get("step") == "safe_pipeline" and run.get("status") == "queued":
            PIPELINE_QUEUE.put(run_id)
            persist_pipeline_run(run)
            pending.append(run_id)
    if pending:
        start_pipeline_worker()


def save_decision(row: dict[str, Any]) -> dict[str, Any]:
    record_id = row.get("record_id")
    if not record_id:
        raise ValueError("missing record_id")
    expected_submission_id = row.get("expected_submission_id")
    saved_row = {
        **{key: value for key, value in row.items() if key != "expected_submission_id"},
        "submission_id": str(row.get("submission_id") or uuid.uuid4().hex),
        "submitted_at": now_iso(),
    }
    with DECISION_LOCK:
        rows = load_jsonl(DECISIONS)
        replaced = False
        output_rows: list[dict[str, Any]] = []
        for existing in rows:
            if existing.get("record_id") == record_id:
                existing_submission_id = existing.get("submission_id")
                if existing_submission_id and expected_submission_id != existing_submission_id:
                    raise ValueError(
                        f"decision_conflict: {record_id} was updated by another reviewer; refresh before resubmitting"
                    )
                output_rows.append(saved_row)
                replaced = True
            else:
                output_rows.append(existing)
        if not replaced:
            output_rows.append(saved_row)
        write_jsonl(DECISIONS, output_rows)
    return {
        "record_id": record_id,
        "replaced_existing_row": replaced,
        "decision_rows": len(output_rows),
        "decision_file": display_path(DECISIONS),
        "submission_id": saved_row["submission_id"],
        "submitted_at": saved_row["submitted_at"],
    }


def resolve_semantic_conflict(record_id: str, action: str, curator: str | None = None, notes: str | None = None) -> dict[str, Any]:
    if not record_id:
        raise ValueError("missing record_id")
    if action not in {"convert_to_reject_label", "confirm_keep_unresolved_weak"}:
        raise ValueError("unknown semantic conflict resolution action")
    with DECISION_LOCK:
        rows = load_jsonl(DECISIONS)
        conflicts = {str(row.get("record_id")): row for row in load_jsonl(SEMANTIC_CONFLICTS)}
        if record_id not in conflicts:
            raise ValueError(f"record_id is not in semantic conflict queue: {record_id}")

        output_rows: list[dict[str, Any]] = []
        updated: dict[str, Any] | None = None
        for existing in rows:
            if existing.get("record_id") != record_id:
                output_rows.append(existing)
                continue
            previous = dict(existing)
            updated = dict(existing)
            if action == "convert_to_reject_label":
                updated.update({
                "decision": "reject_label",
                "canonical_position": None,
                "canonical_wild_type": None,
                "mapping_basis": "unresolved",
                "confidence": 0,
                "notes": notes or (
                    f"已人工确认语义冲突：原 notes 已说明该来源不能支持 {record_id} 标签。"
                    "机器字段同步修正为 reject_label，拒绝该标签，不进入训练。"
                ),
                })
            else:
                updated.update({
                "decision": "keep_unresolved_weak",
                "mapping_basis": "unresolved",
                "confidence": 0,
                "notes": notes or (
                    f"已人工确认语义冲突：{record_id} 暂不作为 reject_label，"
                    "仅保留为 unresolved weak evidence，不进入强监督训练；后续如有真实来源回执再复核。"
                ),
                })
            updated["curator"] = curator or updated.get("curator") or "keweibo"
            updated["semantic_conflict_resolution"] = {
            "resolved_by_button": True,
            "resolution_action": action,
            "previous_decision": previous.get("decision"),
            "previous_notes": previous.get("notes"),
            "conflict_type": conflicts[record_id].get("conflict_type"),
            }
            output_rows.append(updated)

        if updated is None:
            raise ValueError(f"record_id not found in decision file: {record_id}")
        write_jsonl(DECISIONS, output_rows)
    return {
        "record_id": record_id,
        "resolution_action": action,
        "decision": updated.get("decision"),
        "decision_rows": len(output_rows),
        "decision_file": display_path(DECISIONS),
    }


def save_wet_lab_authorization(row: dict[str, Any]) -> dict[str, Any]:
    candidate_id = row.get("feedback_candidate_id")
    authorization_id = row.get("authorization_id")
    if not candidate_id or not authorization_id:
        raise ValueError("missing feedback_candidate_id or authorization_id")
    rows = load_jsonl(WET_LAB_AUTHORIZATIONS)
    replaced = False
    output_rows: list[dict[str, Any]] = []
    for existing in rows:
        if existing.get("feedback_candidate_id") == candidate_id or existing.get("authorization_id") == authorization_id:
            output_rows.append(row)
            replaced = True
        else:
            output_rows.append(existing)
    if not replaced:
        output_rows.append(row)
    write_jsonl(WET_LAB_AUTHORIZATIONS, output_rows)
    return {
        "feedback_candidate_id": candidate_id,
        "authorization_id": authorization_id,
        "replaced_existing_row": replaced,
        "authorization_rows": len(output_rows),
        "authorization_file": str(WET_LAB_AUTHORIZATIONS.relative_to(AI_ROOT)),
    }


def save_hard_gate_decision(kind: str, row: dict[str, Any]) -> dict[str, Any]:
    targets = {
        "strict": (STRICT_REVIEW_DECISIONS, "review_key"),
        "substrate": (SUBSTRATE_REVIEW_DECISIONS, "review_key"),
    }
    if kind not in targets:
        raise ValueError("unknown hard-gate review kind")
    path, key_field = targets[kind]
    key = str(row.get(key_field) or "")
    if not key:
        raise ValueError("missing review_key")
    if row.get("decision") not in {
        "approve_strict_holdout", "reject_candidate", "approve_reviewed_substrate_identity",
        "reject_substrate_identity", "needs_more_info",
    }:
        raise ValueError("invalid hard-gate decision")
    decision = row.get("decision")
    if decision == "approve_strict_holdout":
        required = [
            "source_evidence_confirmed", "numbering_confirmed", "wetlab_result_confirmed",
            "leakage_check_passed", "acceptance_receipt", "review_basis", "reviewer", "reviewed_at",
        ]
        missing = [field for field in required if row.get(field) in (None, "", False)]
        if missing or row.get("approved_label") not in {"go", "watch"}:
            raise ValueError(f"strict approval requires evidence checks, label, reviewer, time, basis and receipt: {missing}")
    if decision == "approve_reviewed_substrate_identity":
        required = [
            "identity_confirmed", "scope_confirmed", "condition_confirmed", "protocol_version_confirmed",
            "representation_type", "acceptance_receipt", "review_basis", "reviewer", "reviewed_at",
        ]
        missing = [field for field in required if row.get(field) in (None, "", False)]
        if missing or row.get("representation_type") not in {"single_compound", "process_mixture", "defined_substrate_set"}:
            raise ValueError(f"substrate approval requires identity checks, representation, reviewer, time, basis and receipt: {missing}")
        if row.get("representation_type") == "process_mixture" and row.get("substrate_smiles"):
            raise ValueError("process mixture cannot carry an inferred single-molecule SMILES")
    rows = load_jsonl(path)
    replaced = False
    output = []
    for existing in rows:
        if str(existing.get(key_field) or "") == key:
            output.append(row)
            replaced = True
        else:
            output.append(existing)
    if not replaced:
        output.append(row)
    write_jsonl(path, output)
    return {"kind": kind, "review_key": key, "replaced_existing_row": replaced, "decision_rows": len(output), "decision_file": str(path.relative_to(AI_ROOT))}


def run_step(step: str) -> dict[str, Any]:
    command = COMMANDS.get(step)
    if not command:
        raise ValueError(f"unknown step: {step}")
    process = subprocess.run(
        command,
        cwd=AI_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=600,
    )
    return {
        "step": step,
        "command": " ".join(command),
        "returncode": process.returncode,
        "ok": process.returncode == 0,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
    }


def start_run_step(step: str) -> dict[str, Any]:
    command = COMMANDS.get(step)
    if not command:
        raise ValueError(f"unknown step: {step}")
    run_id = uuid.uuid4().hex
    initial = {
        "run_id": run_id,
        "step": step,
        "command": " ".join(command),
        "status": "queued",
        "ok": True,
        "started_at": None,
        "finished_at": None,
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "queue_position": PIPELINE_QUEUE.qsize() + 1 if step == "safe_pipeline" else None,
    }
    with RUN_LOCK:
        RUNS[run_id] = initial

    if step == "safe_pipeline":
        persist_pipeline_run(initial)
        PIPELINE_QUEUE.put(run_id)
        start_pipeline_worker()
        return {**initial, "status": "queued", "async": True}

    def worker() -> None:
        with RUN_LOCK:
            RUNS[run_id] = {**RUNS[run_id], "status": "running", "started_at": now_iso()}
        try:
            result = run_step(step)
            status = "succeeded" if result["ok"] else "failed"
            with RUN_LOCK:
                RUNS[run_id] = {
                    **RUNS[run_id],
                    **result,
                    "status": status,
                    "finished_at": now_iso(),
                }
        except Exception as exc:
            with RUN_LOCK:
                RUNS[run_id] = {
                    **RUNS[run_id],
                    "status": "failed",
                    "ok": False,
                    "finished_at": now_iso(),
                    "returncode": 1,
                    "stderr": str(exc),
                }

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return {**initial, "status": "queued", "async": True}


def start_pipeline_worker() -> None:
    global PIPELINE_WORKER
    with RUN_LOCK:
        if PIPELINE_WORKER and PIPELINE_WORKER.is_alive():
            return
        PIPELINE_WORKER = threading.Thread(target=run_pipeline_queue, daemon=True)
        PIPELINE_WORKER.start()


def run_pipeline_queue() -> None:
    while True:
        run_id = PIPELINE_QUEUE.get()
        try:
            with RUN_LOCK:
                RUNS[run_id] = {**RUNS[run_id], "status": "running", "started_at": now_iso()}
            persist_pipeline_run(get_run_status(run_id) or {})
            result = run_step("safe_pipeline")
            status = "succeeded" if result["ok"] else "failed"
            with RUN_LOCK:
                RUNS[run_id] = {
                    **RUNS[run_id],
                    **result,
                    "status": status,
                    "finished_at": now_iso(),
                }
            persist_pipeline_run(get_run_status(run_id) or {})
        except Exception as exc:
            with RUN_LOCK:
                RUNS[run_id] = {
                    **RUNS[run_id],
                    "status": "failed",
                    "ok": False,
                    "finished_at": now_iso(),
                    "returncode": 1,
                    "stderr": str(exc),
                }
            persist_pipeline_run(get_run_status(run_id) or {})
        finally:
            PIPELINE_QUEUE.task_done()


def run_wet_lab_step(step: str) -> dict[str, Any]:
    command = WET_LAB_COMMANDS.get(step)
    if not command:
        raise ValueError(f"unknown wet-lab step: {step}")
    process = subprocess.run(
        command,
        cwd=AI_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=600,
    )
    return {
        "step": step,
        "command": " ".join(command),
        "returncode": process.returncode,
        "ok": process.returncode == 0,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(AI_ROOT), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/status":
            decisions = load_jsonl(DECISIONS)
            semantic_conflicts = load_jsonl(SEMANTIC_CONFLICTS)
            operator_queue = load_json(OPERATOR_QUEUE_REPORT)
            json_response(self, HTTPStatus.OK, {
                "ok": True,
                "mode": "numbering_review_platform",
                "local_only": True,
                "decision_rows": len(decisions),
                "semantic_conflict_rows": len(semantic_conflicts),
                "operator_queue_rows": operator_queue.get("queue_rows"),
                "open_numbering_rows": operator_queue.get("open_numbering_rows"),
                "semantic_conflict_generated_at": load_json(AI_ROOT / "reports" / "numbering_decision_semantic_conflict_report.json").get("created_at"),
                "operator_queue_generated_at": operator_queue.get("created_at"),
                "decision_file": str(DECISIONS.relative_to(AI_ROOT)),
                "allowed_steps": sorted(COMMANDS),
                "wet_lab_allowed_steps": sorted(WET_LAB_COMMANDS),
            })
            return
        if path == "/api/run-step-status":
            run_id = (parse_qs(parsed.query).get("id") or [""])[0]
            run = get_run_status(run_id)
            if not run:
                json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown run_id"})
                return
            json_response(self, HTTPStatus.OK, run)
            return
        if path == "/api/wet-lab/status":
            worklist = load_jsonl(WET_LAB_WORKLIST)
            decisions = load_jsonl(WET_LAB_AUTHORIZATIONS)
            decision_by_candidate = {
                str(row.get("feedback_candidate_id")): row for row in decisions
            }
            json_response(self, HTTPStatus.OK, {
                "ok": True,
                "mode": "wet_lab_authorization_review",
                "local_only": True,
                "worklist_rows": len(worklist),
                "authorization_rows": len(decisions),
                "authorized_rows": sum(
                    1 for row in decisions
                    if row.get("authorization_decision") == "approved_for_feedback_intake"
                ),
                "rows": [
                    {
                        **row,
                        "authorization": decision_by_candidate.get(str(row.get("feedback_candidate_id"))),
                    }
                    for row in worklist
                ],
                "authorization_file": str(WET_LAB_AUTHORIZATIONS.relative_to(AI_ROOT)),
                "allowed_steps": sorted(WET_LAB_COMMANDS),
                "policy": "Human authorization only; no automatic training import or model claim.",
            })
            return
        if path == "/api/hard-gate/status":
            strict_packets = load_jsonl(STRICT_REVIEW_PACKETS)
            substrate_packets = load_jsonl(SUBSTRATE_REVIEW_PACKETS)
            strict_decisions = {str(row.get("review_key")): row for row in load_jsonl(STRICT_REVIEW_DECISIONS)}
            substrate_decisions = {str(row.get("review_key")): row for row in load_jsonl(SUBSTRATE_REVIEW_DECISIONS)}
            bridge_report = load_json(AI_ROOT / "reports" / "hard_gate_decision_benchmark_bridge_report.json")
            bridge_validation = load_json(AI_ROOT / "reports" / "hard_gate_decision_benchmark_bridge_validation_report.json")
            benchmark_validation = load_json(AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json")
            pipeline_run = load_json(AI_ROOT / "reports" / "safe_training_pipeline_run.json")
            json_response(self, HTTPStatus.OK, {
                "ok": True,
                "mode": "hard_gate_review",
                "strict_packets": [{**row, "decision_row": strict_decisions.get(str(row.get("review_key")))} for row in strict_packets],
                "substrate_packets": [{**row, "decision_row": substrate_decisions.get(str(row.get("review_key")))} for row in substrate_packets],
                "strict_decision_rows": len(strict_decisions),
                "substrate_decision_rows": len(substrate_decisions),
                "strict_formal_approved_rows": bridge_report.get("strict_formal_approved_rows", 0),
                "substrate_formal_approved_rows": bridge_report.get("substrate_formal_approved_rows", 0),
                "bridge": bridge_report,
                "bridge_validation": bridge_validation,
                "benchmark_validation": benchmark_validation,
                "pipeline": {
                    "success": pipeline_run.get("success"),
                    "steps_run": pipeline_run.get("steps_run"),
                    "failed_steps": pipeline_run.get("failed_steps"),
                    "created_at": pipeline_run.get("created_at"),
                },
                "allowed_steps": sorted(COMMANDS),
                "policy": "Human review packet only; no automatic strict-row or substrate-fit training import.",
            })
            return
        super().do_GET()

    def do_POST(self) -> None:
        try:
            if self.path == "/api/save-numbering-decision":
                payload = read_json_body(self)
                result = save_decision(payload.get("decision") or {})
                json_response(self, HTTPStatus.OK, {"ok": True, **result})
                return
            if self.path == "/api/resolve-numbering-semantic-conflict":
                payload = read_json_body(self)
                result = resolve_semantic_conflict(
                    str(payload.get("record_id") or ""),
                    str(payload.get("action") or ""),
                    payload.get("curator"),
                    payload.get("notes"),
                )
                json_response(self, HTTPStatus.OK, {"ok": True, **result})
                return
            if self.path == "/api/run-step":
                payload = read_json_body(self)
                step = str(payload.get("step") or "")
                if payload.get("async") or step in ASYNC_STEPS:
                    result = start_run_step(step)
                    json_response(self, HTTPStatus.ACCEPTED, result)
                    return
                result = run_step(step)
                json_response(self, HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_REQUEST, {"ok": result["ok"], **result})
                return
            if self.path == "/api/save-wet-lab-authorization":
                payload = read_json_body(self)
                result = save_wet_lab_authorization(payload.get("authorization") or {})
                json_response(self, HTTPStatus.OK, {"ok": True, **result})
                return
            if self.path == "/api/save-hard-gate-decision":
                payload = read_json_body(self)
                result = save_hard_gate_decision(str(payload.get("kind") or ""), payload.get("decision") or {})
                json_response(self, HTTPStatus.OK, {"ok": True, **result})
                return
            if self.path == "/api/run-wet-lab-step":
                payload = read_json_body(self)
                result = run_wet_lab_step(str(payload.get("step") or ""))
                json_response(self, HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_REQUEST, {"ok": result["ok"], **result})
                return
            json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown endpoint"})
        except Exception as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve numbering review platform")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    restore_pipeline_runs()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving numbering review platform on http://{args.host}:{args.port}/")
    print("Open /ui/numbering_review/index.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping numbering review platform.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
