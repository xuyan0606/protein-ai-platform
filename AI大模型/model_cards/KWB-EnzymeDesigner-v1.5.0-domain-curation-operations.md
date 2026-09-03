# KWB-EnzymeDesigner v1.5.0 Domain Curation Operations

状态：本地域区间审校运营链路完成，未连接服务器，未修改 SQLite 源数据。

## 本轮目标

把无效 domain architecture 区间转化为可审校、可验证、可应用、可追踪的本地工作流，并纳入确定性安全流水线。

## 新增能力

- `scripts/build_domain_interval_batches.py`
- `scripts/build_domain_interval_decision_templates.py`
- `scripts/validate_domain_interval_decisions.py`
- `scripts/apply_domain_interval_curation.py`
- `scripts/build_domain_interval_batch_status.py`
- `datasets/curation/domain_batches/`
- `datasets/curation/domain_decision_templates/`
- `datasets/curation/domain_interval_decisions.jsonl`
- `datasets/curation/domain_intervals_curated.jsonl`
- `reports/domain_interval_batch_report.json`
- `reports/domain_interval_decision_template_report.json`
- `reports/domain_interval_decision_validation_report.json`
- `reports/domain_interval_apply_report.json`
- `reports/domain_interval_batch_status_report.json`

## 治理规则

- 模板文件永远不参与 apply。
- 空决策文件表示尚无真实人工审校，不代表已修复。
- `set_interval` 必须引用队列中的 domain record。
- `start_pos`、`end_pos` 必须为合法整数，且不超过序列长度。
- `confidence` 必须不低于 `0.5`。
- apply 只写本地 JSONL，不修改 SQLite 源数据。

## 当前结果

- invalid domain rows：1942
- queue rows：1000
- batches：5
- batch covered rows：250
- decision rows：0
- decision coverage：0.0
- usable curated rows：0
- safe pipeline：27 steps，0 failed
- master readiness：`blocked_for_model_claim`

## 结论

域区间工作流已经具备可执行运营入口，但数据尚未被人工审校。当前不能把 domain-relative position、mutation-in-domain 等位点特征当作可用事实。
