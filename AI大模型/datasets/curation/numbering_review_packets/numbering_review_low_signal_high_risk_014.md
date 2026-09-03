# numbering_review_low_signal_high_risk_014

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_014.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 429 | stability:325 | low_signal_high_risk | P10635 | P78V | V |  | PMID:31012821 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 430 | stability:340 | low_signal_high_risk | P13051 | M179Q | L |  | PMID:31005388 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 431 | stability:347 | low_signal_high_risk | P13716 | K51M | P |  | PMID:31018243 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 432 | stability:348 | low_signal_high_risk | P14174 | F33R | K |  | PMID:31082356 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 433 | stability:35 | low_signal_high_risk | O00762 | E161A | A |  | PMID:31032395 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 434 | stability:352 | low_signal_high_risk | P14550 | I155Y | L |  | PMID:31099004 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 435 | stability:363 | low_signal_high_risk | P14920 | R146E | Q |  | PMID:31085253 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 436 | stability:364 | low_signal_high_risk | P15104 | N22F | Q |  | PMID:31046891 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 437 | stability:372 | low_signal_high_risk | P15374 | F97Y | T |  | PMID:31037499 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 438 | stability:373 | low_signal_high_risk | P15374 | H58G | I |  | PMID:31003178 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 439 | stability:381 | low_signal_high_risk | P15428 | C16N | G |  | PMID:31071708 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 440 | stability:384 | low_signal_high_risk | P15848 | C107T | T |  | PMID:31029853 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 441 | stability:395 | low_signal_high_risk | P16615 | E930A | I |  | PMID:31011075 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 442 | stability:417 | low_signal_high_risk | P17812 | D371P | G |  | PMID:31030193 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 443 | stability:439 | low_signal_high_risk | P19367 | H768A | F |  | PMID:31023346 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 444 | stability:445 | low_signal_high_risk | P20132 | Q111C | E |  | PMID:31057928 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 445 | stability:447 | low_signal_high_risk | P20338 | Q115I | A |  | PMID:31080053 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 446 | stability:455 | low_signal_high_risk | P21127 | M320R | S |  | PMID:31013066 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 447 | stability:467 | low_signal_high_risk | P21589 | F170M | V |  | PMID:31079236 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 448 | stability:469 | low_signal_high_risk | P21589 | A486N | P |  | PMID:31091943 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 449 | stability:470 | low_signal_high_risk | P21589 | H193E | F |  | PMID:31020507 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 450 | stability:481 | low_signal_high_risk | P21980 | A184I | Q |  | PMID:31012335 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 451 | stability:485 | low_signal_high_risk | P22303 | E430C | S |  | PMID:31036370 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 452 | stability:62 | low_signal_high_risk | O15297 | L87S | A |  | PMID:31081413 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 453 | stability:63 | low_signal_high_risk | O15297 | Q345S | S |  | PMID:31050119 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
