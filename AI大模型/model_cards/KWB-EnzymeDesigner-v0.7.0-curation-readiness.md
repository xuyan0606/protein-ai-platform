# KWB-EnzymeDesigner v0.7.0 Curation Readiness

状态：本地证据分层和结构缓存审计完成，监督模型质量声明继续阻断。

## 目标

把未通过编号校验的 mutation labels 从强监督训练集中隔离，保留为可审计 weak evidence，并形成可执行的编号回源队列。

## 产物

- `datasets/curated/enzyme_mutation_training_table_audited.jsonl`
- `datasets/curated/enzyme_mutation_weak_evidence.jsonl`
- `datasets/curation/numbering_curation_queue.jsonl`
- `datasets/curation/weak_evidence_index.jsonl`
- `reports/numbering_curation_queue_report.json`
- `reports/weak_evidence_index_report.json`
- `reports/structure_cache_audit_report.json`

## 关键结果

- audited rows：500
- verified supervised labels：25
- weak evidence rows：475
- numbering curation queue：475
- queue priority：P0 213、P1 249、P2 13
- weak evidence groups：145 UniProt groups
- PDB sample existing：0
- AlphaFold sample existing：0

## 使用策略

Weak evidence 允许用于：

- 检索上下文
- 报告证据，但必须带编号警告
- 编号回源队列

Weak evidence 禁止用于：

- 强监督训练标签
- 自动 go/no-go 决策
- 结构距离、口袋距离或催化网络结论

## 下一步

1. 按 P0 队列回源 UniProt 版本、isoform 和文献编号。
2. 建设本地只读 PDB/mmCIF/AlphaFold 结构缓存。
3. 修复 domain architecture 区间。
4. verified labels >= 100 后重新训练监督 baseline。
