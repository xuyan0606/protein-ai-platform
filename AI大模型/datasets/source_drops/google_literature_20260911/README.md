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
