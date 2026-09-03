# 调研发现

## 研究方法与证据边界

- 当前执行环境无法解析 `loschmidt.chemi.muni.cz`、`pross.weizmann.ac.il`、GitHub 和 `caver.cz` DNS；没有把网页访问失败当成工具可用证据。
- 本轮主要依据是项目已有设计文档、工具注册和能力审计；外部工具的运行能力、版本和许可证必须在部署时另做 runtime receipt。

## 位点输出能力分类

| 工具/数据源 | 可输出残基位点 | 证据类型 | 当前平台状态 | 关键限制 |
|---|---|---|---|---|
| UniProt reviewed / M-CSA | catalytic / binding / mechanism 位点 | curated L1 | 本地 annotation facade，需完整数据源 | 必须先做序列、PDB author、UniProt 编号映射 |
| InterProScan / Pfam / PROSITE | family/domain/site 区段和保守模体 | profile/signature L2 | `interpro_annotation` / `interproscan_sequence_submit` 接口已存在 | family/domain 不等于催化位点，需配合 M-CSA |
| Swiss-Prot BLAST / HMMER | 同源残基位点迁移的依据 | homolog L3 | `blast_search` 后台任务已有 | `submitted` 不是完成证据，需完成命中/覆盖度/e-value |
| Foldseek | 结构相似命中，不直接输出可下单位点 | structure L3/L4 | `structure_search_foldseek` 可用 | TM-score 和模板标题不能单独确认催化位点 |
| P2Rank / fpocket | pocket、pocket edge、残基坐标 | geometry L4 | 当前缺失，`pocket_channel_interface=not_computed` | 只是口袋几何，不证明增活 |
| PLIP | 底物/配体接触残基、氢键、盐桥、π作用 | complex geometry L4 | 当前缺失 | 需存在真实复合物，不预测亲和力 |
| CAVER | 底物通道、入口残基 | tunnel geometry L4 | 当前缺失 | 需合理构象和通道参数，不是活性测量 |
| HotSpot Wizard | 酶工程热点、子位点、可改残基 | activity design L4 | 当前未接入，未实际运行 | 需家族/催化中心/底物约束，只是设计假设 |
| FireProt / PROSS | 增稳单点或组合设计位点 | stability design L4 | 当前未接入 | 需同源对齐、结构和活性保留检查 |
| FoldX / Rosetta cartesian_ddg | 给定突变的 ΔΔG、冲突和重包装证据 | energy L4 | `rosetta_ddg` 已接口，实时门控 | 必须有真实二进制、scorefile、日志；不能用启发式代替 |
| 平台 `mutation_priority_score` | 位点排序和建议替换 | proxy | 已有 | 是 proxy ranker，不是 FoldX/Rosetta/HotSpot Wizard 的实现 |

## 结论

1. 比活力位点的最小可靠链路是：`BLAST/InterProScan -> M-CSA/UniProt -> P2Rank 或 PLIP -> HotSpot Wizard/二壳层扫描`。
2. 热稳定位点的最小可靠链路是：`FireProt/PROSS -> FoldX/Rosetta ddG -> 催化中心距离和活性风险复核`。
3. 对无 PDB accession 的 SWISS-MODEL，先用 FASTA 完成 BLAST/InterProScan 身份，再用全局序列对齐建立编号；不能靠 Foldseek 模板标题直接认定酶身份。
4. 当前平台最缺的不是又一个自然语言报告器，而是 `P2Rank/PLIP/CAVER` 的真实位点工件和 `HotSpot Wizard/FireProt/PROSS` 的外部设计证据。

## 平台内部审计修正

- `tool_capability_audit` 原先漏登记 `catalytic_site_lookup` 和 `build_site_structure_function_features`，导致它们被审计为 `unknown` 并持续阻断报告级使用。
- 已补充两个能力合同：催化位点工具是 `curated_or_motif_guardrail`；结构位点特征工具是 `residue_geometry_feature_table`。
- 实际能力审计已返回 `unknown_count=0`；两个工具仍必须保留来源、编号、链和结构工件才能进入报告级使用。
