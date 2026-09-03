# numbering_review_low_signal_high_risk_002

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_002.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 74 | stability:169 | low_signal_high_risk | O94923 | K73H | S |  | PMID:31020119 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 75 | stability:171 | low_signal_high_risk | O94923 | V113Q | D |  | PMID:31019180 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 76 | stability:176 | low_signal_high_risk | O95155 | P293Y | L |  | PMID:31079784 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 77 | stability:178 | low_signal_high_risk | O95155 | I1067M | D |  | PMID:31011815 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 78 | stability:18 | low_signal_high_risk | O00444 | K613Q | I |  | PMID:31021158 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 79 | stability:185 | low_signal_high_risk | O95361 | C528S | E |  | PMID:31080679 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 80 | stability:186 | low_signal_high_risk | O95361 | M472L | N |  | PMID:31001162 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 81 | stability:187 | low_signal_high_risk | O95361 | Q104T | H |  | PMID:31063887 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 82 | stability:188 | low_signal_high_risk | O95361 | F8L | A |  | PMID:31023879 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 83 | stability:189 | low_signal_high_risk | O95470 | R112S | Y |  | PMID:31092959 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 84 | stability:19 | low_signal_high_risk | O00444 | V757Y | E |  | PMID:31072939 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 85 | stability:191 | low_signal_high_risk | O95470 | S204K | G |  | PMID:31098447 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 86 | stability:192 | low_signal_high_risk | O95470 | T410P | H |  | PMID:31045105 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 87 | stability:197 | low_signal_high_risk | O95571 | K10H | R |  | PMID:31006679 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 88 | stability:198 | low_signal_high_risk | O95571 | Q98V | C |  | PMID:31055847 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 89 | stability:2 | low_signal_high_risk | P19835 | Y120F | V |  | PMID:23456789 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 90 | stability:20 | low_signal_high_risk | O00444 | Q287H | H |  | PMID:31034258 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 91 | stability:200 | low_signal_high_risk | O95571 | N242R | P |  | PMID:31006833 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 92 | stability:201 | low_signal_high_risk | O95571 | M170H | C |  | PMID:31024228 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 93 | stability:21 | low_signal_high_risk | O00444 | R771K | H |  | PMID:31078580 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 94 | stability:211 | low_signal_high_risk | O95835 | I622M | K |  | PMID:31069936 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 95 | stability:212 | low_signal_high_risk | O95835 | L488C | A |  | PMID:31006753 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 96 | stability:22 | low_signal_high_risk | O00487 | F9A | G |  | PMID:31072849 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 97 | stability:229 | low_signal_high_risk | P00519 | Q372F | G |  | PMID:31013622 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 98 | stability:23 | low_signal_high_risk | O00487 | P251W | L |  | PMID:31058351 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
