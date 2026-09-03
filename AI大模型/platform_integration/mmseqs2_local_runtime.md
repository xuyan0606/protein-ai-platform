# MMseqs2 Local Runtime

P70 records the local MMseqs2 runtime package used for MSA/conservation work.

## Local Cache

- Source root: `cache/external/MMseqs2`
- Binary: `cache/external/MMseqs2/bin/mmseqs`
- Manifest: `reports/mmseqs2_local_runtime_manifest.json`
- Report: `reports/mmseqs2_local_runtime_report.json`

## Use

The binary can be used as the local MMseqs2 executable after a real homolog
database is configured and checked.

## Not Use

This does not generate MSA or conservation features by itself. Homolog database
version, checksum manifest and cache validation are still required before model
feature use.
