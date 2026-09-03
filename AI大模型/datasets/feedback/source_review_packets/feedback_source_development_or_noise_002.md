# feedback_source_development_or_noise_002

Policy: source review packets are not feedback intake and cannot train any model.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/feedback/source_review_drafts/feedback_source_development_or_noise_002.source_review.draft.jsonl`

| rank | bucket | score | type | size | relative path | hits | action |
|---:|---|---:|---|---:|---|---|---|
| 1 | development_or_noise | 30 | .json | 21366 | .tmp/admin-layout-visual-check.json | ph, tm, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 2 | development_or_noise | 30 | .json | 718909 | .tmp/frontend-lint-after.json | mutation, stability, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 3 | development_or_noise | 30 | .json | 440893 | .tmp/frontend-lint-warnings-after-any-1.json | mutation, stability, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 4 | development_or_noise | 30 | .json | 559250 | .tmp/frontend-lint-warnings-after-api-types.json | mutation, stability, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 5 | development_or_noise | 30 | .json | 649881 | .tmp/frontend-lint-warnings-after-hooks-1.json | mutation, stability, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 6 | development_or_noise | 30 | .json | 632058 | .tmp/frontend-lint-warnings-after-hooks-2.json | mutation, stability, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 7 | development_or_noise | 30 | .json | 629117 | .tmp/frontend-lint-warnings-after-hooks-3.json | mutation, stability, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 8 | development_or_noise | 30 | .json | 441227 | .tmp/frontend-lint-warnings-final.json | mutation, stability, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 9 | development_or_noise | 30 | .json | 694355 | .tmp/frontend-lint-warnings.json | mutation, stability, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 10 | development_or_noise | 30 | .json | 744925 | .tmp/frontend-lint.json | mutation, stability, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 11 | development_or_noise | 30 | .txt | 35433 | .tmp/package-contents-final.txt | mutation, ph, stability | confirm_source_then_extract_or_keep_unvalidated |
| 12 | development_or_noise | 30 | .txt | 35433 | .tmp/package-contents-sanitized.txt | mutation, ph, stability | confirm_source_then_extract_or_keep_unvalidated |
| 13 | development_or_noise | 30 | .txt | 35494 | .tmp/package-contents.txt | mutation, ph, stability | confirm_source_then_extract_or_keep_unvalidated |
| 14 | development_or_noise | 30 | .json | 39474 | docs/designs/2026-08-25-tool-orchestration-coverage.json | assay, mutation, ph | confirm_source_then_extract_or_keep_unvalidated |
| 15 | development_or_noise | 20 | .json | 272871 | .tmp/frontend-lint-after-235.json | mutation, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 16 | development_or_noise | 20 | .json | 272871 | .tmp/frontend-lint-after-result-guards.json | mutation, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 17 | development_or_noise | 20 | .json | 34063 | .tmp/frontend-lint-after-set-state-final.json | mutation, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 18 | development_or_noise | 20 | .json | 140726 | .tmp/frontend-lint-after-set-state.json | mutation, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 19 | development_or_noise | 20 | .json | 34063 | .tmp/frontend-lint-chat-agent-400.json | mutation, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 20 | development_or_noise | 20 | .json | 34063 | .tmp/frontend-lint-chat-agent-similar-400.json | mutation, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 21 | development_or_noise | 20 | .json | 272871 | .tmp/frontend-lint-current.json | mutation, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 22 | development_or_noise | 20 | .json | 34063 | .tmp/frontend-lint-markdown-table-final.json | mutation, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 23 | development_or_noise | 20 | .json | 34063 | .tmp/frontend-lint-markdown-table.json | mutation, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 24 | development_or_noise | 20 | .md | 1919 | backend/app/skills/sequence_analysis/SKILL.md | ph, stability | confirm_source_then_extract_or_keep_unvalidated |
| 25 | development_or_noise | 10 | .json | 3050 | .tmp/full-backend-pytest.json | 酶 | confirm_source_then_extract_or_keep_unvalidated |

Required checks:
- Do not import project plans, generated recommendations, benchmark fixtures, or protocol-only documents as feedback.
- Import only genuine KWB wet-lab or historical experimental outcomes.
- Keep failed and inconclusive outcomes if they are real experiments.
- Numbering must be verified before a row becomes training eligible.
