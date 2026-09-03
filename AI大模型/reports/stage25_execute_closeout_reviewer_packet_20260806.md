# Stage 25 Execute Closeout Reviewer Packet

- Date: 2026-08-06
- Mode: execute requested but blocked; reviewer closeout packet only
- Scope: four new lipase/xylanase paper proposals with 24 open apply blockers
- Governance: needs_more_info for every row; no SQLite write, no apply execution, no export-safe release, no model claim
- allow_apply=false
- external_sqlite_mutated=false
- export_safe_released=false
- release_ready=false
- safe_for_model_claim=false
- formal_decision_rows_written=0
- Do not write SQLite
- Required gate: fulltext/source-table evidence and reviewer approval must close before importer apply

## Summary

- Proposal rows: 4
- Checklist rows: 24
- Closed rows: 0
- Approved rows: 0

## LIP_CAND_20260805_003

- Family: lipase
- DOI: 10.1016/j.biortech.2026.135069
- PMID: 42235695
- Stable proposal id: LIP_PAPER_2cda9260
- Evidence level: abstract_only
- Source gap: ScienceDirect/PubMed abstract only; source table/figure and exact residue substitutions unavailable in current evidence set
- Next action: obtain full text and separate mutation evidence from immobilization/process evidence before family importer
- Closeout ready: false

Required before apply:

- CM5 exact residue substitutions
- Candida rugosa lipase WT baseline
- separate mutation effects from immobilization/process metrics
- absolute values, units and assay conditions
- source table/figure/supplement locator
- evidence that process/immobilization metrics are not imported as residue-level variant measurements

Open checklist items:

- `approved_for_family_importer`: Record explicit family-importer approval for this proposal. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `human_review_status`: Set review_status to approved_for_family_importer only after source locators and payload drafts are reviewed. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `intake_approval`: Mark intake approved only after file hash, source locator and reviewer package checks pass. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `paper_pdf`: Place legally obtained full text or supplementary files in the approved local intake path. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `payload_draft`: Fill reviewed variant and/or measurement payload drafts with values, units, conditions and evidence levels. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `source_locators`: Provide source table/figure/supplement locators for every imported identity and measurement claim. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]

## LIP_CAND_20260805_004

- Family: lipase
- DOI: 10.1016/j.enzmictec.2026.110921
- PMID: 42248057
- Stable proposal id: LIP_PAPER_05f2ba60
- Evidence level: abstract_only
- Source gap: ScienceDirect abstract/highlights only; source table/figure not available in current evidence set
- Next action: keep benchmark/source-only unless full text proves engineered variant data
- Closeout ready: false

Required before apply:

- confirm whether full text contains engineered variants
- if no variants, keep benchmark/source-only and do not create variant/measurement importer payload
- source table/figure locator for benchmark characterization if later curated

Open checklist items:

- `approved_for_family_importer`: Record explicit family-importer approval for this proposal. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `human_review_status`: Set review_status to approved_for_family_importer only after source locators and payload drafts are reviewed. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `intake_approval`: Mark intake approved only after file hash, source locator and reviewer package checks pass. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `paper_pdf`: Place legally obtained full text or supplementary files in the approved local intake path. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `payload_draft`: Fill reviewed variant and/or measurement payload drafts with values, units, conditions and evidence levels. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `source_locators`: Provide source table/figure/supplement locators for every imported identity and measurement claim. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]

## XYN_CAND_20260805_001

- Family: xylanase
- DOI: 10.1021/acs.jafc.4c10256
- PMID: 39743673
- Stable proposal id: XYN_PAPER_829e8778
- Evidence level: metadata_only+abstract_only
- Source gap: ACS Supporting Information asset identified as jf4c10256_si_001.doc, but direct download returned HTTP 403 in this run; SI extraction and DSM4 source locator remain pending
- Next action: obtain and parse ACS SI jf4c10256_si_001.doc before family-specific dry-run importer
- Closeout ready: false

Required before apply:

- DSM4 residue-level mutation composition
- WT XynASP absolute baseline
- mutant absolute values and fold changes
- assay substrate, pH, temperature, incubation time
- source table/figure/supplement locator
- approved_for_family_importer allowlist with stable identity fields

Open checklist items:

- `approved_for_family_importer`: Record explicit family-importer approval for this proposal. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `human_review_status`: Set review_status to approved_for_family_importer only after source locators and payload drafts are reviewed. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `intake_approval`: Mark intake approved only after file hash, source locator and reviewer package checks pass. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `paper_pdf`: Place legally obtained full text or supplementary files in the approved local intake path. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `payload_draft`: Fill reviewed variant and/or measurement payload drafts with values, units, conditions and evidence levels. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `source_locators`: Provide source table/figure/supplement locators for every imported identity and measurement claim. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]

## XYN_CAND_20260805_002

- Family: xylanase
- DOI: 10.1016/j.biortech.2026.134883
- PMID: 42134585
- Stable proposal id: XYN_PAPER_f8a5a0d6
- Evidence level: abstract_only
- Source gap: no PMC/open full text; ScienceDirect full text/source table not available in current evidence set
- Next action: obtain full text and measurement source locator before export-safe variant or measurement payload
- Closeout ready: false

Required before apply:

- full-text source table/figure confirming variant composition
- WT or parent 9K-XynB baseline
- mutant absolute values for half-life, kcat/Km, secretion/activity
- units, temperature, pH, substrate and fermentation context
- source locator for each measurement
- measurement_draft entries with variant_name, metric, value/fold_change, unit, condition, evidence_level and confidence

Open checklist items:

- `approved_for_family_importer`: Record explicit family-importer approval for this proposal. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `human_review_status`: Set review_status to approved_for_family_importer only after source locators and payload drafts are reviewed. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `intake_approval`: Mark intake approved only after file hash, source locator and reviewer package checks pass. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `paper_pdf`: Place legally obtained full text or supplementary files in the approved local intake path. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `payload_draft`: Fill reviewed variant and/or measurement payload drafts with values, units, conditions and evidence levels. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
- `source_locators`: Provide source table/figure/supplement locators for every imported identity and measurement claim. [decision=needs_more_info, closed=false, approved_for_family_importer=false, export_safe=false]
