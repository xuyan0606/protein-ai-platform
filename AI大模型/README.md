# 科为博 AI 大模型本地研发区

本目录用于研发科为博自有酶蛋白模型体系，当前目标是先定义本地方案、数据合同、模型接口和评测基线。

## 本地边界

- 仅在本地研发，不自动同步到服务器。
- 未经明确指令，不执行 ECS/SSH/生产部署。
- 本目录内容可用于后续平台接入设计，但默认不影响现有线上服务。

## 目标模型

对外统一命名为 `KWB-EnzymeDesigner`。

它不是单一黑盒分数模型，而是一个多任务酶改造模型：

- 突变候选排序
- 稳定性预测
- 活性风险评估
- 底物适配评分
- 实验成功率预测

## 当前研发状态

### 2026-08-29 状态快照

- 本地 benchmark：6/6 案例通过。
- 文献 measurement registry：24 批、870 条唯一候选、28 个 PMCID，全部为 evidence-only。
- 构建体复核队列：870 条预填记录，当前均为 `queued_blocked`，等待真实 construct 序列和人工回执。
- 五头模型：`ready_head_count=0`，`training_execution_allowed=false`。
- 模型声明与发布：`safe_for_model_claim=false`、`release_ready=false`。

以上数字来自本地最新回归和校验报告；候选数量增长不等于监督训练解锁。

- `0.1.0-rule-mvp`：规则 MVP、本地 HTTP 服务、6-case benchmark 已通过。
- `0.2.0-baseline-ranker`：fixture 训练表和规则校准 baseline 已完成，accuracy = 0.833。
- `0.3.0-data-readiness`：本地 Lipase DB/enzyme DB 只读抽取、数据质量和数据湖清单已完成。
- `0.4.0-supervised-pipeline`：500 条 enzyme mutation labels 已转为监督训练表，并完成 protein-group split 和监督 baseline。
- `0.5.0-feature-enrichment-start`：结构/功能注释代理特征增强表、增强 baseline、运行事件 demo、国际对标调研已完成。
- `0.6.0-data-integrity-gate`：mutation label 编号审计、verified 子集、编号修复建议、位点级序列窗口特征管线已完成。
- `0.7.0-curation-readiness`：weak evidence 分层、编号回源队列、结构缓存审计已完成。
- `0.8.0-curation-application-scaffold`：编号回源决策合同、应用脚本、结构缓存 manifest 和本地配置模板已完成。
- `0.9.0-curation-operations`：P0 回源批次、决策验证、强化应用门控、curation dashboard 已完成。
- `1.0.0-safe-training-entrypoint`：strict repaired supervised 训练入口完成，weak evidence 不会进入训练。
- `1.1.0-safe-pipeline-runner`：安全训练入口检查和串行治理 pipeline runner 已完成。
- `1.2.0-curation-template-status`：P0 决策模板和 batch 覆盖率状态跟踪已完成。
- `1.3.0-master-readiness-board`：待建清单总控看板已完成。
- `1.4.0-workstream-scaffolds`：domain 修复、MSA 保守性、实验反馈三条待建工作流脚手架已完成。

关键结论：

- 监督训练流水线已 ready。
- 当前非泄漏监督 baseline validation/test accuracy = 0.317/0.239，不能宣称为高质量预测模型。
- 粗粒度结构代理特征增强后，当前 baseline 仍未改善，说明下一步要做位点级三维结构和保守性特征。
- 当前 500 条 mutation labels 只有 25 条能与当前 UniProt 序列编号直接验证；这是监督小模型质量的首要阻断。
- 未验证的 475 条标签已降级为 weak evidence，只能用于检索/报告上下文，不能用于强监督训练。
- 本地结构缓存当前未就绪，不能做坐标级位点特征。
- 已有回源决策模板和应用脚本；没有真实决策时不会自动提升 weak evidence。
- 已生成 P0 前 5 个回源工作包，覆盖 125 条最高优先级记录。
- 训练脚本后续应使用 `enzyme_mutation_supervised_repaired_verified.jsonl`，而不是 full repaired/enriched 表。
- 可用 `scripts/run_safe_training_pipeline.py` 串行重跑治理到安全训练入口，避免并行 manifest/readiness 竞态。
- P0 batch 有独立 decision templates；模板不会被 apply 读取，真实覆盖率只看 `numbering_curation_decisions.jsonl`。
- `reports/master_readiness_board.json` 汇总编号、结构缓存、domain、MSA、实验反馈、模型训练、平台接入 7 条工作流。
- domain interval repair queue、MSA conservation targets、experiment feedback template 已生成，均为本地-only scaffold。
- 下一步必须加入结构、口袋、保守性、家族和真实 KWB 湿实验反馈特征。

## 推荐接入方式

短期先作为平台工具接入：

```text
GPT-5.6 主控
  -> 调用 KWB-EnzymeDesigner
  -> 调用结构/注释/MD/配体工具
  -> 汇总证据分层报告
```

长期如果 `KWB-EnzymeDesigner` 的规划能力成熟，再升级为主控模型。

## 目录结构

```text
AI大模型/
  README.md
  LOCAL_ONLY.md
  roadmap.md
  研发计划.md
  milestones.md
  contracts/
    kwb_enzyme_case.schema.json
    kwb_enzyme_designer.schema.json
    tool_event.schema.json
  datasets/
    README.md
    case_schema.md
    sample_case.json
    feature_dictionary.md
    training_plan.md
    curated/
    features/
    feedback/
  benchmarks/
    README.md
    eval_protocol.md
    scorecard.md
    cases/
  prototype/
    baseline_ranker_model.json
    service_api.md
    kwb_enzyme_designer_mvp.md
    kwb_enzyme_designer_rule.py
    kwb_enzyme_designer_service.py
  scripts/
    fasta_numbering_mapper.py
    build_training_table.py
    calibrate_baseline_ranker.py
    data_quality_report.py
    discover_local_data.py
    evaluate_baseline_ranker.py
    extract_feedback_features.py
    extract_features.py
    extract_lipase_features.py
    build_supervised_mutation_table.py
    enrich_supervised_mutation_features.py
    audit_mutation_label_integrity.py
    suggest_numbering_repairs.py
    build_site_level_sequence_features.py
    make_supervised_mutation_split.py
    train_supervised_mutation_baseline.py
    generate_runtime_trace_demo.py
    extract_tool_audit_features.py
    make_family_split.py
    run_local_benchmark.py
    smoke_local_service.py
    train_baseline_ranker.py
  reports/
    baseline_ranker_eval.json
    baseline_calibration_suggestions.json
    data_quality_report.json
    family_split_report.json
    local_data_discovery.json
    sample_case_result.json
    local_benchmark_report.json
    enzyme_mutation_training_table_report.json
    enzyme_mutation_enrichment_report.json
    mutation_label_integrity_report.json
    numbering_repair_suggestions.json
    supervised_mutation_split_report.json
    supervised_mutation_enriched_split_report.json
    supervised_mutation_baseline_eval.json
    supervised_mutation_enriched_baseline_eval.json
    data_lake_manifest.json
    training_readiness_report.json
    runtime_trace_demo.jsonl
  model_cards/
    KWB-EnzymeDesigner-v0.1.0-rule-mvp.md
    KWB-EnzymeDesigner-v0.4.0-supervised-pipeline.md
    version_log.md
  platform_integration/
    agent_workflow.md
    backend_tool_contract.md
    kwb_tool_adapter_stub.py
    local_gate_plan.md
  research/
    international_benchmark_2026.md
  ui/
    component_spec.md
    runtime_panel_design.md
```

## 构建体序列复核工具

拿到 parent/construct FASTA 后，可先运行逐位编号校验：

```bash
python3 scripts/fasta_numbering_mapper.py \\
  --parent parent.fasta \\
  --construct construct.fasta \\
  --mutation N185D
```

工具只输出序列/编号状态；`blocked_*` 结果不能进入训练，也不代表人工审核或授权完成。

## Domain architecture 状态（2026-08-29）

最新一致性快照见 `reports/domain_state_consistency_20260829.json`：1942 条证据中，1785 条为可用于位点特征的单区间，155 条通过 multi-occurrence sidecar 保留全部区间，2 条仍 unresolved。该快照仅说明特征范围一致，不解除监督训练、模型声明或 release gate。

2 条 unresolved 的人工审核入口为 `reports/domain_unresolved_review_packet_20260829.json`；在独立 HMMER、UniProt 或人工证据回执前，必须保持 `keep_unresolved`，不得写入训练特征。

结构缓存当前为样本级就绪而非全量就绪：`training_readiness_report.json` 中 `coordinate_features_scope=sample_only`、`full_cache_ready=false`。现有 502 个 PDB 样本可用于本地解析回归，但不能据此声称 113836 条结构记录已完成坐标特征覆盖。

总看板 `reports/master_readiness_board.json` 当前严格 `ready_streams=1/8`（MSA trusted cache）；`partial_ready`、`runtime_ready`、`local_gate_passed` 仅表示局部证据或本地入口存在，不等同于训练、模型质量声明或 release 放行。

三处状态（domain、training readiness、master board）的自动一致性核验见 `reports/readiness_snapshot_consistency_20260829.json`，当前 `ok=true`。

生产级统一验收入口为 `scripts/validate_production_model_gate.py`，当前报告 `reports/production_model_gate_20260829.json` 为 `production_ready=false`。该 gate 对真实监督标签、五头模型、MSA、结构链、湿实验授权、模型质量、release 和部署逐项做合取校验。

生产模型包必须先通过 `scripts/validate_production_model_package.py`：要求 SHA-256 校验过的神经网络权重、推理入口和 feature/training/evaluation/release 证据。当前无此模型包，故生产 gate 保持阻断；backend 的 `kwb_enzyme_designer` 不会回退为规则或 proxy 推理。
