# KWB-EnzymeDesigner v1.4.0 Workstream Scaffolds

状态：本地待建工作流脚手架完成。

## 目标

把待建清单中尚未启动的 domain、MSA/保守性、实验反馈三条工作流变成本地可执行队列和模板。

## 产物

- `contracts/domain_interval_curation_decision.schema.json`
- `contracts/msa_conservation_manifest.schema.json`
- `contracts/experiment_feedback.schema.json`
- `scripts/build_domain_interval_repair_queue.py`
- `scripts/build_msa_conservation_scaffold.py`
- `scripts/build_experiment_feedback_scaffold.py`
- `datasets/curation/domain_interval_repair_queue.jsonl`
- `datasets/curation/msa_conservation_targets.jsonl`
- `datasets/feedback/experiment_feedback.template.jsonl`
- `datasets/feedback/experiment_feedback.local.jsonl`
- `reports/domain_interval_repair_report.json`
- `reports/msa_conservation_readiness_report.json`
- `reports/experiment_feedback_readiness_report.json`

## 当前结果

- domain invalid rows：1942
- domain queued rows：1000
- MSA targets：158
- MSA present：0
- experiment feedback local rows：0
- reviewed numbered feedback rows：0
- safe pipeline steps：22
- failed steps：0

## 结论

工作流已经启动，但仍缺真实数据和缓存。下一步应先处理编号回源和结构缓存，再逐步补 domain/MSA/feedback 实数据。
