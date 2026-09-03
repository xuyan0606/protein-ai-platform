# numbering_review_abstract_signal_004

Review abstract-signal rows after isoform candidates.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_abstract_signal_004.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 253 | stability:259 | abstract_signal | P05177 | R133N | W |  | PMID:31089418 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 254 | stability:28 | abstract_signal | O00506 | S257G | F |  | PMID:31077092 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |
| 255 | stability:284 | abstract_signal | P08922 | Q2344I | D |  | PMID:31075741 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 256 | stability:335 | abstract_signal | P12694 | M412S | V |  | PMID:31063766 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 257 | stability:396 | abstract_signal | P16615 | K123Q | E |  | PMID:31029419 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 258 | stability:40 | abstract_signal | O14744 | R11P | G |  | PMID:31085318 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 259 | stability:418 | abstract_signal | P17812 | Q460I | K |  | PMID:31088357 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 260 | stability:72 | abstract_signal | O15541 | M182I | P |  | PMID:31076934 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 261 | stability:92 | abstract_signal | O43897 | V36H | T |  | PMID:31090486 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 463 | stability:251 | abstract_signal | P04406 | F258A | I |  | PMID:31021132 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 464 | stability:427 | abstract_signal | P18669 | T145V | L |  | PMID:31050341 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 465 | stability:477 | abstract_signal | P21860 | E1025K | T |  | PMID:31040864 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 466 | stability:8 | abstract_signal | A1L3X0 | Y274M | G |  | PMID:31023660 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
