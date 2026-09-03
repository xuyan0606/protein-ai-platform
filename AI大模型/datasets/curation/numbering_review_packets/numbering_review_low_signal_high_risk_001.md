# numbering_review_low_signal_high_risk_001

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_001.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 49 | stability:1 | low_signal_high_risk | P19835 | F18A | A |  | PMID:12345678 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 50 | stability:10 | low_signal_high_risk | A2RUC4 | G74L | N |  | PMID:31080541 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 51 | stability:104 | low_signal_high_risk | O60502 | M455F | E |  | PMID:31037809 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 52 | stability:105 | low_signal_high_risk | O60502 | A769K | V |  | PMID:31007088 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 53 | stability:106 | low_signal_high_risk | O60502 | I681K | F |  | PMID:31082547 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 54 | stability:109 | low_signal_high_risk | O60729 | G160I | T |  | PMID:31075553 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 55 | stability:11 | low_signal_high_risk | A2RUC4 | G167A | L |  | PMID:31054110 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 56 | stability:110 | low_signal_high_risk | O60729 | H230L | P |  | PMID:31021990 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 57 | stability:112 | low_signal_high_risk | O60729 | Q196D | N |  | PMID:31095244 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 58 | stability:117 | low_signal_high_risk | O60930 | T179S | R |  | PMID:31096425 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 59 | stability:12 | low_signal_high_risk | A2RUC4 | K166Q | N |  | PMID:31098584 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 60 | stability:120 | low_signal_high_risk | O60930 | P197Y | A |  | PMID:31055951 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 61 | stability:121 | low_signal_high_risk | O75151 | T619W | E |  | PMID:31011649 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 62 | stability:122 | low_signal_high_risk | O75151 | W224N | D |  | PMID:31040384 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 63 | stability:123 | low_signal_high_risk | O75151 | G14T | Y |  | PMID:31037794 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 64 | stability:124 | low_signal_high_risk | O75151 | G883H | D |  | PMID:31065879 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 65 | stability:135 | low_signal_high_risk | O75449 | H311F | D |  | PMID:31065265 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 66 | stability:136 | low_signal_high_risk | O75449 | D408M | S |  | PMID:31015163 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 67 | stability:137 | low_signal_high_risk | O75449 | V247I | M |  | PMID:31093817 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 68 | stability:14 | low_signal_high_risk | O00329 | V952Q | K |  | PMID:31072624 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 69 | stability:141 | low_signal_high_risk | O75884 | E23D | W |  | PMID:31048201 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 70 | stability:153 | low_signal_high_risk | O76039 | G862C | L |  | PMID:31067560 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 71 | stability:158 | low_signal_high_risk | O76075 | E141Y | W |  | PMID:31016415 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 72 | stability:159 | low_signal_high_risk | O76075 | M51D | D |  | PMID:31091848 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 73 | stability:16 | low_signal_high_risk | O00329 | H1025F | E |  | PMID:31059211 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
