# PDB-only 酶改造分析 SOP

适用范围：用户只上传 PDB/结构文件，要求提高比活力、热稳定性、底物特异性、pH 适应性或表达可溶性，但没有独立 FASTA、UniProt、底物、assay 或 WT 基线。

## 默认结论

PDB-only 输入可以做结构质控、链/残基统计、结构相似性检索、坐标顺序编号推断和探索性位点预筛。

PDB-only 输入不能直接输出可排单候选突变，也不能声称已确认酶身份、催化残基、底物口袋、UniProt 编号、比活力提升或热稳定性提升。

## 输入审计

必须先记录：

- 上传文件名、对象来源和是否可解析。
- 链、残基数、原子数、缺失残基和序列前缀。
- 是否存在独立 FASTA、UniProt、PDB ID、底物、实验条件和 WT 基线。
- 用户目标是单目标还是多目标，例如比活力 + 热稳定性。

没有独立 FASTA/UniProt 时，编号状态只能写成 `PDB-coordinate-derived` 或 `coordinate_order_inference`。

## 工具边界

| 工具 | 可用作 | 禁止写法 |
|---|---|---|
| `structure_search_foldseek` | 结构相似性和输入质控证据 | 弱 Foldseek 命中确认酶身份、EC、催化残基或底物口袋 |
| `residue_mapping_sifts` 坐标顺序推断 | 本结构内部坐标编号整理 | 把 inferred mapping 写成真实 SIFTS/UniProt 实证映射 |
| `blast_search` | completed/live 或可追溯 cache 时支持同源证据 | `submitted`、`degraded` 或未完成任务进入结论 |
| `predict_properties` | 分子量、pI 等理化背景基线 | 证明热稳定性、比活力、酶身份或突变增益 |
| `kcat_predict` | 启发式动力学背景 | 证明 specific activity、kcat 或突变后活性提升 |

## 目标拆解

比活力需要至少说明：

- specific activity 是按总蛋白还是活性蛋白归一化。
- 是否有 WT 基线、底物、温度、pH、缓冲液和重复数。
- 结构或理化性质不能替代 kcat、Km、kcat/Km 或湿实验 activity assay。

热稳定性需要至少说明：

- 目标指标是 Tm、热半衰期、残余活性、聚集温度还是储存稳定性。
- 是否有热处理条件、检测底物和 WT 基线。
- 理化性质、Foldseek 命中和静态结构不能单独证明热稳定性提升。

多目标必须同时列出协同点和冲突点。比活力提升与热稳定性可能冲突，不能用同一套候选表无差别覆盖。

## 输出规则

第一屏必须包含：

- 当前是否可下单：PDB-only 且身份/编号/目标证据不足时为不可下单。
- 主要证据：结构解析、结构相似性、编号状态、理化背景。
- 主要缺口：独立序列/UniProt、底物/assay、WT 基线、催化口袋、保守性或同源证据。
- 下一步：补 FASTA/UniProt、底物和实验条件，或执行 completed BLAST/InterPro/SIFTS/口袋定位。

报告可以输出 `exploratory_pdb_coordinate_site` 级别的探索性复核窗口，但必须写明低置信、不是最终突变推荐、不得直接排单。

报告不得输出 `experiment_ready_mutation` 或可排单候选表，除非身份、编号、保护位点、目标 assay 和 WT 基线均通过门控。

## HM.pdb 发布 Gate

发布前必须运行默认验收矩阵或 release acceptance：

```bash
python3 scripts/run_acceptance_matrix.py --json
python3 scripts/run_release_acceptance.py --json
```

验收矩阵必须包含并通过 `hm_pdb_deep_quality_gate`。

该 gate 必须覆盖：

- 弱 Foldseek 不确认身份。
- 坐标顺序推断不冒充真实 SIFTS/UniProt。
- submitted BLAST 不进入完成证据。
- 启发式 kcat 不支持比活力结论。
- 身份/编号未过时不输出可排单候选表。

## 升级条件

PDB-only 报告可以升级为候选设计报告的最低条件：

- 独立 FASTA 与 PDB 链一致性通过。
- UniProt 或同源证据确认身份和成熟链边界。
- 编号映射来源清楚，不能只依赖 coordinate order。
- 目标 assay、底物、温度、pH、缓冲液和 WT 基线明确。
- 保护位点、催化位点、口袋或保守性证据完成审计。
