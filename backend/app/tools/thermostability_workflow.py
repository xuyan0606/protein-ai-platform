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
    def diagnostic_value(value):
        if isinstance(value,float) and not math.isfinite(value):
            return str(value)
        if isinstance(value,dict):
            return {k:diagnostic_value(v) for k,v in value.items()}
        if isinstance(value,list):
            return [diagnostic_value(v) for v in value]
        return value
    if 'branches' in result:
        result['branches'] = diagnostic_value(result['branches'])
    scored = {r['mutation']:r for r in result.get('screened_candidates', result.get('preliminary_candidates', []))}
    selected = {r['mutation'] for r in result.get('preliminary_candidates', [])}
    for run in result.get('strategy_runs', []):
        codes = {r['mutation'] for r in run['filtered_candidates']}
        run['scoring_coverage'] = {}
        for key in ('ddgun','thermompnn','esm_preference'):
            count = sum(bool(scored.get(code,{}).get('scores',{}).get(key)) for code in codes)
            run['scoring_coverage'][key] = {'requested':len(codes), 'returned':count,
                                           'complete':bool(codes) and count==len(codes)}
        run['selected_mutations'] = sorted(codes & selected)
        run['candidate_scores'] = {code:scored[code]['scores'] for code in sorted(codes) if code in scored}
    if result.get('strategy_runs'):
        from app.services.thermal_review_exports import review_exports
        result['review_exports'] = review_exports(result)
    result["report_markdown"] = render_thermostability_report(result)
    return result


def _pareto_layers(rows: list[dict]) -> None:
    """Only compare complete, like-for-like score vectors; never add scales."""
    keys = [key for key in ('ddgun','thermompnn','esm_preference') if any(r['scores'].get(key) is not None for r in rows)]
    comparable = [r for r in rows if len(keys)>=2 and all(r['scores'].get(key) is not None for key in keys)]
    def vector(row):
        values={'ddgun':lambda s:s['ddg'], 'thermompnn':lambda s:-s['ddg_pred'], 'esm_preference':lambda s:s['score']}
        return tuple(values[key](row['scores'][key]) for key in keys)
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
    run_thermompnn: bool = False,
) -> dict[str, Any]:
    """Produce reviewed hypotheses; absence of an optional predictor is explicit."""
    from app.tools import thermostability_adapters as adapters

    requested = {"ddgun": run_ddgun, "esm": run_esm, "colabfold": run_colabfold, "coevolution": run_coevolution, 'thermompnn':run_thermompnn}
    forbidden = set(forbidden_tools or [])
    database_was_requested = run_database_lookup
    run_database_lookup = run_database_lookup and "get_stability_data" not in forbidden
    run_ddgun = run_ddgun and not offline and "ddgun_predict" not in forbidden
    run_esm = run_esm and not offline and "esm2_predict" not in forbidden
    run_colabfold = run_colabfold and not offline and "colabfold_predict" not in forbidden
    run_coevolution = run_coevolution and not offline and "evcouplings_analyze" not in forbidden
    run_thermompnn = run_thermompnn and not offline and 'thermompnn_predict' not in forbidden

    sequence = "".join(sequence.split()).upper() if isinstance(sequence, str) else ""
    inputs = dict(sequence=sequence, objective=objective, identity_profile=identity_profile,
                  objective_module_plan=objective_module_plan, mutations=mutations,
                  candidate_sources=candidate_sources, candidate_positions=candidate_positions,
                  pdb_data=pdb_data, structure_source=structure_source, chain_id=chain_id,
                  mapping_rows=mapping_rows, protected_sites=protected_sites,
                  assay_budget=assay_budget, full_length_start=full_length_start, analysis_mode=analysis_mode,
                  identity_reference_result=identity_reference_result)
    result = build_screen(**inputs)
    branches = {key: {"status": "not_requested"} for key in ("database", "colabfold", "ddgun", "esm", "coevolution", 'thermompnn')}
    active = {"ddgun": run_ddgun, "esm": run_esm, "colabfold": run_colabfold, "coevolution": run_coevolution, 'thermompnn':run_thermompnn}
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
        try:
            features = await build_site_structure_function_features(pdb_data=pdb_data, chain_id=chain_id)
        except Exception as exc:
            features = {'status': 'failed', 'reason': f'structure_features_failed:{type(exc).__name__}'}
        if features.get('status') == 'completed':
            inputs['structure_features'] = {**features, 'structure_sha256': hashlib.sha256(pdb_data.encode()).hexdigest()}
            result = build_screen(**inputs)
            result['branches'] = branches
            if prior_blast_tasks:
                result['prior_blast_tasks'] = prior_blast_tasks
            result['structure_feature_receipt'] = {'status': 'completed', 'rows_evaluated': len(features.get('features', [])),
                'structure_sha256': hashlib.sha256(pdb_data.encode()).hexdigest(), 'preview_used_for_selection': False}
        else:
            result['structure_feature_receipt'] = {'status': features.get('status', 'failed'),
                'reason': features.get('reason') or 'structure_features_not_completed', 'rows_evaluated': 0}
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
    if run_thermompnn:
        from app.services.thermal_model_coordinates import model_pdb
        from app.tools.thermompnn_predict import thermompnn_predict
        try:
            remapped,provenance=model_pdb(sequence, inputs.get('pdb_data') or '', inputs['chain_id'])
            prediction=await thermompnn_predict(remapped,codes,sequence=sequence,chain_id=inputs['chain_id'])
            predictions=prediction.get('predictions')
            valid=(prediction.get('status')=='completed' and prediction.get('model')=='ThermoMPNN'
                and bool(prediction.get('model_version'))
                and isinstance(prediction.get('model_sha256'),str) and len(prediction['model_sha256'])==64
                and prediction.get('input_sha256')==provenance['model_structure_sha256']
                and prediction.get('chain_id')==inputs['chain_id']
                and isinstance(predictions,list) and len(predictions)==len(codes)
                and all(isinstance(r,dict) and r.get('mutation') in codes and type(r.get('ddg_pred')) in (int,float)
                    and math.isfinite(r['ddg_pred']) for r in predictions)
                and len({r['mutation'] for r in predictions})==len(codes))
            if valid:
                branches['thermompnn']={**prediction,**provenance,
                    'candidate_coverage':{'requested':len(codes),'returned':len(predictions),'complete':True},
                    'direction':'lower=predicted_stabilizing', 'sign_convention':'negative=predicted_stabilizing',
                    'scientific_boundary':'结构单点ΔΔG模型；不推断Tm、95℃酶活或组合效应；原始分数独立展示。'}
                lookup={r['mutation']:r for r in predictions}
                for row in rows:
                    row['scores']['thermompnn']={**lookup[row['mutation']], 'model':'ThermoMPNN',
                        'model_version':prediction['model_version'],'model_sha256':prediction['model_sha256'],
                        'unit':'kcal/mol','direction':'lower=predicted_stabilizing',
                        'sign_convention':'negative=predicted_stabilizing'}
            else:
                branches['thermompnn']={**prediction,'status':'blocked',
                    'blocked_reason':prediction.get('blocked_reason') or 'thermompnn_complete_unique_finite_bound_scores_required',
                    'candidate_coverage':{'requested':len(codes),'returned':len(predictions) if isinstance(predictions,list) else 0,'complete':False}}
        except Exception as exc:
            branches['thermompnn']={'status':'blocked','predictions':[],
                'blocked_reason':f'thermompnn_structure_or_inference_failed:{type(exc).__name__}'}
    if run_ddgun:
        # Sequence mode avoids treating input positions as PDB author numbers.
        # Direct DDGun3D remains available with its stricter numbering contract.
        try:
            branches["ddgun"] = await adapters.ddgun_predict(sequence, codes)
        except Exception as exc:
            branches["ddgun"] = {'status':'blocked', 'blocked_reason':f'ddgun_request_failed:{type(exc).__name__}', 'predictions':[]}
        prediction = branches["ddgun"]
        if prediction.get("status") == "completed":
            predictions = prediction.get('predictions')
            valid = (isinstance(predictions,list) and len(predictions)==len(codes)
                and all(isinstance(r,dict) and r.get('mutation') in codes
                    and type(r.get('ddg')) in (int,float) and math.isfinite(r['ddg']) for r in predictions)
                and len({r['mutation'] for r in predictions})==len(codes))
            if valid:
                lookup = {r['mutation']:r for r in predictions}
                for row in rows:
                    row['scores']['ddgun'] = {**lookup[row['mutation']], 'method':'DDGun_sequence',
                        'sequence_sha256':result['sequence_sha256'], 'algorithm_commit':prediction.get('algorithm_commit'),
                        'database_version':prediction.get('database_version')}
            else:
                branches['ddgun'] = {**prediction, 'status':'blocked',
                    'blocked_reason':'ddgun_complete_unique_finite_scores_required',
                    'candidate_coverage':{'requested':len(codes), 'returned':len(predictions) if isinstance(predictions,list) else 0, 'complete':False}}
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
        structural = row['scores'].get('thermompnn')
        return (row.get('pareto_layer', 999), -(score['ddg'] if score else float('-inf')),
                structural['ddg_pred'] if structural else float('inf'), bool(row['risks']), row['position'], row['mutant'])
    rows.sort(key=order)
    for row in rows:
        if row["scores"]["ddgun"] is None:
            row["missing_evidence"].append("ddgun_predicted_ddg")
        if run_esm and row["scores"]["esm_preference"] is None:
            row["missing_evidence"].append("esm_evolutionary_preference")
        if run_thermompnn and row['scores'].get('thermompnn') is None:
            row['missing_evidence'].append('thermompnn_predicted_ddg')
        if row["structure_position"] is None:
            row["missing_evidence"].append("mapped_structure_context")
    if exploring:
        from app.services.thermal_structure_hypotheses import select_diverse_candidates
        result['screened_candidates'] = rows
        selected, audit = select_diverse_candidates(rows, assay_budget, exclude_adverse_ddgun=False)
        result['selection_audit'] = audit
        result['preliminary_candidates'] = selected
        result['candidate_counts'] = {'screened': len(rows), 'requested_positions': assay_budget,
                                      'returned_positions': len(selected), 'shortfall': max(0, assay_budget-len(selected))}
        result['selection_policy'] = ('unique_positions_and_auto_probe_substitution_cap_with_pareto_then_ddgun_order; '
                                      'shortfalls_not_backfilled; unscored_rows_are_hypotheses; no_model_hard_filter')
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
                 "Optional independent DDGun/ThermoMPNN; ESM preference/ColabFold/coevolution remain explicit options; "
                 "never claims measured stability improvement."),
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
        **{key: {"type": "boolean", "default": False} for key in ("run_ddgun", "run_esm", "run_colabfold", "run_coevolution", 'run_thermompnn')},
        "msa_policy": {"type": "string", "enum": ["local", "public"], "default": "local"},
        "msa_quality": {"type": "object"}, "alignment": {"type": "string"},
        "run_database_lookup": {"type": "boolean", "default": False}, "uniprot_id": {"type": "string"},
        "offline": {"type": "boolean", "default": False},
        "forbidden_tools": {"type": "array", "items": {"type": "string"}},
    }, "required": ["sequence"]},
    handler=thermostability_candidate_workflow, is_async=True, category="engineering",
    timeout_seconds=tool_timeout("thermostability_candidate_workflow", 1800),
)
