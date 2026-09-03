# numbering_review_abstract_signal_002

Review abstract-signal rows after isoform candidates.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_abstract_signal_002.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 30 | stability:344 | abstract_signal | P13716 | Q3N | P |  | PMID:31037129 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 31 | stability:353 | abstract_signal | P14550 | F202Q | A |  | PMID:31011097 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |
| 32 | stability:357 | abstract_signal | P14735 | E206D | K |  | PMID:31026778 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 33 | stability:378 | abstract_signal | P15428 | C119W | L |  | PMID:31092180 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 34 | stability:389 | abstract_signal | P16455 | C64E | A |  | PMID:31045832 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |
| 35 | stability:415 | abstract_signal | P17643 | R533M | N |  | PMID:31031861 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 36 | stability:416 | abstract_signal | P17812 | R237M | E |  | PMID:31053730 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 37 | stability:437 | abstract_signal | P19367 | C677A | I |  | PMID:31061619 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 38 | stability:449 | abstract_signal | P20338 | V91D | L |  | PMID:31070216 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |
| 39 | stability:450 | abstract_signal | P20338 | I102M | N |  | PMID:31072477 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 40 | stability:459 | abstract_signal | P21128 | E289M | G |  | PMID:31022185 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 41 | stability:466 | abstract_signal | P21589 | A409M | E |  | PMID:31048711 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 42 | stability:77 | abstract_signal | O43143 | T378A | P |  | PMID:31014516 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |
| 43 | stability:80 | abstract_signal | O43323 | R351K | Q |  | PMID:31079279 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 44 | stability:82 | abstract_signal | O43323 | D378M | T |  | PMID:31080351 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 218 | stability:115 | abstract_signal | O60882 | Q474P | V |  | PMID:31077111 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 219 | stability:125 | abstract_signal | O75191 | W462H | V |  | PMID:31053582 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 220 | stability:132 | abstract_signal | O75365 | N64S | T |  | PMID:31024634 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 221 | stability:156 | abstract_signal | O76074 | R797P | L |  | PMID:31015287 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 222 | stability:173 | abstract_signal | O95154 | L270Y | W |  | PMID:31074994 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 223 | stability:181 | abstract_signal | O95342 | Q15W | E |  | PMID:31058806 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 224 | stability:203 | abstract_signal | O95622 | W741T | L |  | PMID:31050339 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |
| 225 | stability:208 | abstract_signal | O95630 | F141M | E |  | PMID:31089745 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 226 | stability:226 | abstract_signal | P00480 | Q117P | H |  | PMID:31093697 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 227 | stability:239 | abstract_signal | P03956 | C191F | I |  | PMID:31019253 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
