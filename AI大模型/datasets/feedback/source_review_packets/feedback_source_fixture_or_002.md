# feedback_source_fixture_or_002

Policy: source review packets are not feedback intake and cannot train any model.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/feedback/source_review_drafts/feedback_source_fixture_or_002.source_review.draft.jsonl`

| rank | bucket | score | type | size | relative path | hits | action |
|---:|---|---:|---|---:|---|---|---|
| 1 | fixture_or_reference | 10 | .json | 1160 | backend/app/data/fixtures/local_annotations/signalp.json | ph | confirm_source_then_extract_or_keep_unvalidated |
| 2 | fixture_or_reference | 10 | .json | 3422 | deploy_data/annotations/mcsa.json | ph | confirm_source_then_extract_or_keep_unvalidated |

Required checks:
- Do not import project plans, generated recommendations, benchmark fixtures, or protocol-only documents as feedback.
- Import only genuine KWB wet-lab or historical experimental outcomes.
- Keep failed and inconclusive outcomes if they are real experiments.
- Numbering must be verified before a row becomes training eligible.
