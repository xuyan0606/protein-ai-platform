# numbering_review_low_signal_high_risk_005

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_005.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 149 | stability:375 | low_signal_high_risk | P15374 | D140N | N |  | PMID:31027195 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 150 | stability:376 | low_signal_high_risk | P15374 | S147V | T |  | PMID:31057525 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 151 | stability:377 | low_signal_high_risk | P15428 | D193Y | S |  | PMID:31065368 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 152 | stability:379 | low_signal_high_risk | P15428 | D184H | G |  | PMID:31080118 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 153 | stability:38 | low_signal_high_risk | O14744 | F67C | T |  | PMID:31013347 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 154 | stability:380 | low_signal_high_risk | P15428 | L257Q | D |  | PMID:31085621 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 155 | stability:382 | low_signal_high_risk | P15848 | I64T | G |  | PMID:31009276 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 156 | stability:383 | low_signal_high_risk | P15848 | Y427D | T |  | PMID:31005472 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 157 | stability:385 | low_signal_high_risk | P15848 | C22A | V |  | PMID:31089601 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 158 | stability:388 | low_signal_high_risk | P16455 | I15K | P |  | PMID:31094350 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 159 | stability:39 | low_signal_high_risk | O14744 | V58C | P |  | PMID:31078588 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 160 | stability:390 | low_signal_high_risk | P16455 | I155M | V |  | PMID:31032795 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 161 | stability:391 | low_signal_high_risk | P16455 | H140T | P |  | PMID:31039678 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 162 | stability:392 | low_signal_high_risk | P16455 | V94L | F |  | PMID:31070965 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 163 | stability:397 | low_signal_high_risk | P16615 | P422G | D |  | PMID:31045588 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 164 | stability:398 | low_signal_high_risk | P16615 | Y54M | I |  | PMID:31044689 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 165 | stability:399 | low_signal_high_risk | P16615 | Q889C | I |  | PMID:31075053 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 166 | stability:41 | low_signal_high_risk | O14744 | R27V | A |  | PMID:31093494 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 167 | stability:411 | low_signal_high_risk | P17643 | Y302A | L |  | PMID:31079828 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 168 | stability:412 | low_signal_high_risk | P17643 | M217V | G |  | PMID:31049656 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 169 | stability:413 | low_signal_high_risk | P17643 | F34Q | E |  | PMID:31065995 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 170 | stability:414 | low_signal_high_risk | P17643 | V429E | N |  | PMID:31068741 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 171 | stability:419 | low_signal_high_risk | P17812 | Y142K | V |  | PMID:31055185 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 172 | stability:436 | low_signal_high_risk | P19367 | C914R | E |  | PMID:31073161 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 173 | stability:438 | low_signal_high_risk | P19367 | S156G | F |  | PMID:31094803 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
