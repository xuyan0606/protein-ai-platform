# numbering_review_low_signal_high_risk_013

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_013.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 404 | stability:89 | low_signal_high_risk | O43598 | S119R | F |  | PMID:31061708 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 405 | stability:98 | low_signal_high_risk | O60264 | I940D | G |  | PMID:31008826 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 406 | stability:99 | low_signal_high_risk | O60264 | Q448L | N |  | PMID:31012419 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 407 | stability:111 | low_signal_high_risk | O60729 | R242Q | Q |  | PMID:31099868 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 408 | stability:113 | low_signal_high_risk | O60729 | K90Q | G |  | PMID:31043678 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 409 | stability:13 | low_signal_high_risk | A2RUC4 | W306I | Q |  | PMID:31007948 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 410 | stability:142 | low_signal_high_risk | O75884 | M33Q | K |  | PMID:31055536 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 411 | stability:145 | low_signal_high_risk | O75897 | F146C | Y |  | PMID:31075232 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 412 | stability:162 | low_signal_high_risk | O76075 | A93W | H |  | PMID:31027031 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 413 | stability:168 | low_signal_high_risk | O94923 | G391Q | L |  | PMID:31026708 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 414 | stability:199 | low_signal_high_risk | O95571 | C123V | G |  | PMID:31036774 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 415 | stability:206 | low_signal_high_risk | O95630 | F23I | S |  | PMID:31058784 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 416 | stability:214 | low_signal_high_risk | O95835 | K1125F | R |  | PMID:31001365 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 417 | stability:220 | low_signal_high_risk | P00338 | Q37I | I |  | PMID:31069046 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 418 | stability:225 | low_signal_high_risk | P00480 | L279E | Q |  | PMID:31003146 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 419 | stability:234 | low_signal_high_risk | P03951 | S563W | Y |  | PMID:31076149 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 420 | stability:237 | low_signal_high_risk | P03951 | F370M | T |  | PMID:31027622 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 421 | stability:262 | low_signal_high_risk | P06865 | D474P | W |  | PMID:31023629 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 422 | stability:269 | low_signal_high_risk | P07902 | N102R | L |  | PMID:31090820 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 423 | stability:270 | low_signal_high_risk | P07902 | P293A | S |  | PMID:31087552 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 424 | stability:276 | low_signal_high_risk | P08253 | N361W | E |  | PMID:31060139 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 425 | stability:277 | low_signal_high_risk | P08519 | G765W | D |  | PMID:31090250 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 426 | stability:282 | low_signal_high_risk | P08922 | N32I | S |  | PMID:31088251 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 427 | stability:305 | low_signal_high_risk | P09884 | L790H | F |  | PMID:31084708 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 428 | stability:307 | low_signal_high_risk | P09936 | E108F | F |  | PMID:31075552 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
