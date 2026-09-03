# structure_chain_single_mismatch_003

Review single-chain structures with sequence-length mismatch.

Policy: this packet is not a reviewed chain mapping and cannot unlock structure-dependent conclusions.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/structure_chain_mapping_decision_drafts/structure_chain_single_mismatch_003.chain_mapping.draft.jsonl`

| rank | PDB | bucket | UniProt | protein | method/resolution | chains | seq len | CA atoms | delta | action |
|---:|---|---|---|---|---|---|---:|---:|---:|---|
| 500 | 13PP | single_chain_ca_length_mismatch | P0DTD1 | Replicase polyprotein 1ab | X-RAY DIFFRACTION / 2.98 | A:315 | 7096 | 313 | -6783 | confirm_chain_and_numbering_or_keep_unreviewed |

Required checks:
- Confirm the biological chain for the UniProt accession.
- Confirm residue numbering, insertion codes, missing residues, engineered tags, and construct truncations.
- Confirm ligands/cofactors only after chain mapping is reviewed.
- Structure distance, pocket, exposure, and catalytic-network features stay blocked until reviewed mapping exists.
