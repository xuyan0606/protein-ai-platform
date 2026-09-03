# feedback_source_fixture_or_001

Policy: source review packets are not feedback intake and cannot train any model.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/feedback/source_review_drafts/feedback_source_fixture_or_001.source_review.draft.jsonl`

| rank | bucket | score | type | size | relative path | hits | action |
|---:|---|---:|---|---:|---|---|---|
| 1 | fixture_or_reference | 80 | .json | 4946 | backend/app/data/fixtures/benchmark_cases/venus_15b.json | mutant, mutation, ph, 实验, 活性, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 2 | fixture_or_reference | 60 | .txt | 1053 | deploy_data/benchmarks/venus-15b/source/淀粉酶背景.txt | ph, 实验, 活性, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 3 | fixture_or_reference | 40 | .json | 6111 | backend/app/data/fixtures/local_annotation_samples.json | activity, mutation, ph, screening | confirm_source_then_extract_or_keep_unvalidated |
| 4 | fixture_or_reference | 40 | .json | 11343 | deploy_data/annotations/base.json | activity, ddg, ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 5 | fixture_or_reference | 40 | .docx | 187595 | deploy_data/benchmarks/venus-15b/docs/reference/auto_selected/科为博酶制剂实验方案（α-淀粉酶A513型、复合葡糖淀粉酶GP185型）巴彦诺尔华恒生物科技有限公司.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 6 | fixture_or_reference | 40 | .docx | 193078 | deploy_data/benchmarks/venus-15b/docs/reference/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南丰源生物2026.4.24..docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 7 | fixture_or_reference | 40 | .docx | 192261 | deploy_data/benchmarks/venus-15b/docs/reference/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南新兴生物.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 8 | fixture_or_reference | 40 | .docx | 193141 | deploy_data/benchmarks/venus-15b/docs/reference/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南新兴生物2026.4.22.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 9 | fixture_or_reference | 40 | .docx | 192322 | deploy_data/benchmarks/venus-15b/docs/reference/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南新兴生物_.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 10 | fixture_or_reference | 40 | .docx | 187595 | deploy_data/benchmarks/venus-15b/source/incoming/reference_docs/auto_selected/科为博酶制剂实验方案（α-淀粉酶A513型、复合葡糖淀粉酶GP185型）巴彦诺尔华恒生物科技有限公司.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 11 | fixture_or_reference | 40 | .docx | 193078 | deploy_data/benchmarks/venus-15b/source/incoming/reference_docs/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南丰源生物2026.4.24..docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 12 | fixture_or_reference | 40 | .docx | 192261 | deploy_data/benchmarks/venus-15b/source/incoming/reference_docs/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南新兴生物.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 13 | fixture_or_reference | 40 | .docx | 193141 | deploy_data/benchmarks/venus-15b/source/incoming/reference_docs/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南新兴生物2026.4.22.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 14 | fixture_or_reference | 40 | .docx | 192322 | deploy_data/benchmarks/venus-15b/source/incoming/reference_docs/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南新兴生物_.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 15 | fixture_or_reference | 30 | .json | 2404 | backend/app/data/fixtures/local_annotations/base.json | activity, ph, screening | confirm_source_then_extract_or_keep_unvalidated |
| 16 | fixture_or_reference | 30 | .json | 17336 | deploy_data/benchmarks/venus-15b/docs/asset_inventory.json | ph, 实验, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 17 | fixture_or_reference | 30 | .json | 17336 | deploy_data/benchmarks/venus-15b/source/incoming/discovery/asset_inventory.json | ph, 实验, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 18 | fixture_or_reference | 30 | .txt | 486 | deploy_data/benchmarks/venus-15b/source/淀粉酶15B序列.txt | ddg, tm, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 19 | fixture_or_reference | 20 | .json | 1656 | backend/app/data/fixtures/local_annotations/interpro.json | activity, ph | confirm_source_then_extract_or_keep_unvalidated |
| 20 | fixture_or_reference | 20 | .json | 530 | backend/app/data/fixtures/local_annotations/mcsa.json | mutation, ph | confirm_source_then_extract_or_keep_unvalidated |
| 21 | fixture_or_reference | 20 | .json | 15621 | deploy_data/annotations/interpro.json | activity, ph | confirm_source_then_extract_or_keep_unvalidated |
| 22 | fixture_or_reference | 20 | .md | 608 | deploy_data/benchmarks/venus-15b/README.md | ph, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 23 | fixture_or_reference | 20 | .json | 1337 | deploy_data/benchmarks/venus-15b/bundle_manifest.json | ph, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 24 | fixture_or_reference | 20 | .md | 1664 | deploy_data/benchmarks/venus-15b/source/incoming/README.md | ph, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 25 | fixture_or_reference | 20 | .json | 4127 | deploy_data/benchmarks/venus-15b/source/incoming/reference_docs/selected_manifest.json | 实验, 酶 | confirm_source_then_extract_or_keep_unvalidated |

Required checks:
- Do not import project plans, generated recommendations, benchmark fixtures, or protocol-only documents as feedback.
- Import only genuine KWB wet-lab or historical experimental outcomes.
- Keep failed and inconclusive outcomes if they are real experiments.
- Numbering must be verified before a row becomes training eligible.
