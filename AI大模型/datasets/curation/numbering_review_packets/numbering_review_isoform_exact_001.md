# numbering_review_isoform_exact_001

Review all isoform exact candidates before any label promotion.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_isoform_exact_001.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 1 | stability:261 | isoform_exact_plus_abstract_signal | P06865 | F9E | S | P06865-2 | PMID:31050886 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 2 | stability:103 | isoform_exact_candidate | O60502 | L511H | S | O60502-2, O60502-4 | PMID:31078391 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 3 | stability:458 | isoform_exact_candidate | P21127 | E560S | H | P21127-9 | PMID:31048474 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 4 | stability:460 | isoform_exact_candidate | P21128 | S107Y | N | P21128-3 | PMID:31094770 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 45 | stability:219 | isoform_exact_candidate | P00338 | L332A | F | P00338-3 | PMID:31018812 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 46 | stability:274 | isoform_exact_candidate | P08253 | H357I | G | P08253-3 | PMID:31002123 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 47 | stability:308 | isoform_exact_candidate | P09936 | L6A | M | P09936-3 | PMID:31017179 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 48 | stability:457 | isoform_exact_candidate | P21127 | L495W | P | P21127-9 | PMID:31099969 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
