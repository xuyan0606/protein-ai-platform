# MSA Trusted Cache Intake

P67 creates the local intake path for trusted precomputed MSA and conservation
features.

## Files

- Template: `datasets/curation/msa_trusted_cache_intake.template.jsonl`
- Local intake: `datasets/curation/msa_trusted_cache_intake.local.jsonl`
- Applied manifest: `reports/msa_conservation_manifest.json`
- Intake report: `reports/msa_trusted_cache_intake_report.json`
- Final validator: `reports/msa_conservation_cache_validation_report.json`

## Required Intake Fields

- `uniprot_id`
- `sequence_length`
- `source`
- `source_database`
- `database_version`
- `msa_path`
- `msa_sha256`
- `conservation_feature_path`
- `conservation_sha256`
- `reviewer`
- `reviewed_at`

## Policy

The intake path accepts only real local files with checksums. It does not run
MMseqs2, generate MSA, or synthesize conservation. Empty or partial intake
remains fail-closed.
