# KWB-EnzymeDesigner v2.11.0 MSA Swiss-Prot Cache

## Purpose

This card records P72: MMseqs2 Swiss-Prot searches have produced per-target
alignment and conservation cache artifacts for the 158 MSA targets.

## Added

- `cache/msa/mmseqs_swissprot_hits.m8`
- `cache/msa/*.aln.fasta`
- `datasets/curation/msa_conservation/*.conservation.json`
- `reports/msa_mmseqs_swissprot_cache_build_report.json`
- Trusted cache intake rows generated from local MMseqs2 evidence.

## Current State

MSA/conservation cache validation passes when all target files and checksums
match. These are homolog-supported computational features, not wet-lab labels.

## Policy

No single-sequence pseudo-conservation, no wet-lab label substitution and no
customer/model-quality claim without the remaining numbering, ddG, feedback and
benchmark gates.
