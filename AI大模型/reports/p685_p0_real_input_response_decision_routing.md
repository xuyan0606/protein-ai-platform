# P685 P0 real-input response decision routing

Status: decision routing is open and empty; no evidence has been released for routing.

- decision_routing_rows: `5`
- open_decision_routing_rows: `5`
- decision_route_executed_rows: `0`
- routed_to_formal_review_rows: `0`
- response_received_rows: `0`
- release_ready: `false`

| Order | Lane | Formal target | Status |
|---:|---|---|---|
| 1 | plate_feedback | `datasets/feedback/experiment_feedback_plate.local.jsonl` | `open_empty_decision_routing` |
| 2 | strict_holdout | `cache/advanced_features/benchmarks/kwb_strict_mutation_holdout/dataset.jsonl` | `open_empty_decision_routing` |
| 3 | substrate_identity | `datasets/curation/substrate_identity_review_decisions.jsonl` | `open_empty_decision_routing` |
| 4 | numbering_curation | `datasets/curation/numbering_curation_decisions.jsonl` | `open_empty_decision_routing` |
| 5 | governance | `datasets/governance/external_license_review_decisions.jsonl;datasets/governance/sequence_ip_fto_decisions.jsonl;datasets/governance/biosecurity_screening_decisions.jsonl` | `open_empty_decision_routing` |

This routing shell does not route evidence, write formal decisions, import labels, assert claims, release, or authorize production.
