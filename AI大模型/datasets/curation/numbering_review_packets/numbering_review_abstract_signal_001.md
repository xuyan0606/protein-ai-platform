# numbering_review_abstract_signal_001

Review abstract-signal rows after isoform candidates.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_abstract_signal_001.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 5 | stability:118 | abstract_signal | O60930 | I127T | P |  | PMID:31079356 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 6 | stability:138 | abstract_signal | O75449 | G15N | E |  | PMID:31062430 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |
| 7 | stability:144 | abstract_signal | O75884 | R138M | D |  | PMID:31059741 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 8 | stability:15 | abstract_signal | O00329 | I208W | S |  | PMID:31010999 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 9 | stability:152 | abstract_signal | O76039 | W877E | H |  | PMID:31089057 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 10 | stability:155 | abstract_signal | O76039 | P247T | L |  | PMID:31087915 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 11 | stability:160 | abstract_signal | O76075 | P11W | R |  | PMID:31068014 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 12 | stability:161 | abstract_signal | O76075 | V300E | K |  | PMID:31091124 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 13 | stability:17 | abstract_signal | O00329 | A86S | Q |  | PMID:31063202 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 14 | stability:170 | abstract_signal | O94923 | Q324P | V |  | PMID:31069661 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 15 | stability:190 | abstract_signal | O95470 | E204I | G |  | PMID:31021013 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 16 | stability:231 | abstract_signal | P00519 | M301F | L |  | PMID:31075740 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 17 | stability:233 | abstract_signal | P03951 | S435Q | G |  | PMID:31054875 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 18 | stability:244 | abstract_signal | P04179 | H33Q | Y |  | PMID:31061399 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 19 | stability:247 | abstract_signal | P04179 | V42E | I |  | PMID:31026441 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |
| 20 | stability:26 | abstract_signal | O00506 | I414K | R |  | PMID:31092281 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 21 | stability:27 | abstract_signal | O00506 | Y362H | V |  | PMID:31074594 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 22 | stability:287 | abstract_signal | P09467 | D105E | I |  | PMID:31081016 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 23 | stability:288 | abstract_signal | P09467 | D279Y | L |  | PMID:31082773 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 24 | stability:294 | abstract_signal | P09769 | E33N | H |  | PMID:31068387 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |
| 25 | stability:299 | abstract_signal | P09874 | W813L | I |  | PMID:31055541 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 26 | stability:300 | abstract_signal | P09874 | K611N | I |  | PMID:31046258 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 27 | stability:303 | abstract_signal | P09884 | D503I | S |  | PMID:31041759 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |
| 28 | stability:306 | abstract_signal | P09884 | Q864M | L |  | PMID:31006134 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 29 | stability:313 | abstract_signal | P0C024 | A212G | V |  | PMID:31011537 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
