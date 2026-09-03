# 研发里程碑

## M0：本地研发区建立

状态：complete

验收：
- 本地目录存在。
- 本地-only 边界已写明。
- 模型合同和工具事件合同已存在。

## M1：数据对象和样本标准

状态：complete

目标交付：
- `datasets/case_schema.md`
- `datasets/sample_case.json`
- 数据质量评分规则

通过标准：
- 覆盖序列、结构、底物、反应、实验条件、突变、证据来源。
- 支持成功和失败样本。
- 支持私有数据和公开数据证据分层。

## M2：Benchmark 第一版

状态：complete

目标交付：
- `benchmarks/eval_protocol.md`
- `benchmarks/scorecard.md`
- 至少 6 个评测案例

通过标准：
- 每个案例有输入、期望行为、禁忌行为和评分标准。
- 能验证结构门控、编号门控、证据分层和突变推荐质量。

当前进度：
- 已完成评测协议和评分卡。
- 已新增 6 个关键流程案例。
- 本地 benchmark harness 跑通，6/6 passed。

## M3：规则 MVP

状态：complete

目标交付：
- `prototype/kwb_enzyme_designer_mvp.md`
- mock 输入输出样例
- 本地工具调用流程设计

通过标准：
- 不训练模型也能给出稳定、多头、可追溯输出。
- 能明确降级和 blocked 原因。

## M4：本地服务原型

状态：complete

目标交付：
- 本地 HTTP 服务草案或实现
- smoke 测试

通过标准：
- `GET /health` 正常。
- `POST /v1/enzyme-design` 返回符合合同的结果。

当前进度：
- 已实现无依赖 CLI 原型 `prototype/kwb_enzyme_designer_rule.py`。
- 已实现无依赖 HTTP 原型 `prototype/kwb_enzyme_designer_service.py`。
- 已通过 `scripts/smoke_local_service.py`。

## M5：第一版规则/fixture baseline

状态：complete（仅 baseline 范围；真实监督小模型未完成）

目标交付：
- `mutation_rank_head`
- `stability_head`
- 模型版本卡
- benchmark 报告

通过标准：
- 固定 benchmark 优于规则 MVP。
- 输出置信度和证据来源。

当前进度：
- 已建立 `v0.1.0-rule-mvp` 模型卡。
- 已建立特征字典和训练数据准备计划。
- 已实现特征抽取、训练表构建、baseline ranker 训练和评估脚本。
- 已生成本地 fixture baseline 模型文件。
- fixture benchmark 评估 accuracy = 0.833；该结果只验证代码与合同流程，不能作为真实模型质量或生产声明。
- 真实 KWB 数据接入和 family-level split 管线已建立，但严格监督标签仍未达到真实小模型训练门槛。

## M7：真实 KWB 数据接入

状态：complete

目标交付：
- KWB Lipase DB 特征抽取器。
- 实验反馈特征抽取器。
- 工具调用审计样本抽取器。
- 数据质量报告。

通过标准：
- 只读读取真实数据。
- 不修改生产数据。
- 能生成脱敏训练表。

当前进度：
- 已实现本地数据发现脚本。
- 已实现数据质量报告脚本。
- 已实现 KWB Lipase DB 只读特征抽取器。
- 已实现本地 enzyme DB 只读抽取器。
- 已生成数据湖 manifest。
- 已生成训练 readiness 报告。
- 已实现实验反馈和工具审计抽取器，当前本地 `backend/protein_ai.db` 缺对应表，脚本按缺表状态输出。
- 本地 `deploy_data/lipase/lipase.db` ready，已抽取 lipase 特征 24 行。
- 本地 `backend/protein_ai.db` 已抽取 enzyme DB features 500 行、enzyme mutation labels 500 行。
- 数据质量总分 84，`ready_for_training=true`。

## M8：模型校准和数据切分治理

状态：complete

目标交付：
- baseline 校准建议。
- family-level split 报告。
- 训练/评估泄漏检查。

通过标准：
- 不为追求满分而自动改权重。
- 输出误差原因和权重建议。
- 输出 family/project group split。

当前进度：
- 已生成 baseline 校准建议 2 条。
- 已生成 family split 报告，当前本地训练表 12 行、3 个 group。
- 已生成监督 mutation protein-group split 报告，500 行、145 个 group、无 group leakage。

## M9：监督小模型流水线

状态：complete

目标交付：
- enzyme mutation 监督训练表。
- protein-group train/validation/test split。
- 无依赖监督 baseline 模型和评估报告。

通过标准：
- 不把 dTm/ddG 等直接标签测量字段作为输入特征。
- 训练、切分、评估可重复运行。
- 质量不足时明确阻断，不包装成生产模型。

当前进度：
- 已生成 `datasets/curated/enzyme_mutation_training_table.jsonl`，500 行、145 个 UniProt group。
- 标签分布：go 161、watch 181、no_go 158。
- split：train 373、validation 60、test 67，无 group leakage。
- baseline 使用 `majority_class` 作为当前最优可复现策略；validation/test accuracy = 0.317/0.239。
- readiness：`ready_for_supervised_training_pipeline=true`，`ready_for_supervised_small_model_claim=false`。

## M10：结构/功能代理特征增强

状态：complete

目标交付：
- 从本地 enzyme DB 合并 PDB、AlphaFold、PFAM、EC、kinetic、reviewed 等非泄漏上下文特征。
- 生成增强训练表。
- 对增强表训练独立 baseline 并出报告。

当前进度：
- 已生成 `datasets/curated/enzyme_mutation_training_table_enriched.jsonl`，500 行。
- 145 个 UniProt group 全部匹配 DB 上下文。
- 500 行有 PDB 证据，498 行有 AlphaFold 证据。
- 增强 baseline validation/test accuracy = 0.317/0.239，未提升。
- 结论：粗粒度结构代理特征不足，下一阶段必须做位点级结构和保守性特征。

## M11：国际对标和高级运行展示

状态：complete

目标交付：
- 国际先进模型路线调研。
- 运行事件 schema 扩展。
- 前端高级运行面板 demo 事件。
- 平台工具 adapter 草案。

当前进度：
- 已新增 `research/international_benchmark_2026.md`。
- 已扩展 `contracts/tool_event.schema.json`，加入阶段、进度、证据计数和展示指标。
- 已新增 `scripts/generate_runtime_trace_demo.py`，生成 8 段运行事件。
- 已新增 `platform_integration/kwb_tool_adapter_stub.py`，明确 GPT-5.6 主控 + KWB 工具模型的调用边界。

## M12：数据完整性门控和位点级序列特征

状态：complete

目标交付：
- mutation label 编号完整性审计。
- verified 监督子集。
- 编号修复建议报告。
- 位点级序列窗口特征表。

当前进度：
- 已新增 `scripts/audit_mutation_label_integrity.py`。
- 500 条增强监督标签中仅 25 条通过 `wild_type == current_sequence[position]` 校验，verified ratio = 0.05。
- mismatch 475 条，均为 `wild_type_mismatch_current_sequence`。
- （历史快照）domain architecture 当时 1942 条区间均无效；截至 2026-08-29，最新一致性快照显示 1785 条单区间和 155 条 multi-occurrence sidecar 可用于位点特征，2 条仍 unresolved。
- PDB 路径 113836 条，但本地文件存在数为 0，当前不能做坐标解析。
- 编号修复建议显示无单一主导 offset，不能用简单偏移自动修复。
- 已新增 `scripts/build_site_level_sequence_features.py`，对 25 条 verified 标签生成位点级序列窗口特征。

结论：
- 当前小模型质量阻断优先级是数据编号治理，不是换算法。
- 未验证标签必须降级为 weak evidence，不能作为强监督标签。

## M13：弱证据分层、编号回源队列和结构缓存审计

状态：complete

目标交付：
- weak evidence index。
- numbering curation queue。
- structure cache audit。
- readiness 阻断项更新。

当前进度：
- 已新增 `scripts/build_numbering_curation_queue.py`。
- 已新增 `scripts/build_weak_evidence_index.py`。
- 已新增 `scripts/audit_structure_cache.py`。
- 编号回源队列 475 行：P0 213、P1 249、P2 13。
- weak evidence index 475 行、145 个 UniProt group。
- weak evidence 禁止作为 supervised training label、automatic go/no-go decision、structure distance claim。
- structure cache audit 显示 PDB/AlphaFold 样本本地存在数为 0，坐标级特征未就绪。

## M14：编号回源应用脚手架和结构缓存 manifest

状态：complete

目标交付：
- 编号回源决策 JSON schema。
- 空决策文件和示例模板。
- 回源决策应用脚本。
- 结构缓存 manifest schema、配置模板和 expected manifest。

当前进度：
- 已新增 `contracts/numbering_curation_decision.schema.json`。
- 已新增 `datasets/curation/numbering_curation_decisions.jsonl` 和 `.template.jsonl`。
- 已新增 `scripts/apply_numbering_curation.py`；当前无真实决策，repaired 表仍只有 25 条强监督标签。
- 已新增 `contracts/structure_cache_manifest.schema.json`。
- 已新增 `config/structure_cache.local.example.json`。
- 已新增 `scripts/build_structure_cache_manifest.py`，生成 500 个 expected structure entries，present 0、missing 500。

## M15：编号回源运营工作包

状态：complete

目标交付：
- P0 curation batches。
- 决策验证脚本。
- 强化后的 apply 门控。
- curation dashboard。

当前进度：
- 已新增 `scripts/build_curation_batches.py`。
- 已生成 P0 前 5 个批次，覆盖 125/213 条 P0 记录。
- 已新增 `scripts/validate_numbering_curation_decisions.py`。
- 已强化 `scripts/apply_numbering_curation.py`：`map_to_canonical` 必须通过当前 canonical sequence WT 校验，且 confidence >= 0.5。
- 已新增 `scripts/build_curation_dashboard.py`。
- 当前决策文件为空，validation 0 invalid，apply 后强监督标签仍为 25。

## M16：安全训练入口

状态：complete

目标交付：
- 从 repaired 全量表中导出 strict supervised table。
- weak evidence 明确排除在训练入口外。
- readiness 使用 strict supervised rows 判断模型声明门槛。

当前进度：
- 已新增 `scripts/build_repaired_supervised_table.py`。
- `datasets/curated/enzyme_mutation_training_table_repaired.jsonl` 500 行中，仅 25 行进入 `enzyme_mutation_supervised_repaired_verified.jsonl`。
- excluded rows 475，原因均为 `not_usable_as_supervised_label`。
- strict 表标签分布：go 8、watch 9、no_go 8。
- strict 表 split 和 baseline sanity 已跑通；样本太少，不作为模型质量依据。

## M17：安全训练流水线 Runner

状态：complete

目标交付：
- strict training entrypoint checker。
- 串行 safe training pipeline runner。
- 防止 manifest/readiness 并行竞态。

当前进度：
- 已新增 `scripts/check_safe_training_entrypoint.py`。
- 已新增 `scripts/run_safe_training_pipeline.py`。
- 安全入口检查：25 行、0 failures、warning 为 `below_model_claim_row_threshold`。
- 串行 pipeline：16 steps run、0 failed。
- 产物：`reports/safe_training_entrypoint_check.json`、`reports/safe_training_pipeline_run.json`。

## M18：回源决策模板和批次状态跟踪

状态：complete

目标交付：
- P0 batch decision templates。
- batch decision coverage report。
- dashboard 展示决策覆盖率。

当前进度：
- 已新增 `scripts/build_curation_decision_templates.py`。
- 已新增 `scripts/build_curation_batch_status.py`。
- 生成 5 个 P0 decision template 文件，共 125 行。
- batch status：5 batches、125 rows、0 decided rows、coverage 0.0。
- safe pipeline runner 已扩展为 18 steps，0 failed。

## M19：待建清单总控看板

状态：complete

目标交付：
- 汇总所有待建工作流状态。
- 给出阻断原因和下一步命令。
- 纳入 safe pipeline。

当前进度：
- 已新增 `scripts/build_master_readiness_board.py`。
- safe pipeline runner 已扩展为 19 steps，0 failed。
- `reports/master_readiness_board.json` 汇总 7 条工作流：numbering curation、structure cache、domain intervals、MSA conservation、KWB feedback、model training、platform integration。
- 当前 overall status：`blocked_for_model_claim`。
- ready streams：0/7。

## M20：待建工作流脚手架

状态：complete

目标交付：
- domain interval repair queue。
- MSA/conservation target scaffold。
- experiment feedback schema/template。
- master readiness board 接入这三条工作流。

当前进度：
- 已新增 `contracts/domain_interval_curation_decision.schema.json`。
- 已新增 `contracts/msa_conservation_manifest.schema.json`。
- 已新增 `contracts/experiment_feedback.schema.json`。
- 已新增 `scripts/build_domain_interval_repair_queue.py`，当前 domain rows 1942、invalid 1942、queued 1000。
- 已新增 `scripts/build_msa_conservation_scaffold.py`，当前 targets 158、present 0、missing 158。
- 已新增 `scripts/build_experiment_feedback_scaffold.py`，当前 local feedback rows 0、reviewed numbered rows 0。
- safe pipeline runner 已扩展为 22 steps，0 failed。

## M6：平台本地接入

状态：in_progress

目标交付：
- `kwb_enzyme_designer` 工具接入设计。
- 前端运行面板设计。
- 本地测试计划。

通过标准：
- 不影响线上。
- 用户确认后才进入发布流程。

当前进度：
- 已完成 `ui/runtime_panel_design.md`。
- 已完成后端工具接入合同和本地 adapter stub。
- 还未改平台源码。
