# KWB-EnzymeDesigner v2.2.0 Advanced Scaffold

## Purpose

This card records the first code step toward a top-tier KWB enzyme model.

## Added Architecture

- sequence PLM feature slot
- MSA/conservation feature slot
- structure-neighborhood GNN feature slot
- ddG backend feature slot
- wet-lab feedback calibration slot
- five-head multi-task output
- Pareto ranking
- uncertainty and missing-modality flags

## Current Status

`scaffold_only_fail_closed`

The scaffold can run locally on a case JSON and produce structured advanced
outputs, but it is not a trained neural model and cannot support model-quality
claims.

## Blocked Until

- reviewed numbering is available
- MSA/cache is ready
- real experiment feedback is imported
- ddG backend artifacts exist
- benchmarks and claim readiness pass

## Policy

No trained-quality claim, no external tool execution claim, no customer delivery
claim, and no production sync claim from this scaffold alone.
