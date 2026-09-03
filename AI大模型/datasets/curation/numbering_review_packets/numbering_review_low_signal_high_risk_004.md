# numbering_review_low_signal_high_risk_004

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_004.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 124 | stability:298 | low_signal_high_risk | P09874 | H945L | K |  | PMID:31076500 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 125 | stability:3 | low_signal_high_risk | P19835 | W85L | L |  | PMID:34567890 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 126 | stability:301 | low_signal_high_risk | P09874 | D383S | S |  | PMID:31053715 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 127 | stability:302 | low_signal_high_risk | P09874 | Y301T | Q |  | PMID:31024369 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 128 | stability:304 | low_signal_high_risk | P09884 | A1410N | T |  | PMID:31008682 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 129 | stability:311 | low_signal_high_risk | P0C024 | D103W | Q |  | PMID:31091287 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 130 | stability:312 | low_signal_high_risk | P0C024 | S117E | T |  | PMID:31006270 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 131 | stability:314 | low_signal_high_risk | P0C024 | N49W | K |  | PMID:31014524 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 132 | stability:32 | low_signal_high_risk | O00762 | N127V | D |  | PMID:31055059 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 133 | stability:33 | low_signal_high_risk | O00762 | R137M | S |  | PMID:31029574 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 134 | stability:336 | low_signal_high_risk | P12694 | N130S | F |  | PMID:31035382 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 135 | stability:337 | low_signal_high_risk | P12694 | T352A | N |  | PMID:31065252 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 136 | stability:338 | low_signal_high_risk | P12694 | I16Y | G |  | PMID:31011702 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 137 | stability:346 | low_signal_high_risk | P13716 | L42I | D |  | PMID:31052313 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 138 | stability:351 | low_signal_high_risk | P14550 | R211A | S |  | PMID:31080637 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 139 | stability:355 | low_signal_high_risk | P14550 | E32Y | A |  | PMID:31018895 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 140 | stability:356 | low_signal_high_risk | P14735 | I140F | A |  | PMID:31090149 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 141 | stability:36 | low_signal_high_risk | O00762 | S28I | R |  | PMID:31078639 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 142 | stability:360 | low_signal_high_risk | P14735 | Q127F | Y |  | PMID:31097212 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 143 | stability:365 | low_signal_high_risk | P15104 | T257H | S |  | PMID:31085973 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 144 | stability:366 | low_signal_high_risk | P15104 | N78Y | Y |  | PMID:31039706 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 145 | stability:367 | low_signal_high_risk | P15104 | D202T | W |  | PMID:31091458 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 146 | stability:368 | low_signal_high_risk | P15104 | W166Y | G |  | PMID:31003870 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 147 | stability:37 | low_signal_high_risk | O14744 | R98Y | K |  | PMID:31090881 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 148 | stability:374 | low_signal_high_risk | P15374 | E162I | I |  | PMID:31074488 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
