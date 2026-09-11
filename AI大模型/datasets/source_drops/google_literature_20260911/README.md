# Google literature source drops

This directory is reserved for primary evidence files discovered through Google
Search or Google Scholar and then verified at the publisher, repository, or
database source.

Rules:

- Search result pages and snippets are discovery evidence only.
- Every primary file must have a SHA-256 entry in
  `datasets/curation/google_literature_source_manifest.jsonl`.
- License text or a source-page capture must be stored beside the primary file.
- A missing primary file, hash, license, or row/table locator remains
  `needs_review` and cannot enter training.
- No credentials, private data, or unverified generated tables belong here.

Acquired 2026-09-11:

- `gotenzymes2_km_data_0.4simi_10fold.csv`: author repository data file from
  LiLabTsinghua/GotEnzymes2; accompanying `gotenzymes2_LICENSE.txt`. The table
  contains sequences and Km(M), but the extracted rows do not contain assay pH
  or temperature, so they remain `needs_review` for model training.
- `skid_BRENDA_Km_data_all_v1.csv`: author repository sample output from the
  SKiD pipeline; accompanying `skid_README_license_capture.md`. The table has
  pH, temperature, and references, but its protein field is an accession
  object rather than a sequence; it is research-only under CC BY-NC-ND 4.0.
- `skid_Main_dataset_v1.xlsx`: official Zenodo record 16874765 (CC BY 4.0),
  containing kcat and Km sheets with values, pH/temperature, UniProt IDs,
  PDB filenames, and references. It does not embed amino-acid sequences, so
  sequence resolution remains a separate provenance step.

The exact URLs, SHA-256 hashes, row/table locators, and import statuses are in
`datasets/curation/google_literature_source_manifest.jsonl`.
