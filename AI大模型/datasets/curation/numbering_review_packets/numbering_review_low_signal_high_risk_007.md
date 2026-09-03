# numbering_review_low_signal_high_risk_007

Review low-signal high-risk rows only after higher-yield packets.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_low_signal_high_risk_007.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 199 | stability:74 | low_signal_high_risk | O43143 | V66P | N |  | PMID:31039931 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 200 | stability:75 | low_signal_high_risk | O43143 | G96E | H |  | PMID:31024471 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 201 | stability:76 | low_signal_high_risk | O43143 | D204Q | R |  | PMID:31007531 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 202 | stability:79 | low_signal_high_risk | O43323 | S364G | H |  | PMID:31093949 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 203 | stability:81 | low_signal_high_risk | O43323 | T127M | E |  | PMID:31005123 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 204 | stability:83 | low_signal_high_risk | O43323 | Q90I | E |  | PMID:31086387 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 205 | stability:94 | low_signal_high_risk | O43897 | I931H | L |  | PMID:31089124 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 206 | stability:95 | low_signal_high_risk | O43897 | D686K | S |  | PMID:31054485 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 262 | stability:100 | low_signal_high_risk | O60264 | P665F | K |  | PMID:31043923 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 263 | stability:101 | low_signal_high_risk | O60307 | W1247R | E |  | PMID:31002781 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 264 | stability:102 | low_signal_high_risk | O60307 | E1263M | F |  | PMID:31018030 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 265 | stability:107 | low_signal_high_risk | O60678 | S67D | C |  | PMID:31012028 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 266 | stability:108 | low_signal_high_risk | O60678 | W178V | R |  | PMID:31095026 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 267 | stability:114 | low_signal_high_risk | O60882 | S367H | Y |  | PMID:31053026 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 268 | stability:116 | low_signal_high_risk | O60882 | Q37C | N |  | PMID:31057187 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 269 | stability:126 | low_signal_high_risk | O75191 | Y452E | L |  | PMID:31016343 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 270 | stability:129 | low_signal_high_risk | O75319 | S137T | F |  | PMID:31044968 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 271 | stability:130 | low_signal_high_risk | O75319 | I162P | L |  | PMID:31013131 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 272 | stability:131 | low_signal_high_risk | O75365 | P117F | L |  | PMID:31098493 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 273 | stability:133 | low_signal_high_risk | O75390 | M327A | K |  | PMID:31079530 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 274 | stability:134 | low_signal_high_risk | O75390 | P249D | H |  | PMID:31050445 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 275 | stability:139 | low_signal_high_risk | O75828 | V70S | I |  | PMID:31044988 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 276 | stability:140 | low_signal_high_risk | O75828 | P194W | Y |  | PMID:31015164 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 277 | stability:146 | low_signal_high_risk | O75897 | H245T | A |  | PMID:31093948 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |
| 278 | stability:147 | low_signal_high_risk | O75897 | I108C | S |  | PMID:31086410 / title_mismatch_risk | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
