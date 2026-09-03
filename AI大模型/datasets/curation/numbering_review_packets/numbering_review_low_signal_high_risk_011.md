# numbering_review_low_signal_high_risk_011

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_011.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 354 | stability:421 | low_signal_high_risk | P17987 | E482G | N |  | PMID:31017352 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 355 | stability:422 | low_signal_high_risk | P17987 | T528P | D |  | PMID:31038456 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 356 | stability:423 | low_signal_high_risk | P18074 | M345Y | R |  | PMID:31046526 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 357 | stability:424 | low_signal_high_risk | P18074 | Q460S | T |  | PMID:31024046 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 358 | stability:426 | low_signal_high_risk | P18440 | T91Y | G |  | PMID:31044711 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 359 | stability:428 | low_signal_high_risk | P18669 | G82F | V |  | PMID:31036472 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 360 | stability:430 | low_signal_high_risk | P18858 | K296E | F |  | PMID:31072374 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 361 | stability:431 | low_signal_high_risk | P18858 | T859G | R |  | PMID:31064012 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 362 | stability:432 | low_signal_high_risk | P18858 | A853P | P |  | PMID:31058305 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 363 | stability:433 | low_signal_high_risk | P19113 | L465E | N |  | PMID:31064652 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 364 | stability:434 | low_signal_high_risk | P19113 | D270G | L |  | PMID:31097554 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 365 | stability:435 | low_signal_high_risk | P19113 | D228N | I |  | PMID:31090170 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 366 | stability:45 | low_signal_high_risk | O14933 | L88P | P |  | PMID:31066468 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 367 | stability:451 | low_signal_high_risk | P20815 | A482D | L |  | PMID:31052159 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 368 | stability:452 | low_signal_high_risk | P20815 | S406C | K |  | PMID:31035712 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 369 | stability:453 | low_signal_high_risk | P20815 | E384Q | N |  | PMID:31009685 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 370 | stability:465 | low_signal_high_risk | P21439 | Q80T | E |  | PMID:31071708 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 371 | stability:471 | low_signal_high_risk | P21675 | V718I | A |  | PMID:31055859 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 372 | stability:472 | low_signal_high_risk | P21675 | L1197P | G |  | PMID:31077679 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 373 | stability:473 | low_signal_high_risk | P21709 | H106L | C |  | PMID:31075453 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 374 | stability:474 | low_signal_high_risk | P21709 | W791K | R |  | PMID:31022034 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 375 | stability:475 | low_signal_high_risk | P21709 | I3H | R |  | PMID:31062321 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 376 | stability:476 | low_signal_high_risk | P21860 | D663C | F |  | PMID:31039657 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 377 | stability:48 | low_signal_high_risk | O14933 | E42S | D |  | PMID:31083725 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 378 | stability:486 | low_signal_high_risk | P22304 | M18N | S |  | PMID:31001858 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
