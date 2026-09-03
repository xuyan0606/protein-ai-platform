# numbering_review_low_signal_high_risk_003

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_003.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 99 | stability:230 | low_signal_high_risk | P00519 | S556N | Q |  | PMID:31085965 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 100 | stability:232 | low_signal_high_risk | P00519 | K876F | R |  | PMID:31041854 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 101 | stability:235 | low_signal_high_risk | P03951 | T432Y | C |  | PMID:31047410 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 102 | stability:236 | low_signal_high_risk | P03951 | H3A | F |  | PMID:31045790 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 103 | stability:24 | low_signal_high_risk | O00487 | N64Q | D |  | PMID:31060647 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 104 | stability:245 | low_signal_high_risk | P04179 | M123Q | R |  | PMID:31035379 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 105 | stability:246 | low_signal_high_risk | P04179 | E28D | L |  | PMID:31036990 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 106 | stability:25 | low_signal_high_risk | O00487 | H190S | Q |  | PMID:31011793 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 107 | stability:257 | low_signal_high_risk | P05177 | N373D | L |  | PMID:31033558 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 108 | stability:258 | low_signal_high_risk | P05177 | F453E | M |  | PMID:31053613 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 109 | stability:260 | low_signal_high_risk | P06865 | R519K | V |  | PMID:31032089 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 110 | stability:263 | low_signal_high_risk | P06865 | P111R | E |  | PMID:31063740 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 111 | stability:264 | low_signal_high_risk | P06865 | S218E | F |  | PMID:31083915 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 112 | stability:279 | low_signal_high_risk | P08519 | A1331R | R |  | PMID:31058210 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 113 | stability:280 | low_signal_high_risk | P08519 | W1031C | I |  | PMID:31072298 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 114 | stability:281 | low_signal_high_risk | P08519 | E781I | W |  | PMID:31084524 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 115 | stability:283 | low_signal_high_risk | P08922 | A990R | S |  | PMID:31022337 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 116 | stability:285 | low_signal_high_risk | P08922 | F1758Q | I |  | PMID:31030274 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 117 | stability:286 | low_signal_high_risk | P08922 | F408V | I |  | PMID:31020848 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 118 | stability:289 | low_signal_high_risk | P09467 | G184K | C |  | PMID:31049560 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 119 | stability:29 | low_signal_high_risk | O00506 | D66G | E |  | PMID:31088865 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 120 | stability:290 | low_signal_high_risk | P09467 | C134L | G |  | PMID:31060179 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 121 | stability:293 | low_signal_high_risk | P09769 | M385S | A |  | PMID:31074357 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 122 | stability:295 | low_signal_high_risk | P09769 | E261I | S |  | PMID:31047827 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 123 | stability:296 | low_signal_high_risk | P09769 | H118A | R |  | PMID:31063121 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
