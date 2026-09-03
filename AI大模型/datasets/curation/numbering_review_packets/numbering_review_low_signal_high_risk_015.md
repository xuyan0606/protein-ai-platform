# numbering_review_low_signal_high_risk_015

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_015.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 454 | stability:70 | low_signal_high_risk | O15541 | M44H | G |  | PMID:31058979 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 455 | stability:78 | low_signal_high_risk | O43143 | V133Q | K |  | PMID:31040601 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 456 | stability:93 | low_signal_high_risk | O43897 | R316C | S |  | PMID:31049106 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 467 | stability:180 | low_signal_high_risk | O95260 | S140T | L |  | PMID:31001822 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 468 | stability:193 | low_signal_high_risk | O95497 | C243N | P |  | PMID:31037941 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 469 | stability:31 | low_signal_high_risk | O00746 | C167N | F |  | PMID:31067934 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 470 | stability:317 | low_signal_high_risk | P10153 | T134I | Y |  | PMID:31063270 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 471 | stability:333 | low_signal_high_risk | P11766 | N305T | P |  | PMID:31005922 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 472 | stability:371 | low_signal_high_risk | P15170 | C59E | K |  | PMID:31014112 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 473 | stability:409 | low_signal_high_risk | P17540 | H122N | L |  | PMID:31055899 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 474 | stability:500 | low_signal_high_risk | P23468 | G628S | V |  | PMID:31075493 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 475 | stability:96 | low_signal_high_risk | O60235 | M418N | I |  | PMID:31015835 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
