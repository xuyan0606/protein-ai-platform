# P680 P0 real-input operator dispatch readiness audit

- audit_rows: `6`
- dispatch_readiness_rows: `5`
- dispatch_ready_rows: `5`
- operator_dispatch_sent_rows: `0`
- operator_acknowledged_rows: `0`
- completion_ready_rows: `0`
- release_ready: `false`

| Priority | Lane | Dispatch status |
|---:|---|---|
| 1 | plate_feedback | `blocked_operator_input_required` |
| 2 | strict_holdout | `blocked_operator_input_required` |
| 3 | substrate_identity | `blocked_operator_input_required` |
| 4 | numbering_curation | `blocked_operator_input_required` |
| 5 | governance | `blocked_operator_input_required` |

Dispatch-ready means the local packet contract is complete. It does not mean a task was sent, acknowledged, completed, or approved.
