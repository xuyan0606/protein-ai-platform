# feedback_source_low_signal_005

Policy: source review packets are not feedback intake and cannot train any model.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/feedback/source_review_drafts/feedback_source_low_signal_005.source_review.draft.jsonl`

| rank | bucket | score | type | size | relative path | hits | action |
|---:|---|---:|---|---:|---|---|---|
| 1 | low_signal_candidate | 10 | .json | 7131 | docs/manuals/remaining-backlog-gate-execution-plan.json | mutant | confirm_source_then_extract_or_keep_unvalidated |
| 2 | low_signal_candidate | 10 | .md | 4042 | docs/manuals/remaining-backlog-gate-execution-plan.md | mutant | confirm_source_then_extract_or_keep_unvalidated |
| 3 | low_signal_candidate | 10 | .json | 12244 | docs/manuals/remaining-backlog-operator-dispatch-checklist.json | mutant | confirm_source_then_extract_or_keep_unvalidated |
| 4 | low_signal_candidate | 10 | .md | 5375 | docs/manuals/remaining-backlog-operator-dispatch-checklist.md | mutant | confirm_source_then_extract_or_keep_unvalidated |
| 5 | low_signal_candidate | 10 | .md | 1560 | docs/manuals/researcher-manual.md | 稳定 | confirm_source_then_extract_or_keep_unvalidated |
| 6 | low_signal_candidate | 10 | .md | 12512 | docs/superpowers/plans/2026-08-26-external-gate-runner.md | tm | confirm_source_then_extract_or_keep_unvalidated |
| 7 | low_signal_candidate | 10 | .md | 3144 | docs/superpowers/specs/2026-09-01-enzyme-platform-remediation-wave-design.md | 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 8 | low_signal_candidate | 10 | .json | 684 | frontend/tsconfig.app.json | tm | confirm_source_then_extract_or_keep_unvalidated |
| 9 | low_signal_candidate | 10 | .json | 591 | frontend/tsconfig.node.json | tm | confirm_source_then_extract_or_keep_unvalidated |
| 10 | low_signal_candidate | 10 | .json | 248170 | matvenus-session-08b460.capture.json | tm | confirm_source_then_extract_or_keep_unvalidated |

Required checks:
- Do not import project plans, generated recommendations, benchmark fixtures, or protocol-only documents as feedback.
- Import only genuine KWB wet-lab or historical experimental outcomes.
- Keep failed and inconclusive outcomes if they are real experiments.
- Numbering must be verified before a row becomes training eligible.
