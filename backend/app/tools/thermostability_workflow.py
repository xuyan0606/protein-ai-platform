"""One guarded workflow with optional scientific services and experimental handoff."""
from __future__ import annotations

import asyncio
import hashlib
import math
from typing import Any

from app.services.thermostability_workflow import build_screen
from app.services.thermostability_limits import tool_timeout
from app.tools.registry import ToolRegistry


def _finish(result: dict) -> dict:
    from app.services.thermostability_report import render_thermostability_report
    result["report_markdown"] = render_thermostability_report(result)
    return result


def _pareto_layers(rows: list[dict]) -> None:
    """Only compare complete, like-for-like score vectors; never add scales."""
    comparable = [r for r in rows if r["scores"]["ddgun"] is not None and r["scores"]["esm_preference"] is not None]
    def vector(row):
        return (row["scores"]["ddgun"]["ddg"], row["scores"]["esm_preference"]["score"])
    remaining = list(comparable)
    layer = 1
    while remaining:
        front = [r for r in remaining if not any(
            all(a >= b for a, b in zip(vector(other), vector(r)))
            and any(a > b for a, b in zip(vector(other), vector(r)))
            for other in remaining if other is not r)]
        for row in front:
            row["pareto_layer"] = layer
        remaining = [r for r in remaining if r not in front]
        layer += 1


async def thermostability_candidate_workflow(
    sequence: str, objective: dict | None = None, identity_profile: dict | None = None,
    objective_module_plan: dict | None = None, mutations: list[str] | None = None,
    candidate_sources: list[dict] | None = None, candidate_positions: list[int] | None = None,
    pdb_data: str = "", structure_source: str = "unknown", chain_id: str = "A",
    mapping_rows: list[dict] | None = None, protected_sites: list[dict] | None = None,
    assay_budget: int = 12, full_length_start: int | None = None,
    run_ddgun: bool = False, run_esm: bool = False, run_colabfold: bool = False,
    msa_policy: str = "local", run_coevolution: bool = False,
    msa_quality: dict | None = None, alignment: str = "",
    run_database_lookup: bool = False, uniprot_id: str = "",
    offline: bool = False, forbidden_tools: list[str] | None = None,
    analysis_mode: str = "strict",
    identity_reference_result: dict | None = None,
    prior_blast_tasks: list[dict] | None = None,
) -> dict[str, Any]:
    """Produce reviewed hypotheses; absence of an optional predictor is explicit."""
    from app.tools import thermostability_adapters as adapters

    requested = {"ddgun": run_ddgun, "esm": run_esm, "colabfold": run_colabfold, "coevolution": run_coevolution}
    forbidden = set(forbidden_tools or [])
    database_was_requested = run_database_lookup
    run_database_lookup = run_database_lookup and "get_stability_data" not in forbidden
    run_ddgun = run_ddgun and not offline and "ddgun_predict" not in forbidden
    run_esm = run_esm and not offline and "esm2_predict" not in forbidden
    run_colabfold = run_colabfold and not offline and "colabfold_predict" not in forbidden
    run_coevolution = run_coevolution and not offline and "evcouplings_analyze" not in forbidden

    sequence = "".join(sequence.split()).upper() if isinstance(sequence, str) else ""
    inputs = dict(sequence=sequence, objective=objective, identity_profile=identity_profile,
                  objective_module_plan=objective_module_plan, mutations=mutations,
                  candidate_sources=candidate_sources, candidate_positions=candidate_positions,
                  pdb_data=pdb_data, structure_source=structure_source, chain_id=chain_id,
                  mapping_rows=mapping_rows, protected_sites=protected_sites,
                  assay_budget=assay_budget, full_length_start=full_length_start, analysis_mode=analysis_mode,
                  identity_reference_result=identity_reference_result)
    result = build_screen(**inputs)
    branches = {key: {"status": "not_requested"} for key in ("database", "colabfold", "ddgun", "esm", "coevolution")}
    active = {"ddgun": run_ddgun, "esm": run_esm, "colabfold": run_colabfold, "coevolution": run_coevolution}
    for key, was_requested in requested.items():
        if was_requested and not active[key]:
            branches[key] = {"status": "skipped", "reason": "user_execution_constraint"}
    if database_was_requested and not run_database_lookup:
        branches["database"] = {"status": "skipped", "reason": "user_execution_constraint"}
    result["branches"] = branches
    if prior_blast_tasks:
        result['prior_blast_tasks'] = prior_blast_tasks
    if result["status"] in {"blocked", "needs_input"}:
        return _finish(result)
    exploring = result.get('analysis_mode') == 'exploration'
    if exploring and result.get('structure', {}).get('status') == 'mapped':
        from app.tools.site_structure_function_features import build_site_structure_function_features
        # Consume all rows in memory before any UI/checkpoint preview truncation.
        features = await build_site_structure_function_features(pdb_data=pdb_data, chain_id=chain_id)
        if features.get('status') == 'completed':
            inputs['structure_features'] = {**features, 'structure_sha256': hashlib.sha256(pdb_data.encode()).hexdigest()}
            result = build_screen(**inputs)
            result['branches'] = branches
            if prior_blast_tasks:
                result['prior_blast_tasks'] = prior_blast_tasks
            result['structure_feature_receipt'] = {'status': 'completed', 'rows_evaluated': len(features.get('features', [])),
                'structure_sha256': hashlib.sha256(pdb_data.encode()).hexdigest(), 'preview_used_for_selection': False}
    if run_database_lookup:
        from app.tools.data_lookup import get_stability_data
        try:
            data = await get_stability_data(uniprot_id)
        except Exception as exc:
            data = {"status": "blocked", "blocked_reason": f"local_database_unavailable:{type(exc).__name__}"}
        branches["database"] = data
        if data.get("found"):
            if data.get("protein_sequence_sha256") != result["sequence_sha256"]:
                branches["database"] = {**data, "status": "blocked", "blocked_reason": "database_target_sequence_mismatch"}
            else:
                sources = list(inputs.get("candidate_sources") or [])
                for record in data.get("records", []):
                    dtm = record.get("dtm")
                    # ΔΔG direction is unknown in this local schema. Only an
                    # explicit positive measured ΔTm proposes a substitution;
                    # assay/context transfer still requires manual review.
                    if isinstance(dtm, (int, float)) and not isinstance(dtm, bool) and math.isfinite(dtm) and dtm > 0:
                        sources.append({"kind": "local_experimental_dtm", "reference": record.get("literature_ref") or f"local:{uniprot_id}",
                                        "sequence_sha256": result["sequence_sha256"], "mutations": [record.get("mutation")]})
                inputs["candidate_sources"] = sources
                result = build_screen(**inputs)
                result["branches"] = branches
    if run_colabfold:
        if pdb_data:
            branches["colabfold"] = {"status": "skipped", "reason": "existing_mapped_structure_reused"}
        else:
            branches["colabfold"] = await adapters.colabfold_predict(sequence, msa_policy=msa_policy)
            predicted = branches["colabfold"]
            if predicted.get("status") == "completed":
                inputs.update(pdb_data=predicted["pdb_data"], structure_source="colabfold", chain_id=predicted["chain_id"])
                result = build_screen(**inputs)
                result["branches"] = branches
                if result["status"] == "blocked":
                    return _finish(result)
    rows = result.get('preliminary_candidates', []) if exploring else result["candidates"]
    if not rows:
        for key, enabled in active.items():
            if enabled and branches[key]['status'] == 'not_requested':
                branches[key] = {'status': 'not_run', 'reason': 'no_eligible_hypotheses'}
        return _finish(result)
    codes = [r["mutation"] for r in rows]
    if run_ddgun:
        # Sequence mode avoids treating input positions as PDB author numbers.
        # Direct DDGun3D remains available with its stricter numbering contract.
        branches["ddgun"] = await adapters.ddgun_predict(sequence, codes)
        prediction = branches["ddgun"]
        if prediction.get("status") == "completed":
            lookup = {r["mutation"]: r for r in prediction["predictions"]}
            for row in rows:
                raw = lookup[row["mutation"]]
                row["scores"]["ddgun"] = {**raw, "method": "DDGun_sequence",
                    "sequence_sha256": result["sequence_sha256"],
                    "algorithm_commit": prediction.get("algorithm_commit"),
                    "database_version": prediction.get("database_version")}
    if run_esm:
        valid = False
        try:
            from app.tools.esm2_predict import esm2_predict
            scored = await asyncio.to_thread(esm2_predict, sequence, codes)
            esm_rows = scored.get("mutations") if isinstance(scored, dict) else None
            valid = (isinstance(scored, dict) and scored.get("is_real_inference") is True
                     and scored.get("is_thermostability_prediction") is False
                     and scored.get("scoring_strategy") == "wild_type_marginal"
                     and isinstance(scored.get("model"), str) and bool(scored["model"].strip())
                     and isinstance(esm_rows, list) and len(esm_rows) == len(codes)
                     and all(isinstance(r, dict) and isinstance(r.get("mutation"), str)
                             and not r.get("error") and not isinstance(r.get("score"), bool)
                             and isinstance(r.get("score"), (int, float))
                             and math.isfinite(r["score"]) for r in esm_rows)
                     and {r["mutation"] for r in esm_rows} == set(codes))
            branches["esm"] = ({**scored, "status": "completed"} if valid else {
                "status": "blocked", "blocked_reason": "esm_complete_finite_wild_type_marginal_scores_required",
                "mutations": []})
        except Exception as exc:
            # Optional model/environment failures must retain earlier evidence.
            # Do not expose model paths, credentials, or malformed NaN payloads.
            branches["esm"] = {"status": "blocked", "mutations": [],
                               "blocked_reason": f"esm_inference_failed:{type(exc).__name__}"}
        if valid:
            lookup = {r["mutation"]: r for r in esm_rows}
            for row in rows:
                row["scores"]["esm_preference"] = {
                    **lookup[row["mutation"]], "model": scored.get("model"),
                    "method": scored.get("method"), "direction": "higher=model_preference",
                    "meaning": "evolutionary_preference_not_thermal_stability"}
    if run_coevolution:
        branches["coevolution"] = await adapters.evcouplings_analyze(sequence, msa_quality or {}, alignment)
        if branches["coevolution"].get("status") == "completed":
            for row in rows:
                pairs = [p for p in branches["coevolution"]["couplings"] if row["position"] in (p["position_i"], p["position_j"])]
                row["coevolution_pairs"] = pairs
                if pairs:
                    row["risks"].append("coupling_background_review_required")
    _pareto_layers(rows)
    def order(row):
        score = row['scores']['ddgun']
        return (row.get('pareto_layer', 999), -(score['ddg'] if score else float('-inf')),
                bool(row['risks']), row['position'], row['mutant'])
    rows.sort(key=order)
    for row in rows:
        if row["scores"]["ddgun"] is None:
            row["missing_evidence"].append("ddgun_predicted_ddg")
        if row["scores"]["esm_preference"] is None:
            row["missing_evidence"].append("esm_evolutionary_preference")
        if row["structure_position"] is None:
            row["missing_evidence"].append("mapped_structure_context")
    if exploring:
        result['screened_candidates'] = rows
        selected, seen = [], set()
        for row in rows:
            if row['position'] not in seen and len(selected) < assay_budget:
                selected.append(row)
                seen.add(row['position'])
        result['preliminary_candidates'] = selected
        result['candidate_counts'] = {'screened': len(rows), 'requested_positions': assay_budget,
                                      'returned_positions': len(selected), 'shortfall': max(0, assay_budget-len(selected))}
        result['selection_policy'] = 'unique_positions_pareto_then_ddgun_then_deterministic_order; unscored_rows_are_hypotheses'
    else:
        result["experimental_plan"].update(
            single_mutants=[r["mutation"] for r in rows[:assay_budget]],
            selection_policy="pareto_layers_for_complete_score_vectors_then_risk_review_and_deterministic_position_order",
            success_criterion="matched-budget thermal improvement with activity retention versus manual/consensus baseline")
    if any(b.get("status") == "blocked" for b in branches.values()):
        result["status"] = "partial"
    result["ranking_boundary"] = "Uncalibrated scores are never added. Pareto layers describe score tradeoffs, not empirical success probabilities."
    return _finish(result)


ToolRegistry.register(
    name="thermostability_candidate_workflow",
    description=("Thermal single-mutant experimental hypotheses with explicit assay endpoint/activity retention, "
                 "sequence-bound identity, numbering, functional protection and deterministic source union. "
                 "Optional DDGun/ESM/ColabFold/coevolution; never claims measured stability improvement."),
    parameters={"type": "object", "properties": {
        "analysis_mode": {"type": "string", "enum": ["strict", "exploration"], "default": "strict"},
        "identity_reference_result": {"type": "object"},
        "prior_blast_tasks": {"type": "array", "items": {"type": "object"}},
        "sequence": {"type": "string"}, "objective": {"type": "object", "description": "endpoint tm/half_life/residual_activity, method, ph, substrate, buffer, cofactors, min_activity_retention_pct; temperature_c/duration_min when applicable"},
        "identity_profile": {"type": "object"}, "objective_module_plan": {"type": "object"},
        "mutations": {"type": "array", "items": {"type": "string"}},
        "candidate_sources": {"type": "array", "items": {"type": "object"}},
        "candidate_positions": {"type": "array", "items": {"type": "integer"}},
        "pdb_data": {"type": "string"}, "structure_source": {"type": "string"},
        "chain_id": {"type": "string", "default": "A"}, "mapping_rows": {"type": "array", "items": {"type": "object"}},
        "protected_sites": {"type": "array", "items": {"type": "object"}},
        "assay_budget": {"type": "integer", "minimum": 1, "maximum": 384, "default": 12},
        "full_length_start": {"type": "integer", "minimum": 1, "description": "Verified full-length coordinate of input residue 1; omit if unknown (no full-length positions will be claimed)."},
        **{key: {"type": "boolean", "default": False} for key in ("run_ddgun", "run_esm", "run_colabfold", "run_coevolution")},
        "msa_policy": {"type": "string", "enum": ["local", "public"], "default": "local"},
        "msa_quality": {"type": "object"}, "alignment": {"type": "string"},
        "run_database_lookup": {"type": "boolean", "default": False}, "uniprot_id": {"type": "string"},
        "offline": {"type": "boolean", "default": False},
        "forbidden_tools": {"type": "array", "items": {"type": "string"}},
    }, "required": ["sequence"]},
    handler=thermostability_candidate_workflow, is_async=True, category="engineering",
    timeout_seconds=tool_timeout("thermostability_candidate_workflow", 1800),
)
