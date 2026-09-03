# feedback_source_historical_feedback_001

Policy: source review packets are not feedback intake and cannot train any model.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/feedback/source_review_drafts/feedback_source_historical_feedback_001.source_review.draft.jsonl`

| rank | bucket | score | type | size | relative path | hits | action |
|---:|---|---:|---|---:|---|---|---|
| 1 | historical_feedback_candidate | 110 | .json | 35825 | matvenus-research/raw/01-SD改造-数据反馈-08b460b1.stream-events.json | activity, mutation, stability, tm, 实验, 底物, 活性, 热稳定, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 2 | historical_feedback_candidate | 110 | .md | 26870 | matvenus-research/reviews/01-SD改造-数据反馈-08b460b1.review.md | activity, mutation, stability, tm, 实验, 底物, 活性, 热稳定, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 3 | historical_feedback_candidate | 100 | .json | 34756 | matvenus-research/raw/14-得到改造位点湿实验数据后的后续处理咨询-5a6b53dd.stream-events.json | ddg, tm, 实验, 底物, 活性, 温度, 热稳定, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 4 | historical_feedback_candidate | 100 | .md | 31542 | matvenus-research/reviews/14-得到改造位点湿实验数据后的后续处理咨询-5a6b53dd.review.md | ddg, tm, 实验, 底物, 活性, 温度, 热稳定, 稳定, 突变, 酶 | confirm_source_then_extract_or_keep_unvalidated |

Required checks:
- Do not import project plans, generated recommendations, benchmark fixtures, or protocol-only documents as feedback.
- Import only genuine KWB wet-lab or historical experimental outcomes.
- Keep failed and inconclusive outcomes if they are real experiments.
- Numbering must be verified before a row becomes training eligible.
