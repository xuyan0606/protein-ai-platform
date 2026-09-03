# P682 P0 real-input response receive preflight

Status: response receive preflight is open and empty; no operator response has been received.

- receive_preflight_rows: `5`
- open_receive_preflight_rows: `5`
- operator_dispatch_sent_rows: `0`
- operator_acknowledged_rows: `0`
- response_received_rows: `0`
- real_input_received_rows: `0`
- completion_ready_rows: `0`
- release_ready: `false`

| Order | Lane | Formal target | Expected response fields | Status |
|---:|---|---|---|---|
| 1 | plate_feedback | `datasets/feedback/experiment_feedback_plate.local.jsonl` | `formal_plate_id, instrument_id, protocol_version, recorded_at, human_qc_decision, human_review_status, reviewer, reviewed_at, review_notes` | `open_empty_awaiting_operator_response` |
| 2 | strict_holdout | `cache/advanced_features/benchmarks/kwb_strict_mutation_holdout/dataset.jsonl` | `real_record_id, source_checksum, label, split_assignment, leakage_review_status, human_acceptance_receipt` | `open_empty_awaiting_operator_response` |
| 3 | substrate_identity | `datasets/curation/substrate_identity_review_decisions.jsonl` | `candidate_id, review_decision, substrate_identity_normalized, source_evidence_locator, reviewer, reviewed_at, decision_rationale` | `open_empty_awaiting_operator_response` |
| 4 | numbering_curation | `datasets/curation/numbering_curation_decisions.jsonl` | `record_id, decision, canonical_uniprot_id, canonical_position, canonical_wild_type, canonical_mutant, source_refs, curator, curated_at` | `open_empty_awaiting_operator_response` |
| 5 | governance | `datasets/governance/external_license_review_decisions.jsonl;datasets/governance/sequence_ip_fto_decisions.jsonl;datasets/governance/biosecurity_screening_decisions.jsonl` | `source_id, decision_scope, verification_status, approved_use, reviewer, reviewed_at, evidence_locator` | `open_empty_awaiting_operator_response` |

This preflight does not send work, receive input, write formal decisions, import labels, assert claims, release, or authorize production.
