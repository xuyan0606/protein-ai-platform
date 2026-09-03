# P677 P0 real-input completion checklist

- checklist_rows: `5`
- completion_ready_rows: `0`
- release_ready: `false`
- safe_for_model_claim: `false`

| Priority | Lane | Formal target | Validator |
|---:|---|---|---|
| 1 | plate_feedback | `datasets/feedback/experiment_feedback_plate.local.jsonl` | `python3 scripts/validate_experiment_feedback_plate_intake.py` |
| 2 | strict_holdout | `cache/advanced_features/benchmarks/kwb_strict_mutation_holdout/dataset.jsonl` | `python3 scripts/build_kwb_strict_mutation_holdout_benchmark.py && python3 scripts/apply_benchmark_score_cache_intake.py && python3 scripts/validate_benchmark_score_cache.py` |
| 3 | substrate_identity | `datasets/curation/substrate_identity_review_decisions.jsonl` | `python3 scripts/validate_substrate_identity_evidence_candidates.py` |
| 4 | numbering_curation | `datasets/curation/numbering_curation_decisions.jsonl` | `python3 scripts/validate_numbering_curation_decisions.py && python3 scripts/apply_numbering_curation.py` |
| 5 | governance | `datasets/governance/external_license_review_decisions.jsonl;datasets/governance/sequence_ip_fto_decisions.jsonl;datasets/governance/biosecurity_screening_decisions.jsonl` | `python3 scripts/validate_external_license_review_decisions.py && python3 scripts/validate_sequence_ip_fto_decisions.py && python3 scripts/validate_biosecurity_screening_decisions.py` |

This checklist is a handoff/control artifact. It does not write reviewed decisions, formal intake, training labels, model claims, release approval, or production authorization.
