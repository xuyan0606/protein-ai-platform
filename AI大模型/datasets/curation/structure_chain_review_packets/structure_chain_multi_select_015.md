# structure_chain_multi_select_015

Review multi-chain structures requiring biological chain selection.

Policy: this packet is not a reviewed chain mapping and cannot unlock structure-dependent conclusions.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/curation/structure_chain_mapping_decision_drafts/structure_chain_multi_select_015.chain_mapping.draft.jsonl`

| rank | PDB | bucket | UniProt | protein | method/resolution | chains | seq len | CA atoms | delta | action |
|---:|---|---|---|---|---|---|---:|---:|---:|---|
| 444 | 13OI | multi_chain_needs_selection | P0DTD1 | Replicase polyprotein 1ab | X-RAY DIFFRACTION / 2.86 | A:313, B:1, C:1 | 7096 | 313 | -6783 | confirm_chain_and_numbering_or_keep_unreviewed |
| 445 | 13OW | multi_chain_needs_selection | P0DTD1 | Replicase polyprotein 1ab | X-RAY DIFFRACTION / 2.98 | A:313, B:1, C:1 | 7096 | 313 | -6783 | confirm_chain_and_numbering_or_keep_unreviewed |
| 446 | 13OP | multi_chain_needs_selection | P0DTD1 | Replicase polyprotein 1ab | X-RAY DIFFRACTION / 2.99 | A:313, B:1, C:1 | 7096 | 313 | -6783 | confirm_chain_and_numbering_or_keep_unreviewed |
| 447 | 12AF | multi_chain_needs_selection | P0DTD1 | Replicase polyprotein 1ab | X-RAY DIFFRACTION / 1.87 | A:305, B:1, C:1, D:1, E:1 | 7096 | 312 | -6784 | confirm_chain_and_numbering_or_keep_unreviewed |
| 448 | 10QQ | multi_chain_needs_selection | P55072 | Transitional endoplasmic reticulum ATPase | ELECTRON MICROSCOPY | A:744, B:744, C:744, D:744, E:744, F:744, G:744, H:744 | 806 | 8820 | 8014 | confirm_chain_and_numbering_or_keep_unreviewed |
| 449 | 12DL | multi_chain_needs_selection | Q8VDF2 | E3 ubiquitin-protein ligase UHRF1 | ELECTRON MICROSCOPY | A:429, AA:456, B:949, BA:154, C:946, CA:157, D:128, DA:463 | 782 | 16739 | 15957 | confirm_chain_and_numbering_or_keep_unreviewed |

Required checks:
- Confirm the biological chain for the UniProt accession.
- Confirm residue numbering, insertion codes, missing residues, engineered tags, and construct truncations.
- Confirm ligands/cofactors only after chain mapping is reviewed.
- Structure distance, pocket, exposure, and catalytic-network features stay blocked until reviewed mapping exists.
