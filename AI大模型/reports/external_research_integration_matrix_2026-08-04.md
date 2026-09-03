# 外部研究到训练、模型声明、客户交付与 release 的接入矩阵

日期：2026-08-04  
范围：Biomni fresh snapshot、closed-loop、OED，以及 KWB 本地现有门控

## 结论

本轮可以把外部研究接入四类工程入口，但“接入入口”不等于“打开能力”：

| 入口 | 可以接入的内容 | 当前状态 | 不能自动发生的事 |
|---|---|---|---|
| 训练 | clean-room kinetics schema、raw/source lineage、replicate summary、predictor feature contract | 可作为输入候选和数据治理适配器 | 不得绕过编号、授权、QC、重复组和每头阈值写训练标签 |
| 模型声明 | predictor plugin boundary、WT mismatch fail-fast、benchmark/evidence provenance、model-card evidence refs | 可写入模型卡和声明门控 | 不得把 feature-ready、proxy ddG、benchmark cache 当成质量声明 |
| 客户交付 | Biomni resource/tool registry 思路、KWB tool contract、license/IP/biosecurity/customer acceptance receipts | 可形成内部交付审查包 | 不得把本地 review manifest 当客户序列包或交付批准 |
| release | artifact manifest、guard links、source checksum、allowed/forbidden claims、execution receipts | local release manifest 可持续生成 | `release_ready` 仍必须由所有独立 gate 共同满足 |

## 外部项目的可迁移边界

### Biomni fresh snapshot

本地 fresh 核心快照为 `cache/external/Biomni-fresh-core/`，已包含旧快照缺失的：

- `biomni/tool/tool_registry.py`
- `biomni/tool/support_tools.py`
- `biomni/utils.py`
- `biomni/tool/tool_description/`
- `pyproject.toml`

其可借鉴链路是：

`tool description -> read_module2api -> ToolRegistry -> ToolRetriever -> execution wrapper -> structured result`

KWB 不直接照搬的原因：

- `ToolRegistry` 只检查三个元数据键；
- 没有 KWB 所需的 license scope、runtime receipt、版本/checksum、参数 schema 兼容性、claim 权限和输出 provenance；
- `support_tools.run_python_repl` 是持久化执行命名空间，不适合直接作为客户或 release 工具执行面；
- A1/assistant wrapper 属于 Biomni 自身交互方式，不是 KWB 的平台边界。

KWB 映射建议：

1. 保留“工具描述与实现分离”；
2. 在注册时增加 `tool_version`、`input_schema`、`output_schema`、`license_scope`、`runtime_receipt_ref`、`claim_scopes`、`timeout_policy`；
3. 执行返回统一 envelope：`request_id`、`tool_id`、`input_hash`、`output_refs`、`source_refs`、`quality_flags`、`claim_eligibility`；
4. formal/training/customer/release 动作必须经过独立 gate，不能由 registry 本身授予。

### closed-loop

可迁移：

- `BasePredictor` 插件边界；
- predictor registry 和组合 predictor；
- `predict_unsupervised` / supervised 分工；
- WT mismatch fail-fast；
- 轮次化 DBTL 编排和评估入口。

不迁移：

- 硬编码 assistant wrapper；
- 固定 subprocess/路径假设；
- 未带 KWB provenance、QC、编号和授权的 predictor 输出直接进入训练或声明。

KWB 映射建议：

`PredictorPlugin -> Feature/Prediction Contract -> Evidence Gate -> Head Trainer/Report`

其中 WT mismatch 必须在输入归一化阶段失败，而不是在报告阶段静默修正。

### OED

OED 的 BRENDA/SABIO-RK 处理适合研究其数据合同：

- mutation token 解析；
- pH、温度、UniProt、PubMed 规范化；
- KM/kcat/kcatKM 单位转换；
- 条件键和记录来源；
- 从同一 `EntryID/context` 派生 kcat/Km 的规则；
- raw record 与 summary 分层。

OED 的原始代码和 GPL-3.0 许可证不能直接复制进闭源平台。KWB 当前使用独立 clean-room 实现：

- `scripts/normalize_kinetics_records_cleanroom.py`
- `scripts/summarize_kinetics_replicates_cleanroom.py`

实现边界：

- raw rows、source checksum、source row index 必须保留；
- summary 只允许在质量干净且 condition hash 一致时聚合；
- summary 输出 median/mean/min/max/std/observation_count 和 raw refs；
- 默认 `training_eligible=false`；
- 任何训练导入仍需走外部数据 license、编号、去重、人工审核和训练阈值门控。

## 四类接入的具体合同

### 训练接入

外部研究产物只能先落到三层：

1. `raw_external_observation`：原始值和来源回执；
2. `normalized_kinetics_observation`：单位、条件、mutation token 的独立归一；
3. `replicate_summary_candidate`：可复核的聚合摘要。

只有经过 source/license、numbering、dedup、QC、review receipt 和 head threshold 的记录，才可转成 formal training import。当前 KWB 五头训练仍为 blocked；activity_risk 有 6 条 source-level eligible rows，但 0 explicit replicates、2 groups，不能满足五头训练阈值。

### 模型声明

可安全写入模型卡的内容：

- 使用了哪些 predictor/plugin 和版本；
- 哪些 feature cache 仅为 model input；
- 哪些 benchmark 为 evaluation-only；
- 哪些 ddG 是 proxy，哪些是 physics backend；
- WT mismatch、结构链、编号、license 和 QC 的失败条件；
- 允许声明与禁止声明的逐项状态。

当前不能写：

- 五头模型质量已经完成；
- 稳定性、活性、底物适配或 assay success 已达到生产质量；
- proxy ddG 等价于湿实验稳定性；
- benchmark cache 已自动证明客户效果。

### 客户交付

可生成的是内部 customer-delivery review package，必须包含：

- artifact/source manifest；
- data/tool license decision；
- sequence IP/FTO decision；
- biosecurity screening；
- human acceptance；
- allowed claims / forbidden claims；
- reproducible execution receipts。

缺少任一审批或 receipt 时，包只能标记为 `internal_review_only`，不能标记为 customer-ready、approved_for_ordering 或 production use。

### release

local release manifest 应继续作为 fail-closed 汇总，而不是审批源。它至少应绑定：

- data lake artifact count 和 missing artifact；
- safe pipeline success；
- positive claim quarantine；
- model claim consistency；
- guard link coverage；
- license/IP/biosecurity/customer gates；
- allowed/forbidden claims；
- local-only boundary。

当前 release 的准确结论仍是：

- `safe_for_model_claim=false`
- `model_quality_ready=false`
- `customer delivery=false`
- `release_ready=false`

## 最小下一步

1. 将 clean-room kinetics 适配器接入“候选数据层”而不是训练层；
2. 将 closed-loop predictor contract 作为 KWB predictor plugin 的设计参考，补齐版本、输入输出 schema、provenance 和 fail-fast 测试；
3. 将 Biomni registry 的资源描述映射到现有 KWB tool contract，但保留 KWB license/runtime/claim gates；
4. 让模型卡、客户交付报告、local release manifest 只读取各自 validator 的结果；
5. 继续保持人工 decision 为空时的 fail-closed 行为。

## 证据路径

- `cache/external/Biomni-fresh-core/`
- `cache/external/closed-loop/`
- `cache/external/OED/`
- `scripts/normalize_kinetics_records_cleanroom.py`
- `scripts/summarize_kinetics_replicates_cleanroom.py`
- `reports/claim_readiness_matrix.json`
- `reports/five_head_training_execution_contract_report.json`
- `reports/local_release_manifest.json`
- `findings.md`
- `progress.md`
