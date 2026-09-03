# numbering_review_low_signal_high_risk_012

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_012.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 379 | stability:487 | low_signal_high_risk | P22304 | Q413C | L |  | PMID:31034949 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 380 | stability:488 | low_signal_high_risk | P22304 | G86S | P |  | PMID:31083271 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 381 | stability:489 | low_signal_high_risk | P22455 | K319W | Y |  | PMID:31060688 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 382 | stability:49 | low_signal_high_risk | O14939 | I710S | L |  | PMID:31052470 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 383 | stability:490 | low_signal_high_risk | P22455 | E91D | F |  | PMID:31001369 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 384 | stability:491 | low_signal_high_risk | P22735 | N654S | E |  | PMID:31084190 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 385 | stability:493 | low_signal_high_risk | P22735 | Q324I | V |  | PMID:31033995 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 386 | stability:499 | low_signal_high_risk | P23468 | N1290A | Y |  | PMID:31046925 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 387 | stability:50 | low_signal_high_risk | O14939 | A189P | L |  | PMID:31038087 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 388 | stability:51 | low_signal_high_risk | O14939 | H451Y | V |  | PMID:31037238 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 389 | stability:52 | low_signal_high_risk | O15067 | K449G | V |  | PMID:31023079 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 390 | stability:53 | low_signal_high_risk | O15067 | E537A | I |  | PMID:31039987 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 391 | stability:54 | low_signal_high_risk | O15067 | I935P | P |  | PMID:31008570 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 392 | stability:55 | low_signal_high_risk | O15111 | F148I | E |  | PMID:31056301 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 393 | stability:56 | low_signal_high_risk | O15111 | I652C | H |  | PMID:31042950 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 394 | stability:57 | low_signal_high_risk | O15269 | K28F | E |  | PMID:31010671 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 395 | stability:58 | low_signal_high_risk | O15269 | S402D | T |  | PMID:31068013 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 396 | stability:59 | low_signal_high_risk | O15269 | G238N | T |  | PMID:31035172 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 397 | stability:65 | low_signal_high_risk | O15484 | I284E | N |  | PMID:31025775 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 398 | stability:67 | low_signal_high_risk | O15488 | V438K | L |  | PMID:31076016 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 399 | stability:69 | low_signal_high_risk | O15488 | H371T | E |  | PMID:31060477 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 400 | stability:73 | low_signal_high_risk | O15541 | W12C | D |  | PMID:31026766 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 401 | stability:84 | low_signal_high_risk | O43464 | W358E | Q |  | PMID:31082325 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 402 | stability:85 | low_signal_high_risk | O43464 | L276D | S |  | PMID:31099859 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 403 | stability:88 | low_signal_high_risk | O43598 | H103Q | Y |  | PMID:31098131 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
