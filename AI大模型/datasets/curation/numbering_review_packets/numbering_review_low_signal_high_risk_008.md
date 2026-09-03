# numbering_review_low_signal_high_risk_008

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_008.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 279 | stability:148 | low_signal_high_risk | O75928 | V23P | L |  | PMID:31009415 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 280 | stability:149 | low_signal_high_risk | O75928 | L541M | I |  | PMID:31017158 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 281 | stability:150 | low_signal_high_risk | O75928 | W332C | D |  | PMID:31018031 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 282 | stability:157 | low_signal_high_risk | O76074 | E85T | Q |  | PMID:31075102 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 283 | stability:163 | low_signal_high_risk | O94762 | V90K | L |  | PMID:31071360 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 284 | stability:164 | low_signal_high_risk | O94762 | Q176A | L |  | PMID:31070006 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 285 | stability:167 | low_signal_high_risk | O94768 | W111N | E |  | PMID:31033420 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 286 | stability:172 | low_signal_high_risk | O95154 | A141F | G |  | PMID:31023034 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 287 | stability:174 | low_signal_high_risk | O95154 | V145K | Y |  | PMID:31023682 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 288 | stability:179 | low_signal_high_risk | O95260 | I79D | C |  | PMID:31055573 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 289 | stability:183 | low_signal_high_risk | O95342 | P1015G | S |  | PMID:31039214 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 290 | stability:194 | low_signal_high_risk | O95497 | S289D | H |  | PMID:31036850 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 291 | stability:195 | low_signal_high_risk | O95544 | K443I | E |  | PMID:31095743 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 292 | stability:196 | low_signal_high_risk | O95544 | Y258G | G |  | PMID:31017341 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 293 | stability:202 | low_signal_high_risk | O95622 | N1007M | Q |  | PMID:31047261 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 294 | stability:205 | low_signal_high_risk | O95622 | E913D | S |  | PMID:31069935 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 295 | stability:207 | low_signal_high_risk | O95630 | E323R | Q |  | PMID:31078533 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 296 | stability:209 | low_signal_high_risk | O95714 | R1356V | N |  | PMID:31024126 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 297 | stability:210 | low_signal_high_risk | O95714 | G30Y | D |  | PMID:31092767 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 298 | stability:215 | low_signal_high_risk | O95881 | K57G | L |  | PMID:31097750 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 299 | stability:216 | low_signal_high_risk | O95881 | K98W | E |  | PMID:31076240 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 300 | stability:221 | low_signal_high_risk | P00338 | A71F | F |  | PMID:31032551 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 301 | stability:222 | low_signal_high_risk | P00374 | F69A | K |  | PMID:31011137 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 302 | stability:223 | low_signal_high_risk | P00374 | F52T | I |  | PMID:31062772 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 303 | stability:224 | low_signal_high_risk | P00480 | C125W | T |  | PMID:31013477 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
