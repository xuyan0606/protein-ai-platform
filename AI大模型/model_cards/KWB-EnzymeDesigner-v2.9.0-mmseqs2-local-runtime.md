# KWB-EnzymeDesigner v2.9.0 MMseqs2 Local Runtime

## Purpose

This card records P70: MMseqs2 has been downloaded into local cache and probed
as a runnable macOS binary.

## Added

- Local MMseqs2 runtime cache under `cache/external/MMseqs2`.
- Runtime manifest with binary sha256, archive sha256 and version probe.
- MSA runtime readiness wiring for project-local binary paths.
- Release manifest fields for MMseqs2 binary and MSA runtime state.

## Current State

The local binary is present and executable. MSA search remains blocked because
no homolog database is configured and trusted MSA/conservation cache validation
is still not ready.

## Policy

No MSA fabrication, no homolog search without a real database, no conservation
feature generation and no model-quality claim.
