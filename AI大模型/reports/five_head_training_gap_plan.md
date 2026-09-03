# Five-Head Training Gap Plan

Generated: 2026-09-03T07:32:22.399777+00:00

This is a fail-closed engineering plan. It does not import labels or train a model.

## Summary

- Status: blocked
- Ready heads: 0/5
- Minimum rows per head: 100
- Minimum explicit replicates per head: 3
- Minimum independent groups per head: 10
- Safe for model claim: false

## Head Gaps

| head | label rows | missing | candidates | samples/reps/groups | thresholds | status | blocker |
|---|---:|---:|---:|---|---|---|---|
| mutation_rank | 0 | 100 | 0 | 0/0/0 | 100/3/10 | blocked | MQ-U001 reviewed numbering and real label provenance |
| stability | 0 | 100 | 0 | 0/0/0 | 100/3/10 | blocked | FireProt license/dedup/import receipt + wet-lab authorization |
| activity_risk | 6 | 94 | 6 | 6/0/2 | 100/3/10 | label_rows_below_threshold | metric-level human authorization and feedback preflight |
| substrate_fit | 0 | 100 | 0 | 0/0/0 | 100/3/10 | blocked | no substrate-fit label source approved |
| assay_success | 0 | 100 | 0 | 0/0/0 | 100/3/10 | blocked | plate intake QC and human extraction |

## Candidate Signals

- Wet-lab numeric candidates: 6
- Wet-lab authorization worklist rows: 12
- FireProt mapped stability candidates: 5067
- FireProt reviewed import candidates: 0

## Policy

This plan quantifies head-specific gaps only. It never approves data, imports labels, trains models, or relaxes model-claim gates.
