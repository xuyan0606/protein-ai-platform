# Numbering Review Packet Board

Generated: 2026-09-03T07:31:08.695747+00:00

This board is local operator tracking only. It is not a reviewed curation decision and not a supervised label source.

| Order | Packet | Rows | Draft Rows | Status | Valid |
|---:|---|---:|---:|---|---|
| 1 | numbering_review_isoform_exact_001 | 8 | 8 | open_blocked_waiting_for_human_review | True / True |
| 2 | numbering_review_abstract_signal_001 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 3 | numbering_review_abstract_signal_002 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 4 | numbering_review_abstract_signal_003 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 5 | numbering_review_abstract_signal_004 | 13 | 13 | open_blocked_waiting_for_human_review | True / True |
| 6 | numbering_review_pubmed_missing_001 | 17 | 17 | open_blocked_waiting_for_human_review | True / True |
| 7 | numbering_review_low_signal_high_risk_001 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 8 | numbering_review_low_signal_high_risk_002 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 9 | numbering_review_low_signal_high_risk_003 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 10 | numbering_review_low_signal_high_risk_004 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 11 | numbering_review_low_signal_high_risk_005 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 12 | numbering_review_low_signal_high_risk_006 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 13 | numbering_review_low_signal_high_risk_007 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 14 | numbering_review_low_signal_high_risk_008 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 15 | numbering_review_low_signal_high_risk_009 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 16 | numbering_review_low_signal_high_risk_010 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 17 | numbering_review_low_signal_high_risk_011 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 18 | numbering_review_low_signal_high_risk_012 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 19 | numbering_review_low_signal_high_risk_013 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 20 | numbering_review_low_signal_high_risk_014 | 25 | 25 | open_blocked_waiting_for_human_review | True / True |
| 21 | numbering_review_low_signal_high_risk_015 | 12 | 12 | open_blocked_waiting_for_human_review | True / True |

## Commands

1. `python3 scripts/validate_numbering_review_packets.py`
1. `python3 scripts/validate_numbering_curation_decisions.py`
1. `python3 scripts/apply_numbering_curation.py`
1. `python3 scripts/run_safe_training_pipeline.py`

## Policy

Numbering review packet board tracks missing human review only; it never writes reviewed decisions, validates labels into training, or enables model claims.
