# KWB-EnzymeDesigner v2.0.0 Model Quality Unlock

## Purpose

This card documents what must be true before the local KWB-EnzymeDesigner can
claim model quality. It is a blocker map, not a quality claim.

## Current Blockers

- Reviewed numbering decisions: missing.
- Strict supervised rows: 25, below the 100 threshold.
- MSA/conservation: runtime and trusted cache not ready.
- Real experiment feedback: no training-eligible rows.
- ddG backend: Rosetta/PyRosetta/FoldX not integrated as executable tools.
- Production sync: not authorized.

## Required Inputs

- `datasets/curation/numbering_curation_decisions.jsonl`
- `reports/msa_conservation_cache_validation_report.json`
- `datasets/feedback/experiment_feedback.local.jsonl`
- a licensed/runtime-verified ddG backend or approved stability baseline
- updated benchmark and claim readiness reports

## Stop Conditions

- Do not use weak evidence as training labels.
- Do not infer Rosetta ddG execution from structure prediction tools.
- Do not claim customer readiness from local review artifacts.
- Do not sync to production without explicit authorization.

## Unlock Order

1. Reviewed numbering
2. MSA/conservation readiness
3. Real feedback intake
4. ddG backend readiness
5. Pipeline rerun and claim readiness review

## Current State

`safe_for_model_claim = false`
