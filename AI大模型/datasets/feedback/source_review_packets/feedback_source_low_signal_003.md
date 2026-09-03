# feedback_source_low_signal_003

Policy: source review packets are not feedback intake and cannot train any model.

Decision draft template: `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/datasets/feedback/source_review_drafts/feedback_source_low_signal_003.source_review.draft.jsonl`

| rank | bucket | score | type | size | relative path | hits | action |
|---:|---|---:|---|---:|---|---|---|
| 1 | low_signal_candidate | 30 | .txt | 486 | Venus-15B淀粉酶项目/淀粉酶15B序列.txt | ddg, tm, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 2 | low_signal_candidate | 30 | .md | 21195 | backend/.agents/skills/design-taste-frontend-v1/SKILL.md | activity, ph, stability | confirm_source_then_extract_or_keep_unvalidated |
| 3 | low_signal_candidate | 30 | .md | 87253 | backend/.agents/skills/design-taste-frontend/SKILL.md | activity, ph, stability | confirm_source_then_extract_or_keep_unvalidated |
| 4 | low_signal_candidate | 30 | .md | 40326 | backend/.agents/skills/imagegen-frontend-mobile/SKILL.md | activity, ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 5 | low_signal_candidate | 30 | .md | 36854 | backend/.agents/skills/imagegen-frontend-web/SKILL.md | conversion, ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 6 | low_signal_candidate | 30 | .md | 8456 | backend/.agents/skills/industrial-brutalist-ui/SKILL.md | ph, substrate, tm | confirm_source_then_extract_or_keep_unvalidated |
| 7 | low_signal_candidate | 30 | .md | 15060 | backend/.agents/skills/redesign-existing-projects/SKILL.md | activity, ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 8 | low_signal_candidate | 30 | .jsonl | 4417 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/literature/screening/sequence_numbering_precheck.jsonl | mutation, ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 9 | low_signal_candidate | 30 | .csv | 7180 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/16B-database-提高稳定性与比活力/03_相对对照派生分析表.csv | 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 10 | low_signal_candidate | 30 | .csv | 32430 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/4G_database-提高比活力/02_单条测量记录判读表.csv | 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 11 | low_signal_candidate | 30 | .csv | 23166 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/4G_database-提高比活力/03_相对对照派生分析表.csv | 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 12 | low_signal_candidate | 30 | .csv | 2035 | 实验数据/2026_08_27_酶改造突变体库-湿实验数据/酶改造突变体库-湿实验数据/4G_database-提高比活力/05_样本与批次对应表.csv | assay | confirm_source_then_extract_or_keep_unvalidated |
| 13 | low_signal_candidate | 20 | .md | 15805 | README.md | mutation, ph | confirm_source_then_extract_or_keep_unvalidated |
| 14 | low_signal_candidate | 20 | .md | 1664 | Venus-15B淀粉酶项目/incoming/README.md | ph, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 15 | low_signal_candidate | 20 | .md | 15992 | backend/.agents/skills/brandkit/SKILL.md | ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 16 | low_signal_candidate | 20 | .md | 10561 | backend/.agents/skills/high-end-visual-design/SKILL.md | ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 17 | low_signal_candidate | 20 | .md | 36442 | backend/.agents/skills/image-to-code/SKILL.md | ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 18 | low_signal_candidate | 20 | .md | 7901 | backend/.agents/skills/minimalist-ui/SKILL.md | ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 19 | low_signal_candidate | 20 | .md | 12053 | backend/.agents/skills/stitch-design-taste/DESIGN.md | ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 20 | low_signal_candidate | 20 | .md | 11851 | backend/.agents/skills/stitch-design-taste/SKILL.md | ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 21 | low_signal_candidate | 20 | .json | 3072 | deploy_data/alphafold/P00691.json | ddg, ph | confirm_source_then_extract_or_keep_unvalidated |
| 22 | low_signal_candidate | 20 | .json | 3205 | deploy_data/alphafold/P19531.json | ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 23 | low_signal_candidate | 20 | .json | 10810 | deploy_data/updates/deploy_data_update_20260718T032158Z.json | ph, tm | confirm_source_then_extract_or_keep_unvalidated |
| 24 | low_signal_candidate | 20 | .md | 20713 | docs/aliyun-live-environment-prep-2026-07-16.md | tm, 酶 | confirm_source_then_extract_or_keep_unvalidated |
| 25 | low_signal_candidate | 20 | .md | 3527 | docs/live-deploy-runbook.md | ph, 酶 | confirm_source_then_extract_or_keep_unvalidated |

Required checks:
- Do not import project plans, generated recommendations, benchmark fixtures, or protocol-only documents as feedback.
- Import only genuine KWB wet-lab or historical experimental outcomes.
- Keep failed and inconclusive outcomes if they are real experiments.
- Numbering must be verified before a row becomes training eligible.
