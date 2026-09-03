# Wet-lab Feedback Authorization Execution Queue

Generated: 2026-09-03T07:32:18.134025+00:00

This queue is local operator navigation only. It is not an authorization, not feedback preflight, and not a training label.

| Order | Variant | Metrics | Modes | Receipt status | Authorized | Preflight | Status |
|---:|---|---:|---|---|---:|---:|---|
| 1 | E331Q | 4 | tradeoff_review_required:4 | open_blocked_no_authorization_decision:4 | 0 | 0 | open_blocked_waiting_for_human_authorization |
| 2 | D105N | 4 | positive_candidate_review_required:3, watch_candidate_review_required:1 | preflight_present_but_receipt_still_fail_closed:4 | 4 | 4 | open_blocked_waiting_for_human_authorization |
| 3 | S265T | 4 | watch_candidate_review_required:4 | preflight_present_but_receipt_still_fail_closed:4 | 4 | 4 | open_blocked_waiting_for_human_authorization |

## Commands

1. `python3 scripts/validate_wet_lab_mutant_library_feedback_authorizations.py`
1. `python3 scripts/build_wet_lab_mutant_library_feedback_preflight.py`
1. `python3 scripts/run_safe_training_pipeline.py`

## Policy

Execution queue guides human review only; it never grants authorization, writes preflight, appends labels, or enables model claims.
