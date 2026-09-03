# Numbering Curation p1_batch_001

Goal: map reported mutation numbering to canonical UniProt positions, or keep unresolved weak.

| record_id | UniProt | mutation | current residue | priority | PMID | nearest matches |
|---|---|---|---|---|---|---|
| stability:4 | P19835 | R45K | D | P1 | PMID:45678901 |  |
| stability:7 | P19835 | S45T | D | P1 | PMID:78901234 | 46(+1) |
| stability:40 | O14744 | R11P | G | P1 | PMID:31085318 | 13(+2), 18(+7) |
| stability:62 | O15297 | L87S | A | P1 | PMID:31081413 | 79(-8) |
| stability:63 | O15297 | Q345S | S | P1 | PMID:31050119 | 344(-1), 332(-13), 330(-15), 360(+15) |
| stability:78 | O43143 | V133Q | K | P1 | PMID:31040601 | 139(+6), 151(+18) |
| stability:92 | O43897 | V36H | T | P1 | PMID:31090486 | 27(-9), 20(-16) |
| stability:93 | O43897 | R316C | S | P1 | PMID:31049106 | 317(+1), 323(+7), 306(-10), 329(+13), 301(-15) |
| stability:111 | O60729 | R242Q | Q | P1 | PMID:31099868 |  |
| stability:113 | O60729 | K90Q | G | P1 | PMID:31043678 |  |
| stability:154 | O76039 | M666Y | E | P1 | PMID:31015572 |  |
| stability:162 | O76075 | A93W | H | P1 | PMID:31027031 |  |
| stability:199 | O95571 | C123V | G | P1 | PMID:31036774 |  |
| stability:234 | P03951 | S563W | Y | P1 | PMID:31076149 |  |
| stability:237 | P03951 | F370M | T | P1 | PMID:31027622 |  |
| stability:262 | P06865 | D474P | W | P1 | PMID:31023629 |  |
| stability:282 | P08922 | N32I | S | P1 | PMID:31088251 |  |
| stability:284 | P08922 | Q2344I | D | P1 | PMID:31075741 |  |
| stability:352 | P14550 | I155Y | L | P1 | PMID:31099004 |  |
| stability:364 | P15104 | N22F | Q | P1 | PMID:31046891 |  |
| stability:372 | P15374 | F97Y | T | P1 | PMID:31037499 |  |
| stability:373 | P15374 | H58G | I | P1 | PMID:31003178 |  |
| stability:381 | P15428 | C16N | G | P1 | PMID:31071708 |  |
| stability:395 | P16615 | E930A | I | P1 | PMID:31011075 |  |
| stability:396 | P16615 | K123Q | E | P1 | PMID:31029419 |  |

Decision output must be appended to `datasets/curation/numbering_curation_decisions.jsonl`.
Use `contracts/numbering_curation_decision.schema.json` fields.
