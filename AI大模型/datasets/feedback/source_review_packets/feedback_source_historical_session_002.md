# feedback_source_historical_session_002

Policy: source review packets are not feedback intake and cannot train any model.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/feedback/source_review_drafts/feedback_source_historical_session_002.source_review.draft.jsonl`

| rank | bucket | score | type | size | relative path | hits | action |
|---:|---|---:|---|---:|---|---|---|
| 1 | historical_session_candidate | 70 | .json | 9199 | matvenus-research/raw/11-提升目标酶对异鼠李素-3-O-葡萄糖苷等双底物的催化效率-9a8882cd.stream-events.json | activity, mutation, 实验, 底物, 活性, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 2 | historical_session_candidate | 70 | .md | 6424 | matvenus-research/reviews/11-提升目标酶对异鼠李素-3-O-葡萄糖苷等双底物的催化效率-9a8882cd.review.md | activity, mutation, 实验, 底物, 活性, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 3 | historical_session_candidate | 60 | .json | 67839 | matvenus-research/raw/12-咨询给定序列酶的改造以提升比活力的方案-065e88f7.stream-events.json | activity, mutation, 实验, 活性, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 4 | historical_session_candidate | 60 | .json | 12843 | matvenus-sessions-list-page1-size50.json | ph, 底物, 活性, 热稳定, 稳定, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 5 | historical_session_candidate | 60 | .json | 12843 | matvenus-sessions-list.json | ph, 底物, 活性, 热稳定, 稳定, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 6 | historical_session_candidate | 10 | .json | 89610 | matvenus-session-08b460.style.json | 实验 | confirm_source_then_extract_or_keep_unvalidated |

Required checks:
- Do not import project plans, generated recommendations, benchmark fixtures, or protocol-only documents as feedback.
- Import only genuine KWB wet-lab or historical experimental outcomes.
- Keep failed and inconclusive outcomes if they are real experiments.
- Numbering must be verified before a row becomes training eligible.
