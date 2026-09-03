# Numbering Hard-Gate Operator Packets

Generated: 2026-09-03T07:33:45.236526+00:00

Operator navigation only. These packets are not reviewed decisions and are not supervised labels.

## Status

- Status: `blocked`
- Packet rows: `21`
- Semantic conflict packets: `0`
- Open numbering packets: `21`
- Semantic conflict rows: `0`
- Open numbering rows: `471`
- Largest open packet: `25` rows
- Label provenance hard gate: `blocked_no_claim_eligible_real_source_labels`
- Claim-eligible labels: `0`
- Safe for model claim: `false`
- Training unlocked: `false`

## Semantic Conflicts First

| order | packet | conflict | record | UniProt | mutation | current decision | recommended resolution |
|---:|---|---|---|---|---|---|---|

## Open Numbering Batches

| order | packet | source packet | bucket | rows | review ranks | priorities |
|---:|---|---|---|---:|---|---|
| 1 | numbering-hard-gate-open-numbering_review_abstract_signal_001 | numbering_review_abstract_signal_001 | abstract_signal | 25 | [5, 29] | {'P0': 25} |
| 2 | numbering-hard-gate-open-numbering_review_abstract_signal_002 | numbering_review_abstract_signal_002 | abstract_signal | 25 | [30, 227] | {'P0': 15, 'P1': 10} |
| 3 | numbering-hard-gate-open-numbering_review_isoform_exact_001 | numbering_review_isoform_exact_001 | isoform_exact_candidate | 4 | [45, 48] | {'P1': 4} |
| 4 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_001 | numbering_review_low_signal_high_risk_001 | low_signal_high_risk | 25 | [49, 73] | {'P0': 25} |
| 5 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_002 | numbering_review_low_signal_high_risk_002 | low_signal_high_risk | 25 | [74, 98] | {'P0': 25} |
| 6 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_003 | numbering_review_low_signal_high_risk_003 | low_signal_high_risk | 25 | [99, 123] | {'P0': 25} |
| 7 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_004 | numbering_review_low_signal_high_risk_004 | low_signal_high_risk | 25 | [124, 148] | {'P0': 25} |
| 8 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_005 | numbering_review_low_signal_high_risk_005 | low_signal_high_risk | 25 | [149, 173] | {'P0': 25} |
| 9 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_006 | numbering_review_low_signal_high_risk_006 | low_signal_high_risk | 25 | [174, 198] | {'P0': 25} |
| 10 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_007 | numbering_review_low_signal_high_risk_007 | low_signal_high_risk | 25 | [199, 278] | {'P0': 8, 'P1': 17} |
| 11 | numbering-hard-gate-open-numbering_review_pubmed_missing_001 | numbering_review_pubmed_missing_001 | pubmed_missing_or_invalid | 17 | [207, 462] | {'P0': 11, 'P1': 6} |
| 12 | numbering-hard-gate-open-numbering_review_abstract_signal_003 | numbering_review_abstract_signal_003 | abstract_signal | 25 | [228, 252] | {'P1': 25} |
| 13 | numbering-hard-gate-open-numbering_review_abstract_signal_004 | numbering_review_abstract_signal_004 | abstract_signal | 13 | [253, 466] | {'P1': 9, 'P2': 4} |
| 14 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_008 | numbering_review_low_signal_high_risk_008 | low_signal_high_risk | 25 | [279, 303] | {'P1': 25} |
| 15 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_009 | numbering_review_low_signal_high_risk_009 | low_signal_high_risk | 25 | [304, 328] | {'P1': 25} |
| 16 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_010 | numbering_review_low_signal_high_risk_010 | low_signal_high_risk | 25 | [329, 353] | {'P1': 25} |
| 17 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_011 | numbering_review_low_signal_high_risk_011 | low_signal_high_risk | 25 | [354, 378] | {'P1': 25} |
| 18 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_012 | numbering_review_low_signal_high_risk_012 | low_signal_high_risk | 25 | [379, 403] | {'P1': 25} |
| 19 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_013 | numbering_review_low_signal_high_risk_013 | low_signal_high_risk | 25 | [404, 428] | {'P1': 25} |
| 20 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_014 | numbering_review_low_signal_high_risk_014 | low_signal_high_risk | 25 | [429, 453] | {'P1': 25} |
| 21 | numbering-hard-gate-open-numbering_review_low_signal_high_risk_015 | numbering_review_low_signal_high_risk_015 | low_signal_high_risk | 12 | [454, 475] | {'P1': 3, 'P2': 9} |

## Fail-Closed Boundary

Fail-closed reviewed-numbering operator packets only. These packets guide human review; they do not write numbering_curation_decisions.jsonl, apply curation, import labels, run a safe pipeline, update a manifest, enable training, support model claims, or grant release readiness.

Forbidden outputs/actions:
- `datasets/curation/numbering_curation_decisions.jsonl`
- `datasets/curated/enzyme_mutation_supervised_claim_eligible.jsonl`
- `reports/data_lake_manifest.json`
- `reports/local_release_manifest.json`
- `safe training pipeline outputs`

No packet is completion-ready. Human review must produce a separate explicit decision and separate validation/apply actions; this scaffold does not perform them.
