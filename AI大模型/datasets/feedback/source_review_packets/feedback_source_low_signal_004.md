# feedback_source_low_signal_004

Policy: source review packets are not feedback intake and cannot train any model.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/feedback/source_review_drafts/feedback_source_low_signal_004.source_review.draft.jsonl`

| rank | bucket | score | type | size | relative path | hits | action |
|---:|---|---:|---|---:|---|---|---|
| 1 | low_signal_candidate | 20 | .md | 5777 | docs/manuals/external-infrastructure-acceptance-checklist.md | mutant, ph | confirm_source_then_extract_or_keep_unvalidated |
| 2 | low_signal_candidate | 20 | .json | 8493 | docs/manuals/remaining-backlog-external-input-packet.json | mutant, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 3 | low_signal_candidate | 20 | .md | 6886 | docs/manuals/remaining-backlog-external-input-packet.md | mutant, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 4 | low_signal_candidate | 20 | .json | 10202 | docs/ops/production-schema-drift-report-20260828.json | assay, mutation | confirm_source_then_extract_or_keep_unvalidated |
| 5 | low_signal_candidate | 20 | .md | 1928 | docs/superpowers/specs/2026-09-01-enzyme-workflow-enforcement-design.md | 稳定, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 6 | low_signal_candidate | 20 | .md | 3962 | frontend/README.md | mutation, tm | confirm_source_then_extract_or_keep_unvalidated |
| 7 | low_signal_candidate | 20 | .json | 205445 | frontend/package-lock.json | ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 8 | low_signal_candidate | 10 | .md | 302 | .pytest_cache/README.md | tm | confirm_source_then_extract_or_keep_unvalidated |
| 9 | low_signal_candidate | 10 | .md | 7857 | backend/.agents/skills/gpt-taste/SKILL.md | ph | confirm_source_then_extract_or_keep_unvalidated |
| 10 | low_signal_candidate | 10 | .md | 3648 | backend/.audit-report.md | tm | confirm_source_then_extract_or_keep_unvalidated |
| 11 | low_signal_candidate | 10 | .md | 302 | backend/.pytest_cache/README.md | tm | confirm_source_then_extract_or_keep_unvalidated |
| 12 | low_signal_candidate | 10 | .txt | 515 | backend/requirements-core.txt | ph | confirm_source_then_extract_or_keep_unvalidated |
| 13 | low_signal_candidate | 10 | .json | 3510 | backend/skills-lock.json | ph | confirm_source_then_extract_or_keep_unvalidated |
| 14 | low_signal_candidate | 10 | .md | 6332 | deploy_data/README.md | ph | confirm_source_then_extract_or_keep_unvalidated |
| 15 | low_signal_candidate | 10 | .json | 2701 | deploy_data/alphafold/I3P686.json | ph | confirm_source_then_extract_or_keep_unvalidated |
| 16 | low_signal_candidate | 10 | .json | 2760 | deploy_data/alphafold/P00692.json | ph | confirm_source_then_extract_or_keep_unvalidated |
| 17 | low_signal_candidate | 10 | .json | 2772 | deploy_data/alphafold/P06278.json | ph | confirm_source_then_extract_or_keep_unvalidated |
| 18 | low_signal_candidate | 10 | .json | 4193 | deploy_data/live_manifest.json | ph | confirm_source_then_extract_or_keep_unvalidated |
| 19 | low_signal_candidate | 10 | .md | 4101 | docs/aliyun-managed-deployment.md | ph | confirm_source_then_extract_or_keep_unvalidated |
| 20 | low_signal_candidate | 10 | .md | 1665 | docs/manuals/2026-09-01-daily-report.md | 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 21 | low_signal_candidate | 10 | .md | 1280 | docs/manuals/2026-09-02-daily-report.md | 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 22 | low_signal_candidate | 10 | .md | 3521 | docs/manuals/external-gate-runner.md | mutant | confirm_source_then_extract_or_keep_unvalidated |
| 23 | low_signal_candidate | 10 | .json | 15087 | docs/manuals/remaining-backlog-execution-tickets.json | mutant | confirm_source_then_extract_or_keep_unvalidated |
| 24 | low_signal_candidate | 10 | .md | 6401 | docs/manuals/remaining-backlog-execution-tickets.md | mutant | confirm_source_then_extract_or_keep_unvalidated |
| 25 | low_signal_candidate | 10 | .json | 6066 | docs/manuals/remaining-backlog-external-input-validation-report.json | mutant | confirm_source_then_extract_or_keep_unvalidated |

Required checks:
- Do not import project plans, generated recommendations, benchmark fixtures, or protocol-only documents as feedback.
- Import only genuine KWB wet-lab or historical experimental outcomes.
- Keep failed and inconclusive outcomes if they are real experiments.
- Numbering must be verified before a row becomes training eligible.
