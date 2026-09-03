# KWB-EnzymeDesigner v0.8.0 Curation Application Scaffold

状态：本地编号回源应用脚手架和结构缓存 manifest 完成。

## 目标

把编号回源从“报告发现”推进到“可执行数据管线”：

- 定义回源决策格式。
- 安全应用回源决策。
- 防止模板或未审核数据误提升为强监督标签。
- 为结构缓存建设生成 expected manifest。

## 产物

- `contracts/numbering_curation_decision.schema.json`
- `datasets/curation/numbering_curation_decisions.jsonl`
- `datasets/curation/numbering_curation_decisions.template.jsonl`
- `scripts/apply_numbering_curation.py`
- `datasets/curated/enzyme_mutation_training_table_repaired.jsonl`
- `reports/numbering_curation_apply_report.json`
- `contracts/structure_cache_manifest.schema.json`
- `config/structure_cache.local.example.json`
- `scripts/build_structure_cache_manifest.py`
- `reports/structure_cache_expected_manifest.json`

## 当前结果

- 回源决策文件为空。
- 应用脚本运行后，强监督标签仍为 25 条。
- weak evidence 没有被自动提升。
- structure cache expected manifest：500 entries，present 0，missing 500。

## 安全规则

- 只有 `map_to_canonical` 且 canonical 字段完整的决策，才可提升为强监督标签。
- `keep_unresolved_weak` 保持弱证据状态。
- `reject_label` 从 repaired 表排除。
- 示例模板不作为真实决策输入。

## 下一步

1. 对 P0 队列做人工/程序回源。
2. 逐批填充 `numbering_curation_decisions.jsonl`。
3. 每批应用后重新跑 integrity/readiness。
4. 建设本地结构缓存并重新跑 structure cache audit。
