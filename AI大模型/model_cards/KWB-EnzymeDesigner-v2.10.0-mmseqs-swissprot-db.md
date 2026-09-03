# KWB-EnzymeDesigner v2.10.0 MMseqs Swiss-Prot DB

## Purpose

This card records P71: a local MMseqs2 UniProtKB/Swiss-Prot homolog database
has been downloaded, built and indexed.

## Added

- Local database prefix `cache/mmseqs_databases/uniprot_sprot`.
- Database checksum manifest and readiness report.
- MSA runtime configuration for the Swiss-Prot database.
- Release manifest fields for homolog database readiness.

## Current State

MMseqs2 runtime and homolog database readiness are available. MSA/conservation
feature generation still requires running target searches and validating output
cache files.

## Policy

No model-quality claim, no wet-lab label substitution and no conservation
feature use until per-target cache validation passes.
