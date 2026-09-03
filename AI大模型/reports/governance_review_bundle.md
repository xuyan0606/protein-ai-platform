# Governance Review Bundle

This bundle coordinates human governance review only. It does not create approvals.

- Total rows: 37
- Open rows: 37
- Completion-ready rows: 0
- Release ready: false
- Safe for model claim: false

| Workstream | Rows | Open | Completion Ready | Decision Input | Validator |
|---|---:|---:|---:|---|---|
| external_license_review | 19 | 19 | 0 | `datasets/governance/external_license_review_decisions.jsonl` | `python3 scripts/validate_external_license_review_decisions.py` |
| biosecurity_screening | 3 | 3 | 0 | `datasets/governance/biosecurity_screening_decisions.jsonl` | `python3 scripts/validate_biosecurity_screening_decisions.py` |
| sequence_ip_fto | 3 | 3 | 0 | `datasets/governance/sequence_ip_fto_decisions.jsonl` | `python3 scripts/validate_sequence_ip_fto_decisions.py` |
| operator_review_actions | 6 | 6 | 0 | `datasets/governance/operator_review_action_decisions.jsonl` | `python3 scripts/validate_operator_review_action_decisions.py` |
| workstream_acceptance | 6 | 6 | 0 | `datasets/governance/workstream_acceptance_decisions.jsonl` | `python3 scripts/validate_workstream_acceptance_decisions.py` |

## First Open Items

- `governance_review:external_license_review:data_source_UniProt`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:data_source_RCSB_PDB`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:data_source_BRENDA`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:data_source_SABIO-RK`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:data_source_MaveDB`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:data_source_ProteinGym`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:data_source_FireProtDB`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:data_source_ProThermDB`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:foreign_tool_mmseqs2`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:foreign_tool_boltz2`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:foreign_tool_chai1`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:foreign_tool_thermompnn`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:foreign_tool_rosetta`: reviewed_valid_but_not_approved -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:foreign_tool_pyrosetta`: reviewed_valid_but_not_approved -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:foreign_tool_foldx`: reviewed_valid_but_not_approved -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:foreign_tool_clean`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:foreign_tool_ligandmpnn`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:foreign_tool_alphafold3`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:external_license_review:foreign_tool_esm3_open`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.
- `governance_review:biosecurity_screening:screening_kwb-venus15b-strict-review-001`: open_blocked_waiting_for_human_decision -> Open the source artifact, complete the matching decision row only after human review, then run the listed validator command.

## Policy

This governance bundle is a shared human-review work queue. It preserves fail-closed gates: no row grants license, FTO, biosecurity, operator, workstream, model, release, ordering, customer, or deployment approval until the separate human decision file and validator explicitly say so.
