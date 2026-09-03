# 55 工具科学编排矩阵（v1）

本矩阵定义工具“何时调用、依赖什么、输出能否进入结论”。工具注册表是能力清单；本文件是编排和证据边界，不能把工具名本身当作证据。

> 历史快照（2026-08-25）：本文按当时的源码注册表统计 58 个工具、1 个 alias、13 个异步调度项。它不是当前线上基线；当前验收以交付包 v2 和 `/api/tools` 实测为准（catalog 55 条、线上 33 个、缺失 22 个，异步 6 个）。

完整覆盖见 `2026-08-25-tool-orchestration-coverage.json`；新增工具或线上对账请同步更新 `tool_baseline_manifest`，不要直接沿用本文历史数字。

## 总体 DAG

```text
输入门控
  -> 身份/基础画像
  -> 结构与编号
  -> 目标模块
  -> 目标证据
  -> 候选生成/评分
  -> 结构/能量/动力学验证
  -> 实验设计与 Go/Watch/No-Go
```

任何节点失败都只能进入 `blocked`、`degraded` 或 `exploratory`，不得跳到下游的 report-grade 结论。

## 编排分层

| 层 | 工具 | 前置条件 | 可输出内容 |
|---|---|---|---|
| 输入 | `bio_specialty_input_gate` | 序列/结构/目标可解析 | 输入缺口和下一步 |
| 身份 | `annotation_bundle`, `interpro_annotation`, `enzyme_identity_profile`, `enzyme_function`, `blast_search`, `literature_live_search`, `external_research_evidence`, `signal_peptide_predict` | 输入通过；外部任务必须终态 | 身份/功能证据，不能仅凭 motif 定论 |
| 结构 | `structure_search_foldseek`, `residue_mapping_sifts`, `residue_numbering_gate`, `catalytic_site_lookup`, `pocket_residue_lookup`, `site_structure_function_features` | 有 PDB/预测结构；链和编号明确 | 结构、位点、映射证据 |
| 目标 | `enzyme_objective_module_plan`, `wt_baseline_registry`, `feedback_iteration_planner` | 身份和 assay context | 目标证据需求、候选允许状态 |
| 候选 | `mutation_priority_score`, `mutation_scan`, `mutation_epistasis_check`, `protssn_score`, `kcat_predict`, `predict_properties`, `protein_benchmark` | identity gate + objective gate + numbering/protected-site gate | 候选排序或探索性假设；不能冒充实验结果 |
| 设计 | `proteinmpnn_design`, `ligandmpnn_design`, `rfdiffusion_design`, `chroma_design`, `esm_if1_design`, `sequence_search`, `progen2_generate`, `evodiff_generate`, `soluble_mpnn_design` | 明确目标、结构输入和设计约束 | 设计序列/结构候选，必须保留模型和 seed |
| 结构预测 | `esmfold_folding`, `alphafold2_folding`, `alphafold_folding`, `rosettafold_folding`, `rosettafold_allatom`, `boltz1_predict` | 序列和可用 runtime/模型 | 结构假设；必须标 runtime、版本、置信度 |
| 配体 | `ligand_preprocess`, `diffdock_docking` | 2D SDF 先转 3D；蛋白结构和 pocket 已确认 | 3D 配体、pose、拓扑；缺 runtime 必须 blocked |
| MD/能量 | `gromacs_md`, `rosetta_ddg` | topology/force field/结构/授权均满足 | 真实轨迹、能量或 ddG；没有 raw artifacts 不得入结论 |
| 治理 | `tool_capability_audit`, `tool_capability_contract`, `scientific_claim_gate`, `external_connectivity_check`, `data_lookup`, `protein_benchmark` | 任意工具结果汇总前 | 证据等级、许可边界、Go/Watch/No-Go |

## 硬门控

1. 身份未确认：禁止正式突变候选和位点结论。
2. 编号未确认：禁止把 PDB residue 映射成 UniProt/实验编号。
3. 目标证据不足：只能输出探索性候选，不能输出 ready candidate table。
4. 异步任务未终态：只能记录 receipt，不能进入 ClaimGate。
5. 2D 配体未生成 3D：禁止 Vina 或 GROMACS。
6. 缺少 topology、TPR、轨迹、XVG/EDR 或原始日志：禁止声称 MD 完成。
7. 许可/数据库条款未确认：对应工具只能 `blocked` 或 `license_review`。

## 组合策略

- 同一证据层优先并行（例如 annotation、literature、structure search），跨层必须按 DAG 顺序。
- 代理预测只能作为排序或风险提示；至少一个可追溯实验/数据库/真实 runtime 证据才能升级结论。
- 候选生成后必须经过 epistasis、保护位点、编号和目标 assay 复核。
- 任何重算都生成新的 evidence snapshot，不覆盖旧报告或旧 checkpoint。

## 当前实现状态

- 已实现：identity/objective/structure/numbering/candidate/async evidence/claim gates。
- 已实现：工具能力、最小 artifact、许可和商业使用边界元数据。
- 已新增：`app.services.tool_orchestration_contract.validate_tool_plan`，对序列、结构、身份和目标门控做无副作用的计划预检，并在确认执行阶段按 typed dependency order fail-closed。
- 已新增运行模式检查：工具必须已注册；异步工具不得被请求为同步执行；队列时限低于 registry timeout 时输出 warning。
- 历史快照（2026-08-25）：当时统计的 13 个异步工具均满足 `registry_timeout <= scheduler.time_limit`；GROMACS 已从 7200s 调整为 5400s。当前线上异步数量以 `/api/tools` 实测 6 个为准。
- 已新增组合级拒绝契约：编号依赖 SIFTS 映射，候选上位性依赖候选集，docking 依赖结构与 3D 配体，GROMACS 依赖 topology；`submitted/pending/running` 仅是 receipt，不满足终态证据。
- 已下沉：coverage JSON 的每个工具行现在包含 `requires/provides/evidence_level/runtime_mode/license_status`，并由测试校验其与 Python typed-DAG 常量一致。
- 已接入：认证 `/tools` 列表 API 与 ToolPanel 展示上述元数据；手动调用前可见前置条件、输出能力、证据等级、运行方式和许可审查状态。
- 已接入：`POST /tools/{name}/preflight` 复用同一契约；ToolPanel 在调用前提交已输入的序列/结构/配体/topology 状态，缺失依赖时 fail-closed 并显示阻断码。
- 已接入：preflight 可接收当前用户拥有的 `task_ids`，仅将持久化审计中 `completed` 的对应工具映射为 evidence；submitted/running/failed 不产生解锁。
- 已接入：preflight 还支持当前用户拥有的不可变 `snapshot_id`，并按相同 completed-provider 规则合并快照证据。
- 运行时发现：本地 ARM64 ligand-worker 可运行 GROMACS/Vina/ACPYPE/Open Babel，但 ACPYPE 自带 AmberTools 为 x86_64，已由 runtime-check 正确阻断；需 x86_64 worker 或 ARM64 原生 AmberTools 才能解锁 topology。
- 已验证架构解法：`protein-ai-ligand-worker:amd64` runtime-check 六项全通过；生产应将 `ligand_cpu` 队列绑定到 x86_64 worker，ARM64 节点不得承载 AmberTools topology。
- 待实现：由项目上下文自动选择最新适用 snapshot，而不是由客户端传递 snapshot ID。
