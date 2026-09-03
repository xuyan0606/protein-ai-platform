# MMseqs2 Homolog Database

P71 records the local UniProtKB/Swiss-Prot MMseqs2 database used as the first
real homolog search backend.

## Local Cache

- Database prefix: `cache/mmseqs_databases/uniprot_sprot`
- Manifest: `reports/mmseqs_homolog_database_manifest.json`
- Report: `reports/mmseqs_homolog_database_report.json`

## Use

The database may be used by MMseqs2 search jobs after runtime readiness passes.
It is a reviewed Swiss-Prot source and is intentionally smaller than UniRef for
the first local unlock.

## Not Use

The database alone is not an MSA/conservation feature cache. Search outputs and
per-target conservation files still need to be generated, checksummed and
validated before model feature use.
