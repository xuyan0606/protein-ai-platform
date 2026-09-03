# numbering_review_low_signal_high_risk_009

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_009.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 304 | stability:228 | low_signal_high_risk | P00505 | E171P | D |  | PMID:31056182 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 305 | stability:238 | low_signal_high_risk | P03956 | F29E | Q |  | PMID:31055668 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 306 | stability:241 | low_signal_high_risk | P04062 | S307Q | L |  | PMID:31020433 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 307 | stability:249 | low_signal_high_risk | P04180 | M25D | F |  | PMID:31065565 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 308 | stability:250 | low_signal_high_risk | P04180 | M100Q | I |  | PMID:31097184 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 309 | stability:252 | low_signal_high_risk | P04406 | R78D | Q |  | PMID:31085750 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 310 | stability:253 | low_signal_high_risk | P04626 | T330V | R |  | PMID:31017197 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 311 | stability:255 | low_signal_high_risk | P04626 | Y1251D | L |  | PMID:31018694 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 312 | stability:265 | low_signal_high_risk | P07384 | W328C | K |  | PMID:31062051 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 313 | stability:266 | low_signal_high_risk | P07384 | C219I | G |  | PMID:31083321 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 314 | stability:267 | low_signal_high_risk | P07384 | D181G | A |  | PMID:31068784 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 315 | stability:268 | low_signal_high_risk | P07902 | K343G | A |  | PMID:31021566 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 316 | stability:271 | low_signal_high_risk | P07998 | M83A | Q |  | PMID:31014891 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 317 | stability:272 | low_signal_high_risk | P07998 | K105V | S |  | PMID:31075810 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 318 | stability:273 | low_signal_high_risk | P07998 | C25I | P |  | PMID:31049488 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 319 | stability:291 | low_signal_high_risk | P09543 | F55M | L |  | PMID:31027260 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 320 | stability:30 | low_signal_high_risk | O00746 | V178K | G |  | PMID:31088225 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 321 | stability:315 | low_signal_high_risk | P0C870 | D156L | A |  | PMID:31022327 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 322 | stability:316 | low_signal_high_risk | P0C870 | W71R | Y |  | PMID:31058561 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 323 | stability:318 | low_signal_high_risk | P10153 | D58L | N |  | PMID:31084822 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 324 | stability:319 | low_signal_high_risk | P10619 | D356E | L |  | PMID:31050471 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 325 | stability:320 | low_signal_high_risk | P10619 | S97E | E |  | PMID:31092867 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 326 | stability:321 | low_signal_high_risk | P10619 | F233V | W |  | PMID:31081328 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 327 | stability:322 | low_signal_high_risk | P10632 | P400H | E |  | PMID:31060419 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 328 | stability:324 | low_signal_high_risk | P10632 | T339R | M |  | PMID:31056555 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
