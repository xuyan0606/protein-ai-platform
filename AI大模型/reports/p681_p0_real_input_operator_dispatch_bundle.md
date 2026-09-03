# P681 P0 real-input operator dispatch bundle

Status: locally prepared for manual use; dispatch remains blocked until an operator performs the action.

- bundle_rows: `5`
- manual_dispatch_bundle_ready_rows: `5`
- operator_dispatch_sent_rows: `0`
- operator_acknowledged_rows: `0`
- completion_ready_rows: `0`
- release_ready: `false`

| Order | Lane | Formal target | Validator | Status |
|---:|---|---|---|---|
| 1 | plate_feedback | `datasets/feedback/experiment_feedback_plate.local.jsonl` | `python3 scripts/validate_experiment_feedback_plate_intake.py` | `ready_for_manual_dispatch_blocked` |
| 2 | strict_holdout | `cache/advanced_features/benchmarks/kwb_strict_mutation_holdout/dataset.jsonl` | `python3 scripts/build_kwb_strict_mutation_holdout_benchmark.py && python3 scripts/apply_benchmark_score_cache_intake.py && python3 scripts/validate_benchmark_score_cache.py` | `ready_for_manual_dispatch_blocked` |
| 3 | substrate_identity | `datasets/curation/substrate_identity_review_decisions.jsonl` | `python3 scripts/validate_substrate_identity_evidence_candidates.py` | `ready_for_manual_dispatch_blocked` |
| 4 | numbering_curation | `datasets/curation/numbering_curation_decisions.jsonl` | `python3 scripts/validate_numbering_curation_decisions.py && python3 scripts/apply_numbering_curation.py` | `ready_for_manual_dispatch_blocked` |
| 5 | governance | `datasets/governance/external_license_review_decisions.jsonl;datasets/governance/sequence_ip_fto_decisions.jsonl;datasets/governance/biosecurity_screening_decisions.jsonl` | `python3 scripts/validate_external_license_review_decisions.py && python3 scripts/validate_sequence_ip_fto_decisions.py && python3 scripts/validate_biosecurity_screening_decisions.py` | `ready_for_manual_dispatch_blocked` |

This bundle is a local execution aid. It does not send work, receive input, write formal decisions, import labels, assert claims, release, or authorize production.
