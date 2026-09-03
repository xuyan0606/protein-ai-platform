"""Conservative epistasis risk check before combining mutations."""

from __future__ import annotations

import itertools
import re
from typing import Any

from app.tools.registry import ToolRegistry


MUT_RE = re.compile(r"^([A-Z])([0-9]+)([A-Z])$")


def _position(code: str) -> int | None:
    match = MUT_RE.match(str(code).strip().upper())
    return int(match.group(2)) if match else None


def _pair_key(a: str, b: str) -> str:
    return ":".join(sorted([a.upper(), b.upper()]))


def _mutation_position_pair_key(a: str, b: str) -> str | None:
    pos_a = _position(a)
    pos_b = _position(b)
    if pos_a is None or pos_b is None:
        return None
    return ":".join(sorted([str(pos_a), str(pos_b)]))


def _graph_distance_lookup(residue_distance_graph: dict[str, Any] | None) -> dict[str, float]:
    if not isinstance(residue_distance_graph, dict):
        return {}
    lookup: dict[str, float] = {}
    for edge in residue_distance_graph.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        source = edge.get("source_position")
        target = edge.get("target_position")
        distance = edge.get("distance_ca_angstrom")
        if source is None or target is None or distance is None:
            continue
        try:
            distance_value = float(distance)
        except (TypeError, ValueError):
            continue
        key = ":".join(sorted([str(int(source)), str(int(target))]))
        lookup[key] = distance_value
    return lookup


def _pair_distance(
    a: str,
    b: str,
    *,
    structural_distances: dict[str, float],
    graph_distances: dict[str, float],
) -> tuple[float | None, str]:
    explicit = structural_distances.get(_pair_key(a, b))
    if explicit is not None:
        return explicit, "explicit_pairwise_distance_map"
    graph_key = _mutation_position_pair_key(a, b)
    if graph_key:
        graph_distance = graph_distances.get(graph_key)
        if graph_distance is not None:
            return graph_distance, "residue_distance_graph_v1"
    return None, "not_available"


def _report_contract(
    *,
    has_mechanism_tags: bool,
    has_structural_distances: bool,
    has_residue_distance_graph: bool,
    has_same_region_groups: bool,
    has_single_mutant_feedback: bool,
    missing_evidence: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "mutation_epistasis_check_report_contract_v1",
        "evidence_inputs": {
            "mechanism_tags": "provided" if has_mechanism_tags else "missing",
            "structural_distances": "provided" if has_structural_distances else "missing",
            "residue_distance_graph": "provided" if has_residue_distance_graph else "missing",
            "same_region_groups": "provided" if has_same_region_groups else "missing",
            "single_mutant_feedback": "provided" if has_single_mutant_feedback else "missing",
        },
        "distance_source_priority": [
            "explicit_pairwise_distance_map",
            "residue_distance_graph_v1",
            "sequence_gap_fallback",
        ],
        "required_missing_evidence": missing_evidence,
        "must_not_claim": [
            "trained_epistasis_model",
            "validated_combination_effect",
            "higher_order_combination_safety",
            "pocket_channel_interface_assignment_from_ca_distance",
        ],
        "boundary": (
            "This check is a conservative rule-based combination risk screen. It can use explicit pairwise "
            "distances or residue_distance_graph_v1 CA edges, but it does not train an epistasis model, "
            "prove combination benefit, or identify pockets/channels/interfaces."
        ),
    }


def _phenotype_status(feedback: dict[str, Any] | None) -> str:
    if not feedback:
        return "unknown"
    decision = feedback.get("decision") or feedback.get("status")
    if decision in {"go", "positive", "validated"}:
        return "go"
    if decision in {"no_go", "negative", "failed"}:
        return "no_go"
    metrics = feedback.get("metrics") or {}
    activity = metrics.get("activity_retention_pct")
    tm_delta = metrics.get("tm_delta_c")
    try:
        if activity is not None and float(activity) < 50:
            return "no_go"
        if tm_delta is not None and float(tm_delta) <= -2:
            return "watch"
    except (TypeError, ValueError):
        pass
    return "watch"


async def mutation_epistasis_check(
    mutations: list[str],
    mechanism_tags: dict[str, list[str]] | None = None,
    structural_distances: dict[str, float] | None = None,
    residue_distance_graph: dict[str, Any] | None = None,
    same_region_groups: list[list[str]] | None = None,
    single_mutant_feedback: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assess whether single mutations are safe to combine."""
    normalized = [str(item).strip().upper() for item in mutations or [] if str(item).strip()]
    if len(normalized) < 2:
        return {
            "status": "blocked",
            "blocked_reason": "need_at_least_two_mutations",
            "required_inputs": ["mutations"],
            "report_contract": _report_contract(
                has_mechanism_tags=False,
                has_structural_distances=False,
                has_residue_distance_graph=False,
                has_same_region_groups=False,
                has_single_mutant_feedback=False,
                missing_evidence=["mutations"],
            ),
        }

    mechanism_tags = mechanism_tags or {}
    structural_distances = structural_distances or {}
    single_mutant_feedback = single_mutant_feedback or {}
    graph_distances = _graph_distance_lookup(residue_distance_graph)
    has_mechanism_tags = bool(mechanism_tags)
    has_structural_distances = bool(structural_distances)
    has_residue_distance_graph = bool(graph_distances)
    has_same_region_groups = bool(same_region_groups)
    has_single_mutant_feedback = bool(single_mutant_feedback)
    region_lookup: dict[str, str] = {}
    for idx, group in enumerate(same_region_groups or [], start=1):
        for mutation in group:
            region_lookup[str(mutation).strip().upper()] = f"region_{idx}"

    pairwise: list[dict[str, Any]] = []
    total_score = 0
    blockers: list[str] = []
    warnings: list[str] = []

    for a, b in itertools.combinations(normalized, 2):
        reasons: list[str] = []
        score = 0
        distance, distance_source = _pair_distance(
            a,
            b,
            structural_distances=structural_distances,
            graph_distances=graph_distances,
        )
        pos_a = _position(a)
        pos_b = _position(b)

        if distance is None and pos_a is not None and pos_b is not None:
            sequence_gap = abs(pos_a - pos_b)
            if sequence_gap <= 5:
                score += 3
                reasons.append("nearby_in_sequence_without_structure_distance")
        elif distance is not None:
            if distance < 5:
                score += 5
                reasons.append("too_close_may_erase_local_effect_or_destabilize")
            elif distance < 10:
                score += 2
                reasons.append("same_local_neighborhood")

        if region_lookup.get(a) and region_lookup.get(a) == region_lookup.get(b):
            score += 3
            reasons.append("same_region_or_pocket")

        tags_a = set(mechanism_tags.get(a) or [])
        tags_b = set(mechanism_tags.get(b) or [])
        overlap = sorted(tags_a & tags_b)
        if overlap:
            score += 2
            reasons.append(f"shared_mechanism:{','.join(overlap)}")
        if "charge_change" in tags_a and "charge_change" in tags_b:
            score += 2
            reasons.append("repeated_charge_change")
        if "loop_rigidification" in tags_a and "loop_rigidification" in tags_b:
            score += 2
            reasons.append("repeated_loop_rigidification")

        status_a = _phenotype_status(single_mutant_feedback.get(a))
        status_b = _phenotype_status(single_mutant_feedback.get(b))
        if "no_go" in {status_a, status_b}:
            score += 6
            reasons.append("single_mutant_no_go")
        elif "unknown" in {status_a, status_b}:
            score += 1
            reasons.append("missing_single_mutant_feedback")

        if score >= 7:
            risk = "high"
            blockers.append(f"{a}+{b}")
        elif score >= 3:
            risk = "medium"
            warnings.append(f"{a}+{b}")
        else:
            risk = "low"

        total_score += score
        pairwise.append({
            "pair": [a, b],
            "risk": risk,
            "score": score,
            "distance_angstrom": distance,
            "distance_source": distance_source,
            "reasons": reasons or ["orthogonal_by_available_evidence"],
        })

    high_count = sum(1 for item in pairwise if item["risk"] == "high")
    medium_count = sum(1 for item in pairwise if item["risk"] == "medium")
    if high_count:
        recommendation = "no_go"
    elif medium_count:
        recommendation = "watch"
    else:
        recommendation = "go"

    gradient_plan = []
    if recommendation == "go":
        gradient_plan.append({"step": 1, "variant": "+".join(normalized), "purpose": "direct_combination_validation"})
    else:
        go_single = [
            mutation for mutation in normalized
            if _phenotype_status(single_mutant_feedback.get(mutation)) == "go"
        ]
        if go_single:
            gradient_plan.append({"step": 1, "variant": go_single[0], "purpose": "validated_parent"})
        gradient_plan.append({"step": 2, "variant": "pairwise_subset", "purpose": "test lowest-risk pairs before higher-order combination"})

    required_missing_evidence = [
        item for item in [
            "pairwise_structural_distances" if any(row["distance_angstrom"] is None for row in pairwise) else None,
            "single_mutant_feedback" if any("missing_single_mutant_feedback" in row["reasons"] for row in pairwise) else None,
        ]
        if item
    ]

    return {
        "status": "ok",
        "recommendation": recommendation,
        "mutations": normalized,
        "pairwise_risks": pairwise,
        "summary": {
            "high_risk_pairs": high_count,
            "medium_risk_pairs": medium_count,
            "risk_score_total": total_score,
            "blocked_pairs": blockers,
            "watch_pairs": warnings,
        },
        "gradient_experiment_plan": gradient_plan,
        "required_missing_evidence": required_missing_evidence,
        "report_contract": _report_contract(
            has_mechanism_tags=has_mechanism_tags,
            has_structural_distances=has_structural_distances,
            has_residue_distance_graph=has_residue_distance_graph,
            has_same_region_groups=has_same_region_groups,
            has_single_mutant_feedback=has_single_mutant_feedback,
            missing_evidence=required_missing_evidence,
        ),
    }


ToolRegistry.register(
    name="mutation_epistasis_check",
    description=(
        "Check epistasis and combination risk before merging validated single mutations. "
        "Flags same-pocket, close-distance, repeated mechanism, repeated charge/loop changes, "
        "and single-mutant No-Go evidence. Use before proposing multi-mutant constructs."
    ),
    parameters={
        "type": "object",
        "properties": {
            "mutations": {"type": "array", "items": {"type": "string"}},
            "mechanism_tags": {
                "type": "object",
                "description": "Mapping mutation -> tags such as charge_change, loop_rigidification, activity_gain, stability_gain.",
            },
        "structural_distances": {
            "type": "object",
            "description": "Mapping pair key like A10V:D55N -> C-alpha distance in Angstrom.",
        },
        "residue_distance_graph": {
            "type": "object",
            "description": "Optional residue_distance_graph_v1 payload with CA edge list; used to derive pair distances when explicit pairwise distances are absent.",
        },
        "same_region_groups": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
            "description": "Groups of mutations in the same pocket/loop/function surface.",
        },
            "single_mutant_feedback": {
                "type": "object",
                "description": "Mapping mutation -> wet-lab interpretation with decision/status and optional metrics.",
            },
        },
        "required": ["mutations"],
    },
    handler=mutation_epistasis_check,
    category="engineering",
    timeout_seconds=30,
)
