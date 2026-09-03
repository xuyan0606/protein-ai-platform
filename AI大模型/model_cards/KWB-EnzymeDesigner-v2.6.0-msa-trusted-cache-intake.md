# KWB-EnzymeDesigner v2.6.0 MSA Trusted Cache Intake

## Purpose

This card records P67: the local trusted MSA/conservation cache intake path.

## Added

- MSA trusted cache intake schema.
- Empty local intake file and full target template.
- Apply script that builds `msa_conservation_manifest.json` only from real local
  files with source metadata and checksums.
- Pipeline wiring before final MSA cache validation.

## Current State

No trusted MSA/cache rows have been accepted. The system remains blocked because
the local intake is empty and no runtime/database/cache is configured.

## Policy

No fake MSA, no single-sequence conservation, no model-quality claim.
