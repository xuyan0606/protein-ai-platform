# numbering_review_low_signal_high_risk_006

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_006.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 174 | stability:441 | low_signal_high_risk | P19835 | L185I | R |  | PMID:31046810 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 175 | stability:442 | low_signal_high_risk | P20132 | E152K | L |  | PMID:31042651 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 176 | stability:443 | low_signal_high_risk | P20132 | Q127E | N |  | PMID:31052179 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 177 | stability:444 | low_signal_high_risk | P20132 | S66T | G |  | PMID:31066518 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 178 | stability:446 | low_signal_high_risk | P20132 | P218K | S |  | PMID:31005981 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 179 | stability:448 | low_signal_high_risk | P20338 | F85W | G |  | PMID:31043685 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 180 | stability:454 | low_signal_high_risk | P21127 | A21W | K |  | PMID:31079390 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 181 | stability:456 | low_signal_high_risk | P21127 | W271S | E |  | PMID:31036512 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 182 | stability:461 | low_signal_high_risk | P21128 | I291C | V |  | PMID:31004786 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 183 | stability:462 | low_signal_high_risk | P21128 | W165Q | S |  | PMID:31065512 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 184 | stability:468 | low_signal_high_risk | P21589 | S258R | V |  | PMID:31093728 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 185 | stability:478 | low_signal_high_risk | P21980 | D544I | L |  | PMID:31073465 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 186 | stability:479 | low_signal_high_risk | P21980 | S453K | R |  | PMID:31003316 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 187 | stability:480 | low_signal_high_risk | P21980 | R375N | P |  | PMID:31049048 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 188 | stability:482 | low_signal_high_risk | P22303 | T260A | S |  | PMID:31005757 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 189 | stability:483 | low_signal_high_risk | P22303 | K260C | S |  | PMID:31022777 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 190 | stability:484 | low_signal_high_risk | P22303 | V485E | I |  | PMID:31010856 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 191 | stability:494 | low_signal_high_risk | P23458 | D542T | R |  | PMID:31090052 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 192 | stability:495 | low_signal_high_risk | P23458 | C350Y | H |  | PMID:31084674 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 193 | stability:496 | low_signal_high_risk | P23458 | H592N | G |  | PMID:31027620 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 194 | stability:497 | low_signal_high_risk | P23458 | H529S | Q |  | PMID:31018326 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 195 | stability:498 | low_signal_high_risk | P23458 | W957M | E |  | PMID:31091920 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 196 | stability:60 | low_signal_high_risk | O15297 | C598I | H |  | PMID:31040108 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 197 | stability:61 | low_signal_high_risk | O15297 | P436Y | I |  | PMID:31098517 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 198 | stability:64 | low_signal_high_risk | O15297 | G26S | Q |  | PMID:31065768 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
