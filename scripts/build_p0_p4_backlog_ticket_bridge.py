#!/usr/bin/env python3
"""Build a read-only bridge from P0-P4 contracts to remaining backlog tickets."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATUS_EXPORT = PROJECT_ROOT / "docs" / "manuals" / "p0-p4-status-export.json"
DEFAULT_EXECUTION_TICKETS = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-execution-tickets.json"
DEFAULT_GO_NO_GO = PROJECT_ROOT / "docs" / "manuals" / "remaining-backlog-go-no-go-summary.json"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "docs" / "manuals" / "p0-p4-backlog-ticket-bridge.json"
DEFAULT_OUTPUT_MD = PROJECT_ROOT / "docs" / "manuals" / "p0-p4-backlog-ticket-bridge.md"


# This is deliberately explicit. A related runtime ticket must not be treated
# as resolving a scientific, wet-lab, or product-approval blocker by inference.
CONTRACT_TICKET_LINKS: dict[str, list[dict[str, Any]]] = {
    "specified_mutation_review": [
        {
            "ticket_id": "RB-002-gpu_gromacs_md_live",
            "relationship": "supporting_evidence_only",
            "covered_blockers": [],
            "notes": "MD artifacts can support review context, but do not close numbering, pocket, conservation, WT baseline, or experiment feedback.",
        },
        {
            "ticket_id": "RB-003-md_blackbox_live_e2e",
            "relationship": "supporting_evidence_only",
            "covered_blockers": [],
            "notes": "Black-box MD evidence remains computational support and cannot promote the review to experimental validation.",
        },
    ],
    "site_structure_function_mvp": [
        {
            "ticket_id": "RB-002-gpu_gromacs_md_live",
            "relationship": "direct_blocker_support",
            "covered_blockers": ["real ddG/packing/MD RMSF artifacts"],
            "notes": "Supports the MD-derived portion only; pocket/channel/interface and conservation remain separate blockers.",
        },
        {
            "ticket_id": "RB-003-md_blackbox_live_e2e",
            "relationship": "supporting_evidence_only",
            "covered_blockers": [],
            "notes": "Black-box MD execution does not replace validated structure-feature calculators.",
        },
    ],
    "multi_objective_candidate_table": [
        {
            "ticket_id": "RB-002-gpu_gromacs_md_live",
            "relationship": "supporting_evidence_only",
            "covered_blockers": [],
            "notes": "MD runtime evidence may inform ranking, but does not provide wet-lab validation or matched WT assay controls.",
        },
    ],
    "followup_review_routes": [
        {
            "ticket_id": "RB-003-md_blackbox_live_e2e",
            "relationship": "supporting_evidence_only",
            "covered_blockers": [],
            "notes": "A live MD result can be attached to a follow-up, but does not supply prior trace context or structured experiment feedback.",
        },
    ],
    "numbering_registry": [],
    "catalytic_mechanism_profile": [],
    "reaction_profile": [],
    "wt_baseline_registry": [
        {
            "ticket_id": "RB-002-gpu_gromacs_md_live",
            "relationship": "supporting_evidence_only",
            "covered_blockers": [],
            "notes": "WT PDB input is an MD prerequisite, not a same-batch WT assay baseline.",
        },
    ],
    "residue_feature_table_contract": [
        {
            "ticket_id": "RB-002-gpu_gromacs_md_live",
            "relationship": "direct_blocker_support",
            "covered_blockers": ["real ddG or MD RMSF artifacts"],
            "notes": "Supports MD-derived residue evidence only; conservation and pocket/tunnel calculations remain open.",
        },
        {
            "ticket_id": "RB-003-md_blackbox_live_e2e",
            "relationship": "supporting_evidence_only",
            "covered_blockers": [],
            "notes": "Black-box execution is not a validated pocket or conservation calculator.",
        },
    ],
    "objective_score_contract": [
        {
            "ticket_id": "RB-002-gpu_gromacs_md_live",
            "relationship": "supporting_evidence_only",
            "covered_blockers": [],
            "notes": "MD can add one computational objective signal, but does not close matched WT baseline or objective assay data.",
        },
    ],
    "candidate_table_generation_contract": [],
    "dbtl_trace_contract": [
        {
            "ticket_id": "RB-007-maintenance_window_drills",
            "relationship": "supporting_approval_only",
            "covered_blockers": [],
            "notes": "Maintenance-window evidence supports operational review, not product approval for a formal DBTL write model.",
        },
    ],
    "feedback_import_and_next_round_contract": [
        {
            "ticket_id": "RB-002-gpu_gromacs_md_live",
            "relationship": "supporting_evidence_only",
            "covered_blockers": [],
            "notes": "MD artifacts are not QC-passed replicated wet-lab feedback or formal Go/Watch/No-Go decisions.",
        },
    ],
    "industrial_closed_loop_readiness": [
        {
            "ticket_id": "RB-001-formal_domain_https",
            "relationship": "direct_blocker_support",
            "covered_blockers": ["maintenance window and live gate approval"],
            "notes": "Formal HTTPS and identity configuration is part of production gate readiness, but does not approve the gate.",
        },
        {
            "ticket_id": "RB-005-oss_minio_live_e2e",
            "relationship": "direct_blocker_support",
            "covered_blockers": ["maintenance window and live gate approval"],
            "notes": "Controlled storage round-trip supports operational readiness, but does not approve production learning policy.",
        },
        {
            "ticket_id": "RB-007-maintenance_window_drills",
            "relationship": "direct_blocker_support",
            "covered_blockers": ["maintenance window and live gate approval"],
            "notes": "This is the direct operator path for maintenance-window evidence; explicit approval remains required.",
        },
    ],
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _source(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": _relative(path),
        "sha256": _sha256(path),
        "created_at": payload.get("created_at"),
    }


def _ticket_index(tickets: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(ticket.get("ticket_id")): ticket
        for ticket in tickets.get("tickets") or []
        if isinstance(ticket, dict) and ticket.get("ticket_id")
    }


def _resolve_ticket(
    configured_ticket_id: str,
    ticket_index: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]] | None:
    ticket = ticket_index.get(configured_ticket_id)
    if ticket is not None:
        return configured_ticket_id, ticket

    # Ticket numbers are presentation-only and can change when a ready item is
    # removed. Resolve the stable item name after the RB-NNN prefix.
    stable_name = configured_ticket_id.split("-", 2)[-1]
    matches = [
        (ticket_id, candidate)
        for ticket_id, candidate in ticket_index.items()
        if str(candidate.get("name") or "") == stable_name
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _contract_row(contract: dict[str, Any], ticket_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    name = str(contract.get("contract_name") or "")
    blockers = [str(value) for value in contract.get("external_blockers") or []]
    configured = CONTRACT_TICKET_LINKS.get(name, [])
    links: list[dict[str, Any]] = []
    covered: list[str] = []
    for raw_link in configured:
        configured_ticket_id = str(raw_link.get("ticket_id") or "")
        resolved = _resolve_ticket(configured_ticket_id, ticket_index)
        if resolved is None:
            raise ValueError(f"{name} references missing ticket {configured_ticket_id}")
        ticket_id, ticket = resolved
        covered_blockers = [str(value) for value in raw_link.get("covered_blockers") or []]
        covered.extend(value for value in covered_blockers if value in blockers and value not in covered)
        links.append(
            {
                "ticket_id": ticket_id,
                "ticket_name": ticket.get("name"),
                "ticket_status": ticket.get("ticket_status"),
                "priority": ticket.get("priority"),
                "lane": ticket.get("lane"),
                "relationship": raw_link.get("relationship"),
                "covered_blockers": covered_blockers,
                "notes": raw_link.get("notes"),
            }
        )
    uncovered = [blocker for blocker in blockers if blocker not in covered]
    status = "linked" if links and not uncovered else "partially_linked" if links else "contract_followup_only"
    return {
        "phase": contract.get("phase"),
        "contract_name": name,
        "contract_status": contract.get("status"),
        "approval_required": contract.get("approval_required") is True,
        "approval_state": contract.get("approval_state"),
        "ticket_link_status": status,
        "ticket_links": links,
        "external_blockers": blockers,
        "covered_blockers": covered,
        "uncovered_blockers": uncovered,
        "local_followups": list(contract.get("local_followups") or []),
        "must_not_claim": list(contract.get("must_not_claim") or []),
    }


def build_bridge(
    status_export: dict[str, Any],
    execution_tickets: dict[str, Any],
    go_no_go: dict[str, Any],
    status_path: Path = DEFAULT_STATUS_EXPORT,
    tickets_path: Path = DEFAULT_EXECUTION_TICKETS,
    go_no_go_path: Path = DEFAULT_GO_NO_GO,
) -> dict[str, Any]:
    ticket_index = _ticket_index(execution_tickets)
    contracts = [
        _contract_row(contract, ticket_index)
        for contract in status_export.get("contract_status_items") or []
        if isinstance(contract, dict)
    ]
    known_contracts = {row["contract_name"] for row in contracts}
    unmapped_config = sorted(set(CONTRACT_TICKET_LINKS) - known_contracts)
    if unmapped_config:
        raise ValueError(f"bridge mapping contains unknown contracts: {', '.join(unmapped_config)}")

    ticket_to_contracts: dict[str, list[dict[str, Any]]] = {
        ticket_id: [] for ticket_id in ticket_index
    }
    for contract in contracts:
        for link in contract["ticket_links"]:
            ticket_to_contracts[link["ticket_id"]].append(
                {
                    "phase": contract["phase"],
                    "contract_name": contract["contract_name"],
                    "ticket_link_status": contract["ticket_link_status"],
                    "relationship": link["relationship"],
                    "covered_blockers": link["covered_blockers"],
                }
            )

    ticket_rows = []
    for ticket in execution_tickets.get("tickets") or []:
        if not isinstance(ticket, dict):
            continue
        ticket_id = str(ticket.get("ticket_id") or "")
        linked_contracts = ticket_to_contracts.get(ticket_id, [])
        ticket_rows.append(
            {
                "ticket_id": ticket_id,
                "name": ticket.get("name"),
                "priority": ticket.get("priority"),
                "lane": ticket.get("lane"),
                "ticket_status": ticket.get("ticket_status"),
                "linked_contracts": linked_contracts,
                "contract_impact_status": "linked_to_contracts" if linked_contracts else "operator_ticket_only",
            }
        )

    contract_counts = {
        "total": len(contracts),
        "linked": sum(row["ticket_link_status"] == "linked" for row in contracts),
        "partially_linked": sum(row["ticket_link_status"] == "partially_linked" for row in contracts),
        "contract_followup_only": sum(row["ticket_link_status"] == "contract_followup_only" for row in contracts),
    }
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "p0_p4_backlog_ticket_bridge_v1",
        "mode": "read_only_p0_p4_backlog_ticket_bridge",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "live_gate_execution_allowed": False,
        "source_status_export": _source(status_path, status_export),
        "source_execution_tickets": _source(tickets_path, execution_tickets),
        "source_go_no_go": _source(go_no_go_path, go_no_go),
        "go_no_go_decision": go_no_go.get("decision"),
        "ready_for_live_gate_execution": go_no_go.get("ready_for_live_gate_execution") is True,
        "contract_counts": contract_counts,
        "ticket_count": len(ticket_rows),
        "contracts": contracts,
        "tickets": ticket_rows,
        "bridge_contract": {
            "source_bound": True,
            "read_only": True,
            "linked_means_all_external_blockers_are_mapped": True,
            "partially_linked_keeps_uncovered_blockers": True,
            "contract_followup_only_means_no_operator_ticket_is_claimed_to_resolve_it": True,
            "ticket_links_are_explicit_not_keyword_inferred": True,
            "does_not_upgrade_contract_status": True,
        },
        "next_action": (
            "collect ticket inputs only for linked runtime/operations paths; keep contract-only blockers in P0-P4 review"
        ),
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# P0-P4 Backlog Ticket Bridge",
        "",
        f"- schema_version: `{payload['schema_version']}`",
        f"- go_no_go_decision: `{payload['go_no_go_decision']}`",
        f"- ready_for_live_gate_execution: `{payload['ready_for_live_gate_execution']}`",
        f"- contract_count: `{payload['contract_counts']['total']}`",
        f"- linked: `{payload['contract_counts']['linked']}`",
        f"- partially_linked: `{payload['contract_counts']['partially_linked']}`",
        f"- contract_followup_only: `{payload['contract_counts']['contract_followup_only']}`",
        "",
        "## Contract To Ticket",
        "",
        "| Phase | Contract | Status | Ticket Link Status | Tickets | Uncovered Blockers |",
        "|---|---|---|---|---|---|",
    ]
    for contract in payload["contracts"]:
        ticket_ids = ", ".join(link["ticket_id"] for link in contract["ticket_links"]) or "none"
        uncovered = "; ".join(contract["uncovered_blockers"]) or "none"
        lines.append(
            f"| `{contract['phase']}` | `{contract['contract_name']}` | `{contract['contract_status']}` | "
            f"`{contract['ticket_link_status']}` | `{ticket_ids}` | {uncovered} |"
        )
    lines.extend(["", "## Ticket To Contract", ""])
    for ticket in payload["tickets"]:
        lines.extend(
            [
                f"### {ticket['ticket_id']}",
                f"- Status: `{ticket['ticket_status']}`",
                f"- Contract impact: `{ticket['contract_impact_status']}`",
            ]
        )
        if ticket["linked_contracts"]:
            lines.append("- Contracts:")
            for link in ticket["linked_contracts"]:
                blockers = ", ".join(link["covered_blockers"]) or "none"
                lines.append(
                    f"  - `{link['phase']}/{link['contract_name']}`: `{link['relationship']}`, covered blockers: {blockers}"
                )
        else:
            lines.append("- No P0-P4 contract is claimed to be resolved by this ticket.")
        lines.append("")
    lines.extend(
        [
            "## Boundary",
            "",
            "- This bridge is read-only and does not execute live gates.",
            "- `ready_local_contract` remains distinct from live complete, wet-lab validated, or model retrained.",
            "- Uncovered blockers remain blockers even when a related operator ticket becomes ready.",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _comparable(payload: dict[str, Any]) -> dict[str, Any]:
    comparable = dict(payload)
    comparable.pop("created_at", None)
    return comparable


def check_bridge(
    output: Path,
    status_path: Path = DEFAULT_STATUS_EXPORT,
    tickets_path: Path = DEFAULT_EXECUTION_TICKETS,
    go_no_go_path: Path = DEFAULT_GO_NO_GO,
) -> tuple[bool, dict[str, Any]]:
    if not output.exists():
        return False, {"status": "stale-or-missing", "reason": "bridge_missing", "output": str(output)}
    try:
        existing = _load_json(output)
        current = build_bridge(
            _load_json(status_path),
            _load_json(tickets_path),
            _load_json(go_no_go_path),
            status_path,
            tickets_path,
            go_no_go_path,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return False, {"status": "stale-or-missing", "reason": "bridge_rebuild_failed", "error": str(exc), "output": str(output)}
    current_cmp = _comparable(current)
    existing_cmp = _comparable(existing)
    current_ok = existing_cmp == current_cmp
    return current_ok, {
        "status": "current" if current_ok else "stale-or-missing",
        "reason": None if current_ok else "bridge_differs_from_current_sources",
        "output": str(output),
        "contract_count": current["contract_counts"]["total"],
        "ticket_count": current["ticket_count"],
        "source_bound_current": current_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-export", default=str(DEFAULT_STATUS_EXPORT))
    parser.add_argument("--execution-tickets", default=str(DEFAULT_EXECUTION_TICKETS))
    parser.add_argument("--go-no-go", default=str(DEFAULT_GO_NO_GO))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    status_path = Path(args.status_export).expanduser().resolve()
    tickets_path = Path(args.execution_tickets).expanduser().resolve()
    go_no_go_path = Path(args.go_no_go).expanduser().resolve()
    output_json = Path(args.output_json).expanduser().resolve()
    output_md = Path(args.output_md).expanduser().resolve()
    if args.check:
        ok, response = check_bridge(output_json, status_path, tickets_path, go_no_go_path)
        print(json.dumps(response, ensure_ascii=False, sort_keys=True))
        return 0 if ok else 1

    payload = build_bridge(
        _load_json(status_path),
        _load_json(tickets_path),
        _load_json(go_no_go_path),
        status_path,
        tickets_path,
        go_no_go_path,
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(payload, output_md)
    response = {
        "status": "current",
        "contract_count": payload["contract_counts"]["total"],
        "ticket_count": payload["ticket_count"],
        "contract_counts": payload["contract_counts"],
        "output_json": str(output_json),
        "output_md": str(output_md),
        "network_io": payload["network_io"],
        "destructive_actions": payload["destructive_actions"],
        "secrets_printed": payload["secrets_printed"],
    }
    print(json.dumps(response, ensure_ascii=False, sort_keys=True) if args.json else f"summary\tcontracts={response['contract_count']}\ttickets={response['ticket_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
