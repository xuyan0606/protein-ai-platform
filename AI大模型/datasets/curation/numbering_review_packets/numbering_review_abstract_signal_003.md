# numbering_review_abstract_signal_003

Review abstract-signal rows after isoform candidates.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_abstract_signal_003.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 228 | stability:240 | abstract_signal | P03956 | F188D | G |  | PMID:31061574 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 229 | stability:243 | abstract_signal | P04062 | W265T | Q |  | PMID:31068355 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 230 | stability:254 | abstract_signal | P04626 | L695P | E |  | PMID:31027371 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 231 | stability:275 | abstract_signal | P08253 | L310V | R |  | PMID:31053791 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 232 | stability:292 | abstract_signal | P09543 | E201T | T |  | PMID:31090091 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 233 | stability:309 | abstract_signal | P09936 | P216C | A |  | PMID:31002133 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 234 | stability:323 | abstract_signal | P10632 | E449F | L |  | PMID:31062422 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 235 | stability:326 | abstract_signal | P10635 | P26R | R |  | PMID:31079620 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 236 | stability:330 | abstract_signal | P11233 | L89M | F |  | PMID:31040020 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 237 | stability:331 | abstract_signal | P11233 | I177G | A |  | PMID:31018591 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 238 | stability:334 | abstract_signal | P11766 | W9L | K |  | PMID:31013107 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 239 | stability:393 | abstract_signal | P16591 | N56R | E |  | PMID:31017975 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 240 | stability:402 | abstract_signal | P17050 | N141K | D |  | PMID:31040226 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 241 | stability:408 | abstract_signal | P17405 | V362C | T |  | PMID:31066983 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 242 | stability:43 | abstract_signal | O14757 | R318G | Q |  | PMID:31076615 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 243 | stability:46 | abstract_signal | O14933 | C144R | T |  | PMID:31024820 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 244 | stability:492 | abstract_signal | P22735 | F196M | Q |  | PMID:31074061 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 245 | stability:86 | abstract_signal | O43464 | E284P | D |  | PMID:31021606 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 246 | stability:97 | abstract_signal | O60235 | H119E | K |  | PMID:31051012 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 247 | stability:127 | abstract_signal | O75319 | M33A | E |  | PMID:31034876 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 248 | stability:143 | abstract_signal | O75884 | N82F | M |  | PMID:31001205 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 249 | stability:154 | abstract_signal | O76039 | M666Y | E |  | PMID:31015572 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 250 | stability:165 | abstract_signal | O94762 | F456Y | T |  | PMID:31012978 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 251 | stability:175 | abstract_signal | O95155 | V1089P | L |  | PMID:31016564 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 252 | stability:256 | abstract_signal | P05177 | S90E | R |  | PMID:31036716 / title_has_broad_protein_signal | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
