# numbering_review_pubmed_missing_001

Review missing or invalid PubMed references before any label promotion.

Policy: this packet is not a curation decision and must not be used as a supervised label source.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/numbering_review_decision_drafts/numbering_review_pubmed_missing_001.decisions.draft.jsonl`

| rank | record_id | bucket | UniProt | mutation | current residue | candidate isoforms | PMID/title flag | review action |
|---:|---|---|---|---|---|---|---|---|
| 207 | stability:119 | pubmed_missing_or_invalid | O60930 | F234L | A |  | PMID:31012099 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 208 | stability:151 | pubmed_missing_or_invalid | O76039 | S713L | G |  | PMID:31095153 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 209 | stability:184 | pubmed_missing_or_invalid | O95361 | K301H | V |  | PMID:31084276 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 210 | stability:213 | pubmed_missing_or_invalid | O95835 | H510W | T |  | PMID:31010912 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 211 | stability:297 | pubmed_missing_or_invalid | P09769 | D205P | M |  | PMID:31067195 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 212 | stability:345 | pubmed_missing_or_invalid | P13716 | V258F | L |  | PMID:31076707 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 213 | stability:354 | pubmed_missing_or_invalid | P14550 | K29E | V |  | PMID:31043426 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 214 | stability:359 | pubmed_missing_or_invalid | P14735 | G496K | Y |  | PMID:31080893 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 215 | stability:5 | pubmed_missing_or_invalid | P19835 | D67N | P |  | PMID:56789012 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 216 | stability:6 | pubmed_missing_or_invalid | P19835 | A102G | Y |  | PMID:67890123 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 217 | stability:91 | pubmed_missing_or_invalid | O43897 | D173A | S |  | PMID:31093640 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 457 | stability:66 | pubmed_missing_or_invalid | O15484 | K338M | I |  | PMID:31079172 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 458 | stability:9 | pubmed_missing_or_invalid | A1L3X0 | A213V | V |  | PMID:31022041 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 459 | stability:177 | pubmed_missing_or_invalid | O95155 | R857G | I |  | PMID:31056069 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 460 | stability:217 | pubmed_missing_or_invalid | O95881 | P162F | A |  | PMID:31062785 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 461 | stability:4 | pubmed_missing_or_invalid | P19835 | R45K | D |  | PMID:45678901 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |
| 462 | stability:7 | pubmed_missing_or_invalid | P19835 | S45T | D |  | PMID:78901234 / pubmed_missing_or_invalid | confirm_source_or_keep_unresolved_weak |

Required checks:
- Confirm the original source really reports this protein and mutation.
- Confirm whether the source uses canonical, isoform, mature-protein, construct, or author numbering.
- Confirm wild-type residue, mutant residue, assay method, and measurement provenance.
- Only reviewed rows should be manually copied into `datasets/curation/numbering_curation_decisions.jsonl`.
