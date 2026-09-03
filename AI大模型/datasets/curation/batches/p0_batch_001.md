# Numbering Curation p0_batch_001

Goal: map reported mutation numbering to canonical UniProt positions, or keep unresolved weak.

| record_id | UniProt | mutation | current residue | priority | PMID | nearest matches |
|---|---|---|---|---|---|---|
| stability:1 | P19835 | F18A | A | P0 | PMID:12345678 | 32(+14) |
| stability:2 | P19835 | Y120F | V | P0 | PMID:23456789 | 125(+5), 102(-18) |
| stability:3 | P19835 | W85L | L | P0 | PMID:34567890 | 71(-14) |
| stability:441 | P19835 | L185I | R | P0 | PMID:31046810 |  |
| stability:5 | P19835 | D67N | P | P0 | PMID:56789012 | 48(-19) |
| stability:6 | P19835 | A102G | Y | P0 | PMID:67890123 | 87(-15) |
| stability:37 | O14744 | R98Y | K | P0 | PMID:31090881 | 100(+2), 101(+3), 91(-7) |
| stability:38 | O14744 | F67C | T | P0 | PMID:31013347 | 54(-13), 50(-17) |
| stability:39 | O14744 | V58C | P | P0 | PMID:31078588 | 45(-13) |
| stability:41 | O14744 | R27V | A | P0 | PMID:31093494 | 18(-9), 13(-14) |
| stability:60 | O15297 | C598I | H | P0 | PMID:31040108 | 603(+5), 605(+7) |
| stability:61 | O15297 | P436Y | I | P0 | PMID:31098517 | 437(+1), 428(-8), 426(-10), 418(-18), 417(-19) |
| stability:64 | O15297 | G26S | Q | P0 | PMID:31065768 | 17(-9), 16(-10), 8(-18) |
| stability:74 | O43143 | V66P | N | P0 | PMID:31039931 |  |
| stability:75 | O43143 | G96E | H | P0 | PMID:31024471 | 104(+8), 107(+11) |
| stability:76 | O43143 | D204Q | R | P0 | PMID:31007531 | 207(+3), 210(+6) |
| stability:77 | O43143 | T378A | P | P0 | PMID:31014516 | 391(+13) |
| stability:79 | O43323 | S364G | H | P0 | PMID:31093949 | 349(-15), 384(+20) |
| stability:80 | O43323 | R351K | Q | P0 | PMID:31079279 | 355(+4), 361(+10) |
| stability:81 | O43323 | T127M | E | P0 | PMID:31005123 | 126(-1) |
| stability:82 | O43323 | D378M | T | P0 | PMID:31080351 |  |
| stability:83 | O43323 | Q90I | E | P0 | PMID:31086387 |  |
| stability:91 | O43897 | D173A | S | P0 | PMID:31093640 |  |
| stability:94 | O43897 | I931H | L | P0 | PMID:31089124 |  |
| stability:95 | O43897 | D686K | S | P0 | PMID:31054485 | 674(-12) |

Decision output must be appended to `datasets/curation/numbering_curation_decisions.jsonl`.
Use `contracts/numbering_curation_decision.schema.json` fields.
