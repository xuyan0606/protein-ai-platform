# numbering_review_low_signal_high_risk_010

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_010.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 329 | stability:327 | low_signal_high_risk | P10635 | T253Q | E |  | PMID:31015098 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 330 | stability:328 | low_signal_high_risk | P10721 | C917Y | F |  | PMID:31081294 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 331 | stability:329 | low_signal_high_risk | P10721 | P717Q | S |  | PMID:31022418 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 332 | stability:332 | low_signal_high_risk | P11233 | S4Q | N |  | PMID:31089025 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 333 | stability:339 | low_signal_high_risk | P13051 | E194L | V |  | PMID:31089007 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 334 | stability:341 | low_signal_high_risk | P13051 | T297M | N |  | PMID:31014443 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 335 | stability:342 | low_signal_high_risk | P13686 | F256S | V |  | PMID:31063810 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 336 | stability:343 | low_signal_high_risk | P13686 | D148M | V |  | PMID:31064012 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 337 | stability:349 | low_signal_high_risk | P14174 | V60G | C |  | PMID:31069019 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 338 | stability:350 | low_signal_high_risk | P14174 | M57V | C |  | PMID:31061152 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 339 | stability:361 | low_signal_high_risk | P14920 | S244L | L |  | PMID:31087517 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 340 | stability:362 | low_signal_high_risk | P14920 | P141Q | G |  | PMID:31003667 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 341 | stability:370 | low_signal_high_risk | P15170 | G54Q | E |  | PMID:31032832 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 342 | stability:386 | low_signal_high_risk | P16234 | C988Q | Y |  | PMID:31018058 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 343 | stability:387 | low_signal_high_risk | P16234 | R237E | V |  | PMID:31044975 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 344 | stability:394 | low_signal_high_risk | P16591 | I534M | T |  | PMID:31030816 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 345 | stability:400 | low_signal_high_risk | P17050 | P84S | G |  | PMID:31089470 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 346 | stability:403 | low_signal_high_risk | P17050 | M292K | Q |  | PMID:31061138 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 347 | stability:404 | low_signal_high_risk | P17252 | S368W | K |  | PMID:31072280 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 348 | stability:405 | low_signal_high_risk | P17252 | D322S | E |  | PMID:31016676 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 349 | stability:406 | low_signal_high_risk | P17405 | F179C | S |  | PMID:31041594 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 350 | stability:407 | low_signal_high_risk | P17405 | V43I | L |  | PMID:31088918 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 351 | stability:410 | low_signal_high_risk | P17540 | F145A | L |  | PMID:31049115 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 352 | stability:42 | low_signal_high_risk | O14757 | H304Y | N |  | PMID:31094978 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 353 | stability:420 | low_signal_high_risk | P17987 | H507G | T |  | PMID:31072690 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
