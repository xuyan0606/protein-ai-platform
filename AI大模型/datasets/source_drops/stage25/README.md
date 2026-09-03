# Stage 25 Source Drops

Place locally authorized fulltext, supporting information, or source-table files here.

Operator checklist:

- `reports/stage25_source_acquisition_shortlist_20260806.md`

Expected paths:

- `39743673/jf4c10256_si_001.doc`
- `39743673/10.1021_acs.jafc.4c10256_fulltext.pdf`
- `42134585/10.1016_j.biortech.2026.134883_fulltext.pdf`
- `42134585/source_table_or_supplement_for_9K-XynB2`
- `42235695/10.1016_j.biortech.2026.135069_fulltext.pdf`
- `42235695/CM5_variant_and_process_source_locator`
- `42248057/10.1016_j.enzmictec.2026.110921_fulltext.pdf`
- `42248057/XyEst_rXyEst_benchmark_source_locator`

Public web search results are only acquisition leads. They do not replace local
fulltext/SI files, reviewed table or figure locators, formal decisions, SQLite
apply approval, benchmark intake, model claims, customer delivery, or release.

After placing files, run:

```bash
python3 scripts/build_stage25_post_source_drop_rerun_receipt_20260806.py
python3 scripts/run_stage25_fail_closed_validation_20260806.py
```

The rerun receipt is fail-closed and contains no SQLite-write commands.
