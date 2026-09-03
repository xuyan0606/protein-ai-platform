# Mutation Label 编号治理计划

## 当前结论

`mutation_label_integrity_report.json` 显示：

- 500 条增强监督 mutation labels 中，仅 25 条 wild type 与当前 UniProt 序列位点一致。
- 475 条存在 `wild_type_mismatch_current_sequence`。
- verified ratio = 0.05。
- 1942 条 `domain_architecture` 区间均为 0/0，当前不能用于位点级 domain 特征。
- 113836 条 PDB 路径记录在本地没有对应文件，当前不能直接做坐标解析。

## 修复优先级

### P0：标签编号回源

目标：

- 保留原始文献/数据库 mutation code。
- 找到标签对应的 UniProt accession、版本、isoform 或原始序列。
- 建立 `reported_position -> canonical_position` 映射。

阻断条件：

- 没有原始序列或版本信息时，不允许把该行作为强监督标签。

### P1：弱标签分层

把现有 475 条 mismatch 样本降级为：

- weak evidence
- literature/reference evidence
- not supervised label

只有 `numbering_verified_by_sequence=true` 的样本进入监督训练。

### P2：Domain 区间修复

当前 `domain_architecture.start_pos/end_pos` 全为 0，不能计算：

- mutation_in_pfam_domain
- domain_relative_position
- catalytic domain boundary

需要重新导入 HMMER/PFAM 结果或从原始注释表恢复区间。

### P3：结构文件缓存

当前 DB 有 PDB 路径记录，但本地文件不存在。需要：

- 建立只读结构缓存目录。
- 校验 PDB/mmCIF 文件 hash。
- 允许从上传结构或 AlphaFold/ESMFold 结果计算位点级结构特征。

### P4：进入可声明小模型

最小门槛：

- verified mutation labels >= 100。
- verified ratio >= 0.5。
- validation/test 均高于 majority baseline。
- 不使用 dTm/ddG 等直接标签字段作为输入。
