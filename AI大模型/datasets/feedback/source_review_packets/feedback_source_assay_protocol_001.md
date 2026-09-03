# feedback_source_assay_protocol_001

Policy: source review packets are not feedback intake and cannot train any model.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/feedback/source_review_drafts/feedback_source_assay_protocol_001.source_review.draft.jsonl`

| rank | bucket | score | type | size | relative path | hits | action |
|---:|---|---:|---|---:|---|---|---|
| 1 | assay_protocol_reference | 40 | .docx | 187595 | Venus-15B淀粉酶项目/incoming/reference_docs/auto_selected/科为博酶制剂实验方案（α-淀粉酶A513型、复合葡糖淀粉酶GP185型）巴彦诺尔华恒生物科技有限公司.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 2 | assay_protocol_reference | 40 | .docx | 193078 | Venus-15B淀粉酶项目/incoming/reference_docs/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南丰源生物2026.4.24..docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 3 | assay_protocol_reference | 40 | .docx | 192261 | Venus-15B淀粉酶项目/incoming/reference_docs/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南新兴生物.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 4 | assay_protocol_reference | 40 | .docx | 193141 | Venus-15B淀粉酶项目/incoming/reference_docs/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南新兴生物2026.4.22.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 5 | assay_protocol_reference | 40 | .docx | 192322 | Venus-15B淀粉酶项目/incoming/reference_docs/auto_selected/科为博酶制剂实验方案（α-淀粉酶、糖化酶）河南新兴生物_.docx | ph, 实验, 温度, 酶 | confirm_source_then_extract_or_keep_unvalidated |

Required checks:
- Do not import project plans, generated recommendations, benchmark fixtures, or protocol-only documents as feedback.
- Import only genuine KWB wet-lab or historical experimental outcomes.
- Keep failed and inconclusive outcomes if they are real experiments.
- Numbering must be verified before a row becomes training eligible.
