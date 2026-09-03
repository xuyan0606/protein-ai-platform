# MSA Swiss-Prot Cache

P72 records the local MMseqs2 Swiss-Prot search outputs and derived
per-target alignment/conservation cache.

## Artifacts

- Hit table: `cache/msa/mmseqs_swissprot_hits.m8`
- Alignment cache: `cache/msa/*.aln.fasta`
- Conservation cache: `datasets/curation/msa_conservation/*.conservation.json`
- Build report: `reports/msa_mmseqs_swissprot_cache_build_report.json`
- Final validator: `reports/msa_conservation_cache_validation_report.json`

## Use

These features are homolog-supported computational evidence from reviewed
Swiss-Prot sequences and may be used as MSA/conservation feature inputs after
validator pass.

## Not Use

They are not wet-lab labels, not Rosetta/FoldX ddG, not reviewed numbering
decisions and not sufficient for customer/model-quality claims by themselves.
