# Wet-lab Feedback Authorization Dashboard

Generated: 2026-09-03T07:32:17.942943+00:00

This dashboard is local review navigation only. It is not an authorization, not feedback preflight, and not a training label.

## Summary

- Worklist rows: 12
- Valid worklist rows: 12
- Authorized rows: 8
- Critical tradeoff rows: 4
- Requires human input rows: 12
- Safe for model claim: false

## Variant Queue

| Variant | Priority | Metrics | Outcomes | Ratio range | Authorized | Status |
|---|---|---:|---|---:|---:|---|
| E331Q | critical_tradeoff_review | 4 | go:1, no_go:1, watch:2 | 0.6075-1.4082 | 0 | blocked_human_authorization_required |
| D105N | medium_mixed_benefit_review | 4 | go:3, watch:1 | 1.0467-1.3944 | 4 | blocked_human_authorization_required |
| S265T | standard_multi_property_review | 4 | watch:4 | 0.7570-1.0408 | 4 | blocked_human_authorization_required |

## Local Commands

1. `python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py`
1. `python3 scripts/build_wet_lab_mutant_library_feedback_authorization_worklist.py`
1. `python3 scripts/validate_wet_lab_mutant_library_feedback_authorization_worklist.py`
1. `python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py`
1. `python3 scripts/build_wet_lab_mutant_library_feedback_intake_apply_plan.py`
1. `python3 scripts/run_safe_training_pipeline.py`

## Policy

Dashboard only; not an authorization, not feedback preflight, and not a training label. Human authorization decisions must be written separately and validated before any preflight or intake can proceed.
