# Numbering Deep Audit

This report is an independent, fail-closed audit. It does not change human decisions or labels.

## Result

- Stability records checked: 549
- Numbering review queue rows checked: 475
- Generated-source fingerprint rows: 542
- Fixture-source rows: 7
- Current UniProt WT mismatches: 523
- ddG/dTm direction conflicts under KWB convention: 546
- Existing decision semantic conflicts: 0
- Rows recommended for reject_label: 549

## Audit Rules

1. A generated-source or fixture fingerprint is not a real ProThermDB receipt.
2. An isoform residue coincidence cannot repair an unsupported literature/source join.
3. Under KWB convention, negative ddG and positive dTm both indicate stabilization; same-sign values are flagged for direction conflict.
4. A human decision whose text says reject but whose machine decision is keep_unresolved_weak is flagged for explicit human resolution.

## Boundary

- No decisions were changed.
- No labels were promoted or rejected automatically.
- safe_for_model_claim remains false.
