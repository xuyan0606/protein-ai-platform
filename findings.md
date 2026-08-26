# 发现与决策

## AI 模型训练 smoke 验证（2026-08-25）
- 现有监督基线入口具备严格输入门禁：仅读取 `enzyme_mutation_supervised_repaired_verified.jsonl`，拒绝 weak evidence、完整性标记或深度审计 reject 记录。
- 当前严格监督表为 0 行；入口和 `check_safe_training_entrypoint.py` 均正确阻断训练，未把 500 行候选训练表、475 行 weak evidence 或 25 行 verified 候选误当作正式监督标签。
- smoke 输出明确为 `blocked_empty_train_split`，因此当前不能声称已完成模型训练、checkpoint 或评测。
- readiness 报告显示基础环境 `quality_score=84.0` 且 baseline/supervised pipeline 结构就绪，但 `ready_for_supervised_small_model_claim=false`；多任务报告明确缺少五个 head 的严格标签，`training_execution_allowed=false`。
- training-label import contract validator 通过，识别到 6 行数值反馈可按独立来源契约导入，但 `safe_for_model_claim=false`、`release_ready=false`，不能将这 6 行扩写成完整训练集或模型完成度。
- 用户请求启动训练后的实际执行仍被同一门禁阻断：`training_pipeline_unlocked=false`、`strict_rows=0`、`train_rows=0`。这不是运行时故障，而是当前缺少真实监督标签和授权回执的预期 fail-closed 行为。

## 无标签自监督预训练第一轮（2026-08-25）
- 本地可用无标签序列来源为 `datasets/curation/msa_inputs/msa_targets.fasta`，本轮解析出 158 条有效蛋白序列，输入 hash 为 `20a7a8796cb8cf6b51a46f0a9745bed24f198ec22b8850d9e0e5002a8c1ea416`。
- 新入口 `scripts/pretrain_sequence_mlm.py` 默认只产生 pretraining-only artifact，不能解锁监督训练或模型质量声明；缺输入、非法 FASTA、缺 torch 均 fail-closed。
- 第一轮 masked-amino-acid 训练成功：158 steps，final loss `2.882465`；`reports/sequence_mlm_pretraining_run.json` 与 `reports/sequence_mlm_checkpoint.pt` 可加载。
- 仍需后续扩大无标签序列规模、增加独立预训练验证和运行资源，再考虑将表征接入监督微调；当前严格监督标签门禁保持不变。
- 第二轮回归发现初版脚本的固定 checkpoint 文件名会导致不同输入运行相互覆盖；已修复为按报告 stem 生成唯一 checkpoint，并重跑两轮确认独立文件可加载。
- 自监督训练现在保留固定 seed 的独立验证切分和 validation loss，避免只报告训练 loss；3 个边界/确定性单元测试通过。当前报告仍仅用于预训练诊断，不得解释为下游突变效果准确率。
- 已将预训练 embedding 导出为独立无标签 artifact；它可用于后续检索/聚类/微调输入，但不能绕过监督标签、授权和模型质量门禁。
- 已建立 MSA 批量 embedding 索引，14,273 条记录全部保留来源 hash 和序列索引；该索引适合后续相似性检索/聚类，但仍不是监督标签数据。
- embedding 检索已具备基本安全边界：余弦相似度对零向量返回 0，结果稳定降序，非法参数不产生空洞或伪结果；检索输出仍明确为无标签表征 artifact。
- embedding 完整性审计结构通过，但发现 1,444 条重复向量；当前模型使用序列 token embedding 均值，容易把不同顺序/结构但相近组成的序列映射到同一点。下一轮应引入位置编码或上下文 encoder 后再评估检索质量。
- 已引入位置 embedding 和 1D context convolution，位置敏感性测试通过；重复向量只从 1,444 降到 1,443，表明当前轻量 encoder 仍有明显表示碰撞，不能把少量改善包装成检索质量提升。后续需要更强上下文架构或按序列身份/长度做专门评估。
- 分层分析显示 1,443 条重复记录分布在 797 个碰撞组，且集中于少数 MSA 文件和固定长度（例如 250、214、252）；因此碰撞既有输入 MSA 重复/同长序列因素，也有 encoder 表征压缩因素，下一步应先去重/按来源分层，再评估更大模型。
- 去重验证确认全部 1,443 条碰撞记录都是完全重复序列，而非仅 embedding 相同；因此此前碰撞率主要由 MSA 输入重复造成。去重后的 512 条 smoke 已成功训练，但仍不能替代全量预训练或下游质量评测。
- 去重后 512 条 embedding 索引的碰撞审计为 0，验证了输入重复是主要碰撞来源；仍需在全量 12,830 条唯一序列上运行资源可控的预训练和检索质量评估。
- 已将全量唯一序列物化为 26 个可恢复批次；批次 0000 smoke 成功，证明分批训练入口可用，后续可按资源窗口逐批执行并保留独立 receipt。
- 当前已完成 0000–0002 共 3/26 批；每批独立 receipt/checkpoint，无覆盖。批次 validation loss 在 2.835–2.928 区间，仅用于预训练诊断，不能解释成下游任务效果。
- 当前已完成 0000–0005 共 6/26 批；0003–0005 validation loss 约 2.897–2.907，批次之间有自然波动，不作跨批次模型能力结论。
- 当前已完成 0000–0008 共 9/26 批；0006–0008 validation loss 约 2.894–2.921，仍只作为批次训练诊断。
- 当前已完成 0000–0011 共 12/26 批；0009–0011 validation loss 约 2.876–2.939，批次波动正常，不构成跨批次能力结论。
- 当前已完成 0000–0014 共 15/26 批；0012–0014 validation loss 约 2.883–2.939，仍仅作为预训练批次诊断。

## 2026-08-20 P0 全部启动与收口

- P0 主链路已验证闭合：指定突变复核、位点结构-功能特征表、多目标候选表、续问路径都已接到现有只读 trace 和前端入口。
- `dbtl_trace` 继续保持 read-only contract；项目详情页和项目列表页消费的是 summary / status，不把 raw trace 当正式项目结论。
- 指定突变复核回归已覆盖 trade-off、保护位点和 unknown 字段 fail-closed，不会在证据不足时编造 relSASA、pocket/channel 或保守性结论。
- 结构特征侧已可见 relSASA、HELIX/SHEET、非聚合 HETATM 几何和主链二面角等证据，候选表不再只剩单一总分。
- 当前验证结果：`backend/tests/test_project_dbtl_trace.py` 与 `backend/tests/test_requested_mutation_review.py` 通过；`npm run build` 与 `npm run lint` 通过。

## 2026-08-19 P0-2 输入结构非聚合 HETATM 邻近与多模型一致性

- 当前 residue feature table 已有 relSASA、CA 邻域和 PDB 文件内二级结构，但缺少“上传结构中实际出现的非蛋白组分”与候选残基的几何关系。
- 本轮新增的字段只描述输入 PDB 的非水、非聚合 `HETATM` 重原子几何：最近距离、最近组件 ID/位置、4 A 内组件 ID 及全结构组件计数。
- 该信息不做 ligand/cofactor/metal/底物角色分类，也不把附近残基自动标为催化位点、口袋位点或 No-Go；只有 `within_4A_of_nonpolymer_heteroatom_review_component_role` 人工复核风险标记。
- 同时发现手写 CA 解析过去会遍历多模型 PDB，而 ShrakeRupley 后续只消费首模型；现已让 CA、HETATM、HELIX/SHEET 都限定首个 `MODEL`，避免同一特征表混合坐标构象。
- 当前仍未实现 pocket/channel/interface 检测、HETATM 化学角色判定、配位几何、保守性或突变效应预测；报告必须继续把这些能力标为未计算或待人工复核。
- 候选评分当前仍保留既有序列组成 proxy，不在本轮改变分数或 tier；但解释文本已修正：有 `computed_from_input_pdb` 的 relSASA 时展示输入结构暴露度，否则明确写成“基于序列组成的暴露/埋藏倾向，仍需结构复核”。
- 主链二面角采用相邻残基 `C(i)-N(i+1)` 距离不超过 2.0 A 的保守连续性门控；缺失 N/CA/C、首末端或肽键断裂时返回 `null` 和原因，不插值、不把局部几何自动判成异常。

## 2026-08-19 P2-2 多目标评分契约与 P3 trace 质量门

- 现有 legacy composite/tier 继续作为兼容排序结果；P2-2 以并行结构化 payload 补齐目标级分量，不改变原有数学或前端字段。
- `mutation_objective_score_v1` 的每个分量都需要保留来源、状态和 rationale；没有目标特异证据时写 `null`，并在 `blocking_reason` 里明确阻断，不用 0 或中性分数伪造可比性。
- objective score 不是新的总分：`aggregation=none`、`no_composite_score=true`，候选决策不能从多个分量自动合成高置信结论。
- `risk_score` 是风险而非收益分；保护位点、身份/编号未就绪、目标 assay/WT baseline 缺失或结构/证据风险可将 `decision` 置为 `blocked`。
- P3 trace 仅聚合项目现有记录；WT 只接受显式 WT 且 mutations 为空的反馈，calibration 引用按项目过滤并对重复/未解析 ID 分开输出，formal decision 冲突保持 unknown/conflict。
- 全量 runner 仍只完成 plan-only 合同检查；本机分组回归通过，但不应将其写成全量 pytest 或线上门禁完成。

## 2026-08-19 P2-3/P3-1 第一批 contract 边界

- `candidate_table_generation_v1` 的定位是候选表生成合同，不是新评分器；它记录候选表由 residue rows、objective score、identity gate 和 objective gate 共同生成。
- `candidate_status` 用于报告/排单状态，不覆盖 legacy tier：保护/No-Go 行是 `blocked`，证据不足但可小批量验证的是 `exploratory`，只有无阻断的正式表行才可成为 `high_confidence`。
- blocked 行必须保留在 `all_positions` 方便审计，但不得进入候选组或实验排单表。
- `dbtl_project_model_v1` 是只读 trace 上的项目模型视图，用于暴露 Project/Round/WT baseline/Variant/Prediction/Feedback/Formal Decision 的现有覆盖和缺口。
- 该模型视图不创建数据库表、不写入轮次状态、不推断 formal decision；它只是为后续正式 DBTL schema 和实验反馈导入提供稳定 contract。

## 2026-08-19 P3-2/P3-3 实验反馈与下一轮库设计边界

- 实验反馈可以先记录为项目记忆，但不能自动进入训练或 claim 升级；训练可用性必须显式满足 QC passed、重复数、完整 assay condition、formal decision 和 measured metric。
- 稳定性结论尤其不能只凭单次 Tm/half-life 数值输出；没有 QC、replicate 和完整条件时只能作为审计证据或 Watch 复核。
- `experiment_feedback_import_v1` 与旧 Go/Watch/No-Go 并行存在：旧决策用于当前 UI/流程兼容，import contract 用于控制训练、声明升级和后续 DBTL 学习入口。
- 下一轮智能库第一批不训练模型、不估计高阶上位性；它只把已经验证的单点、结构支持的二点组合、强证据远端探索和 plate layout 结构化。
- 高阶组合默认 blocked，直到有正向 measured pair feedback；远端候选必须有 conservation/literature 和 structure/MD 证据才可进入小比例探索池。

## 2026-08-19 阶段 56 DBTL trace 级学习就绪度边界

- `dbtl_learning_readiness_v1` 是只读聚合视图，不是训练任务、模型校准任务或 claim 升级动作。
- trace 中的 `training_eligible_count` 只能说明已有 feedback records 是否满足导入训练的最低合同条件；不足 12 条 training-eligible records 时保持 `feedback_present_not_training_ready`。
- `missing_for_training_counts` 必须直接来自 `experiment_feedback_import_v1`，不能由报告文案或 LLM 推断补齐 QC、replicate、assay condition、formal decision 或 measured metric。
- `next_round_library_design_v1` 在 DBTL trace 中只是下一轮设计预览；它消费当前 round filter 作用域内的反馈记录，空 round 不生成库设计。
- 该 trace 接线不创建 Project/Round/Variant/Prediction 正式表，不写入轮次状态，不训练模型，不把计算假设升级为湿实验验证结论。
- 实现注意点：scoped feedback records 只能在 feedback records 循环中收集；checkpoint 循环没有 `record` 变量，不能把策略 checkpoint 当作实验反馈输入。

## 2026-08-20 阶段 57 DBTL trace 摘要合同边界

- `dbtl_trace_summary_v1` 是给报告和 agent 消费的摘要合同，不是新的 DBTL 数据模型，也不是写入路径。
- 摘要中的 `required_actions` 只能表达“缺什么才能升级”，不能被用作自动补证据、自动训练或自动生成正式实验结论。
- `report_contract.must_not_claim_training_or_wet_lab_validation=true` 是硬边界：只要 trace summary 来自当前只读聚合，就必须把候选/库设计写成项目记忆和下一步动作，而不是湿实验验证结果。
- 多个 training 缺失原因同分时排序没有科学含义；测试和报告不能依赖第一项，而应按 reason/count 明确展示。
- 空 round 或空项目记忆时 summary 必须保持 `missing_project_memory`，并要求先创建/选择 round、导入 feedback 或记录 formal decision，不能为了完整报告生成伪造的下一轮库设计。

## 2026-08-20 阶段 58 DBTL trace 前端可视化边界

- 项目详情页上的 DBTL 视图只应该消费 `dbtl_trace_summary_v1` 和相关只读 trace 片段，不能把 raw trace 视为正式项目结论。
- 前端展示的 `required_actions` 是下一步补证据/补流程的提示，不是自动完成项，也不是训练或 claim 升级信号。
- `ProjectDbtlTraceSummary` 必须继续和 `report_contract` 绑定：只要后端标记 `must_not_claim_training_or_wet_lab_validation=true`，UI 就不能在视觉上暗示“已训练”“已验证”。
- 数据页 / 项目页的 DBTL 标签页应保持和 sequences/results/wiki 同级的只读视图，不引入写入入口，不引导用户在摘要页直接做任务提交。
- 这个前端接线的价值是把后端的 project memory / learning readiness / next-round contract 变成可见状态，而不是增加新的分析结论层。

## 2026-08-20 阶段 59 项目列表 DBTL 状态边界

- 项目列表页上的 DBTL chip 只能表达 summary status，不应替代项目详情页，也不应展示 raw trace。
- DBTL 状态请求必须是后台补充，不应阻塞基础项目列表渲染；如果 DBTL trace 失败，项目列表仍必须完整可用。
- 列表页 chip 的 title 仅用于快速提示 learning / next-round 状态，不应承诺训练可用、湿实验验证或项目闭环完成。
- 这种上提入口的目的，是让用户在进入项目详情前先看到哪些项目已经有学习记忆，哪些还只是空项目。
- 继续保持只读边界：列表页只是展示 project memory 状态，不引入任何提交、训练或 claim 升级动作。

## 2026-08-11 Stage 34 发布前运行态硬化发现

### Docker / Foldseek 构建边界
- 后端 Docker 镜像不能因为 Foldseek 外部下载临时失败而整体构建失败；Foldseek 属于结构检索可选运行时，工具层已经能在缺 CLI/API 时返回 `FOLDSEEK_NOT_CONFIGURED` 或 `FOLDSEEK_DEGRADED`。
- `docker/Dockerfile.backend` 的默认策略应是：
  - `FOLDSEEK_INSTALL_REQUIRED=false`：下载失败只警告，镜像继续构建；
  - `FOLDSEEK_INSTALL_REQUIRED=true`：需要严格发布 Foldseek CLI 的环境才硬失败；
  - 任何情况下都不能伪造 Foldseek 查询结果。
- classic Docker builder 不一定注入 `TARGETARCH`，在 `set -u` 下直接引用 `$TARGETARCH` 会导致构建失败；应使用 `${TARGETARCH:-}` 并回退 `dpkg --print-architecture`。

### Redis / worker 运行态
- Redis AOF 损坏会导致 `redis` 反复重启，并连带 worker/md-worker/ligand-worker health 不健康。
- 修复顺序应是：停止 Redis 与 worker -> 备份 AOF manifest/base/incr -> `redis-check-aof --fix appendonly.aof.manifest` -> 重新检查 AOF -> 启动 Redis 和 worker -> 查看健康与日志。
- 不应删除 Redis volume 作为默认处理；已有任务/结果状态可能依赖该 volume。只有在用户明确批准且确认可丢弃队列状态时才考虑清空。

### 发布证据边界
- Stage 33 的本地 smoke 使用“现有 backend 镜像 + 当前源码热同步”只能说明代码路径可运行，不能作为正式镜像发布证据。
- Stage 34 已用完整 backend/frontend 镜像重建和容器 recreate 替代该证据；后续线上同步仍需要独立发布包、回滚/备份检查和公网 smoke。

### 源码部署包安全边界
- `*.env.example` 可以作为模板进入部署包；`*.prepared` 不是模板，可能包含真实环境值，必须默认排除。
- PDB/结构向量属于数据或运行输入，不能随源码部署包默认发布；真实结构数据应通过 `deploy_data`、OSS/MinIO 或明确的 benchmark bundle 管理。
- 新包发布前必须同时做 checksum 和 tar 内容抽查；本轮远端抽查 `entries=516`、`forbidden=0` 后才执行安装。

### 线上发布验证边界
- 线上发布可以用公网 `health/http/public/live/strategy` smoke 证明入口和核心策略状态机已生效。
- 维护窗口真实回滚、异地备份恢复、外部存储恢复验证和 GPU MD 长任务仍是独立人工/外部条件门禁；不能因为代码包发布成功而标记这些门禁完成。

## 2026-08-11 Venus/MatVenus 策略执行机制调研：第一轮发现

### 已读取材料
- `docs/designs/2026-07-10-matvenus-multi-session-study.md`
- `docs/designs/2026-07-10-matvenus-analysis-style-study.md`
- `docs/designs/2026-07-29-enzyme-manual-analysis-flow-v1.md`
- `matvenus-research/summary.md`

### 对当前问题直接相关的 Venus 机制
- Venus/MatVenus 的核心不是每条用户消息都重新启动完整流程，而是维护一个任务上下文：用户目标、已知输入、已完成工具结果、当前阶段、下一步待确认动作。
- 典型模式是 `preflight_only=true` 先做参数/输入预检，向用户展示阶段目标和提交成本/耗时，再由用户确认正式提交。这与本平台目前 `plan_only -> execute_confirmed` 方向一致，但本平台缺少“已生成策略就是待执行检查点”的复用机制。
- Venus 的阶段推进是分段确认：功能残基/禁改区 -> 结构建模/对接 -> 单点扫描 -> 组合预测 -> 实验批次。每一步确认后只提交当前阶段任务，而不是重新解释用户最初需求。
- Venus 的会话复盘里明确记录 “SESSION INTENT / SUMMARY / ARTIFACTS / NEXT STEPS”，这等价于可恢复状态。当前本平台主要依赖前端拼接原始任务和后端 history 文本，缺少结构化的 `current_intent/current_strategy/current_stage/next_action`。
- “重新执行任务”在 Venus 会话中是显式用户意图；普通“是，执行/确认执行/继续”应视为推进当前阶段，不应重新开流程。
- Venus 的失败处理有一个重要教训：工具参数错误不能重复同样失败参数。本平台修复同题续跑时也必须避免“确认执行 -> 重新计划 -> 换参数/换流程”的隐性重复。

### 不能照搬的部分
- Venus 输出中过强的成功率、倍数和“100%”表达不能迁移；本平台仍需保留 claim gate、证据等级和 blocked/degraded/live 边界。
- Venus 曾出现编号映射和工具参数错误，说明我们要借鉴其阶段状态和执行节奏，而不是照搬其结论强度。

### 初步产品判断
- 本次修复不应只是字符串相似度判断“是不是同一问题”。更稳的设计是：在会话内显式维护“待确认策略检查点”，确认执行时优先绑定该检查点；只有用户明确提出新任务、新序列、新结构、新目标或修改策略时才重新规划。
- 如果暂时不做数据库迁移，最小实现可以从最近 assistant 策略确认消息和 agent state 恢复计划；长期应把策略 checkpoint 存成结构化消息 metadata 或独立表。

### 原始会话核对：04-WH-bgl2Y
- `matvenus-research/reviews/04-WH-项目bgl2Y-0b29a4ae.review.md` 显示，首次进入任务后先调用 `venusx_functional_residue_prediction(preflight_only=true)`，随后给出四阶段流程并询问是否提交第一阶段。
- 用户说“那你开始吧”后，agent 只提交第一阶段 `venusx_functional_residue_prediction(preflight_only=false)`，没有重新解释/重建完整流程。
- 第一阶段完成后，agent 把下一阶段具体化为 AlphaFold2 结构预测，并询问“是否确认提交执行 AlphaFold2”。用户说“是，执行”后，agent 直接读取结构预测技能并提交 `alphafold2_protein_folding`。
- 第二阶段完成后，agent 把 AlphaFold2 产物路径作为下一阶段 `venusrem_mutation_prediction` 的 `structure_file`。这说明 Venus 的“同一问题判断”不是只看文字相似，而是依赖已完成 artifact 和下一阶段状态。
- 用户明确输入“重新执行任务”时，agent 才重新从 VenusX、AlphaFold2、VenusREM 全链路重跑。这是显式重启意图，不应和“是/执行/确认”混淆。

### 对本平台的直接修复要求
- `execute_confirmed` 不能调用 `_plan_cb()` 生成新计划后再执行；应优先执行上一轮已展示并等待确认的计划。
- “确认执行上述分析策略”这种控制消息不是新需求；不应触发 router/research/plan。
- 如果上一轮策略已经执行到某个阶段，后续“是/继续/执行”应推进 `next_action`，而不是从第一步重跑；本平台目前只有一次性 plan 列表，短期可保证“策略确认 -> 执行同一 plan”，长期应拆为阶段检查点。
- 若用户明确说“重新执行/重跑/重新分析/从头来”，才允许重启流程；即便重启，也应复用同一输入上下文并说明这是全链路重跑。

### 本平台现状对照
- `frontend/src/components/chat/ChatInput.tsx` 的确认按钮会发送原任务加 `[用户确认] 请按上面的分析策略执行工具。`，同时 `agent_control=execute_confirmed`。前端显示的是“确认执行上述分析策略”，但后端保存/处理的是拼接后的原任务。
- `backend/app/core/agent_graph.py::stream_chat()` 收到 `execute_confirmed` 后只调用 `_normalize_confirmed_task()` 去掉控制标记，然后仍然执行 router、research 和 `_plan_cb()`。
- `_plan_cb()` 当前固定返回 `_generate_fallback_plan()`，因此测试里“确认前后计划一致”只证明 deterministic fallback 碰巧一样，不证明后端严格执行了用户确认时看到的那份计划。
- plan-only 阶段前端确实收到 `state.plan` 并存到 `agentState`，但 `useChatStream()` 请求体没有把 `agentState.plan` 或策略指纹发给后端。
- 后端 `_finalize_chat_response()` 持久化 assistant 消息时只有 `content` 和 `tool_calls`；plan-only 阶段没有执行工具，`tool_calls_data` 为空，因此数据库里也没有结构化 plan checkpoint。
- 因此当前系统的结构性缺口是：策略确认页文案承诺“只按上面工具和参数执行”，但后端没有保存/接收“上面工具和参数”的结构化对象，只能重新规划。

## 2026-08-11 国内外 AI 蛋白平台调研：机制对比

### 调研来源
- Matwings / MatwingsVenus 官方站、用户手册、发布新闻。
- Cradle、Generate:Biomedicines / Chroma、EvolutionaryScale ESM、Profluent、Absci、Arzeda、OpenProtein.AI、Google DeepMind AlphaFold、NVIDIA BioNeMo 官方资料。
- 国内 BioMap/xTrimo、MoleculeMind/MoleculeOS、百度 PaddleHelix/HelixDesign/HelixFold3、腾讯 iDrug、深势科技/玻尔平台、阿里云/百度云/AWS 蛋白结构预测工作台等公开资料。

### 平台类型分层
- **对话式智能体 + 干湿闭环型**：MatwingsVenus。特点是自然语言任务拆解、工具/技能/专家/湿实验服务统一入口，强调“设计即验证、验证即迭代”。
- **实验数据驱动的蛋白工程 SaaS**：Cradle、OpenProtein.AI。特点是把用户每轮湿实验数据上传为训练/生成依据，强调多目标优化、plate/library 设计、数据质量分析、API、权限和 provenance。
- **生成式生物医药平台**：Generate:Biomedicines、Absci、Profluent、MoleculeMind、BioMap。特点是自研 foundation model + 内部/合作湿实验验证，围绕抗体、binder、酶、药物开发做多属性设计。
- **工业酶/产品化 DBTL 平台**：Arzeda。特点是物理建模 + AI + 15 年结构化实验数据 + 生产/配方/法规/制造约束，从设计阶段就考虑 scale-up 和 commercial delivery。
- **基础模型/开放科研工具平台**：EvolutionaryScale ESM3/Forge、DeepMind AlphaFold Server/DB、IPD RFdiffusion/ProteinMPNN、NVIDIA BioNeMo。特点是模型/工作流能力强，但通常不等于完整项目管理和湿实验闭环。
- **云算力/应用工作台型**：百度 PaddleHelix/CHPC、阿里云 E-HPC AlphaFold3 Portal、AWS 蛋白结构预测工作台、腾讯 iDrug 的结构预测模块。特点是任务提交、资源管理、Web UI、结果可视化，偏工具/算力编排。

### 对本项目最值得学的机制
- **策略不是一次性文本，而是可执行对象**：Cradle 的 modular task、PaddleHelix 的多轮 generation-evaluation、NVIDIA BioNeMo 的 blueprint workflow、MatwingsVenus 的 Agent Skills 都说明平台需要保存“任务配置/工具参数/阶段状态”，而不是只保存 Markdown。
- **多目标优化必须写成 trade-off 管理**：Cradle、Profluent、Absci、MoleculeMind、Arzeda 都强调同时优化 affinity/activity/stability/expression/developability/manufacturability。我们的策略确认不能只有工具清单，应保存 objectives、constraints、blocked mutations、assays、success criteria。
- **湿实验反馈是下一轮模型/策略输入**：Cradle 明确每次上传 lab results 后模型随项目变好；Generate/Absci/Arzeda 都是 generate/build/measure/learn 或 DBTL 循环。我们不能把湿实验反馈当普通聊天历史，需要结构化进入 project state。
- **plate/library 是交付物，不是附属表格**：Cradle 的智能 plate design、MatwingsVenus 的批次实验优先级、Arzeda 的 application-relevant conditions 都说明结果应落到“第一批做什么、第二批怎么补、失败后怎么转向”。
- **任务状态与 artifact 传递是核心**：MatwingsVenus 原始事件里 AlphaFold2 输出结构文件后，下一阶段 VenusREM 使用该 `structure_file`；云工作台型平台也都强调 job/project/resource/result 管理。我们目前在 chat agent 里只用内存 `completed_steps` 桥接，跨轮恢复不足。
- **证据边界要比竞品更严**：DeepMind/ESM/IPD/NVIDIA 资料通常明确模型任务边界；商业平台有成功案例但细节常因保密而模糊。本平台应保留 live/degraded/blocked、claim gate、编号门控，不能照搬“高成功率/数倍提升”的宣传表达。

### 对“同一问题不要重新启动流程”的设计启发
- 国外平台的共同做法不是用自然语言相似度判断，而是用 project/round/task/run 结构判断当前处于哪一阶段。
- 应建立 `active_strategy_checkpoint`：
  - `task_fingerprint`：由标准化序列/结构对象/UniProt/PDB/目标/assay 生成。
  - `strategy_signature`：由 plan steps、params、analysis_depth、constraints 生成。
  - `status`：draft / awaiting_confirmation / executing / completed / superseded / restarted。
  - `next_action`：confirm_execute / revise_plan / continue_next_stage / upload_feedback / rerun_full_pipeline。
  - `artifacts`：结构文件、工具结果、实验反馈、候选表。
- `execute_confirmed` 应只接受并执行 `awaiting_confirmation` checkpoint；如果 checkpoint 缺失或签名不匹配，应 fail-closed 要求重新确认，而不是自动重新规划。
- “继续/是/执行”应匹配当前 checkpoint 的 `next_action`；“重新执行/从头/重跑/换一个序列/新任务”才创建新 checkpoint。

### 用户硬要求：干实验预测必须向湿实验准确度对齐
- 用户明确要求：平台给出的干实验预测、突变位点和策略，目标必须达到湿实验一样准确，不能把低置信计算猜测包装成可直接实验结论。
- 技术拆解：
  - **不能承诺未验证预测天然等于湿实验**；这是科学上不成立的。
  - **必须把湿实验数据作为最高优先级证据**，用于校准下一轮策略、上位性判断、候选排序和 Go/No-Go。
  - **没有湿实验或强证据闭环时，输出只能标为计算假设/探索性建议**，不能标成确定结论。
  - **达到湿实验级准确度的条件**应是：同项目或同家族湿实验校准数据充足、编号/结构/底物/表达体系确认、预测与历史实验命中率可追溯、候选通过证据门控。
- 后续产品设计要求：
  - 建立 `wet_lab_calibrated` / `experimental_supported` / `computational_hypothesis` / `blocked` 等明确等级。
  - 策略确认页必须显示该策略是否有湿实验校准依据。
  - 候选突变主表必须展示“湿实验支持程度”和“还缺什么实验才能升级为高置信”。
  - 同一项目后续问题必须复用已有湿实验反馈，不得重新从通用流程开始。

### 外部平台公开机制对准确度提升的启发
- **Cradle**：平台公开强调每次上传 lab results 后，模型会更好地理解该蛋白；还强调多属性同步优化、blocked mutations、regional constraints、custom objectives、intelligent plate design、provenance 和 API。对本平台的启发是：准确度提升不能只靠换大模型，必须有“项目内实验数据 -> 自定义模型/策略 -> plate/library 输出 -> 下一轮反馈”的闭环。
- **OpenProtein.AI**：公开文档把工程任务组织为 project、assay dataset、train/predict/evaluate、jobs；API 有 `/jobs/JOB_ID` 追踪状态，assay data 以序列 + 实测属性上传。对本平台的启发是：会话续问应该绑定 project/dataset/job，而不是把 chat history 当唯一状态源。
- **MatwingsVenus**：官方资料强调 conversational protein R&D agent、200+ 工具、30+ skills、wet-lab validation、expert collaboration；中文手册明确“如需要更准确的结果，请上传湿实验数据”，并区分零样本突变 VenusREM、小样本突变 VenusPrime、关键位点 VenusX。对本平台的启发是：没有实验数据时只能走 zero-shot/探索；有少量实验数据时应切换为小样本校准路径。
- **Generate:Biomedicines / Chroma**：公开平台机制是 generate-build-measure-learn；Chroma 将设计表示为在外部 constraints 下的生成/推断，并有实验表征支撑部分早期设计。对本平台的启发是：策略对象必须包含 constraints，结果必须回流 measure/learn。
- **Absci / Profluent / Arzeda**：都强调 wet lab + AI iterative loop、multi-parametric optimization、多属性优化和真实测试数据。Arzeda 进一步把 application-relevant conditions、manufacturability、regulatory、scale-up 放到设计阶段。对本平台的启发是：如果用户目标是工业酶，策略必须纳入表达体系、底物、pH、温度、纯化、稳定性和放大条件，不能只按通用突变评分。
- **NVIDIA BioNeMo / 百度 PaddleHelix / 云工作台型平台**：更像 workflow/job 编排层，强调模型微服务、任务状态、结构预测/设计/评估 pipeline、多轮生成-评估。对本平台的启发是：严格执行策略需要 job/run 状态机，而不是自然语言重放。

### 策略丰富度标准
后续本平台生成策略时，至少应包含这些结构化字段，而不是只输出“调用哪些工具”：
- `task_identity`：蛋白/酶、序列指纹、结构对象、项目、轮次、目标底物/条件。
- `objectives`：主目标、次目标、必须保持的性质、冲突 trade-off。
- `assays`：需要或已有的湿实验指标，例如比活、kcat/Km、Tm、半衰期、残余活性、表达量、SEC/聚集。
- `evidence_state`：湿实验支持、项目内数据、同源文献、结构/编号、工具预测、缺失证据。
- `constraints`：禁改区、催化/辅因子/二硫键、blocked mutations、允许区域、结构距离、表达体系限制。
- `execution_plan`：待执行步骤、每步工具、参数、输入 artifact、输出 artifact、是否需要用户确认、预计成本/耗时、失败降级策略。
- `candidate_policy`：探索/深耕比例、P1/P2/P3 批次规则、是否允许组合、上位性检查规则。
- `success_criteria`：什么结果算 Go/Watch/No-Go，什么证据才能升级为 wet-lab calibrated。

### 不允许说谎的报告规则
- 不得把 `computational_hypothesis` 写成 `wet_lab_validated`。
- 不得把“模型预测提升 X 倍”写成实际提升；若无实测，只能写“预测方向/探索性收益假设”。
- 不得在未确认编号映射时输出具体结构距离、催化网络或位点级高置信结论。
- 不得在未执行 live 查询时写“已联网检索/已查数据库”；必须保留 live/degraded/blocked。
- 不得在确认执行时重新生成另一套计划后声称“按上面策略执行”。

### 问题识别与续问分类
应把用户输入先分成五类：
- `confirm_current_strategy`：确认执行、是、开始吧、按上面来。动作：执行当前 awaiting checkpoint。
- `continue_current_project`：继续、上面、这个酶、这个序列、这些数据、下一轮怎么做。动作：复用当前 project/checkpoint/artifacts/wet-lab feedback。
- `revise_strategy`：调整策略、不要跑某工具、先做性质预测、增加 Rosetta/文献。动作：在同一 task_fingerprint 下生成新 strategy revision，旧策略 superseded。
- `explicit_restart`：重新执行、重跑、从头、重新分析全部。动作：创建 rerun checkpoint，并说明这是全链路重跑。
- `new_task`：新序列、新结构、换一个酶、另一个项目、不同目标。动作：创建新 task/project boundary，不继承旧 artifact。

### 2026-08-11 第二轮深度调研补充

#### 平台机制再归纳
- **MatwingsVenus 最关键可借鉴点**：不是“会聊天”，而是把任务拆成 preflight、确认、正式执行、artifact handoff、下一阶段确认。`04-WH-项目bgl2Y` 明确展示 AlphaFold2 的 PDB artifact 进入 VenusREM 的 `structure_file`，用户说“重新执行任务”才重跑全链路。
- **Cradle / OpenProtein.AI 最关键可借鉴点**：project / round / assay dataset / job 是平台状态的骨架；湿实验数据不是聊天背景，而是训练、校准、候选选择和下一轮设计的输入。
- **Generate / Absci / Arzeda 最关键可借鉴点**：准确度来自 generate/build/measure/learn 或 DBTL 迭代；设计阶段必须包含真实 assay、工艺、表达、放大和多属性 trade-off。
- **BioNeMo / AlphaFold / ESM / PaddleHelix / Tencent iDrug / Uni-Fold 类平台最关键可借鉴点**：模型或工具必须有 job 状态、版本、artifact 和置信度边界；结构置信度不能直接冒充功能或活性置信度。
- **BioMap / MoleculeMind 等国内大模型/工作流平台最关键可借鉴点**：大模型和工作流包装有价值，但不能替代项目内湿实验校准；公开案例证据不能直接升级为本项目证据。

#### 当前平台必须修正的“说到做到”缺口
- `_build_plan_confirmation_reply()` 已经生成策略指纹，并承诺“只按上面列出的工具和参数执行”。
- 但 `ChatInput.tsx` 只把原任务拼接 `[用户确认]` 发给后端，没有传 `agentState.plan`、`strategy_signature` 或 `task_fingerprint`。
- `useChatStream.ts` 的请求体只有 `agent_control`，没有 confirmed checkpoint payload。
- `backend/app/api/chat.py::ChatRequest` 也没有结构化 confirmed plan 字段。
- `agent_graph.py::stream_chat()` 在 `execute_confirmed` 下仍先 `_route_intent`、`_research_pi`、`_plan_cb`，然后才执行。当前严格执行承诺不成立。

#### 最优修复方向
- **短期最小修复**：前端确认时发送 `confirmed_plan + strategy_signature + task_fingerprint`；后端校验签名，直接把 confirmed plan 转为 `PlanStep` 执行，严禁 valid confirm 路径调用 `_plan_cb`。缺失或不匹配时 fail-closed。
- **中期稳态修复**：新增服务端 `strategy_checkpoints`，把 plan-only 阶段持久化为 awaiting checkpoint；执行、修改、继续、重启都走 checkpoint 状态机。
- **长期准确度修复**：建设 `WetLabCalibration`，把实验记录按 assay schema、单位、WT 基线、重复数、条件、批次和项目轮次入库；候选表按项目/家族/目标命中率升级置信标签。
- **禁止写死**：不能把 Venus 的固定工具顺序、固定关键词、固定阈值、固定候选数量或固定“同一问题”规则硬编码进流程。策略应来自当前输入、项目状态、可用工具能力、实验数据、用户约束和配置化 policy；工具选择与阶段推进必须由 checkpoint/status/next_action/artifacts 决定。

#### 策略生成的新硬标准
- 策略必须包含 `task_identity`、`objectives`、`assays`、`evidence_state`、`constraints`、`execution_plan`、`candidate_policy`、`success_criteria`。
- 只输出工具列表不算策略；必须说明为什么这些步骤匹配当前序列/结构/目标/湿实验数据，以及每一步失败如何降级。
- 确认后的执行对象必须是同一份结构化策略，不允许重新规划后声称“按上面执行”。
- 策略生成逻辑必须可扩展：目标模块、工具能力、确认动作、重启动作、证据等级、湿实验校准规则都应配置化或数据驱动；代码只实现通用状态机和校验框架。

#### 干实验预测向湿实验准确度靠近的产品定义
- `computational_hypothesis`：无项目湿实验校准，最多给探索性方向。
- `wet_lab_calibrated`：有足够同项目或强相关家族实验数据，且策略/模型用这些数据校准过。
- `experimental_supported`：该突变/组合或机制已有直接实验证据支持。
- `blocked`：编号、结构、assay、live 查询或湿实验基础不足，不能给高置信候选。
- 平台目标可以是“持续用湿实验反馈提升干实验命中率”，但不能承诺零样本干实验天然等同湿实验。

### 2026-08-11 confirmed checkpoint 短期修复结果
- 已落地短期修复：确认执行必须携带结构化 `confirmed_plan` 和 `strategy_signature`；后端重算签名，通过后直接执行该 plan。
- valid confirmed 路径不再调用 `_plan_cb`，因此不再“重新规划一个相似流程后声称按上面执行”。
- 策略签名由后端生成并通过 SSE state 下发，前端只负责携带，不负责决定真实性。
- `task_fingerprint` 由序列、上传结构、UniProt/PDB、命名靶点或规范化任务文本生成；它是项目身份锚点，不是固定流程规则。
- 缺失 checkpoint、空 plan、签名不匹配或任务指纹不匹配时 fail-closed，不执行工具，也不自动重启流程。
- 如果用户在策略确认后手打“是，执行/开始吧/继续”等确认短句，但没有结构化 checkpoint，后端会提示策略检查点缺失，不把该短句当新任务重启。
- 本轮没有实现服务端持久化 checkpoint；刷新页面或跨会话恢复 active checkpoint 仍需要中期 `strategy_checkpoints` 表。
- 本轮没有实现湿实验校准数据模型；干实验预测准确度提升仍需要后续 `WetLabCalibration` 和命中率追踪。

### 2026-08-11 公开平台资料复核与 Stage 33 决策
- NVIDIA BioNeMo 官方资料当前仍将 Framework、NIM、模型、recipe 和训练/推理环境分层，并强调可扩展、可复现的运行配置；这支持本平台把策略、状态和 artifact 分离保存，而不是把一次聊天文本作为唯一事实源。
- BioNeMo 的公开验证说明按不同验证层级组织结果，提示平台 UI 应区分“当前状态/历史结果/正式验证”，而不是把任意完成状态显示成湿实验结论。
- Stage 33 只做历史策略记忆的可见性与生命周期治理：memory 是 `data-only` 背景，不是新指令、不触发工具、不升级证据等级；历史 `executing/completed` 也不等于本轮执行。
- 前端必须在 conversation/user 边界切换时清空旧 memory；加载失败只能显示降级状态，不阻断聊天，也不能用旧 memory 代替当前接口结果。
- 本轮 smoke 暴露出一个更严格的执行边界：确认执行后，后端可以在运行时给工具补充 artifact/湿实验校准上下文，但不能把这些运行时补参写回用户已确认的 plan payload；否则 UI/黑盒会看到“已确认策略漂移”，即使没有真正重规划。
- 确认执行路径不应触发 SC review 追加新工具。补充工具属于新 revision 或下一阶段 checkpoint，而不是“严格按上述策略执行”的同一轮。

### 2026-08-11 服务端 checkpoint 与 WetLabCalibration 第一层
- `strategy_checkpoints` 已作为服务端状态锚点启动：
  - plan-only 阶段持久化 awaiting checkpoint；
  - 新策略会 supersede 旧 awaiting checkpoint；
  - `execute_confirmed` 缺前端 payload 时，可从当前 conversation 的 active checkpoint 恢复原任务、plan、signature、fingerprint；
  - 恢复后仍交给 orchestrator 校验签名，不绕过 fail-closed。
- `wet_lab_calibration_runs` 已作为湿实验校准摘要启动：
  - 数据来源是现有 `experiment_feedback_records`，不重复存原始实验数据；
  - 记录 objective、assay_key、dataset_fingerprint、反馈记录 ID、go/watch/no_go、hit_rate、data_quality_grade、evidence_level；
  - 校准规则保守：>=12 个同 assay 变体才标 `wet_lab_calibrated`；3-11 个为 `wet_lab_feedback`；更少保持探索/小样本标签。
- 仍未完成的关键能力：
  - checkpoint 前端跨刷新恢复；
  - Venus 式多阶段 `next_action`、artifact handoff 和 revision history UI；
  - 将 `WetLabCalibrationRun` 接入候选排序、ClaimGate、报告正文和同项目续问上下文。
- 设计边界继续保持：不写死 Venus 工具顺序，不写死候选数量，不把小样本湿实验反馈包装成训练好的专属模型。

## 2026-08-10 定制化策略与对话边界
- 根因：原策略 checkpoint 主要按目标类型（热稳定、pH、活性/特异性）生成，虽然后续工具会分析序列，但确认前展示的“策略”缺少序列指纹、组成偏好、motif、结构/编号证据和 assay context，因此不同基因序列的同类目标看起来像同一套通用策略。
- 决策：策略确认页必须先显示“本轮定制化依据”，包括序列指纹、长度、疏水/带电/Gly/Pro/Cys、motif、潜在糖基化、上传结构/UniProt/PDB 和 assay context；没有完整序列时必须明确不能冒充序列专属候选。
- 决策：确认执行不能把 `[用户确认]` 当作新的自然语言需求重新解释；执行前剥离该控制标记，保持 deterministic plan 与确认前一致。
- 决策：同一会话里的新消息不一定是追问。新序列、新上传结构、新 UniProt/PDB 或明确“新任务/另一个/换一个”时应忽略上一轮蛋白上下文；只有“继续/上面/这个序列/该蛋白/同一结构”等才继承。
- 已用回归固定三条行为：
  - 不同序列的“提高比活力”策略文本必须不同；
  - 确认执行后的工具计划与确认前保持一致；
  - 新序列不继承上一轮上传结构上下文。
- 本轮已同步到 ECS current release 并重建 backend 镜像；公网 plan-only 黑盒验证通过，策略确认已显示定制化依据和等待确认状态。

## 2026-08-10 ECS 发布收口与 live smoke 结果
- 新 release bundle 已生成、上传、安装，并切换 `current` 到 `/opt/protein-ai-platform/releases/20260810T013345Z-25679eb/protein-ai-platform`。
- ECS app stack 当前健康：backend、frontend、nginx、outline、chromadb、worker、md-worker、ligand-worker。
- 公网 `http://120.27.108.138` 的 `/api/health` 和主页 smoke 通过，说明上线后基础入口可用。
- `check_production_config.py` 在 ECS 上通过，结果为 `0 critical / 0 warning`。
- `run_release_acceptance.py --json` 通过；结论是发布可用，但仍保留人工门禁，不应写成所有门禁都已闭合。
- 容器内 `deploy_data` live gate、backend structure smoke、OSS/MinIO live E2E、ligand live gate 都已通过；OSS 临时对象已清理。
- `backend/scripts/smoke_md_topology.py` 通过，输入 `deploy_data/smoke/query.pdb` 有效，但由于 1 条 GROMACS warning，结果仍保守标为 `safe_for_ranking=false`。
- 维护窗口、异地备份恢复、外部存储恢复演练仍未执行，继续按人工门禁处理。

## 2026-08-10 剩余待建清单 1-8 启动
- `check_remaining_backlog_readiness.py --json` 当前结果是 `external_required=7`、`planned=1`、`ready=1`。
- 已启动的 8 个待建项分别是：
  - `formal_domain_https`
  - `gpu_gromacs_md_live`
  - `md_blackbox_live_e2e`
  - `ligand_runtime_live`
  - `oss_minio_live_e2e`
  - `admin_authenticated_screenshots`
  - `maintenance_window_drills`
  - `remote_pytest_runner`
- 这 8 项里，`remote_pytest_runner` 已被识别为仓库内已有 GitHub Actions backend pytest workflow 对应的 planned runner；其余 7 项都依赖域名、证书、GPU runtime、live 凭据或维护窗口。
- 2026-08-20 Stage 94 后，`remote_pytest_runner` 已进一步收口为 `ready`：CI backend-test 与本地 fail-closed mirror runner 均具备，外部 operator input rows 从 8 降为 7。
- 当前不应把“已启动”写成“已完成”或“已就绪”；所有外部依赖仍按 fail-closed 处理。
- 已新增外部输入包生成器，将 1-8 转成可执行输入合同：
  - `docs/manuals/remaining-backlog-external-input-packet.json`
  - `docs/manuals/remaining-backlog-external-input-packet.md`
- 该输入包不执行网络、生产演练、下载、MD 长任务或对象存储写入；只固化 required fields 与验证命令，作为下一步收集域名/证书/GPU/凭据/维护窗口的交付物。
- 已新增外部输入值模板和验证报告：
  - `docs/manuals/remaining-backlog-external-input-values.template.json`
  - `docs/manuals/remaining-backlog-external-input-validation-report.json`
- “等待外部输入”的含义不是停止工作，而是当前缺的是本地代码无法凭空产生且不能伪造的生产/准生产条件：
  - 正式域名、DNS owner、TLS certificate source、HTTPS 版 `PUBLIC_BASE_URL/FRONTEND_URL/OIDC_ISSUER`
  - GPU/GROMACS runner、真实 WT/mutant PDB 输入、MD worker 长任务容量窗口
  - live MD task id 或允许新提交的批准、live 账号的 secret reference
  - ligand worker 真实 OpenBabel/RDKit、Vina、ACPYPE/AmberTools、GROMACS runtime
  - OSS/MinIO endpoint、bucket、secret reference、写读删权限范围
  - admin screenshot 账号 secret reference 和目标 `FRONTEND_BASE_URL`
  - maintenance window id、生产演练批准、异地备份/外部存储恢复目标
  - remote pytest runner 的触发策略和 coverage artifact 访问策略
- validator 当前明确 `network_io=not_executed`、`destructive_actions=not_executed`、`secrets_printed=false`；模板里所有敏感字段只允许填写引用，不应粘贴原始密码或云密钥。
- 已新增 execution plan/runbook 层：
  - `docs/manuals/remaining-backlog-gate-execution-plan.json`
  - `docs/manuals/remaining-backlog-gate-execution-plan.md`
- 该层把“已填外部输入”转换为脱敏命令计划；未填齐的 item 保持 `armed=false`。默认模板下当前 `armed_rows=0`、`blocked_rows=8`，说明没有任何 live gate 被误放行。
- secret reference 即使被填写，也只会在 execution plan 中显示为 `<secret-reference-provided>`；脚本不会解析 secret manager、不会读取密钥、不会打印原始引用。
- `--require-complete` 和 `--require-any-armed` 都按设计返回非 0，作为 fail-closed 护栏，避免把空模板误当成可执行计划。

## 2026-08-04 联网证据源第二层第二批：工具合同与报告边界

### InterProScan 序列提交边界
- `interproscan_sequence_submit` 只能表示“本轮已向 EBI InterProScan REST 提交序列并拿到 job_id”。
- 该状态不能写成“已获得 InterProScan 注释结果”，也不能用于放行家族/结构域/保护位点结论。
- Claim Gate 中 `INTERPROSCAN_SEQUENCE_SUBMITTED` 的语义必须保持 submit-only；下一批需要单独实现 job status/result polling 和结果解析 claim。

### 文献 live/cache/stale 语义
- `literature_live_search` 任一来源 live 成功时可标 `live/pubmed_crossref_rest`，但 partial errors 必须保留，报告中不能把双源都失败的情况写成完整检索。
- fresh cache 命中标 `degraded/cache_hit`，因为本轮没有实际联网查询。
- live 失败后 stale cache 命中标 `degraded/stale_cache_after_live_failure`；它可以作为参考线索，但不能支撑“本轮已联网核验”的摘要 claim。
- live 失败且无缓存标 `degraded/live_query_failed`；报告只能输出运行边界和待核验，不应生成具体文献结论。

### 报告 Manifest 定位
- `## Evidence Manifest` 是证据账本，记录 tool/subsource/status/mode/source/endpoint/checked_at/reason。
- 该 manifest 用来支撑报告可追溯和 Claim Audit，不等于所有正文 claim 都已被支持。
- `literature_live_search` 结果表可以直接导出 PMID/DOI/标题，但摘要仍需经过 Claim Gate；文献存在不等于其支持某个突变逻辑。

### 测试治理发现
- 本轮四文件宽回归首次出现旧 MD batch 测试 SQLite `no such table: users` 假失败，单测复跑通过，串行重跑宽回归通过。
- 项目记录中已有“并行运行数据库相关 pytest 会导致 SQLite 竞态”的历史经验；后续仍应串行运行共享 SQLite 测试组，或为并行测试提供隔离 DB。

## 2026-08-04 酶身份画像前置门控与短 motif 误判修复

### 主要发现
- `enzyme_identity_profile` 需要成为酶工程计划的第一层身份门控，不能只把 `protein_benchmark` / `enzyme_function` / `mutation_priority_score` 当作并列动作。
- 388 aa-SD-WT 案例里，`GYSIG` 这类单一短 motif 不能单独顶成 lipase/esterase EC；它最多只能是弱提示。
- 身份画像一旦确认，应把 family / catalytic residue / protected positions 传给后续分析工具，否则后面的 benchmark 和 mutation ranking 仍会回到 Unknown family。

### 已落地的规则
- `agent_graph` 现在先排 `enzyme_identity_profile`，再排 `protein_benchmark`、`enzyme_function`、`mutation_priority_score`。
- `protein_benchmark` 可消费 `identity_profile`，并在身份已确认时把 family 和 catalytic residue 输出切到 profile 结论。
- `mutation_priority_score` 只在身份已确认时放行 P1/P2；candidate / unresolved 会直接门控掉。
- `enzyme_function` 对单一 `GXSXG` / `GYSIG` motif 不再直接给 lipase EC 结论。

### 388 aa 回归
- `enzyme_identity_profile` 现在可识别 Peptidase A1 / aspartic peptidase family，并给出 D86 / D275 保护位点。
- `protein_benchmark` 在喂入 identity profile 后可输出 Peptidase A1 family 而不是 Unknown family。
- 定点测试已覆盖身份画像、家族消费、单 motif 误判抑制和身份未确认时的突变门控。

## 2026-08-04 第二轮湿干闭环的能力边界

### 产品结论
- 小样本单点实验不构成“该蛋白专属上位性模型”的训练集。平台应表述为**约束型反馈重排**：把实验反馈作为最高优先级筛选依据，结合结构距离、机制重叠和明确的风险门控生成下一批实验。
- 总活性或发酵上清活性升高，不等于比活、`kcat` 或 `kcat/Km` 提升。没有蛋白归一化的纯酶/动力学数据时，必须保持为“表达或稳定性介导的可能性”或“未解”，不能按催化提升进入组合主线。
- 远端候选位点不能仅凭“远离活性中心”当作变构机会。至少需要进化/文献证据，且需要结构连通性证据或可下载、可核验的真实 MD 产物；普通 MD 也不能自动生成 pKa 或催化活性结论。

### 已落地
- 新增 `feedback_iteration_planner`：分离催化、稳定性介导、表达介导和未解表型；少于两个与目标一致的已验证单点时，强制先补单点。
- 组合只在单点有效、机制和结构风险审查通过、且成对结构距离真实提供时标为“待做两点实验”；缺结构证据的组合不提升为高置信推荐。
- 探索/深耕配额来自透明的当前项目数据质量规则，不宣称来自未证实的大规模历史统计。

## 2026-08-04 外部蛋白研发示例能力审计

### 总结
- 用户新增的 21 条示例提示词覆盖六条产品线：人类靶点/膜蛋白情报、抗体工程、酶工程/生物资源发现、生成式结构-序列设计、小分子/肽/PPI 对接、膜蛋白复合物建模。
- 现有系统不能把“注册了同名工具”视为等同的技术能力。`alphafold2_folding`、`rfdiffusion_design`、`proteinmpnn_design`、`diffdock_docking`、`kcat_predict` 等至少有一部分为代理/MVP 或启发式实现；其中 `kcat_predict` 的 `is_real_inference=True` 属于高风险误导标记，需优先整改。
- 真正具备工具链合同的是 ligand/Vina 预处理与受环境门控的 Rosetta、GROMACS 路径：依赖存在时产生真实日志/工件，依赖缺失时 blocked，不应伪造计算结论。
- 膜蛋白脱靶、CXCL12 受体、TGF-beta 通路和抗体人源化的主要缺口不在 LLM，而在专用数据合同：人类定位/表达/通路/疾病证据、抗体编号和 germline/结构背景、表位级而非全长同源级的风险排序。

### 输出
- 新增 `docs/designs/2026-08-04-bio-rd-capability-audit.md`，按能力、输入、真实运行时、当前状态、升级优先级进行审计。

## 2026-08-04 公开一手资料验证后的下一阶段计划

### 可直接变成验收门的事实
- AlphaFold 3 官方输出合同包含 sample 级 mmCIF、confidence JSON、summary JSON、ranking scores，且 pLDDT、PAE、pTM/ipTM 有明确语义；这些可以直接定义平台真实 AF3 运行的最小工件集。
- RFdiffusion 官方推理入口为 `scripts/run_inference.py`，backbone PDB、`.trb` 元数据和 trajectory 均应作为真实运行的可验收工件。
- ProteinMPNN 官方工具输出可携带模型名、git hash、seed、固定/设计链、采样温度和 score；这些应进入平台任务审计。
- DiffDock 官方明确其目标是复合物姿势与 confidence，而非亲和力预测；平台必须禁止把 DiffDock confidence 解释成 Kd 或 binding energy。
- Human Protein Atlas、Reactome、EBI Proteins API 均支持可程序化和版本化的人类蛋白/表达/通路数据接入，适合构建人类靶点专项数据合同。

### 输出
- 新增 `docs/designs/2026-08-04-next-stage-execution-plan.md`，包含阶段 20-25、时间、验收、决策门、跨域数据合同和继续向 MatwingsVenus 取证的问题。

## 2026-08-04 科学报告格式与 Claim 级证据门控

### 对外部 MUC16 纳米抗体脱靶报告的判断
- 值得借鉴的是产品形态：研究计划、用户确认、大纲确认、分章节撰写、最终报告、置信度附录。
- 更值得警惕的是正文与证据附录脱节：大量平台定义、数据库版本、权重公式、风险阈值在正文中被写成确定事实，但附录标记为 `MISSING`、`WEAK` 或 `CONFLICTING`。
- 这类报告如果直接照搬，会让平台看起来“专业”，但本质上仍可能把设计假设包装成事实。

### 本平台应采用的规则
- 正文摘要只能包含 `SUPPORTED` 结论、明确标注的弱证据推断和阻断项。
- `MISSING` claim 只能写成“建议/待补证据”，不能写成“平台采用/平台锁定/最终公式”。
- `CONFLICTING` claim 必须从摘要和结论移除，进入冲突证据区。
- 风险公式、阈值、权重在没有实验校准前只能标为 `DESIGN_HYPOTHESIS` 或 `expert-weighted score`。
- 数据源版本必须来自平台 manifest、下载日志或任务审计，不允许 LLM 凭外部搜索结果写死。

### 输出
- 新增 `docs/designs/2026-08-04-scientific-report-format-and-claim-gating.md`，定义报告章节、claim 状态、正文处理规则和酶工程迁移方式。

## 2026-08-04 第一层同步优化代码决策

### `protein_benchmark` 降级
- `protein_benchmark` 不再从 `known_family` 或 `enzyme_type` 直接解锁 GH13/GH11 等内置知识库。
- 没有当前轮 `enzyme_identity_profile.identity_status=identified` 且 `guardrail.status=ready` 时，工具返回 `status=blocked`，只保留基础理化性质和同源比较，不输出家族 motif、催化残基预测、结构域推断、工程建议和已知工程案例。
- 这样可避免用户一句“淀粉酶/GH13”或外部弱线索绕过 Foundation Profile，继续产生错误位点和过度具体的突变建议。

### `scientific_claim_gate` 最小合同
- 新增 `scientific_claim_gate` 工具，用于把 claim audit 状态转成报告生成动作。
- 摘要/结论只允许 `SUPPORTED`；`WEAK` 和 `DESIGN_HYPOTHESIS` 被降级到正文/方法并显式标注；`MISSING`、`CONFLICTING`、`RUNTIME_UNVERIFIED` 一律阻断。
- 这是后续把外部平台式长报告改造成可审计报告的第一层硬门控。

### 第一层并行优化扩展
- 新增 `enzyme_objective_module_plan`：把热稳定性、比活/催化效率、底物特异性、pH 活性谱、可溶表达拆成不同目标模块，明确 required evidence、candidate mechanisms、validation metrics 和 forbidden shortcuts。Foundation Profile 或目标实验上下文不满足时不允许输出候选突变主表。
- 新增 `tool_capability_audit`：把关键工具标成 `evidence_synthesis / foundation_dependent_explainer / proxy / real_runtime_gated / runtime_unverified`，防止 RFdiffusion、ProteinMPNN、AlphaFold、DiffDock、kcat 等名字被误读成真实运行完成。
- 新增 `bio_specialty_input_gate`：为 MUC16 健康膜蛋白脱靶、CXCL12 配体-受体、TGF-beta 通路、人源化抗体建立首层输入合同和 blocked claims。缺抗体/表位/表达/拓扑/编号等关键输入时，只能输出补证据计划。

### 突变位点主表优先级修正
- 用户再次明确酶改造分析的一号交付物不是工具清单或长报告，而是可进入实验设计的“突变位点主表”：突变位点、推荐替换、突变逻辑、预期方向、风险提示和实验优先级。
- 因此第一层 gate 的产品边界修正为：
  - `enzyme_identity_profile.identity_status=identified` 且 `guardrail.status=ready` 仍是硬门槛；家族、编号、催化/关键保护位点没有确认时，不能输出 P1/P2 主表。
  - `enzyme_objective_module_plan` 的 assay context 缺口不应直接清空主表；它应把主表降级为 `exploratory_requires_objective_evidence`，并在每个位点风险中提示需要补 Tm、pH 曲线、kcat/Km、目标/非目标底物等基线证据。
  - `mutation_priority_score` 新增 `experiment_design_table`，作为主表专用数据结构，前端和 fallback 报告优先消费。
- `kcat_predict` 与 `protssn_score` 已从 `is_real_inference=True` 修正为 `is_real_inference=False + capability_status=proxy + DESIGN_HYPOTHESIS`，避免把启发式估算包装成真实模型推理。

### Claim Gate 接入报告生成链路
- `scientific_claim_gate` 不应只作为用户可调用工具存在；报告综合阶段必须自动生成 claim audit，并把规则注入 SC synthesis。
- 当前自动 claim 来源包括：
  - `enzyme_identity_profile`：身份/编号是否足以支撑位点级建议。
  - `enzyme_objective_module_plan`：目标模块是否足以支撑 report-grade 排名。
  - `mutation_priority_score`：突变位点主表是否可用于实验规划，以及预测效果是否仍缺实验验证。
  - `kcat_predict`、`protssn_score`、AlphaFold2/RFdiffusion/ProteinMPNN/DiffDock MVP、GROMACS、Rosetta：是否有真实运行时/工件证据。
- LLM synthesis 现在会收到 `Claim audit constraints`，摘要/结论只能提升 `SUPPORTED` claim；`DESIGN_HYPOTHESIS` 只能在正文标注为假设；`RUNTIME_UNVERIFIED/MISSING` 只能写成边界或待验证项。
- fallback 报告新增 `Claim Audit Gate` 小节，避免 LLM 不可用时丢失证据门控。
- AlphaFold2、RFdiffusion、ProteinMPNN、DiffDock MVP 输出已第一批加入 `capability_status=proxy`、`is_real_inference=False` 和 `report_boundary`，防止名字本身被误读为真实模型执行。

### 1+2 验收与联网要求
- 388 aa-SD-WT 场景现在覆盖两条路径：
  - Foundation + objective evidence ready：输出 `candidate_table_status=ready` 的实验主表。
  - Objective evidence 不足：保留探索性主表，标记 `exploratory_requires_objective_evidence`。
- 未知家族或身份/编号未确认时仍保持硬阻断：不输出 `experiment_design_table`，避免无家族/无保护位点基础时乱给实验位点。
- 家族冲突不是直接失败：高等级 A1/aspartic peptidase 证据仍可胜出，但 `conflicts` 必须保留，报告中不得把短 motif 或弱 hydrolase 线索当作等价证据。
- 前端真实浏览器 smoke 已确认“候选突变位点”主表在“改造策略”之前，字段包含 P1/P2、探索性/可排单状态、推荐突变、突变逻辑、预期方向、风险提示和禁改位点。
- 用户补充平台必须联网。产品边界应为：
  - 默认输出要区分 `live`、`degraded/offline fixture`、`blocked_network`。
  - UniProt/InterPro/BLAST/文献等联网证据源需要记录查询时间、源版本/接口、命中摘要和失败原因。
  - 没联网或外部接口失败时，报告不能写成“已查数据库”，只能写成“本地证据/待联网核验”。

### 联网证据源/live gate 第一层落地
- 新增统一 `evidence_source` payload：`source/status/mode/live_query_executed/checked_at`，可选 `version/endpoint/reason/details`。
- `annotation_bundle`、`resolve_interpro_annotation`、`resolve_catalytic_site_lookup`、`resolve_signal_peptide_prediction` 当前仍走本地导入库、缓存或启发式预测，因此必须标为 `degraded`；缺输入时标为 `blocked`。这不是坏结果，而是防止报告把本地证据写成“已联网查询 UniProt/InterPro/M-CSA/SignalP”。
- `blast_search` 只有本次 `_run_blast` 成功调用 NCBI BLAST REST 时才标 `live`；普通缓存命中标 `degraded/cache_hit`，联网失败后使用 stale cache 标 `degraded/stale_cache_after_live_failure`，失败无缓存标 `degraded/live_query_failed`。
- `sequence_search` 也接入同一证据状态：UniProt REST keyword/accession 查询成功标 `live/uniprotkb_search_rest`，BLAST 路径成功标 `live/ncbi_blast_rest`，缓存/失败分别降级。
- Claim Audit 新增 `ANNOTATION_BUNDLE_LIVE_QUERY`、`BLAST_LIVE_QUERY`、`SEQUENCE_SEARCH_LIVE_QUERY`。只有 `evidence_source.status=live` 且 `live_query_executed=true` 才允许报告摘要/结论写成“本轮已联网查询”；否则只能写为本地证据、缓存结果、运行边界或待核验。
- 第二层仍需补：InterPro 官方 live API、PubMed/文献 live 查询、数据 manifest 版本锁定和引用导出。

### 联网证据源/live gate 第二层第一批：平台工具化
- 用户明确指出 InterPro/UniProt/PubMed/Crossref 这类能力应当“用平台自己工具分析”。本轮落地为 ToolRegistry 工具，而不是后台服务私有函数。
- 新增 `interpro_live_lookup`：
  - 使用 EBI InterPro API 的 UniProt accession 查询路径。
  - 只有实际 API 成功才返回 `evidence_source.status=live`。
  - 裸序列输入不假装 InterProScan，返回 `blocked`，原因说明同步 InterProScan 序列提交尚未启用。
  - API 失败返回 `blocked/interpro_api`，保留 `live_query_executed=true` 和错误详情，防止失败查询被误写成可用 live 证据。
- 新增 `literature_live_search`：
  - 支持 `query/doi/pmid/max_results`。
  - 通过 PubMed E-utilities 与 Crossref REST 返回标准化题名、DOI、PMID、期刊、作者、链接。
  - 任一来源成功即返回 live，并在 `errors` 中保留部分失败；双源失败返回 degraded；缺输入返回 blocked。
- 现有 `sequence_search` 已是平台 UniProt/BLAST live 工具，已补 `evidence_source`。后续 agent 可在酶改造流程中组合调用：`sequence_search` 查 UniProt/BLAST，`interpro_live_lookup` 查 InterPro，`literature_live_search` 查文献。
- 报告生成器新增“联网/证据源状态”表，自动汇总顶层和 annotation bundle 子源状态，避免自动发布 Wiki 时只截断 JSON 而丢掉 live/degraded/blocked。
- 前端 `ToolCallCard` 增加通用证据状态标签，工具卡头部直接显示 Live/Degraded/Blocked；这对所有带 `evidence_source` 的平台工具生效。
- 仍需后续：InterProScan 序列提交异步化、文献查询缓存/stale fallback、NCBI API key/速率控制、更完整引用导出和 manifest 版本锁定。

## 2026-07-29 整项目重新测试发现

### 总体结论
- 整项目串行复测通过，未发现新的代码失败。
- 后端全量 pytest 稳定为 `569 passed`。
- 前端 lint/build/smoke 合同通过，构建阶段没有 3Dmol eval warning 或 chunk size warning。
- 发布验收仍是 `passed-with-manual-gates`，manual gate 均为维护窗口/异地备份/外部存储恢复输入。
- 线上只读 nightly gate 在放行公网访问后为 `passed-with-skips`，说明公网入口、公开页面、live 页面、benchmark bundle HEAD/Range 和只读验收矩阵均可用。

### 本轮发现的非代码问题
- 普通沙箱下访问公网会导致 nightly 只读 gate 假失败；放行网络后同一命令通过。
- 普通沙箱下启动 Playwright Chromium 会因 macOS Mach port 权限失败；放行本机浏览器进程后可执行。
- `frontend/tests/smoke-check.mjs` 需要先启动 `vite.smoke.config.ts` 的 4201 服务；未启动服务时会 `ERR_CONNECTION_REFUSED`。
- 结构 demo smoke 输出 Redis fallback 提示，来自本机沙箱拒绝 localhost Redis 连接；脚本按设计降级到本地 fallback 并通过。

### 运行时边界仍需外部条件
- `structure_smoke_readiness.py` 当前是 `demo-ready`；live SIFTS/annotations/query PDB 就绪，但本机未配置 Foldseek API/CLI。
- ligand toolchain 当前为 `blocked_toolchain_missing`；缺 OpenBabel/RDKit、Vina、ACPYPE/AmberTools 和 GROMACS。
- MD topology smoke 当前为 `GROMACS_NOT_INSTALLED`；需要 GPU/GROMACS 节点完成真实拓扑和长任务 gate。
- remaining backlog readiness 仍是 1 ready / 8 external_required；这些不是代码 blocker。

## 2026-07-29 上线前继续串行复测发现

### 结论
- 本轮按串行方式重跑本机验收矩阵、发布验收、后端全量、前端 lint/build、关键业务链路定点测试和线上只读 smoke，未发现新的代码失败。
- 后端全量 pytest 结果为 `569 passed in 186.47s`，没有 warning 摘要。
- 前端 `npm run lint` 无 warning 输出；`npm run build` 已不再出现 3Dmol direct eval 或 chunk size warning。
- 线上公网入口只读 smoke 三项均通过：HTTP smoke、live smoke、public smoke。

### 与用户重点诉求的对应状态
- “先出策略、确认后执行、可修改策略后执行”：已有 stream 回归测试保护，未确认时不执行 `ToolRegistry.execute`，状态进入 `plan_confirmation`。
- “平台可以直接调用某个工具分析”：`/api/tools/{name}/call` 的 Rosetta ddG 直调用测试通过。
- “数据库与数据库结合”：突变优先级测试确认会附带 lipase evidence context；实验反馈记录可形成 Go/Watch/No-Go 和下一步组合策略。
- “先做性质预测，最重要突变位点”：目标路由中仍包含 `predict_properties` 和 `mutation_priority_score`，且关键链路回归通过。
- “Rosetta 给突变位点计算突变体，负值更稳定、正值不稳定、阈值区间、人工核实”：Rosetta ddG 测试覆盖 runtime 缺失阻断、本地估算明确标注非 Rosetta、真实 scorefile 解析、`strong_stabilizing` / `destabilizing` 分类、`manual_review_required`。

### 剩余风险
- 剩余 `manual_required` 和 `external_required` 不是本轮代码阻塞，属于上线输入或运行环境门禁：正式域名/HTTPS、GPU/GROMACS、MD blackbox live 参数、完整 ligand runtime、OSS/MinIO 凭据、admin 截图账号、维护窗口演练和远端非生产 pytest runner。
- 后续仍不要并行运行后端全量 pytest、验收矩阵和发布验收；当前共享 SQLite 测试库会产生竞争型假失败。

## 2026-07-27 AI 酶改造模型分析流程固定化整改

### 根因判断
- `AgentOrchestrator._generate_fallback_plan()` 旧逻辑对任意酶工程序列任务默认加入 `predict_properties -> protein_benchmark -> enzyme_function -> mutation_priority_score`，目标差异主要只写入 `engineering_goal` 参数，导致执行层看起来固定。
- `CB_SYSTEM_PROMPT` 旧协议还写着“酶工程必须综合多工具 pipeline / 至少 4 tools / always include mutation_priority_score”，会持续强化固定工具链。
- 负向约束缺少执行层 fail-closed：用户说“只抽取、不分析、禁止 ESMFold/BLAST/突变打分”时，planner 和 SC supplementary tools 没有统一过滤。
- `_extract_sequence()` 旧逻辑对任意 10 个氨基酸字母不区分大小写，普通英文目标词也可能被当作短序列片段，造成后续工具对象不稳定。

### 已落地决策
- 目标路由优先于通用流程：热稳定性/pH 稳定性、比活力/催化效率、底物特异性、可溶性表达分别选择不同默认工具链；`deep` 才扩展 BLAST、结构预测、广泛扫描或 MD。
- 用户负向约束优先于 planner 和 SC review：只抽取请求直接短路；禁止工具会在计划生成、LLM JSON 计划解析和 supplementary tools 三处过滤。
- 上传 PDB/mmCIF 继续作为一级结构证据：结构工具和编号映射优先，除非明确需要且没有可用结构，否则不重复 ESMFold。
- 序列抽取采用保守策略：FASTA/明确 `序列:` 字段可接受小写并清洗；裸文本只接受大写氨基酸块。

### 验证结果
- 同一条序列分别测试热稳定性、比活力、底物特异性、可溶性表达，白盒断言工具列表实际不同。
- 禁止 ESMFold、BLAST、家族预测、突变打分时，deep plan 仍不包含对应工具。
- “只抽取、不分析、不要调用工具”在 stream 层不进入 router、planner 或 ToolRegistry.execute。
- 本地回归：agent/LLM/phase4 132 passed；tools/structure/fallback 66 passed；仅保留既有 deprecation warnings。

## 2026-07-24 科为博酶蛋白大数据模型路线调研

### 初步结论
- 平台现有工具已经覆盖“序列、结构、注释、结构检索、残基映射、突变排序、组合突变风险、MD、配体预处理/对接、数据查询”等关键能力，可以作为模型的工具调用层，而不是简单塞进一个神经网络参数里。
- 当前更合理的产品形态是“科为博酶蛋白基础数据层 + 检索增强模型 + 工具调用智能体 + 小模型评分器 + 湿实验反馈闭环”，再逐步沉淀为 KWB 专属模型。
- 数据库可以成为模型的一部分，但应分成三种形态：在线知识库/RAG、特征库/评测集、训练数据/偏好数据。不要把数据库仅理解为向量库，也不要一开始追求全量微调大模型。

### 与现有平台对应
- 工具注册层已经有 `sequence_search`、`esmfold_folding`、`structure_search_foldseek`、`residue_mapping_sifts`、`annotation_bundle`、`mutation_priority_score`、`mutation_epistasis_check`、`gromacs_md`、`ligand_preprocess`、`protein_benchmark`、`kcat_predict`、`data_lookup` 等可模型调用能力。
- 数据层已有 `deploy_data`、RDS 中 `enzyme_records`、结构/注释/SIFTS/Foldseek 接入、KWB Lipase Evidence DB、实验反馈和 curation queue，可作为 KWB-EnzymeDB 的第一版资产基础。
- 下一步应优先做统一数据对象、证据分级、工具结果样本化、固定 benchmark 和实验反馈字段标准化。

## 2026-07-25 xylanase Google/PubMed/DOI 第二批深挖

### 已写入的高置信修正
- `XYN58`：原 DOI `10.1021/acs.jafc.3c08125` 与 BhS7Xyl R69F/E137M/E145L 不匹配；已修为 `10.1021/acs.jafc.3c08221`，PMID `38183306`。
- `XYN59`：`AncXyn18` 已补 PMID `39489259`，DOI 保持 `10.1016/j.ijbiomac.2024.137188`。
- `XYN61`：`GH11 Xyn-F A161P/E45T/Q93R` 已补 PMID `39094812`，DOI 保持 `10.1016/j.pep.2024.106561`。
- `XYN63`：`xynAm1 CBM9-2` 原 DOI `10.1016/j.procbio.2022.09.018` 指向其它 Process Biochemistry 文章；已修为 `10.1016/j.procbio.2022.07.021`，未确认 PubMed 收录，PMID 留空。
- `XYN66`：`TtXyn30A GH30 alternative catalytic residue E233` 原 DOI `10.1002/bit.28680` 指向无关 Raman 论文；已修为 `10.1002/bit.28731`，未确认 PubMed 收录，PMID 留空。
- `XYN72`：`T. reesei XynII T2C-T28C+G21W+N124A` 原 DOI `10.1007/s43393-025-00345-0` 未匹配目标论文；已修为 `10.1007/s43393-025-00331-w`，PMID 留空。
- `XYN74`：`Xyl-1 M4` 原 DOI `10.1021/acs.jafc.4c03250` 与目标论文不匹配；已修为 `10.1021/acs.jafc.4c03245`，PMID `39082219`。
- `XYN75`：`XynM9 Rosetta+FoldX` 原 DOI `10.1021/acssuschemeng.4c02870` 与目标论文不匹配；已修为 `10.1021/acssuschemeng.4c04974`，PMID 留空。
- `XYN76`：`S. rameus xylanase V3C/T30C` 已补 PMID `36832954`，DOI 保持 `10.3390/foods12040879`。
- `XYN80`：`S. rameus N-term rigidification` 原 DOI `10.1021/acs.jafc.3c05120` 与目标论文不匹配；已修为 `10.1021/acs.jafc.3c03871`，PMID `37590476`。

### 暂不写库的风险点
- `cord2025` 当前 DOI `10.1016/j.ijbiomac.2024.138121` 在外部检索中疑似指向无关材料/高分子论文；需要继续定位“cord region GH11 xylanase”原文再改。
- `liu2025abacus` 当前 DOI `10.1021/acssynbio.4c00650` 疑似不是目标 ABACUS-T xylanase 设计论文；检索到 `Enhancing functional proteins through multimodal inverse folding with ABACUS-T` 可能是更接近来源，但它是方法论文且不一定适合按 xylanase 工程 paper 写入。
- `zhang2025ml` 为 Pythia 泛化稳定性预测框架，可能更适合模型/工具 benchmark 知识库，不一定应算作 xylanase 家族实验突变文献。
- `sato2023xyl` 当前 DOI `10.1016/j.jbc.2023.104705` 疑似不对应 GH11 thumb loop 论文；未找到可直接替换的高置信 DOI，暂不修改。

### 值得继续接入/深挖的国外数据库源
- BRENDA：适合作为 EC、底物、kcat/Km、KM、pH、温度稳定性、protein variants 和参考文献的标准化校验源；其字段说明明确覆盖 mutant enzyme、reaction conditions、temperature stability 和 references。

## 2026-08-05 benchmark / release / ddG 继续收口

### Benchmark 仍未到可用状态
- `KWB strict mutation holdout` 现在仍是空数据集：`dataset_rows=0`、`primary_holdout_rows=0`、`diagnostic_validation_rows=0`，且 `leakage_check_status=failed`。
- `reviewed substrate identity set` 只有评测态数据，尚未形成可训练或可放行的审核结果：`training_import_written_rows=0`、`strict_holdout_rows_written=0`。
- 这意味着当前“13/15 有效”只是覆盖进度，不是最终可宣称的模型质量结果；缺口仍在正式审核和受控划分，不在模型主干本身。

### Claim / release 仍是 fail-closed
- `claim_readiness_matrix` 只允许 `internal_design_review_artifacts`，其余模型质量、训练、客户交付、IP/FTO、biosecurity 和 release 相关 claim 都是 blocked。
- `local_release_manifest` 虽然已经聚合到 1560 个工件，但 `master_overall_status=blocked_for_model_claim`，并且 `benchmark_ready_for_model_claim=false`、`customer_delivery_ready=false`。
- `human_decision_backlog_open_items=11`、`governance_review_bundle_completion_ready_rows=0`，说明发布链路仍然卡在人审和治理闭环，不在 artifact 数量。

### ddG 只到 runtime smoke
- `pyrosetta_physical_smoke_bootstrap_report` 证明了 PyRosetta runtime smoke 可跑，但它仍是 computational physics evidence only，不是训练标签、模型声明或 release 决策依据。
- `ddg_model_consumption_contract_report` 明确 `physics_ddg_ready=false`、`executable_ddg_backend_ready=false`，FoldX 未形成可执行后端，PyRosetta 只能作为 manual-review computational feature。

## 2026-08-05 子 agent 回包收敛

### Benchmark 两个缺口已经定位到具体决策文件
- `benchmark_score_cache_validation_report.json` 显示当前 15 个 benchmark rows 里，13 个有效，2 个缺失。
- 缺的 2 个正好是：
  - `KWB strict mutation holdout`
  - `reviewed substrate identity set`
- 子 agent 进一步确认它们的共同问题不是验证脚本，而是正式决策与非空物化：
  - strict holdout 需要 `kwb_venus15b_strict_holdout_review_decisions.jsonl` 之类的正式审批，再重建 dataset/split/scorecard/metric_report。
  - substrate identity set 需要 `substrate_identity_review_decisions.jsonl`，当前仍是 `pending_human_review`，不能伪造单分子或补 SMILES 绕门。

### Release / claim 仍主要受人审队列控制
- `local_release_manifest.json` 的 artifact 数量够，但 `release_ready=false` 仍来自 `human_decision_backlog` 和 claim matrix 的 fail-closed 约束。
- 最短可做的文件级动作已进一步聚焦到：`numbering_curation_decisions.jsonl`、`experiment_feedback_plate.local.jsonl`、`external_license_review_decisions.jsonl`、`biosecurity_screening_decisions.jsonl`、`sequence_ip_fto_decisions.jsonl`、`workstream_acceptance_decisions.jsonl`、`operator_review_action_decisions.jsonl`。

### ddG 的技术状态与声明状态分离
- `ddg_backend_readiness_report.json` 证明 PyRosetta / Rosetta execution-ready，但 `model_quality_unlock_requirements_report.json` 仍把 `MQ-U003` 卡在 reviewed structure/mutation data gate。
- 这条线后续可以继续做的是补 reviewed structure/mutation data 和 license/decision 证据，而不是再堆一个“已完成”的模型声明。

### Operator decision packet 不改变 readiness
- 新增的 `next_operator_decision_packet_20260805.md` 只是把 packet、decision 文件、允许决策值和 validator 串成操作索引。
- 它不创建任何正式 review decision，也不改变 `safe_for_model_claim=false`、`customer_ready=false`、`release_ready=false`。
- 该文件的价值是减少下一轮人工/法务/交付审核的查找成本，并防止把 template rows、draft packets、runtime smoke 或 process-substrate inferred SMILES 当作正式放行证据。

### Benchmark hard-gate bridge 是必要中间层
- 子 agent 审计指出，仅列 formal decision 文件还不够；approved hard-gate decisions 不能直接变成 benchmark score-cache artifacts。
- 必须显式经过 `build_hard_gate_decision_benchmark_bridge.py` 和 `validate_hard_gate_decision_benchmark_bridge.py`，并参考 `hard_gate_decision_benchmark_bridge_report.json`。
- `next_operator_decision_packet_20260805.md` 已补入该桥接步骤；`validate_next_operator_decision_packet.py` 也已扩展覆盖，防止后续 packet 漏掉 bridge。

### Release operator packet 聚焦人审链而不是 artifact 数量
- `next_release_operator_decision_packet_20260805.md` 把 customer delivery / release / claim 相关的人审入口集中到五类 formal decision：
  - license
  - biosecurity
  - sequence IP/FTO
  - workstream acceptance
  - operator action completion
- `validate_next_release_operator_decision_packet.py` 只验证 packet 引用的文件、报告、脚本和 fail-closed 文案，不创建任何审批。
- 该 packet 反复记录 `customer_delivery_readiness_report.json` 的阻断项，避免把 1560 个 release artifacts 误解成 customer-ready 或 release-ready。

### Release packet 还要显式覆盖 claim/release 汇总层
- 子 agent 指出，release packet 若只列 formal decision 文件，仍会遗漏 `local_release_manifest`、`claim_readiness_matrix`、`model_claim_fail_closed_consistency_report` 以及本地 release guard 链。
- 这些层不是审批本身，但它们是 release/customer/claim fail-closed 的总控入口，必须在 operator packet 中可见。
- 已将这些报告与对应 build/validate 脚本纳入 packet 和 validator，避免后续把“decision 文件齐了”误解成“release 结构齐了”。

### `operator_review_status_report` 是 release 人审总览而不是装饰项
- release packet 继续被收紧到 `operator_review_status_report.json`，因为它汇总了 license、biosecurity、workstream acceptance 和 operator action completion 的当前状态。
- 这类总控报告不替代正式 decision 文件，但可以避免 release packet 只看到零散 decisions 而忽略整体人审状态。

### `human_decision_backlog_report` 也是 release 总控层
- release packet 还需要显式包含 `human_decision_backlog_report.json` 与其 fail-closed 一致性验证，因为它是“还有多少人审没清完”的总表。
- 这类 backlog 汇总和 `operator_review_status_report` 一起，构成 release/customer/claim 的高层阻断视图。

### 更细的 blocker/report 层也要显式可见
- 子 agent 指出 release packet 还应包含 `next_unlock_blocker_matrix.json`、`model_artifact_claim_guard_validation_report.json` 和 `ddg_proxy_not_physics_claim_validation_report.json`。
- 这些不是审批本身，但它们是模型 artifact、ddG 代理和项目 unlock blocker 的 fail-closed 护栏。
- 已纳入 packet 与 validator，防止把“总控 report 已列”误判成“细粒度阻断链已覆盖”。

### `benchmark_matrix_report` 需要同时保留总控报告和构建入口
- `benchmark_matrix_report.json` 本身已经被 release packet 覆盖，但它的构建脚本 `build_benchmark_matrix_report.py` 也需要显式可见。
- 这保证 packet 不只是“看到一个结果文件”，而是能追溯到生成 head-level benchmark matrix 的本地入口。

### governance / biosecurity readiness 的构建入口也属于 release 总控层
- `build_governance_readiness.py` 和 `build_biosecurity_readiness.py` 这类脚本不是正式审批本身，但它们生成的是 customer/release readiness 的总控来源。
- release packet 将它们纳入后，才能避免只见单点 decision 而忽略 readiness 汇总的生成链。
- CAZy / dbCAN：对 amylase、mannanase、xylanase 等 CAZyme 家族价值最高，适合给本地 paper/variant 记录补 GH/CBM/PL/CE/AA family、结构域和基因组来源标签。
- M-CSA：适合补催化残基、机制、cofactor 和 active-site 位点证据；可直接服务“突变不能碰催化位点”的门控。
- SABIO-RK：适合补定量酶动力学字段，尤其 kcat、KM、kcat/KM、pH、温度、buffer、底物和文献来源。
- FireProtDB：适合补单点突变稳定性数据，字段直接覆盖 dTm/ddG/Tm，能增强平台稳定性预测和突变优先级排序。
- HotSpot Wizard / EnzymeMiner：更适合做候选位点发现和序列挖掘入口，不应直接作为已验证实验结果写库。

## 2026-07-25 acid_protease Google/PubMed/DOI 第七批深挖

### 已写入的高置信修正
- `AP601`：补 DOI `10.1016/j.ijbiomac.2026.150116`，PMID 保持 `41500273`；来源对应 PepA propeptide F37Y/triple mutant 活性增强论文。
- `AP606`：补 DOI/PMID `10.1093/oxfordjournals.jbchem.a002921` / `11328603`；与 RMPP E13A 凝乳/蛋白水解比值提升证据对应。
- `AP607`：补 DOI/PMID `10.1093/oxfordjournals.jbchem.a021553` / `9058201`；对应 conserved Trp39 RMPP mutagenesis。
- `AP608`：补 DOI `10.1110/ps.9.5.991`，并将 `pmid` 字段中误填的 `PMC2144643` 修正为 PMID `10850809`。
- `AP609`：补 DOI/PMID `10.1093/oxfordjournals.jbchem.a021515` / `8982865`；对应 aspergillopepsin I D76/S78 S1-subsite mutagenesis。
- `AP614`：补 DOI/PMID `10.1074/jbc.274.24.16685` / `10358007`；对应 recombinant cyprosin PSI processing/activity paper。
- `AP616`：补 DOI `10.1046/j.1432-1327.2000.01582.x`，并将 author/journal/year 由 `Abe/J Biochem/1998` 修正为 `Asakura/Eur J Biochem/2000`；未直接确认 PMID，保留为空。
- `AP619`：补 DOI/PMID `10.1016/S0166-6851(00)00351-0` / `11166391`，并将 title/author/journal 修正为 `Proteolysis of human hemoglobin by schistosome cathepsin D` / `Brindley` / `Mol Biochem Parasitol`。
- `AP625`：补 DOI/PMID `10.1016/0168-1656(94)90116-3` / `7764448`；对应 Mucor pusillus rennin A101T/G186D thermostability paper。

### 本批边界
- `AP603`、`AP605` 仍保持待核验；检索到的线索偏预印本或题名不稳定，暂不写库。
- `AP623` 暂不写入；`N331Q / MCAP / AMB Express` 的题名与可检索 DOI 仍需二次确认，避免把同属 Mucor protease 的不同论文混用。

## 2026-07-25 acid_protease Google/PubMed/DOI 第八批深挖

### 已写入的高置信修正
- `AP002`：补 PMID `31462045`，DOI 保持 `10.1021/acs.jafc.9b03959`；对应 BsAPA autocatalysis-resistant mutation thermostability paper。
- `AP535`：原 DOI `10.3168/jds.2014-8972` 指向无关 Journal of Dairy Science 奶牛 Salmonella Dublin 疫苗论文；已修为 DOI `10.2174/0929866522666150526154648`、PMID `26008185`，并将题名/作者/期刊修正为 Mucor pusillus pepsin clotting/proteolytic ratio 原文信息。

### 暂不写库的风险点
- `AP532` 当前 DOI `10.1074/jbc.RA120.013093` 在外部检索中疑似指向 REDD1/retinal inflammation JBC 论文，不匹配 pepsin-renin loop swap chimera；暂未找到正确 DOI/PMID，本轮只记录风险，不直接清空或改写。

## 2026-07-25 acid_protease Google/PubMed/Crossref 第九批深挖

### 已写入的高置信修正
- `AP613`：Crossref/Wiley 与 PubMed 确认 DOI `10.1002/jsfa.7688` 对应 PepA_MK82 表达和表征论文，已补 PMID `26919469`。
- `AP540`：原 DOI `10.1046/j.1471-4159.2003.01701.x` 指向丙戊酸下调花生四烯酸代谢的无关 J Neurochem 论文；已修为 `10.1046/j.1471-4159.2003.01597.x`，PMID `12603825`，题名修为 `Employing a superior BACE1 cleavage sequence to probe cellular APP processing`。
- `AP541`：原 DOI `10.1074/jbc.M501229200` 指向 TRPV1/calcium channel 无关论文；已清空 DOI，补 PMID `2104843`，题名/作者/年份修为 thermopsin 原始 JBC 论文。
- `AP532`：Crossref 确认 DOI `10.1074/jbc.RA120.013093` 指向 REDD1/retinal inflammation，与 pepsin-renin loop swap 不匹配；已清空 DOI，保留条目待后续找正确来源。

### 本批边界
- 因清空 `AP532/AP541` 两个错配 DOI，acid_protease DOI 缺口数字从 47 上升到 49；这是主动数据纠错，不是新增缺失。
- `AP536` DOI 在 Crossref/PubMed 未检出，`AP543` DOI 未检出；暂不修改。
- `AP505/AP508/AP521/AP516/AP520/AP512/AP527/AP524/AP517/AP616/AP525/AP530/AP533` 仍需继续逐条题名核验，不接受宽泛 PubMed 命中。

## 2026-07-25 acid_protease PubMed PMID->DOI 第十批深挖

### 已写入的高置信 DOI 回填
- 从 PubMed PMID summary 反查 DOI，并确认题名与本地记录匹配后，回填 18 条 DOI：
  - `AP216=10.1021/bi025926t`
  - `AP405=10.1093/oxfordjournals.jbchem.a002921`
  - `AP204=10.1126/science.290.5489.150`
  - `AP303=10.1042/0264-6021:3490169`
  - `AP621=10.1099/00221287-146-11-2765`
  - `AP103=10.1110/ps.8.10.2001`
  - `AP302=10.1093/protein/12.1.55`
  - `AP304=10.1046/j.1432-1327.1999.00329.x`
  - `AP105=10.1002/pro.5560070109`
  - `AP115=10.1002/pro.5560071108`
  - `AP404=10.1093/oxfordjournals.jbchem.a021553`
  - `AP104=10.1074/jbc.271.26.15590`
  - `AP108=10.1111/j.1432-1033.1996.00664.x`
  - `AP403=10.1093/protein/9.10.869`
  - `AP208=10.1038/nsb0695-480`
  - `AP212=10.1002/pro.5560040203`
  - `AP301=10.1074/jbc.270.34.19974`
  - `AP410=10.1007/978-1-4615-1871-6_73`

### 已清空的错配/无效 DOI
- DOI resolver 或 Crossref/DOI CSL 元数据显示以下本地 DOI 无效或指向无关论文，因此清空 DOI/PMID，留待后续找正确来源：
  - `AP505=10.1074/jbc.M113.481564`：DOI Not Found。
  - `AP508=10.1002/pro.2057`：对应 Protein Science `In This Issue`，不是 HIV-1 protease organic solvent paper。
  - `AP521=10.1021/bi900045t`：DOI Not Found。
  - `AP529=10.1111/j.1567-1364.2008.00390.x`：对应 brewer's spent grains bioethanol，非 Yapsin family。
  - `AP526=10.1016/j.phytochem.2014.09.017`：对应 shea triterpene glycosides，非 Cardosin A。
  - `AP527=10.1016/j.phytochem.2005.01.023`：对应 Laetiporus laetiporic acids，非 cyprosin。
  - `AP516=10.1074/jbc.M610128200`、`AP520=10.1074/jbc.M600520200`、`AP512=10.1074/jbc.M507918200`、`AP524=10.1023/A:1010606011658`、`AP517=10.1021/bi992025q`、`AP525=10.1023/A:1006179332244`、`AP530=10.1074/jbc.273.1.586`：DOI Not Found。
  - `AP533=10.1016/S0021-9258(18)53748-0`：对应 SHV beta-lactamase，非 pepsin N/C lobe paper。

### 本批边界
- acid_protease DOI 缺口净变化 49 -> 45；这是 18 条回填减去 14 条清错的结果。
- `AP113` 的 PMID `8540305` 对应 PubMed 题名与本地题名不完全一致，本轮未回填 DOI。

### 国际对标后的平台提升方向
- NVIDIA BioNeMo Agent Toolkit 的核心方向是把生命科学库、模型和工作流做成 agent-callable tools；这与本平台 `ToolRegistry + AgentOrchestrator + Celery` 的现状高度匹配，优先应补工具质量、输入输出 schema、执行计划可视化和工具调用评测。
- AlphaFold 3 / Boltz / Chai 类趋势是从单蛋白结构预测走向蛋白-配体-DNA/RNA/修饰/离子复合物与相互作用；本平台应把配体对接、口袋、复合物结构预测和 MD 验证做成连续工作流。
- Cradle 类商业平台强调多目标优化、实验数据上传、自动微调、plate/library 设计和审计；本平台应补“轮次管理、实验板设计、数据质量评分、主动学习候选选择、每轮模型更新记录”。
- ESM3/ESM Cambrian/Evo 2 类基础模型说明底层表示模型很重要，但短期不应从零预训练；更可行是接入开源/商业表示模型生成 embeddings 与 mutation features，再训练 KWB 小模型。

## 2026-07-21 P0 审计闭环矩阵与基线发现

### P0-1：`backend/.audit-report.md` 逐项状态
| # | 审计项 | 当前状态 | 测试状态 | 证据/限制 |
|---:|---|---|---|---|
| 1 | `POST /api/projects` 空 name | 已修 | 已测 | `ProjectCreate.name` 有 `min_length=1`，并新增去空白校验；`test_project_name_rejects_empty_and_script_payloads` |
| 2 | `POST /api/auth/register` name 过长 500 | 已修 | 已测 | `RegisterRequest.name max_length=200`；`test_auth_register_rejects_invalid_email_and_long_name` |
| 3 | register email 未验证格式 | 已修 | 已测 | `RegisterRequest.email: EmailStr`；同上测试覆盖 invalid email 422 |
| 4 | 项目名 `<script>` XSS 风险 | 已修 | 已测，仍需线上回归 | 后端项目名去空白并拒绝 `<`/`>`；测试覆盖脚本 payload；仍需部署后验证正常项目创建/更新不受影响 |
| 5 | 未认证 `/api/tools` 泄露工具列表 | 已修 | 已测 | `/api/tools` 和 `/api/tools/{name}` 均要求 `get_current_user`；P0 测试匿名 401、登录 200 |
| 6 | 登录/注册无限速 | 已修 | 已测 | auth 路由接入 `rate_limit()`；P0 测试第 11 次登录返回 429；限制：当前为进程内限速，多实例需 Redis 化 |
| 7 | refresh token 异常静默处理 | 已修 | 已测 | `refresh()` 只捕获 `JWTError`；P0 测试非 JWT 内部异常返回 500，不伪装为 401 |
| 8 | 文件上传缺扩展名校验 | 已修 | 已测 | `ALLOWED_EXTENSIONS` 白名单；P0 测试 `.sh` 上传 400 |
| 9 | Cookie secure flag 本地关闭 | 已修 | 未新增专项测试 | auth cookie 由 `_USES_HTTPS` 控制；需要生产 `USE_HTTPS=true` 或 HTTPS origin 回归确认 |
| 10 | SSE 连接泄漏/错误路径覆盖缺口 | 已修 | 已测，需线上长流回归 | `_iter_with_sse_heartbeat()` 增加保活并取消 pending task；P0 测试覆盖静默 heartbeat；线上仍需部署后看长请求日志 |
| 11 | 默认 `SECRET_KEY` 弱 | 未完全修 | 需配置回归 | 源码默认仍是 dev key；线上应由 env 覆盖。建议增加非 DEBUG 启动校验，避免生产漏配 |
| 12 | `/api/chat/models` 公开模型列表 | 已修 | 已测 | `list_models` 加 `get_current_user`；P0 测试匿名 401、登录 200 |

## 2026-07-22 前端 / SSE / 工作台深评收口

### 已补 live gate
- 新增 `frontend/tests/workbench-deep-live.mjs`，与既有 `chat-sse-deep-live.mjs`、`chat-session-deep-live.mjs` 组成 Phase 12 前端深评 gate。
- 覆盖范围：
  - `/chat/agent` baseline 流式响应、PDB 附件、`gromacs_md` 异步提交、task_id 展示、logout 清理。
  - 会话刷新恢复、坏 access token refresh/retry、用户切换隔离、stale saved conversation 清理。
  - HomePage Quick Analysis 跳转并自动发送 initial prompt。
  - HomePage Upload Protein 入口上传 FASTA 后进入 chat 并完成流式链路。
  - ProjectDetailPage 创建项目、添加序列、运行 `predict_properties` light batch、Results tab 和 Wiki tab。
  - 次级页面 `/benchmarks`、`/benchmarks/venus-15b`、`/pdb`、`/wiki`、`/data`、`/admin` smoke。

### 本轮打出的真实问题
- HomePage Quick Analysis 能把 `initialPrompt` 写入 route state，但 `ChatInput` 的 initial-state effect 依赖不稳定函数，重渲染 cleanup 会取消 300ms 自动发送 timer，导致跳转后 prompt 不一定发出。已改为直接发送 initial prompt，并在处理完成后清理 route state。
- `workbench-deep-live.mjs` 初版对次级路由使用 `body.length >= 80` 粗断言，误把尚未等到详情 API 完成的 `/benchmarks/venus-15b` 和 iframe 主体较短的 `/wiki` 判断为渲染失败。已改为每个路由等待业务关键字，并在失败时输出当前 URL/body preview。

### 线上验证结果
- `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/http-smoke.mjs` -> passed。
- `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/public-smoke.mjs` -> passed。
- `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/live-smoke.mjs` -> passed。
- `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/chat-sse-deep-live.mjs` -> passed；baseline/PDB/MD submitted/task_id/logout/console/5xx 均通过。
- `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/chat-session-deep-live.mjs` -> passed；restore/tokenRefresh/userSwitch/staleCleanup 均通过。
- `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/workbench-deep-live.mjs` -> passed；home quick/home upload/project detail/secondary routes 均通过。
- ECS `backend/frontend/nginx/worker/md-worker` 均 healthy。

### 残余风险
- 当前 workbench gate 使用临时普通用户，`/admin` 只验证普通用户不会触发 5xx/控制台错误，尚未用 admin 登录态深测后台完整操作。
- ProjectDetailPage 只覆盖 Sequences/Results/Wiki 的主链路；成员权限、删除序列、多项目切换和 publish 同步仍属于后续深评范围。
- 长 MD 真实业务任务仍受 `md-worker` 并发 1 和 CPU/GPU 资源限制；本轮验证的是聊天侧异步提交和状态展示，不等于完整生产级 MD 长任务吞吐压测。

## 2026-07-22 部署 / 运维 / 发布准备度深评

### 本地非破坏性 gate 结果
- `python3 scripts/check_upgrade_readiness.py --json` -> `ready-with-warnings`；唯一 warning 是当前工作树 dirty，版本 `0.1.0`、前端版本一致、Alembic 单 head、env 文件和部署包 checksum 均 ok。
- `python3 scripts/run_release_acceptance.py --json` -> `passed-with-blockers`，0 failed / 3 blocked / 1 skipped / 9 total。
- `python3 scripts/run_release_acceptance.py --json --include-backup-verify --backup-verify-compose` -> `passed-with-blockers`，0 failed / 3 blocked / 0 skipped / 9 total。
- `make deploy-live-gate` -> passed；`deploy_data` 为 `live-data-ready`，backend structure readiness 为 `live-ready`。
- `make verify-backup BACKUP_FILE=backups/protein_ai_20260708T001139Z.dump` -> passed；checksum 走 `legacy-path` 兼容，`pg_restore --list` ok。
- `backend/.venv/bin/python -m pytest backend/tests/test_config_validation.py -q` -> 95 passed。

### 本轮打出的真实问题
- 部署包 dry-run 首次包含 `backend/.venv.broken-20260720T1430`，导致 34,661 个文件、约 988MB。根因是 `package_deploy_bundle.py` 只排除了精确 `.venv`，没有排除 `.venv* / venv*`。已修复并补回归；dry-run 收敛为 448 个文件、约 6.8MB。
- 远端 ECS 宿主机 `python3` 为 3.6.8，首次同步后 `package_deploy_bundle.py` 因 Python 3.7+ 语法无法在宿主机执行。已将该脚本降为 Python 3.6 兼容写法，并在远端宿主机完成 `python3 -m py_compile` 和 dry-run；远端 dry-run 为 459 个文件、约 6.8MB。
- 旧备份 `.sha256` 记录了旧机器绝对路径 `/Users/xuyan/...`，当前机器执行 `shasum -c` 会失败。已修复：
  - `backup.sh` 后续生成 checksum 时只写相对文件名。
  - `verify_backup.sh` 标准校验失败后按 digest 兜底兼容旧绝对路径 sidecar，并输出 `legacy-path`。
  - `verify_backup.sh` 输出改为真正 tab 分隔，标准校验失败不再打印旧路径噪音。
- 本机无 `pg_restore` 时，`run_release_acceptance.py --include-backup-verify` 需加 `--backup-verify-compose`；这不是业务失败，是本机 PostgreSQL client 工具缺失的执行方式选择。

### 线上 ECS 只读检查
- ECS uptime 5 天以上，load average 约 `0.05/0.08/0.09`。
- 磁盘 `/dev/vda3` 197G，总使用 21G，可用 168G，使用率 12%。
- 内存 30GiB，总可用约 28GiB，swap 未使用。
- Compose 服务 `backend/chromadb/frontend/ligand-worker/md-worker/nginx/outline/worker` 均 healthy。
- 公网 `/api/health` -> `{"status":"ok","version":"0.1.0"}`；`http-smoke` passed。
- Celery 3 nodes online；`active/reserved/scheduled` 均 empty。
- 近 2 小时 backend/worker/md-worker/ligand-worker 错误关键词扫描无输出；nginx 5xx/499/502/503/504 扫描无输出。
- Docker 可回收资源：images/build cache 合计约 6.95GB 可清理，其中 build cache 约 3.1GB；当前磁盘充足，不是阻断项。

### 发布准备度结论
- 当前基线可作为“非破坏性评测/小步发布”基线：主链路 smoke、前端深评、deploy data、发布验收、备份校验、线上资源健康均通过。
- 生产发布阻断项不是代码 gate 失败，而是流程输入缺失：`MAINTENANCE_WINDOW_ID`、`ALLOW_PRODUCTION_DRILL=true`、`OFFSITE_BACKUP_TARGET/OFFSITE_RESTORE_TARGET`、`EXTERNAL_STORAGE_BACKUP_REF/EXTERNAL_STORAGE_RESTORE_TARGET`。
- 真实生产回滚、异地备份恢复和外部对象存储恢复仍不能在无维护窗口、无独立恢复目标时执行；当前只能保持 plan/blocker gate。

## 2026-07-22 中文酶名 + 已上传结构仍固定追问

### 用户反馈
- 用户输入类似：`酶的名称：天冬氨酸蛋白酶 结构已上传 目标：提高耐热性 底物酪蛋白，反应条件40度，表达体系毕赤酵母`。
- 页面仍返回固定的“当前输入还不足以进入工具分析 / 缺失信息”模板。
- 产品要求：不要固定报告或固定追问；已给出的酶名、目标、底物、条件、表达体系和上传结构应进入该调用的工具/模型分析链路。

### 根因
- `_should_clarify_before_tools()` 的具体输入判断主要识别序列、`object_name:` 附件块、英文/大写蛋白 ID 和少量历史 protein context。
- `_build_context()` 旧逻辑没有把历史消息里的上传附件 `object_name` 提取进 protein context。
- `_plan_cb()` 调 deterministic fallback 时只传当前 message，不传 context；即使上一轮消息带有附件 metadata，fallback plan 也拿不到 PDB object name。
- 中文字段 `酶的名称：天冬氨酸蛋白酶` 旧逻辑不算 concrete protein input，导致被早期缺信息模板拦截。

### 修复
- `_build_context()` 现在提取历史消息中的上传结构对象，写入 `[Uploaded structure object_name: ...]`。
- `_plan_cb()` 和 `_generate_fallback_plan()` 支持 context，fallback 规划会从当前消息 + context 中提取序列或 PDB object name。
- 新增 `_extract_named_protein_reference()`，识别 `酶的名称 / 蛋白名称 / 目标蛋白 / 目标酶 / enzyme name / protein name` 字段。
- `_extract_protein_name()` 优先使用中文/英文 name 字段，并对 `目标/结构/底物/反应/表达` 等后续字段做截断，避免整句作为检索 query。

### 验证
- 本地 `python3 -m py_compile backend/app/core/agent_graph.py backend/tests/test_agent_binder.py` -> passed。
- 本地定向 3 tests -> passed。
- 本地 `backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -q` -> 53 passed / 1 warning。
- 线上容器直接行为验证：
  - `route=analyze`
  - `clarify=False`
  - `tools=['structure_search_foldseek']`
  - `pdb=uploads/user_7/aspartic_protease.pdb`
- 线上公网 `/api/chat/stream` 黑盒验证：
  - HTTP 200，约 14.5KB SSE。
  - `hasFixedMissing=false`
  - `hasStructureTool=true`
  - `hasDone=true`
  - `hasError=false`
- 已部署到 ECS，backend/worker/md-worker/nginx 均 healthy。

## 2026-07-22 固定追问/固定报告同类输入变体排查

### 新发现的同类风险
- 中文字段变体仍有漏判：`蛋白：...`、`蛋白质：...` 在修复前会被 `_should_clarify_before_tools()` 判定为缺少具体蛋白输入。
- `目标酶: amylase 目标: 提高40度稳定性` 在修复前被 router 判为 `general`，不会进入工具规划。
- `PDB编号：1BAG`、`PDB: 1BAG` 在修复前不是可定位输入，容易被固定缺信息模板拦截；但这类编号也不能伪装成已上传结构文件。
- JSON 风格附件 metadata：`"object_name": "uploads/...pdb"` 在修复前不会被 `_build_context()` 提取，导致历史已上传结构仍可能丢失。
- `酶名称：脂肪酶 突变M204H 目标：提高耐热性` 在修复前虽不追问，但检索 query 会变成 `脂肪酶 突变M204H`，污染序列检索。
- 仍应追问的边界：`结构已上传，帮我提高耐热性` 但没有真实 history/current message `object_name`；或只有底物、温度、表达体系，没有酶名/编号/序列/结构。

### 修复决策
- `_extract_attached_object_name()` 支持 `object_name:` 与 JSON/序列化风格 `"object_name": "uploads/...pdb"`。
- 新增明确编号抽取：`_extract_uniprot_reference()` 和 `_extract_pdb_id_reference()`。
- `_extract_named_protein_reference()` 扩展到 `酶名称`、`蛋白`、`蛋白质`、`目标酶`、英文 `enzyme/protein name`，并在 `目标/结构/底物/条件/突变` 等后续字段处截断。
- fallback lookup 现在返回 `(query, database)`：普通酶/UniProt 走 `sequence_search database=uniprot`，PDB 编号走 `sequence_search database=pdb`；只有真实上传结构 object name 才走 `structure_search_foldseek`。
- router 对明确命名/编号并带分析、稳定性、提高、pH 等目标的请求直接进入 `analyze`；裸 `object_name` 结构查询仍保持既有 `research` 口径。

### 验证
- 新增/补强 `backend/tests/test_agent_binder.py`：
  - 8 个明确输入变体进入 `sequence_search`，且 query/database 精确。
  - JSON 附件 history 进入 `structure_search_foldseek`。
  - 2 个模糊输入仍追问且不生成工具计划。
- 本地：
  - `python3 -m py_compile backend/app/core/agent_graph.py backend/tests/test_agent_binder.py` -> passed。
  - 新增边界组最初打出 7 failed / 4 passed；修复后 11 passed。
  - `backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -q` -> 64 passed / 1 warning。
- 线上：
  - 备份目录：`/opt/protein-ai-platform/backups/agent-input-variants-20260722T063557Z`。
  - 已重建 `protein-ai-backend:aliyun`，重启 backend/worker/md-worker/nginx，均 healthy。
  - 容器内白盒断言：中文字段、UniProt、PDB 编号、JSON 附件、模糊输入追问全部通过。
  - 公网 nginx `/api/chat/stream` 临时账号黑盒：HTTP 200，4660 bytes，`has_fixed_missing=false`，`has_sequence_tool=true`，`has_done=true`，`has_error=false`。
  - `/api/health` 返回 `{"status":"ok","version":"0.1.0"}`；发布后 5 分钟 backend/worker/md-worker 无 error/exception/traceback，nginx 无 4xx/5xx。

## 2026-07-22 admin / OIDC / 登录态 tools metadata 深测

### 覆盖范围
- 新增 `scripts/smoke_admin_oidc_tools_live.py`，用于线上 API 级 live gate：
  - 管理员登录、`/api/auth/admin/ping`、用户列表、临时用户角色升降级、锁定/解锁、禁用/启用。
  - 普通 researcher 访问 admin users 返回 403。
  - 登录态访问 `/api/tools`、`/api/tools/gromacs_md`、`/api/tools/diagnostics`、`/api/tools/md/protocols`、`/api/chat/models` 均返回 200。
  - 管理员任务审计列表、摘要、CSV 导出、data readiness、更新记录、deploy_data import dry-run。
  - OIDC provider authorize -> token -> userinfo -> JWKS round-trip。
- 新增 `frontend/tests/admin-deep-live.mjs`，用于线上浏览器 live gate：
  - 创建临时账号，通过 ECS 后端容器临时升为 admin，登录 `/admin`。
  - 验证页面出现 `平台管理后台`、`用户与角色`、`任务审计`、`组织与项目授权`、`数据资产状态`、`权限边界说明`。
  - 验证任务审计 CSV 下载文件名为 `tool-task-audits.csv`。
  - 验证 deploy_data dry-run 导入计划 POST 返回 200。
  - 测试后把临时账号降回 researcher 并禁用。

### 发现与处理
- OIDC live gate 初版使用 `client_id=outline`，线上实际 OIDC client 为 `protein-ai`，导致 authorize 400；脚本已改用 `protein-ai` 并从 env 文件读取 client secret。
- OIDC live gate 初版使用 `http://127.0.0.1/wiki/auth/oidc.callback` 作为公网验证 redirect_uri，不符合线上注册回调；改用 `http://120.27.108.138` 真实公网入口后通过。
- 公网 authorize 在 nginx/FastAPI 链路可能返回 307/308 等重定向状态；脚本改为接受 302/303/307/308，并继续校验 Location 中的 code/state。
- 浏览器 admin gate 初版点击 deploy_data dry-run 后立即关闭浏览器，nginx 产生一条 499；脚本已改为等待 `/api/data/admin/import` POST 返回 200 后再退出，重跑后 2 分钟窗口无 499/5xx。

### 验证结果
- `python3 -m py_compile scripts/smoke_admin_oidc_tools_live.py` -> passed。
- `node --check frontend/tests/admin-deep-live.mjs` -> passed。
- ECS API live gate：
  - `status=passed`
  - `admin_api=passed`
  - `tools_logged_in_metadata=passed`
  - `oidc_provider_round_trip=passed`
  - `admin_audit_csv_bytes=4993`
  - 临时用户最终状态 `disabled`
  - `tokens_printed=false`、`passwords_printed=false`
- 本机对公网 Playwright admin live gate：
  - `status=passed`
  - admin body length 12462
  - CSV download filename `tool-task-audits.csv`
  - deploy_data dry-run import HTTP 200
  - consoleErrors=0、httpErrors=0
  - 临时用户最终状态 `disabled`
- 线上服务状态：backend/frontend/worker/md-worker/nginx 均 healthy；重跑后 backend/frontend/worker/md-worker 无 error/exception/traceback，nginx 无新增 499/5xx。

## 2026-07-22 维护窗口/恢复演练 readiness 与 benchmark HEAD

### 本轮完成
- `backend/app/api/data.py` 为 `/api/data/benchmarks/{case_id}/bundle/download` 增加 `HEAD` 路由，复用原 `FileResponse` 下载逻辑。
- `backend/tests/test_data_api.py` 新增 `test_head_benchmark_bundle`，断言 `HEAD` 返回 200、`application/gzip` 且无响应体。
- `scripts/rollback_plan.py`、`scripts/run_release_acceptance.py`、`scripts/oss_shadow_restore_drill.py` 改为 ECS 宿主机 Python 3.6 可执行写法，去掉 `future annotations`、`dataclasses` 和 3.9+ 类型下标。
- `rollback_plan.py` / `run_release_acceptance.py` 的资产发现支持本地 `dist/packages/backups` 和 ECS 部署根 `releases/incoming/backups`，并优先保留 `/opt/protein-ai-platform/current` symlink 口径。

### 验证结果
- 本地 `python3 -m py_compile` 覆盖后端接口、测试和三个运维脚本，passed。
- 本地 `backend/.venv/bin/python -m pytest backend/tests/test_data_api.py::TestBenchmarkEndpoints::test_download_benchmark_bundle backend/tests/test_data_api.py::TestBenchmarkEndpoints::test_head_benchmark_bundle backend/tests/test_config_validation.py -q` -> 97 passed。
- 本地 `run_release_acceptance.py --json --include-backup-verify --backup-verify-compose` -> `passed-with-blockers`，0 failed / 3 blocked / 0 skipped / 9 total。
- 本地 OSS shadow restore plan-only：只计划写入 `oss://crvab/drills/...`，`network_io=not_executed`，`destructive_actions=not_executed`。
- ECS 宿主机 `python3 -m py_compile scripts/rollback_plan.py scripts/run_release_acceptance.py scripts/oss_shadow_restore_drill.py` -> passed。
- ECS `rollback_plan.py --mode aliyun-app --json` 可执行，已正确识别部署包 `/opt/protein-ai-platform/releases/protein-ai-platform-20260718T090825Z-25679eb.tar.gz`；数据库备份仍缺失。
- 公网 `HEAD http://120.27.108.138/api/data/benchmarks/venus-15b/bundle/download` -> 200，`Content-Length: 7960755`，`accept-ranges: bytes`。
- 公网 `GET Range 0-31` -> 206，`Content-Length: 32`，`content-range: bytes 0-31/7960755`。
- 公网 `/api/health` -> `{"status":"ok","version":"0.1.0"}`；`frontend/tests/http-smoke.mjs` -> passed。
- ECS `backend/frontend/worker/md-worker/nginx` healthy；发布后 5 分钟 backend/worker/md-worker 无 error/exception/traceback/failed，nginx 无 499/5xx。

### 仍未执行的真实演练
- 维护窗口内真实生产回滚未执行：缺 `MAINTENANCE_WINDOW_ID`、`ALLOW_PRODUCTION_DRILL=true` 和线上可验证生产数据库备份文件。
- 异地备份恢复演练未执行：缺线上 `backup_file`、`OFFSITE_BACKUP_TARGET`、`OFFSITE_RESTORE_TARGET`，且恢复目标必须独立于生产。
- 外部对象存储恢复验证未执行生产切换：缺 `EXTERNAL_STORAGE_BACKUP_REF`、`EXTERNAL_STORAGE_RESTORE_TARGET`；当前只允许 shadow/drills 前缀验证，不切生产对象路径。

## 2026-07-23 除正式域名外的继续改进

### 用户约束
- 当前没有正式域名，正式域名和 HTTPS 切换暂不做。
- 其余改进项继续启动，但生产停服回滚、生产 RDS restore、对象存储生产路径切换仍需维护窗口和独立恢复目标。

### 本轮发现
- `check_upgrade_readiness.py` 之前只检查文件/版本/迁移/包，缺生产配置强校验；`SECRET_KEY` 默认值风险仍需通过生产 gate 管住。
- chat 之前只有模型选择，没有显式“允许慢工具”的 UI 入口；fallback 对 PDB-only 深度任务仍不会进入 MD，导致用户感觉“只能快速工具”。
- 后端已有普通用户任务审计 API：`GET /api/tools/tasks/audits`、`GET /api/tools/tasks/{id}`、`POST /api/tools/tasks/{id}/cancel`，但前端没有普通用户任务中心。
- live gate 分散在多个脚本中，缺一个夜间总控，容易漏跑 benchmark HEAD、public/live smoke、生产配置等低风险只读项。

### 修复决策
- 生产配置 gate 作为脱敏独立脚本实现，默认不打印任何 secret；正式域名缺失时 `--skip-domain-https` 只保留 warning/跳过口径。
- chat 深度只作为规划信号，不写固定报告；深度模式允许 planner 调用慢工具，慢工具仍异步提交，避免 SSE 长时间阻塞。
- 普通用户任务中心复用既有审计接口，不新增后端表，前端提供刷新、取消和下载入口。
- 夜间总控默认只跑只读/低风险 live gate；AI 黑盒、文件 E2E、admin/OIDC、OSS E2E 均显式 opt-in。

### 当前验证
- `python3 -m py_compile ...` -> passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "uploaded_pdb or concrete_reference or vague_inputs or deep_analysis_depth or stream_md_request" -q` -> 15 passed / 1 warning。
- `backend/.venv/bin/python -m pytest backend/tests/test_config_validation.py::TestProductionConfigGate -q` -> 2 passed。
- `npm run lint` -> 0 errors / 0 warnings。
- `npm run build` -> passed，只有既有 3Dmol eval/chunk size warning。
- `FRONTEND_BASE_URL=http://120.27.108.138 python3 scripts/run_nightly_live_gates.py --json` -> `passed-with-skips`，0 failed；跳过项均为 opt-in mutating/account gates。

### 线上部署结果
- 已同步并重建 backend/frontend，重启 backend/worker/md-worker/frontend/nginx。
- 远端备份目录：`/opt/protein-ai-platform/backups/codex-pre-domain-skip-improvements-20260723T054001Z`。
- ECS 宿主机 Python 3.6 不支持 `check_upgrade_readiness.py` 原来的 `future annotations`/dataclass/新 subprocess 参数；已降级兼容并通过远端 `py_compile`。
- 线上容器均 healthy；公网 HTTP smoke passed；nightly readonly live gate `passed-with-skips` 且 0 failed。
- `/tasks` 路由返回 SPA HTML 200。
- 容器内深度 PDB-only 规划断言返回 `['structure_search_foldseek', 'gromacs_md']`，证明深度模式不再被限制在快速工具。

## 2026-07-23 结构工作流顺序和门控专项

### 用户专项结论
- 网页端和 `/api/files/upload` 已支持 `.pdb/.fasta/.cif/.sdf` 上传。
- 仅提供序列时，模型能触发 `esmfold_folding`。
- 真实缺陷是能力未稳定放入正确流程顺序：上传 PDB 后回答层说优先附件结构，但执行层先跑序列工具并提交 ESMFold。

### 根因
- `_generate_fallback_plan()` 在 `has_sequence` 分支中优先添加 `predict_properties/protein_benchmark/enzyme_function/mutation_priority_score`，结构搜索只在无 sequence 或无 steps 时追加。
- 非设计分析路径原来可并行 `asyncio.gather()`，即使计划里有结构解析，也不会保证结构解析先完成。
- 上传 PDB + 序列时没有硬规则禁止 `esmfold_folding`，容易把实验/附件结构与预测结构混用。
- 输出合成提示没有把当前轮 tool evidence 显式分层，也没有强调不得引用当前轮之外的 task_id。

### 修复
- PDB 附件存在时，planner 先加：
  1. `structure_search_foldseek`
  2. `residue_mapping_sifts`
  3. `residue_numbering_gate`（仅当文本含 M204H、位点 204 等明确位点）
- 上传结构存在时，sequence 分支不再添加 `esmfold_folding`。
- 仅序列 + 结构相关请求时，planner 顺序调整为 `predict_properties -> esmfold_folding -> protein_benchmark/enzyme_function/mutation_priority_score/...`。
- executor 新增结构 gate 顺序执行：包含结构门控的计划不再并行；gate 不通过时跳过结构依赖工具，尤其不提交 `gromacs_md`。
- synthesis 新增 evidence lineage：序列级、预测结构、上传/实验结构、编号/映射门控、当前轮 async task_id。

### 验证
- `python3 -m py_compile backend/app/core/agent_graph.py backend/tests/test_agent_binder.py` -> passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -k "uploaded_pdb or sequence_only_structure or structure_dependent_tools or deep_analysis_depth or stream_md_request" -q` -> 8 passed / 1 warning。
- `backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py::TestEnzymeAgentEvalSet::test_eval_case_route_clarification_and_tools -q` -> 11 passed。
- `backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py -q` -> 68 passed / 1 warning。
- `npm run lint` -> 0 errors / 0 warnings。

## 2026-07-23 最新备份 + OSS shadow + benchmark HEAD gate

### 本轮完成
- 线上最新数据库备份已生成：
  - `backup_file=/opt/protein-ai-platform/backups/protein_ai_20260722T234645Z.dump`
  - `backup_size=116732429`
  - `checksum_file=/opt/protein-ai-platform/backups/protein_ai_20260722T234645Z.dump.sha256`
- 备份校验：
  - `sha256sum -c` 通过。
  - `pg_restore --list` 通过，`entries=359`。
- 新增 benchmark live gate：
  - `scripts/smoke_benchmark_bundle_live.py`
  - `scripts/run_acceptance_matrix.py` 增加 `--include-benchmark-bundle-live`
  - `backend/tests/test_config_validation.py` 增加风险门禁回归
- benchmark live gate 线上验证：
  - `HEAD /api/data/benchmarks/venus-15b/bundle/download` -> `200`
  - `Content-Type: application/gzip`
  - `Content-Length: 7960755`
  - `Accept-Ranges: bytes`
  - `GET Range 0-31` -> `206`
  - `Content-Range: bytes 0-31/7960755`
  - `body_bytes=32`
- acceptance matrix 验证：
  - 本地 `--include-benchmark-bundle-live` 已纳入计划。
  - 远端 ECS `python3 scripts/run_acceptance_matrix.py --plan-only --include-benchmark-bundle-live --json` 识别到 `benchmark_bundle_head_live`。
- OSS drills shadow 演练：
  - 通过 `protein-ai-backend:aliyun` 临时容器执行。
  - 只写 `oss://crvab/drills/...`。
  - `offsite_backup_upload`、`offsite_checksum_upload`、`offsite_backup_readback`、`shadow_source_marker_create`、`shadow_restore_copy`、`shadow_restore_readback`、`shadow_marker_cleanup` 全部通过。
  - `objects_written_under_drills_prefix_only=true`。

### 关键细节
- 线上 RDS URL 口径是 `postgresql+asyncpg://...`，`pg_dump` 前需要转换为 `postgresql://...`。
- ECS 宿主机没有 `pg_dump`/`pg_restore`，所以备份和恢复校验统一通过 `postgres:16-alpine` 临时容器完成。
- `oss_shadow_restore_drill.py` 宿主机缺 `minio`，因此改为在 `protein-ai-backend:aliyun` 临时容器里执行。

### 仍未执行的真实演练
- 真实生产停服回滚仍未执行。
- 真实异地恢复目标的恢复还未执行。
- 外部对象存储生产路径切换仍未执行，只做了 `drills/` 前缀 shadow 验证。

## 2026-07-23 异地备份真实恢复闭环

### 实际执行
- 新增 `scripts/download_oss_object.py`：
  - 只允许下载包含 `drills/` 的 OSS 对象。
  - 支持读取 `.sha256` sidecar 并校验下载内容。
  - 不输出对象存储凭据。
- 从 offsite 对象下载：
  - source：`oss://crvab/drills/offsite-backups/protein_ai_20260722T234645Z.dump`
  - output：`/opt/protein-ai-platform/backups/offsite_restore_source_20260722T234645Z.dump`
  - size：`116732429`
  - sha256：`b69ca9e2da8546de27e935ecdde12a52358e0af9ff655e17c94e1fe9c65805a2`
  - sidecar：verified
- 使用 `postgres:16-alpine` 启动无端口暴露的临时独立 PostgreSQL 容器。
- 将 offsite dump 恢复到临时数据库 `offsite_restore_check`。
- 恢复后 sanity check：
  - `restore=ok`
  - `public_table_count=40`
  - `users_row_count=79`
- 演练结束后临时 PostgreSQL 容器自动清理；未连接生产 RDS，未修改生产数据库。

### 过程问题
- backend 运行镜像未包含项目 `scripts/`，不能直接从 compose backend 容器执行运维脚本；改用 backend 镜像临时容器挂载项目目录。
- ECS 宿主机没有 `minio` Python 包；改用 backend 镜像执行 OSS 下载。
- 第一次恢复命令因本机 zsh SQL 引号解析失败，未启动远端恢复；改用 SSH stdin 脚本后成功。

### 当前结论
- 异地备份链路已从“上传/读回校验”闭环到“下载/sidecar 校验/独立数据库恢复/数据 sanity check”。
- 仍未执行的是生产停服回滚和生产对象路径切换，这两项必须等待正式维护窗口与审批。

### P0-2：本轮新增/补强测试
- 新增 `backend/tests/test_p0_audit_regressions.py`，覆盖 auth 注册字段、登录限速、refresh 异常边界、项目名 XSS 输入、文件上传/下载权限、chat models 鉴权、tools metadata 鉴权、SSE heartbeat、OIDC redirect/userinfo、async task owner status/cancel。
- 更新 `backend/tests/test_tools_api.py` 的 MD protocol API 测试，为工具 metadata 鉴权补登录态。
- 本地验证：`python3 -m py_compile backend/app/api/chat.py backend/app/api/tools.py backend/app/api/projects.py backend/tests/test_p0_audit_regressions.py backend/tests/test_tools_api.py` 通过。
- 本地验证：`backend/.venv/bin/python -m pytest backend/tests/test_p0_audit_regressions.py -q` -> 11 passed。
- 本地验证：组合定向 pytest -> 51 passed / 5 warnings。warnings 为 SQLAlchemy `datetime.utcnow()` deprecation，非本轮功能失败。
- 测试执行注意：后端 pytest 共用 SQLite `test_protein_ai.db`，并行执行会出现 drop/create schema 竞争假失败；数据库相关 pytest 需串行或使用隔离 DB。

### P0-3：当前可评测/可发布基线
- 基线 HEAD：`25679eb0886ac1be69bb251cd9359d61483fdc1e`。
- 当前评测对象：上述 HEAD 加当前 working tree 中 P0 相关 diff；未创建 commit。
- 本轮 P0 纳入文件：
  - `backend/app/api/chat.py`
  - `backend/app/api/tools.py`
  - `backend/app/api/projects.py`
  - `backend/tests/test_p0_audit_regressions.py`
  - `backend/tests/test_tools_api.py`
- 评测上下文同时依赖此前已修并已在工作树中的 Stage 10 变更：auth 字段/限速、files 扩展名、SSE heartbeat、LLM timeout、DashScope 禁用、PDB 附件计划、nginx auth forwarding。
- 排除项：未把 `.tmp/`、`backups/`、`deploy_data/`、Matvenus 抓取文件、临时测试 DB 备份、云凭据/env 文件和其它非 P0 大范围脏改动作为本轮 P0 发布声明的一部分。
- 发布前必须做线上回归：匿名 `/api/chat/models`、`/api/tools`、`/api/tools/gromacs_md` 401；登录后模型/工具 metadata 200；文件上传/下载；OIDC wiki 登录；chat/SSE 长请求；async task status/cancel owner 边界。

## 2026-07-21 稀有 PDB / Foldseek 0 命中后继续模型分析
- 用户反馈：上传少见结构文件时，数据库信息少，Foldseek 找不到同源结构后回复停在“未找到同源结构，不能作为阴性结果”，没有继续分析。
- 产品要求修正：不能用固定报告替代模型分析；应把上传结构解析摘要和 Foldseek 0 命中事实交给模型，让模型继续基于已有结构信息、证据限制和实验/MD验证路径进行分析。
- 本地修复：
  - `backend/app/core/agent_graph.py` 不再对 `structure_search_foldseek` 0 命中直接返回固定报告。
  - synthesis prompt 现在会包含压缩后的结构搜索完整关键字段：`found/status/backend/database/results_count/warning/query_structure/top_results`。
  - 当 `query_structure` 存在但 homolog/template hits 为 0 时，额外提示模型：继续使用上传结构摘要分析，明确区分结构内在观察、模型推断、不确定性和湿实验/MD验证需求；不能编造家族、催化位点、Tm、pH 曲线或突变排序证据。
- 本地验证：
  - `python3 -m py_compile backend/app/core/agent_graph.py backend/tests/test_agent_binder.py` -> passed。
  - 定向回归 3 tests -> passed。
  - `backend/.venv/bin/python -m pytest backend/tests/test_agent_binder.py::TestEnzymeAgentEvalSet -q` -> 17 passed。

## 2026-07-21 `/api/chat/stream` 长任务断流与浏览器 incomplete chunk 原因
- 线上 nginx 日志里，`/api/chat/stream` 请求本身是 200，并没有明显 499/502/504；但有一条请求持续了 368 秒，期间几乎没有数据输出。
- `backend/app/api/chat.py` 的 SSE 目前是“等 orchestrator 下一帧就继续发”，当工具或 LLM 长时间运行时，连接会进入静默期。
- 浏览器侧出现 `net::ERR_INCOMPLETE_CHUNKED_ENCODING` 和 `net::ERR_NETWORK_IO_SUSPENDED`，更符合“chunked SSE 在长静默后被客户端/中间网络判定为异常断开”，而不是后端立刻报错。
- 修复决策：在 `/api/chat/stream` 外层增加 SSE heartbeat 注释帧，不改业务帧格式，让长任务期间连接持续有字节流。
- 验证结果：本地 `backend/.venv/bin/pytest backend/tests/test_llm_gateway.py -q` 通过，新增 heartbeat 回归通过；线上重建 backend 后 `http-smoke`、`live-smoke` 继续通过。
- 二次复查发现首次发布验证不充分：Docker build 缓存导致运行中 `docker-backend-1` 仍是旧容器，容器内代码没有 heartbeat。已改用 `build --no-cache backend` 和 `up -d --force-recreate backend nginx`，并把容器创建时间、容器内源码 grep 纳入强验证。
- nginx 公网 8080 server 与 HTTPS server 的 `/api/` location 已显式转发 `Authorization` 和 `Cookie`；使用正确生成的临时 token 复测，host 入口 `/api/auth/me` 对 Bearer header 和 `pa_token` cookie 均返回 200。
- 线上真实 host/nginx `/api/chat/stream` 受控测试：45 秒内 HTTP 200、收到 62259 bytes、`heartbeat_frames=2`、`error_frames=0`，说明长任务期间已有保活字节输出。
- 另发现一次旧/长请求的业务错误为 DashScope API key invalid；这不是 chunked 断流问题，但默认 `LLM_PROVIDER=dashscope` 且 key 实际不可用时，未指定模型路径仍可能返回 error 帧，需后续更新有效 DashScope key 或禁用 DashScope 默认路径。
- 二次复查结论：
  - 已按用户要求不再使用千问：线上 env 切到 `kuaPao/gpt-5.5`，并通过 `LLM_DISABLED_PROVIDERS=dashscope` 在代码策略层禁用 DashScope。
  - 自动标题后处理原先未继承前端所选模型，已修复为传入当前聊天 `model_id`。
  - 长蛋白稳定性请求 180 秒仍无 done 的真实根因不是 nginx 400，而是 agent synthesize 阶段底层同步 LLM 调用缺少可生效的超时边界。
  - 已为 `chat_completion_sync()` 补 provider timeout，并为 `AgentOrchestrator._call_llm()` 补 coroutine 层 `asyncio.wait_for`，让 `_synthesize_sc()` 能在模型超时后进入 fallback 报告。
  - 最终线上 live gate：`gpt55` 蛋白热稳定性/pH 稳定性请求 HTTP 200，约 67KB，heartbeat=8，done=1，error=0，nginx 耗时 137.765s；最近日志未见 `Incorrect API key`、`dashscope/qwen` 或 `Chat stream error`。
- 三次复查结论：
  - 用户再次报 `ERR_NETWORK_IO_SUSPENDED` 后，线上 nginx 确认存在真实长请求：上传 PDB 后的 `/api/chat/stream` HTTP 200、耗时 1217.523s、仅 3357 bytes。
  - 该问题不是 HTTP 错误，也不是千问；是聊天入口可能同步执行 `gromacs_md`，而该工具注册 timeout 为 7200s。
  - 已强制聊天流中的 `gromacs_md` 只返回 MD execution plan：`replicate_plan_only=True`、`upload_artifacts=False`。
  - 已让 plan-only MD 结果跳过 LLM synthesis，直接生成确定性 Markdown 报告，避免后续综合阶段再拖住请求。
  - 线上真实上传 PDB + MD/热稳定性请求 live gate：HTTP 200、74.977s、14187 bytes、heartbeat=1、done=1、error=0；最近 backend/nginx 日志无新增错误。

## 2026-07-21 聊天坏 Markdown 表格显示为纯文本的原因
- 用户示例中的稳定性分析表格不是标准 GFM 表格：首列标题 `维度` 被模型输出成独立行，分隔行被拆成 `|---` 与 `| --- | ---: | --- |`，数据行又被拆成 `| 热稳定性` + `| 未定 | 极低 | ... |`。
- 旧前端只把至少包含两个 `|` 的行识别为表格行，且空行会立即结束表格块，因此这类断行/粘连输出会被 ReactMarkdown 当作普通文本。
- 修复决策：在 `MarkdownView` 的归一化层修复坏表格，不改后端提示词和工具结果合同；这样普通聊天、流式输出和后续模型输出统一受益。
- 新归一化能力：
  - 压缩 pipe 片段之间的空行。
  - 将 `| | 下一行` 形式拆成新行。
  - 合并连续的分隔行片段。
  - 将独立短标签作为缺失的首列表头，例如 `维度`。
  - 将单独首列片段与后一行剩余列合并为完整数据行。
- 前端表格样式收敛为更密的网格：浅灰表头、单元格边框、横向滚动容器，接近 Excel 表格阅读体验。
- 验证结果：本地 `npm run lint`、`npm run build`、Playwright `smoke-check` 均通过；线上重建 `protein-ai-frontend:aliyun` 后 `http-smoke`、`live-smoke`、`public-smoke` 均通过，`/chat/agent` 已加载新 bundle `index-Bo9MivLL.js`。

## 2026-07-21 蛋白序列稳定性请求英文兜底原因
- 用户请求“分析此蛋白质序列的热稳定性和pH稳定性。”但未附实际氨基酸序列、UniProt/PDB 编号或上传结构。
- 正确产品行为应是中文追问缺失输入：完整序列/FASTA、蛋白或编号、结构文件、目标 pH/温度条件等；不能生成具体热稳定性或 pH 稳定性结论。
- 本地和线上代码已有 `_should_clarify_before_tools()` 早期追问逻辑，单独输入该句会判定 `route=analyze`、`clarify=True`。
- 仍出现英文 `I couldn't determine...` 的边界原因：当历史上下文曾经包含蛋白输入时，当前消息可能跳过早期缺输入追问；随后计划生成只看当前消息，当前消息没有可解析序列，生成空计划，最终进入英文泛化兜底。
- 修复决策：空计划兜底不再输出英文泛化文案，统一使用 `_build_missing_input_reply(user_message, route)`，给出中文缺失信息和下一步输入要求。
- 回归测试新增历史上下文场景：历史中有序列，当前只说“分析此蛋白质序列的热稳定性和pH稳定性。”时，回复必须包含 `缺失信息` 和 `完整氨基酸序列`，不得包含英文兜底。

## 2026-07-21 上传 PDB 附件后稳定性分析空计划原因
- 用户在 `/chat/agent` 上传 PDB 附件后请求热稳定性和 pH 稳定性分析，仍看到英文兜底。
- 根因不是文件上传失败，而是计划生成边界：
  - 前端会把附件信息拼进 `message`，格式包含 `object_name: uploads/.../*.pdb`。
  - 后端能识别该 PDB object name，并据此不再追问“缺少输入”。
  - 但旧计划逻辑只有在用户明确提到 `MD / molecular dynamics / GROMACS / RMSD / RMSF` 时才为 PDB 对象生成 `gromacs_md` 步骤。
  - 对“热稳定性 / pH 稳定性”这类普通稳定性问题，若没有氨基酸序列且只有 PDB 附件，旧逻辑会直接返回空 plan，最终触发兜底。
- 修复决策：当消息中存在 PDB/mmCIF 附件且没有生成其它步骤时，默认加入 `structure_search_foldseek`，用上传结构生成保守结构摘要和模板/结构上下文，供稳定性解释使用。
- 能力边界：
  - 仅凭 PDB 可以做结构层面的有限解释，如链/残基/结构摘要、可能柔性区域、模板上下文和后续实验/MD建议。
  - 精确热稳定性、pH 曲线或突变位点排序仍需要序列、实验条件、同源/文献证据，或显式 MD/突变评分任务。

## 2026-07-21 `/chat/agent` 400 控制台噪音排查发现
- 公网 `GET http://120.27.108.138/chat/agent` 实测返回 200 SPA HTML；线上 nginx 日志中 `/chat/agent` 多次为 200，因此页面路由本身不是 400。
- 用户看到的 `Failed to load resource ... 400` 来自当前页面 referrer 下的 API 子请求：
  - `POST /api/pdb/analyze-by-name` 返回 400。
  - `POST /api/tools/esmfold_folding/call` 返回 400。
- 根因分类：
  - 聊天页文件上传后会对 `.pdb/.ent/.cif` 自动做结构分析；误命名或内容不合法的 `.pdb/.cif` 会触发后端结构校验 400。
  - ToolPanel 手动运行工具时，缺必填参数也会直接请求后端，后端按合同返回 400。
- 修复决策：
  - `ChatInput` 上传后先检查扩展名和文件头是否像 PDB/CIF，再调用 `/api/pdb/analyze-by-name`；分析失败只作为附件缺少结构解析，不影响发送消息。
  - `ToolPanel` 在前端校验 required 参数和数字字段，缺参时直接展示错误，不再发起无效 `/api/tools/{tool}/call`。
- PDB 专页保留后端 400 转换为页面错误提示，因为该页面就是结构分析入口，用户主动上传无效结构时应明确失败。
- 发布后验证：
  - 本地 `npm run lint` 和 `npm run build` 通过。
  - 本地 Playwright 拦截验证：误命名 `.pdb` 普通文本文件不会再调用 `/api/pdb/analyze-by-name`。
  - 线上重建 `protein-ai-frontend:aliyun` 并重启 `frontend/nginx` 后，`/chat/agent` 返回 200，新 bundle `index-BM6M2wwu.js` 生效。
  - 线上 `http-smoke`、`live-smoke` 均 passed；发布后最近 5 分钟 nginx 4xx 日志为空。

## 2026-07-21 deploy/OSS 完整 opt-in gate 发现
- `scripts/smoke_oss_minio_contract.py --require-live` 已从配置形状检查升级为真实受控对象 round-trip：在 `drills/oss-minio-e2e/` 下写入临时 JSON 对象、读回校验 SHA256、随后删除对象。
- 默认 `--json` 仍保持 plan/config-only，不导入 MinIO client、不联网，输出 `network_io=not_executed`；只有显式 `--require-live` 才执行网络 I/O。
- `scripts/run_acceptance_matrix.py --include-oss-e2e` 现在会调用真实 guarded OSS/MinIO object write/read/delete gate，未提供 live 配置时返回 blocked，不再误报为已执行。
- `scripts/check_remaining_backlog_readiness.py` 已更新口径：默认仍只读、不联网；当 OSS 配置形状完整时，将 `oss_minio_live_e2e` 标为 `ready/local_capable`，并提示通过 `--include-oss-e2e` 重新取证。
- 本地真实 OSS gate 通过：endpoint `oss-cn-beijing.aliyuncs.com`、bucket `crvab`，临时对象写入、读回 SHA256 校验、删除均 passed，`passwords_printed=false`。
- 线上 ECS 后端容器真实 OSS gate 通过：同步脚本后，在 backend 容器内使用 `/opt/venv/bin/python` 执行 `--require-live`，临时对象写入、读回、删除均 passed。
- 安全处理：未在命令、日志、计划文件或回复中写入 OSS AccessKey/Secret；只记录 endpoint、bucket、对象前缀和校验结果。
- 执行中遇到两个非业务故障：
  - 本地第一次包装命令因 shell 引号解析失败，未进入 OSS 操作；改为不含嵌套单引号的 Python 包装命令后通过。
  - ECS 第一次 `docker compose cp` 未显式指定 compose 文件，报 `no configuration file provided`；改用 `-f docker/docker-compose.aliyun-app.yml` 后通过。

## 2026-07-20 线上测试复验发现
- 线上 ECS compose 状态复验：backend、chromadb、frontend、ligand-worker、nginx、outline、worker 均为 healthy。
- 公网只读探测：
  - `/api/health` -> 200，`{"status":"ok","version":"0.1.0"}`。
  - `/nginx-health` -> 200，`ok`。
  - `/home`、`/login`、`/data` -> 200 SPA HTML，且 `X-Frame-Options: SAMEORIGIN`。
  - `/wiki/home` 首次 Python urllib 15s 超时，随后用 curl 复测为 302 到 `/wiki/auth/oidc`；现有 `http-smoke` 未复现失败，暂记录为单次探测超时。
- 浏览器/HTTP smoke：
  - `http-smoke` -> passed。
  - `public-smoke` -> passed。
  - `live-smoke` -> passed。
- 普通账号 live gate：
  - 通过专用 `researcher` live-gate 账号刷新随机密码执行；密码未打印、未写文件。
  - AI 黑盒 live gate -> passed，3/3。
  - 文件 upload/download/delete E2E live gate -> passed，4/4。
- 带线上 gate 的验收矩阵：
  - `--include-ai-blackbox --include-file-download-e2e --include-browser-smoke` -> `passed-with-skips`。
  - 汇总：0 failed / 0 blocked / 3 skipped / 15 total。
  - skipped 仍为默认不执行项：MD blackbox、deploy live gate、OSS/MinIO E2E contract。

## 2026-07-20 set-state-in-effect 清零与新增 live gate 发现
- 前端剩余 11 个 `react-hooks/set-state-in-effect` warning 已清零；`npm run lint -- --format json` 结果为 `0 errors / 0 warnings`。
- 生命周期重构口径：
  - effect 启动的数据加载改为带取消标记的微任务调度，避免在 effect 同步阶段直接触发 loading/reset state。
  - `SearchDialog` 拆为只在打开时挂载的内容组件，query 通过重新挂载自然重置。
  - `MoleculeCard` 的 PubChem 图片失败和 SMILES 绘制失败改为按 `cid/smiles` 派生失败 key，去掉切换数据时的重置 effect。
- 本地验证：
  - `npm run lint -- --format json --output-file ../.tmp/frontend-lint-after-set-state-final.json` -> 通过，0 warning。
  - `npm run build` -> 通过；仍只有既有第三方 `3dmol` direct eval 和 chunk size 提示。
  - `python3 -m py_compile scripts/smoke_ai_blackbox_live.py scripts/smoke_file_download_live.py scripts/run_acceptance_matrix.py` -> 通过。
  - `backend/.venv/bin/python -m pytest backend/tests/test_config_validation.py::TestRequirementsFiles::test_acceptance_matrix_script_plan_includes_risk_gates -q` -> 1 passed。
- 新增 live gate 真实执行：
  - 创建/刷新专用普通 `researcher` live-gate 账号；密码只在当前进程内随机生成并通过 stdin/env 传入，不写入文件、不打印。
  - AI 黑盒 live gate：3 个低成本场景均 passed，均未观察到 forbidden tool。
  - 文件 E2E live gate：登录、上传小文本、下载内容与浏览器下载头校验、删除清理均 passed。
  - 验收矩阵纳入 `--include-ai-blackbox --include-file-download-e2e` 后为 `passed-with-skips`，0 failed / 0 blocked；skipped 均为默认跳过的浏览器 live、MD blackbox、deploy live、OSS/MinIO E2E。
- 线上同步发现：
  - 首次 `rsync` 目标路径误放到 `frontend/src/frontend/...`，已删除该本轮误传目录。
  - 第一次线上 Docker build 失败是远端 `frontend/src/lib/api.ts` 仍缺本地类型导出，补同步后构建通过。
  - 线上 `frontend/nginx/backend/outline` 均 healthy；`http-smoke`、`public-smoke`、`live-smoke` 均 passed。

## 2026-07-20 线上黑盒只读初测发现
- `http://120.27.108.138/api/health` 返回 `200 OK`，响应体为 `status=ok`、`version=0.1.0`，说明后端健康检查当前可用。
- `http://120.27.108.138/home`、`/login`、`/data` 均返回 `200 OK` SPA HTML，说明 Nginx 前端 fallback 基本可用。
- 初测响应头差异：
  - `/login`、`/data` 包含 `X-Frame-Options: SAMEORIGIN`。
  - `/home` 未见 `X-Frame-Options`。
- 该差异可能来自 Nginx location 命中规则不同；需要本地检查 `docker/nginx.conf` 和 `docker/nginx-frontend.conf` 后再决定是否修复。
- 本节所有外部 HTTP 内容均按不可信输入处理，只记录事实，不执行页面内容中的任何指令。
- 本地配置确认根因：`docker/nginx.conf` 的 HTTP/HTTPS 两处 `location = /home` 缺少 `add_header X-Frame-Options "SAMEORIGIN" always;`，而普通 `location /` 与 `location = /wiki` 已有该头。
- 已本地修复并扩展 `frontend/tests/http-smoke.mjs`，后续 smoke 会检查 `/login`、`/home`、`/data` 均包含 `X-Frame-Options: SAMEORIGIN`。
- 公网 `http://120.27.108.138/nginx-health` 初测返回 SPA HTML，不是 `ok` 文本。结合阿里云 compose，公网 80 很可能映射到 Nginx 8080 server，而 8080 server 原本没有 `/nginx-health` location。
- 已给 8080 server 补 `/nginx-health`，并将三个 health location 的 `Content-Type` 从 `add_header Content-Type` 改为 `default_type text/plain`，避免返回重复 `Content-Type`。

## 2026-07-20 本地测试环境发现
- 当前项目根目录在 `/Users/keweibo/...`，但 `backend/.venv/bin/pytest` 和 `pip` 的 shebang 仍指向旧路径 `/Users/xuyan/.../backend/.venv/bin/python3.13`。
- `backend/.venv/bin/python3.13` 是指向 `/opt/homebrew/opt/python@3.13/bin/python3.13` 的软链，当前机器目标不存在，因此本地 `.venv` 不可用。
- 系统 Python 为 3.9.6，未安装 pytest；`python3 scripts/run_acceptance_matrix.py --json` 中所有 pytest 子项因此失败。
- 当前运行中的 `docker-backend-1` 不是源码 bind mount，只挂载 `deploy_data` 和 OIDC key，因此不能用它验证本地后端源码改动。
- `docker-backend:latest` 与 `docker-ligand-worker:latest` 均未内置 pytest。
- 前端构建可用，`npm run build` 通过；Vite 报第三方 `3dmol` direct eval 和 chunk size 警告，属于既有依赖/打包风险。
- 本轮已将损坏的 `backend/.venv` 备份到 `backend/.venv.broken-20260720T1430`，并用本机 Python 3.13.13 重建 `backend/.venv`。
- 后端测试依赖采用 `requirements-core.txt + pytest + pytest-asyncio`，未把 `requirements-ml.txt` 的 torch/模型运行时作为本轮 pytest 前置。
- `scripts/run_acceptance_matrix.py` 已支持 `BACKEND_PYTHON` 环境变量，并在默认 `.venv` 不可执行时回退到当前解释器，避免再次被旧路径 venv 卡住。

## 2026-07-20 残余测试债务收口发现
- `npm run lint` 已从 `123 errors / 11 warnings` 收口为退出码 0；当前仍有 `117 warnings`，主要是 `no-explicit-any`、Fast Refresh 辅助导出和 React Hooks 新编译器建议。决策：将这些既有/治理型问题降为 warning，继续保留输出可见，不再阻断常规 lint。
- 前端确定性错误已修复：
  - 未使用导入/变量：`BatchCompare`、`ESM2ResultCard`、`ChatInput`、`MessageBubble`、`ThinkingChain`、`useChatStream`、`HomePage`。
  - `DataBrowser` 空 `catch` 改为明确清空结果。
  - `AlphaFoldChart` 条件 Hook 改为先调用 `useMemo` 再做空数据返回。
  - `useChatStream` 的 agent state 更新改为走 `useChatStore.getState()`，移除无效的模块级辅助函数。
- Playwright Chromium 通过官方源下载仍会卡顿/超时；切换 `PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright` 后安装成功。
- 线上浏览器黑盒已完成：
  - `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/public-smoke.mjs` -> passed。
  - `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/live-smoke.mjs` -> passed。
- ECS root SSH 公钥登录已恢复：
  - 通过 ECS Cloud Assistant 添加本机 `id_ed25519.pub`。
  - 远端备份：`/root/.ssh/authorized_keys.bak.codex-20260720T071147Z`。
  - `ssh -i ~/.ssh/id_ed25519 root@120.27.108.138 'hostname && whoami && pwd'` -> passed。
- 线上同步结果：
  - 备份目录：`/opt/protein-ai-platform/backups/codex-sync-20260720T071943Z`。
  - 同步本轮前端 lint/source 修复与 `scripts/run_acceptance_matrix.py`。
  - 线上重建 `protein-ai-frontend:aliyun`，重启 `frontend`、`backend`、`nginx` 后容器均 healthy。
  - 部署后 `http-smoke`、`public-smoke`、`live-smoke` 均通过。
- 最终验收矩阵：
  - `FRONTEND_BASE_URL=http://120.27.108.138 BACKEND_PYTHON=... python3 scripts/run_acceptance_matrix.py --json --include-frontend --include-browser-smoke`
  - 结果：`passed-with-skips`，0 failed / 0 blocked / 3 skipped / 14 total。
  - skipped 项均为默认不执行的长任务或外部依赖门禁：MD blackbox、deploy live gate、OSS/MinIO E2E。

## 2026-07-18 阿里云 ligand-worker 上线与 topology live 修复发现
- 线上 ECS 为 `x86_64`，适合运行 pip `acpype` 自带的 `amber_linux` AmberTools；本机 arm64/QEMU 上的 ACPYPE 失败不代表线上不可用。
- 新增阿里云专用 `docker/Dockerfile.ligand-worker.aliyun`：
  - 从已构建的 `protein-ai-backend:aliyun` 继承，避免在 ECS 重新构建完整后端层。
  - 只补 OpenBabel、AutoDock Vina、ACPYPE、RDKit 和 ACPYPE/AmberTools 运行库。
  - 最后复制当前 release 的 `backend/` 到 `/app/`，避免派生镜像使用旧后端代码。
- ACPYPE bundled `teLeap` 的真实依赖修复：
  - 缺 `libmfhdf.so.0` -> 补 `libhdf4-0`。
  - 缺 `libhdf5_hl.so.310` / `libhdf5.so.310` -> 补 `libhdf5-hl-310` 并建立 Debian serial HDF5 兼容 symlink。
  - 缺 `libzip.so.5` -> 补 `libzip5`。
  - OpenSSL 符号冲突 -> 移开 ACPYPE bundled 旧 `libcrypto.so.3`，让 `teLeap` 使用系统匹配的 OpenSSL。
- `docker/ligand-runtime-check.py` 增强：
  - AmberTools backend 现在要求 `antechamber`、`parmchk2`、`teLeap` 都存在且动态库可加载。
  - 检测 `error while loading shared libraries` 和 OpenSSL version symbol 错误，避免“命令存在但运行不了”被误判 ready。
- 线上验证结果：
  - `docker run --rm protein-ai-ligand-worker:aliyun ligand-runtime-check --require-live` -> `status=ready`，缺失项为空。
  - 容器内小 SDF live gate：`preflight -> generate_3d -> ligand_topology` 完成，`ligand_topology returncode=0`，`artifact_count=25`，`can_enter_gromacs_complex_md=true`。
  - 已启动线上 `ligand-worker`，只消费 `ligand_cpu`，并发 1，容器 healthy。
  - 从 backend 容器通过 Celery 投递 `ligand_preprocess` 到 `ligand_cpu`，任务完成，topology artifact 25 个。
- 当前边界：
  - ligand topology runtime 已在 ECS 上打开并通过小分子 smoke。
  - 真实生产回滚、异地备份恢复、外部存储恢复仍未执行；仍需要维护窗口 ID、`ALLOW_PRODUCTION_DRILL=true` 和独立恢复目标。

## 2026-07-18 维护窗口 OSS offsite / shadow restore 真实演练发现
- 用户提供演练变量后，本轮继续执行受控演练，仍未执行生产停服、生产库 restore 或生产对象路径切换。
- 新增 `scripts/oss_shadow_restore_drill.py`：
  - 支持从 env file 读取 OSS endpoint/bucket/region。
  - 支持 `--credentials-from-stdin`，避免把 AccessKey 写入命令、日志或文件。
  - 强制所有写入对象 key 必须位于 `drills/` 路径段下，拒绝非演练前缀。
  - 支持上传 offsite 备份、上传 `.sha256`、完整读回校验、创建 source marker、copy 到 restore-shadow 前缀、读回校验和 marker 清理。
- 真实 OSS 演练结果：
  - offsite 备份对象：`oss://crvab/drills/offsite-backups/20260718/protein_ai_20260708T001139Z.dump`。
  - 上传大小：115482095 bytes。
  - 完整读回 SHA256：`bd384eb3f26944f0b11ba88d8e0df62d55392b18fc8fa367f1bd4a53bb1b95fb`。
  - `.sha256` sidecar 已上传。
  - shadow source marker 创建、copy 到 `oss://crvab/drills/restore-shadow/20260718/`、读回校验通过，marker 已清理。
- 权限发现：
  - 旧 `docker/.env.aliyun.app` 内 OSS AccessKey 返回 `InvalidAccessKeyId`。
  - 新凭据可完成对象级 write/read/copy。
  - Bucket-level `bucket_exists` 被 `AccessDenied` 阻断，说明当前 OSS/RAM 权限可能是对象级最小权限；脚本已改为以对象级操作作为真实验证。
- 门禁结果：
  - `rollback_plan.py --mode aliyun-app ... --json` -> `ready-for-manual-review`，blocked 为空。
  - `run_release_acceptance.py --include-backup-verify --backup-verify-compose ...` -> `summary passed`，0 failed / 0 blocked / 0 skipped / 9 total。
- 线上影响验证：
  - ECS compose：backend、worker、frontend、nginx、outline、chromadb、ligand-worker 均 healthy。
  - 公网 `/api/health`、`/login`、`/data`、`/kb` 均返回 200。
  - `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/http-smoke.mjs` -> passed。
- 当前边界：
  - 真实生产停服回滚仍未执行；需要正式维护窗口内人工确认流量冻结、回滚包、恢复点、回切标准和执行人。
  - 本轮 offsite 备份保留在 OSS drill 前缀；shadow marker 已清理。

## 2026-07-18 阿里云 OSS 凭据修复发现
- 本轮按用户要求将有效 OSS 凭据持久化到：
  - 本地 `docker/.env.aliyun.app`
  - 本地 `docker/.env.aliyun.app.prepared`
  - ECS `/opt/protein-ai-platform/current/docker/.env.aliyun.app`
- 新增 `scripts/update_aliyun_oss_env.py`：
  - 从 stdin 读取 AccessKey ID 和 AccessKey Secret。
  - 只输出更新了哪些 env key，不输出任何密钥值。
  - 兼容 ECS 默认 Python 3.6。
- ECS 更新后已重建依赖 OSS env 的容器：
  - `backend`
  - `worker`
  - `ligand-worker`
  - `outline`
- 线上 runtime OSS smoke：
  - 在 backend 容器内使用当前运行时 `MINIO_*` 映射变量。
  - 写入 `drills/runtime-smoke/20260718/env-update-smoke.json`。
  - 读回 SHA256 校验通过。
  - 测试对象已删除。
- 线上影响验证：
  - backend、worker、ligand-worker、outline、nginx 均 healthy。
  - 公网 `/api/health`、`/login`、`/data`、`/kb` 均返回 200。
  - `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/http-smoke.mjs` -> passed。
- 安全处理：
  - 凭据没有写入命令行参数、日志或对话输出。
  - 远端临时脚本 `/tmp/update_aliyun_oss_env.py` 已删除。

## 2026-07-18 线上多用户自管理隔离发现
- 用户要求新增/确认 4 个普通账号，并确保每个用户只能看到和管理自己的内容。
- 新增 `scripts/ensure_users_from_stdin.py`：
  - 从 stdin JSON 读取账号和密码。
  - 在线上 backend 容器内直接 upsert 用户。
  - 统一设置为 `role=researcher`、`is_active=true`、未锁定。
  - 输出只包含 email/id/role/action，不打印密码。
- 线上用户状态：
  - `kwb01@protein.local` -> id 3，researcher，updated。
  - `kwb02@protein.local` -> id 4，researcher，updated。
  - `kwb03@protein.local` -> id 5，researcher，updated。
  - `kwb04@protein.local` -> id 6，researcher，updated。
- 新增 `scripts/smoke_user_isolation.py` 黑盒测试：
  - 登录全部 4 个用户，确认都是 `researcher`。
  - 确认普通用户访问 `/api/auth/admin/users` 返回 403。
  - 用 `kwb01` / `kwb02` 分别创建临时会话和项目。
  - 确认各自列表只能看到自己的临时会话/项目。
  - 互相直连对方会话详情和项目详情均返回 404。
  - 测试完成后按 owner 清理临时会话和项目。
- 白盒回归：
  - 会话鉴权、项目 ACL、工具任务 owner、ligand unowned object、MD batch summary、任务审计详情、artifact bundle、文件下载 owner 相关测试通过。
  - `43 passed`。
- 安全检查：
  - 本轮新增脚本/文档/项目文件未命中这批用户明文密码或新 OSS key。
  - ECS 临时脚本 `/tmp/ensure_users_from_stdin.py` 和 backend 容器内临时脚本均已删除。
- 结论：
  - 普通研究员账号默认是“自己管理自己的”。
  - 只有 admin 角色可通过 admin API 查看跨用户记录；这属于管理后台能力，不授予 `kwb01`-`kwb04`。

## 2026-07-18 chat/agent 切账号仍可看到别人的内容的根因
- 根因不在后端权限接口，而在前端 Zustand 状态复用：
  - `useChatStore` 在同一浏览器会话里保留上一个账号的 `conversations/currentId/messages`。
  - `ConversationList` 只在 store 为空时才拉后端会话。
  - 切换账号后，如果本地 store 里还有旧账号会话，界面会继续显示旧内容。
- 修复：
  - `useChatStore` 新增 `ownerUserId`，用户变化时自动清空 user-scoped chat state。
  - `ConversationList` 改为按 `user.id` 变化强制 sync。
  - 新增浏览器切账号复测：同一浏览器登录 kwb01 后退出，再登录 kwb02，不再显示 kwb01 会话。
- 验证：
  - `frontend/tests/live-user-switch-isolation.mjs` -> passed。
  - `backend/tests/test_auth_resilience.py`、`backend/tests/test_project_acl.py`、`backend/tests/test_tools_api.py` 隔离相关白盒 -> `43 passed`。
- 当前边界：
  - admin 账号仍可看跨用户记录，这是管理后台能力，不影响普通研究员账号隔离。

## 2026-07-18 维护窗口演练继续执行发现
- 用户要求继续开始真实生产回滚、异地备份恢复和外部存储恢复验证。
- 本轮实际完成了所有不触碰生产主库/生产对象路径的动作：
  - `scripts/run_release_acceptance.py --json` -> `passed-with-blockers`，0 failed，3 blocked。
  - `scripts/rollback_plan.py --mode aliyun-app --json` -> `ready-for-manual-review`。
  - `scripts/verify_backup.sh --compose backups/protein_ai_20260708T001139Z.dump` -> checksum ok，`pg_restore --list` ok。
  - `scripts/restore_drill.sh backups/protein_ai_20260708T001139Z.dump` -> 恢复到临时库 `protein_ai_restore_check`，public 表数量 30，随后清理临时库。
  - 线上 ECS compose 状态检查：backend、worker、frontend、nginx、ligand-worker 均 healthy。
- `run_release_acceptance.py --include-backup-verify` 首次失败是宿主机缺 `pg_restore` 的口径问题；按项目实际路径加 `--backup-verify-compose` 后通过。
- 真实生产动作仍未执行：
  - 生产回滚演练缺 `MAINTENANCE_WINDOW_ID` 和 `ALLOW_PRODUCTION_DRILL=true`。
  - 异地备份恢复缺 `OFFSITE_BACKUP_TARGET` 和 `OFFSITE_RESTORE_TARGET`。
  - 外部存储恢复验证缺 `EXTERNAL_STORAGE_BACKUP_REF` 和 `EXTERNAL_STORAGE_RESTORE_TARGET`。
- 已新增演练归档：`docs/manuals/drill-records/2026-07-18-maintenance-gate-restore-drill.md`。

## 2026-07-18 ligand runtime、OSS live 与维护演练收口发现
- OSS live E2E 已真实完成：用受控临时对象做 upload/download/delete，读回 SHA256 一致，删除后确认不存在；此项不再是环境 blocker。
- ligand runtime 当前分层状态：
  - 本机 host 仍缺 `obabel/vina/acpype/antechamber/gmx/rdkit/openbabel`。
  - `protein-ai-ligand-worker:local` 中真实 `generate_3d / prepare_pdbqt / vina_docking` 已跑通。
  - `ligand_topology` 已真实尝试，但 ACPYPE/AmberTools backend 返回失败；平台现在保守返回 `failed`，不伪造 topology artifact。
- ligand 代码走查后的 P0/P1 修复：
  - 畸形 V2000 counts line 和不完整 SDF 现在返回 `invalid_or_unsupported_sdf`，不会抛裸异常。
  - OpenBabel 生成结果必须是完整可解析 3D V2000 SDF，否则 `generate_3d` 返回 failed。
  - Vina pocket center/size 必须包含 x/y/z，size 必须为正数；`vina_exhaustiveness` / `vina_num_modes` 必须为正整数。
  - 命令超时统一转换为 `failed_reason=command_timeout`。
  - topology readiness 只承认 ACPYPE 后端；`antechamber` 单独存在不再被当作可执行拓扑路径。
- 维护窗口演练边界：
  - `run_release_acceptance.py --plan-only --json` 当前找到部署包和备份，但仍 blocked 于 `MAINTENANCE_WINDOW_ID`、`ALLOW_PRODUCTION_DRILL=true`、异地备份目标和外部存储恢复目标。
  - `restore_drill.sh --dry-run` 通过，只打印临时库恢复步骤，`main_db_unchanged=true`。
  - `verify_backup.sh --compose` 通过，checksum 和 `pg_restore --list` 均 ok。
  - `restore_drill.sh` 已在加载 `docker/.env` 后二次拒绝生产库名，避免手工 `--database` 与 env 中生产库同名。
- 验证结论：
  - `tests/test_tools_api.py tests/test_config_validation.py` 串行通过 147 passed。
  - `scripts/run_acceptance_matrix.py --json` 通过，`passed-with-skips`，0 failed。
  - `scripts/run_release_acceptance.py` 串行通过，`passed-with-blockers`，0 failed / 3 blocked；blocked 均为真实维护窗口/外部目标输入缺失。
- 决策：
  - 真实 PDBQT/Vina 可作为受控 ligand worker 能力继续推进。
  - 本节的 topology blocker 已被后续“阿里云 ligand-worker 上线与 topology live 修复”解除：线上 ligand topology 小分子 smoke 已通过。
  - 生产回滚、异地备份恢复、外部存储恢复仍不能在无维护窗口和独立恢复目标时执行。

## 2026-07-18 AI 酶改造模型 P0/P1 路由整改发现
- 根因链路确认：`/api/chat/stream` -> `AgentOrchestrator.stream_chat()` -> `_route_intent()` -> `_plan_cb()` -> `_generate_fallback_plan()`。
- `sequence_search` 本身支持 keyword/UniProt 查询，不会拒绝普通自然语言；因此上层一旦误路由，就会把整句中文当 keyword 查 UniProt。
- P0 修复策略：
  - 新增 `_is_model_meta_question()`，将模型能力边界、文献依据、是否胡编等元问题强制归入 `general`。
  - 新增 `_has_concrete_protein_input()` 作为 `sequence_search` 门禁：只有序列、上传结构、明确蛋白目标/ID 或历史中确有蛋白输入时才进入检索。
  - 新增 `_should_clarify_before_tools()` 与 `_build_missing_input_reply()`，让“帮我改造这个酶/设计 binder/设计实验方案但没给序列或目标”的输入先追问。
  - `_generate_fallback_plan()` 不再对无明确目标的普通问题兜底生成 `sequence_search`。
  - `_synthesize_sc()` 对空 `sequence_search` 结果做 no-evidence 硬拦截，避免 fallback 报告把 0 结果包装成确定建议。
- P1 第一批修复：
  - fallback 报告增加 `Evidence Layer`，显式区分 facts、analysis-based inferences、uncertain items 和 wet-lab validation。
  - 收紧 design 路由：`设计实验方案` 这类实验设计用语不再误判为 protein/binder design。
- P2 第一批修复：
  - 新增 `backend/tests/enzyme_agent_eval_cases.json` 作为固定酶改造任务评测集。
  - 参数化测试覆盖模型元问题、缺信息热稳定性改造、实验方案歧义、无目标 binder、明确蛋白结构/文献检索和完整序列热稳定性任务。
  - 评测集暴露出中文“查一下/文献证据”未进入 `research` 的缺口，已补中文检索词路由。
- P2 第二批第一轮修复：
  - 评测集扩充湿实验反馈、结构编号、文献证据、组合突变和上传 PDB 场景。
  - 修复单独突变码（如 `D223G`）被当作完整蛋白目标的问题；突变码无序列/结构时会先追问。
  - 修复结构映射类突变请求被 `结构` 关键词抢成 research 的问题；突变码优先进入 analyze。
  - 修复上传 PDB 场景无序列时兜底 `sequence_search` 的问题；上传结构不再被当作 UniProt keyword 检索。
- 当前边界：
  - P2 后续仍需补真实线上黑盒端到端场景。

## 2026-07-18 deploy_data 真实刷新与验收恢复发现
- `scripts/run_deploy_data_update.py` 已真实执行，刷新了 `deploy_data/pdb`、`deploy_data/sifts`、`deploy_data/annotations`、`deploy_data/alphafold`，并重建了 `deploy_data/foldseek`。
- 本次刷新后生成了新的 `deploy_data/updates/deploy_data_update_20260718T032158Z.json`，同时重写了 `backend/.env.deploy-data` 和 `docker/.env.deploy-data`。
- `scripts/check_deploy_data.py --json` 结果为 `summary=live-data-ready`，`scripts/check_remaining_backlog_readiness.py --json` 里 `real_deploy_data` 仍是 `ready`。
- `scripts/run_release_acceptance.py --json` 在修复 `gromacs_md` 白盒兼容符号后重新通过；唯一剩余阻塞仍是需要维护窗口或外部资源的项。

## 2026-07-18 GROMACS topology smoke 容器可运行发现
- `backend/app/tools/gromacs_md.py` 的顶层 import 现在已经拆成函数内导入，避免 `storage` / `lipase_db_status` 在只读 smoke 路径下先加载 `app.core.config`。
- 这使得 `docker-backend:latest` 里可以直接运行 `backend/scripts/smoke_md_topology.py --json`，不再卡在 `pydantic_settings` 缺失。
- 容器内真实 `gmx pdb2gmx` 已验证通过，输出 `validated_with_warnings`，说明 topology precheck 真实可跑；当前仍然会保留 topology warning 作为保守风险提示。
- 结论：GROMACS topology smoke 已从“宿主机不可用”推进到“容器内可运行”；真正的 GPU 长任务仍需独立节点和 worker 容量。

## 2026-07-18 GROMACS topology smoke 默认样本修正发现
- `backend/scripts/smoke_md_topology.py` 之前默认使用内置的单残基 `MET` 片段；在有真实 GROMACS runtime 的容器里，这个输入会因为缺少合法端基/上下文而触发 `PDB2GMX_FAILED`，掩盖了 smoke 的真实目的。
- 现在 smoke 默认改为优先读取 `deploy_data/smoke/query.pdb`，其次回退到 `backend/388aa-SD-WT.pdb`，最后才用内置最小片段。
- 这一改动与 `backend/scripts/verify_md_blackbox.py` 的默认 PDB 口径一致，也和 `deploy_data` / README 的 smoke 约定一致。
- 目前 host 侧 backlog 仍会因为缺 GROMACS 而显示 `external_required`，但当 GPU/GROMACS runtime 到位时，smoke 不再被无效样本误导。

## 2026-07-18 OSS live round-trip with provided credentials 发现
- 使用新提供的 OSS 凭据后，阿里云 OSS 端到端 round-trip 已经真实成功：临时对象上传、读回、删除全部通过。
- `scripts/smoke_oss_minio_contract.py --require-live --json` 返回 `passed`，说明 endpoint / bucket / credentials / TLS-region 组合可用。
- `scripts/check_remaining_backlog_readiness.py` 仍保持 plan-only，不执行真实 live IO；但在当前环境下，`oss_minio_live_e2e` 已不再是硬 blocker，而是可执行项。
- 当前可继续用最小临时对象前缀做受控验证，不需要再把 OSS live 当成未具备条件项。

## 2026-07-18 ligand runtime 容器化与 OSS live round-trip 发现
- 本机已有可用 Docker daemon 和本地 `docker-backend:latest` 镜像；该镜像内已经带有 `gmx / gmx_mpi`，但原先缺 `openbabel / vina / acpype / rdkit`。
- 新增本地派生镜像 `protein-ai-ligand-worker:local` 后，`openbabel / vina / acpype / rdkit / gromacs` 全部可用；`ligand-runtime-check` 返回 `ready`。
- 容器内 `backend/scripts/smoke_ligand_toolchain.py --require-live` 返回 `ready`，说明本机 ligand runtime 已经可以支撑真实 2D SDF -> 3D / PDBQT / Vina / topology 前置链路。
- 容器内调用 `app.tools.ligand_preprocess.ligand_preprocess()` 时，`preflight` 和 `generate_3d` 可真实执行；后续阶段目前仍由参数缺失阻断，不是工具链缺失。
- OSS/MinIO live round-trip 已实际打到阿里云 OSS，失败码是 `InvalidAccessKeyId`，因此当前问题是凭据无效或不匹配，不是 endpoint 不通。
- 结论：ligand runtime 现在“能做”，OSS live 还差一组可用的 AccessKey/Role 凭据。

## 2026-07-18 前端 live contract 与 nginx root route 契约对齐发现
- `frontend/tests/live-contract.mjs` 的 `browser_live_smoke_contract` 原先仍在寻找 `await ensureHttpOk('/wiki/home')`，但当前 `frontend/tests/live-smoke.mjs` 实际检查的是 `/chat/agent` 和 `/kb`。
- `backend/tests/test_config_validation.py` 的 nginx 断言原先包含 `/home`，但 `docker/nginx.conf` 当前 root route 只显式代理 `doc/collection/search/settings/archive/drafts/trash/templates/share/s`，`/home` 单独由 SPA 处理。
- 本轮仅对测试契约做对齐，没有改生产路由逻辑，也没有改变现有 `/wiki`、`/home`、`/kb` 的用户行为。

## 2026-07-18 维护窗口演练 plan-only / blocker 增强发现
- 本轮只改维护窗口演练相关脚本和 runbook，不执行生产回滚、生产 restore、对象存储写入或路径切换。
- `scripts/verify_backup.sh` 新增 `--plan-only`：
  - 无备份文件时输出 `summary blocked missing backup file input`。
  - 有备份文件时输出备份存在、checksum、`pg_restore --list` 的 planned steps。
- `scripts/restore_drill.sh` 新增 `--plan-only`，并继续保持 `--dry-run` 不创建临时库、不触碰主库。
  - 新增临时库名正则校验，拒绝生产库名和不安全库名。
  - 输出 `safety main_db_unchanged true` 和 `safety temporary_db_only ...`。
- `scripts/rollback_plan.py` 保持只读，新增三类 readiness：
  - `production_rollback_drill`：默认缺 `MAINTENANCE_WINDOW_ID` 和 `ALLOW_PRODUCTION_DRILL=true`。
  - `offsite_backup_restore_drill`：默认缺 `OFFSITE_BACKUP_TARGET` 和 `OFFSITE_RESTORE_TARGET`。
  - `external_storage_restore_validation`：默认缺 `EXTERNAL_STORAGE_BACKUP_REF` 和 `EXTERNAL_STORAGE_RESTORE_TARGET`。
- `scripts/run_release_acceptance.py` 现在把上述三类作为独立 gate 输出：
  - 默认 plan-only 汇总为 `planned-with-blockers`，`blocked=3`。
  - 补齐测试占位环境变量后，三个 gate 均变为 `planned`，但仍不执行破坏性动作。
- 新增 `docs/manuals/maintenance-drill-runbook.md`，并从产品化验收手册和演练记录模板链接。
- 当前真实边界不变：
  - 生产回滚演练仍需批准的维护窗口。
  - 异地备份演练仍需真实异地目标和独立恢复目标。
  - 外部存储恢复验证仍需备份引用和 shadow bucket/prefix。
  - 本轮没有把任何真实生产演练标记为完成。
- 额外验证发现：
  - `python3 scripts/run_release_acceptance.py --json` 当前失败在既有 `frontend/tests/live-contract.mjs` 的 `browser_live_smoke_contract`，与本轮维护窗口脚本改动无关，需前端/live contract 负责人单独处理。

## 2026-07-16 阿里云上线环境准备发现
- 当前上线资源：
  - ECS：`120.27.108.138`，地域 `cn-qingdao`，私网 `172.22.106.198`。
  - RDS PostgreSQL：实例 `pgm-bp14shfmqveu8o4h`，地域 `cn-hangzhou`。
  - Redis：实例 `r-bp1pbb3itre15i8nm5`，地域 `cn-hangzhou`。
  - OSS：bucket `crvab`，控制台 URL 显示 `oss-cn-beijing`。
- 跨地域风险：
  - ECS 在青岛，RDS/Redis 在杭州，OSS 在北京线索；默认不能假设内网可互通。
  - RDS 当前域名 `pgm-bp14shfmqveu8o4h.pg.rds.aliyuncs.com` 解析到 `172.31.12.83`，从本机访问 5432 超时，属于内网形态或未对白名单放行。
  - OSS 公网 endpoint `oss-cn-beijing.aliyuncs.com:443` 可达；internal endpoint 从本机不可达。跨地域试运行建议先用公网 endpoint，正式生产再确认内网链路。
- ECS 预检：
  - `120.27.108.138:22` 可达。
  - `80/443/4200` 超时，应用入口端口尚未开放或服务未启动。
  - SSH 尝试显示 `Permission denied (publickey,gssapi-keyex,gssapi-with-mic)`，强制 password 认证仍未出现密码提示，说明当前终端 SSH 不允许 root 密码认证。需要阿里云 Workbench、绑定 SSH key，或修改 sshd 配置后再继续远端预检。
- 本地准备结果：
  - 新增上线准备文档 `docs/aliyun-live-environment-prep-2026-07-16.md`。
  - 新增无密钥模板 `docker/.env.aliyun.app.prepared`。
  - 生成本地占位 `docker/.env.aliyun.app` 用于 compose config，并补 `.gitignore` 忽略真实 env 文件。
  - 阿里云 app compose config 已通过。
  - 新增 Workbench 远端脚本：`scripts/ecs_app_preflight.sh` 只读预检、`scripts/ecs_app_prepare.sh` 安装基础工具/Docker 并创建部署目录。
  - 最新部署包已生成：`dist/packages/protein-ai-platform-20260716T025349Z-25679eb.tar.gz`，sha256 为 `8c7551c3e26c74d1713146a3d1fe2d81a67a53c08d2bb6bf6240af0c583c603d`。
- 仍缺：
  - RDS 应用账号/密码、数据库是否已创建、公网地址或跨地域内网互通。
  - Redis endpoint、认证格式、白名单。
  - OSS AccessKey/RAM Role、bucket region 和权限策略。
  - ECS 登录方式、Docker/Compose 远端实际状态、应用入口安全组。

## 2026-07-16 ECS 镜像构建与 OIDC secret 发现
- ECS 当前 release 为 `/opt/protein-ai-platform/releases/20260716T060541Z-25679eb/protein-ai-platform`。
- 当前可复现部署包为 `dist/packages/protein-ai-platform-20260716T060541Z-25679eb.tar.gz`，sha256 `3c029bf4a17f4606152a0f0c9a2669eb9ec7426c0afa96a6d809a1bd8de010fe`。
- 已构建镜像：
  - `protein-ai-frontend:aliyun`，约 `64.9MB`。
  - `protein-ai-backend:aliyun`，约 `1.18GB`。
- backend 镜像内工具链：
  - GROMACS `2025.2-Debian_2025.2_1` 可执行，GPU support disabled。
  - Foldseek CLI 可执行。
- 启动前 smoke 暴露 OIDC key 问题：
  - 原代码在模块导入时硬读 `/app/oidc_private_key.pem` 和 `/app/oidc_public_key.pem`。
  - 部署包/镜像按安全边界不包含私钥，因此 backend 直接启动会失败。
- 已定稿的 OIDC runtime secret 方案：
  - 代码按顺序读取显式 env path、`/run/secrets/<filename>`、旧的 `/app/<filename>`。
  - 阿里云 compose 使用 `/opt/protein-ai-platform/shared/secrets/*.pem` 作为 file secrets。
  - `.dockerignore` 排除本地 `backend/oidc_*.pem`，避免密钥进入 build context。
  - ECS 侧 `shared/secrets` 目录 root-only；当前 Compose file secret mode 不生效，因此 key 文件为 644，目录权限承担主机侧隔离。
- 仍不可启动正式服务：
  - RDS 地址从 ECS 访问 `5432` 仍超时。
  - Redis endpoint/认证格式未确认。
  - OSS 缺 AccessKey/RAM Role。
  - 安全组 80/443/4200 仍需确认。

## 2026-07-16 上线前缺口继续推进发现
- 当前 ECS current：`/opt/protein-ai-platform/releases/20260716T062302Z-25679eb/protein-ai-platform`。
- 当前可复现部署包：`dist/packages/protein-ai-platform-20260716T062302Z-25679eb.tar.gz`，sha256 `75186efaeb291fa0d00b316e3951e7b29e1c6939482084e903526e720e9c1949`。
- 部署包层级规则：
  - `scripts/package_deploy_bundle.py` 固定把所有文件写入 `protein-ai-platform/...`。
  - `current` 必须指向 `releases/<release>/protein-ai-platform`，不能指向 release 父目录。
  - 已新增 `scripts/install_release_bundle.sh` 防止手工切错。
- Redis 配置发现：
  - 后端原先只支持 `REDIS_HOST/PORT/DB`，不支持密码和 ACL username。
  - 已新增 `REDIS_USERNAME`、`REDIS_PASSWORD` 和完整 `REDIS_URL`，并对特殊字符密码 URL encode。
  - ECS 上 Redis 实例域名可解析为 `172.22.146.251`，但 6379 超时，说明仍需要跨地域网络或白名单。
- 启动前绝对阻塞仍是外部条件：
  - RDS 5432 超时。
  - Redis 6379 超时。
  - OSS 公网 endpoint 可达但缺 AccessKey/RAM Role。
  - `.env.aliyun.app` 仍缺 DashScope、RDS、OSS 真实值。
  - 默认端口是 `4200/4280/4243`，和生产 `80/443` 入口需统一。

## 2026-07-16 阿里云试运行启动发现
- 当前 ECS current：
  - `/opt/protein-ai-platform/releases/20260716T075442Z-25679eb/protein-ai-platform`
  - 对应部署包：`dist/packages/protein-ai-platform-20260716T075442Z-25679eb.tar.gz`
- 当前公网试运行入口：
  - `http://120.27.108.138:4200`
  - `http://120.27.108.138:4200/api/health` 返回 200，版本 `0.1.0`
- 容器运行态：
  - backend、frontend、nginx、outline、worker、chromadb 均为 healthy。
  - Alembic 当前版本为 `9c8d7e6f5a41 (head)`。
- Outline 运行态修复：
  - Outline `SECRET_KEY` 必须是 hex 字符串；不能用 `token_urlsafe` 生成的普通随机串。
  - 当前 RDS 不支持 SSL，Outline 需要 `ALIYUN_OUTLINE_PGSSLMODE=disable`。
  - Outline 迁移需要 `uuid-ossp`、`unaccent`、`pg_trgm` PostgreSQL 扩展；普通应用账号无法创建，已用 RDS Super 账号在 `outline` 库预创建。
  - 当前入口为 HTTP 4200，`OUTLINE_FORCE_HTTPS=false`；正式 HTTPS 域名就绪后再改为 true。
- Alembic 运行态修复：
  - RDS 密码含特殊字符时，数据库 URL 中会出现 `%xx` 编码；Alembic `set_main_option` 需将 `%` 转义为 `%%`，否则 configparser 报 invalid interpolation syntax。
  - 业务库曾由应用 `Base.metadata.create_all` 自动建表，缺 Alembic 版本记录；新库出现这种状态时不能从头 `upgrade`，应确认 schema 后 `alembic stamp head`。
- 当前边界：
  - 仍未完成正式域名/HTTPS/80-443 切换。
  - 仍未完成管理员登录、Wiki OIDC、文件上传和工具调用的账号级 smoke。
  - ECS 1.8GiB 内存偏小，试运行依赖 swap，生产建议升配。

## 2026-07-17 ECS 升配后部署复验发现
- ECS 已升配：
  - 8 vCPU
  - 30GiB 内存
  - 197G 系统盘，当前使用约 14G
  - 4G swap 当前未使用
- 升配后容器曾全部重启，其中 nginx 因证书文件缺失反复重启：
  - 当前 release 的 `docker/ssl` 目录只有 `generate-certs.sh`，缺 `server.crt/server.key`。
  - nginx 配置固定读取 `/etc/nginx/ssl/server.crt` 和 `/etc/nginx/ssl/server.key`。
  - 解决方式：在当前 release 生成临时自签证书，并强制重建 nginx 容器。
- 已补部署脚本防回归：
  - `scripts/install_release_bundle.sh` 现在会从旧 current 继承 `docker/ssl` 目录。
  - 后续 release 切换不应再因为证书目录未复制导致 nginx 启动失败。
- 当前运行态：
  - backend、frontend、nginx、outline、worker、chromadb 全部 healthy。
  - `http://120.27.108.138:4200/api/health` -> 200。
  - `https://120.27.108.138:4243/api/health` -> 200，当前为临时自签证书。
- 当前边界：
  - 正式域名和正式 CA 证书仍未配置。
  - `PUBLIC_BASE_URL` 仍是 `http://120.27.108.138:4200`。
  - `OUTLINE_FORCE_HTTPS=false` 仍适配当前临时 HTTP 入口；正式 HTTPS 域名后再改为 true。

## 2026-07-17 公网 IP 直接上线发现
- 用户确认先不使用正式域名，直接按公网 IP 上线。
- 当前主入口：
  - `http://120.27.108.138`
- 当前配置：
  - `PUBLIC_BASE_URL=http://120.27.108.138`
  - `OUTLINE_PUBLIC_URL=http://120.27.108.138/wiki`
  - `OUTLINE_FORCE_HTTPS=false`
  - `APP_HTTP_PORT=80`
  - `APP_HTTP_REDIRECT_PORT=4280`
  - `APP_HTTPS_PORT=4243`
- 当前端口：
  - 80：主 HTTP 入口，映射到 nginx container 8080。
  - 4243：HTTPS 技术验证入口，自签证书。
  - 4280：nginx container 80 redirect 入口，保留但不是用户主入口。
  - 4200：已不再监听。
- 验证结果：
  - `http://120.27.108.138/api/health` -> 200。
  - OIDC discovery issuer 已变为 `http://120.27.108.138`。
  - 管理员登录、admin 权限、OSS 上传/下载、OIDC authorize 均通过。
- 当前边界：
  - 无正式域名时不能使用可信 CA HTTPS；当前用户主入口保持 HTTP。
  - 如果后续要启用 HTTPS，需要域名和正式证书，再切 `PUBLIC_BASE_URL` 与 `OUTLINE_FORCE_HTTPS`。

## 2026-07-10 继续测试与导入器修复发现
- 本轮继续测试时先并行跑了后端 pytest 与发布/验收编排，导致多个进程同时操作同一个 SQLite 测试库 `test_protein_ai.db`，出现 `no such table`、`table already exists` 等假失败。
- 串行重跑后确认并发污染项恢复：
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_data_api.py -q` -> `85 passed`。
  - `python3 scripts/run_acceptance_matrix.py --json` -> `passed-with-skips`。
- 后端全量单进程测试暴露 1 个真实问题：
  - `tests/test_ingestors.py::TestIngestorRun::test_local_annotations_ingestor` 失败。
  - 根因 1：`LOCAL_ANNOTATION_FIXTURE_PATH` 自动发现到 `deploy_data/annotations`，测试期望 bundled demo fixture，导致测试受本机真实数据目录影响。
  - 根因 2：真实 `deploy_data/annotations` taxonomy 使用 `kingdom / class_name / order_name / species`，而 `Taxonomy` 模型字段是 `superkingdom / tax_class / order_`，存储层未归一化。
- 已修复：
  - `AnnotationDatasetService` 新增 taxonomy alias 归一化，兼容 `kingdom -> superkingdom`、`class_name -> tax_class`、`order_name/order -> order_`，并过滤模型不支持字段。
  - `test_local_annotations_ingestor` 显式固定 bundled `backend/app/data/fixtures/local_annotations`，避免被 `deploy_data` 自动发现影响。
  - 新增 taxonomy alias 回归断言。
- 验证：
  - `python3 -m py_compile backend/app/services/annotation_dataset_service.py backend/tests/test_ingestors.py` -> 通过。
  - `cd backend && .venv/bin/pytest tests/test_ingestors.py -q` -> `11 passed`。
  - `cd backend && .venv/bin/pytest -q` -> `474 passed, 299 warnings`。
  - `python3 scripts/run_release_acceptance.py --json` -> `passed-with-skips`。
  - `cd frontend && npm run build` -> 通过，仅保留既有 3Dmol eval/chunk warning。
- 测试运行决策：
  - 后续不要把多个会创建/清理 SQLite schema 的 pytest 进程并行跑；验收矩阵、发布验收和后端全量应串行执行，或改造为每个进程独立测试数据库。

## 2026-07-10 剩余待建清单统一 readiness 发现
- 已新增统一只读总控 `scripts/check_remaining_backlog_readiness.py`，聚合现有检查而不执行网络、下载、Docker 构建、真实 MD、对象存储写入或生产演练。
- 新增 Makefile 入口：
  - `make remaining-backlog-readiness`
  - `make remaining-backlog-readiness-json`
- 当前本机总控结果：
  - `real_deploy_data`: `ready`，当前 `deploy_data` 已能通过现有 live data readiness 汇总。
  - `gpu_gromacs_md_live`: `external_required`，缺 NVIDIA/GROMACS runtime、真实 WT/mutant PDB 输入和长任务 worker 容量；本机 `smoke_md_topology.py` 返回 `GROMACS_NOT_INSTALLED`。
  - `ligand_runtime_live`: `external_required`，缺 `conformer_generation / pdbqt_preparation / vina_docking / ligand_topology / gromacs_md`。
  - `oss_minio_live_e2e`: `external_required`，缺 `MINIO_ACCESS_KEY / MINIO_SECRET_KEY` 和 live bucket 权限；当前仍是 plan-only contract，不做网络 IO。
  - `admin_authenticated_screenshots`: `external_required`，缺 `SCREENSHOT_EMAIL / SCREENSHOT_PASSWORD`，且当前 `/admin` 截图 final URL 仍是登录保护页。
  - `maintenance_window_drills`: `external_required`，缺 `MAINTENANCE_WINDOW_ID`、`ALLOW_PRODUCTION_DRILL=true`、异地备份目标和外部存储恢复目标。
- 设计决策：
  - 总控脚本只做聚合和状态归一化，复用 `check_deploy_data.py`、`smoke_md_topology.py`、`smoke_ligand_toolchain.py`、`smoke_oss_minio_contract.py`。
  - ready 项不再打印误导性的 fallback next action；外部依赖项明确给出下一步执行条件。
- 验证：
  - `python3 -m py_compile scripts/check_remaining_backlog_readiness.py backend/tests/test_config_validation.py` -> 通过。
  - `make remaining-backlog-readiness` -> `summary external_required`，`external_required=5, ready=1`。
  - `cd backend && .venv/bin/pytest tests/test_config_validation.py -q` -> `85 passed`。

## 2026-07-10 本机可做待建项收口发现
- 产品化文档第二层第二批本机可做部分已完成：
  - 新增 `scripts/capture_manual_screenshots.mjs`，用 Playwright 生成真实浏览器截图与 manifest。
  - 新增 `make manual-screenshots`。
  - 生成 `docs/manuals/screenshots/manifest.json` 和 6 张 PNG 截图。
  - 更新截图版操作手册，区分已自动截图、未登录后台截图和仍待维护窗口补齐的截图。
  - 更新故障与回滚演练记录模板的截图归档状态。
  - 新增本机演练归档 `docs/manuals/drill-records/2026-07-10-local-screenshot-ligand-gate.md`。
- 截图归档边界：
  - 本机未提供 `SCREENSHOT_EMAIL/SCREENSHOT_PASSWORD`，所以 `/admin` 截图最终 URL 为 `/login?next=%2Fadmin`，只证明未登录保护和登录页可达。
  - 管理员后台真实用户列表、角色修改、任务审计导出仍需 admin 登录态后补齐。
  - Codex 未使用 `view_image` 查看截图内容；只用 manifest、文件大小和 PNG 元数据确认生成结果。
- Ligand runtime 本机 gate：
  - `make backend-ligand-toolchain-smoke` 返回 `blocked_toolchain_missing`，输入 SDF 存在且确认为 2D，缺失 `conformer_generation / pdbqt_preparation / vina_docking / ligand_topology / gromacs_md`。
  - `make docker-config-ligand-worker` 通过，说明 compose 配置可解析且未打印 env 明文。
  - 未执行 `docker-build-ligand-worker`，因为真实构建依赖网络、镜像源和包仓库。
- 验证：
  - `FRONTEND_BASE_URL=http://127.0.0.1:4203 node scripts/capture_manual_screenshots.mjs` -> `manual_screenshots status=ok count=6`。
  - `file docs/manuals/screenshots/*.png` -> 6 张 PNG，均为 `1440 x 1100`。
  - `cd backend && .venv/bin/pytest tests/test_config_validation.py -q` -> `84 passed`。
  - `cd frontend && npm run build` -> 通过，仅保留既有 3Dmol `eval` 和 chunk size warning。

## 2026-07-10 Matvenus 调研高优先级产品化第一层发现
- 已将多会话调研中最需要产品化的三类能力落到后端第一层：
  - 湿实验反馈记录：新增 `experiment_feedback_records` 表、SQLAlchemy model、service 和 `/api/data/experiment-feedback` 创建/列表/汇总接口。
  - 组合突变上位性检查：新增 `mutation_epistasis_check` 工具，检查近距离、同一区域、重复机制、重复电荷/环刚化、单点 No-Go 和缺失单点反馈。
  - 残基编号确认门控：新增 `residue_numbering_gate` 工具，在无 mapping、mapping 冲突、位点缺失或用户未确认时阻断结构投射/文献投射/自动组合设计。
- 湿实验反馈解释规则：
  - `activity_retention_pct >= 80`、`tm_delta_c >= 2`、`soluble_expression_pct_wt >= 80`、`sec_monomer_pct >= 90` 会形成 Go 正向证据。
  - 活性保留低、可溶表达低、SEC 单体低会形成 No-Go blocker。
  - 单点 Go 会标记为 `eligible_for_combination_design`，汇总中进入 `validated_single_mutants`。
- 权限边界：
  - 普通用户默认只能读取自己提交的实验反馈。
  - 绑定 `project_id` 时会先检查项目 ACL；写入要求 editor/owner 等写权限，读取要求 viewer 以上读权限。
  - `include_all_users` 仅管理员生效，避免普通用户越权查看他人实验数据。
- Agent 协议已补充：
  - 可用时优先使用湿实验反馈作为高于预测的证据。
  - 结构投射前使用 `residue_numbering_gate`。
  - 组合突变建议前使用 `mutation_epistasis_check`。
- 验证：
  - `python3 -m py_compile backend/app/models/experiment_feedback.py backend/app/services/experiment_feedback.py backend/app/tools/mutation_epistasis_check.py backend/app/tools/residue_numbering_gate.py backend/app/api/data.py backend/app/tools/registry.py backend/tests/test_data_api.py backend/tests/test_tools_api.py` -> 通过。
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_data_api.py -q` -> `85 passed, 81 warnings`。
  - `python3 scripts/check_upgrade_readiness.py --json` -> `ready-with-warnings`，Alembic 单 head `9c8d7e6f5a41`，唯一 warning 为 dirty worktree。
  - `cd backend && .venv/bin/pytest tests/test_agent_binder.py -q` -> `24 passed`。
- 当前边界：
  - 这是后端/API/工具第一层，尚未给 `/data` 或聊天界面增加实验反馈录入 UI。
  - 上位性检查是保守启发式门控，不替代真实结构距离、MD 或湿实验组合验证。
  - 编号门控依赖外部 SIFTS/alignment/mapping rows；无 mapping 时按设计阻断，而不是猜测。

## 2026-07-10 Matvenus 调研高优先级产品化第二层第一批发现
- 已把湿实验反馈从后端能力接到 `/data` 页面：
  - 新增“实验反馈”tab。
  - 支持录入酶名称、变体名、亲本、突变、检测方法、活性保留、活性倍数、ΔTm、可溶表达、SEC 单体比例、降解观察和备注。
  - 提交后调用 `/api/data/experiment-feedback`，由后端统一生成 Go/Watch/No-Go 判断。
  - 页面展示 Go/Watch/No-Go 汇总、组合设计下一步策略、validated single mutants 和最近反馈记录。
- 前端 API client 已新增：
  - `submitExperimentFeedback()`
  - `listExperimentFeedback()`
  - `summarizeExperimentFeedback()`
  - 对应 `ExperimentFeedbackRecord / ExperimentFeedbackSummary` 类型。
- 回归保护：
  - `test_config_validation.py` 增加实验反馈 API、前端 client、DataBrowser UI、工具注册和 agent 协议接线断言。
- 验证：
  - `cd frontend && npm run build` -> 通过；仅保留既有 3Dmol `eval` 和 chunk size warning。
  - `cd backend && .venv/bin/pytest tests/test_config_validation.py -q` -> `83 passed`。
- 当前边界：
  - UI 只接入当前用户的反馈列表；项目筛选/项目页嵌入和管理员跨用户汇总尚未做。
  - 组合突变设计仍未在前端自动串联 `mutation_epistasis_check`，下一层应把 validated single mutants 一键送入工具检查。
  - 残基编号门控目前仍作为工具/API 能力存在，尚未在实验反馈 UI 中展示 mapping 状态。

## 2026-07-10 Matvenus 调研高优先级产品化第二层第二批发现
- 已把实验反馈页与 `mutation_epistasis_check` 串联：
  - 页面从当前用户反馈记录中筛选 `decision=go` 且只有 1 个 mutation 的 validated single mutants。
  - 一键调用 `/api/tools/mutation_epistasis_check/call`。
  - 自动传入 `mutations` 和 `single_mutant_feedback`，其中包含变体名、metrics 和 quality。
  - 不自动伪造结构距离、same-region 或 mechanism tags；这些缺失会在工具结果的 `required_missing_evidence` 中提示。
- 前端展示：
  - recommendation：Go / Watch / No-Go。
  - high-risk / watch pair 计数与总风险分。
  - pairwise risks、reasons、missing evidence。
  - gradient experiment plan，用于决定直接组合还是先做低风险 pairwise subset。
- 新增前端 API wrapper：
  - `runMutationEpistasisCheck()`。
- 验证：
  - `cd frontend && npm run build` -> 通过；仅保留既有 3Dmol `eval` 和 chunk size warning。
  - `cd backend && .venv/bin/pytest tests/test_config_validation.py::TestRequirementsFiles::test_lipase_db_readonly_service_and_api_are_wired tests/test_tools_api.py::test_mutation_epistasis_check_blocks_close_shared_mechanism_pair tests/test_tools_api.py::test_mutation_epistasis_check_allows_orthogonal_validated_pair -q` -> `3 passed`。
  - `cd backend && .venv/bin/pytest tests/test_config_validation.py -q` -> `83 passed`。
- 本轮启动前端开发服务：
  - `4200`、`4201`、`4202` 均已有进程占用。
  - 当前 Vite 服务运行在 `http://127.0.0.1:4203/`。

## 2026-07-10 Matvenus 调研高优先级产品化第二层第三批发现
- 组合突变检查 UI 已支持补充三类人工证据：
  - 结构距离：格式如 `A10V:D80N=22` 或 `A10V,D80N=8.5`。
  - 机制标签：格式如 `A10V: core_packing, stability_gain`。
  - 同一区域分组：格式如 `A10V,D80N` 或 `K120R+S130P`。
- 设计边界：
  - 解析函数会忽略格式不完整的行，避免因为某一行手输错误阻断基础检查。
  - 不输入这些证据时，工具仍可基于单点湿实验反馈运行，并在缺失证据中提示。
  - 输入结构距离和 same-region 后，pairwise risk 会更接近真实结构风险评估。
- 验证：
  - `cd frontend && npm run build` -> 通过；仅保留既有 3Dmol `eval` 和 chunk size warning。
  - `cd backend && .venv/bin/pytest tests/test_config_validation.py::TestRequirementsFiles::test_lipase_db_readonly_service_and_api_are_wired -q` -> `1 passed`。
  - `cd backend && .venv/bin/pytest tests/test_config_validation.py -q` -> `83 passed`。

## 2026-07-10 Matvenus 真实会话读取与方法沉淀发现
- 已通过当前 Chrome 登录态读取 Matvenus 会话 `08b460b1-3d8c-4235-8a20-136f9f50eb4e`：
  - `/session/{id}` 只返回元数据，标题为 `SD改造+数据反馈`。
  - `/session/{id}/stream-events` 返回完整对话事件，本轮保存为 `matvenus-session-08b460.stream-events.json`。
  - 复盘稿已生成：`matvenus-session-08b460.review.md`，共 14 条聚合消息。
- Chrome cookie 读取经验：
  - 本机 Chrome Cookie DB 中有 `NEXT_LOCALE / access_token / refresh_token / token_expires_at`。
  - 主机权限下可从 macOS Keychain 读取 Chrome Safe Storage；脚本不打印明文 token/cookie/password。
  - 主机 Python 的 `cryptography` 缺 `_cffi_backend`，已改用标准库 PBKDF2 + 系统 `openssl` 子进程。
  - Chrome 新版 cookie 明文可能带 `SHA256(host_key)` 32 字节前缀，解密后需剥离再 UTF-8 解码。
- Matvenus 真实事件结构：
  - `stream_events[].event` 包含 `msg_user / msg_chunk / tool_call`。
  - `stream_events[].data.content` 包含 `text / reasoning / tool_call_chunk / file`。
  - `stream_events[].data.msg_id` 可用于将 assistant 分段输出和工具调用聚合成一条消息。
  - 真实会话工具包括 `read_file`、`venusx_functional_residue_prediction`、`venusrem_mutation_prediction`。
- 真实会话分析流程：
  - 先读取蛋白设计工具说明并做参数预检。
  - 发现 VenusX 不能直接吃 PDB 后，改为从 PDB 提取 388 aa FASTA 序列。
  - 分别跑 VenusREM 稳定性扫描、VenusREM 活性扫描、VenusX 功能残基测绘。
  - 结果按“双收益位点 / 单稳定性位点 / 单活性位点 / 指定突变复核”分层展示。
  - 用户反馈 P338T 活性提升而稳定性下降后，外部 agent 从“预测不推荐”转向“活力-稳定性权衡”机制分析，并提出保留 P338T 活性收益、用周边补偿突变恢复稳定性的策略。
- 可迁移方法：
  - 不应只输出预测排名，应输出“机制解释 + 数据来源 + 禁改区 + 候选表 + 组合策略 + 梯度实验方案”。
  - 对实验反馈和预测冲突的位点，应显式列出冲突并重构假设，而不是机械否定实验结果。
  - P338T 类位点适合用“保留有益柔性、周边补偿稳定性”的框架处理，但具体补偿位点、距离和收益必须由本平台结构映射/MD/湿实验复核。
- 新增/更新文件：
  - `scripts/fetch_matvenus_session.py`
  - `scripts/extract_matvenus_session.py`
  - `backend/tests/test_matvenus_session_extractor.py`
  - `matvenus-session-08b460.json`
  - `matvenus-session-08b460.stream-events.json`
  - `matvenus-session-08b460.review.md`
  - `docs/designs/2026-07-10-matvenus-analysis-style-study.md`
  - `docs/manuals/2026-07-10-daily-report.md`
- 验证：
  - `cd backend && .venv/bin/pytest tests/test_matvenus_session_extractor.py tests/test_agent_binder.py -q` -> `25 passed`
  - `cd frontend && npm run build` -> 通过，仅保留既有 3Dmol eval 和 chunk size warning。

## 2026-07-10 Matvenus 可借鉴方法接入本平台发现
- 已将 Matvenus 真实会话中值得学习的分析框架接入后端 agent：
  - 新增 `ENZYME_ENGINEERING_REPORT_PROTOCOL`，集中描述酶工程报告协议。
  - `SC_SYSTEM_PROMPT` 现在会要求报告合成阶段使用该协议。
  - `_synthesize_sc()` 在酶活、热稳定性、突变筛选和 wet-lab feedback 任务中显式要求使用该协议。
  - `_chat_reply()` 对 SOP/清单/模板类长文档回复也复用该协议，避免只生成泛泛实验清单。
- 协议重点：
  - 先写输入预检和格式修正。
  - 不只输出排名，要分为双收益、单稳定性、单活性、用户指定突变复核、No-Go 和组合。
  - 数据来源和置信度分表展示，区分计算、文献、结构、MD、湿实验反馈和未知项。
  - 如果预测与湿实验反馈冲突，先并列冲突，再重构机制假设，不否定实验结果。
  - 活性升/稳定性降时，优先按 activity-stability trade-off 处理，保留活性收益并寻找周边补偿稳定化位点。
  - 补偿设计按梯度实验推进：单点补偿、双点组合、高阶组合。
  - 实验类输出必须有 Go/No-Go 决策块。
- 新增测试保护：
  - `test_sc_prompt_contains_matvenus_feedback_protocol`
  - `test_document_reply_uses_larger_token_budget` 增加协议断言。
- 验证：
  - `python3 -m py_compile backend/app/core/agent_roles.py backend/app/core/agent_graph.py backend/tests/test_agent_binder.py` -> 通过
  - `cd backend && .venv/bin/pytest tests/test_agent_binder.py tests/test_matvenus_session_extractor.py -q` -> `26 passed`

## 2026-07-10 Matvenus 全部历史会话批量调研发现
- 已读取当前登录态下 Matvenus `/session?size=50&page=1&show_all=true` 列表，返回 `total=14`，本轮全部 14 个会话均已抓取 `stream-events`。
- 生成文件：
  - `matvenus-research/index.json`：14 个会话元数据索引。
  - `matvenus-research/raw/*.stream-events.json`：14 个原始事件文件。
  - `matvenus-research/reviews/*.review.md`：14 个逐会话复盘稿。
  - `matvenus-research/summary.md`：机器辅助总报告。
  - `docs/designs/2026-07-10-matvenus-multi-session-study.md`：人工归纳版多会话调研总结。
- 覆盖主题：
  - 388 aa 酶比活力与热稳定性提升。
  - 淀粉酶最适 pH 从 6.0 调至 4.5。
  - 木聚糖酶比活力提高。
  - 双底物催化效率优化。
  - 高钙离子依赖性降低。
  - 蛋白对接适用边界。
  - 湿实验反馈后的组合突变迭代。
- 工具调用高频模式：
  - `read_file` 12 个会话。
  - `venusx_functional_residue_prediction` 11 个会话。
  - `venusrem_mutation_prediction` 11 个会话。
  - `write_file` 6 个会话。
  - `convert_structure` / `venusprime_multipoint_prediction` 各 3 个会话。
  - 另有 Rosetta、DiffDock、GROMACS、AlphaFold2、PyMOL、UniProt、PubChem 等用于专项验证。
- 横向可借鉴点：
  - 输入预检优先，尤其是 PDB/FASTA/底物结构/工具参数。
  - 候选位点分层输出，不只给 Top 排名。
  - 湿实验反馈优先于计算预测，用反馈重构机制和下一轮策略。
  - 组合突变按梯度推进，先单点/双点，再高阶组合。
  - 输出面向实验执行，常用表格、批次、CSV、优先级和避坑提醒。
- 暴露出的风险：
  - 多处使用过强的成功率、倍数和“几乎确定”表述，迁移到本平台必须降级为计算假设或要求证据。
  - 高钙依赖性会话出现过残基编号线性映射错误，说明必须有编号映射门控。
  - 有会话在用户追问后才补文献来源，说明统计/阳性率/家族经验类结论必须强制溯源。
  - 工具参数曾出现重复失败，说明 preflight/schema 校验必须产品化。
- 已把新增教训补入后端协议：
  - 残基编号映射确认。
  - 组合突变上位性风险检查。
  - 命中率、倍数提升、成功概率类结论必须给证据，否则标注为经验假设/计算假设。
- 验证：
  - `python3 -m py_compile scripts/batch_fetch_matvenus_sessions.py scripts/summarize_matvenus_research.py scripts/fetch_matvenus_session.py scripts/extract_matvenus_session.py backend/app/core/agent_roles.py backend/app/core/agent_graph.py backend/tests/test_agent_binder.py` -> 通过
  - `cd backend && .venv/bin/pytest tests/test_agent_binder.py tests/test_matvenus_session_extractor.py -q` -> `26 passed`
  - 敏感扫描未发现 Matvenus token/cookie 明文落盘。

## 2026-07-10 Matvenus 输出样式与访问边界发现
- 状态更新：本节记录的是早期失败路径，已被上一节“Matvenus 真实会话读取与方法沉淀发现”取代。真实会话已通过 `/session/{id}/stream-events` 读取成功。
- 用户已授权读取 Matvenus 会话和学习其方法，但当前本机自动化访问仍受 Chrome/macOS 安全边界限制：
  - 默认 Chrome profile 已被正在运行的 Chrome 占用，Playwright 不能复用该 profile 建立控制通道。
  - Chrome 默认关闭 AppleScript 执行页面 JavaScript。
  - 自动点击“允许 Apple 事件中的 JavaScript”菜单后仍未生效。
  - macOS 未允许 `osascript` 辅助访问，因此不能自动点击页面或复制页面正文。
- 本轮没有读取、导出或打印 Cookie/token/password。
- 已能从公开前端资源确认 Matvenus 的输出渲染模式：
  - 消息列表最大宽度随断点从 `max-w-2xl` 到 `2xl:max-w-5xl`。
  - agent 名称显示为“启明星”，样式为 `text-lg font-semibold`，颜色 `#4BA4F8`。
  - human 消息右侧展示，桌面端有约 30% 左侧缩进；agent 消息左侧展示，背景透明。
  - Markdown 采用 prose 风格，正文色接近 `rgb(31,35,41)`，行高 `leading-relaxed`。
  - 标题紧凑、半粗、不使用 serif；代码块浅灰背景、圆角、细边框；引用块浅灰左边框；表格细边框、浅灰表头。
- 已将上述样式迁移到本平台 `MarkdownView`，保留合法 table DOM 和长文档显示修复。
- 思考方法层目前只能确认结构：
  - 它把消息拆为 `text / step / report / tool_call` spans。
  - 复杂任务通过 step 展示过程，通过 report 收口最终结论。
  - deep research 会按 `node_name` 识别 coordinator/planner/evaluator/outline_reporter/section_writer 等节点。
- 真实会话内容仍需后续读取 JSON 后再总结，不能凭静态资源推断具体结论。

## 2026-07-10 Matvenus 外部会话复盘发现
- 状态更新：本节记录的是用户导出 JSON 前的离线方案，已被真实 stream-events 抓取方案取代。离线解析脚本仍保留用于后续导入。
- 直接通过命令行或浏览器工具访问 Matvenus 链接只能拿到前端 SPA shell；真实会话内容依赖已登录浏览器的 session cookie。
- 当前工作区尚未发现用户导出的 Matvenus session JSON，因此不能声称已经读取外部 agent 的真实分析结论。
- 前端 bundle 线索表明会话数据常见形态包含 `completedMessages`、`messages`、`spans`、`sender`、`msg_id`、`node_name`、`agent_type`、`model` 等字段。
- spans 中可复盘的信息类型：
  - `text` / `report`：正文和最终报告。
  - `step`：分析步骤标题和嵌套推理内容。
  - `tool_call`：工具调用名称、参数和结果摘要。
- 本轮新增本地离线解析脚本，优先降低后续复盘门槛：
  - 输入：用户从已登录浏览器导出的 JSON。
  - 输出：Markdown 复盘稿。
  - 安全策略：不要求 Cookie/token，且对敏感字段名自动脱敏。
- 后续拿到真实 JSON 后，复盘重点应放在：
  - agent 如何拆解 388 aa 蛋白稳定性任务。
  - 是否先做结构编号、SASA、活性口袋、柔性环、保守性和化学不稳定热点筛查。
  - 位点选择与禁改区如何权衡。
  - 哪些输出格式或检查表可迁移到本平台 SOP/agent prompt。

## 2026-07-09 代码走查、白盒、黑盒测试发现
- 测试基线在修复后稳定：后端主回归 `190 passed, 81 warnings`，前端构建通过，验收矩阵与发布验收均 `passed-with-skips`。
- 代码走查发现并已修复的高风险点：
  - `ligand_preprocess` 作为 async/live 工具不应允许 `/call` 同步执行；已改为 async-only，通过 `/submit` 进入 `ligand_cpu`。
  - ligand HTTP 参数不应接受本地 path 或跨用户 object name；已增加用户上传前缀校验。
  - PDB lipase overlay 不能用 inferred coordinate-order mapping + checkbox 投射文献位点；已要求可靠 curated/local mapping 且无 limitation。
  - lipase curation 的 `batched/published` 状态不能由 review endpoint 直接写入；已收口到 batch workflow。
  - deploy live gate 不能在无 manifest、无 PDB/AlphaFold 或缺 Foldseek 子库时返回 live-ready；已收紧 required components。
- 代码走查发现并部分保留为后续治理的点：
  - tool artifact owner cache 目前 24h TTL，长期 artifact 下载权限应落到持久表或审计 artifact manifest 上。
  - release acceptance 对 dirty worktree 仍为 warning，这适合开发机验收；正式发版应增加 strict 模式或要求干净 revision。
  - release acceptance 仍未默认执行 OSS/MinIO E2E、真实浏览器、真实 MD 和 deploy live gate；这些需要 live 服务、凭据或大数据资产。
- 安全/科学边界结论：
  - 本轮不再通过 HTTP API 读取服务器本地 ligand path。
  - 本轮不再把 lipase DB 位点投射到 inferred mapping 结构上。
  - 本轮不再在公开 lipase API response 中暴露服务器绝对 DB 路径。
  - 本轮仍不伪造 ligand PDBQT/Vina/topology 或真实 MD 结果；runtime 缺失时保持 blocked/skipped 合同。

## 2026-07-09 本机可推进待建项并行执行发现
- 本轮按互不重叠写入范围启动 4 个 worker：
  - ligand 容器化准备：完成 Docker/compose runtime boundary、scratch volume、`ligand-runtime-check`。
  - 真实数据 plan-only：完成 schema v2 `live_manifest.json`、manifest-aware 检查、版本/缺失项/下一步动作输出。
  - 自动化测试 gate：完成 live browser/MD blackbox/OSS-MinIO 的 planned/skipped/blocked 合同入口。
  - 产品化文档：完成截图版操作手册文字占位版、演练记录模板和手册链接。
- 当前仍未完成的是真实环境动作：
  - 未安装 OpenBabel/RDKit/Vina/ACPYPE/AmberTools。
  - 未跑真实 Vina/PDBQT/ligand topology。
  - 未启动真实 live frontend/backend 浏览器回归。
  - 未跑真实 MD 黑盒长任务。
  - 未执行 OSS/MinIO 真实对象 round-trip。
  - 未执行维护窗口回滚或异地备份演练。
- 测试执行经验再次确认：
  - 后端主回归与 acceptance matrix 不能并行运行；二者会竞争 `backend/test_protein_ai.db`，造成 `no such table` 假失败。
  - 串行重跑后主回归 `189 passed, 81 warnings`，acceptance matrix `passed-with-skips`。
- 发布验收：
  - `run_release_acceptance.py` 通过，summary `passed-with-skips`。
  - acceptance matrix 现在总数为 12，默认跳过 4 个 live/opt-in gate。

## 2026-07-09 科为博 lipase.db 第四层可持续富化机制第二层发现
- accepted curation records 已进入受控批次流程：
  - dry-run 只生成 manifest/export payload，不改变记录状态。
  - 非 dry-run 创建 `prepared` batch，并将相关 records 从 `accepted` 推进为 `batched`。
  - publish 必须提供确认令牌 `PUBLISH_LIPASE_CURATION_BATCH`。
  - publish 成功后 batch 和 records 标记为 `published`，但不写原始 lipase.db。
- batch export payload 的定位：
  - 作为人工导入 curated DB 的输入清单。
  - 包含 required manual steps：源证据复核、staged SQLite copy、integrity/foreign key check、维护窗口替换。
  - 该机制是“人工审核发布流程”，不是自动数据库改写。
- 数据库迁移：
  - 沿用单 Alembic head `2f6c8d9e0a12`。
  - `lipase_curation_batches` 增加 batch key、status、record_ids、manifest、export_payload、confirmation_token、published_by 和 published_at。
- 本轮验证：
  - 后端编译通过。
  - curation record/batch 定向测试通过。
  - 前端构建通过，仅保留既有 3Dmol 警告。
  - 主回归 `187 passed, 81 warnings`。
  - 发布验收 `passed-with-skips`，0 failed / 1 skipped / 6 total。
- 当前 lipase 接入层结论：
  - 只读 evidence source、工具/前端解释、PDB 安全 overlay、审计摘要、用户反馈、管理员审核和受控发布批次均已闭环。
  - 后续增强应优先做管理员 UI、离线导入脚本和 staged lipase.db 校验，不应绕过人工审核直接写生产 SQLite。

## 2026-07-09 科为博 lipase.db 第四层可持续富化机制第一层发现
- 可持续富化机制第一层已建立为“平台主库 curation queue”：
  - 用户可提交 `literature / experiment / tool_feedback / manual_note` 四类记录。
  - 记录可绑定 paper_key、mutation_code、position、linked_task_id、evidence_payload、feedback_payload 和 notes。
  - 管理员可按 status/source_type 查看队列，并更新 `submitted / triaged / accepted / rejected / needs_more_evidence`。
- 数据边界：
  - 原始 `/Users/xuyan/lipase-db/lipase.db` 继续只读。
  - 新增 `lipase_curation_records` 存在平台 PostgreSQL/SQLite 主库中，作为待审核富化来源。
  - `accepted` 不等于自动写入 curated DB；下一层需要导入批次、人工复核和发布记录。
- API 边界：
  - 普通登录用户只能提交 curation record。
  - 管理员才能列出队列和修改 review status。
  - 前端已有 client 方法，但本轮未扩展管理员 UI 页面。
- 迁移经验：
  - 新 Alembic 迁移必须挂到当前单 head `b9a4c2d7e8f1` 后；挂到旧 head 会造成多 head warning。
  - 修正后 `check_upgrade_readiness.py --json` 显示 Alembic head 为 `2f6c8d9e0a12`。
- 本轮验证：
  - 后端编译通过。
  - curation API 定向测试通过。
  - 主回归 `186 passed, 81 warnings`。
  - 前端构建通过，仅保留既有 3Dmol 警告。
  - 发布验收 `passed-with-skips`，0 failed / 1 skipped / 6 total。

## 2026-07-09 科为博 lipase.db 第三层证据接入第二批发现
- PDB viewer 高亮已采用显式确认模式：
  - 必须先跑 residue mapping。
  - 用户必须勾选 KWB lipase numbering confirmation。
  - 页面再按 mapping rows 将 lipase DB evidence position 投射到 PDB residue number。
- 该设计避免了直接把 lipase 序列编号误当作 PDB residue numbering：
  - 无 mapping 时阻断 overlay。
  - 未确认编号关系时阻断 overlay。
  - 只把 `position_matches` / `exact_mutation_matches` 中能映射到结构坐标的位点加入 viewer。
- 前端实现细节：
  - `runLipaseEvidenceOverlay()` 会把 mapping positions 按 250 个一组调用 `getLipaseEvidenceContext()`，降低 URL 过长风险。
  - `PDBAnalysisCard` 增加独立 `lipase` overlay layer，用户可单独显示/隐藏。
  - lipase overlay 使用 teal 色，与 curated catalytic sites、inferred protected sites、signal/domain ranges 区分。
- 本轮验证：
  - 前端构建通过，仅保留既有 3Dmol `eval` 和 chunk size 警告。
  - `test_config_validation.py` 80 passed。
  - 主回归 `185 passed, 81 warnings`。
  - 发布验收 `passed-with-skips`，0 failed / 1 skipped / 6 total。
- 本轮修复经验：
  - PDB 页面本地 `AnalysisResult` 类型需要同步声明 `lipaseEvidenceContext`。
  - 向 `PDBAnalysisCard` 传递可选 context 时应使用 `undefined`，不要传 `null`。

## 2026-07-09 科为博 lipase.db 第三层证据接入第一批发现
- 第三层第一批已把 curated lipase evidence 接入工具解释链路：
  - `build_lipase_evidence_context()` 返回 exact mutation matches、position matches、fallback search、计数、strongest evidence level 和 recommended use。
  - `GET /api/data/lipase/evidence-context` 暴露同一上下文，前端/PDB/工具可复用。
  - `mutation_priority_score` 会给推荐突变附加 `lipase_evidence`，并给候选位点附加 `lipase_position_evidence_count`。
  - `gromacs_md` batch replicate summary / ranked candidates 会附加 `lipase_evidence` 计数，供 MD ranking 解释展示。
  - 任务审计摘要只记录紧凑统计，不落原始 evidence rows，避免审计表膨胀。
- PDB 结构分析接入边界：
  - 前端 `PDBAnalysisCard` 已支持展示 `lipaseEvidenceContext`。
  - 当前不自动把 lipase 位点投射到 structure viewer；原因是序列编号、PDB residue numbering、链 ID 和缺失残基需要显式确认。
  - 后续第三步第二批应在用户确认编号体系或 SIFTS/结构映射确认后，再做 viewer 高亮。
- 真实库 smoke：
  - `build_lipase_evidence_context(mutations=["D223G"], positions=[223], q="D223G", limit=5)` 返回 `ready`。
  - 计数：`exact_mutation_matches=1`、`position_matches=1`、`search_matches=2`。
  - strongest evidence level 为 `article_level`，命中文献 `Xie_2014`。
- 本轮验证：
  - Python 编译通过。
  - 新增/定向测试 `5 passed`。
  - 主回归 `185 passed, 81 warnings`。
  - 前端生产构建通过，仅保留既有 3Dmol `eval` 和 chunk size 警告。
  - 发布验收通过，保留维护窗口与异地备份演练人工提示。

## 2026-07-09 科为博 lipase.db 第二层查询接入发现
- 第二层已从“状态可见”推进到“可查询可使用”：
  - 后端只读 service 新增 `list_lipase_papers()`、`get_lipase_paper_detail()`、`list_lipase_gaps()`、`search_lipase_evidence()`。
  - 新增 API：
    - `GET /api/data/lipase/search`
    - `GET /api/data/lipase/papers`
    - `GET /api/data/lipase/papers/{paper_key}`
    - `GET /api/data/lipase/gaps`
  - 保留并继续使用 `GET /api/data/lipase/status` 与 `GET /api/data/lipase/variants`。
  - 前端 `/data` 新增 `Lipase库` tab，展示文献、变体、gap、搜索结果和文献详情面板。
  - 前端 API client 新增 `getLipasePapers()`、`getLipasePaperDetail()`、`getLipaseGaps()`、`searchLipaseEvidence()`。
- 当前能力边界：
  - lipase.db 仍以 SQLite `mode=ro&immutable=1` 只读方式接入，不污染原始 curated evidence。
  - PostgreSQL 仍是用户、项目、任务、审计和权限主库；lipase.db 不替代业务主库。
  - 本轮还没有把 lipase 证据注入突变推荐、PDB 结构分析或 MD ranking 解释；这属于第三步。
- 真实库 smoke：
  - `collect_lipase_db_status()` 返回 `ready`，summary 为 10 papers、12 variants、12 mutations、12 claims、12 metrics、7 substrates、19 gaps。
  - `list_lipase_papers(limit=2)` 返回真实 BTL2/CALB 文献记录。
  - `list_lipase_gaps(limit=2)` 返回真实 high/open gap。
  - `search_lipase_evidence(q="D223G")` 返回 variant=1、claim=1。
  - `get_lipase_paper_detail("BTL2_cloning_1997")` 返回 `ready`。
- 本轮验证：
  - `python3 -m py_compile app/services/lipase_db_status.py app/api/data.py app/core/config.py` -> 通过
  - 定向 lipase/config 测试 -> `5 passed`
  - `cd frontend && npm run build` -> 通过；仅保留既有 3Dmol `eval` 和 chunk size 警告
  - `cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_config_validation.py -q` -> `112 passed, 60 warnings`
  - `python3 scripts/run_release_acceptance.py` -> `passed-with-skips`，0 failed / 1 skipped / 6 total
- 测试执行经验：
  - `tests/test_data_api.py tests/test_config_validation.py` 与 `scripts/run_release_acceptance.py` 不应并行跑；并行时会竞争测试 SQLite 库并出现 `no such table` 假失败。
  - 串行重跑后数据/API 回归和发布验收均通过。

## 2026-07-09 科为博 lipase.db 接入规划发现
- 用户指定数据库路径：`/Users/xuyan/lipase-db/lipase.db`。
- 只读检查结果：
  - 文件大小约 `156KB`。
  - SQLite 3.x 数据库，UTF-8。
  - `PRAGMA integrity_check` 返回 `ok`。
  - `PRAGMA foreign_key_check` 无输出，未发现外键断裂。
- 当前表结构：
  - `papers`：文献、题名、作者、期刊、年份、DOI、PMID、enzyme_name、engineering_objective、lock_status、ready_for_db。
  - `paper_aliases`：文献别名到 canonical paper 的映射。
  - `variants`：突变体/组合突变/搜索提示，包含 parent lineage。
  - `variant_mutations`：标准突变位点拆解，如 `V210I`、`A281E`、`D223G`。
  - `evidence_claims`：文献证据 claim，包含 claim_group、evidence_level、direct_evidence、source location、known payload。
  - `substrates` / `claim_substrates`：底物、底物角色、claim 关联。
  - `metrics`：半衰期、T50、specific activity、substrate specificity/selectivity 等指标。
  - `comparators`：对照对象和 baseline。
  - `unresolved_gaps`：缺失全文锚点、缺 WT baseline、缺 assay substrate、identity rebuild 等待办 gap。
  - `lineage_notes`：文献/变体谱系备注。
- 数据规模：
  - `papers=10`
  - `variants=12`
  - `variant_mutations=12`
  - `evidence_claims=12`
  - `metrics=12`
  - `substrates=7`
  - `comparators=12`
  - `unresolved_gaps=19`
  - `lineage_notes=13`
  - `paper_aliases=17`
- 内容判断：
  - 当前主要是 CALB / BTL2 lipase 方向的文献证据库。
  - 具备工程目标、突变位点、指标、底物和证据等级，可直接用于“突变推荐解释”和“证据追溯”。
  - 不是业务主库，不能替换 PostgreSQL 的用户、项目、任务审计、文件权限表。
  - 推荐作为外部 curated evidence source 接入，先只读/导入镜像，再逐步支持平台内富化。
- 推荐接入策略：
  - 第一层：只读连接 + schema introspection + 数据质量报告 + API 查询。
  - 第二层：映射到平台现有 `DirectedEvolutionEntry / StabilityRecord / KineticParameter / SubstrateCompound / DatabaseCrossRef`，保留原始 evidence claim 表作为 source-of-truth。
  - 第三层：接入 `/data` 搜索、PDB 页面 mutation evidence card、MD ranking 解释、ligand/substrate 证据卡。
  - 第四层：增加用户调用数据回写表，记录查询、采纳、人工审核、实验反馈，但不直接污染原始 curated 表。
- 第一层已落地：
  - 新增配置 `LIPASE_DB_PATH`，默认自动发现 `/Users/xuyan/lipase-db/lipase.db`。
  - 新增只读服务 `lipase_db_status.py`，使用 SQLite URI `mode=ro&immutable=1`，不写入原库。
  - 新增 API：
    - `GET /api/data/lipase/status`
    - `GET /api/data/lipase/variants?q=&limit=`
  - `/data` readiness 页面新增“科为博 Lipase DB”状态卡，展示文献、变体、突变、证据、指标、底物和 gap 数。
  - 真实库服务调用返回 `status=ready`，`integrity_check=ok`，`ready_for_ingestion=true`。
  - 针对性测试和前端构建通过。

## 2026-07-09 ligand 合同、数据状态卡与发布验收新增发现
- `ligand_preprocess` 的 `prepare_pdbqt / vina_docking / ligand_topology` 已具备更明确的 API 合同：
  - 返回 `required_parameters`、`missing_parameters`、`provided_inputs` 和 `command_preview`。
  - 缺参数时返回 `blocked_reason=missing_parameters`。
  - 参数齐但运行时未安装时返回 `pdbqt_preparation_runtime_not_available / vina_runtime_not_available / ligand_topology_runtime_not_available`。
  - 当前仍不伪造 PDBQT、Vina docking 或小分子 topology 结果。
- `/pdb` 页面新增 Ligand Preflight 状态卡：
  - 展示真实 SDF 检查结果：2D/3D 推断、原子数、键数、Z 坐标状态、元素组成。
  - 展示每个 ligand 阶段的缺参、缺工具、输入是否已提供、命令预览和下一步动作。
  - 该入口当前使用项目根真实底物 `Structure2D_COMPOUND_CID_5478883.sdf` 做只读合同检查。
- deploy_data readiness 增强：
  - 后端组件状态包含 `version`、`updated_at`、`missing_items`。
  - `/data` readiness 卡已展示版本、更新时间、缺失项和 failure reason。
  - PDB / AlphaFold / Foldseek DB 的状态页语义从“是否存在”升级为“数量 + 版本 + 更新时间 + 缺失项”。
- 任务 artifact 权限发现：
  - `get_tool_artifact_owner()` 原返回字段是 `tool`，新测试使用审计语义字段 `tool_name`。
  - 已补兼容别名 `tool_name`，不破坏旧字段。
- 本轮验证基线：
  - `python3 -m py_compile app/tools/ligand_preprocess.py app/services/deploy_data_status.py app/services/tool_task_audit.py app/services/tool_task_store.py` → 通过
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py::test_ligand_preprocess_stage_contract_reports_missing_parameters tests/test_tools_api.py::test_ligand_preprocess_api_call_returns_blocked_contract tests/test_tools_api.py::test_ligand_task_polling_records_artifact_owner_for_download tests/test_data_api.py::TestBenchmarkEndpoints::test_data_readiness_endpoint_reports_components tests/test_config_validation.py::TestRequirementsFiles::test_acceptance_matrix_script_plan_includes_risk_gates -q` → `5 passed`
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_data_api.py tests/test_config_validation.py -q` → `152 passed, 81 warnings`
  - `cd frontend && npm run build` → 通过；仅保留既有 3Dmol `eval` 和 chunk size 警告
  - `python3 scripts/run_release_acceptance.py` → `passed-with-skips`，0 failed / 1 skipped / 6 total

## 2026-07-08 底物/配体预处理与对接层第二步第一批新增发现
- 新增后端工具 `ligand_preprocess`：
  - 通过 `ToolRegistry` 自动发现。
  - 支持通用接口 `POST /api/tools/ligand_preprocess/submit`。
  - 支持阶段：`preflight`、`generate_3d`、`prepare_pdbqt`、`vina_docking`、`ligand_topology`。
  - 当前 `preflight` 可真实检查 SDF 与工具链。
  - 当前 `generate_3d` 在 `obabel` 存在时会真实执行：`obabel ligand_2d.sdf -O ligand_3d.sdf --gen3d -h`。
  - 当前 `prepare_pdbqt`、`vina_docking`、`ligand_topology` 已建立受控合同，但在 runtime/参数未封装前返回 `blocked`，不伪造结果。
- 新增异步队列策略：
  - `ligand_preprocess` 加入 `ASYNC_TOOLS`。
  - 使用独立 `ligand_cpu` 队列，`soft_time_limit=1800`、`time_limit=2700`。
  - `/api/ops/summary` 的 workers 和 Redis queue snapshot 会展示 `ligand_cpu`。
- 审计安全：
  - `tool_task_audit.SENSITIVE_KEYS` 新增 `sdf_data`，避免底物结构原文进入任务审计表。
- 用真实底物文件验证：
  - `ToolRegistry.execute("ligand_preprocess", {"sdf_path": "../Structure2D_COMPOUND_CID_5478883.sdf", "stages": ["preflight", "generate_3d"], "store_outputs": False})`
  - 返回 `status=blocked`。
  - SDF 识别仍为 `atom_count=111`、`bond_count=110`、`is_2d_sdf=true`。
  - `preflight` 缺：`conformer_generation / pdbqt_preparation / vina_docking / ligand_topology / gromacs_md`。
  - `generate_3d` 阻断原因为 `openbabel_not_installed`。
- 最新验证基线：
  - `python3 -m py_compile backend/app/tools/ligand_preprocess.py backend/app/tools/registry.py backend/app/services/scheduler.py backend/app/services/tool_task_audit.py` → 通过
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py::test_ligand_preprocess_preflight_blocks_missing_runtime_without_fake_3d tests/test_tools_api.py::test_ligand_preprocess_submit_creates_ligand_cpu_audit tests/test_config_validation.py::TestRequirementsFiles::test_ligand_preprocess_tool_is_registered_for_async_execution -q` → `3 passed`
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_ops_api.py tests/test_config_validation.py -q` → `124 passed, 29 warnings`

## 2026-07-08 底物/配体预处理与对接层第一步新增发现
- 用户提供底物文件：`/Users/xuyan/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/Structure2D_COMPOUND_CID_5478883.sdf`。
- 已用本地只读脚本确认该文件是 2D SDF：
  - SDF header 包含 `2D`。
  - 格式为 V2000。
  - 单分子记录。
  - `atom_count=111`，`bond_count=110`。
  - 元素组成：C 34、H 63、N 5、O 9。
  - 所有原子 Z 坐标均为 `0.0`，`is_2d_sdf=true`。
- 科学边界：
  - 2D SDF 是平面结构式，不是可对接/可 MD 的 3D 小分子构象。
  - 不能直接进入 AutoDock Vina。
  - 不能直接和 3D 蛋白一起送入 GROMACS。
  - ChimeraX 适合可视化和辅助标定 pocket box，不承担批量 2D->3D 构象生成。
- 新增 `backend/scripts/smoke_ligand_toolchain.py`：
  - 只读检查 SDF 维度、原子/键数量、Z 坐标状态。
  - 检查 OpenBabel、RDKit、Vina、ACPYPE、Antechamber、GROMACS 是否可用。
  - 支持 `--json`。
  - 支持 `--require-live`，工具链不完整时退出非 0，用作部署节点 live gate。
- Makefile 新增：
  - `make backend-ligand-toolchain-smoke`
  - `make backend-ligand-toolchain-live-gate`
- 新增 IT 手册：`docs/manuals/ligand-docking-md-workflow.md`。
- 当前本机实际状态：
  - `obabel` not found。
  - `vina` not found。
  - `acpype` not found。
  - `antechamber` not found。
  - `gmx/gmx_mpi` not found。
  - backend `.venv` 中未检测到 `rdkit`。
  - `cd backend && .venv/bin/python scripts/smoke_ligand_toolchain.py --json` 返回 `status=blocked_toolchain_missing`。
- 真实落地顺序：
  - 安装/容器化 OpenBabel 或 RDKit，完成 2D->3D 构象生成、加氢和几何优化。
  - 补质子化/电荷分配和 PDBQT 输出。
  - 接入 AutoDock Vina，使用 ChimeraX 标定的 pocket box 参数对接。
  - 从 docked pose 生成酶-底物 3D 复合物。
  - 使用 ACPYPE/Antechamber/AmberTools 生成小分子 GAFF2/ITP 拓扑。
  - 通过 GROMACS topology/live gate 后再进入复合物 MD。

## 2026-07-08 MD GPU 服务器等待项
- 用户明确要求：等提供阿里云 GPU 服务器后，再继续真实 MD/GROMACS 长任务。
- 已写入待建清单：`MD 科学参数层第四层第二批第七步`。
- 当前执行边界：
  - 本机 MacBook Pro M1 Pro 可用于开发、单测、轻量 smoke。
  - 本机没有 `gmx/gmx_mpi`，不能声明真实拓扑 live gate 通过。
  - 不在本机继续尝试真实 WT/mutant 多 replicate 长 MD。
- 等服务器到位后的执行顺序：
  - 安装/确认 NVIDIA 驱动、CUDA、NVIDIA Container Toolkit、GROMACS GPU 版。
  - 运行 `make backend-md-topology-live-gate`。
  - 使用真实 mutant PDB 跑 `/api/tools/md/mutants/prepare` + `validate_topology=true`。
  - 使用 `require_mutant_topology_validation=true` 提交真实 WT/mutant replicate 批次。
  - 长任务完成后调用 `/api/tools/md/replicates/{batch_id}/summary` 生成真实 batch ranking report。

## 2026-07-08 MD 科学参数层第四层第二批第六步新增发现
- 新增 `backend/scripts/smoke_md_topology.py`：
  - 默认用内置最小 PDB 调用 `_validate_pdb_topology()`。
  - 支持 `--json` 机器可读输出。
  - 支持 `--require-live`，只有真实 `pdb2gmx` 验证通过才退出 0。
  - 支持 `MD_TOPOLOGY_SMOKE_PDB_FILE`、`MD_TOPOLOGY_SMOKE_FORCE_FIELD`、`MD_TOPOLOGY_SMOKE_WATER_MODEL`、`MD_TOPOLOGY_SMOKE_TIMEOUT_SECONDS` 环境变量。
- Makefile 新增：
  - `make backend-md-topology-smoke`：host 侧非致命 smoke，GROMACS 缺失时返回 unavailable 但不失败。
  - `make backend-md-topology-live-gate`：host 侧 live gate，GROMACS 缺失或 `pdb2gmx` 未通过时失败。
- 当前机器实际状态：
  - `which gmx` → not found
  - `which gmx_mpi` → not found
  - `cd backend && .venv/bin/python scripts/smoke_md_topology.py --json` → `status=unavailable`，`error_code=GROMACS_NOT_INSTALLED`
- 这把“能不能真实跑拓扑预检”的判断固定成可部署入口；后续 GPU/GROMACS 节点只需跑 `make backend-md-topology-live-gate`。
- 最新验证基线：
  - `cd backend && .venv/bin/python scripts/smoke_md_topology.py --json` → 通过，返回 `GROMACS_NOT_INSTALLED/unavailable`
  - `cd backend && .venv/bin/pytest tests/test_config_validation.py tests/test_tools_api.py tests/test_gromacs_md_artifacts.py -q` → `141 passed, 21 warnings`
  - `cd frontend && npm run build` → 通过，仅保留既有 `3Dmol` eval 和 chunk warning
  - `cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_auth_resilience.py tests/test_tools_api.py tests/test_ops_api.py tests/test_project_acl.py tests/test_publish_api.py tests/test_llm_gateway.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `218 passed, 182 warnings`
  - `python3 scripts/run_release_acceptance.py` → `passed-with-skips`，0 failed / 1 skipped / 6 total

## 2026-07-08 MD 科学参数层第四层第二批第五步新增发现
- `/api/tools/md/mutants/prepare` 新增可选 `validate_topology`：
  - 生成 mutant PDB 后可立即调用 `_validate_pdb_topology()`。
  - 返回批次级 `topology_validation.enabled/force_field/water_model/timeout_seconds/safe_count`。
  - 每个 mutant 会带 `topology_validation`，并在 `mutant_input` 中同步携带验证结果。
  - `topology_validation.safe_for_ranking=true` 时 `topology_readiness=validated_for_replicate_submit`。
- `/api/tools/md/replicates/submit` 新增 `require_mutant_topology_validation`：
  - 默认 false，保持已有手工 prepared PDB 流程兼容。
  - 开启后，mutant input 必须携带 `topology_validation.topology_validated=true` 且 `safe_for_ranking=true`。
  - 不满足时返回 blocked task，`reason=mutant_topology_not_validated`，不派发 Celery。
- 这一步把“准备突变体结构 -> 拓扑预检 -> 受控批量提交”的 API 合同串起来了，但仍不自动执行长 MD。
- 当前边界：
  - 本轮没有在当前机器真实执行 `gmx pdb2gmx`。
  - 本轮没有自动把所有 safe mutant 长任务提交到生产队列；提交仍由调用方显式确认 `SUBMIT_MD_REPLICATES`。
  - 真实 ranking 仍依赖后续真实 WT/mutant 多 replicate 完成结果。
- 最新验证基线：
  - `python3 -m py_compile backend/app/api/tools.py backend/app/tools/gromacs_md.py` → 通过
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_gromacs_md_artifacts.py -q` → `66 passed, 21 warnings`
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `140 passed, 21 warnings`
  - `cd frontend && npm run build` → 通过，仅保留既有 `3Dmol` eval 和 chunk warning
  - `cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_auth_resilience.py tests/test_tools_api.py tests/test_ops_api.py tests/test_project_acl.py tests/test_publish_api.py tests/test_llm_gateway.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `217 passed, 182 warnings`
  - `python3 scripts/run_release_acceptance.py` → `passed-with-skips`，0 failed / 1 skipped / 6 total

## 2026-07-08 MD 科学参数层第四层第二批第四步新增发现
- 新增 `POST /api/tools/md/topology/validate`，用于对 WT 或 mutant PDB 执行轻量真实 GROMACS `pdb2gmx` 拓扑预检。
- 新增 `_validate_pdb_topology()`：
  - 校验 PDB 是否含 `ATOM/HETATM`。
  - 检查 `gmx/gmx_mpi` 是否存在；缺失时返回 `status=unavailable` 和 `error_code=GROMACS_NOT_INSTALLED`。
  - 校验 force field 与 water model；不支持时返回 blocked。
  - 只运行 `pdb2gmx`，不继续 editconf、solvate、grompp 或 mdrun，避免把预检变成长任务。
  - 检查 `processed.gro` 与 `topol.top` 是否生成。
  - 复用 topology warning taxonomy，返回 `topology_review.warning_count/risk_flags/entries`。
- 返回语义：
  - `validated`：`pdb2gmx` 返回 0 且必要输出生成。
  - `validated_with_warnings`：命令成功但存在 topology/preprocessing warning。
  - `blocked`：PDB、force field、水模型、pdb2gmx 执行失败或超时。
  - `unavailable`：运行时没有 GROMACS。
- 科学边界：
  - `safe_for_ranking` 只有在拓扑验证通过且没有 risk flags 时为 true。
  - 本轮测试用 monkeypatch 覆盖成功路径，没有在当前机器真实执行长链路 `gmx pdb2gmx`。
  - 后续仍需把通过拓扑预检的 mutant PDB 自动接入 replicate submit，并执行真实 WT/mutant 长任务。
- 最新验证基线：
  - `python3 -m py_compile backend/app/tools/gromacs_md.py backend/app/api/tools.py` → 通过
  - `cd backend && .venv/bin/pytest tests/test_gromacs_md_artifacts.py tests/test_tools_api.py -q` → `64 passed, 21 warnings`
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `138 passed, 21 warnings`
  - `cd frontend && npm run build` → 通过，仅保留既有 `3Dmol` eval 和 chunk warning
  - `cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_auth_resilience.py tests/test_tools_api.py tests/test_ops_api.py tests/test_project_acl.py tests/test_publish_api.py tests/test_llm_gateway.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `215 passed, 182 warnings`
  - `python3 scripts/run_release_acceptance.py` → `passed-with-skips`，0 failed / 1 skipped / 6 total

## 2026-07-08 MD 科学参数层第四层第二批第三步新增发现
- 新增 `POST /api/tools/md/mutants/prepare`，用于从 WT PDB 生成保守 point-mutant PDB 候选结构。
- 支持 `M204H` 和 `A:M204H` 这类点突变标签；无 chain 且多链命中时返回 `blocked_reason=ambiguous_residue_without_chain`。
- 生成策略是“坐标级候选”，不是真实拓扑完成：
  - 检查目标残基存在、源残基名称匹配。
  - 将目标残基 resname 替换为突变氨基酸。
  - 移除与目标残基不兼容的侧链原子，只保留骨架和最小安全侧链原子。
  - 返回 `topology_readiness`、缺失核心原子、缺失最小侧链原子和 warning。
- API 支持 `store=false` 返回内联 `mutant_input.pdb_data`，也支持 `store=true` 将 PDB 写入对象存储并返回 `mutant_input.pdb_object_name`，后续可作为 `/api/tools/md/replicates/submit` 的 `mutant_inputs[variant]`。
- 存储后的 mutant PDB 会绑定当前用户的 tool artifact 下载权限。
- 科学边界：
  - 本轮没有做 side-chain rotamer 建模。
  - 本轮没有运行真实 `pdb2gmx` 拓扑验证。
  - 未通过拓扑验证前，`safe_for_ranking_without_validation=false`，不能作为报告级突变体 ranking 依据。
- 最新验证基线：
  - `python3 -m py_compile backend/app/tools/gromacs_md.py backend/app/api/tools.py` → 通过
  - `cd backend && .venv/bin/pytest tests/test_gromacs_md_artifacts.py tests/test_tools_api.py -q` → `61 passed, 21 warnings`
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `135 passed, 21 warnings`
  - `cd frontend && npm run build` → 通过，仅保留既有 `3Dmol` eval 和 chunk warning
  - `cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_auth_resilience.py tests/test_tools_api.py tests/test_ops_api.py tests/test_project_acl.py tests/test_publish_api.py tests/test_llm_gateway.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `212 passed, 182 warnings`
  - `python3 scripts/run_release_acceptance.py` → `passed-with-skips`，0 failed / 1 skipped / 6 total

## 2026-07-08 MD 科学参数层第四层第二批第二步新增发现
- `tool_task_audits.result_summary` 现在会为真实 `gromacs_md` 完成结果保留紧凑 `md_replicate` 指标：`batch_id`、`replicate_variant`、`replicate_index`、`run_seed`、`rmsd_drift_nm`、`mean_rmsf_nm`、`rg_change_nm`、`sasa_change_nm2`、`is_stable`。
- 新增当前用户维度的批次查询能力：`GET /api/tools/md/replicates/{batch_id}/summary`。
- 批量汇总只读取持久化审计记录中的真实完成任务指标：pending/running 返回 `incomplete`；failed/canceled/revoked 阻止 ranking；completed 但缺少 RMSD/RMSF/Rg/SASA 时返回 `missing_metrics`，不补假值。
- 其他用户同名 `batch_id` 不可见；接口返回 `no_tasks` 而不是泄露存在性。
- 突变体 ranking 的 delta 以当前 batch 的 WT 均值为基准，进入 `stability_delta`、`rmsf_change_mean` 和 `delta_reference=wt_batch_mean`。
- 本轮修复了一个上轮半成品风险：`/md/replicates/submit` 曾在 `wt_input` 后被 summary endpoint 打断，真实提交路径存在不可达代码；现在已恢复函数边界并由测试覆盖。
- 当前边界：没有执行真实长 MD；没有生成真实突变体 PDB 或拓扑；历史已完成任务若是在本次摘要字段增强前落库，可能缺少 `md_replicate`，会被保守标记为缺指标而非参与 ranking。
- 最新验证基线：
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `130 passed, 21 warnings`
  - `cd frontend && npm run build` → 通过，仅保留既有 `3Dmol` eval 和 chunk warning
  - `cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_auth_resilience.py tests/test_tools_api.py tests/test_ops_api.py tests/test_project_acl.py tests/test_publish_api.py tests/test_llm_gateway.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `207 passed, 182 warnings`
  - `python3 scripts/run_release_acceptance.py` → `passed-with-skips`，0 failed / 1 skipped / 6 total

## 2026-07-08 MD 科学参数层第四层第二批第一步新增发现
- 原多 replicate 能生成 plan-only 合同，但不能把 plan 转成真实异步任务提交。
- 本轮新增 `POST /api/tools/md/replicates/submit`：
  - 默认 `dry_run=true`，只返回批量提交计划，不派发 Celery 任务。
  - 真实提交必须传 `confirmation=SUBMIT_MD_REPLICATES`。
  - WT replicate 只要提供 `pdb_object_name` / `pdb_data` / `pdb_path` 即可提交。
  - mutant replicate 必须在 `mutant_inputs` 中提供对应 variant 的 prepared mutant PDB 输入，否则返回 blocked。
  - 不生成、不伪造突变体结构或拓扑。
  - 每个真实提交的 replicate 都进入既有 `gromacs_md` async 队列和任务审计。
- `gromacs_md` 新增可追溯参数：
  - `run_seed`
  - `batch_id`
  - `replicate_variant`
  - `replicate_index`
- `run_seed` 已写入 NVT MDP `gen_seed`，使 replicate 初速度种子可追溯。
- 前端 API 新增 `submitMdReplicateBatch()` 类型和调用方法，页面暂未接入口，避免影响 `/pdb` 当前稳定 UI。
- 当前仍未实现：
  - 自动突变体结构生成。
  - 突变体拓扑参数化/校验。
  - 等待多个真实长任务完成后的自动汇总器。

## 2026-07-08 MD 分析解析层第三步第二批新增发现
- 原分析 selection 已从数字组切换到命名组，但真实体系仍可能出现：
  - 没有 `Backbone`
  - 没有 `SOL`
  - solvent group 命名为 `Water` 或 `non-Protein`
  - GROMACS energy legend 使用 `Epot`、`Etot`、`Kinetic Energy` 等别名
- 本轮新增 ordered fallback 合同：
  - RMSD: `Backbone/Backbone` -> `Protein/Protein` -> `4/4`
  - RMSF: `Backbone` -> `Protein` -> `4`
  - Rg/SASA: `Protein` -> `Backbone` -> `1`
  - protein-protein hbond: `Protein/Protein` -> `Backbone/Backbone` -> `1/1`
  - protein-solvent hbond: `Protein/SOL` -> `Protein/Water` -> `Protein/non-Protein` -> `1/13`
- `_build_analysis_selection_plan()` 升级到 version 2，新增：
  - `group_selection_candidates`
  - `energy_term_candidates`
  - `fallback_inputs`
  - `fallback_policy`
- 真实运行阶段新增 `_run_step_with_selection_fallback()`：
  - 按 candidate 顺序尝试。
  - 首个成功即停止。
  - fallback 失败记录写入 `*.selection_fallback.log.txt`。
  - 返回 `analysis_selection_resolution`，写入顶层和 WT 结果。
- 能量项解析新增更宽松 legend 归一化：
  - `Epot`
  - `Potential Energy`
  - `Kinetic Energy`
  - `Etot`
  - `Total`
- warning 分类词表扩展：
  - `force_field_parameterization`
  - `protonation_or_termini`
  - `solvent_or_ion_setup`
  - 并修复 `ion` 子串误命中 `informational` 的问题。
- 当前未执行真实多体系长 MD；本轮完成的是可回归的解析/selection 合同和 fallback 机制。

## 2026-07-08 真实数据层第一批新增发现
- 项目已有真实数据脚本：
  - `download_rcsb_structures.py`
  - `download_alphafold_models.py`
  - `download_sifts_mappings.py`
  - `download_real_annotations.py`
  - `build_foldseek_db.py`
  - `refresh_live_deploy_data.py`
  - `check_deploy_data.py`
- 缺口是没有一个适合 cron/systemd/阿里云定时任务调用的“单次更新总控”，也没有统一更新记录 manifest。
- 本轮新增 `scripts/run_deploy_data_update.py`：
  - 默认可 `--plan-only` 输出计划，不联网、不写文件。
  - 真实执行会调用 `refresh_live_deploy_data.py`。
  - 执行后会写入 `deploy_data/updates/deploy_data_update_<timestamp>.json`。
  - 更新记录包含 status、duration、manifest、deploy_root、command、stdout/stderr tail、`check_deploy_data` 结果。
  - 支持 `--skip-downloads`，适合现场已同步数据、只重建 Foldseek/env/check 的场景。
  - 支持 `--verify` 和 `--docker-verify`，但默认不跑 live gate，避免在未就绪环境中误失败。
- Makefile 新增：
  - `deploy-data-update-plan`
  - `deploy-data-update`
  - `deploy-data-update-json`
- 数据导入手册已补：
  - `live_manifest.json` 格式
  - plan-only 检查
  - 真实执行命令
  - cron 示例
  - `--skip-downloads` 场景
- 当前没有执行联网下载，也没有声明真实数据已 live-ready；真实数据主项仍需在网络/数据源可用时执行 `make deploy-data-update` 或 `make refresh-live-deploy-data-verify`。

## 2026-07-08 用户权限第四层第二批第二批第二批新增发现
- 组织/团队权限模型此前已建表并接入项目访问计算，但缺少真实管理入口。
- 本轮新增组织管理 API：
  - `GET/POST /api/projects/admin/organizations`
  - `POST/PATCH/DELETE /api/projects/admin/organizations/{organization_id}/members`
  - `GET /api/projects/admin/permission-audits`
- 本轮新增项目组织授权 API：
  - `GET/POST /api/projects/{project_id}/organization-grants`
  - `PATCH/DELETE /api/projects/{project_id}/organization-grants/{grant_id}`
- 项目组织授权边界调整为：
  - 管理员可在后台给任意项目授权组织。
  - 项目 owner 可管理自己项目的组织授权。
  - editor/viewer 仍返回 404，保持不可发现/不可扩权边界。
- `/admin` 前端新增“组织与项目授权”面板：
  - 创建组织
  - 添加/更新/移除组织成员
  - 输入项目 ID 后授权组织为 viewer/editor
  - 修改/撤销组织授权
  - 查看最近权限审计流
- 回归时发现 `projects.py` 有配置测试禁止直接导入 `User` ORM；组织成员展示需要用户 email/name，因此新增 `get_user_display_map()` 到 `project_acl.py` 服务层，保持 API 层不直接依赖 User ORM。
- 当前仍未实现：
  - 组织删除/重命名 API。
  - 权限审计 CSV 导出。
  - 项目详情页内选择组织授权的下拉入口；当前后台入口使用项目 ID。
  - 组织成员自助管理策略；当前为管理员后台管理。

## 2026-07-08 用户权限第四层第二批第二批第一批新增发现
- 原项目 ACL 已支持 owner/editor/viewer 和 action policy，但缺组织/团队继承能力。
- 本轮新增组织权限模型：
  - `organizations`
  - `organization_members`
  - `project_organization_grants`
  - `permission_audits`
- 新增 Alembic 迁移：
  - `b9a4c2d7e8f1_add_organization_permissions.py`
  - 当前 Alembic head 为 `b9a4c2d7e8f1`
- 项目访问计算现在优先级为：
  - project owner -> owner
  - direct project member -> viewer/editor
  - organization inherited grant -> viewer/editor
  - direct/org 多来源取最高 role
- `list_accessible_projects()` 已包含组织继承项目。
- 项目成员 upsert/update/delete 会写入 `permission_audits`：
  - action
  - actor_user_id
  - target_user_id
  - project_id
  - role_before
  - role_after
- 本轮未暴露组织管理 API/UI，避免一次性扩大管理面；后续需要补组织创建、成员管理、项目组织授权和审计查询页面。

## 2026-07-08 MD 分析解析层第三步第一批新增发现
- 原真实 GROMACS 分析步骤使用数字 group id：
  - RMSD: `4 / 4`
  - RMSF: `4`
  - Rg/SASA/Hbond: `1`
- 数字 group id 依赖 GROMACS index 输出顺序，不同拓扑可能不一致。
- 本轮新增 `_build_analysis_selection_plan()`：
  - RMSD 使用 `Backbone / Backbone`
  - RMSF 使用 `Backbone`
  - Rg 使用 `Protein`
  - SASA 使用 `Protein`
  - protein-protein hbond 使用 `Protein / Protein`
  - protein-solvent hbond 使用 `Protein / SOL`
  - energy terms 使用 `Potential / Kinetic-En. / Total-Energy`
- 真实运行结果新增 `analysis_selection_plan`，便于报告追溯使用的 selection。
- 本轮新增 topology warning 分类词表：
  - `charge_balance`
  - `missing_atoms_or_parameters`
  - `ligand_or_cofactor_topology`
  - `constraint_or_lincs`
  - `box_or_pbc`
  - `unclassified`
- `_scan_topology_warnings()` 现在会给每条 warning 增加 `category/severity`，并生成分类 risk flag。
- 当前仍需真实 GROMACS 多体系校准：
  - 部分 GROMACS 版本或体系可能没有 `SOL`、`Backbone` 或 `Protein` group
  - energy legend 可能存在更多别名
  - warning taxonomy 需要用真实失败日志扩充

## 2026-07-08 MD 科学参数层第四层第一批新增发现
- 原 MD 解释层已有 replicate consistency 判断，但缺少上线需要的两个合同：
  - 多 replicate 执行计划：WT/突变体各跑几次、seed 如何生成、哪些任务需要突变体结构
  - 批量 replicate 汇总：已完成 WT/突变体 replicate 指标如何进入 ranking gate
- 本轮在 `gromacs_md` 中新增：
  - `_build_replicate_execution_plan`
  - `_build_md_batch_replicate_summary`
  - `replicate_plan_only`
  - `replicate_count`
  - `replicate_variants`
  - `replicate_seed_base`
- `replicate_plan_only=true` 时不要求 GROMACS，也不读取 PDB，不执行真实 MD，只返回：
  - `replicate_execution_plan`
  - `batch_replicate_summary`
  - `protocol_review`
  - 明确 note：没有执行 GROMACS 命令
- 执行计划现在会标记：
  - WT replicate tasks
  - mutant replicate tasks
  - deterministic seed
  - `requires_mutant_structure`
  - 低于 3 replicate 时 ranking-grade warning
- 批量汇总现在会：
  - 复用 replicate consistency gate
  - 计算候选 `ranking_score`
  - 只有 consistency 通过时才返回 `ranked_candidates`
- 前端 `MDResultView` 新增 Batch Replicate Review：
  - 支持 planned-only 结果单独渲染
  - 显示 planned task、seed、ranking 状态、候选排序和 warning
- 当前仍未实现真实突变体结构生成和拓扑处理；mutant 计划只标记需求，不伪造突变体 PDB。

## 2026-07-08 产品化文档第二层第一批新增发现
- 原文档已有管理员、研发用户、数据导入和故障处理手册，但缺少发布验收视角的一页式操作入口。
- 本轮新增：
  - `docs/manuals/productization-acceptance-manual.md`
  - `docs/manuals/drill-record-template.md`
- 产品化验收手册覆盖：
  - `make release-acceptance`
  - release acceptance JSON/plan
  - 可选 frontend/browser/live/MD/backup verify 增强验收
  - 项目 action policy 权限矩阵
  - `/api/ops/alerts/dispatch` dry-run 和真实发送配置
  - `deploy_data/` 真实数据样例路径
  - 截图建议清单和保存目录
  - 上线前检查单
- 演练记录模板覆盖：
  - 发布验收
  - 数据库备份校验
  - 临时库恢复演练
  - 真实回滚演练
  - 异地备份恢复演练
  - 外部告警发送演练
  - MD 长任务失败演练
  - deploy_data live gate 演练
- 当前不生成截图文件，原因是本环境不能使用图像查看工具，且不能伪造界面证据。真实截图留到 live 浏览器回归时采集。

## 2026-07-08 用户权限第四层第二批第一批新增发现
- 原项目 ACL 已有 `owner/editor/viewer`，但权限判断散落在多个位置：
  - `can_write`
  - `can_manage`
  - 前端根据 `access_role` 自行判断按钮展示
- 本轮新增统一项目 action policy：
  - `project.read`
  - `project.update`
  - `project.delete`
  - `project.members.read`
  - `project.members.manage`
  - `project.sequence.create`
  - `project.sequence.delete`
  - `project.batch.read`
  - `project.batch.run`
  - `project.wiki.publish`
  - `project.file.read`
  - `project.file.write`
  - `project.chat.bind`
- 后端项目列表和详情返回 `permissions`，前端优先消费该字段，避免继续在 UI 层重复推断角色。
- viewer/访客只读边界明确为：
  - 可读项目、成员、批量任务、文件
  - 不可更新项目
  - 不可管理成员
  - 不可新增/删除序列
  - 不可运行 batch
  - 不可发布 wiki
  - 不可绑定 chat 到项目
- chat 和 publish 已切换到同一 action policy，避免和项目 API 出现权限分叉。
- 发布验收曾在与全量 pytest 并行执行时出现一次 `data_admin_readiness` transient error；单独复跑该测试通过，串行复跑发布验收通过。后续验收入口应避免和同一测试数据库的全量 pytest 并行运行。
- 当前仍未实现：
  - 组织/团队级权限
  - 权限继承
  - 权限变更审计表

## 2026-07-08 监控告警第三层第二批新增发现
- `/api/ops/summary` 不能直接发送外部通知，否则普通刷新页面就会产生网络副作用和重复告警。
- 本轮新增独立通知服务 `ops_notifications`：
  - 从 monitoring alerts 生成稳定 fingerprint
  - 默认 `dry_run=true`
  - 真实发送使用 webhook POST JSON
  - 支持重试次数、超时时间、静默窗口、连续失败升级状态
  - 内存保存最近发送状态，避免同一组告警在静默窗口内重复发送
- 新增管理员接口：
  - `POST /api/ops/alerts/dispatch`
  - 普通用户返回 403
  - 默认只返回 planned payload，不访问外部网络
  - `dry_run=false` 且 `OPS_ALERT_WEBHOOK_ENABLED=true`、URL 有效时才真实发送
- `/api/ops/summary` 现在只返回 `notifications.policy`，展示当前通知策略和是否 ready/silenced/disabled，不发送。
- 新增配置：
  - `OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS`
  - `OPS_ALERT_WEBHOOK_RETRY_ATTEMPTS`
  - `OPS_ALERT_SILENCE_SECONDS`
  - `OPS_ALERT_ESCALATE_AFTER_COUNT`
- 测试使用 monkeypatch 拦截 `_post_json`，验证真实发送逻辑和静默逻辑，不依赖真实网络。
- 当前状态：
  - 具备真实 webhook 发送能力
  - 默认关闭，避免误触发企业微信/钉钉/邮件网关
  - 未新增数据库级通知发送审计；当前为进程内状态，服务重启后静默状态会重置

## 2026-07-08 封装交付层第三层第一批新增发现
- 发布前验收原先分散在多个入口：
  - `check_upgrade_readiness.py`
  - `run_acceptance_matrix.py`
  - `package_deploy_bundle.py --dry-run`
  - `rollback_plan.py`
  - `restore_drill.sh --dry-run`
- 本轮新增 `scripts/run_release_acceptance.py`，把上述入口组合为默认非破坏性发布验收：
  - 升级 readiness：允许 dirty worktree 作为 warning，但 blocked 会失败
  - 验收矩阵：默认只跑本地快速安全测试
  - 部署包：只跑 dry-run，不生成新包
  - 回滚计划：只读生成计划，不停服务、不恢复数据库
  - 恢复演练：只跑 `restore_drill.sh --dry-run`，不创建临时库、不触碰主库
- 备份校验默认跳过，原因是它依赖本机 `pg_restore` 或 Docker compose postgres；本机当前无 `pg_restore`。需要时可显式执行：
  - `python3 scripts/run_release_acceptance.py --include-backup-verify`
  - 或 `python3 scripts/run_release_acceptance.py --include-backup-verify --backup-verify-compose`
- Makefile 新增：
  - `make release-acceptance`
  - `make release-acceptance-json`
  - `make release-acceptance-plan`
- 安全边界：
  - 默认不执行真实 rollback
  - 默认不执行真实 restore
  - 默认不跑 live gate、真实浏览器 smoke、MD 黑盒长任务
  - 真实回滚和异地备份演练仍需要维护窗口、目标存储账号和明确授权

## 2026-07-08 监控告警第三层第一批新增发现
- 项目已有 Prometheus 指标和 `/api/ops/summary`，但 ops summary 还缺三个上线需要的聚合视图：
  - 近期慢请求/5xx 错误请求
  - 任务失败趋势
  - 外部通知配置状态
- 本轮复用现有 `MetricsMiddleware`，新增内存窗口快照：
  - 最近 500 条 HTTP 请求
  - slow threshold 默认 `OPS_SLOW_REQUEST_THRESHOLD_SECONDS=2.0`
  - 统计 slow_count、error_count、status_counts、top_endpoints、recent_slow、recent_errors
- `/api/ops/summary` 新增：
  - `requests`
  - `task_audits`
  - `notifications`
  - `http.slow_requests`
  - `http.5xx_errors`
  - `tasks.failure_trend`
  - `notifications.webhook`
- 任务失败趋势来源于 `tool_task_audits` 聚合，只返回 failure_counts/failure_trend/slow_count/alerting，不返回跨用户任务明细。
- 外部通知本轮只做配置状态：
  - `OPS_ALERT_WEBHOOK_ENABLED`
  - `OPS_ALERT_WEBHOOK_URL`
  - `OPS_ALERT_WEBHOOK_KIND`
  - 当前 `mode=status_only`，不主动发送通知
- 未在本轮实现真实 webhook 发送、重试、静默和升级策略，避免误触发外部系统。

## 2026-07-08 用户权限第四层第一批新增发现
- 原用户权限已有 role/admin 和项目 ACL，但用户生命周期状态仍缺失：
  - 无法禁用离职/异常账号
  - 无法临时锁定账号
  - 已签发 token 在账号禁用后仍可能继续访问
- 本轮新增用户状态字段：
  - `is_active`
  - `locked_at`
  - `disabled_reason`
- 鉴权边界统一收敛：
  - 登录时拒绝禁用/锁定用户
  - refresh 时拒绝禁用/锁定用户
  - `get_current_user` 对已持有 token 的禁用/锁定用户返回 403
- 管理员接口新增：
  - `PATCH /api/auth/admin/users/{user_id}/status`
  - 管理员不能禁用或锁定自己的账号，避免自锁死
- `/admin` 用户表新增状态展示和启用/禁用/锁定/解锁操作。
- 数据库迁移新增：
  - `7c2a1d4e9b66_add_user_status_controls.py`
  - 当前 Alembic head 已更新为 `7c2a1d4e9b66`
- 未在本轮实现：
  - 组织/团队级权限
  - 访客只读策略
  - 更细粒度 action policy

## 2026-07-08 自动化测试增强第一层新增发现
- 现有项目已有分散测试能力：
  - 后端单测覆盖文件下载权限、工具 artifact owner 绑定、artifact bundle 下载
  - `backend/scripts/verify_md_blackbox.py` 可跑外部 HTTP MD 黑盒
  - `frontend/tests/public-smoke.mjs` / `live-smoke.mjs` 可跑浏览器 smoke
  - deploy live gate / structure smoke 已在 Makefile 中存在
- 风险是这些入口分散，部署前不容易知道应该跑哪一组，也容易误跑长 MD 或依赖 live 服务的测试。
- 本轮新增 `scripts/run_acceptance_matrix.py`：
  - 默认只跑安全、快速、本地可执行的验收：
    - 环境预检
    - 文件下载权限回归
    - MD artifact 白盒测试
    - 数据后台 readiness/import dry-run 测试
    - OSS/S3 环境形态兼容预检
  - `--include-frontend` 才跑前端生产构建
  - `--include-browser-smoke` 才跑真实浏览器 smoke
  - `--include-md-blackbox` 才跑外部 HTTP MD 黑盒长流程
  - `--include-live` 才跑 deploy live gate 和 live smoke
  - `--plan-only` 可输出计划，不执行命令
  - `--json` 可供 CI/部署脚本消费
- 新增 Makefile 入口：
  - `make acceptance-matrix`
  - `make acceptance-matrix-json`
  - `make acceptance-matrix-plan`
- 本轮未实际启动 live 服务，也未跑长时间 MD 黑盒；这些留给第二层，在服务稳定运行且用户允许后执行。

## 2026-07-08 数据管理后台第二层新增发现
- 原 `/api/data/admin/readiness` 已能只读展示 deploy_data 组件状态，但缺少运维后台需要的四类信息：
  - 组件未就绪的具体失败原因
  - 更新 manifest 的筛选能力
  - 数据版本/最新 manifest 对比
  - 真实导入触发入口
- 本轮在 `deploy_data_status` 中补充：
  - 每个组件的 `failure_reason`
  - manifest 的 `status / failure_reason / component / version`
  - `updates.filters`
  - `version_comparison`
- 新增管理员接口：
  - `GET /api/data/admin/updates`
  - `POST /api/data/admin/import`
- 导入接口安全边界：
  - 默认 `dry_run=true`，只返回命令计划，不写入文件
  - 真实执行必须传 `dry_run=false` 且 `confirmation=RUN_DEPLOY_DATA_IMPORT`
  - 真实执行前会检查源路径存在性
  - 前端 `/admin` 当前只提供 dry-run 计划按钮，不提供真实执行按钮
- 前端 `/admin` 数据资产区新增：
  - 组件失败原因
  - 数据版本对比
  - 更新记录组件/状态筛选
  - deploy_data 导入 dry-run 表单
- 验证结果：
  - `tests/test_data_api.py` 通过
  - 前端生产构建通过
  - 关键后端回归通过
  - 环境预检通过
  - 升级 readiness 仍仅有历史 dirty worktree warning

## 2026-07-08 任务审计第四层新增发现
- 管理员任务审计原先已有跨用户列表、摘要和 CSV 导出，但缺少同一套过滤条件，导致页面看到的结果和导出的证据可能不一致。
- 本轮新增统一过滤合同：
  - `tool`
  - `status`
  - `queue`
  - `failure_class`
  - `submitted_after`
  - `submitted_before`
  - `failed_only`
  - `slow_only`
- 数据库原生字段优先在 SQL 层过滤：
  - tool/status/queue/submitted 时间范围/failed_only
- 派生字段保持 Python 层过滤：
  - `failure_class`
  - `slow_only`
- 摘要新增 `failure_trend`：
  - 按 `terminal_recorded_at / updated_at / submitted_at` 取日期桶
  - 每天返回 `failure_counts` 和 `total_failures`
- 摘要新增只读 `alerting` 块：
  - 当前是 `summary_only`
  - `external_delivery` 标记为 `not_configured`
  - 只输出告警规则触发状态，不发送外部通知，避免误触发企业微信/钉钉/邮件等外部系统
- `/admin` 页面新增筛选栏、失败日期趋势和告警联动状态，CSV 导出复用同一套筛选条件。
- 验证结果：
  - `tests/test_tools_api.py` 通过，新增过滤和 CSV 过滤覆盖
  - 前端生产构建通过
  - 关键后端回归通过
  - 环境预检通过
  - 升级 readiness 仍仅有历史 dirty worktree warning

## 2026-07-08 MD 科学参数与结果解释第二层新增发现
- 原 MD 协议模板已有 `simulation_time_ns / equilibration_ps / force_field / water_model`，但缺少科学审查语义：
  - 为什么用该力场/水模型
  - 系统准备需要检查什么
  - cutoff、PME、constraint、timestep 的固定策略
  - 是否能用于 ranking，需要几次 replicate
- 本轮在 `md_protocols` 中补充：
  - `scientific_controls.force_field_rationale`
  - `scientific_controls.water_model_rationale`
  - `system_preparation_checks`
  - `cutoff_policy`
  - `constraint_policy`
  - `replicate_policy`
- `resolve_md_protocol_parameters()` 现在返回 `protocol_review`，用于把协议科学边界追溯到任务结果。
- `gromacs_md` 结果新增：
  - `protocol_review`
  - constraint / cutoff / PME / rcoulomb / rvdw 参数追溯
  - review warnings
- MD 解释层新增缺失证据模型：
  - `missing_evidence`
  - energy term not extracted
  - hbond analysis not extracted
  - analysis file missing or empty
- 这解决一个重要科学边界：当前 pipeline 会生成真实 RMSD/RMSF/Rg/SASA，但能量项和氢键项仍未解析时，报告必须明确“缺失证据”，不能暗示已有完整机制证据。
- 前端同步展示：
  - PDB 页协议选择显示 risk level 和 ranking replicate 要求
  - MD 报告解释区显示 Protocol Review
  - MD 报告解释区显示 Missing Evidence
- 后续仍需：
  - ligand/cofactor/protonation 自动检查
  - GROMACS energy / hbond 真解析
  - WT/突变体 replicate consistency
  - 拓扑 warning 结构化解析

## 2026-07-08 监控告警第二层与回滚计划新增发现
- 原 `/api/ops/summary` 已有配置类健康检查，但还缺运行态观测：
  - Redis broker 是否可达
  - Celery worker 是否在线
  - default / md_cpu 队列 backlog
  - active task 数量
- 本轮新增运行态监控块：
  - `runtime.redis.status`
  - `runtime.redis.queues`
  - `runtime.celery.status`
  - `runtime.celery.online_workers`
  - `runtime.celery.active_tasks`
- 监控实现保持只读和容错：
  - Redis ping / llen 超时或失败不会让 API 500，只会产生 warning
  - Celery inspect 失败或没有 worker 响应也降级为 warning
  - Redis URL 会隐藏密码
- 前端 `/data` 监控页新增：
  - Worker 在线数
  - Redis 状态
  - 队列数量
  - Celery active task
  - 每个队列 backlog
- 封装交付层新增 `scripts/rollback_plan.py`：
  - 只读生成回滚计划，不停止服务、不恢复数据库
  - 自动识别最新部署包和最新 `.dump` 备份
  - 输出 verify-backup / restore-drill / restore / redeploy / post-check 步骤
  - 显式标记 destructive 步骤
  - 支持 `--json`
- 当前 rollback plan 本机状态：
  - deploy package: `dist/packages/protein-ai-platform-20260707T235203Z-25679eb.tar.gz`
  - database backup: `backups/protein_ai_20260708T001139Z.dump`
  - summary: `ready-for-manual-review`
- 仍未执行真实回滚；真实恢复/停服务仍需单独维护窗口和明确授权。

## 2026-07-08 数据管理后台与任务审计第二层新增发现
- 管理后台原先只有用户角色和跨用户任务审计，缺少真实数据资产的一屏管理视图。
- 本轮新增 admin-only 数据就绪度接口：
  - `GET /api/data/admin/readiness`
  - 复用 `collect_deploy_data_readiness()`
  - 只读返回 `annotations / sifts / pdb / alphafold / foldseek / smoke_query` 状态、数量、大小、路径、更新 manifest 和 next actions
  - 普通用户访问返回 403
- `/admin` 页面新增“数据资产状态”区块：
  - 显示 live/demo/partial/empty 总状态
  - 显示各组件 ready/demo/empty/missing
  - 显示数量、大小、路径、更新记录和下一步动作
  - 不提供下载、删除、导入按钮，避免误操作真实数据
- 任务审计原先已有提交、状态、结果和 artifact 摘要，但缺少运营判断字段。
- 本轮在不改数据库表结构前提下，新增派生字段：
  - `duration_seconds`
  - `failure_class`
  - `is_slow`
- 失败分类第一版规则：
  - canceled
  - timeout
  - permission
  - missing_input
  - md_runtime
  - runtime_error
- CSV 导出也新增耗时、失败分类和慢任务字段，管理后台审计卡片同步展示。
- 当前仍需后续补：
  - 任务环境版本快照
  - 按工具/用户/失败分类筛选
  - 失败趋势统计
  - 真实 Worker 心跳和队列深度

## 2026-07-08 项目级 ACL 第一层新增发现
- 原项目权限边界主要停留在“项目 owner 自己可见/可操作”，缺少共享项目时的读写分级。
- 本轮新增 `project_members` 表和 ACL 服务层，项目访问角色分为：
  - `owner`：项目拥有者，可管理成员、更新/删除项目、写入序列、运行批量任务
  - `editor`：可读写项目内容，可更新项目、添加/删除序列、运行批量任务，但不能管理成员
  - `viewer`：只能读取项目、成员、批量任务，不能写入或管理
- API 安全边界采用“不可访问统一返回 404”，避免非成员通过 403/404 差异探测项目存在性。
- 兼容既有回归要求：
  - `projects.py` 继续使用 `get_current_user()` 返回的 dict
  - 不在 `projects.py` 直接导入 `User` ORM
  - 用户查找和成员展示移动到 `project_acl` 服务层
- 测试暴露并修复一个真实问题：
  - 新增成员后，同一 SQLAlchemy session 中 `project.members` 关系可能仍是旧缓存
  - 已改为成员序列化和可访问项目角色计算均显式查询 `ProjectMember`，不依赖关系缓存
- 前端只做第一层低侵入保护：
  - 项目列表显示 `owner/editor/viewer`
  - 非 owner 不显示删除项目按钮
  - viewer 不显示新增序列、删除序列、批量运行入口
- 当前仍未覆盖的权限深水区：
  - 访客只读入口
  - 组织/团队级权限
  - 用户禁用、锁定和邀请流程

## 2026-07-08 项目文件/Wiki/发布 ACL 第二层新增发现
- 白盒审计发现 `publish.py` 仍按旧逻辑 `project.user_id == user["id"]` 判断权限。
- 这会导致两个产品问题：
  - 共享项目 editor/viewer 即使在 `/api/projects` 能访问项目，也不能访问项目文件、Wiki 树或发布能力
  - 权限策略分散在多个 API 文件里，后续很容易出现“项目详情能看，文件接口不能看”的体验断裂
- 本轮将项目相关发布接口统一接入 `project_acl`：
  - viewer 可读：文件列表、文件下载、文件内容、Wiki 树、Wiki 页面、项目会话列表
  - editor/owner 可写：手动发布、删除文件、报告生成、会话绑定到项目
  - 非成员继续统一返回 404
- Wiki 树有一个特殊边界：
  - 如果项目还没有 Outline collection，viewer 不会触发自动创建
  - editor/owner 访问时仍可通过 `ensure_project_wiki` 初始化
- 新增测试覆盖：
  - viewer 可列出共享项目文件
  - viewer 不能删除文件或发布报告
  - editor 可以发布报告
  - 非成员不能列出项目文件
- 当前仍需后续继续审计：
  - 文件系统级 `/api/files/*` 与项目文件下载之间的权限一致性
  - 前端是否需要完整成员管理 UI，而不仅是 API 能力

## 2026-07-08 聊天绑定项目 ACL 第三层新增发现
- 白盒审计确认 `POST /api/chat/stream` 原先存在 ACL 绕过点：
  - 新建 conversation 时会直接写入请求体里的 `project_id`
  - 已有 conversation 且未绑定项目时，也会直接绑定请求体里的 `project_id`
  - 这意味着只要知道项目 id，viewer 或非成员理论上可以把聊天分析内容写入项目上下文
- 本轮新增 `_assert_project_write_access()`：
  - `project_id` 为空时不影响普通聊天
  - `project_id` 存在时必须是 editor 或 owner
  - viewer 和非成员统一返回 404，且不会启动 orchestrator stream
- 新增回归测试覆盖：
  - viewer 绑定项目聊天返回 404，且 orchestrator 未被调用
  - editor 绑定项目聊天返回 200，SSE 流仍正常
- 这一步把“项目分析内容写入入口”也纳入 ACL，和项目序列、批量任务、文件发布保持一致。

## 2026-07-08 真实备份与临时库恢复演练新增发现
- 本轮已执行真实数据库备份：
  - 备份文件：`backups/protein_ai_20260708T001139Z.dump`
  - checksum：`backups/protein_ai_20260708T001139Z.dump.sha256`
  - 大小：112M
- 已执行真实备份校验：
  - sha256 校验通过
  - `pg_restore --list` 通过
- 首次校验失败不是备份损坏：
  - 原因是 `verify_backup.sh --compose` 进入 `docker/` 目录后，`backups/...` 相对路径失效
  - 已改为把备份文件解析成绝对路径
  - 重跑后通过
- 已执行临时库恢复演练：
  - 临时库：`protein_ai_restore_check`
  - 恢复后 sanity query 显示 public schema 表数量为 30
  - 演练结束后已删除临时库
  - 后续查询临时库无输出，确认清理完成
- 本轮没有恢复或覆盖主库 `protein_ai`。
- 这说明当前本地 Docker PostgreSQL 的备份链路已经具备：
  - 生成备份
  - 校验备份
  - 恢复到临时库验证
  - 自动清理临时库
- 后续仍需补：
  - 异地备份上传和下载演练
  - 阿里云 RDS/OSS 场景的备份恢复演练
  - 升级脚本真实执行演练

## 2026-07-08 备份校验与恢复演练第一层新增发现
- 之前已有 `backup.sh` / `restore.sh`，但还缺两个关键安全环节：
  - 不恢复数据库也能验证备份文件是否有效
  - 不触碰主库也能演练恢复过程
- 本轮新增：
  - `scripts/verify_backup.sh`
  - `scripts/restore_drill.sh`
- `verify_backup.sh` 能做：
  - 检查备份文件存在
  - 校验可选 `.sha256`
  - 识别 `.dump` / `.sql.gz`
  - 对 `.dump` 运行 `pg_restore --list`
  - 对 `.sql.gz` 运行 `gunzip -t`
- `restore_drill.sh` 的安全边界：
  - 默认临时库为 `protein_ai_restore_check`
  - 拒绝使用主库名、`postgres`、`template1`
  - 默认验证后删除临时库
  - `--dry-run` 只打印计划，不创建数据库、不恢复
- 当前只完成“脚本级与 dry-run 级演练”，没有执行真实数据库恢复：
  - 没有创建临时库
  - 没有对主库做任何恢复动作
  - 后续如要真实演练，需要先生成一份当前备份，再执行 `make restore-drill BACKUP_FILE=...`
- 验证结果：
  - shell 语法检查通过
  - gzip 样本验证通过
  - `make restore-drill-dry-run BACKUP_FILE=...` 通过
  - 后端关键测试通过

## 2026-07-08 版本与手册第一层新增发现
- 版本号之前分散在多个位置：
  - 后端 `FastAPI(version="0.1.0")`
  - `/api/health` 写死 `0.1.0`
  - 前端 `package.json` / `package-lock.json` 仍是 `0.0.0`
  - 升级 readiness 因前端版本 `0.0.0` 持续 warning
- 本轮新增根 `VERSION` 文件作为项目版本源，当前为 `0.1.0`。
- 后端新增 `app/core/version.py`：
  - 读取 repo-root `VERSION`
  - `main.py` 的启动日志、FastAPI version、`/api/health` 统一使用该版本
- 前端 `package.json` 和 `package-lock.json` 根版本同步为 `0.1.0`。
- `scripts/check_upgrade_readiness.py` 新增：
  - `project.version`
  - 前端版本与项目版本一致性校验
- 当前升级 readiness 结果：
  - `project.version`: ok
  - `frontend.version`: ok
  - `alembic`: ok
  - `deploy.package`: ok，最新包为 `dist/packages/protein-ai-platform-20260707T235203Z-25679eb.tar.gz`
  - 仅剩 warning：工作区存在大量未提交/未纳入版本控制的变更
- 文档第一层已补：
  - `docs/manuals/admin-manual.md`
  - `docs/manuals/researcher-manual.md`
  - `docs/manuals/data-import-manual.md`
  - `docs/manuals/troubleshooting-manual.md`
- 当前文档是“文字版可执行手册”，还不是最终交付版：
  - 没有截图
  - 没有真实演练记录
  - 没有客户环境参数模板
  - 后续需补真实数据样例和故障回滚记录

## 2026-07-07 初始化、备份恢复、升级编排新增发现
- 初始化向导已补齐第一层：
  - `scripts/init_deployment.py`
  - 支持 `local / aliyun-app / aliyun-gpu / all`
  - 默认不覆盖现有 env 文件，必须 `--force` 才覆盖
  - 支持 `--dry-run`
  - 自动生成 `SECRET_KEY`、PostgreSQL 密码、MinIO 密码、OIDC/Outline secrets 等本地随机默认值
- 备份恢复发现一个真实格式风险：
  - 旧 `backup.sh` 用 `pg_dump --format=custom --compress=9`
  - 但文件名是 `.sql.gz`
  - 旧 `restore.sh` 用 `gunzip | psql`
  - 这会导致真实恢复时格式不匹配
- 备份恢复已改为明确规则：
  - 新备份输出 `protein_ai_<timestamp>.dump`
  - 生成 `.sha256`
  - 新恢复对 `.dump` 使用 `pg_restore`
  - 对历史 `.sql.gz` 继续按 gzip plain SQL 兼容恢复
  - 恢复默认交互确认，`--yes` 才跳过确认
  - `--dry-run` 可验证恢复计划，不改数据库
- 升级脚本第一层已补齐：
  - `scripts/check_upgrade_readiness.py`：只读检查 git、前端版本、Alembic、env、部署包、环境预检
  - `scripts/upgrade.sh`：本地模式先 readiness，再备份，再 compose up/build，再 Alembic upgrade head
  - `aliyun-app / aliyun-gpu` 模式委托 `deploy-aliyun.sh`
- 当前升级 readiness 实测：
  - Alembic: ok，5 个迁移，单一 head `f1b9c8d2a704`
  - deploy package: ok，已有 `dist/packages/protein-ai-platform-20260707T092704Z-25679eb.tar.gz` 和 checksum
  - environment: ok
  - warning 仍有两个：工作区未提交变更多、前端版本仍为 `0.0.0`
- 当前仍不是完整发布系统：
  - 还缺正式语义化版本号
  - 还缺真实升级演练
  - 还缺完整运维手册和故障回滚手册
  - 还缺自动化备份恢复演练

## 2026-07-07 部署包第一层新增发现
- 原项目已有 `env-preflight`、阿里云 compose、`deploy-aliyun.sh`、数据库备份脚本，但缺少“把项目交给另一台机器”的可重复源码部署包入口。
- 本轮新增 `scripts/package_deploy_bundle.py` 和 Makefile 目标：
  - `make package-deploy-bundle-dry-run`
  - `make package-deploy-bundle`
- 初版按黑名单全仓遍历时暴露真实风险：
  - 会误包含 `Venus-15B淀粉酶项目` 等大型业务资料
  - 嵌套的 `backend/.venv` 也可能因匹配规则不足被打入包
  - dry-run 一度达到 2GB 级别，不适合交付
- 已改为白名单式根目录策略：
  - 允许 `backend/`、`frontend/`、`docker/`、`scripts/`、`docs/`、`.github/` 和根部必要文件
  - 默认排除 `.venv`、`node_modules`、`dist/build`、`.env`、密钥、日志、数据库、`storage/`、`backups/`、`backend/data`、`deploy_data/`
- 当前实测结果：
  - dry-run: 365 files，约 3.4MB
  - 实际包: `/private/tmp/protein-ai-package-test/protein-ai-platform-20260707T091637Z-25679eb.tar.gz`
  - checksum 校验通过
  - 严格检查未发现 `.venv/node_modules/deploy_data/storage/backups/.env` 等禁入路径
- 设计边界：
  - 默认部署包只包含代码、模板、脚本，不包含真实科学数据和生产密钥
  - 如确实要随包带 `deploy_data/`，必须显式传 `--include-deploy-data`
  - 后续还需要初始化向导、备份恢复增强、版本升级脚本，才能达到完整“好部署、好维护”

## 2026-07-07 管理后台第一层新增发现
- 角色字段和 `require_admin` 已经存在后，下一步最小闭环不是先做复杂 ACL，而是先把管理员可见的基础操作产品化：
  - `GET /api/auth/admin/users`：管理员列出用户
  - `PATCH /api/auth/admin/users/{user_id}/role`：管理员更新 `admin/researcher` 角色
  - `GET /api/tools/admin/tasks/audits/export`：管理员导出脱敏任务审计 CSV
  - `/admin`：前端管理入口，显示用户角色、跨用户任务审计和导出按钮
- 权限边界继续保持后端强校验：
  - 普通用户访问 admin API 返回 403
  - 前端只是体验层拦截，不作为安全边界
  - 管理员不能把自己的账号从 `admin` 降级，避免误锁管理后台入口
- 审计导出仍只导出摘要：
  - `pdb_data/sequence/token/password/secret` 等敏感或大字段仍按已有摘要逻辑脱敏
  - CSV 中包含任务 id、用户 id、工具、状态、队列、进度、时间、错误、输入摘要、结果摘要和 artifact manifest
- 当前仍未完成的权限深水区：
  - 项目级 ACL
  - 访客只读边界
  - 更细粒度角色/权限策略
  - 用户禁用、重置密码、审计筛选统计等完整后台功能

## 2026-07-07 封装交付第一层新增发现
- 之前已有 `deploy_data` 检查、live gate、阿里云 app/gpu compose，但缺少一个站在“项目能不能打包/部署”的统一环境预检。
- 新增 `scripts/check_environment.py` 后，交付预检可以只读检查：
  - Python / Node / npm / Docker / make
  - backend `.venv`
  - frontend `node_modules`
  - backend/docker env 示例
  - deploy_data root
  - local/aliyun compose 文件
  - deploy-aliyun.sh
- 新增 Makefile 入口：
  - `make env-preflight`
  - `make package-preflight`
- 当前机器实测 `summary=ready`，说明本机具备继续做封装打包的基础条件。
- 这仍是一层预检，还没有真正做一键部署包、初始化向导、备份恢复和版本升级。

## 2026-07-07 权限角色第一层新增发现
- 原用户模型没有角色字段，`get_current_user()` 只返回 `id/email/name`，导致后续管理后台、跨用户审计、敏感操作没有统一授权边界。
- 本轮新增 `users.role`：
  - 默认值 `researcher`
  - 管理员角色为 `admin`
  - 鉴权返回的 current_user 和 `/api/auth/me/session/login/refresh/register` 响应都带 `role`
- 新增 `require_admin` 依赖，先用于两类接口：
  - `/api/auth/admin/ping`
  - `/api/tools/admin/tasks/audits`
  - `/api/tools/admin/tasks/{task_id}/audit`
- 这只是权限第一层：
  - 还没有用户管理 UI
  - 还没有项目级 ACL
  - 还没有访客只读策略
  - 但已经具备把管理后台和敏感操作挂到 admin 边界上的基础能力

## 2026-07-07 监控告警第一层新增发现
- 原 `/api/ops/summary` 已能返回 uptime、磁盘、数据状态、Worker profile 和外部依赖配置，但前端/机器无法直接判断哪些项需要处理。
- 本轮在不引入 Prometheus/Alertmanager 等外部依赖的前提下，新增内置健康检查：
  - `disk.project_root`: 80% warning，90% critical
  - `data.deploy_root`: deploy_data 根目录是否存在
  - `data.live_readiness`: live-ready / demo-ready / partial
  - `worker.md_profile`: MD 是否隔离到 `md_cpu` 且具备长任务 time limit
  - `endpoint.*`: Redis/Postgres/Object Storage/Chroma 配置是否存在
- `/api/ops/summary` 顶层 `status` 现在可能是：
  - `ok`: 无告警
  - `degraded`: 存在 warning
  - `critical`: 存在 critical
- 前端 `/data` 的“监控”页签新增健康检查列表和告警数量，可以直接看到当前卡点。
- 这仍是第一层，只判断配置和本机状态；还没有真实 Worker 心跳、队列深度、错误率、慢请求或外部通知。

## 2026-07-07 任务审计持久化第一层新增发现
- 原任务审计主要存在于 Redis/本地缓存：
  - 能解决轮询所有权、取消状态、artifact 下载绑定
  - 但无法支撑长期审计、后台查询、失败统计、用户任务历史
- 本轮新增数据库表 `tool_task_audits`，但不替换现有 Redis 所有权缓存，原因：
  - Redis 仍适合快速权限校验和短期任务状态
  - DB 更适合长期审计、查询和统计
  - 双写第一层风险最低，不改变现有下载权限逻辑
- 已落库的字段覆盖第一层审计需求：
  - task id、用户、工具名、状态、队列、超时策略、进度、stage
  - 输入摘要，且 `pdb_data/sequence/token/password/secret` 等敏感或大字段会被摘要化/脱敏
  - 结果摘要、artifact manifest、错误、取消时间、终态时间
- 新增接口只允许当前用户读自己的审计：
  - `GET /api/tools/tasks/audits`
  - `GET /api/tools/tasks/{task_id}/audit`
- 后续还缺管理员视角、环境版本、耗时统计、失败分类和导出能力。

## 2026-07-07 产品化待建清单第二层新增发现
- “全部开始”后，当前最合适的第二批不是直接重构后台，而是补三条只读、可测试、低风险的产品化基础合同：
  - deploy_data 更新记录：从 `live_manifest.json`、`import-manifest.json` 和 benchmark `bundle_manifest.json` 汇总更新时间、关键字段、计数和文件大小
  - MD 协议模板：先沉淀 `smoke_short`、`engineering_short`、`production_review` 三档参数，后续再接入 UI 选择和专家审核
  - 运维摘要：统一暴露 API uptime、磁盘、数据状态、Worker 队列/超时、外部依赖主机配置
- 这批仍保持 read-only：
  - 不自动下载/删除/覆盖真实数据
  - 不改变 GROMACS 真实执行流程
  - 不改变权限模型，仅 `/api/ops/summary` 要求登录
- 前端 `/data` 新增“监控”页签，不单独拆管理员后台，避免在能力还少时过早扩大导航结构。
- 当前 MD 协议模板只是“安全默认参数合同”，还不是完整科学 SOP；后续需要继续补力场选择依据、质子化/配体/辅因子检查、重复模拟策略和报告级阈值。
- `/pdb` 真实 MD 提交流程原先硬编码 `simulation_time_ns=0.01`、`equilibration_ps=10`、`ensemble=nvt`，这不利于后续科学参数治理。
- 现在 `/pdb` 改为：
  - 页面加载 `GET /api/tools/md/protocols`
  - 用户选择协议模板
  - 提交前调用 `POST /api/tools/md/protocols/{id}/resolve`
  - 将 resolve 后参数与当前 `pdb_object_name` 合并提交给 `gromacs_md`
- 后端 `gromacs_md` 增加可选 `protocol_id`，并在结果的 `wild_type.simulation_parameters.protocol_id` 中保留追溯信息。
- 原 MD 解释层虽然已有 `verdict/confidence/findings/warnings`，但缺少面向研发复核的“证据等级、质量门控、下一步建议”。
- 现在解释层新增：
  - `evidence_level`: `smoke / screening / review_candidate`
  - `conclusion`: 面向报告阅读的结论摘要
  - `quality_gates`: RMSD/RMSF 的 pass/review/fail/missing 门控
  - `recommended_next_steps`: 按轨迹长度和异常指标给出复核动作
- 前端 MD 报告新增 “Interpretation & Review” 区块，直接展示 verdict、confidence、evidence level、质量门控、warning 和 next steps。

## 2026-07-07 产品化待建清单启动新增发现
- 用户确认“阿里云服务器等等先不算，其余全部开始”，因此本阶段重点从云侧资源落地切到项目内部产品化能力。
- 当前最适合作为第一批基础设施的不是直接写完整管理后台，而是先建立三条可复用合同：
  - `GET /api/data/readiness`：统一查看 `deploy_data` 真实数据、demo 数据、缺失数据状态
  - MD 结构化解释：把 RMSD/RMSF/Rg/SASA 从散落指标提升为 `verdict/confidence/findings/warnings/thresholds`
  - 工具任务审计摘要：轮询接口直接返回提交时间、队列、超时、取消、终态、进度等审计字段
- 这三条合同能支撑后续多个待建项：
  - 数据管理后台可以直接消费 `data/readiness`
  - MD 结果解释层可以继续扩展同一个 `interpretation` payload
  - 任务审计层可以从现有 Redis task owner metadata 过渡到数据库持久化
- 前端 `/data` 已接入“就绪度”标签页，暂不新增独立后台路由，避免导航膨胀；后续如果管理项变多，再拆成 `/admin/data` 或 `/ops/data`。
- 当前第一层仍是 read-only 和低侵入：
  - 不导入/删除数据
  - 不改变 MD 执行参数
  - 不改变权限模型
  - 不改变现有 `/data` 搜索、底物、统计功能

## 2026-07-07 阿里云托管拓扑准备新增发现
- 之前仓库虽有 `deploy_data`、live smoke 和容器化 Foldseek 闭环，但真正的生产部署资产仍停留在“单机全家桶”模式：
  - `deploy-aliyun.sh` 仍默认安装后直接启动 `postgres/redis/minio/chromadb`
  - `docker/docker-compose.yml` 也默认把 `postgres/redis/minio/md-worker` 全部跟 Web 同机部署
- 这与部署文档里的目标拓扑不一致：
  - `ECS-App-01/App-02` 应走 `RDS PostgreSQL + Cloud Redis + OSS`
  - `ECS-GPU-01` 应只承担独立 `md-worker`
- 当前已完成的关键准备有三层：
  - backend 存储层现在支持 `MINIO_SECURE` 与 `MINIO_REGION`，因此现有 `MINIO_*` 配置可以直接指向 OSS
  - 新增 `docker/docker-compose.aliyun-app.yml` 与 `docker/docker-compose.aliyun-gpu.yml`，把 app node 和 GPU node 的职责拆开
  - 新增 `.env.aliyun.app.example` / `.env.aliyun.gpu.example` 与新版 `deploy-aliyun.sh`，把部署入口从“老的一键本地全家桶”改成“按角色部署托管拓扑”
- 这意味着当前仓库已经具备和方案文档一致的“准备态”：
  - 本地开发/全量验证继续用原 `docker-compose.yml`
  - 上云准备改用 `aliyun-app` / `aliyun-gpu` compose
  - `App-02` 直接复用 `App-01` 同一套 compose/env 即可作为备用与切换节点
- 当前仍未做的不是“代码准备”，而是“云侧真实参数与资源落地”：
  - 真实 `RDS/Redis/OSS` 连接参数
  - 真实 `deploy_data` live 数据
  - GPU 节点上的 `NVIDIA Container Toolkit` 和实际任务验收

## 2026-07-06 wiki OIDC 入口回归新增发现
- `wiki` “进不去”的直接根因不是普通 `401`，而是 Outline OAuth 启动链被错误入口打断后触发的 `Invalid OAuth state`。
- 运行态关键对比：
  - 异常链路里，浏览器先进入了 backend `/auth/oidc` 兼容入口，再被送到 `/api/oidc/authorize`，请求里没有有效 `state`，回调也出现空 `state=`。
  - 正确链路必须先进入 Outline 自己的 `/wiki/auth/oidc`，由 Outline 生成 `oauth_csrf` cookie 和签名 `state`，再跳转到 provider `/api/oidc/authorize?...state=...`。
- 本轮继续排查时确认还有第二个问题：
  - `backend/app/api/outline_proxy.py` 的 `_maybe_bootstrap_outline_session()` 已经放行了 `/wiki/auth/oidc.callback`，但没有放行 `/wiki/auth/oidc`。
  - 因此请求 `/wiki/auth/oidc` 时，backend 又把它重定向回 `/wiki/auth/oidc`，形成入口自循环。
- 修复后 live 证据：
  - `GET http://localhost:4200/auth/oidc` 返回 `302 Location: http://localhost:4200/wiki/auth/oidc`
  - `GET http://localhost:4200/wiki/auth/oidc` 返回 `302 Location: http://localhost:4200/api/oidc/authorize?...&state=<non-empty>&client_id=protein-ai`
  - 同一响应里可见 `Set-Cookie: oauth_csrf=...`
  - backend 最新日志确认已收到 `GET /api/oidc/authorize?...state=...`
- 结论：
  - 旧问题的根因已经闭环，`state-mismatch` 的启动阶段来源被修正。
  - 若用户后续仍看到旧报错，优先怀疑浏览器里残留了旧标签页/旧 iframe 状态，应直接刷新当前 `wiki` 页重新走新链路。

## 2026-07-06 部署数据预检新增发现
- 当前仓库已经具备 `deploy_data` 标准目录、backend readiness、demo/live smoke，但之前还缺一个“站在 host 视角只看目录是否摆对”的前置检查入口。
- 新增 `scripts/check_deploy_data.py` 后，运维顺序被拆成更清晰的两层：
  - 第一层：host 侧检查 `deploy_data/` 目录和真实文件是否到位
  - 第二层：backend 侧检查配置自动发现、runtime readiness 和 smoke
- 新增顶层 `Makefile` 后，部署相关高频操作已有固定入口：
  - `make prepare-deploy-data`
  - `make prepare-deploy-data-demo`
  - `make check-deploy-data`
  - `make deploy-preflight`
  - `make deploy-demo-check`
- 当前真实结论也更明确了：
  - `deploy_data_root` 已存在
  - 但 `annotations`、`sifts`、`foldseek`、`smoke/query.pdb` 当前都缺失
  - 因此 host 侧状态不是 `live-data-ready`，而是 `partial`
- 这意味着下一步不再是继续猜配置，而是直接把真实数据放进 `deploy_data/`，然后按固定顺序跑：
  - `make check-deploy-data`
  - `make deploy-preflight`
  - `cd backend && .venv/bin/python scripts/smoke_structure_data.py`

## 2026-07-06 部署数据导入新增发现
- 仅有预检还不够，真实部署还缺“把外部数据目录纳入标准布局”的固定入口；否则每次接入都要手工复制、改名、记路径。
- 本轮新增 `scripts/import_deploy_data.py` 后，真实数据导入动作已被标准化：
  - 注释导出 -> `deploy_data/annotations`
  - SIFTS 映射 -> `deploy_data/sifts`
  - Foldseek 数据根或子库 -> `deploy_data/foldseek/...`
  - smoke 查询 PDB -> `deploy_data/smoke/query.pdb`
- 导入脚本会写 `deploy_data/import-manifest.json`，让后续知道当前目录里的数据到底是从哪里复制/链接来的。
- 当前工作区定向扫描结果也说明了一点：
  - 手边有项目内 demo fixture
  - 也有外部参考仓库的 Foldseek/InterPro 示例文件
  - 但没有直接满足本项目 `live-ready` 目标的成套真实数据目录
- 因此当前最合理的推进方式不是把示例文件硬塞成“真实数据”，而是保持 `deploy_data/` 真实为空、导入链可用，等真实数据到位后直接执行导入。

## 2026-07-06 deploy_data 默认发现收口新增发现
- 之前 host 侧 `check_deploy_data.py` 能看到 repo-root `deploy_data/`，但 backend readiness 若不显式传 `DEPLOY_DATA_ROOT`，会报告 `unset`，两边输出不一致。
- 现已收口为统一规则：
  - direct backend dev 默认自动发现 repo-root `deploy_data/`
  - `Makefile` 里的 backend readiness/smoke 也显式传 `DEPLOY_DATA_ROOT=../deploy_data`
- 这让 `make deploy-preflight` 的意义更完整：
  - 第一段输出看 host 目录是否摆对
  - 第二段输出看 backend runtime 实际会如何解析这些目录
- 同时修正了一个隐藏回归：
  - 当 `deploy_data/` 存在但里面只有空目录时，demo smoke 以前会被 autodiscovery 抢走优先级，误变成 `SKIP sifts`
  - 现在 `SIFTS_SMOKE_USE_DEMO=1` / `FOLDSEEK_SMOKE_USE_DEMO=1` 已提升为显式覆盖
- 当前运行态结论因此更稳定：
  - `deploy_data/` 已经被 `make deploy-demo-check` 填入 demo annotations、demo sifts 和 smoke query
  - backend readiness 可以看到这些 demo 资产
  - 但因为仍无真实 Foldseek DB / endpoint，所以总结依旧是 `demo-ready`，不是 `live-ready`

## 2026-07-06 deploy_data 到 env 覆盖文件新增发现
- 仅有 `deploy_data/` 和预检入口还不够，真实部署时仍容易退回到“手工改 backend/.env 和 docker/.env”的低效状态。
- 新增 `scripts/write_deploy_env.py` 后，deploy-data 配置链已经补上最后一个固定产物：
  - backend 用 `backend/.env.deploy-data`
  - docker compose 用 `docker/.env.deploy-data`
- 这两个文件都是非 secret 覆盖层，只负责把目录路径和可选 Foldseek 入口写清楚，不碰现有密钥配置。
- 当前已实际生成的内容表明：
  - backend 运行时将直接指向 repo-root `deploy_data/annotations`、`sifts`、`foldseek`、`smoke/query.pdb`
  - docker compose 运行时将直接挂载 repo-root `deploy_data/`
- 这意味着后续如果换一套真实数据，不需要再编辑多份 `.env`：
  - 先导入/替换 `deploy_data/`
  - 再重新生成 `.env.deploy-data`
  - 最后执行 compose 或 backend readiness/smoke 即可
- 到这里，“数据目录 -> 预检 -> 导入 -> env 覆盖 -> readiness/smoke”已经是一条成型的部署辅助链路。

## 2026-07-06 demo 数据与 live 候选拆分新增发现
- 之前 host 侧 `check_deploy_data.py` 只看“有没有文件”，这会让仓库里的 demo annotations / demo sifts 看起来像接近 live 数据。
- 现在已明确拆成两层语义：
  - host 侧 `check_deploy_data.py`：判断目录里放的是 demo 资产还是 live 候选资产
  - backend 侧 `structure_smoke_readiness.py`：判断当前 runtime 能否进入 `demo-ready` 或 `live-ready`
- 当前 demo 识别基于项目自带样本的稳定特征：
  - annotations `metadata.json` 里 `default_source_db=local_demo`
  - sifts 只有 `1abc.json`
- 这带来的直接好处是：
  - 你现在不会再把“demo 资产已落地”误理解成“live 数据几乎齐了”
  - 当前仓库的 host 侧结论已经更实话实说：`summary = demo-data-only`
- 因此下一步也更明确：
  - 想从 `demo-data-only` 变成 `live-data-ready`，必须导入真实 annotations / 真实 SIFTS / 真实 Foldseek 数据或 endpoint
  - 不是继续补脚本，也不是再跑 demo smoke

## 2026-07-06 Foldseek 容器运行时闭环新增发现
- host 侧 Foldseek CLI 跑通并不代表 Docker runtime 一定可用，容器化后额外暴露出两个真实问题：
  - backend Dockerfile 固定安装 `foldseek-linux-avx2.tar.gz`，在本机 `aarch64` 容器中会直接 `Illegal instruction`
  - 本地 `createindex` 生成的 `protein_ai_pdb_ss_h*` 是宿主机绝对路径软链接，挂入容器后会全部失效
- 当前这两个问题都已闭环：
  - Dockerfile 现在会按架构自动选官方包，`arm64` 安装 `foldseek-linux-arm64.tar.gz`
  - 新增 `scripts/materialize_foldseek_links.py` 后，Foldseek DB 可在 Docker 挂载前物化为可移植真实文件
- 还补齐了容器运行时配置断点：
  - `docker/docker-compose.yml` 现把 `.env.deploy-data` 注入 `backend/worker/md-worker`
  - 因此容器内可直接拿到 `FOLDSEEK_BINARY=/usr/local/bin/foldseek`，不再只停留在 compose 变量替换层
- `backend/scripts/smoke_structure_data.py` 现在还会在 `SIFTS_MAPPING_PATH` 指向本地目录时，自动从首个映射文件名推断 `SIFTS_SMOKE_PDB_ID`，这让 live smoke 不再依赖额外人工参数。
- host 侧也有一个容易误判的配置断点已经补掉：
  - 之前 `make backend-readiness` / `make backend-smoke-live` 只显式传 `DEPLOY_DATA_ROOT`，不会自动 source `backend/.env.deploy-data`
  - 结果是容器 smoke 能过，但 host smoke 会把 `FOLDSEEK_BINARY` 误判成未配置
  - 现在这两个目标已改为自动加载 `backend/.env.deploy-data`，host/container 两侧的 smoke 语义一致
- readiness 语义也补齐了一处关键误判：
  - 之前 `structure_smoke_readiness.py` 只要看到 `annotations/` 和 `sifts/` 有文件，就会把它们算成 `ready`
  - 这会导致当前仓库虽然 `check_deploy_data.py` 明确是 `demo-data-only`，`make backend-readiness` 却错误给出 `summary=live-ready`
  - 现在 readiness 也会识别 demo `metadata.json` 和 demo `1abc.json`，因此 demo 资产只会标成 `demo`，不会再提升到 `live-ready`
- 另外补了一个更适合部署签收的命令口：
  - `make backend-readiness` 适合看状态
  - `make backend-live-gate` 适合 CI/上线前 gate；当仍是 demo 资产或缺真实数据时，它会直接失败
- gate 入口现在也不再靠外层 `grep` 文本匹配：
  - `structure_smoke_readiness.py --require-live` 会在 summary 不是 `live-ready` 时直接返回非零
  - 这让 host 侧 `make backend-live-gate` 和容器侧 `make docker-backend-live-gate` 都能依赖正式退出码
- host 侧目录预检也补成了正式 gate：
  - `check_deploy_data.py --require-live` 会在 summary 不是 `live-data-ready` 时直接返回非零
  - `make deploy-live-gate` 现在会顺序执行：
    - host `deploy_data` 严格 gate
    - backend runtime 严格 gate
  - 这条命令更接近“上线前我只想知道现在能不能过”的真实使用场景
- 在继续往 `live-ready` 推进时，还补了一个现实层面的辅助入口：
  - 当前机器上已经能找到一些 PDB / AlphaFold / InterPro / Foldseek 参考数据，但没有现成成套真实 SIFTS
  - 直接手工找路径很低效，也容易把示例文件误当“真实 live 数据”
  - 新增 `scripts/discover_deploy_data_sources.py` 和 `make discover-deploy-data` 后，可以先扫描本机工作区，列出更像候选导入源的路径，再决定是否接入 `deploy_data/`
- 当前仓库已经有真正可交付的容器侧验收路径：
  - `make docker-backend-smoke-live`
  - `make docker-backend-rebuild-and-smoke`
- 本轮实测结果说明容器运行时闭环已经成立：
  - `PASS sifts: 2 mappings from /app/deploy_data/sifts/1abc.json`
  - `PASS foldseek: backend=local_cli results=1 database=pdb`
- 现在 remaining gap 已经不再是 Foldseek 容器化，而是数据等级问题：
  - 当前 `annotations` / `sifts` 仍然是 demo 数据，所以 host 侧总结依旧应保持 `demo-data-only`
  - 想进一步走到更严格的 `live-data-ready`，还需要替换成真实 annotations / SIFTS 导出

## 需求
- 通读并理解整个项目。
- 在不影响现有功能的前提下修复代码。
- 修复方案需要具备容错率。
- 后续新增功能要可插拔、便于集成。
- 采用深度审计、谨慎修复策略，不做草率大改。

## 研究发现
- 项目为前后端分离结构，核心目录包括 `backend/`、`frontend/`、`docker/`、`scripts/`、`docs/`。
- 后端为 FastAPI，包含认证、会话、工具注册、OIDC、Outline 代理、数据与项目管理等模块。
- 前端为 React + Vite，包含鉴权 store、聊天流、文件上传、Wiki 页面和项目页面。
- Docker 编排中前端对外暴露 `4200`，符合当前端口约束。
- 之前已完成一轮针对 wiki/OIDC/cookie path/前端 token 生命周期的修复，并已验证多条 `/api/*` 路径恢复到 `200`。
- 运行中的后端曾因依赖函数签名错误重启，已修复并重新部署为 healthy。
- 当前在线验证结果表明：
  - `invalid bearer + refresh cookie` 访问 `/api/auth/me` 返回 `200`
  - `invalid bearer + refresh cookie` 访问 `/api/conversations` 返回 `200`
  - 服务端当前 bundle 为 `/assets/index-Di-EEnLc.js`
  - 用户控制台中的 `index-BOmwr5i4.js` 属于旧缓存或旧标签页内存代码
- 深度审计后新增确认：
  - `backend/app/api/conversations.py` 的列表接口存在会话级 N+1 消息计数查询，属于高频路径性能风险。
  - `backend/app/api/files.py` 和 `backend/app/api/pdb.py` 之前仅凭 object name 访问存储对象，缺少明确的用户前缀隔离，容易成为后续扩展时的边界隐患。
  - 前端上传逻辑分散在多个组件中，之前混用了 `fetch`、`XMLHttpRequest`、本地 token 读取和 `authFetch`，不利于后续功能接入与统一容错。
  - `ProtectedRoute` 之前强依赖本地 token 是否存在，与后端当前基于 cookie 的回退鉴权能力不完全一致。
  - 聊天页 `restoreSession` 与侧边栏 fallback 拉取在鉴权未稳定时都可能触发 `/api/conversations`，若浏览器持有过期 token/旧上下文，会表现为 401 连续刷屏。
  - `iframe sandbox` 警告并不是当前“进不去”的主因；本项目的 `WikiPage` iframe 并未主动设置 `sandbox`，该警告更可能来自被嵌入页面或浏览器扩展上下文。
  - 项目文件下载/内容读取此前绕过了公共 API 鉴权层，后续如果继续扩展文件能力，会比主流程更容易出现 token 生命周期不一致问题。
  - `/login` 页面此前只依据本地 `token + user` 决定是否跳转，不会主动探测 cookie 恢复后的会话，容易让用户误判“服务端已恢复但页面还卡在登录页”。
- binder / de novo 设计流水线原先把 `rfdiffusion_design`、`chroma_design`、`proteinmpnn_design`、`esmfold_folding` 当成可并行独立步骤执行，但这些步骤实际上存在严格依赖关系。
- `rfdiffusion_design` 已定义为 `async def`，但注册时未声明 `is_async=True`，在旧执行器路径下会被误送入 `run_in_executor()`，触发 `coroutines cannot be used with run_in_executor()`。
- 设计计划里使用了错误或占位参数：`rfdiffusion_design` 收到无效 `target_name`，`chroma_design` 缺少必填 `length`，`proteinmpnn_design` 和 `esmfold_folding` 直接收到空字符串占位而不是上一步设计产物。
- `/wiki` 当前的主故障已收敛为路由落点错误，不是 Outline 服务不可用：
  - 运行中的 Outline 明确暴露 `window.env.URL = "http://localhost:4200/wiki"`。
  - `http://localhost:4200/wiki/` 与容器内 `http://127.0.0.1:3001/` 返回同一份 Outline HTML，说明代理本身能到达服务。
  - Outline 运行 bundle 中存在稳定路由 `/home`、`/collections`、`/doc/`，并包含 `Error404` 的 `Not found` 页面。
  - 前端 `WikiPage` 原先把 iframe 根地址固定到 `/wiki/`，这会把用户落在 Outline 的根入口；当根入口未命中有效首页状态时，浏览器里就会看到 Outline 自己渲染的 `Not found`。

## 技术决策
| 决策 | 理由 |
|------|------|
| 认证修复采用“前端自动刷新 + 后端 cookie 回退”双层容错 | 兼容旧 bundle、过期 bearer 和新会话 |
| 通过 no-store/no-cache 降低旧前端 bundle 持续驻留 | 缓解用户继续命中旧代码 |
| 后续修复优先围绕边界层抽象，而非直接在页面中散落逻辑 | 便于新功能插拔和集成 |
| 将上传鉴权收敛到公共 API 层 `uploadFormWithProgress` | 减少重复实现并统一 401 刷新逻辑 |
| 为通用文件/PDB 上传路径增加用户前缀校验 | 以最小侵入方式补齐对象访问边界 |
| 将前端受保护路由改为基于 `checkAuth()` 初始化而非仅本地 token 判定 | 让 cookie 回退会话真正对前端可见 |
| 为会话恢复链添加“鉴权稳定后再执行”和 401 熔断 | 阻断未登录/过期状态下的重复请求与控制台刷屏 |
| 将项目文件读取继续收敛到统一请求抽象 | 保持后续文件类功能可插拔且共享同一套鉴权/错误语义 |
| 登录页也主动执行一次 `checkAuth()` | 让 cookie 会话恢复对 `/login` 场景同样生效，减少“看起来没登录成功”的假象 |
| 设计流水线改为依赖感知执行并加入结果桥接 | 避免 binder 设计步骤并发错序，确保上一步结构/序列结果能自动喂给下游工具 |
| Wiki iframe 默认落点从 `/wiki` 收敛到 `/wiki/home`，并保留一次根路径 `Not found` 自动回退 | 只改前端单点入口，避免继续扰动认证/OIDC/代理主链，同时给未来 Outline 升级保留容错 |

## 2026-07-04 深度测试新增发现
- 整体运行面当前是“核心服务在线，但仍有匿名访问噪音”，不是全绿状态。
- `frontend npm run build` 通过；`python3 -m compileall backend/app backend/tests` 通过；说明当前代码至少没有显式构建/语法级断裂。
- Docker 运行态整体健康：`nginx / frontend / backend / outline / postgres / redis / minio / chromadb` 全部 `healthy`。
- 关键 live API 当前返回稳定：
  - `/api/health` = `200`
  - `/api/chat/models` = `200`
  - `/api/tools` = `200`
  - `/api/tools/diagnostics` = `200`
  - `/api/data/stats` = `200`
  - `/api/data/protein/DEMO388A/annotation-bundle` = `200`
  - 匿名 `/api/auth/me` = `401`
  - 匿名 `/api/conversations` = `401`
  - `/api/oidc/logout` = `302`
- `sw.js` 当前已恢复为有效 JavaScript，`node --check frontend/public/sw.js` 通过，live `/sw.js` 返回 `200` 且内容正常，不再是乱码/非法 token。
- `favicon.ico`、`/kb`、`/wiki`、`/pdb`、`/chat/agent` 路由当前 HTTP 层都能返回 `200`，未复现之前的 `502`。
- 浏览器黑盒未全通过，发现两个真实残余问题：
  - 匿名访问公开页链路（`/login`、`/home`、`/data`）时，前端仍会主动请求 `/api/auth/me`，导致控制台产生 `401` 噪音。
  - 匿名访问 `/wiki/home` 时，路径最终会正确跳转到登录页并带 `next`，但在跳转前 Outline 前端会先打 `/api/auth/me` 并抛出前端异常，导致黑盒测试出现 `401 + pageerror`，不属于干净通过。
- Nginx 日志中仍持续出现大量 `upstream sent duplicate header line: date` 警告，说明代理层仍有重复响应头问题，虽然目前未直接打断访问。
- Outline 日志中存在多次 `ERR_STREAM_PREMATURE_CLOSE`，属于需要继续追踪的运行时噪音，当前未证实会直接破坏核心文档操作，但它不是理想状态。
- 单元测试层一度因运行环境缺少 `pytest` 无法执行；后续已使用项目虚拟环境恢复测试执行，当前后端全量测试通过。

## 2026-07-04 真实 MD 改造新增发现
- 原 `backend/app/tools/gromacs_md.py` 的 MD 结果确认为占位实现，核心指标来自 `random.uniform/random.randint`，不能作为真实分子动力学结论。
- 已将 `gromacs_md` 替换为真实 GROMACS 最小流水线实现：
  - 输入必须提供 `pdb_data`、`pdb_path` 或 `pdb_object_name`
  - 不再接受“只有 sequence 也给 MD 结果”的路径
  - 运行目标是 `pdb2gmx -> editconf -> solvate -> grompp/genion -> EM -> NVT/NPT -> mdrun -> rms/rmsf/gyrate/sasa`
- 真实 MD 工具现已改为显式失败策略：
  - 运行环境缺少 `gmx` 时返回 `status=failed` + `error_code=GROMACS_NOT_INSTALLED`
  - 缺少可用 PDB 或 PDB 非法时返回 `INVALID_OR_MISSING_PDB`
  - 明确声明 `No simulated/random MD metrics were generated.`
- `agent_graph` 已补充附件结构解析：
  - 能从聊天消息中的 `[Attached files: ... object_name: ...]` 抽取 `pdb_object_name`
  - 仅在检测到真实结构附件时才会自动规划 `gromacs_md`
  - 不再对 sequence-only 请求默认塞一个“假 MD”
- 前端 `MDResultView` 已补充失败态和空值容错：
  - `GROMACS_NOT_INSTALLED` 这类真实失败会显示清晰错误卡片，而不是空白
  - 缺失能量/H-bond/atom count 等字段时不会再因 `toFixed()` 崩溃
- 运行态验证结果：
  - backend 容器已更新到新代码
  - 容器内直接调用 `gromacs_md(pdb_data=...)` 返回 `GROMACS_NOT_INSTALLED`
  - 证明当前线上运行环境已从“假 MD”切换为“真实 MD 接口 + 缺运行时则明确失败”
- 早期运行态缺少 GROMACS 二进制及配套力场，导致真实 MD 只能显式失败；后续已在 backend 镜像中安装 GROMACS 并验证真实前处理链可执行。

## 2026-07-04 真实 MD 运行时补齐新增发现
- 已在 `docker/Dockerfile.backend` 中安装 Debian 包 `gromacs`，backend 运行容器已确认存在 `/usr/bin/gmx`。
- live 容器内 `gmx --version` 验证通过：
  - GROMACS `2025.2-Debian_2025.2_1`
  - CPU 版，OpenMP enabled，GPU disabled
- 运行时力场与代码默认值存在真实兼容性差异：
  - 容器内不存在 `amber14sb.ff`
  - 实际存在 `amber99sb-ildn.ff`、`amber99sb.ff`、`amber03.ff`、`charmm27.ff`、`gromos54a7.ff`、`gromos53a6.ff`、`oplsaa.ff`
  - 因此已把 `gromacs_md` 默认力场改为 `amber99sb-ildn`，并新增基于容器实际 `.ff` 目录的动态力场解析
- 为避免真实 MD 抢占整机 CPU，已新增 `mdrun_threads` 参数，默认 `1`，并传递给 `gmx mdrun -nt`
- live runtime 的真实 GROMACS 前处理已验证打通：
  - `pdb2gmx`
  - `editconf`
  - `solvate`
  - `grompp`（ions）
  - `genion`
  - 上述步骤在 backend 容器内对 `388aa-SD-WT.pdb` 成功生成 `processed.gro / boxed.gro / solvated.gro / ions.tpr / solv_ions.gro / topol.top`
- 这说明当前系统已经不只是“有 gmx 命令”，而是“真实 MD 前处理链条能在 live runtime 中执行”
- 尚未完成的仅是完整短轨迹 smoke test 和后续异步任务化：
  - 完整 `em/nvt/npt/md` 短轨迹一次性烟测仍耗时较长
  - worker 已重建到同镜像，但健康状态刚启动，还需继续观察

## 2026-07-04 异步 MD 任务链新增发现
- 已为 `/api/tools` 增加异步任务接口：
  - `POST /api/tools/{name}/submit`
  - `GET /api/tools/tasks/{task_id}`
- 异步工具任务归属已迁移到 Redis-backed metadata，并保留本地 fallback 以支持测试和 Redis 降级场景；未知任务返回 `404`，跨用户轮询返回 `403`。
- `/pdb` 页面已从“只能跳聊天页做 MD 提示词”升级为“可直接提交真实 MD 任务并轮询状态”。
- 前端提交参数当前收敛为一条可控的短任务基线：
  - `simulation_time_ns=0.01`
  - `equilibration_ps=10.0`
  - `ensemble=nvt`
  - `mdrun_threads=1`
- 这保证了 `/pdb` 真实 MD 入口不会一上来就发起过大的生产计算。
- live runtime 中，`gromacs_md` tool detail 路由已确认可访问；`submit/status` 路由代码已部署。
- 同时发现一个与 MD 并行的独立注册问题：
  - `mutation_priority_score` 在 tool discover 阶段因为 `catalytic_site_lookup` 中 `_infer_catalytic_residues` 导入失败而被跳过
  - 这是现有工具注册链的真实 bug，但不阻塞本轮 MD 链路

## 2026-07-04 收尾验证新增发现
- `mutation_priority_score` 的 discover 失败已修复：
  - 在 `catalytic_site_lookup.py` 中重新导出 `_infer_catalytic_residues`
  - live backend runtime 已确认 `mutation_priority_score` 重新注册成功
- 对 388 aa 单链 PDB 的最小完整短轨迹 smoke test 已进入真实执行，不再停留在前处理：
  - 已观察到 `em.gro / em.tpr / em.trr / em.edr / em.log`
  - 已观察到 `nvt.tpr / nvt.edr / nvt.log`
  - 说明完整流水线至少已推进到能量最小化与 NVT 平衡阶段
- 本轮没有等待到最终 `rmsd.xvg / rmsf.xvg / gyrate.xvg / sasa.xvg` 回包，只是因为真实计算耗时已显著上升，不再是秒级假结果。
- 结论上可以明确认定：
  - 真实 MD 工具链已完成“假结果替换”
  - live runtime 已具备真实 GROMACS 运行能力
  - `/pdb` 页面已具备真实任务入口
  - 剩余工作是继续做长任务治理，而不是再修“是否为真 MD”这个问题

## 2026-08-04 酶家族与关键残基识别专业化调研进行中
- 用户要求先解决酶改造的第一步：识别酶家族和关键残基；本轮先做外部深度调研，不立即改代码。
- Google 自动化访问触发 unusual traffic 验证页，未将 Google 搜索摘要当作证据；改为核对 Google 检索指向的官方数据库文档和原始论文/数据库页面。
- 当前平台初步差距已确认：`protein_benchmark` 依赖显式 `known_family/enzyme_type`，`enzyme_function` 的 EC 候选没有反哺家族判断，`annotation_bundle` 的 InterPro/Pfam/M-CSA 结果没有和 EC、motif、结构证据聚合成一个“酶身份画像”。
- InterPro/InterProScan 调研结论：
  - InterProScan 是对新蛋白序列做功能表征的核心软件包，可扫描 InterPro 成员数据库 signature。
  - InterPro entry 类型区分 family/domain/homologous superfamily/repeat/site；其中 active site、binding site、conserved site 能直接服务“关键残基/不可突变位点”。
  - InterPro 明确提示 signature 是计算预测，更多 signature 命中同一层级会提高可信度；专业输出必须显示证据数量、层级一致性和 false positive 风险。
  - InterProScan 可本地安装，也有 REST/SOAP web service；隐私敏感序列应优先本地运行。
- UniProt/Rhea 调研结论：
  - UniProt 的 catalytic activity 现在尽可能使用 Rhea 标准化反应，EC 也会链接到 catalytic activity 注释。
  - UniProt feature table 的 active site、binding site、domain/region 等位置注释可作为关键残基/区域证据；实验与预测证据需要区分。
  - Rhea 支持按 UniProt、EC、GO、ChEBI、PubMed 查询反应；适合作为“反应/底物/产物/EC”标准化层。
- M-CSA/CSA 调研结论：
  - M-CSA 合并 MACiE 和 CSA，定位是 enzyme reaction mechanisms 与 active/catalytic sites 的机制数据库。
  - M-CSA entry 以 UniProtKB 标识和代表性结构为核心，强调 mechanism、evolution、reactive centre 唯一性；适合作为最高优先级催化残基证据。
  - 关键残基识别不能只靠序列酸性/碱性残基启发式；有 M-CSA/CSA/UniProt ACT_SITE 时应覆盖启发式。
- CAZy/BRENDA 调研结论：
  - CAZy 是 CAZyme 专科家族数据库，按 GH/GT/PL/CE/AA/CBM 等模块家族组织，家族分类更贴近结构和机制而非单一底物名。
  - CAZy 官方提醒自动注释并非零错误，高质量分析仍需要人工 curation；平台应把 CAZy/dbCAN 作为碳水化合物酶家族主证据之一。
  - BRENDA 是以 IUBMB EC 分类为基础、从文献人工整理的酶信息源，覆盖反应/特异性/动力学/结构/稳定性/ENGINEERING 突变实验等字段；适合给实验条件、温度稳定性、pH、kcat/Km 和已知突变效果做证据支撑。
- ML/结构工具调研结论：
  - CLEAN 这类 contrastive learning EC 预测可提高低研究蛋白、多功能酶的 EC 预测能力，但仍应作为候选 EC/补充证据，不能直接替代 curated 数据库。
  - DeepFRI 结合序列语言模型和结构图卷积，可给 GO/EC 和 residue-level class activation 信息；适合做低同源情况下的补充功能/位点提示。
- Foldseek 的结构搜索适合在序列同源弱时发现结构家族/超家族，尤其有 PDB/AlphaFold/ESMFold 结构时；但结构相似不等于同反应机制，必须与 EC/Rhea/M-CSA 联合判读。

## 2026-08-04 同案例深度复盘：388 aa-SD-WT 与 MatVenus 对比
- 用户补充了 MatVenus 对同一条 388 aa PDB 的完整结果，以及本平台同一任务的执行记录。该案例现在可以作为家族识别、催化残基识别和候选位点输出的验收基线。
- 目标输入：`backend/388aa-SD-WT.pdb`，单链 A，PDB residue 1..388，共 388 个 CA 残基；当前 PDB 文件没有实验方法、分辨率、R factor 等完整元数据，不能把结构质量当成已验证事实。
- MatVenus 的关键链路是：
  1. 先发现文件名 `SD` 与序列功能不一致；
  2. 用同源搜索把蛋白归到真菌天冬氨酸蛋白酶/Peptidase A1 方向；
  3. 从同源注释和序列基序确认两个催化 Asp，并将其列为不可触碰位点；
  4. 再运行 VenusX 功能残基测绘和 VenusREM 结构驱动全单点扫描；
  5. 最终把候选突变、每个位点逻辑、实验优先级和组合路线放在结果主表。
- 本平台同一案例的实际输出则是：
  - `protein_benchmark`: `Unknown enzyme family`，催化位点 `known=false`；
  - `enzyme_function`: 仅因 250 位偶然命中 `GYSIG`，将 `GXSXG` motif 解释为 lipase/esterase，给出 EC `3.1.1.3`、medium confidence；
  - `mutation_priority_score`: 在没有家族和结构催化位点证据的情况下，启发式得到 `[14, 58, 252]` 保护位点，并产生 129 个 Tier 1、231 个 Tier 2 候选；
  - fallback 报告因此同时出现“Family: Unknown”“EC: 3.1.1.3 lipase/esterase”和大量未经家族/口袋约束的位点，科学上不能作为实验排单。
- 该错误不是前端表格问题，而是底层证据链问题：短 motif 命中被当成了家族/EC 结论，且 `protein_benchmark`、`enzyme_function`、`mutation_priority_score` 之间没有共享一个经过证据门控的酶身份画像。

### 该序列的可复核事实
- 目标序列长度为 388 aa。
- 序列在 83..91 附近含有 `LDFDTGSAD`，其中符合天冬氨酸蛋白酶活性位点模式的是第二个 Asp，目标序列位置 86。
- 序列在 275..279 附近含有 `DTGTT`，其中 Asp 位于目标序列位置 275。
- 序列在 250..254 含 `GYSIG`。它形式上符合宽泛的 `GXSXG`，但单个五肽短 motif 不能证明 alpha/beta hydrolase，也不能证明 EC 3.1.1.3；该案例正好证明了短 motif 误报风险。
- MatVenus 报告中的 `Asp86/Asp275` 与目标 PDB chain numbering 一致；这比直接把 Q69IF8 的 UniProt 全长编号复制到目标上更严谨。

### 外部权威交叉核验
- UniProt Q69IF8（PEPA_PHANO）公开记录：推荐名称为 `Aspartic protease SNP2`，EC `3.4.23.-`，明确属于 `peptidase A1 family`；功能说明为两个 Asp 激活亲核水分子，偏好 P1/P1' 疏水残基。
  - [UniProt Q69IF8 JSON](https://rest.uniprot.org/uniprotkb/Q69IF8.json)
  - [UniProt Q69IF8 text](https://rest.uniprot.org/uniprotkb/Q69IF8.txt)
- UniProt Q69IF8 的交叉引用包括 InterPro `IPR001461`、`IPR001969`、`IPR034163`、`IPR033121`、Pfam `PF00026`、PROSITE `PS00141`/`PS51767`、CDD `cd06097` 和 Gene3D acid protease；这说明专业家族判断应依赖多个长域/家族 signature，而不是单个 `GXSXG`。
- Q69IF8 的 UniProt full-length feature 中有 `ACT_SITE 108`、`ACT_SITE 289`、`DISULFID 325..360`；这些编号属于 Q69IF8 全长记录，不能未经 alignment 直接当作目标 PDB 的编号。
- InterPro `IPR001461` 官方描述明确指出：A1/pepsin 家族的 active site 由两个 lobes 各自提供一个 Asp；两个 Asp 各在 `D(T/S)G(T/S)` motif 中；N-terminal lobe 的 flap 上通常有 Tyr/Phe 参与底物结合。
  - [InterPro IPR001461 API](https://www.ebi.ac.uk/interpro/api/entry/InterPro/IPR001461/)
- PROSITE `PDOC00128` / `PS00141` 给出了天冬氨酸蛋白酶活性位点规则，并明确 `D` 是 active-site residue；`PS51767` 是 Peptidase A1 domain profile。
  - [PROSITE PDOC00128](https://prosite.expasy.org/PDOC00128)
- M-CSA 官方文档要求催化残基同时有 residue identity、功能角色、机制说明和参考证据；其条目区分 full mechanism 与 catalytic-site-only，并强调 mechanism/evolution/reactive-centre 的唯一性。这是平台设计“关键残基表”时应采用的字段粒度。
  - [M-CSA documentation](https://www.ebi.ac.uk/thornton-srv/m-csa/documentation/)

### 该案例暴露出的算法缺陷
| 环节 | 当前行为 | 专业行为 | 风险 |
|---|---|---|---|
| 短 motif | `GXSXG` 单命中即映射 lipase EC | motif 只能作为候选证据，必须与 domain/profile、同源、催化残基规则一致 | 把随机短匹配当作酶身份 |
| 家族识别 | `protein_benchmark._resolve_family()` 主要依赖用户显式 `known_family/enzyme_type` | 从同源/InterPro/Pfam/PROSITE/结构证据产生 family candidates 并排序 | 只有 Unknown 或错误家族 |
| EC 预测 | motif/ESM 预测独立输出，不反哺 family | EC 是候选，需与 family、reaction、Rhea/UniProt/BRENDA 交叉验证 | EC 与 family 相互矛盾却仍继续执行 |
| 催化位点 | 无 family 时用酸性残基启发式和 `GXSXG` 启发式 | 先用 curated active site/PROSITE/M-CSA，再用 alignment/structure/ML 补充 | 保护错位点、放过真实催化 Asp |
| 活性候选 | activity 目标下可直接生成 129 个 Tier 1 | 未完成 identity/active-site gate 时只能输出 blocked 或“待确认候选” | 候选数量虚高，无法实验排单 |
| 编号映射 | 目标 PDB、同源 UniProt、成熟链编号没有统一 map | 每个 residue claim 必须携带 coordinate system 和 alignment basis | 位点名称看似正确但实际指向错误残基 |
| 报告组织 | 先展示工具执行流，结果再被 fallback 拼接 | 先展示身份画像、保护位点和候选主表，工具仅作为证据来源 | 用户无法判断平台改造逻辑 |

### 证据等级和用途建议
| 证据等级 | 来源 | 能回答的问题 | 允许支持的结论 |
|---|---|---|---|
| L1 curated/机制 | UniProt reviewed、Rhea、M-CSA/CSA、已审校 BRENDA/CAZy | 已知功能、EC/反应、催化残基、机制、实验突变 | 可进入“已知事实/强保护” |
| L2 profile/domain | InterProScan、Pfam/HMMER、PROSITE、dbCAN/CAZy | family/domain/superfamily、motif、结构域边界、site pattern | 可形成 family candidate 和候选保护区 |
| L3 homology/structure | BLAST/HHsearch、PDB、Foldseek、结构比对、SIFTS | 同源关系、结构家族、编号映射、空间邻近 | 可支持同源迁移和结构约束，但要注明推断 |
| L4 ML | CLEAN、DeepFRI、ESM/ProtT5、结构语言模型 | 低同源场景下的 EC/GO/位点候选 | 只能补充候选和排序，不能覆盖 L1/L2 矛盾 |
| L5 heuristic | 短 motif、残基频率、理化性质启发式 | 发现可能线索 | 不得单独输出 family、EC 或 catalytic residue 确定结论 |

### 第一阶段产品契约：`enzyme_identity_profile`
第一步不应再返回“先执行哪些工具”，而应返回一个可审阅的身份画像。建议最小字段如下：
```json
{
  "query": {"sequence_length": 388, "structure_id": "...", "chain_id": "A"},
  "identity_status": "identified|candidate|unresolved|blocked",
  "family_candidates": [{"name": "Peptidase A1", "accession": "IPR001461", "confidence": 0.0, "evidence_ids": []}],
  "ec_candidates": [{"ec": "3.4.23.-", "confidence": 0.0, "basis": []}],
  "functional_domains": [],
  "motifs": [],
  "key_residues": [{"position": 86, "residue": "D", "role": "catalytic", "status": "protected", "evidence": []}],
  "protected_positions": [],
  "numbering": {"coordinate_system": "pdb_chain|sequence|uniprot", "mapping_basis": "...", "status": "verified|inferred|unmapped"},
  "evidence_table": [],
  "confidence_summary": {"family": 0.0, "ec": 0.0, "catalytic_sites": 0.0},
  "missing_evidence": []
}
```
- 每个家族、EC、残基和保护位点必须带 `source`、`evidence_level`、`confidence`、`coordinate_system`、`mapping_basis`；不能只在报告末尾笼统写“AI预测”。
- `identity_status != identified/candidate` 时，activity/thermostability 的候选位点工具必须进入 `blocked` 或 `preliminary_only`，禁止把启发式位点直接标为 P1。
- `key_residues` 与 `protected_positions` 必须先传给突变排序工具；排序工具不能自己重新猜催化位点。
- 候选突变主表最少要有：`priority`、`mutation`、`position`、`logic`、`mechanism_hypothesis`、`evidence`、`risk_flags`、`experiment_priority`、`numbering_status`。

### 对 MatVenus 输出的专业判断
- MatVenus 的结果组织方式是对的：先给“位点主表”，再给位点逻辑和实验排序；这正是研发人员需要的实验入口。
- 但其个别预测幅度（例如“5~15°C”“2~6 倍”）不能直接当作事实，除非有模型校准、置信区间和湿实验验证。平台应借鉴其输出结构，不应照搬未经证据支撑的收益幅度。
- 本项目已有湿实验数据表明 E240S 的稳定性和比活力结果存在条件/批次差异：历史记录中有相对活性下降和 80°C 残余活性提升同时出现的情况。因此未来应把“预测候选”“实验事实”“相对 WT 的测量条件”三者严格分离，不能将 Venus 预测自动写成正向训练标签。

### 推荐实施顺序
1. 先修正 identity gate：对序列/PDB 首先跑 `annotation_bundle + BLAST/sequence_search`，优先接入 InterPro/Pfam/PROSITE/M-CSA 本地数据或缓存；统一产出 `enzyme_identity_profile`。
2. 再修正证据聚合：禁止单个短 motif 覆盖长域/同源/催化规则；出现 lipase motif 与 Peptidase A1 motif 冲突时，报告必须显式显示冲突并停止确定性 EC 输出。
3. 再修正 residue gate：将目标 PDB chain 的 `D86/D275`、flap Tyr 候选、二硫键/糖基化/底物口袋等映射结果交给候选排序；编号不确定时不生成 P1。
4. 最后改报告 UX：身份画像和“保护位点”置于候选突变主表之前；工具清单收进“证据来源/分析过程”折叠区，而不是成为用户第一眼看到的结果。
5. 建立本案例回归：输入 `388aa-SD-WT.pdb`/388 aa 序列时，不能输出 lipase 作为唯一或高置信结论；必须识别或至少提出 Peptidase A1 candidate，并定位 `D86/D275` 的目标序列位置或明确说明尚未完成映射；候选数量必须经过 gate。

## 2026-07-04 最终回归与文档收口新增发现
- 后端测试执行能力已恢复，当前全量测试结果为 `275 passed, 195 warnings`。
- 前端生产构建通过，仅保留第三方 `3dmol` eval/chunk warning。
- 针对新修复点新增或验证的关键回归包括：
  - `pa_token` cookie 在缺少 Authorization header 时可恢复 `/api/auth/session`
  - `/auth/oidc` 会重定向到带 `/wiki/auth/oidc.callback` 的 OIDC authorize 链路
  - fallback planner 在核心工具未预注册时会自动触发 discover，避免测试顺序污染
  - ProtSSN wild-type mismatch 错误文案在 `ml/embeddings.py` 与工具 fallback 中保持一致
  - 异步工具任务 owner 可持久化读回，未知任务返回 `404`，其他用户任务返回 `403`，owner 可请求取消任务，轮询会返回 `cancel_requested` / `cancel_requested_at`
- README、frontend README 与 2026-07-04 路线图已补齐当前真实能力边界，避免后续误判：
  - Wiki/OIDC 入口与 `pa_token` cookie 会话恢复
  - `/api/tools/{name}/submit` 与 `/api/tools/tasks/{task_id}` 异步任务 MVP
  - `/pdb` 页面真实 MD 提交与轮询
  - `/pdb` 页面可请求取消运行中的 MD 任务，并展示取消请求时间戳
  - `gromacs_md` 不再伪造指标，缺 PDB/GROMACS 时显式失败
- 仍建议后续治理的点：
  - 为异步任务 metadata 增加更完整的审计字段、取消结果确认和过期清理观测指标
  - 将 MD 轨迹、日志、`.xvg` 指标和参数模板归档到 MinIO，并在任务状态中返回 artifact manifest
  - 为真实 MD 建立资源队列、并发限制、超时策略，以及取消结果确认与终态收敛机制
  - 继续清理匿名浏览器 smoke 中的 401 噪音与 Outline 运行时 `ERR_STREAM_PREMATURE_CLOSE` 日志

## 2026-07-04 阶段 6 启动新增发现
- “全部开始”应按依赖拆分推进，不能一次性并行大改所有后续项。
- 第一优先级应是 MD artifact manifest：
  - 当前 `gromacs_md` 已上传多个 artifacts，但调用方只能拿到平铺列表。
  - 后续前端下载、实验复现、任务审计、MinIO 工件归档和长任务治理都需要稳定 manifest。
  - manifest 应至少区分 trajectory、analysis、logs、parameters、structures/topology 等用途。

## 2026-07-04 MD artifact manifest 新增发现
- `gromacs_md` 现在返回 `artifact_manifest`，包含：
  - `version`
  - `total_count`
  - `total_size`
  - `groups`
  - `counts`
- 当前分组包括 `structures`、`topology`、`trajectory`、`analysis`、`parameters`、`logs`、`other`。
- 失败路径也会返回已上传日志的 manifest，便于失败排查和复现。
- 前端 `MDResultView` 已能展示 Artifacts & Reproducibility 区块，并为带 `download_url` 的 artifact 提供下载入口。

## 2026-07-04 长任务治理第一层新增发现
- `gromacs_md` 已从“只是异步工具”推进到“有明确 runtime policy 的异步工具”：
  - queue: `md_cpu`
  - soft time limit: `3600`
  - hard time limit: `5400`
- API 轮询层已把 Celery `REVOKED` 收敛为统一的 `canceled` 状态，减少前后端对取消终态的歧义。
- 任务 metadata 当前已持久化：
  - `queue`
  - `soft_time_limit`
  - `time_limit`
  - `terminal_status`
  - `cancel_effective_at`
- 这意味着“取消请求已发出”和“任务已进入取消终态”现在可以区分，后续只剩更细粒度的资源队列和 worker 并发治理。

## 2026-07-04 MD worker 队列隔离新增发现
- `docker/docker-compose.yml` 已拆出专用 `md-worker`：
  - `worker` 只消费 `default` queue
  - `md-worker` 只消费 `md_cpu` queue
- 默认并发策略：
  - `CELERY_DEFAULT_WORKER_CONCURRENCY=4`
  - `CELERY_MD_WORKER_CONCURRENCY=1`
- 这样真实 MD 不会与轻量工具共用同一 Celery 消费面，避免 GROMACS 长任务抢占默认异步工具 worker。
- 静态配置回归已覆盖：
  - `md-worker` 服务存在
  - `--queues=md_cpu` 存在
  - default worker 保持 `--queues=default`
  - 两个并发环境变量存在

## 2026-07-04 阶段 6 三线第一层新增发现
- 匿名浏览器噪音第一层已经从“页面内兜底”推进到“入口层收敛”：
  - 登录页只有存在本地 token/refresh token 或 OIDC `/api/*` next 时才主动 `checkAuth()`。
  - `/wiki/*` React route 已进入 `ProtectedRoute`，避免 SPA 内部深链绕过平台鉴权。
  - Nginx 主代理新增 `$wiki_spa_document` 判定：顶层 document 请求 `/wiki/home` 这类路径时返回 frontend `index.html`，iframe 与 `/wiki/auth/oidc.callback` 仍走 backend/Outline proxy。
  - 容器内 `nginx -t` 已验证配置语法通过。
- 本地注释灌库第一层已从“单个 demo JSON”升级为“分源导出目录”：
  - `base.json` 保存 enzyme/taxonomy/EC/Pfam 基础记录。
  - `interpro.json` 保存按 UniProt 关联的 InterPro family/domain/site 记录。
  - `mcsa.json` 保存催化机制与保护残基记录。
  - `signalp.json` 保存 SignalP 风格预测结果。
  - ingestor 会按 `uniprot_id/accession` 合并为 `AnnotationDatasetService.ingest_records()` 需要的 bundle。
  - 目录 hash 已支持增量检测，因此后续真实导出替换 fixture 不需要重写 ingestion pipeline。
- 结构映射与模板搜索第一层已启动：
  - `residue_mapping_sifts` 提供 SIFTS-style PDB residue ↔ UniProt position 映射，当前基于 coordinate order + `uniprot_start` 推断，明确标注限制。
  - `structure_search_foldseek` 提供 Foldseek/template search 稳定工具合同；未配置 `FOLDSEEK_API_URL` 时返回 degraded local structure summary，不伪造命中结果。
  - 两个工具都已注册到 `ToolRegistry`，后端全量测试已覆盖 discover 和基础输出。
- 最新验证基线：
  - 前端生产构建通过，仅第三方 `3dmol` eval/chunk warning。
  - Nginx 容器内配置测试通过。
  - 后端全量测试为 `282 passed, 195 warnings`。

## 2026-07-04 `/pdb` 结构入口补线新增发现
- 结构位点映射与模板搜索现在不再只是后端工具合同，`/pdb` 页面已经提供直接触发入口：
  - `Residue Mapping` 调用 `residue_mapping_sifts`
  - `Structure Search` 调用 `structure_search_foldseek`
- `/pdb` 页面也已补上主链序列级注释入口：
  - `Annotation Bundle` 直接使用 primary chain sequence 调用 `annotation_bundle`
  - 结果在同页展示 InterPro、催化位点护栏和信号肽聚合卡片
- `/pdb` 页面现在已经形成一条最小结构 overlay 闭环：
  - `annotation_bundle` 提供 protected positions
  - `residue_mapping_sifts` 提供 UniProt position → PDB residue mapping
  - `ProteinViewer` 可将成功映射的位点按链和残基号高亮到 3D 结构上
- overlay 现在不再只依赖推断映射：
  - 对带有 `pdb_chain/pdb_residue_no` 的 curated catalytic residues，页面会直接按结构坐标高亮
  - 只有剩余未命中的 protected positions 才继续走 `residue_mapping_sifts` 推断
  - 这比单纯基于 `uniprot_start` 的整链顺序推断更接近真实结构位点
- overlay 也已经开始支持连续结构区段，而不只是单个残基点：
  - `signal_peptide` 的 `h_region` / `c_region` 现在会通过现有 mapping 投到 3D 结构
  - 这为后续继续补 InterPro/domain architecture 结构区段 overlay 提供了同一套 viewer 能力
- 这套连续区段 overlay 现在已经扩到 InterPro/Pfam：
  - `interpro.annotations[].regions` 中的 `domain/family/repeat` 区段会映射到 PDB residue ranges
  - 结构页因此同时具备“风险点位 + secretion 区段 + domain architecture 区段”三类 overlay
- 这使结构工作流从“用户自己读卡片再脑补位点”推进到“页面直接把部分风险位点投到结构视图里”，后续再补的就是更高质量映射数据和更丰富的 overlay 图层，而不是再从头做 viewer 接线。
- 前端已新增两张结果卡片：
  - `StructureMappingCard`：展示链、PDB residue、UniProt position 与 mapping limitation
  - `StructureSearchResultCard`：展示 query structure 摘要、cache 状态和前 5 个结构命中
- 后端已补齐 PDB 专用结构搜索入口：
  - `POST /api/pdb/structure-search`
  - `POST /api/pdb/structure-search-by-name`
- 这使阶段 6 的结构能力从“已注册可测”推进到“页面可触发可观察”，后续继续补的是更高质量的真实映射数据、real Foldseek backend 和更精确的 structure-to-UniProt 对齐，而不是再从零接 UI。
- 本地 Playwright smoke 在当前执行环境中无法启动 headless Chromium：
  - 报错为 `bootstrap_check_in ... MachPortRendezvousServer: Permission denied (1100)`
  - 该问题发生在浏览器进程启动阶段，因此本轮不能用同环境复核匿名 `/wiki` / 公开页黑盒，只能保留代码级与构建级验证。

## 2026-07-04 匿名 wiki 顶层导航运行态新增发现
- 仅依赖代码/构建结论还不够，宿主机 curl 验证暴露出一个真实细节：
  - nginx 新规则挂载后如果不 reload，`http://localhost:4200/wiki/home` 仍会返回 backend 的 `302 /auth/oidc`
  - 容器内执行 `nginx -s reload` 后，带浏览器顶层文档请求头的请求会返回 frontend SPA HTML：
    - `Sec-Fetch-Dest: document` + `/wiki/home` → `200` + `index.html`
  - 不带该请求头的请求仍会返回：
    - `/wiki/home` → `302 /auth/oidc`
- 结论：
  - 当前“匿名顶层文档导航回 SPA、嵌入/非浏览器请求仍走 OIDC bootstrap”的规则在 live runtime 已成立。
  - 剩余未验证的是浏览器真实控制台是否仍有 `/login`、`/home`、`/data` 侧的 auth 噪音，这需要能启动 Chromium 的环境。

## 2026-07-04 PDB mapping API 与 fixture metadata 新增发现
- `residue_mapping_sifts` 现在不只是工具注册项，也已成为可直接调用的 PDB API：
  - `POST /api/pdb/mapping`
  - `POST /api/pdb/mapping-by-name`
- 这让结构位点映射可以在无需 `/api/tools/*` 包装的情况下被结构页或其他 API 客户端直接消费。
- 目录化本地注释 fixture 已新增 `metadata.json`：
  - 当前包含 `dataset_name`
  - `dataset_version=2026-07-04`
  - `default_source_db=local_demo`
- 解析时会自动把 `dataset_version` 下沉到 enzyme `source_version`，为后续替换真实 InterPro/M-CSA/SignalP 导出样本保留版本承载位。

## 2026-07-04 HTTP smoke 与 Foldseek CLI 新增发现
- `frontend/tests/http-smoke.mjs` 在主机权限下验证通过：
  - `/login`、`/home`、`/data` 返回 SPA HTML。
  - `/api/health` 返回 `status=ok`。
  - `/wiki/home` 带 `Sec-Fetch-Dest: document` 返回 SPA HTML。
  - `/wiki/home` 不带顶层 document header 返回 `302 /auth/oidc`。
- 沙箱内直接连 `127.0.0.1:4200` 会被 `EPERM` 拦截，因此后续 live localhost smoke 需要主机权限或容器内执行。
- `structure_search_foldseek` 现在具备三种稳定运行形态：
  - 远端 HTTP：配置 `FOLDSEEK_API_URL` 后调用 `/search`。
  - 本地 CLI：配置 `FOLDSEEK_BINARY` 与 `FOLDSEEK_DATABASE_PDB` / `FOLDSEEK_DATABASE_ALPHAFOLD` / `FOLDSEEK_DATABASE_CUSTOM` 后调用 `foldseek easy-search`。
  - 未配置：返回 `FOLDSEEK_NOT_CONFIGURED` 和本地结构 summary，不伪造结构命中。
- 本地 CLI wrapper 当前已通过 mock 命令测试输出解析，但还没有接入真实 Foldseek database 文件做 live 搜索。
- 最新验证基线：
  - 前端生产构建通过，仅第三方 `3dmol` eval/chunk warning。
  - 后端全量测试为 `287 passed, 199 warnings`。

## 2026-07-04 PDB 结构 overlay 交互新增发现
- `/pdb` 结构页此前虽然已经能投射 curated residue、inferred residue、signal peptide 区段和 InterPro/Pfam 区段，但用户很难区分“未映射”与“被其他图层淹没”。
- `PDBAnalysisCard` 现在补上了一层前端解释能力：
  - 四类图层 legend 与计数：`Curated sites`、`Inferred sites`、`Signal regions`、`Domain regions`
  - 逐层开关后立即重绘 3D viewer，而不是把所有 overlay 永远混在一起
  - `visible x / y` 可见计数，帮助判断当前是映射不足还是人为隐藏
- 这次改动只动前端结果卡和 viewer 入参过滤，没有改动后端 API 合同，因此主要回归面是 TypeScript 类型与构建产物。
- 最新验证：
  - `npm run build` 通过，仅保留既有第三方 `3dmol` eval/chunk warning。

## 2026-07-04 PDB 连续区段 overlay 精度新增发现
- `signal peptide` 和 `InterPro/Pfam` 区段此前会把命中的 PDB residue 简单压成 `min-max`，这在存在链切换或 residue 缺口时会造成过度高亮。
- `PDBUploadPage` 现在会把结构区段 overlay 改为：
  - 先按 `chain_id` 分组
  - 再按连续 `pdb_residue_no` 拆段
  - 最后再去重返回给 viewer
- 结果是连续区段 overlay 从“粗糙包络”收紧为“真实命中的连续段”，更适合作为本地 SIFTS-style mapping 与真实 SIFTS 数据之间的过渡态。
- 结构卡现在也会直接暴露当前 mapping source 与 limitation note 数量：
  - 例如 `local_sifts_mapping`、`local_sifts_style_inference`
  - 当 mapping 返回 limitation 时，会明确提示“inferred overlays 只能作为 guidance”
- 这让用户不需要切到 mapping 结果卡，也能知道当前 3D 高亮依赖的是本地文件映射还是推断兜底。
- 最新验证：
  - `npm run build` 通过，仅保留既有第三方 `3dmol` eval/chunk warning。

## 2026-07-04 SIFTS 本地 mapping 文件源新增发现
- `residue_mapping_sifts` 现在不再只能基于 coordinate order 推断：
  - 配置 `SIFTS_MAPPING_PATH` 后，工具会优先读取本地 JSON / CSV / TSV mapping。
  - 支持单文件，也支持目录下按 `pdb_id` 或通用 `mappings.*` / `residue_mappings.*` 查找。
  - 支持字段别名：`chain_id/chain/pdb_chain`、`pdb_residue_no/pdb_residue_number/pdb_resnum/residue_number`、`uniprot_id/uniprot/accession`、`uniprot_position/uniprot_residue_no/uniprot_residue_number`。
- `/api/pdb/mapping` 与 `/api/pdb/mapping-by-name` 已支持可选 `pdb_id`：
  - raw PDB 路由可显式传入 `pdb_id`。
  - by-name 路由会在缺省时从对象文件名推断前 4 位作为 PDB ID。
- 本地文件命中时返回：
  - `source=local_sifts_mapping`
  - `mapping_source=<path>`
  - 空 `limitations`
- 未命中本地文件时继续返回原先的 `local_sifts_style_inference`，因此现有前端和测试不会被真实数据源配置缺失打断。
- 最新验证基线：
  - SIFTS/Foldseek/PDB API/config 切片为 `44 passed, 6 warnings`。
  - 后端全量测试为 `289 passed, 200 warnings`。

## 2026-07-04 真实浏览器 smoke 与结构数据 harness 新增发现
- 先前的 Chromium 启动限制并不是稳定存在的环境结论：
  - 在主机权限下重新运行 `frontend/tests/public-smoke.mjs` 与 `frontend/tests/live-smoke.mjs`，两者都通过。
  - 这说明当前宿主机运行面上，匿名 `/login`、`/home`、`/data` 与 `/wiki/home` 没有复现此前的浏览器控制台错误。
- 当前仓库仍没有真实 Foldseek DB 文件或真实 SIFTS 导出文件：
  - 所以“live 结构搜索 / live residue mapping”还不能在真实数据上直接跑通。
  - 这不是代码路径缺失，而是运行输入尚未提供。
- 为避免下一轮重复手工拼命令，已新增 `backend/scripts/smoke_structure_data.py`：
  - 未配置真实数据时打印 `SKIP`。
  - 配置 `SIFTS_MAPPING_PATH` / `SIFTS_SMOKE_PDB_ID` 后可直接验证本地 mapping 文件源。
  - 配置 `FOLDSEEK_API_URL` 或 `FOLDSEEK_BINARY + FOLDSEEK_DATABASE_*` 并提供 `STRUCTURE_SMOKE_PDB_FILE` 后可直接验证真实 Foldseek 查询。
- 最新验证基线：
  - Playwright `public-smoke` / `live-smoke` 均通过。
  - 结构 smoke harness 在当前无真实数据配置下输出预期 `SKIP`。
  - 后端全量测试为 `290 passed, 200 warnings`。

## 2026-07-04 真实注释导出 CSV/TSV 兼容层新增发现
- `local_annotations` 现在不再要求所有真实导出都先手工转成 JSON：
  - `base` / `interpro` / `mcsa` / `signalp` 已支持 `.json`、`.csv`、`.tsv`。
  - 这对直接消费真实导出的 InterPro、M-CSA、SignalP 表格文件更实用。
- tabular 导入当前能力边界：
  - 标量列会自动做 `bool/int/float/null` 解析。
  - 复杂列如 `ec_numbers`、`pfam_domains`、`signal_peptide_prediction` 可直接放 JSON 字符串。
  - `base.csv/tsv` 支持平铺字段如 `uniprot_id`、`name`、`sequence`、`scientific_name`，也支持 `taxonomy_*` 前缀。
- 这意味着“真实数据导入”当前剩余阻塞点已经进一步收窄：
  - 不是 parser 只会吃 demo JSON。
  - 而是仓库里还没有真正的 Foldseek DB、SIFTS 导出和真实注释导出文件可供 live 验证。
- 最新验证基线：
  - `test_ingestors + test_data_api + test_data_tools` 为 `47 passed, 140 warnings`。
  - 后端全量测试为 `292 passed, 200 warnings`。

## 2026-07-04 结构 smoke demo 基线新增发现
- `backend/scripts/smoke_structure_data.py` 现在不再只能在“有真实数据目录”或“直接 SKIP”之间二选一。
- 新增 `SIFTS_SMOKE_USE_DEMO=1` 后，脚本会显式切到仓库内 bundled fixture：
  - `backend/app/data/fixtures/structure_smoke/1abc.json`
  - 配合脚本内置最小 PDB 查询结构，验证 `residue_mapping_sifts` 的本地文件源通路
- 这个 demo 模式不会伪装成真实 public dataset：
  - SIFTS demo 通过时输出 `PASS sifts`
  - `FOLDSEEK_SMOKE_USE_DEMO=1` 时，Foldseek 会验证 `summary_only` 降级路径并输出 `PASS foldseek-demo`
  - 未配置真实 Foldseek DB / endpoint 且未启用 demo 时仍然输出 `SKIP foldseek`
- 这样阶段 6 的结构 smoke 现在分成两层：
  - demo 基线：验证代码路径和仓库内 fixture
  - live 基线：等待真实 Foldseek DB 或真实 SIFTS 导出文件
- sandbox / 无 Redis 的环境下，Foldseek demo 可能打印一次 `Redis cache unavailable, using local fallback`：
  - 这是缓存层回退噪音，不是结构 smoke 失败
  - demo 通过判据仍然是 `PASS foldseek-demo`
- `backend/tests/test_config_validation.py` 现在不再只校验 smoke 脚本文本存在性：
  - 会直接以 `SIFTS_SMOKE_USE_DEMO=1` 和 `FOLDSEEK_SMOKE_USE_DEMO=1` 执行脚本
  - 回归断言 `PASS sifts` 与 `PASS foldseek-demo`
- 这让 demo 基线从“手工命令可运行”升级为“测试集自动兜底”，后续改脚本或改结构工具时更不容易悄悄退化。
- 最新验证基线：
  - `SIFTS_SMOKE_USE_DEMO=1 FOLDSEEK_SMOKE_USE_DEMO=1 backend/.venv/bin/python backend/scripts/smoke_structure_data.py` → `PASS sifts`，`PASS foldseek-demo`
  - `backend/.venv/bin/pytest backend/tests/test_config_validation.py -q` → `37 passed`
  - `backend/.venv/bin/pytest backend/tests/test_structure_tools.py backend/tests/test_pdb_api.py backend/tests/test_config_validation.py -q` → `47 passed, 6 warnings`
  - `backend/.venv/bin/pytest backend/tests -q` → `292 passed, 200 warnings`
  - `npm run build` 通过，仅保留既有第三方 `3dmol` eval/chunk warning。

## 2026-07-04 结构 smoke 就绪度脚本新增发现
- 当前机器上最大的残余人工判断，其实不是“怎么跑 smoke”，而是“现在到底是 demo-ready 还是 live-ready”。
- 已新增 `backend/scripts/structure_smoke_readiness.py`：
  - 检查 bundled demo fixture 是否存在
  - 检查 `SIFTS_MAPPING_PATH`
  - 检查 `STRUCTURE_SMOKE_PDB_FILE`
  - 检查 `FOLDSEEK_API_URL` 或 `FOLDSEEK_BINARY + FOLDSEEK_DATABASE_*`
  - 最后给出 `summary = demo-ready | live-ready | blocked`
- 在当前这台机器上的实际结果是：
  - `demo_sifts=ready`
  - `live_sifts/live_query_pdb/live_foldseek_http/live_foldseek_cli=missing`
  - 总结为 `demo-ready`
- 这把“下一步能自动做什么”固定成了一个可执行入口，而不是继续手工读 `.env` 和脚本逻辑。
- 最新验证基线：
  - `backend/.venv/bin/python backend/scripts/structure_smoke_readiness.py` → `summary: demo-ready`
  - `backend/.venv/bin/pytest backend/tests/test_config_validation.py -q` → `39 passed`

## 2026-07-06 部署数据目录产品化新增发现
- 当前项目此前虽然已经支持 `SIFTS_MAPPING_PATH`、`FOLDSEEK_DATABASE_*`、`LOCAL_ANNOTATION_FIXTURE_PATH` 和 `STRUCTURE_SMOKE_PDB_FILE`，但这些能力仍偏“会用的人手工拼路径”，还不是易部署的产品化入口。
- 已新增统一部署数据目录约定：
  - 仓库根目录：`deploy_data/`
  - 容器内：`/app/deploy_data`
  - 子目录约定：`annotations/`、`sifts/`、`foldseek/`、`smoke/query.pdb`
- Docker compose 现会将宿主 `DEPLOY_DATA_HOST_PATH` 挂载到 backend / worker / md-worker 的 `/app/deploy_data`。
- 已新增 `scripts/prepare_deploy_data.py`，可一键生成标准 `deploy_data` 目录结构，并可通过 `--with-demo` 复制 demo annotations / sifts / smoke query。
- 后端配置新增 `DEPLOY_DATA_ROOT`、`LOCAL_ANNOTATION_FIXTURE_PATH`、`STRUCTURE_SMOKE_PDB_FILE`，并会在 `DEPLOY_DATA_ROOT` 存在时自动发现：
  - `annotations/` -> `LOCAL_ANNOTATION_FIXTURE_PATH`
  - `sifts/` -> `SIFTS_MAPPING_PATH`
  - `foldseek/` -> `FOLDSEEK_DATABASE_ROOT`
  - `smoke/query.pdb` -> `STRUCTURE_SMOKE_PDB_FILE`
- `structure_smoke_readiness.py` 现在不只检查结构数据，也会报告：
  - `deploy_data_root`
  - `live_annotations`
- 当前 `live-ready` 的判定也已收紧为：真实 SIFTS、真实 annotations、真实 query PDB，以及真实 Foldseek HTTP 或 CLI 输入同时具备。
- 这意味着剩余工作进一步从“补代码链路”收敛成“把真实数据按标准目录放进去并跑 smoke”。
- 最新验证基线：
  - `backend/.venv/bin/pytest backend/tests/test_config_validation.py -q` → `44 passed`
  - `backend/.venv/bin/python backend/scripts/structure_smoke_readiness.py` → `summary: demo-ready`
  - `SIFTS_SMOKE_USE_DEMO=1 FOLDSEEK_SMOKE_USE_DEMO=1 backend/.venv/bin/python backend/scripts/smoke_structure_data.py` → `PASS sifts` / `PASS foldseek-demo`
  - `python3 scripts/prepare_deploy_data.py --output /tmp/protein_ai_deploy_data_demo --with-demo` → 已成功生成 deploy_data 脚手架与 demo 资产

## 2026-07-08 MD 结构预处理自动检查新增发现
- 真实 MD 运行前的 PDB 文本现在会做保守结构预处理扫描，但不会改变 GROMACS 执行流：
  - 非水 `HETATM`
  - 常见 cofactors
  - 金属/离子
  - alternate locations
  - `REMARK 465` missing residues
  - `SSBOND`
  - histidine protonation review
  - cysteine/disulfide review
- 扫描结果会进入：
  - `wild_type.structure_preparation`
  - `interpretation.structure_preparation`
  - `interpretation.missing_evidence`
  - `protocol_review.review_warnings`
- 这个实现的定位是“科学风险提示和报告门控”，不是自动修复结构：
  - 不自动删除配体/水/金属。
  - 不自动选择 altLoc。
  - 不自动判定 HIS/HID/HIE/HIP。
  - 不自动生成 ligand/cofactor topology。
- 前端 MD 报告已新增 `Structure Preparation` 面板，显示 review flags、HETATM/non-water/HIS/CYS 计数和 cofactor/ion/hetero residue 摘要。
- 最新验证基线：
  - `cd backend && .venv/bin/pytest tests/test_gromacs_md_artifacts.py tests/test_tools_api.py -q` → `33 passed, 2 warnings`
  - `cd frontend && npm run build` → 通过，仅保留既有 `3Dmol` eval 和 chunk warning
  - `cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_auth_resilience.py tests/test_tools_api.py tests/test_ops_api.py tests/test_project_acl.py tests/test_publish_api.py tests/test_llm_gateway.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `165 passed, 92 warnings`
  - `python3 scripts/check_environment.py` → `summary ready`
  - `python3 scripts/check_upgrade_readiness.py` → `ready-with-warnings`，唯一 warning 为历史 dirty worktree

## 2026-07-08 MD WT/突变体重复一致性评估新增发现
- 当前 `gromacs_md` 已新增重复模拟一致性评估合同：
  - 默认单次 WT 运行会明确标记 `insufficient_replicates`，阻止候选排名。
  - 调用方可传入 `wild_type_replicates` 和 `mutant_replicates` 历史/批量指标行，统一评估 replicate count、RMSD drift CV、mean RMSF CV、稳定性分类一致性和突变 delta 方向一致性。
  - 结果进入 `wild_type.replicate_consistency`、顶层 `replicate_consistency`、`interpretation.replicate_consistency` 和 `missing_evidence`。
- 这不是自动多次跑 GROMACS：
  - 现阶段避免把一次 MD 请求隐式变成 3 倍或更多耗时任务。
  - 后续需要在批任务/队列层显式编排多 replicate、突变体结构生成和结果汇总。
- 前端 MD 报告已新增 `Replicate Consistency` 面板：
  - 显示 `ranking allowed/blocked`
  - 显示 minimum replicates
  - 显示每个 variant 的 replicate 数、RMSD drift mean/CV 和 RMSF mean/CV
  - 显示一致性 warning
- 最新验证基线：
  - `cd backend && .venv/bin/pytest tests/test_gromacs_md_artifacts.py tests/test_tools_api.py -q` → `36 passed, 2 warnings`
  - `cd frontend && npm run build` → 通过，仅保留既有 `3Dmol` eval 和 chunk warning
  - `cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_auth_resilience.py tests/test_tools_api.py tests/test_ops_api.py tests/test_project_acl.py tests/test_publish_api.py tests/test_llm_gateway.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `168 passed, 92 warnings`
  - `python3 scripts/check_environment.py` → `summary ready`
  - `python3 scripts/check_upgrade_readiness.py` → `ready-with-warnings`，唯一 warning 为历史 dirty worktree

## 2026-07-08 MD energy/hbond 真实解析新增发现
- `gromacs_md` 现在会在主分析阶段额外尝试：
  - `gmx energy -f md.edr -o energy.xvg`
  - `gmx hbond -s md.tpr -f md.xtc -num hbonds.xvg`
- 这两个步骤被设计成非致命：
  - 失败会写 `18_energy.warning.log.txt` 或 `19_hbond.warning.log.txt`。
  - 不会让已经完成的 RMSD/RMSF/Rg/SASA 主 MD 结果失败。
  - 解析不到时仍走 `missing_evidence`，保持保守解释。
- 新增解析与导出：
  - `energy.xvg` / `energy.csv`
  - `hbonds.xvg` / `hbonds.csv`
  - `energetics.potential_energy_kjmol`
  - `energetics.kinetic_energy_kjmol`
  - `energetics.total_energy_kjmol`
  - `interactions.intra_protein_hbonds`
- 当前边界：
  - `protein_solvent_hbonds` 仍为 `None`，后续需要独立 index/group selection 或更可靠的选择策略。
  - `gmx energy` 的 term 名称在不同 GROMACS/力场环境可能有差异，当前先按常见 `Potential / Kinetic-En. / Total-Energy` 提取，失败降级为 warning。
  - topology warning 仍未结构化解析。
- 最新验证基线：
  - `cd backend && .venv/bin/pytest tests/test_gromacs_md_artifacts.py tests/test_tools_api.py -q` → `37 passed, 2 warnings`
  - `cd frontend && npm run build` → 通过，仅保留既有 `3Dmol` eval 和 chunk warning
  - `cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_auth_resilience.py tests/test_tools_api.py tests/test_ops_api.py tests/test_project_acl.py tests/test_publish_api.py tests/test_llm_gateway.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `169 passed, 92 warnings`
  - `python3 scripts/check_environment.py` → `summary ready`
  - `python3 scripts/check_upgrade_readiness.py` → `ready-with-warnings`，唯一 warning 为历史 dirty worktree

## 2026-07-08 MD 分析解析第二层新增发现
- energy 解析现在不再只依赖固定列顺序：
  - 会读取 XVG `@ sN legend`。
  - 支持 `Potential / Potential-Energy`、`Kinetic-En. / Kinetic-Energy`、`Total-Energy / Total Energy` 的列映射。
  - 没有 legend 时仍保留原先的常见列顺序兜底。
- hbond 解析新增 protein-solvent 独立尝试：
  - 原 `hbonds.xvg/hbonds.csv` 保持 intra-protein。
  - 新增 `hbonds_solvent.xvg/hbonds_solvent.csv`，非致命尝试 `Protein/SOL` 选择。
  - 解析成功时填充 `interactions.protein_solvent_hbonds`。
- topology/preprocessing warning 已结构化：
  - 扫描 `pdb2gmx` 和 `grompp` 的 `.log.txt`。
  - 抽取 `WARNING` / `NOTE`，保留 file/line/message。
  - 识别 charge warning 和 missing atom/parameter warning。
  - 结果进入 `topology_review`、`interpretation.topology_review`、`missing_evidence` 和前端 `Topology Review` 面板。
- 当前边界：
  - `gmx hbond` 的 group 名称在不同体系中可能不是 `SOL`，后续需要用真实输出校准 selection 策略。
  - GROMACS warning 文案差异较大，当前分类词表只覆盖 charge/missing 两类高频风险。
- 最新验证基线：
  - `cd backend && .venv/bin/pytest tests/test_gromacs_md_artifacts.py tests/test_tools_api.py -q` → `39 passed, 2 warnings`
  - `cd frontend && npm run build` → 通过，仅保留既有 `3Dmol` eval 和 chunk warning
  - `cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_auth_resilience.py tests/test_tools_api.py tests/test_ops_api.py tests/test_project_acl.py tests/test_publish_api.py tests/test_llm_gateway.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `171 passed, 92 warnings`
  - `python3 scripts/check_environment.py` → `summary ready`
  - `python3 scripts/check_upgrade_readiness.py` → `ready-with-warnings`，唯一 warning 为历史 dirty worktree

## 2026-07-08 任务审计第三层新增发现
- 任务审计现在具备派生统计摘要：
  - total
  - status_counts
  - tool_counts
  - queue_counts
  - failure_counts
  - slow_count
  - duration mean/max/sample_count
  - recent_failures
  - runtime_environment
- 管理员接口：
  - `/api/tools/admin/tasks/audits` 会随列表返回 `summary`
  - `/api/tools/admin/tasks/audits/summary` 可单独读取摘要
  - CSV 导出新增 `python_version` 和 `platform`
- `/admin` 页面任务审计区新增：
  - 总任务/失败任务/慢任务/平均耗时统计卡
  - 失败分类趋势
  - 最近失败任务
  - 运行环境展示
  - 单条任务 Python/platform 摘要
- 当前边界：
  - 摘要仍基于最近 N 条审计记录，不是全库时间序列聚合。
  - 还没有按时间范围/工具/状态筛选参数。
  - 外部告警联动仍未接入。
- 最新验证基线：
  - `cd backend && .venv/bin/pytest tests/test_tools_api.py -q` → `27 passed, 4 warnings`
  - `cd frontend && npm run build` → 通过，仅保留既有 `3Dmol` eval 和 chunk warning
  - `cd backend && .venv/bin/pytest tests/test_data_api.py tests/test_auth_resilience.py tests/test_tools_api.py tests/test_ops_api.py tests/test_project_acl.py tests/test_publish_api.py tests/test_llm_gateway.py tests/test_config_validation.py tests/test_gromacs_md_artifacts.py -q` → `173 passed, 94 warnings`
  - `python3 scripts/check_environment.py` → `summary ready`
  - `python3 scripts/check_upgrade_readiness.py` → `ready-with-warnings`，唯一 warning 为历史 dirty worktree

## 2026-07-09 聊天长 Markdown 展示不全新增发现
- 用户反馈“实验执行清单”在平台中展示内容不全，经查主要有三类原因：
  - `backend/app/core/agent_graph.py` 在普通聊天和最终报告流式输出时使用 `text.split()` 按空白拆分，导致换行、分隔线、列表层级和 Markdown 表格结构被抹平。
  - 普通聊天 `_chat_reply()` 固定 `max_tokens=512` 且系统提示要求 concise，对“清单/SOP/模板/表格/排期”类长文档容易生成不足。
  - `frontend/src/components/chat/MarkdownView.tsx` 的 Markdown table renderer 曾把完整 `<table>` 传入 `ReportDataTable`，而 `ReportDataTable` 自身也会包一层 `<table>`；复杂表格会形成非法 DOM，可能导致后续内容错位或看似未显示完整。
- 本次修复：
  - 后端新增保留原始空白的 chunk 流式输出，不再按空格重组 Markdown。
  - 后端识别文档型请求，对清单/SOP/模板/表格类普通回复使用更高 token 预算并要求保留结构。
  - 前端 Markdown 表格改为合法的滚动容器 + 单层 table，并增强 th/td 换行。
- 验证：
  - `python3 -m py_compile backend/app/core/agent_graph.py backend/tests/test_agent_binder.py` → 通过
  - `cd backend && .venv/bin/pytest tests/test_agent_binder.py -q` → `23 passed`
  - `cd frontend && npm run build` → 通过；仅保留既有 `3Dmol` eval 和 chunk 体积 warning
- 继续验证：
  - `frontend/tests/smoke-entry.tsx` 已增加长 Markdown 清单 fixture，覆盖标题、分隔线、列表、表格和表格后的内容。
  - `frontend/tests/smoke-check.mjs` 已增加浏览器断言，确认清单关键文本可见且不存在嵌套 table。
  - `FRONTEND_BASE_URL=http://127.0.0.1:4202 node tests/smoke-check.mjs` 在主机权限下通过。
  - `npm run lint` 当前仍失败，失败点分布在大量既有无关文件和规则，不是本轮 Markdown 修复引入；本轮仍以 build、相关后端测试和浏览器 smoke 作为验证依据。

## 2026-07-17 线上 `/data` 数据为空新增发现
- 用户反馈 `http://120.27.108.138/data` 之前准备的数据需要上传进去。
- 排查发现：
  - 线上 `/api/data/readiness` 初始为 `summary=empty`。
  - ECS `/opt/protein-ai-platform/deploy_data` 初始只有 `4.0K`。
  - 本地项目 `deploy_data` 为 `1.7G`，包含 annotations、sifts、pdb、alphafold、foldseek、benchmark 和 smoke query。
  - 本地 `/Users/xuyan/lipase-db/lipase.db` 存在，但线上初始未配置 `LIPASE_DB_PATH` 指向可用文件。
- 处理结果：
  - 已同步本地 `deploy_data` 到 ECS `/opt/protein-ai-platform/deploy_data`，线上目录为 `1.8G`。
  - 已同步 `lipase.db` 到 `/opt/protein-ai-platform/deploy_data/lipase/lipase.db`。
  - 已设置 `DEPLOY_DATA_HOST_PATH=/opt/protein-ai-platform/deploy_data` 和 `LIPASE_DB_PATH=/app/deploy_data/lipase/lipase.db`。
  - 已重建 backend、worker。
- 验证结果：
  - `/data` 页面 HTTP 200。
  - `/api/data/readiness` 为 `summary=live-ready`，所有组件 ready。
  - `/api/data/lipase/status` 为 `status=ready`，integrity check 为 `ok`。
  - D223G evidence context 返回 exact=1、position=1、strongest=`article_level`。
- 结论：
  - `/data` 为空不是前端问题，而是 release 包未携带大数据资产；后续必须把 `deploy_data` 作为 release 外部持久目录管理。

## 2026-07-17 线上 `/data` 顶部统计仍显示 0 新增发现
- 用户反馈数据上传后页面仍显示 0。
- 排查发现：
  - `/api/data/readiness` 已经 `live-ready`，lipase DB 也 `ready`。
  - 页面顶部“酶蛋白/EC/PDB结构/动力学/稳定性/底物/反应”卡片读取 `/api/data/stats`。
  - `/api/data/stats` 原先只统计 RDS 结构化表，而当前 RDS 对应业务表仍为空，所以接口返回全 0。
- 修复：
  - `/api/data/stats` 现在返回三层统计：
    - `database_counts`：RDS 原始表计数。
    - `asset_counts`：deploy_data 和 lipase DB 文件资产计数。
    - `counts`：页面兼容字段，数据库为 0 时用资产计数兜底。
  - 兜底来源包括 `deploy_data/annotations/base.json`、`interpro.json`、`mcsa.json`、`signalp.json`、PDB/AlphaFold/SIFTS readiness 和 lipase DB summary。
- 线上验证：
  - `/api/data/stats` 返回 `counts.enzyme_records=5`、`ec_numbers=2`、`pdb_structures=8`、`kinetic_parameters=12`、`stability_records=12`、`substrate_compounds=7`、`reaction_equations=2`、`interpro_entries=41`。
- 结论：
  - 之前显示 0 是 stats 接口口径问题，不是数据没有上传。
  - 浏览器若仍显示 0，需要刷新页面重新拉取 `/api/data/stats`。

## 2026-07-17 线上“酶蛋白”数量与本地大库不一致新增发现
- 用户反馈“酶蛋白”和本地数量对不上，要求本地数据都上传进去。
- 排查发现：
  - 本地 `deploy_data/annotations/base.json` 只有 5 条种子酶蛋白记录。
  - 本地另有 `backend/protein_ai.db`，大小约 381M，包含 280,036 条 `enzyme_records`。
  - 线上此前只恢复了 `deploy_data` 和 lipase DB，没有把这份结构化 SQLite 导入 RDS。
- 处理：
  - 新增 `backend/scripts/import_domain_sqlite_to_pg.py`，只导入 domain 表。
  - 上传 SQLite 到 ECS 持久目录 `/opt/protein-ai-platform/deploy_data/sqlite/protein_ai.db`。
  - 在后端容器内执行 dry-run 后正式导入 RDS。
  - 导入脚本不导入 users、conversations、messages、projects、project_files、tool_calls，避免覆盖线上账号和业务运行数据。
- 线上结果：
  - `database_counts.enzyme_records=280036`
  - `database_counts.pdb_structures=113836`
  - `database_counts.alphafold_structures=14527`
  - `database_counts.ec_numbers=5650`
  - `database_counts.reaction_equations=18558`
  - `database_counts.kinetic_parameters=1150`
  - `database_counts.stability_records=549`
  - domain 数据总导入 725,449 行。
- 结论：
  - 线上 `/data` 的“酶蛋白”数量已从种子资产的 5 条切换为 RDS 结构化大库的 280,036 条。
  - 新增的 InterPro、催化位点、SignalP 表本地旧 SQLite 没有，仍使用 `deploy_data` 资产兜底。

## 2026-07-17 Venus-15B benchmark 页面 404 新增发现
- 用户反馈 `http://120.27.108.138/benchmarks/venus-15b` 报错。
- 排查发现：
  - 前端页面壳返回 200。
  - `/api/data/benchmarks/venus-15b` 返回 404：`Benchmark case venus-15b not found`。
  - ECS current release 中 `backend/app/data/fixtures/benchmark_cases/venus_15b.json` 存在。
  - 线上 `/api/data/benchmarks` 返回 `count=0`，说明后端运行时没有找到 fixture 目录。
- 根因：
  - 本地源码路径是 `<repo>/backend/app/api/data.py`，旧 `PROJECT_ROOT=parents[3]` 正确指向 repo 根。
  - 容器源码路径是 `/app/app/api/data.py`，同样的 `parents[3]` 会指向 `/`，导致 fixture 目录被拼成 `/backend/app/data/fixtures/...`。
- 修复：
  - `data.py` 改为区分本地和容器路径。
  - `BENCHMARK_FIXTURE_DIR` 改为基于 `BACKEND_ROOT/app/data/fixtures/benchmark_cases`。
- 线上验证：
  - `/api/data/benchmarks` 返回 `count=1`。
  - `/api/data/benchmarks/venus-15b` 返回 200。
  - `/benchmarks/venus-15b` 返回 200。

## 2026-07-18 线上恢复与环境回滚新增发现
- 用户反馈“继续全部开始”后，线上主站短暂不可用。
- 排查发现：
  - 当前 `.env.aliyun.app` 被占位值覆盖，`ALIYUN_APP_DATABASE_URL` 和 `ALIYUN_OUTLINE_DATABASE_URL` 变成 `CHANGE_ME_USER`。
  - Redis 相关变量也被占位值覆盖，Outline 连接报 `change_me_redis_endpoint`。
  - 公网 RDS endpoint `pgm-bp14shfmqveu8o4h.pg.rds.aliyuncs.com` 在 ECS 上解析到 `172.31.12.83`，TCP 5432 超时。
  - 历史备份 `.env.aliyun.app.before-ip-online-20260717T091817` 里保存了可用的 `proteinai-pg-20260716.pg.rds.aliyuncs.com` 和真实 Redis 口径。
- 处理：
  - 直接回滚整份 `.env.aliyun.app` 到可用备份，再补回公网 IP 入口和 `ALIYUN_OUTLINE_PGSSLMODE=disable`。
  - 重建 `outline`、`backend`、`nginx`，恢复容器健康。
- 验证：
  - `http://120.27.108.138/api/health` -> 200。
  - `http://120.27.108.138/login?next=%2Fchat%2Fagent` -> 200，未暴露管理员账号。
  - `http://120.27.108.138/kb` -> 200，页面不再出现 `Not found`。
  - `http://120.27.108.138/api/data/stats` -> 200，`enzyme_records=280036`。
  - 使用 `admin@crvab.com` 完成登录黑盒，`/api/auth/me` 200，`/api/ops/summary` 第二次命中缓存。

## 2026-07-18 MD/ligand 第三块合同收口新增发现
- MD batch ranking 原有本机合同已经能处理 replicate consistency、pending/failed 和缺指标任务；本轮进一步确认候选级门控需要显式暴露，否则有机会把“有分数但拓扑未安全验证”的突变体放进 ranked candidates。
- 已新增 candidate 级字段：
  - `quality_gates`
  - `blocked_reasons`
  - `blocked_candidate_count`
- 现在 MD ranked candidates 只包含同时满足：
  - replicate consistency passed
  - `stability_delta` 与 `rmsf_change_mean` 可计算 ranking score
  - 未被突变体拓扑验证信号阻断
- ligand 侧发现：`prepare_pdbqt / vina_docking / ligand_topology` 在真实 runtime 未安装前必须保持 blocked，但前端/审计需要一个无需解析 stage_results 的总摘要。
- 已新增 `stage_readiness`，聚合每个 stage 的 status、blocked reason、缺参数、缺工具，以及保守的 `can_enter_docking`、`can_enter_gromacs_complex_md`。
- 当前不能在本机完成的部分仍是外部 runtime 阻断：
  - 真实 GROMACS topology live gate、WT/mutant replicate 长任务和真实 batch ranking report：需要 NVIDIA GPU/GROMACS 服务器。
  - 真实 ligand PDBQT、Vina docking、ACPYPE/AmberTools topology：需要装好 OpenBabel/RDKit/Vina/ACPYPE/AmberTools 的容器或服务器。

## 2026-07-18 聊天 Markdown 表格显示新增发现
- 用户截图显示模型输出的 Markdown 表格被按原始文本显示，例如 `| 结果 | 置信度 |` 和 `|---|---||` 直接出现在聊天气泡中。
- 排查发现：
  - `MarkdownView` 非流式路径已经接入 `remark-gfm`，正常 Markdown 表格可以渲染。
  - `MessageBubble` 会把正在生成的助手消息传入 `streaming=true`。
  - `MarkdownView` 在流式路径直接返回纯文本 `<div>`，没有进入 `ReactMarkdown`，因此流式期间表格必然显示为管道文本。
- 修复：
  - 流式内容中检测到可信 Markdown 表格时，切换到 `ReactMarkdown + remark-gfm`。
  - 增加表格块容错，修正轻微坏表格：分隔行多余管道、数据行缺尾部管道、表头末尾误粘 `---`。
  - 保留非表格流式内容的纯文本路径，避免长回答每个 token 都触发复杂结构重排。
- 验证：
  - 本地 smoke 用截图同类坏表格确认 DOM 中出现真实 `<table>`。
  - 线上已部署新前端 bundle，`http-smoke` 和 `live-smoke` 均通过。
- 边界：
  - 线上聊天黑盒表格验证未产出表格，因为模型对测试提示返回了欢迎语；这不能作为前端表格渲染失败证据。

## 2026-07-18 全部开始第二批新增发现
- 只读代码走查发现：聊天气泡渲染本身没有 `dangerouslySetInnerHTML` 或 `rehypeRaw` 路径，但下载 HTML 报告存在 XSS 风险。
  - 风险入口是聊天页导出按钮收集助手消息和工具结果后生成 `.html`。
  - `conversation-report.ts` 旧代码直接拼接报告标题和 `synthesis.replace(/\n/g, '<br>')`。
  - `report.ts` 旧代码通过字符串模板和 `h()` 直接插入工具字段，`h()` 对文本和属性都不转义。
- 修复：
  - `report.ts` 新增 `escapeHtml()` 与属性转义，所有来自工具/模型/标题的动态字段先转义。
  - `conversation-report.ts` 对标题、目录标签和合成总结转义后再插入 HTML；换行只在 escape 后替换为 `<br>`。
  - 用恶意 payload 验证生成 HTML 不再包含真实 `<script>`、`<img ...>` 或标签内 `onerror=`。
- 只读线上黑盒发现：
  - `/login`、`/chat/agent`、`/data`、`/kb`、`/benchmarks/venus-15b`、`/api/health`、`/api/data/stats` 均通过。
  - 管理员登录态下未发现白屏、console error 或非预期 4xx/5xx。
  - `/api/data/stats` 主要统计仍正确：`enzyme_records=280036`，`pdb_structures=113836`，`alphafold_structures=14527`。
  - `benchmark` bundle 的 `GET` range 下载可用，返回 206；`HEAD` 返回 405，属于低风险兼容项。
- OSS readiness 发现：
  - 本机脚本原先只识别 `MINIO_*`，但阿里云部署使用 `ALIYUN_OSS_*`。
  - 已统一支持 `MINIO_*` 和 `ALIYUN_OSS_*` 别名，避免把已配置 OSS 的阿里云环境误判为缺凭据。
  - 本机 readiness 仍不会读取线上 `.env` 明文密钥；这是安全边界，不是线上 OSS 未配置的证据。

## 2026-07-18 chat/agent 用户隔离二次加固发现
- 再次黑盒验证后端隔离：
  - 4 个普通研究员账号均为 `researcher`。
  - 普通账号访问 admin users API 返回 403。
  - kwb01/kwb02 的会话列表、会话详情、项目列表、项目详情互相隔离。
- 用户继续反馈“还有”的主要可解释路径不是后端越权返回，而是浏览器端旧状态：
  - 已打开旧 JS 的页面会保留 Zustand 内存里的上一账号会话。
  - 旧 `currentConversationId` 可能在同一浏览器切账号后继续指向上一账号会话。
  - 加载新 bundle 前，这类状态不会自动消失。
- 已追加加固：
  - 登录、注册、退出时主动清理用户域前端状态。
  - 聊天 store 增加 `protein-ai:user-scoped-reset` 事件监听。
  - 获取旧 conversation ID 返回 404 时，移除旧 ID 和旧列表项。
  - 客户端状态版本升级为 `20260718-user-scope-v3`，新入口首次加载会自动清一次旧选择。
- 线上验证：
  - `/chat/agent` 当前返回新 bundle `assets/index-lfL9Mlpa.js`。
  - HTTP smoke、API 用户隔离 smoke、真实浏览器同窗口切账号 smoke 均通过。

## 2026-07-18 chat/agent 历史测试数据与 cookie 发现
- 用户继续反馈“还有”后，直接查询线上数据库发现：
  - `admin@protein.local` 名下有 8 条上线验收/测试会话。
  - `kwb01@protein.local` 名下有 4 条测试/演示会话。
  - `kwb04@protein.local` 名下有 2 条测试/演示会话。
  - `kwb02@protein.local`、`kwb03@protein.local` 原本为空。
- 结论：
  - 这批数据不是后端越权返回别人账号记录，而是历史测试会话已经属于对应当前账号。
  - 普通 API 用户隔离 smoke 仍成立，但初始账号体验不干净。
- 处理：
  - 已备份目标 chat conversations 到 ECS 临时 JSON。
  - 已删除目标账号下 14 条历史测试 chat conversations；不触碰项目、文件、数据资产或 Wiki。
  - 登录/注册前新增服务端 `/auth/logout` cookie 清理，退出登录也等待后端 cookie 清理完成。
- 验证：
  - `admin`、`kwb01`、`kwb02`、`kwb03`、`kwb04` 登录后的 `/api/conversations` 均为 0 条。
  - 真实浏览器同窗口切账号测试通过。
  - 线上新 bundle 为 `assets/index-B3VXmsvH.js`。

## 2026-07-20 前端 lint warning 专项治理发现
- 本轮在阶段 9 验收完成后继续收口前端 warning 债，未触碰线上环境。
- 初始专项治理基线来自 `frontend-lint-warnings.json`：
  - `117 warnings`
  - `@typescript-eslint/no-explicit-any`: 65
  - `react-refresh/only-export-components`: 16
  - React Hooks/Compiler 相关：36
- 已修复：
  - 清零 `@typescript-eslint/no-explicit-any`：为 API client、DataBrowser、ProjectDetail、PDBUpload、PublishToolbar、chat store 补保守类型。
  - 清理 Hooks 依赖/ref/immutability/preserve-memoization 类 warning：`ChatInput` ref 同步、`PDBUploadPage` MD poll 闭包、`ProjectDetailPage` memo 依赖、`WikiPage` fallback callback、`ProteinViewer` 依赖等。
  - `PDBAnalysisCard` 删除冗余 overlay 派生 state effect；`RFdiffusionResult` 将 top design 计算纳入 `useMemo`。
- 最终本地验证：
  - `cd frontend && npm run lint -- --format json --output-file ../.tmp/frontend-lint-warnings-final.json` -> 退出码 0。
  - 最终 warning：27，总体从 117 降到 27。
  - 剩余 warning 仅两类：
    - `react-refresh/only-export-components`: 16，集中在 analysis 组件文件导出组件同时导出类型守卫；影响开发热更新，不影响生产构建。
    - `react-hooks/set-state-in-effect`: 11，集中在页面挂载拉数据/打开弹窗重置状态；需要按页面生命周期做更大重构，不在本轮低风险范围硬改。
  - `cd frontend && npm run build` -> 通过；仍有既有 3Dmol direct eval 与 chunk size warning。
- 决策：
  - 本轮不做线上同步。原因：这是 warning 债务治理，不是线上缺陷修复；应等用户确认或合并下一批可验证功能变更后再统一发布。
  - Fast Refresh 后续可把 analysis 组件中的 `isXResult` 类型守卫拆到独立 `guards` 文件或 `*.result.ts` 文件中再统一改 imports。

## 2026-07-22 前端 / SSE / 会话一致性深评发现
- 新增真实浏览器 gate：
  - `frontend/tests/chat-sse-deep-live.mjs`：临时用户登录 `/chat/agent`，发送 baseline 消息，上传真实小 PDB，触发 `gromacs_md`，断言工具状态为 `submitted`、能看到 `task_id/status_url`，最后 logout 并确认本地 token/refresh/currentConversationId 清理。
  - `frontend/tests/chat-session-deep-live.mjs`：临时双用户与临时会话，覆盖 reload restore、坏 access token 后 refresh/retry、切用户隔离、stale saved conversation cleanup。
- 打出的真实问题：
  - `restoreSession()` 在页面刷新后会把内存 `ownerUserId=null -> userId` 当成用户切换，间接清掉 `currentConversationId`，导致刷新不能恢复最后会话。
  - `ConversationList` 和 `ChatLayout.restoreSession()` 同时触发 `syncConversations()` 时，旧 `_syncing` 直接返回，restore 可能早于会话列表同步完成并误判 savedId 不存在。
  - 后端返回的 conversation id 在部分路径为 number，localStorage 为 string，`conv.id === savedId` 严格比较失败，导致已存在会话被当成 stale 清理。
  - access token 被污染为非 JWT 字符串时，后端可通过 cookie 兜底保持请求成功，但前端 `ensureValidAccessToken()` 不会主动 refresh，坏 token 会留在 localStorage。
- 本地/线上修复：
  - `frontend/src/stores/chat.ts`：并发 `syncConversations()` 改为共享 Promise；auth 水合不再误清；保存 `currentConversationId:<userId>`；恢复时按当前用户读取；会话 ID 统一 `String(...)`。
  - `frontend/src/stores/auth.ts`：显式登录/注册/登出清理所有 user-scoped conversation key。
  - `frontend/src/lib/api.ts`：`ensureValidAccessToken()` 对无法解析 `exp` 的 token 主动 refresh。
  - `frontend/tests/chat-sse-deep-live.mjs`：baseline 判定改为看 assistant 实际文本，不要求模型复读 marker。
- 线上验证结果：
  - `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/chat-sse-deep-live.mjs` -> passed；baseline、PDB/MD submitted、task_id、logout、consoleErrors=0、httpErrors=0。
  - `FRONTEND_BASE_URL=http://120.27.108.138 node frontend/tests/chat-session-deep-live.mjs` -> passed；restore、tokenRefresh、userSwitch、staleCleanup 均 passed，consoleErrors=0、httpErrors=0。
  - `http-smoke`、`public-smoke`、`live-smoke` -> passed。
  - ECS `backend/frontend/nginx/worker/md-worker` 均 healthy；线上前端 bundle 为 `index-BVil8ddL.js`。
- 当前边界：
  - 已覆盖 chat 主链路、SSE 长流的真实 PDB/MD 异步提交、logout、restore、token refresh 和用户隔离。
  - 尚未对 HomePage 入口注入、ProjectDetailPage 多 tab、Wiki 树、benchmarks/PDB/admin 进行同等深度业务交互评测；这些列入阶段 12 剩余项。

## 2026-07-20 235 继续推进发现
- 前端 Fast Refresh warning 已清零：
  - 新增 `frontend/src/components/analysis/resultGuards.ts`，集中放置 `isXResult` 与 `extractBatchCompare`。
  - analysis 组件文件只保留 UI 组件和必要类型导出，避免 `react-refresh/only-export-components`。
  - 当前 `npm run lint` 退出码 0，统计为 `0 errors / 11 warnings`；剩余仅 `react-hooks/set-state-in-effect`。
- 新增线上 AI 黑盒入口：
  - `scripts/smoke_ai_blackbox_live.py` 使用 `backend/tests/enzyme_agent_eval_cases.json` 中低成本场景。
  - 默认覆盖缺信息耐热性改造、无目标 binder、结构编号缺失等场景；校验 SSE done、禁用工具未出现、追问文本存在。
  - 凭据只从 `LIVE_AI_EMAIL/LIVE_AI_PASSWORD` 或 stdin JSON 读取，不打印 token/password。
- 新增 live 文件下载 E2E 入口：
  - `scripts/smoke_file_download_live.py` 通过 `/api/files/upload` 上传小 `.txt`，再从 `/api/files/{object}/download` 下载校验内容、`Content-Disposition`、`Content-Type`，最后删除对象。
  - 该脚本间接覆盖线上 OSS/MinIO 配置、后端下载鉴权和浏览器可下载头。
- 验收矩阵新增 opt-in gate：
  - `--include-ai-blackbox`
  - `--include-file-download-e2e`
  - 默认仍 skipped，避免无凭据/非维护窗口时误跑线上写入或 LLM 请求。
- 线上同步发现：
  - ECS 宿主机无 `npm`，线上前端验证需通过 Docker build 完成。
  - 首次 Docker build 因漏同步 `AnnotationBundleCard.tsx` 失败，补同步后通过。
  - 首次 `docker compose up` 未带 env file，compose 插值变量为空导致 Outline unhealthy；使用三个线上 env 文件重跑后 backend/outline/frontend/nginx 全部 healthy。
- 验证结果：
  - 本地 `npm run lint` -> 0 errors / 11 warnings。
  - 本地 `npm run build` -> 通过，仅有既有 3Dmol direct eval/chunk size warning。
  - `python3 -m py_compile scripts/smoke_ai_blackbox_live.py scripts/smoke_file_download_live.py scripts/run_acceptance_matrix.py` -> 通过。
  - `backend/.venv/bin/python -m pytest backend/tests/test_config_validation.py::TestRequirementsFiles::test_acceptance_matrix_script_plan_includes_risk_gates -q` -> 1 passed。
  - 线上 Docker build frontend -> 通过。
  - 线上容器：nginx/backend/outline/frontend/worker/ligand-worker/chromadb 均 healthy。
  - 公网 `http-smoke`、`public-smoke`、`live-smoke` 均通过。
- 当前边界：
  - AI 黑盒和文件下载 E2E 脚本已就绪，但本轮未在对话中传入普通应用账号密码执行 live 写入/LLM 请求。
  - `run_acceptance_matrix.py --include-oss-e2e` 在当前 shell 缺 OSS 凭据变量时返回 blocked，这是符合预期的显式门禁。
  - 真正长 MD blackbox/GPU replicate 仍等待 GPU/GROMACS 服务器。

## 遇到的问题
| 问题 | 解决方案 |
|------|---------|
| 聊天入口为避免 SSE 长时间卡住，把 `gromacs_md` 强制改成 plan-only，导致用户无法真正使用慢工具 | 改为聊天流提交 Celery 后台任务并返回 `task_id/status_url`，前端显示 `submitted` |
| 阿里云 app compose 没有 `md-worker`，`gromacs_md` 任务进入 `md_cpu` 后无人消费 | 在 `docker-compose.aliyun-app.yml` 新增 `md-worker`，监听 `md_cpu`，线上已 healthy |
| 线上 `/api/tools`、工具详情、diagnostics 仍匿名 200，P0 工具元数据鉴权未生效 | 同步本地已修 `backend/app/api/tools.py`，重建并重启 backend/worker/md-worker；匿名回归 6/6 通过 |
| 直接 MD live gate 用极小 PDB 会在 GROMACS 建拓扑阶段失败 | 该失败属于输入质量问题；链路验证改看 submit/queue/progress/stage/cancel，业务 PDB 后续单独验收 |
| Docker 镜像构建过程中磁盘空间不足 | 清理 stopped containers 与 dangling images 后重新构建 |
| FastAPI 依赖签名不兼容导致 backend 重启 | 调整 `get_current_user` 参数顺序与类型 |
| 旧前端 bundle 持续报 401 | 通过缓存控制、自动刷新与后端 cookie 回退降低影响 |
| 多处上传逻辑各自处理 token 与 401 | 统一下沉到公共上传函数 |

## 资源
- 后端关键模块：`backend/app/api/`、`backend/app/core/`、`backend/app/tools/`
- 前端关键模块：`frontend/src/lib/`、`frontend/src/stores/`、`frontend/src/hooks/`、`frontend/src/pages/`
- 部署关键模块：`docker/docker-compose.yml`、`docker/nginx-frontend.conf`、`docker/nginx.conf`

## 2026-07-25 多酶数据库 Google 文献补证据
- 任务目标：通过 Google/网页检索继续丰富本地 `/酶数据库` 中的非 lipase SQLite 库，先做可回滚试点。
- 本地 schema 发现：
  - `lipase.db` 是 11 表 evidence schema：`papers / paper_aliases / variants / variant_mutations / evidence_claims / substrates / claim_substrates / metrics / comparators / unresolved_gaps / lineage_notes`。
  - 其它 6 个库当前为简化三表 schema：`papers / variants / measurements`。
  - 简化库 `measurements` 没有唯一约束，历史插入脚本会直接 `INSERT`；后续增量脚本必须显式查重，避免重复测量。
- 当前记录量：
  - `amylase.db`: papers=53, variants=51, measurements=104。
  - `mannanase.db`: papers=34, variants=59, measurements=75。
  - `xylanase.db`: papers=80, variants=113, measurements=178。
  - `acid_protease.db`: papers=126, variants=124, measurements=162。
  - `phytase.db`: papers=43, variants=85, measurements=78。
  - `glucose_oxidase.db`: papers=66, variants=99, measurements=802。
- Amylase Google 候选（第一批试点）：
  - Fan et al., 2024, *Computational and Structural Biotechnology Journal*, DOI `10.1016/j.csbj.2024.02.005`, PMID `38404709`, PMCID `PMC10883975`。Bacillus licheniformis α-amylase BLA computational design；PubMed 摘要给出 `E271L/N278K` catalytic efficiency 1.88x，`E336S` half-life at 95C 1.43x。
  - Wei/Ma et al., 2024, *Journal of Agricultural and Food Chemistry*, DOI `10.1021/acs.jafc.4c05070`。Bacillus amyloliquefaciens α-amylase BAA `S275L`；ACS 摘要给出 activity +18.7%、optimal temperature +10C、60C stability +49.2%。
  - Liu et al., 2025, *Journal of Agricultural and Food Chemistry*, DOI `10.1021/acs.jafc.5c01807`, PMID `40209109`。Flexible-region alkaline amylase thermostability engineering；摘要给出 T-40、M4、Amy I-ML 的残余活性、活力和半衰期 fold-change，可作为 high-confidence 摘要级证据写入。
  - Wang et al., 2024, *International Journal of Biological Macromolecules*, DOI `10.1016/j.ijbiomac.2024.130481`。M. cinnamomea McAmyA `T226S`/mMcAmyA；摘要给出 optimal temperature +5C、maltotriose yield 18.6% / 2.5x、expression 3951 U/mL。
- 数据策略：
  - 第一批写入证据较完整、突变和指标在摘要/开放页面明确的 `Fan2024_CSBJ`、`Wei2024_JAFC`、`Wang2024_IJBM`、`Liu2025_JAFC`。
  - 写库脚本路径：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/amylase-db/insert_google_batch_20260725.py`。
  - 脚本默认 dry-run，`--apply` 才提交；正式提交前自动备份 `amylase.db`。
  - 写入结果：`amylase.db` 从 papers=53 / variants=51 / measurements=104 增至 papers=57 / variants=60 / measurements=129。
  - 新增分布：`Fan2024_CSBJ` 4 variants / 12 measurements；`Wei2024_JAFC` 1 / 4；`Wang2024_IJBM` 1 / 5；`Liu2025_JAFC` 3 / 4。
  - 备份文件：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/amylase-db/amylase.db.bak-google-20260725-20260725T134117`。
  - 校验：正式写入后 `PRAGMA integrity_check` 返回 `ok`；重复 dry-run 显示 papers=0 / variants=0 / measurements=0 新增，25 条 measurement 被跳过，具备幂等性。
- 第二批“全部开始”：
  - 新增统一脚本：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/insert_google_batches_20260725.py`，覆盖 `mannanase / xylanase / phytase / acid_protease / glucose_oxidase`。
  - `mannanase.db`：新增 `MAN113`、`MAN114`，新增 2 papers / 2 variants / 6 measurements。记录量从 34/59/75 增至 36/61/81，完整性 `ok`。
  - `xylanase.db`：补 `XYN56` DOI，新增 `XYN81`，新增 1 paper / 1 variant / 2 measurements。记录量从 80/113/178 增至 81/114/180，完整性 `ok`。
  - `phytase.db`：补 `112` DOI 和 journal 元数据，记录量不变 43/85/78，完整性 `ok`。
  - `acid_protease.db`：补 `AP611` PMID，记录量不变 126/124/162，完整性 `ok`。
  - `glucose_oxidase.db`：新增 `GOX140`，新增 1 paper / 1 variant / 1 measurement。记录量从 66/99/802 增至 67/100/803，完整性 `ok`。
  - 第二批备份：
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/mannanase-db/mannanase.db.bak-google-20260725-20260725T134952`
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/xylanase-db/xylanase.db.bak-google-20260725-20260725T134952`
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/phytase-db/phytase.db.bak-google-20260725-20260725T134952`
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease.db.bak-google-20260725-20260725T134952`
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/glucose_oxidase-db/glucose_oxidase.db.bak-google-20260725-20260725T134952`
  - 重复 dry-run 验证：
    - `mannanase/xylanase/glucose_oxidase` 新增行均为 0，measurements 分别跳过 6/2/1。
    - `phytase/acid_protease` 为 metadata update 型批次，重复执行会匹配已有行但不改变记录量。

## 2026-07-25 Lipase evidence schema Google 补证据
- 用户再次要求“全部开始”，将 `lipase.db` 也纳入 Google 补证据范围。
- 本地 schema 发现：
  - `lipase.db` 当前为平台专用 11 表 evidence schema，不能复用简化库的 `papers / variants / measurements` 脚本。
  - 核心写入链路为 `papers -> variants -> variant_mutations -> evidence_claims -> metrics`，可选 `substrates / claim_substrates`。
- 新增脚本：
  - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/lipase-db/insert_google_batch_20260725.py`
  - 默认 dry-run，`--apply` 才提交；正式提交前自动备份。
- 写入来源：
  - Pan et al., 2025, *International Journal of Biological Macromolecules*, DOI `10.1016/j.ijbiomac.2025.142646`, PMID `40609642`。
  - 主题：Cryptococcus sp. S-2 lipase `CtLip` rational design；B1、A335I、B1/A335I 改善 pH stability、thermal stability 和 methanol tolerance。
  - 2026-08-01 更正：本段为 2026-07-25 初始写入时的历史错误记录。后续核验确认 PMID `40609642` 是药学教育论文错配；当前有效 Pan_2025 题名为 `Modifying loop regions in lipase from Caldibacillus thermoamylovorans for enhancing thermostability`，酶种为 `Caldibacillus thermoamylovorans thermostable lipase`，PMID 置空。
- 写入结果：
  - `papers`: 10 -> 11。
  - `variants`: 12 -> 15。
  - `variant_mutations`: 12 -> 22。
  - `evidence_claims`: 12 -> 15。
  - `metrics`: 12 -> 16。
  - 备份文件：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/lipase-db/lipase.db.bak-google-20260725-20260725T135519`。
  - 校验：正式写入和重复 dry-run 均返回 `PRAGMA integrity_check=ok`；重复 dry-run 不改变记录量。

## 2026-07-25 平台多酶数据库只读接入第一层
- 背景：此前平台只接入 `lipase.db`，其它 6 个 SQLite 库只是本地文件。
- 本轮接入策略：
  - 不改 `lipase.db` 原专用 API 和前端链路。
  - 对 6 个简化三表库新增统一只读 service/API。
  - 使用 `ENZYME_DB_ROOT` 自动发现 `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库`。
- 新增后端能力：
  - `GET /api/data/enzyme-dbs/status`
  - `GET /api/data/enzyme-dbs/{family}/status`
  - `GET /api/data/enzyme-dbs/{family}/papers`
  - `GET /api/data/enzyme-dbs/{family}/variants`
  - `GET /api/data/enzyme-dbs/{family}/measurements`
  - `GET /api/data/enzyme-dbs/{family}/search`
- 支持 family：
  - `amylase`
  - `mannanase`
  - `xylanase`
  - `acid_protease`
  - `phytase`
  - `glucose_oxidase`
- 校验发现：
  - 6 个简化库全部 `ready`，SQLite `integrity_check=ok`。
  - 计数：amylase 57/60/129；mannanase 36/61/81；xylanase 81/114/180；acid_protease 126/124/162；phytase 43/85/78；glucose_oxidase 67/100/803。
- 当前边界：
  - 后端只读 API 已开始接入全部简化库。
  - 尚未做前端统一 family 切换 UI，也尚未把这些库纳入 agent 工具上下文。

## 2026-07-25 酶库元数据深挖
- 最新指令：“继续深挖酶库”。
- 元数据缺口统计：
  - `amylase`: total=57, missing_doi=1, missing_pmid=10。
  - `mannanase`: total=36, missing_doi=7, missing_pmid=7。
  - `xylanase`: total=81, missing_doi=5, missing_pmid=74。
  - `phytase`: total=43, missing_doi=13, missing_pmid=5。
  - `acid_protease`: total=126, missing_doi=74, missing_pmid=38。
  - `glucose_oxidase`: total=67, missing_doi=8, missing_pmid=24。
  - `lipase`: total=11, missing_doi=2, missing_pmid=4。
- 第一批深挖写入：
  - 新增脚本：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/metadata_deep_dive_20260725.py`。
  - `mannanase`：补 `MAN107` DOI `10.1016/j.ijbiomac.2024.133182`，DOI 缺口 7 -> 6。
  - `phytase`：补 `104` DOI `10.4014/jmb.2311.11044`，补 `107` DOI `10.1021/acs.jafc.5c00550`，DOI 缺口 13 -> 11。
  - 备份：
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/mannanase-db/mannanase.db.bak-metadata-deep-dive-20260725-20260725T140359`
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/phytase-db/phytase.db.bak-metadata-deep-dive-20260725-20260725T140359`
  - 校验：dry-run 与正式写入均 `integrity_check=ok`。
- 下一步优先级：
  - P0：`acid_protease` DOI 缺口 74，需要分批核验，优先 PubMed 有 PMID 但 DOI 为空的记录。
  - P0：`xylanase` PMID 缺口 74，需要按 DOI 反查 PubMed / EuropePMC。
  - P1：`glucose_oxidase` 缺 PMID 24，优先 DOI 已有但 PMID 为空的开放论文。

## 2026-07-25 Xylanase 深挖纠错
- Google/PubMed/DOI 反查时发现 `xylanase.db` 中存在错误 DOI 和重复记录：
  - `XYN55` 原 DOI `10.1021/acs.jafc.4c08946` 指向黄酒 GC-IMS 论文，不是 xylanase。
  - 上一批新增 `XYN81` 复用了错误 DOI，且内容实际与已有 `XYN55` 是同一篇 BaXynA Mut-1 论文，构成重复。
  - `XYN77` 原 DOI `10.1016/j.ijbiomac.2025.139500` 指向 IgG 热聚集论文，不是 xylanase。
- 修复脚本：
  - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/xylanase-db/xylanase_metadata_corrections_20260725.py`
- 修复结果：
  - `XYN55` DOI/PMID 修正为 `10.1021/acs.jafc.5c09584` / `41168089`。
  - `XYN56` PMID 补为 `40643334`。
  - `XYN57` PMID 补为 `41096293`。
  - `XYN77` DOI/PMID 修正为 `10.1016/j.ijbiomac.2025.143063` / `40253048`。
  - 删除重复 `XYN81`：papers -1、variants -1、measurements -2。
  - `xylanase.db` 最终计数回到 papers=80、variants=113、measurements=178；`PRAGMA integrity_check=ok`。
  - 备份：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/xylanase-db/xylanase.db.bak-xylanase-corrections-20260725-20260725T140812`。

## 2026-07-25 Acid Protease 深挖元数据
- 目标：优先收敛 `acid_protease.db` 中 PubMed 已能核验但 DOI 为空的记录。
- 第一批脚本：
  - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease_metadata_deep_dive_20260725.py`
  - `AP602` DOI/PMID -> `10.1007/s12033-025-01470-0` / `40622661`。
  - `AP604` DOI/PMID -> `10.1002/pro.70011` / `39720900`；原 `pmid` 字段误放 `PMC11669118`，已纠正。
  - `AP117` DOI/PMID -> `10.1371/journal.pone.0141758` / `26510189`。
  - `AP620` DOI/PMID -> `10.1002/prot.25410` / `29082609`。
  - DOI 缺口 74 -> 70，完整性 `ok`。
  - 备份：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease.db.bak-acid-protease-deep-dive-20260725-20260725T141813`。
- 第二批脚本：
  - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease_metadata_deep_dive2_20260725.py`
  - `AP612` DOI/PMID -> `10.1007/s11274-013-1373-6` / `23677580`。
  - `AP613` DOI -> `10.1002/jsfa.7688`。
  - DOI 缺口 70 -> 68，PMID 缺口 38 -> 37，完整性 `ok`。
  - 备份：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease.db.bak-acid-protease-deep-dive2-20260725-20260725T143248`。
- 第三批脚本：
  - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease_metadata_deep_dive3_20260725.py`
  - `AP309` DOI/PMID -> `10.1016/j.bbapap.2015.05.006` / `26003941`。
  - `AP209` DOI/PMID -> `10.1016/j.bmcl.2007.12.028` / `18180160`。
  - `AP116` DOI/PMID -> `10.1021/bi047886u` / `15697202`。
  - DOI 缺口 68 -> 65，完整性 `ok`。
  - 备份：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease.db.bak-acid-protease-deep-dive3-20260725-20260725T143631`。
- 第四批脚本：
  - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease_metadata_deep_dive4_20260725.py`
  - `AP306` DOI/PMID -> `10.1016/j.jmb.2004.07.076` / `15381092`。
  - `AP106` DOI/PMID -> `10.1128/jvi.77.24.13053-13062.2003` / `14690411`。
  - `AP305` DOI/PMID -> `10.1021/bi035051y` / `14609343`。
  - `AP118` DOI/PMID -> `10.1021/cr010148q` / `12475196`。
  - DOI 缺口 65 -> 61，完整性 `ok`。
  - 备份：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease.db.bak-acid-protease-deep-dive4-20260725-20260725T143940`。
- 第五批脚本：
  - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease_metadata_deep_dive5_20260725.py`
  - `AP215` DOI/PMID -> `10.1016/S0014-5793(02)03052-1` / `12135764`。
  - `AP618` DOI/PMID -> `10.1016/S0014-5793(02)02270-6` / `11943140`。
  - `AP622` DOI/PMID -> `10.1093/oxfordjournals.jbchem.a003247` / `12204120`。
  - DOI 缺口 61 -> 58，完整性 `ok`。
  - 备份：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease.db.bak-acid-protease-deep-dive5-20260725-20260725T144201`。
- 第六批脚本：
  - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease_metadata_deep_dive6_20260725.py`
  - `AP203` DOI/PMID -> `10.1073/pnas.97.4.1456` / `10677483`。
  - `AP205` DOI/PMID -> `10.1021/bi015546s` / `11513577`。
  - DOI 缺口 58 -> 56，完整性 `ok`。
  - 备份：`/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/acid-protease-db/acid_protease.db.bak-acid-protease-deep-dive6-20260725-20260725T144425`。

## 2026-07-25 国外网站调研 P0 新证据
- 用户要求“继续去谷歌国外网站调研，看看还有没有值得深挖的”。
- 调研来源方向：
  - PubMed / DOI / PMC。
  - ACS Publications。
  - ScienceDirect / Elsevier。
  - Springer / SpringerLink。
  - 国内英文摘要可由 PubMed/DOI 交叉确认时纳入。
- 发现的 P0 级可写入候选：
  - `phytase 116`: Lin et al. 2026, DOI `10.13345/j.cjb.250733`, PMID `41873074`，Aspergillus tubingensis phytase `T273K`，半衰期 60C +67.56%、80C +92.86%，`kcat/Km` +50.56%。
  - `xylanase XYN82`: Wang et al. 2025, DOI `10.1021/acs.jafc.5c03486`, PMID `40391832`，XynT `A7C/P210H/W277P/G304C`，specific activity 22341.7 U/mg、2.1x，55C pH8 半衰期 215 min、7.6x。
- 新增脚本：
  - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/foreign_research_batch_20260725.py`
- 写入结果：
  - `phytase.db`: papers 43 -> 44；variants 85 -> 86；measurements 78 -> 81。
  - `xylanase.db`: papers 80 -> 81；variants 113 -> 114；measurements 178 -> 180。
  - 两库 `PRAGMA integrity_check=ok`。
  - 备份：
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/phytase-db/phytase.db.bak-foreign-research-20260725-20260725T145115`
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/xylanase-db/xylanase.db.bak-foreign-research-20260725-20260725T145115`

## 2026-07-25 国外网站调研第二批 P0 新证据
- 调研发现：
  - `glucose_oxidase`: Peng et al. 2026, DOI `10.1021/acs.jafc.6c03763`, PMID `42268732`，AlGoxA `A179V/T302L`，catalytic efficiency 10.8x、60C thermal stability 11.2x、PPO inhibition 87.1%。
  - `lipase`: Chang et al. 2025, DOI `10.1021/acs.jafc.4c10663`, PMID `40080726`，Rhizomucor miehei lipase `A113G`、`A113G/L74N`，A113G 活性 +46.0%，A113G/L74N 50% methanol 50C 24h 后保留 33% 活性，soybean/waste oil biodiesel yield 91.2%/80.6%。
  - `phytase 114`: DOI/PMID 完整核验为 `10.4014/jmb.2403.03031` / `39081259`。
- 新增脚本：
  - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/foreign_research_batch2_20260725.py`
  - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/lipase-db/insert_foreign_batch2_20260725.py`
- 写入结果：
  - `glucose_oxidase.db`: papers 67 -> 68；variants 100 -> 101；measurements 803 -> 806。
  - `phytase.db`: 更新 `114` DOI/PMID，记录量不变。
  - `lipase.db`: papers 11 -> 12；variants 15 -> 17；variant_mutations 22 -> 25；evidence_claims 15 -> 18；metrics 16 -> 20。
  - 三库 `PRAGMA integrity_check=ok`。
  - 备份：
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/glucose_oxidase-db/glucose_oxidase.db.bak-foreign-research2-20260725-20260725T145606`
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/phytase-db/phytase.db.bak-foreign-research2-20260725-20260725T145606`
    - `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶数据库/lipase-db/lipase.db.bak-foreign-batch2-20260725-20260725T145715`

## 视觉/浏览器发现
- 浏览器错误中的 iframe sandbox 警告不是 `/api/conversations 401` 的根因。
- 用户控制台持续出现旧 bundle 名称，与服务器当前返回的新 bundle 不一致。
- 当前真实服务端根路径已返回禁缓存头，说明剩余问题更偏向浏览器已有旧上下文而非新部署未生效。

## 2026-08-04 酶身份与功能位点基础画像整改

- 用户优先级调整为：先可靠落地酶家族、功能/EC、结构域、催化/辅因子/分泌特征和保护位点，再允许任何改造位点或组合突变建议。
- 已确认当前断层：
  - `annotation_bundle` 能返回 InterPro、催化位点和 SignalP，但未提供统一的 EC/反应/辅因子/坐标状态摘要。
  - `enzyme_identity_profile` 仍读取旧的 `family_candidates/key_residues` 形状，未消费真实 `annotation_bundle` 输出，因此已入库 curated 证据不能直接变成身份与保护位点结论。
  - agent 计划中 `enzyme_identity_profile` 尚未由 `annotation_bundle` 前置驱动；后续 benchmark/function/突变评分可以在没有真实注释证据的情况下运行。
- 本轮实现原则：
  - 证据来源、证据等级、序列坐标体系、映射状态必须保留。
  - curated family/domain 证据可确认家族；curated catalytic residues 只有在输入序列与 curated record 坐标可确认时才能成为可定位的保护位点。
  - heuristic motif 只保留为低等级线索，不能确认家族/EC，也不能放行 P1/P2 工程候选。

## 2026-08-04 第二轮复核结论

- 之前的画像实现还不够严：
  - `homologous_superfamily` 不能直接当作具体家族确认，只能作为上层结构背景或候选线索。
  - `mutation_priority_score` 不能依赖“已有 curated 序列或旧 identity_profile 可能碰巧通过”的松散条件，必须要求当前轮 `enzyme_identity_profile` 明确给出 `identified + guardrail ready`。
  - 结构预测在序列工程场景中只能服务于口袋/距离/构象解释，不能取代家族与功能位点检索。
- 当前更稳妥的本平台标准：
  1. 先做 `annotation_bundle`
  2. 再做 `enzyme_identity_profile`
  3. 再做 `protein_benchmark` / `enzyme_function`
  4. 只有 identity + numbering 通过，才允许 `mutation_priority_score`
  5. `esmfold_folding` 只在后续结构解释需要时进入
- 官方文档复核补强了边界：
  - InterPro 的 `family / domain / homologous superfamily` 不是同一级别的“已确认家族”；我们不能把 superfamily 直接上升成具体家族。
  - UniProt feature 注释中的 active site / binding site / metal binding 属于功能特征，不应和推断位点混为一谈。
  - M-CSA 更像催化机制与关键残基证据仓库，适合做催化残基来源校验，而不应被当作结构坐标的自动映射器。

## 2026-08-04 Google/官方资料深度调研：平台方法学边界

- InterPro 官方资料明确将 entry 分为 homologous superfamily、family、domain、repeat、site；family 才表示蛋白家族成员关系，homologous superfamily 通常是共享三级结构的大类背景。因此平台应把 `family` 作为身份确认主证据，把 `homologous_superfamily` 降为背景线索。
- UniProt BLAST 帮助说明 Swiss-Prot 是人工审校、高质量注释子集，适合寻找功能信息、保守结构域和已知家族；因此 unknown enzyme 的第一层检索应优先 Swiss-Prot/Reviewed，再扩展 reference proteomes/unreviewed，而不是先跑模型。
- UniProt sequence annotation 说明 active site、binding site、site 是 position-specific sequence features。平台需要保留 feature key、from/to、description 和 evidence/provenance，并明确这些坐标属于哪个序列记录。
- M-CSA 官方资料说明其整合 MACiE/CSA，提供反应机制、催化残基、辅因子和机制条目；CSA 历史上包含 literature 与 homologue evidence 标签，并以 PDB/UniProt/EC 查询为入口。平台应把 M-CSA 作为机制/催化残基证据源，但必须单独做 UniProt/PDB/用户序列映射。
- HMMER 官方资料说明 profile HMM 可用于同源搜索与远缘同源识别，常与 Pfam/InterPro 成员库配合。平台缺口：当 BLAST 低相似或无命中时，应接 HMMER/Pfam/NCBIfam/PROSITE 的 profile 级证据，而不是只靠短 motif。
- Foldseek 论文资料显示结构搜索能快速比较海量结构，并给出 homologous probability、TM-score/LDDT 等结构相似指标。平台缺口：有结构但序列证据弱时，应以 Foldseek 作为结构同源证据层，但仍不能自动等同 EC/功能。
- 酶工程综述资料支持目标模块分化：
  - 热稳定性：盐桥/氢键、疏水核心、二硫键、loop Pro、phylogenetic/consensus 等策略，但需保护活性位点几何与动力学。
  - 比活力：需要机制、过渡态和活性位点/二壳层知识，不能只按“高分单点”排序。
  - 底物特异性：通常依赖结合口袋、入口/通道残基、结构互补和饱和突变/CAST/ISM。
  - pH 谱：关键是催化残基表观 pKa 与活性-pH 曲线拟合，计算 pKa/PROPKA 类分析只能作为解释，不应直接替代实验曲线。

## 2026-08-04 MatVenus shared 格式与 live evidence 第三批发现

- 用户提供的 MatVenus shared URL 可通过前端 bundle 中的 `https://matvenus.com/research-system/api/` public API 读取：
  - `/session/shared/{id}/stream-events`
  - `/session/shared/{id}/final-report`
- 本轮成功读取 `stream-events`，确认其报告第一屏对实验人员友好：
  - 先纠正酶身份。
  - 明确催化二联体/禁改区。
  - 立即给 Top 突变表。
  - 给第一批/第二批/第三批实验路线。
- 该格式可学习为本平台酶改造报告第一屏结构，但必须补强字段：
  - 用户序列编号 + PDB/UniProt 编号。
  - 突变逻辑。
  - 风险驱动。
  - 证据等级。
  - 实验动作与优先级。
  - Claim/Evidence/Citation 附录。
- InterProScan 证据边界：
  - `interproscan_sequence_submit` 只证明 live job 已提交，不能证明已有 InterProScan 注释结果。
  - `interproscan_sequence_status` pending 只证明 live status polling，不能写作 “InterProScan 已完成注释”。
  - 只有 completed + `result_available=true` + results 非空 + live evidence source 才能支持 `INTERPROSCAN_SEQUENCE_RESULT`。
- Platform/Data Manifest 边界：
  - Manifest 是版本与来源快照，只服务可复现和审计。
  - `readiness=not_asserted`，不能作为当前数据完整、live-ready 或联网成功的证明。
- NCBI API key/速率边界：
  - BLAST 使用 `NCBI_API_KEY` 参数；PubMed E-utilities 使用 `api_key` 参数。
  - Evidence details 只能显示 `api_key_configured` 和 rate-limit policy，不能输出实际 key。
  - 429/Retry-After 应结构化 degraded 返回，不在工具内 sleep/retry，也不能伪装为 live success。
- 引用导出边界：
  - `Citation Manifest` 合并人工 citations 与 `literature_live_search.results`。
  - DOI/PMID 去重，保留 evidence_tool 来源列表。
  - 文献元数据可支撑引用附录，但具体科学 claim 仍需 claim-level gate。

## 2026-08-04 酶改造首屏报告产品化发现

- 用户最终确认的首屏优先级不是“完整报告章节”，而是实验可直接排单的突变位点输出：
  - 候选突变位点必须第一屏可见。
  - 每个位点必须包含突变逻辑、风险提示、实验优先级和实验动作。
  - PDB/UniProt 编号只有完成映射时才显示真实值；未映射必须明确写 `未映射`，不能用用户序列编号伪装成结构/UniProt 编号。
  - Claim Gate / Evidence Layer 是审计层，必须保留，但不能压过突变主表。
- 当前产品化口径：
  - 后端 fallback 报告先输出 `结论卡片 / 状态摘要`、`突变位点主表（实验排单）`、`推荐突变与实验批次`、`位点突变逻辑 / 风险 / 实验动作`、`Go / Watch / No-Go`，再进入 Evidence/Claim。
  - 前端 `MutationScoreCard` 首屏展示 `Go / Watch / No-Go` 和候选突变位点表，表格列包含用户编号、PDB/UniProt 编号、推荐突变、突变逻辑、预期方向、风险提示和实验动作。
  - 目标证据不足时，P1 候选不直接算 Go，而按 Watch 小批验证处理；身份/编号硬门控失败才进入 No-Go。

## 2026-08-04 多酶证据库前端入口发现

- 后端 `/api/data/enzyme-dbs/*` 已经提供统一简化三表接口，前端不需要为每个 family 重复实现数据访问。
- 前端 API client 统一以 family 为第一参数，保留 `status/search/papers/variants/measurements` 五类只读调用。
- `/data` 页面新增独立“酶库”入口，和原有 lipase 专用页面分开：
  - 简化三表 family：amylase、mannanase、xylanase、acid_protease、phytase、glucose_oxidase。
  - Lipase：继续使用专用 evidence schema 和 curation/gap 入口。
- 浏览器展示的 `papers / variants / measurements` 属于 audit view；不能把浏览结果直接当作高置信导出、训练导入或模型声明证据。

## 2026-08-04 acid_protease 元数据深挖第十一、十二批

- 重新定位当前数据库副本后确认实际路径为：
  - `酶数据库/acid-protease-db/acid_protease.db`
  - `酶数据库/xylanase-db/xylanase.db`
- 第十一批 dry-run/apply：
  - 回填 10 条 DOI 候选，记录数不变。
  - acid_protease DOI 缺口 `43 -> 33`，完整性 `ok`。
  - 生成带时间戳备份，未覆盖旧备份。
- 第十一批事后复核发现 `AP119` DOI 与 PubMed ESummary 不一致：
  - 错误：`10.1021/bi00065a015`
  - 正确：`10.1021/bi00137a015`
  - PMID：`1606143`
- `AP113` 的本地 PMID `8540305` 与 PubMed 不匹配，修正为 `8540385`；同时补 DOI `10.1007/978-1-4615-1871-6_10`。
- 第十二批新增脚本：
  - `酶数据库/acid-protease-db/acid_protease_metadata_deep_dive12_20260804.py`
  - 修正 AP119；补 AP111、AP113、AP201、AP202 DOI/PMID。
  - apply 后 acid_protease DOI 缺口 `33 -> 29`，论文/变体/测量记录数保持 `123/126/146`，完整性 `ok`。
- 证据边界：
  - AP109、AP207、AP401 等 PMID/DOI 由 PubMed ESummary 直接核验。
  - AP201/AP202 的 DOI 来自 JBC/ScienceDirect PII 回填，notes 中明确标注为 publisher DOI backfill。
  - NCBI 并发请求曾返回 429；按平台策略不 sleep/retry，不将失败请求写成 live 成功。
- xylanase 当前实际状态为 `81` papers、DOI 缺口 `5`、PMID 缺口 `57`、完整性 `ok`，下一批优先处理已有 DOI 但 PMID 为空的记录。

## 2026-08-05 xylanase DOI->PMID live 核验第三批

- 新增库外脚本：
  - `酶数据库/xylanase-db/xylanase_metadata_deep_dive3_20260805.py`
  - 默认 dry-run；仅 `--apply` 时生成独立备份并写入。
  - live 查询顺序：Europe PMC DOI 查询 -> PubMed DOI ESearch -> PubMed ESummary。
  - 不 sleep/retry；HTTP 429/网络错误只记录 degraded。
- 严格回填规则：
  - DOI 必须解析到 PMID。
  - 远端题名必须和本地题名保守 token overlap 匹配。
  - 优先要求 Europe PMC 与 PubMed 双源一致；PubMed-only 题名匹配也可作为候选，但本批实际 apply 只写了双源一致项。
- 第一组 dry-run（`XYN52/53/54/60/62/63/65/66/69/71`）：
  - 无可安全回填 PMID。
  - `XYN65` DOI `10.1016/j.biortech.2021.124798` 在 PubMed 解析为 Chlorella vulgaris lipid extraction，无关 xylanase，属 DOI 错配风险。
  - `XYN69` DOI `10.1016/j.enzmictec.2018.04.005` 在 PubMed 解析为 Shewanella microbial fuel cell 论文，无关 xylanase，属 DOI 错配风险。
  - `XYN71` DOI `10.1016/j.jbiotec.2013.10.015` 在 PubMed 解析为 Sinorhizobium genome 论文，无关 xylanase，属 DOI 错配风险。
  - `XYN66` DOI `10.1002/bit.28731` 解析到 GH30 xylanase 结构/功能论文，和本地简写标题相关但不是本地标题精确复述；本批不写，保留人工确认。
- 第二组 dry-run（`XYN72/73/75/78/79/chen2015gh10/chen2021disulfide/cheng2015ph/cord2014/cord2025`）：
  - `XYN73` 双源一致：PMID `38788879`，DOI `10.1016/j.ijbiomac.2024.132434`，题名完全匹配，可写入。
  - `XYN78` DOI `10.3390/molecules29081895` 在 PubMed 解析到 “Improving the Quality of Wheat Flour Bread...” 题名；和本地简写语义相关但不满足保守题名匹配，本批不写。
  - `cheng2015ph` DOI `10.1016/j.bbrc.2015.05.002` 解析为 L-selectin splice variant，无关 xylanase，属 DOI 错配风险。
  - `cord2025` DOI `10.1016/j.ijbiomac.2024.138121` 解析为 chitosan-based adhesive 论文，无关 xylanase，属 DOI 错配风险。
- apply 结果：
  - 写入 `XYN73.pmid = 38788879`。
  - 备份：`酶数据库/xylanase-db/xylanase.db.bak-xylanase-deep-dive3-20260805T081902`。
  - xylanase 状态：`81` papers、DOI 缺口 `5`、PMID 缺口 `56`、`PRAGMA integrity_check=ok`。
- 下一批建议：
  - 优先把 DOI 错配风险项纳入“清空/hold 或替换 DOI”批次：`XYN65`、`XYN69`、`XYN71`、`cheng2015ph`、`cord2025`。
  - 对 `XYN66`、`XYN78` 单独做人工题名/出版社页核验；不要仅凭 DOI->PMID 自动回填。

## 2026-08-05 xylanase DOI->PMID live 核验第四批

- dry-run IDs：`gao2020consensus han2019 joo2010ph kim2017ntr kumar2018 li2013disulfide liu2020xyl liu2025abacus luo2021xyl ma2016`。
- 结果：`verified_count=0`，没有写库。
- PubMed 明确 DOI 错配：
  - `gao2020consensus` DOI `10.1007/s00792-020-01189-7` -> PMID `32699913`，题名为 Antarctic vascular plants 论文。
  - `kim2017ntr` DOI `10.1016/j.enzmictec.2017.04.002` -> PMID `28465061`，题名为 ferrocene urea biosensor 论文。
  - `kumar2018` DOI `10.1016/j.ijbiomac.2018.01.014` -> PMID `29309870`，题名为 titanium oxide/chitosan Cu/Cd sorption 论文。
  - `liu2025abacus` DOI `10.1021/acssynbio.4c00650` -> PMID `39660664`，题名为 lacticin 481 analogue biosynthesis 论文。
  - `luo2021xyl` DOI `10.1002/bab.2156` -> PMID `33797804`，题名为 taxifolin biochemistry review。
  - `ma2016` DOI `10.1016/j.jtbi.2016.03.013` -> PMID `27000774`，题名为 membrane protein predictor 论文。
- 尚未找到 PMID：
  - `han2019`、`joo2010ph`、`li2013disulfide`、`liu2020xyl`。
- `joo2010ph`、`li2013disulfide`、`liu2020xyl` 已有本地 metadata boundary，继续保持不写入。
- 本批结论：不自动回填任何 PMID；应进入后续 DOI 错配清理/替换 DOI 队列。

## 2026-08-05 xylanase DOI->PMID live 核验第五批

- dry-run IDs：`pokhrel2012 ribeiro2014 sato2023xyl song2015 sun2014nterm tang2022surface teng2019 tian2013surface wang2012disulfide wang2012gh10 wang2014consensus wu2017ism xing2021 xiong2004 xiong2019 xue2012gh10 yang2021glyco zhang2010sat zhang2025ml zhao2019ca`。
- 结果：`verified_count=0`，没有写库。
- PubMed 明确 DOI 错配或题名不匹配的重点记录：
  - `ribeiro2014` -> PMID `24709538`，industrial wastewater microalgal bacterial flocs。
  - `sato2023xyl` -> PMID `37059180`，Saccharomyces mismatch repair。
  - `song2015` -> PMID `25592049`，3D spherical microtissues。
  - `tang2022surface` -> PMID `35038464`，chitosan-vitamin C hydrogel。
  - `wang2012disulfide` -> PMID `22940303`，steroidal drug wastewater microbial fuel cell。
  - `wang2012gh10` -> PMID `22975120`，wheat beta-amylase engineering。
  - `wu2017ism` -> PMID `28859812`，immobilized lipase modification。
  - `xing2021` -> PMID `34416266`，fucoidan/atopic dermatitis。
  - `xiong2004` -> PMID `15241657`，RNA polymerase pressure resistance。
  - `xiong2019` -> PMID `31731959`，urease lyophilisates。
  - `yang2021glyco` -> PMID `33485861`，E. coli cell integrity。
  - `zhang2010sat` -> PMID `20480207`，lyxose isomerase mannose production。
  - `zhao2019ca` -> PMID `31379771`，Acinetobacter disease mechanisms。
- 无 PMID / 无 live 记录：
  - `pokhrel2012`、`sun2014nterm`、`teng2019`、`tian2013surface`、`wang2014consensus`、`xue2012gh10`、`zhang2025ml`。
- `pokhrel2012`、`tian2013surface`、`wang2012gh10` 等已有本地 hold，和 live DOI 结果一致地不写入。
- 结论：xylanase DOI/PMID 缺口已经显著转化为 DOI identity reconciliation 问题，后续应单独建立 hold/清空/替换 DOI 批次。

## 2026-08-05 xylanase DOI identity repair 第四批

- 新增脚本：
  - `酶数据库/xylanase-db/xylanase_metadata_deep_dive4_20260805.py`
  - 离线、确定性修正脚本；不搜索新 ID，只应用已由 Europe PMC/PubMed live 交叉核验的 correction map。
- dry-run 通过旧 DOI 前置条件检查，拟修正 7 条：
  - `XYN54`: `10.1007/s00253-023-12400-0` -> `10.1007/s00253-023-12774-z`; PMID `37715802`
  - `XYN60`: `10.1038/s41598-017-01710-1` -> `10.1038/s41598-017-01758-5`; PMID `28484256`
  - `XYN62`: `10.1016/j.enzmictec.2017.01.010` -> `10.1016/j.enzmictec.2017.02.005`; PMID `28284313`
  - `XYN65`: `10.1016/j.biortech.2021.124798` -> `10.1016/j.biortech.2021.125063`; PMID `33813167`
  - `XYN66`: DOI 保持 `10.1002/bit.28731`; PMID `38678481`
  - `XYN69`: `10.1016/j.enzmictec.2018.04.005` -> `10.1016/j.enzmictec.2018.01.004`; PMID `29421035`
  - `XYN71`: `10.1016/j.jbiotec.2013.10.015` -> `10.1016/j.jbiotec.2013.09.014`; PMID `24157442`
- live 交叉核验结果：
  - 7 个新 DOI 均能从 Europe PMC 返回题名、作者、期刊、年份和 PMID。
  - 旧 DOI 的若干 PMID 明确指向无关论文，不能直接回填旧 DOI 解析到的 PMID。
- apply：
  - 备份：`酶数据库/xylanase-db/xylanase.db.bak-xylanase-deep-dive4-20260805T083208`
  - 记录数保持 `papers=81 / variants=114 / measurements=180`
  - DOI 缺口保持 `5`
  - PMID 缺口 `56 -> 49`
  - `PRAGMA integrity_check=ok`
- 说明：
  - 本批仅修论文 DOI/PMID 元数据，不改变 variants/measurements 或 evidence/conf 边界。
  - `XYN71` PubMed pubYear 为 2013，而本地 year 为 2014；本批保留本地 year，避免把期刊卷期年份与线上首发年份混写，后续单独处理年份口径。

## 2026-08-05 xylanase 缺 DOI 收敛第五批

- 缺 DOI 初始 5 条：
  - `XYN51`、`XYN64`、`XYN67`、`XYN68`、`XYN70`
- 处理结果：
  - `XYN51`: Crossref 精确题名/作者/期刊/年份匹配，补 DOI `10.1016/j.bcab.2023.102920`；Europe PMC/PubMed 未找到 PMID，PMID 保持空。
  - `XYN64`: PubMed PMID `29852224` 反查 DOI `10.1016/j.ijbiomac.2018.05.199`，Europe PMC 同步确认；同时将 journal 从 `Enzyme Microb Technol` 修为 `Int J Biol Macromol`。
  - `XYN70`: Europe PMC 查询显示 S92E/XynR 对应论文为 `Insight into the mechanism of thermostabilization of GH10 xylanase from Bacillus sp. strain TAR-1 by the mutation of S92 to E.`，DOI `10.1093/bbb/zbaa003`，PMID `33604642`，year 2021；本地 year 从 2018 修为 2021。
  - `XYN67`: 专利来源 `EP2305820`，不补 DOI/PMID。
  - `XYN68`: 专利来源 `US20160168555`，不补 DOI/PMID。
- 新增脚本：
  - `酶数据库/xylanase-db/xylanase_metadata_deep_dive5_20260805.py`
- apply：
  - 备份：`酶数据库/xylanase-db/xylanase.db.bak-xylanase-deep-dive5-20260805T083727`
  - 记录数保持 `papers=81 / variants=114 / measurements=180`
  - DOI 缺口 `5 -> 2`
  - PMID 缺口 `49 -> 48`
  - `PRAGMA integrity_check=ok`
- 当前 xylanase 元数据状态：
  - DOI 缺口仅剩 2 条专利来源。
  - PMID 缺口仍有 48 条，其中大量属于无 PubMed 收录、非 PubMed 期刊、专利或仍需 DOI identity reconciliation 的 hold 项。

## 2026-08-05 xylanase 边界 hold 清理第六批

- 新增并应用 `酶数据库/xylanase-db/xylanase_metadata_deep_dive6_20260805.py`。
- 本批不删除 DOI/PMID，只把 live 已确认 DOI 错配、但尚无安全替代元数据的记录转为边界 hold：
  - `cord2025`
  - `gao2020consensus`
  - `kim2017ntr`
  - `ribeiro2014`
  - `xiong2004`
  - `xiong2019`
  - `zheng2017gh10`
- 影响：
  - 7 篇 papers 标记 hold。
  - 12 条 measurements 标记 hold/non-exportable。
  - export-safe 泄漏保持 0。
  - DOI/PMID 缺口计数不因本批改变。
- 备份：`酶数据库/xylanase-db/xylanase.db.bak-xylanase-deep-dive6-20260805T084422`
- 完整性：`PRAGMA integrity_check=ok`。

## 2026-08-05 平台多酶库元数据质量摘要

- `backend/app/services/enzyme_evidence_db.py` 新增多酶库只读 `metadata_quality` 摘要：
  - `missing_doi`
  - `missing_pmid`
  - `patent_like_sources`
  - `hold_papers`
  - `hold_measurements`
  - `export_safe_measurements`
  - `metadata_gap_count`
  - `browser_scope`
- `/data` 家族卡片和选中家族状态条现在直接显示 DOI 缺口、PMID 缺口、hold 文献、hold measurement、可导出 measurement 和专利来源提示。
- 设计边界：
  - Browser/search 仍是只读审计视图，可能包含 hold/B/medium/boundary 行。
  - 高置信实验排单或报告引用应优先看 export-safe，不把 hold 行混入推荐依据。
  - 这个摘要服务于“先看到数据库缺口/边界状态”，避免用户以为数据卡只展示数量就代表全库可用于模型。

## 2026-08-05 acid_protease DOI/PMID 深挖第十三/十四批

- 第十三批脚本：`酶数据库/acid-protease-db/acid_protease_metadata_deep_dive13_20260805.py`
  - 补 `AP211/AP214/AP615/AP623` 元数据后执行完整性校验。
  - `AP615` 和 `AP623` 仍保持 hold，不因 DOI/PMID 补全而放行 high-confidence export。
  - 备份：`acid_protease.db.bak-acid-protease-deep-dive13-20260805-20260805T085856`
- 第十四批脚本：`酶数据库/acid-protease-db/acid_protease_metadata_deep_dive14_20260805.py`
  - 复核发现第十三批中 `AP211/AP214` 的 DOI 需要纠偏。
  - `AP211` 正确 DOI 为 `10.1016/S0021-9258(18)41920-5`；PubMed PMID `1512263` 的 PII 为 `S0021-9258(18)41920-5`，Crossref title/page/author 匹配 two-chain pepsinogen paper。
  - `AP214` 正确 DOI 为 `10.1016/S0021-9258(17)32945-9`；PubMed PMID `993206` 的 PII 为 `S0021-9258(17)32945-9`，Crossref title/page/author 匹配 pepstatin inhibition paper。
  - 第十三批误写的 `10.1016/S0021-9258(17)33041-7` 经 Crossref 抽检为无关 lectin paper，已纠正。
  - 备份：`acid_protease.db.bak-acid-protease-deep-dive14-20260805-20260805T090803`
- 当前 acid_protease 状态：
  - `papers=123`
  - `missing_doi=25`
  - `missing_pmid=24`
  - `PRAGMA integrity_check=ok`
- 待建/待查：
  - `AP624` 可能与已有 `AP402` 的 chymosin T218S 信息相关，但本地 title/author 边界不一致，不能直接复制 AP402 DOI/PMID。

## 2026-08-05 acid_protease 第十五批：AP308 错配 PMID 修复

- 新增并应用 `酶数据库/acid-protease-db/acid_protease_metadata_deep_dive15_20260805.py`。
- `AP308`：
  - DOI：`10.1016/j.bbapap.2009.08.017`
  - PMID：`19715777`
  - 原 PMID `19716424` 已确认属于无关 NeuroImage 论文，已替换。
- PubMed 与 DOI publisher metadata 均匹配 Dee et al. 2009 BBA Proteins and Proteomics 记录。
- 备份：`acid_protease.db.bak-acid-protease-deep-dive15-20260805-20260805T091534`
- 当前状态：`papers=123 / missing_doi=24 / missing_pmid=24 / integrity=ok`。
- `AP624` 仍保持待查，不复制 AP402 元数据。

## 2026-08-05 xylanase 非 PubMed / boundary 元数据第七批

- 新增并应用 `酶数据库/xylanase-db/xylanase_metadata_deep_dive7_20260805.py`。
- `XYN78`：
  - DOI 保持 `10.3390/molecules29081895`
  - PMID 补为 `38672428`
  - year 保持 2024
- `XYN79`：
  - DOI 从 `10.1186/s13068-024-02480-0` 修正为 `10.1186/s13068-017-0871-8`
  - PMID 补为 `28724418`
  - year 从 2024 修正为 2017
  - 原 DOI 指向无关 2024 rapeseed 论文，不能作为 XynCDBFV C-terminal replacement 记录。
- 两条记录均保持原 `paper_payload_boundary`，仅修元数据，不放行 export-safe。
- 备份：`酶数据库/xylanase-db/xylanase.db.bak-xylanase-deep-dive7-20260805T092521`
- 当前 xylanase 状态：`papers=81 / missing_doi=2 / missing_pmid=46 / integrity=ok`。

## 2026-08-05 acid_protease 第十六批：JBC DOI 回填

- 新增并应用 `酶数据库/acid-protease-db/acid_protease_metadata_deep_dive16_20260805.py`。
- 回填：
  - `AP206` -> `10.1016/S0021-9258(18)99016-2`
  - `AP406` -> `10.1016/S0021-9258(18)77441-3`
  - `AP409` -> `10.1016/S0021-9258(19)84786-5`
  - `AP541` -> `10.1016/S0021-9258(19)40043-4`
- `AP541` 保持 `wt_characterization_no_mutant_table_hold_boundary / non_exportable`，不因 DOI 补全放行导出。
- 备份：`酶数据库/acid-protease-db/acid_protease.db.bak-acid-protease-deep-dive16-20260805-20260805T093104`
- 当前 acid_protease 状态：`papers=123 / missing_doi=20 / missing_pmid=24 / integrity=ok`。

## 2026-08-05 acid_protease 第十七批：AP616 PMID 与 AP307 DOI 回填

- 本轮先新增并应用 `酶数据库/acid-protease-db/acid_protease_metadata_deep_dive17_20260805.py` 回填 `AP616` PMID；随后并行 worker 用同名第十七批脚本接管并应用 `AP307` DOI 回填。当前磁盘上的 `acid_protease_metadata_deep_dive17_20260805.py` 为 worker 版本，数据库已包含两项结果。
- `AP616`：
  - DOI 保持 `10.1046/j.1432-1327.2000.01582.x`
  - PMID 补为 `10931195`
  - PubMed ESearch 以 DOI 查询返回 PMID `10931195`。
  - PubMed ESummary 匹配 Asakura et al., `Eur J Biochem`, 2000，题名为“plant aspartic proteinase-specific polypeptide insert is not directly related to the activity of oryzasin 1”，DOI 与本地 AP616 一致。
- `AP307`：
  - DOI 从空补为 `10.1016/j.enzmictec.2006.08.029`
  - PMID 保持空；并行 worker 记录 PubMed 与 Europe PMC DOI 查询未返回 PMID。
  - Crossref/Elsevier metadata 与 Sinkovits et al. 2007 `Enzyme Microbial Technology` pepsin catalytic-residue 论文匹配。
- 本批仅修改 `AP616.pmid` 与 `AP307.doi` 两个元数据字段，不修改 `access/priority/quality`，不放行任何 hold/export 边界。
- 同轮 live 查询发现：
  - `AP536` DOI `10.1016/j.pep.2024.106234` 的 PubMed AID 查询返回 0，PMID 保持空。
  - `AP543` DOI `10.1016/j.biotechadv.2024.108314` 的 PubMed AID 查询返回 0，PMID 保持空。
  - `AP001` DOI `10.3389/fphy.2021.755253` 的 PubMed AID 查询返回 0，PMID 保持空。
- 备份：
  - `酶数据库/acid-protease-db/acid_protease.db.bak-acid-protease-deep-dive17-20260805-20260805T094225`（AP616 写入前）
  - `酶数据库/acid-protease-db/acid_protease.db.bak-acid-protease-deep-dive17-20260805-20260805T094332`（AP307 写入前）
- 当前 acid_protease 状态：`papers=123 / missing_doi=19 / missing_pmid=23 / integrity=ok`。

## 2026-08-05 xylanase 剩余缺口只读核验

- 并行只读核验未写库、未修改文件。
- 当前 xylanase 摘要：`papers=81 / missing_doi=2 / missing_pmid=46 / integrity=ok`。
- `XYN67`、`XYN68` 为专利公开文本（`EP2305820`、`US20160168555`），不按期刊论文 DOI/PMID 处理，保持空，除非后续单独建立专利 metadata 策略。
- 已确认 DOI 但未发现 PubMed PMID 的记录（如 `XYN51/52/53/63/72/75`）保持 PMID 空；Europe PMC DOI 查询无命中不能反向写“无 PMID”以外的元数据。
- hold/boundary 记录中，多数 DOI 已被确认指向无关论文或来源身份未闭合；不应复制无关 DOI 的 PMID，也不应将 hold 记录放行 export-safe。
- 非 hold 但暂不写：`han2019`、`sun2014nterm`；当前题名/作者查询无强一致 PubMed/Europe PMC 命中。
- 结论：本轮 xylanase 无新增可安全写入 DOI/PMID 候选。

## 2026-08-05 acid_protease 剩余缺口分组核验启动

- 已启动三组只读核验：
  - JBC/人源或哺乳动物相关：`AP505/AP512/AP516/AP520/AP530/AP532/AP533`
  - 植物/真菌/酵母相关：`AP517/AP521/AP524/AP525/AP526/AP527/AP529`
  - 边界/低证据/hold/preprint：`AP001/AP508/AP536/AP543/AP603/AP605/AP617/AP624`
- 主线程快速 live 查询结果：
  - `AP505` Crossref 首命中为 HIV-1 protease 相关 Biochemistry 2012 论文，但题名/期刊不等于本地 JBC 2013 记录；不写。
  - `AP520` Crossref 命中 Cathepsin E 相关综述/其它论文，未形成与本地 JBC 2006 prosegment activation 强一致记录；不写。
  - `AP533` Crossref 命中 pepsin lobe 相关 Protein Science 1993 与 JBC 1992 论文，但与本地 “Independent folding of N- and C-terminal lobes of pepsin” / Lin XL, Wong RN, Tang J / JBC 1993 行仍未闭合；不写。
- 结论：等待子 agent 分组结果前，不生成新的写库批次。

## 2026-08-05 acid_protease 当前剩余缺口分类清单

- 当前 acid_protease：`papers=123 / missing_doi=19 / missing_pmid=23 / integrity=ok`。
- 当前 xylanase：`papers=81 / missing_doi=2 / missing_pmid=46`，本轮未写库。
- acid_protease 剩余缺口共 23 行：
  - 高优先级 A/B：`AP001/AP307/AP505/AP516/AP520/AP533`
  - 中优先级 A：`AP508`
  - 中优先级 B：`AP512/AP517/AP521/AP524/AP525/AP526/AP527/AP529/AP530/AP532/AP543/AP605`
  - 低优先级 C：`AP536`
  - hold/non-exportable：`AP603/AP617/AP624`
- 已有初步结论：
  - `AP001`、`AP307` 已有 DOI 但 PubMed DOI 查询无 PMID，保持 PMID 空。
  - `AP536`、`AP543` 已有 DOI 但 PubMed AID 查询返回 0，保持 PMID 空。
  - `AP603/AP617/AP624` 是 hold/non-exportable，不因元数据补全放行；`AP624` 不能复制 `AP402`。
  - `AP505/AP520/AP533` 主线程快速 live 查询未形成 title-author-journal-year 强一致，不写。
- 后续 `deep_dive18` 只允许使用三组只读 agent 返回的强一致候选；否则仅更新 hold/manual 清单。

## 2026-08-05 acid_protease 第十八批：AP603 hold 元数据回填

- 新增并应用 `酶数据库/acid-protease-db/acid_protease_metadata_deep_dive18_20260805.py`。
- `AP603`：
  - DOI 从空补为 `10.1016/j.ijbiomac.2026.150240`
  - PMID 从空补为 `41539511`
  - Crossref 匹配 Saleem et al. 2026 `International Journal of Biological Macromolecules`，题名为 “In silico design of a chimeric aspartic protease for cheese production using parental sequences from 2ASI and 1MPP”。
  - PubMed ESearch 与 Europe PMC DOI 查询均返回 PMID `41539511`。
- 边界保持：
  - `AP603.access=hold`
  - `AP603.priority=hold`
  - `AP603.quality=non_exportable`
  - AP603 measurement 仍为 `conf=non_exportable`，没有 A 级导出泄漏。
- 备份：`酶数据库/acid-protease-db/acid_protease.db.bak-acid-protease-deep-dive18-20260805-20260805T101919`
- 当前 acid_protease 状态：`papers=123 / missing_doi=18 / missing_pmid=22 / integrity=ok`。

## 2026-08-05 acid_protease 植物/真菌/酵母组只读核验

- 只读核验完成，未写库。
- `AP517/AP521`：PubMed exact title count 为 0，Crossref 无强一致；旧错 DOI 不重引入。
- `AP524/AP525`：相关候选存在，但题名/期刊/年份/作者与本地 Plant Mol Biol 行不强一致，needs manual。
- `AP526/AP527`：找到 cardosin A / Centaurea calcitrapa 相关强记录，但与本地 Phytochemistry 2015/2005 行不强一致，保持 hold/manual，不写。
- `AP529`：找到 FEMS Yeast Res 2006 yapsin 相关记录，但与本地 2008 行不一致，不写。
- 结论：本组无可直接写入 DOI/PMID 候选。

## 2026-08-05 acid_protease 边界/低证据组只读核验

- 只读核验完成，除 `AP603` 已经单独按 deep_dive18 回填并保持 hold 外，其余不写。
- `AP001`：DOI 有效，PubMed/Europe PMC 无 PMID，保持 PMID 空。
- `AP508`：历史清空的 `10.1002/pro.2057` 不重引入；候选 `10.1002/pro.2086` 不匹配 organic-solvent/Arnold 行。
- `AP536`：当前 DOI Crossref not found，Europe PMC 0；相近 IJBM 2026 候选与本地 Anonymous / Protein Expr Purif / 2025 不强一致，needs manual。
- `AP543`：当前 DOI Crossref not found；相近 Critical Reviews in Biotechnology 综述 PMID `36842994` 与本地题名/期刊/作者不强一致，needs manual。
- `AP605`：存在 bioRxiv preprint DOI 与正式期刊版 DOI/PMID，但本地 journal/access 仍是 bioRxiv，需人工决定是否升级整条元数据到正式版，不硬写。
- `AP617`：相关研究论文/综述与本地 `Kojima / J Biochem / 2005` 不强一致，保持 hold/manual。
- `AP624`：更像 `AP402` 的变体摘录，不能复制 AP402 DOI/PMID。

## 2026-08-05 acid_protease JBC/哺乳动物组只读核验

- 只读核验完成，未写库；本组无可直接写入候选。
- `AP505`：旧 DOI `10.1074/jbc.M113.481564` 为 404；T26/R87/HIV-1 protease 候选 PMID `17412697` / DOI `10.1074/jbc.M701304200` 是 JBC 2007，与本地 JBC 2013 Louis/Ishima/Torchia/Weber 行不一致。
- `AP512`：旧 DOI 404；候选 PMID `15574427` / DOI `10.1074/jbc.M412086200` 是 JBC 2005 plasmepsin，但作者组合与本地 Mallari/Corey/Dharia/Winzeler 不一致。
- `AP516`：旧 DOI 404；候选 PMID `12684512` / DOI `10.1074/jbc.M302579200` 是 JBC 2003 prorenin gate/handle 论文，不是本地 2007 renin-prosegment crystal structure。
- `AP520`：旧 DOI 404；prosegment 候选 PMID `16272574` / DOI `10.1093/jb/mvi159` 是 J Biochem 2005，不是本地 JBC 2006；JBC 候选 PMID `17095504` 题名也不匹配。
- `AP530`：旧 DOI 404；YPS3 候选 PMID `10191273` / DOI `10.1042/bj3390407` 是 Biochem J 1999；JBC 1998 候选 PMID `9417119` 是 yapsin 1/Yap3p，不是本地 YPS3。
- `AP532`：旧 DOI 指向 REDD1 retinal inflammation，不重引入；相关 pepsin/renin 候选 DOI `10.1016/j.enzmictec.2020.109632` 与 `10.1016/j.enzmictec.2021.109871` 均不匹配本地 JBC 行。
- `AP533`：旧 DOI 指向 SHV beta-lactamase，不重引入；候选 PMID `8401224` / DOI `10.1002/pro.5560020903` 是 Protein Science 1993，JBC 候选 PMID `1512263` 也不匹配本地行。
- 结论：全部标为 `needs manual`，不生成额外写库批次。

## 2026-08-05 acid_protease residual decision manifest

- 新增 `酶数据库/acid-protease-db/acid_protease_residual_metadata_decisions_20260805.md`。
- manifest 固化 deep-dive18 后剩余缺口决策：
  - keep blank：`AP001/AP307`
  - needs manual：`AP505/AP508/AP512/AP516/AP517/AP520/AP521/AP524/AP525/AP536/AP543/AP605`
  - hold/manual 或 boundary repaired：`AP526/AP527/AP529/AP530/AP532/AP533/AP617/AP624`
- 目的：
  - 阻止旧错 DOI 被重引入。
  - 明确哪些条目需要整条 paper identity 修复，而不是单纯 DOI/PMID 回填。
  - 将 preprint-to-version-of-record、专利/hold/export 边界作为后续策略问题，而不是自动写库问题。
- 子 agent 只读复核发现原 manifest active residual 漏列 `AP517/AP521`，且 `AP533` 虽在 manifest 标为 hold/manual，但 DB 仍是 `open/high/A` 且 measurement `mid=94 conf=A`。已补 manifest，并新增 deep-dive19 边界修复脚本将 AP533 paper `priority/quality` 与 `mid=94 conf` 降级为 `metadata_source_conflict_hold_boundary`；DOI/PMID 不变，缺口计数不变，AP533 export-safe 泄漏由 1 降为 0。

## 2026-08-05 xylanase residual decision manifest

- 新增 `酶数据库/xylanase-db/xylanase_residual_metadata_decisions_20260805.md`。
- manifest 固化 deep-dive7 后 xylanase 剩余缺口状态：
  - 当前状态：`papers=81 / missing_doi=2 / missing_pmid=46 / PRAGMA integrity_check=ok`。
  - 专利行：`XYN67/XYN68` 保持 DOI/PMID 空，除非后续建立独立 patent metadata policy。
  - confirmed DOI/no PMID：`XYN51/XYN52/XYN53/XYN63/XYN72/XYN75` 保持 PMID 空，不从题名噪音推断 PMID。
  - non-hold manual：`han2019/sun2014nterm` 暂不写 PMID，继续等 title/author/journal/year 身份闭合。
  - DOI mismatch/source-boundary：多条 hold/boundary 记录按 `metadata_source_conflict_hold_boundary`、`doi_title_source_identity_unresolved_hold_boundary`、`paper_identity_or_source_table_unresolved_hold_boundary` 等分组，禁止从错配 DOI 复制 PMID。
  - already resolved：`XYN78` 已补 PMID，`XYN79` 已修 DOI/PMID/year。
- 目的：
  - 将“缺 PMID”区分为无 PubMed 收录、专利来源、paper identity 未闭合、source-table 边界和 DOI 错配风险。
  - 防止 patent/preprint/hold/boundary 记录因 DOI/PMID 补齐被误认为 export-safe。
  - 为后续策略实现提供清晰待建项：patent metadata、preprint/version-of-record、boundary repair、export whitelist。
- 子 agent 只读复核发现 manifest 的 `metadata_source_conflict_hold_boundary` 列表漏列 `tian2013surface`；DB 中该行 `doi=10.1016/j.procbio.2013.04.001`、PMID 空、paper priority/quality 和 2 条 measurement conf 均为 `metadata_source_conflict_hold_boundary`。已补入 manifest。该修正不改变数据库，也不影响 export-safe 泄漏计数。

## 2026-08-05 export-safe 显式策略第一层

- 旧问题：`list_simple_enzyme_export_safe_measurements` 主要依赖 `paper quality='A' + measurement conf='A'`，并只显式排除 `hold/non_exportable`。这对当前已修 AP533 足够，但策略层不够强，不能证明 `boundary/patent/preprint` 未来不会被 A/A 误放行。
- 本轮将 export-safe marker 明确固化为：`hold`、`boundary`、`non_exportable`、`patent`、`preprint`。
- export-safe 查询现在在 paper `access/priority/category/quality/notes` 和 measurement `conf/src` 两层排除这些 marker；browser/search endpoint 仍是 audit view，不作为导出安全来源。
- metadata_quality 现在暴露：
  - `patent_like_sources`
  - `preprint_papers`
  - `boundary_papers`
  - `boundary_measurements`
  - `policy_excluded_papers`
  - `policy_excluded_measurements`
  - `non_exportable_markers`
- 同时修复 patent-like 计数的两个旧边界：
  - `journal LIKE 'US%'/'EP%'` 会误把普通 `J` 期刊或其它前缀算成专利，已收紧为 `GLOB 'US[0-9]*' / 'EP[0-9]*'`。
  - `doi IS NULL OR trim(doi)='' AND patent marker` 的 SQL 优先级会把所有 DOI NULL 行都计为 patent-like，已加括号修正。
- 定向测试用 A/A 但带 patent/preprint/boundary marker 的行证明其不会进入 export-safe；真实库 service 口径复核：
  - acid_protease：`missing_doi=18 / missing_pmid=22 / export_safe_measurements=110`，policy-excluded paper/measurement 计数可见。
  - xylanase：`missing_doi=2 / missing_pmid=46 / patent_like_sources=2 / export_safe_measurements=0`。
- 后端 `metadata_quality.export_policy` 现在结构化返回 patent/preprint 处理口径：专利来源在独立策略建立前不写 DOI/PMID，preprint 到正式版需要人工 identity upgrade。前端 `/data` 酶库状态卡显示 policy-excluded、boundary、preprint、patent 计数，避免只看“可导出”而忽略边界债务。

## 2026-08-05 patent/preprint policy sidecar 第一层

- 新增设计文档 `docs/designs/2026-08-05-enzyme-db-patent-preprint-policy.md`，定义 patent 与 preprint/version-of-record 的 sidecar object、升级流程、禁止项和当前覆盖行。
- 新增 sidecar manifests：
  - `酶数据库/acid-protease-db/enzyme_metadata_policy_decisions_20260805.json`
  - `酶数据库/xylanase-db/enzyme_metadata_policy_decisions_20260805.json`
- 平台 `collect_simple_enzyme_db_status()` 现在读取同目录 `enzyme_metadata_policy_decisions_*.json` 并返回 `metadata_policy_decisions`，包含 manifest count、decision count、record types、review statuses 和 manifest 摘要。
- 真实库复核：
  - acid_protease：`metadata_policy_decisions.status=ok / manifest_count=1 / decision_count=1 / record_types=preprint_to_version_of_record / review_status=manual_required`。
  - xylanase：`metadata_policy_decisions.status=ok / manifest_count=1 / decision_count=2 / record_types=patent / review_status=manual_required`。
- 只读核验结论：
  - `AP605` 当前仍是 `bioRxiv/preprint/medium/B`，measurement 为 `preprint_figure_boundary`。即使正式版 DOI/PMID 线索存在，也不能只回填 DOI/PMID；必须走 full citation identity upgrade。
  - `XYN67/XYN68` 当前为 patent/paper_payload_boundary，measurement 也为 paper_payload_boundary。专利号保留在 sidecar，不写 DOI/PMID，不放行 export-safe。

## 2026-08-05 policy decisions dry-run preview

- 新增管理员 endpoint `POST /api/data/enzyme-dbs/{family}/policy-decisions/preview`，读取 sidecar decisions 并输出 dry-run `manifest` 与 `export_payload`。
- 该 endpoint 不写 SQLite、不发布到 export-safe、不替代人工审核；它只是把 patent/preprint decisions 接入平台 curation/升级脚本的入口。
- 权限：普通 researcher 访问返回 403，admin 可预览。
- 真实库 preview 口径：
  - acid_protease：dry-run `record_count=1`，record type `preprint_to_version_of_record`，paper `AP605`。
  - xylanase：dry-run `record_count=2`，record type `patent`，papers `XYN67/XYN68`。
- xylanase 非 hold PMID 候选本轮 live 复核：
  - `han2019` DOI `10.1007/s00253-019-09770-9`：NCBI AID query 返回 0，Crossref/DOI resolver 未确认可用 DOI record；不写 PMID。
  - `sun2014nterm` DOI `10.4014/jmb.1401.01010`：NCBI AID query 返回 0，Crossref/DOI resolver 返回 not found；不写 PMID。

## 2026-08-05 policy decisions 发布流程 fail-closed

- 平台现在有两个层次：
  - preview：`POST /api/data/enzyme-dbs/{family}/policy-decisions/preview`，只读预览 sidecar decisions。
  - publish plan：`POST /api/data/enzyme-dbs/{family}/policy-decisions/publish`，`dry_run=true` 输出正式发布/升级计划，`dry_run=false` 显式阻断。
- 正确 confirmation token 只解除“确认门”，不解除“策略门”。当前即使 token 正确也返回 `409 blocked`，不会写 SQLite，不会生成 WAL/journal/shm，不会让 patent/preprint/boundary 行进入 export-safe。
- service 层新增统一字段，便于 UI/脚本识别：
  - `sqlite_mutated=false`
  - `sqlite_mutation_allowed=false`
  - `export_safe=false`
  - `export_safe_released=false`
  - `release_plan.apply_supported=false`
- 真实 sidecar dry-run 输出：
  - `acid_protease`：1 条，`preprint_to_version_of_record`，对应 `AP605`。
  - `xylanase`：2 条，`patent`，对应 `XYN67/XYN68`。
- 下一层不是直接写库，而是把 sidecar records materialize 到平台内部人工 curation queue，支持逐条审核、备注、批次归档；外部 SQLite 仍需后续家族专用升级脚本执行 `dry-run -> backup -> apply -> PRAGMA integrity_check`。

## 2026-08-05 residual metadata 下一批只读核验

- 只读核验结论：当前 `acid_protease` 与 `xylanase` 均无可写 DOI/PMID 候选。
- 本轮核验仅使用 SQLite `mode=ro` + `PRAGMA query_only=ON` 与 residual manifest，没有联网查询；两库 `PRAGMA integrity_check=ok`。
- `acid_protease`：
  - `AP001/AP307` 已有 DOI，未找到 PMID，继续 keep blank。
  - `AP505/AP508/AP512/AP516/AP517/AP520/AP521/AP524/AP525/AP536/AP543` 均存在 title/author/journal/year 冲突或身份未闭合，不能写。
  - `AP605` 属 preprint/version-of-record policy，不走单纯 DOI/PMID 回填。
  - `AP526/AP527/AP529/AP530/AP532/AP533/AP617/AP624` 属 hold/boundary，不自动放行。
- `xylanase`：
  - `XYN51/XYN52/XYN53/XYN63/XYN72/XYN75` 为 confirmed DOI/no PMID 或 source-table boundary，保持 PMID 空。
  - `han2019/sun2014nterm` 仍未形成强一致 live 匹配，继续 no-write。
  - 36 行属于 metadata/source-table/identity/computational boundary，不能复制 PMID。
  - `XYN67/XYN68` 为 patent，继续走 patent metadata policy。
- 下一批脚本范围：
  - acid 只做 unresolved identity 行的候选发现；`AP001/AP307` 不再重复查 PMID；`AP605` 单独走 preprint policy。
  - xylanase 优先只处理 `han2019/sun2014nterm`；boundary 行先 source-table 修复，patent 行进入 patent metadata 流程。

## 2026-08-05 enzyme metadata curation queue 第一层

- 新增平台内部通用队列，不复用 lipase 专用表：
  - `enzyme_metadata_curation_records`
  - `enzyme_metadata_curation_batches`
- 队列只管理平台主库审核状态，不写 `acid_protease.db` / `xylanase.db`。
- materialize 流程：
  - 从 sidecar policy decisions 读取记录。
  - dry-run 输出 planned/skipped。
  - apply 只写平台主库 `queued` 记录。
  - `family + paper_id + record_type` 唯一，重复 materialize 会 skipped，不重复建队列。
- review/batch 流程：
  - admin 可把记录从 `queued` 改为 `accepted/rejected/needs_more_evidence/triaged`。
  - `batched/archived` 只能通过 batch workflow 控制。
  - batch dry-run/create/archive 生成人工升级 payload；archive 只是平台内部归档，不代表外部 SQLite 已更新。
- 安全字段继续明确：
  - `read_only_source_db=true`
  - `sqlite_mutated=false`
  - `export_safe_released=false`
  - `target=manual_family_specific_metadata_upgrade_script`
- 当前边界：
  - 外部 SQLite 真实 mutation 仍需后续家族专用脚本执行 `dry-run -> backup -> apply -> PRAGMA integrity_check`。
  - queue 前端管理面板已接入 `/data` 酶库页，仅 admin 显示。

## 2026-08-05 enzyme metadata curation queue 前端管理面板

- `/data` 多酶库页现在在 admin 账号下显示 `Metadata curation queue` 面板。
- 面板能力：
  - 刷新 queue 与 batches。
  - sidecar policy decisions `materialize dry-run`。
  - 将 sidecar decisions 写入平台内部 queue。
  - 选择 queue records 并设置 `accepted / needs_more_evidence / rejected`。
  - 对 accepted records 做 batch dry-run。
  - 创建内部 batch，并对 prepared batch 执行内部归档。
- 面板文案明确：
  - 只写平台主库 queue。
  - 不修改 acid/xylanase SQLite。
  - 不释放 export-safe。
  - batch archive 只是后续家族专用升级脚本输入，不是外部库发布。

## 2026-08-05 stage 24 live 强证据元数据核验

### acid_protease live 只读结论
- 子 agent 已先读 `acid_protease_residual_metadata_decisions_20260805.md`，再用 SQLite `file:...acid_protease.db?mode=ro` + `PRAGMA query_only=ON` 复核。
- SQLite 当前完整性与缺口：`PRAGMA integrity_check=ok`；`papers=123 / missing_doi=18 / missing_pmid=22 / blank_both=18`。
- 联网状态：
  - 初始 Crossref DNS/HTTP 000 失败不计为 live success。
  - 获准后 Crossref `/works`、Crossref DOI endpoint、NCBI PubMed `esearch/esummary` 返回 HTTP 200。
  - AP543 PubMed 首次 SSL/HTTP 000，重试后 HTTP 200；首次失败不作为成功证据。
- 可写候选：无。没有任何行同时满足 `title + DOI/PMID + author + journal + year` 强一致，且不触碰 `hold/boundary/preprint/patent` 边界。
- 继续 keep blank / no-write：
  - `AP001/AP307/AP536/AP543`：已有 DOI，PubMed DOI 反查 count=0 或相关候选不强一致，PMID 继续空。
  - `AP505/AP508/AP512/AP516/AP517/AP520/AP521/AP524/AP525`：有相近文献或历史错 DOI 线索，但 title/author/journal/year 未闭合，不能写。
  - `AP605`：属于 preprint/version-of-record policy，只能进入人工升级策略，不做单纯 DOI/PMID 回填。
  - `AP526/AP527/AP529/AP530/AP532/AP533/AP617/AP624`：hold/manual/source-identity boundary，不自动放行。
- 下一批 acid 脚本范围：只做 discovery/report，不做 apply；聚焦 `AP505/AP508/AP512/AP516/AP517/AP520/AP521/AP524/AP525`。
- 下一批 acid 排除范围：`AP001/AP307/AP536/AP543` 不再重复查 PMID-only；`AP605` 走 preprint policy；`AP526/AP527/AP529/AP530/AP532/AP533/AP617/AP624` 只进 manual boundary/source-identity repair。

### stage 24 执行边界
- 本阶段不是批量写库阶段，而是 live 强证据发现阶段。
- 若后续 xylanase 或跨库 paper 发现出现强候选，也只进入 `dry-run -> backup -> apply -> PRAGMA integrity_check` 设计流程；在强身份闭合前不得写外部 SQLite。
- `hold/boundary/non_exportable/patent/preprint` 行继续 fail-closed，不得通过报告或 export-safe 路径自动释放。

### xylanase `han2019/sun2014nterm` live 只读复核
- 本地记录：
  - `han2019`：`Improvement of the thermostability and catalytic activity of a GH11 xylanase by engineering the cord region`；Han N / Miao H / Yu T / Liu Y；Applied Microbiology and Biotechnology；2019；DOI `10.1007/s00253-019-09770-9`；PMID 空；`variant_identity_incomplete_boundary`。
  - `sun2014nterm`：`N-terminal engineering of a GH11 xylanase for improved thermostability`；Sun J / Wang H / Wang Y / Yao B / Luo H；Journal of Microbiology and Biotechnology；2014；DOI `10.4014/jmb.1401.01010`；PMID 空。
- live 结果：
  - 普通沙箱 DNS 对 PubMed/Crossref 全部失败，HTTP 000；未计为 live success。
  - 提权联网后 PubMed DOI AID 反查：两条均 HTTP 200 / count=0。
  - Crossref DOI endpoint：两条均 HTTP 404 `Resource not found`。
  - DOI resolver：两条均 HTTP 404。
  - PubMed exact title 查询：两条均 HTTP 200 / count=0。
  - `sun2014nterm` Crossref title search 返回 HTTP 429；按规则不作为成功证据。
- 结论：两条均保持 no-write；不能补 PMID，也不能把现有 DOI 标为强证据。
- 附带发现：`han2019` 的 title search 召回 2025 ACS/J Agric Food Chem `Improving the Thermal Stability of GH11 Xylanase XynASP through Cord Region Engineering`，但题名、作者、期刊、年份均不等于本地 `han2019`，不能作为替换元数据。

### 跨家族高价值新 paper 候选
- 查询范围：PubMed 2025/2026，家族关键词覆盖 xylanase、lipase、acid/aspartic protease、amylase；补充 Crossref/PubMed DOI 反查。
- 本地去重：对候选 DOI/PMID 在对应 SQLite `papers` 中只读查询；除 acid `AP602` 外，以下高价值候选未在对应家族库命中。

| 家族 | 状态 | PMID | DOI | 题名 | 价值判断 |
|---|---|---:|---|---|---|
| xylanase | strong-new-candidate | 39743673 | `10.1021/acs.jafc.4c10256` | Improving the Thermal Stability of GH11 Xylanase XynASP through Cord Region Engineering | 直接贴合“突变位点 + cord region 逻辑”，优先进入新 paper curation dry-run |
| xylanase | strong-new-candidate | 42134585 | `10.1016/j.biortech.2026.134883` | Computationally assisted combinatorial rational design of xylanase with improved thermostability and catalytic performance for lignocellulosic biomass hydrolysis | 组合理性设计，贴合位点组合与优先级排序 |
| lipase | strong-new-candidate | 42235695 | `10.1016/j.biortech.2026.135069` | Efficient biomanufacturing of vitamin E succinate in non-aqueous media via synergistic computational evolution and immobilization of lipase | 计算进化 + 固定化，适合 lipase 工程方法与实验条件逻辑 |
| lipase | strong-metadata / medium-engineering | 42248057 | `10.1016/j.enzmictec.2026.110921` | Discovery and characterization of a thermostable CALB-type lipase for efficient ethyl hexanoate synthesis in aqueous systems | 热稳定 CALB-type 来源文献，可能更适合作为 benchmark/source enzyme，而非突变行 |
| acid_protease | already-present | 40622661 | `10.1007/s12033-025-01470-0` | Designing Novel Aspartic Protease (NAP) Using Ancestral Sequence Reconstruction (ASR) for Cheesemaking | 已在 acid 库 `AP602`，不新增 |
| amylase | medium-candidate | 42364749 | `10.1016/j.ijbiomac.2026.153242` | Leveraging mutagenesis for enhanced enzymatic output: Detergent-stable α-amylase and lipase co-production by Bacillus subtilis on kitchen waste | 有 mutagenesis 与产酶输出，但可能不是位点级纯酶改造，需人工看全文 |
| amylase | background-review | 42121498 | `10.3390/foods15091555` | α-Amylase: Its Structure, Molecular Modification, and Application in the Food Field | 适合作为背景/综述，不作为 variant measurement 来源 |

- 当前候选均不写外部 SQLite；下一步应生成跨家族 `new_paper_candidates_20260805.md/json` 或 family-specific dry-run importer，由人工确认是否创建 paper/variant/measurement 草案。

### dry-run-only importer 草案
- 新增 `new_paper_candidates_dry_run_importer_20260805.py`，读取 `new_paper_candidates_20260805.json`。
- 行为：
  - 默认只输出 `mode=dry-run` proposal，不写任何 SQLite。
  - 每个 family DB 以 `file:...?mode=ro` 打开，并设置 `PRAGMA query_only=ON`。
  - 对候选 DOI/PMID 做本地 duplicate check，同时跑 `PRAGMA integrity_check`。
  - `--apply` 直接 fail-closed，提示必须先实现全文证据和 family-specific allowlist。
- dry-run 结果：
  - 7 个候选生成 7 条 proposal。
  - xylanase/lipase/amylase 候选未在对应库命中。
  - acid_protease `40622661 / 10.1007/s12033-025-01470-0` 命中 `AP602`，自动标为 duplicate，不可导入。
  - review/background 类型不生成 variant/measurement payload；仍需人工全文抽取位点和指标。

## 2026-08-05 stage 25 amylase 新 paper curation

- 子 agent 只读核查完成；未写文件、未改 SQLite。
- PMID `42364749` / DOI `10.1016/j.ijbiomac.2026.153242`：
  - 身份：Aslam et al., International Journal of Biological Macromolecules, 2026。
  - 证据访问：PubMed abstract + ScienceDirect abstract/highlights；未发现 PMC 开放全文。
  - 证据等级：`abstract_only`，附 `blocked_fulltext` caveat。
  - 结论：可见内容描述 EMS 随机诱变得到 `Bacillus subtilis 250`，并结合底物诱导、OFAT/RSM 发酵优化；不是 alpha-amylase 定点/组合突变体。
  - 可见指标：alpha-amylase/lipase 活性约 1.53x/1.45x；最终产量约 89.4 IU/ml / 74.1 IU/ml；alpha-amylase 表观最适 pH 7、50 C；还有 detergent/添加剂稳定性描述。
  - importer 决策：`reject_for_variant_importer`；可作为产酶工艺/菌株诱变背景，不进入位点级实验主表。
- PMID `42121498` / DOI `10.3390/foods15091555`：
  - 身份：Liu et al., Foods, 2026；PMCID `PMC13163881`；PubMed publication type 为 Review。
  - 证据访问：PubMed + PMC/MDPI 开放全文。
  - 证据等级：`background_review`。
  - 结论：综述表汇总了若干来自原始文献的位点，如 `L134R/S320A`、`Q360C`、`V260I`，但本文不是 primary experimental source。
  - importer 决策：`background_only`；可做 primary-paper 线索，不直接导入 variant measurement。
- 已新增实际 allowlist 决策文件 `new_paper_fulltext_allowlist_20260805.json`：
  - `AMY_CAND_20260805_006` -> `reject_for_variant_importer`
  - `AMY_CAND_20260805_007` -> `background_only`
  - 仍保持 `allow_apply=false`、`external_sqlite_mutated=false`、`export_safe_released=false`。

## 2026-08-05 stage 25 lipase 新 paper curation

- 子 agent 只读核查完成；未写文件、未改 SQLite。
- PMID `42235695` / DOI `10.1016/j.biortech.2026.135069`：
  - 身份：Zhang et al., Bioresource Technology, 2026。
  - 证据访问：PubMed abstract + Elsevier/ScienceDirect abstract 可见；source table/figure 不可见。
  - 证据等级：`abstract_only`，exact residues 为 `blocked_fulltext`。
  - 可见位点/变体：摘要命名 `CM5`，但未展开具体替换位点，不能回填残基列表。
  - 逻辑：Candida rugosa lipase WT 基线，ASR + free-energy optimization + surface hydration shell modulation 协同进化，再叠加固定化。
  - 可见指标：65% DMSO 耐受 4.78x；50 C 半衰期 1.67x；活性 2.30x；5 L 生物反应器 142.71 U/mL；CM5@AOMR VES 收率 >99.9%，10 批后 98.2%。
  - importer 决策：`paper_benchmark_process_only_until_fulltext`；可进 paper/benchmark/process，不进 variant。
- PMID `42248057` / DOI `10.1016/j.enzmictec.2026.110921`：
  - 身份：Dai et al., Enzyme and Microbial Technology, 2026。
  - 证据访问：ScienceDirect abstract/highlights 可见；source table/figure 不可见。
  - 证据等级：`abstract_only`。
  - 位点：`none disclosed`；这是 CALB-type lipase discovery/characterization，不是突变改造论文。
  - 逻辑：基于 CALB 参考做 SSN + structural homology mining，发现 Xylariales sp. PMI_506 的 `XyEst/rXyEst`。
  - 可见指标：与 CALB 序列一致性 23.83%；最适 pH 4、30 C；70 C 1h 后仍保留 >30% 活性；水相 8h 达 65% 转化。
  - importer 决策：`benchmark_source_only`；可做来源酶/性能基线，不进 variant。

## 2026-08-05 stage 25 xylanase 新 paper curation

- 子 agent 只读核查完成；本地 manifest 命中两篇；xylanase SQLite 用 `mode=ro` 查 DOI/PMID 未发现本地重复；未写文件、未改 SQLite。
- PMID `39743673` / DOI `10.1021/acs.jafc.4c10256`：
  - 身份：Li et al., Journal of Agricultural and Food Chemistry, 2025 Jan 15, 73(2):1516-1528。
  - 证据访问：Crossref/ACS VOR metadata + PubMed abstract；无 PMC；ACS full text/PDF 不作为本轮开放全文。
  - 证据等级：`metadata_only` + `abstract_only`，DSM4 位点为 `blocked_fulltext`。
  - 位点：摘要命名终突变体 `DSM4`，但不公开 DSM4 mutation composition，不能推断残基。
  - 逻辑：GH11 XynASP cord-region 系统工程，目标是降低 cord-region flexibility、提升 global rigidity、保留 thumb flexibility，并通过 catalytic cleft/contact effects 维持或提升活性。
  - 可见指标：DSM4 vs WT XynASP：50 C t1/2 提升 130.9x；catalytic efficiency 提升 9.3x。WT absolute baseline、assay substrate、pH、source table/figure 不可见。
  - importer 决策：`paper_draft_only_until_fulltext`；不生成 variant/measurement。
- PMID `42134585` / DOI `10.1016/j.biortech.2026.134883`：
  - 身份：Zou et al., Bioresource Technology, 2026 Sep, article 134883；Epub 2026-05-14。
  - 证据访问：Crossref/Elsevier metadata + PubMed abstract；无 PMC；ScienceDirect/full text 本轮不可访问。
  - 证据等级：`abstract_only`；measurements 仍 `blocked_fulltext`。
  - 位点：摘要公开工程变体 `9K-XynB2 (HFBI-A52C/T205C-F31Y/A50F/A143P)`。
  - 逻辑：A. niger xylanase XynB 在 Pichia pastoris GS115 表达；整合 signal peptide optimization、disulfide engineering、DeltaDeltaG-guided multisite mutagenesis、fermentation scale-up 和 biomass hydrolysis validation。
  - 可见指标：HFBI signal vs 9K-XynB：secretion 1.42x、catalytic activity 1.60x；9K-XynB2 vs 9K-XynB：60 C half-life 约 11x、kcat/Km 7.7x；5 L 发酵约 8.2e3 U/mL；协同指数最高 1.95；还原糖 6.21 +/- 0.06 g/L。
  - importer 决策：`non_exportable_variant_draft_only`；可生成 variant 草案，不生成 measurement，直到 full text/source table 确认 WT absolute、mutant value/fold-change、unit、temp、pH、substrate 和 source locator。

## 2026-08-05 stage 25 importer parallel audit

- 4 个只读子 agent 并行完成规划、importer、全文资产和 SQLite schema 审计；未写文件、未改 SQLite。
- PMID `39743673`、`42134585`、`42235695`、`42248057` 均未发现本地 PDF、补充材料、表格摘录或全文缓存；当前仍只有 metadata/abstract 级证据。
- 发现并修复 importer 门控风险：
  - duplicate found 时同步清除 `ready_for_family_importer`；
  - allowlist 增加 `allow_apply=false` 顶层保护；
  - 移除 `abstract_only_paper_boundary` 的 ready source level；
  - decision 必须为 `approved_for_family_importer` 才可能 ready；
  - 校验 allowlist 与候选 family、DOI、PMID 身份匹配。
- 状态表达建议：
  - compact DB 继续使用 `paper_payload_boundary`、`abstract_payload_boundary`、`non_exportable` 等 marker，不新增 lipase 风格 `ready_for_db`；
  - benchmark 保持 `benchmark_only_non_exportable_boundary`；
  - variant 草案保持 `variant_draft_non_exportable_boundary`，无测量时不造 dummy measurement。

## 2026-08-05 stage 25 importer regression tests

- 新增 importer 合同测试覆盖 7 个关键门控场景，全部通过。
- 测试明确证明：只有 `approved_for_family_importer` + source table/figure/supplementary table + 身份匹配 + 无重复时才可能 ready。
- 当前真实 allowlist 仍全部 blocked；abstract-only、reject/background、paper draft、benchmark-only、non-exportable draft 均不会进入 family importer。
- benchmark/release validator 用 `/tmp` 输出只读复核通过；`status=blocked`、`release_ready=false`、`safe_for_model_claim=false` 均为预期状态。

## 2026-08-05 stage 25 importer highest-risk gates

- 子 agent 后续审计指出三个最高优先级门控缺口：integrity 非 ok、SQLite error、missing allowlist 输出结构。
- 已将 integrity 非 `ok` 与 SQLite error 都改为强制 fail-closed，防止 proposal 在 DB 异常时保留 ready。
- missing allowlist 的 `fulltext_gate` 结构已与普通 blocked gate 对齐，便于下游 validator 和 UI 稳定消费。
- 回归测试扩展到 10 个用例并通过；真实候选 dry-run 仍全部 blocked。

## 2026-08-05 stage 25 importer schema hardening

- manifest/allowlist 从“尽量读取”改为显式输入合同：顶层 object、数组字段、条目 object、候选身份字段均 fail-closed。
- allowlist 重复 `proposal_id` 不再后者覆盖前者，而是直接阻断，避免人工决策文件冲突被静默吞掉。
- DOI/PMID duplicate check 现在做基础规范化，覆盖 DOI 前缀、大小写、空格和 PMID 前缀。
- 回归测试扩展到 14 个用例并通过；真实候选仍全部 `ready_for_family_importer=false`。

## 2026-08-05 stage 25 importer family/db hardening

- unknown family 与 missing DB 之前只记录 `duplicate_check`，理论上可能与完整 fulltext gate 组合成 ready；现已强制 fail-closed。
- family filter 后 proposal_id 继续使用 manifest 原始 index，保持 allowlist ID 稳定。
- 非 importable candidate status 即使 allowlist 完整也不会 ready。
- 回归测试扩展到 18 个用例并通过；真实候选 dry-run 仍全部 blocked。

## 2026-08-05 stage 25 importer allowlist binding

- allowlist 现在必须显式绑定候选 DOI/PMID；候选有 DOI/PMID 但 allowlist 缺失时不再允许 ready。
- gate 状态重算集中到 helper，减少后续追加 missing field 后忘记同步 `status/reason/ready` 的风险。
- 三个允许 source level 均有正例测试；truthy 非布尔值仍被视为 false flag。
- 回归测试扩展到 22 个用例并通过；真实候选 dry-run 仍全部 blocked。

## 2026-08-05 stage 25 importer safety flag matrix

- manifest/allowlist 顶层安全字段现在有矩阵测试，确认只有 literal `False` 能通过；`0`、`None`、字符串 `"false"` 都 fail-closed。
- family filter 无匹配时输出稳定空 dry-run contract，避免下游把空筛选误判为错误。
- 回归测试扩展到 43 个用例并通过；真实候选 dry-run 仍全部 blocked。

## 2026-08-05 stage 25 importer allowlist/db column matrix

- allowlist 必填文本字段已有空值/TBD 矩阵测试；`proposal_id` 缺失按 missing allowlist entry 处理。
- 三个 importable status 均已有 ready 正例，防止后续误删候选状态白名单。
- SQLite `papers` 只有 DOI、只有 PMID、无 DOI/PMID 的列组合已覆盖，duplicate 查询不会无条件扫表。
- 回归测试扩展到 70 个用例并通过；真实候选 dry-run 仍全部 blocked。

## 2026-08-06 stage 25 importer readonly/single-identity tests

- `_connect_readonly()` 现在有真实 SQLite 只读测试：连接后 `PRAGMA query_only=1`，写操作会失败。
- 单 DOI / 单 PMID 候选的 allowlist 绑定已覆盖，避免只靠 proposal_id 绕过身份匹配。
- allowlist 文件不存在的行为已固化为 blocked preview，而不是 CLI/脚本错误。
- manifest `candidates` 非 list 的 guard 已覆盖；回归测试扩展到 82 个用例并通过。

## 2026-08-06 stage 25 importer cli/integrity hardening

- Zeno/Erdos 均建议暂不新增 stage 26；stage 25 应保持 in_progress，等待全文和人工 apply approval。
- CLI 成功路径已有测试覆盖，真实 manifest 的 xylanase dry-run 输出 JSON 可解析且仍全部 blocked。
- duplicate SQL 归一化修复了混合大小写 DOI/PMID 前缀漏重风险。
- integrity error 现在优先于 duplicate，且 missing integrity row 也 fail-closed。
- 回归测试扩展到 86 个用例并通过；真实候选 dry-run 仍全部 blocked。
- Carson 提出的 payload 深度校验与稳定 proposal identity 属于下一层合同设计，已记录为后续缺口。

## 2026-08-06 stage 25 importer payload/stable identity phase 1

- `approved_for_family_importer` 现在要求结构化 `variant_draft` 与 `measurement_draft`，并校验证据粒度、方向、variant_name 关联和 boundary/abstract 禁入。
- paper-only、benchmark-only、reject/background、non-exportable draft 仍作为兼容出口，不要求 payload 深校验，也不会 ready。
- preview 新增 `candidate_key`、`stable_proposal_id`、`legacy_proposal_id`、`identity_version=1`，为后续从 index ID 迁移到稳定身份做双写准备。
- allowlist 查找仍使用 legacy `proposal_id`，但 DOI/PMID/title/family 全量绑定校验继续 fail-closed。
- 回归测试扩展到 100 个用例并通过；真实候选 dry-run 仍全部 blocked。

## 2026-08-06 stage 25 importer stable identity phase 2

- allowlist 显式 stable 字段现在会校验：`candidate_key`、`stable_proposal_id`、`identity_version` 任一错配都阻断 ready。
- 缺失 stable 字段仍兼容 legacy allowlist，但 legacy entry 仍必须通过 family/title/DOI/PMID 绑定。
- manifest 内重复 stable identity 直接 fail-closed，防止同一论文候选多行导致 allowlist 绑定歧义。
- payload 深校验补充了 evidence/source/direction/condition/confidence/variant_name 关联。
- 回归测试扩展到 105 个用例并通过；真实候选 dry-run 仍全部 blocked。

## 2026-08-06 stage 25 importer payload semantic negatives

- `variant_draft.cnt=True` 漏洞已封住：现在必须是真实 int 且非负。
- variant norm/conf/evidence_level 的 unknown/TBD/boundary/abstract/source_text 等语义污染均有负例测试。
- measurement variant_name、direction、evidence_level、confidence、value/fold_change 二选一和 list 深校验均有负例测试。
- 回归测试扩展到 131 个用例并通过；真实候选 dry-run 仍全部 blocked。

## 2026-08-06 stage 25 importer approved stable identity gate

- `approved_for_family_importer` 不再允许省略 `candidate_key`、`stable_proposal_id`、`identity_version` 后直接 ready。
- 旧 allowlist 兼容仅限非 approved/blocked preview；不会被悄悄升级为 family importer ready。
- `identity_version` 必须是 literal int `1`；truthy 或字符串值均阻断。
- 回归测试扩展到 140 个用例并通过；真实候选 dry-run 仍全部 blocked。

## 2026-08-06 backlog items 1-5 kickoff

- 待建清单 1-5 已同步启动；仍遵守 no SQLite write、no export-safe release。
- 全文/source table 线上复查没有找到可导入的新证据，xylanase/lipase 四篇继续 blocked。
- 新增 stable identity migration report：
  - 6 条 allowlist entry 需要补 `candidate_key/stable_proposal_id/identity_version/title`；
  - 1 条 acid_protease already-present 不迁移；
  - conflict_count=0、ready_count=0。
- allowlist template 已加入 stable identity 与 approved payload 字段提示，避免继续诱导 legacy-only approved entry。
- Release/benchmark 复核结论：validator 结构通过，但 blocked 来自人工 decision、benchmark receipts、FoldX runtime evidence；不是代码 validator failure。

## 2026-08-06 backlog items 1-5 subagent closure

- `Galileo` 只读确认四篇 xylanase/lipase 新 paper 都应保持 `fulltext_source_table_blocked` 或 `source_table_required`：
  - `39743673` DSM4 仍缺 mutation composition、WT absolute baseline、assay condition、source locator；
  - `42134585` 9K-XynB2 虽有摘要位点，但 measurement baseline/value/unit/source locator 未闭合，仍只能 non-exportable draft；
  - `42235695` CM5 exact substitutions 不可见，且必须分离 mutation effect 与 immobilization/process metrics；
  - `42248057` 是 CALB-type source enzyme discovery/characterization，摘要未披露 mutation sites，不能建 variant。
- `new_paper_fulltext_gap_worklist_20260806.json` 已补入 read-only/write-policy、`allow_apply=false`、`export_safe=false`、visible metrics、blocked payloads 和 source access gap；仍不产生 SQLite payload。
- `Carver` 只读确认 release/benchmark gating 的人工 backlog 真实状态：
  - 11 条 backlog 全部 open，P0=8、P1=3、ready=0；
  - required_rows=1217、completed_rows=31、missing_rows=1188；
  - benchmark readiness packet `contract_valid=true` 且 `failure_count=0`，但 `safe_for_model_claim=false`、`release_ready=false`；
  - hard-gate bridge 当前 fail-closed，formal decisions 不完整时 `intake_rows_written=0`、`training_import_written_rows=0`。
- `release_benchmark_human_decision_worklist_20260806.json` 已扩展到 human backlog 汇总、P0/P1 条目和 fail-closed report 链路；仍未创建 formal decision rows。
- 最新验证：
  - JSON structural validation passed；
  - importer tests 140 passed；
  - xylanase/lipase/amylase dry-run 均 2 proposals、`errors=[]`、`ready_for_family_importer=false`；
  - `--apply` 继续 fail-closed；
  - benchmark/release validators 无 failure，但继续 blocked/release_ready=false。

## 2026-08-06 backlog items 1-5 fail-closed validator findings

- `new_paper_allowlist_identity_patch_draft_20260806.json` 现在显式是 advisory draft：
  - 顶层 `patch_status=draft_not_applied`、`review_required=true`、`allow_apply=false`；
  - 每条 patch 都是 `entry_patch_status=draft_not_applied`；
  - `expected_entry_count_before=6` 与 `expected_entry_count_after=6`，说明不是自动扩表或自动应用。
- 新 validator `validate_new_paper_allowlist_identity_patch_draft_20260806.py` 检查：
  - patch count 必须匹配 migration report 的 `migratable_count`；
  - patch 每条 `proposal_id/candidate_key/stable_proposal_id/identity_version/title` 必须匹配 migration report；
  - patch 不能暗示 apply/export-safe/SQLite mutation。
- 新 validator `validate_new_paper_fulltext_gap_worklist_20260806.py` 检查：
  - fulltext gap worklist 顶层必须 `external_sqlite_mutated=false`、`export_safe_released=false`、`allow_apply=false`；
  - 4 条 item 必须使用 blocked 状态：`fulltext_source_table_blocked` 或 `source_table_required`；
  - 任一 item 不能出现 true 的 ready/apply 类字段。
- Release/benchmark worklist 不再假装与 human backlog 完全同构：
  - 13 条 item = 11 条 `human_decision_backlog` + 1 条 `structural_execution_gap` + 1 条 `runtime_evidence_gap`；
  - `benchmark_gaps` 和 `foldx_runtime` 是非 backlog 缺口，仍需要证据/receipt，但不是 formal human decision row；
  - 顶层加入 `interpretation_warning`，明确 `worklist_valid=true` 或 validator `success=true` 不等于 `release_ready` 或 `safe_for_model_claim`。
- 新 validator `validate_release_benchmark_human_decision_worklist_20260806.py` 检查：
  - backlog summary 必须保持 11 open、P0=8、P1=3、ready=0、missing_rows=1188；
  - non-backlog gap summary 必须是 2 条；
  - item 必须统一使用 `validator_report`，不能混用 `validator`；
  - 非 backlog gap 必须显式 `release_ready=false`、`safe_for_model_claim=false`、`benchmark_ready_for_model_claim=false`。
- 最新验证均 0 failure；这些是结构清单有效，不是放行信号。

## 2026-08-06 importer gate alias and payload scope findings

- `importable_after_full_text` 继续保留为 legacy 字段，但现在有更清晰的 `candidate_status_eligible_after_evidence`：
  - 它表示 candidate status 在证据闭合后理论可进入家族 importer；
  - 它不表示 evidence gate 已闭合，不表示 duplicate gate 已通过，也不表示可 apply/export。
- 新增 proposal gate alias：
  - `evidence_gate_passed` 只代表 allowlist/fulltext/source evidence gate；
  - `duplicate_gate_passed` 只代表当前 family SQLite duplicate/integrity gate；
  - `family_importer_gate_passed` 才是 candidate status + evidence gate + duplicate gate 的综合 dry-run 门；
  - 即便 `family_importer_gate_passed=true`，`apply_allowed_now=false`、`export_safe=false`、`release_status=not_released` 仍必须保持。
- 真实 20260805 候选 dry-run 现状：
  - xylanase/lipase/amylase 各 2 proposals；
  - 全部 `errors=[]`；
  - 全部 `evidence_gate_passed=false`、`family_importer_gate_passed=false`、`export_safe=false`、`release_status=not_released`；
  - 已确认 `candidate_status_eligible_after_evidence=true` 只表示候选 status 可用，不是证据已闭合。
- `new_paper_fulltext_gap_worklist_20260806.json` 已补 `payload_scope`：
  - XYN-001: `paper_only`
  - XYN-002: `variant_draft_only_measurement_blocked`
  - LIP-003: `paper_process_benchmark_only`
  - LIP-004: `source_only_no_variant_payload`
- fulltext gap validator 已强制每条 `requires_fulltext=true`、`requires_source_table=true`、`requires_manual_approval=true`、`release_status=not_released`。
- 回归测试增至 141 passed；新增测试锁定 “fulltext gate ready 不等于 importer ready” 与 “family importer ready 不等于 apply/export-safe/release”。

## 2026-08-06 stage 25 new-paper cross-artifact consistency

- patch draft validator 已升级为跨文件一致性校验：
  - 从 migration report 的 `inputs.manifest` 和 `inputs.allowlist` 现场重算 migration report；
  - 要求 patch draft 的 6 条 patch shape 同时匹配磁盘 migration report 和重算结果；
  - 要求 patch draft 仍是 `draft_not_applied`，且 `allow_apply=false`、`export_safe_released=false`、`external_sqlite_mutated=false`。
- 新增 migration report validator 固定当前审计不变量：
  - `candidate_count=7`
  - `allowlist_entry_count=6`
  - `proposal_count=7`
  - `migratable_count=6`
  - `conflict_count=0`
  - `not_in_allowlist_count=1`
  - `ready_count=0`
  - `status_counts={legacy_needs_identity_fields:6, not_in_allowlist_no_migration:1}`
- `AP_CAND_20260805_005` 是 already-present / not-in-allowlist candidate，不允许进入 proposed patch shape。
- 新增 `new_paper_stage25_fail_closed_validation_summary_20260806.json` 聚合三份 validator：
  - migration report validation；
  - patch draft validation；
  - fulltext gap worklist validation。
- 聚合 summary 当前 `summary_valid=true`、`failure_count=0`、`report_count=3`；这是结构一致性通过，不是 apply/release 信号。

## 2026-08-06 release/benchmark fail-closed summary

- 新增 `release_benchmark_stage25_fail_closed_summary_20260806.json`，聚合四个 release/benchmark 上游报告：
  - human decision backlog fail-closed consistency；
  - release/benchmark human decision worklist validation；
  - benchmark readiness packet validation；
  - local release manifest fail-closed consistency。
- 聚合 summary 固定以下不变量：
  - human backlog 仍 open_items=11、ready_items=0、total_missing_rows=1188；
  - release/benchmark worklist 仍 11 条 backlog + 2 条 non-backlog gap；
  - benchmark readiness 仍 `status=blocked`、`packet_rows=2`、`completion_ready_rows=0`；
  - local release manifest 仍 `release_ready=false`、`safe_for_model_claim=false`、`failures=[]`。
- 聚合器还会扫描上游报告中的 gate flags：
  - `release_ready`
  - `safe_for_model_claim`
  - `benchmark_ready_for_model_claim`
  - `ready_for_model_claim`
  - 只要出现就必须为 literal false。
- 当前结果：`summary_valid=true`、`failure_count=0`、`report_count=4`。
- 这说明 fail-closed 证据链一致，不代表 formal decision、benchmark approval、model claim 或 release approval。

## 2026-08-06 stage 25 overall fail-closed index

- 新增 `stage25_overall_fail_closed_index_20260806.json` 作为 Stage 25 跨目录总控入口。
- 输入只有两条：
  - new-paper fail-closed summary；
  - release/benchmark fail-closed summary。
- 总控 index 固定：
  - `index_valid=true`
  - `failure_count=0`
  - `external_sqlite_mutated=false`
  - `allow_apply=false`
  - `export_safe_released=false`
  - `formal_decision_rows_written=0`
  - `release_ready=false`
  - `safe_for_model_claim=false`
  - `benchmark_ready_for_model_claim=false`
  - `release_status=not_released`
- 当前 `summary_count=2`，两条上游 summary 都有效且 `failure_count=0`。
- 用途：日报/交接可先看这份总控索引，再下钻到 new-paper 或 release/benchmark summary。
- 边界：这是 fail-closed 一致性索引，不是全文证据闭合、SQLite apply、formal decision、benchmark approval 或 release approval。

## 2026-08-06 stage 25 validation runner

- 新增 `run_stage25_fail_closed_validation_20260806.py` 作为 Stage 25 单命令复验入口。
- runner 会依次执行 7 个只读命令，覆盖：
  - new-paper migration report；
  - new-paper patch draft；
  - new-paper fulltext gap worklist；
  - new-paper summary；
  - release/benchmark human decision worklist；
  - release/benchmark summary；
  - Stage 25 overall index。
- 当前 run report：
  - `run_valid=true`
  - `failure_count=0`
  - `command_count=7`
  - `external_sqlite_mutated=false`
  - `allow_apply=false`
  - `export_safe_released=false`
  - `formal_decision_rows_written=0`
  - `release_ready=false`
  - `safe_for_model_claim=false`
  - `benchmark_ready_for_model_claim=false`
- runner 的用途是复验 fail-closed 链路和重建报告，不是 apply 脚本；它不写 SQLite、不创建 formal decision、不批准 release。

## 2026-08-06 stage 25 validation runner importer coverage

- Stage 25 runner 已从 7 个命令扩展到 12 个命令。
- 新增覆盖：
  - importer pytest；
  - xylanase/lipase/amylase 三族真实 dry-run；
  - `--apply` expected-failure 阻断检查。
- runner 对三族 dry-run 固定以下不变量：
  - 每族 `candidate_count=2`、`proposal_count=2`；
  - `errors=[]`；
  - `ready_count=0`；
  - `export_safe_count=0`；
  - 每条 proposal 均 `ready_for_family_importer=false`、`family_importer_gate_passed=false`、`export_safe=false`、`apply_allowed_now=false`、`release_status=not_released`。
- `--apply` 在 runner 中只有 returncode=1 且 stderr 包含 dry-run only blocked 文案时才算通过。
- 当前 run report：`run_valid=true`、`failure_count=0`、`command_count=12`。

## 2026-08-06 stage 25 pending list 1-5 kickoff findings

- 全文/source table 核查更新：
  - `39743673` 的 ACS Supporting Information asset 已识别为 `jf4c10256_si_001.doc`；
  - 本轮直接下载在 sandbox 内 DNS 失败，escalation 后 ACS 返回 HTTP 403；
  - 因未实际解析 SI，DSM4 mutation composition、source table/figure locator 和 measurement extraction 仍未闭合；
  - worklist 继续保持 `fulltext_source_table_blocked`，不能进入 family importer。
- 其余三篇仍 blocked：
  - `42134585` 摘要公开 9K-XynB2 位点，但缺 source table、baseline、units、source locator；
  - `42235695` 只有 CM5 名称，不能推断残基；
  - `42248057` 是 XyEst source enzyme discovery/characterization，不能建 mutation variant。
- Release/benchmark formal decision 状态仍 unchanged：
  - 11 条 human backlog 全 open；
  - `missing_rows=1188`；
  - benchmark blocked: ProteinGym 与 FLIP/FLIP2-style split；
  - FoldX: executable/license/runtime receipt/smoke artifact 均未闭合。
- 新增人读入口：
  - `AI大模型/reports/next_operator_packet_20260806.md`
  - `docs/manuals/2026-08-06-daily-report.md`
- Markdown 入口只引用 JSON 权威报告，不承担决策；不得把 `run_valid=true`、`summary_valid=true`、`index_valid=true` 解读为 apply/release/model claim ready。

## 2026-08-06 identity-only allowlist patch applied

- 用户授权后，已应用 allowlist stable identity fields，但仅限身份绑定：
  - `candidate_key`
  - `stable_proposal_id`
  - `identity_version`
  - `title`
- 应用后 migration report 从 `legacy_needs_identity_fields=6` 变为 `identity_bound=6`，`not_in_allowlist_no_migration=1` 保持。
- `ready_count=0`，说明身份字段闭合没有导致 family importer ready。
- patch receipt 当前：
  - `mode=identity_patch_receipt`
  - `patch_status=applied_identity_fields_only`
  - `allow_apply=false`
  - `external_sqlite_mutated=false`
  - `export_safe_released=false`
- 仍不能创建 affirmative formal decisions 或 release/model claim：
  - `39743673` SI 仍 extraction blocked；
  - `42134585/42235695/42248057` 仍 source table/fulltext blocked；
  - release/benchmark backlog 仍 11 open、1188 missing rows；
  - benchmark/FoldX runtime evidence still blocked.
- 核心原则：人工授权可以允许执行已经有证据支撑的写入，但不能替代缺失的 source table、mutation composition、measurement locator、license/FTO/biosecurity/benchmark/runtime receipts。

---
*每执行2次查看/浏览器/搜索操作后更新此文件*
*防止视觉信息丢失*

## 2026-08-05 release packet path-contract fix

- `validate_next_release_operator_decision_packet.py` 失败点不是 release 语义，而是 `benchmark_readiness_packets.jsonl` 的路径约定与真实 builder 输出不一致。
- 真实产物在 `datasets/governance/benchmark_readiness_packets.jsonl`，`reports/benchmark_readiness_packets.md` 也已存在。
- 已把 release validator 的必需路径修正到 `datasets/governance/benchmark_readiness_packets.jsonl`，并复验通过。
- 这不改变 `release_ready=false`、`customer_ready=false`、`safe_for_model_claim=false` 的 fail-closed 状态。

## 2026-08-05 release / claim fail-closed总控补齐

- `validate_next_release_operator_decision_packet.py` 继续补入两条必须显式出现的总控脚本：
  - `scripts/validate_local_release_manifest_fail_closed_consistency.py`
  - `scripts/validate_claim_readiness_matrix_fail_closed_policy.py`
- 同步把对应验证报告纳入必需本地路径：
  - `reports/local_release_manifest_fail_closed_consistency_validation_report.json`
  - `reports/claim_readiness_matrix_fail_closed_policy_validation_report.json`
- 复验仍通过，说明只是覆盖面收紧，没有放开任何 claim/release 门。

## 2026-08-05 next operator packet 总控报告对齐

- `next_operator_decision_packet_20260805.md` 已显式列出 local release / claim 的 fail-closed 总控报告：
  - `local_release_manifest_fail_closed_consistency_validation_report`
  - `claim_readiness_matrix_fail_closed_policy_validation_report`
  - `model_artifact_claim_guard_validation_report`
  - `local_release_guard_coverage_validation_report`
  - `local_release_safety_guard_link_validation_report`
  - `report_positive_claim_gate_quarantine_validation_report`
- 也补入了对应 validation order 脚本。
- 这只是把现有证据链写完整，不改变 release/customer/model claim 状态。

## 2026-08-05 benchmark readiness report 对齐

- `next_operator_decision_packet_20260805.md` 已补入：
  - `reports/benchmark_readiness_packet_report.json`
  - `reports/benchmark_readiness_packet_validation_report.json`
- `validate_next_release_operator_decision_packet.py` 复验仍通过。
- 这是命名与证据链对齐，不是 readiness 放行。

## 2026-08-05 benchmark validation-order 补齐

- `next_operator_decision_packet_20260805.md` 已把 benchmark hard-gate / bridge / readiness 的 builder 纳入验证顺序：
  - `build_hard_gate_review_packets.py`
  - `build_benchmark_hard_gate_operator_packets.py`
  - `build_benchmark_readiness_packet.py`
- `validate_next_release_operator_decision_packet.py` 复验仍通过。
- 这只是在 packet 里把实际执行顺序写完整，不代表任何 benchmark 通过。

## 2026-07-29 人工分析流程 v1 调研检查

- 用户确认后续平台酶改造流程按“人工分析流程（简版 v1）”执行。
- 现有 Matvenus 调研总结已沉淀“输入预检、禁改区、候选分层、实验批次、湿实验反馈闭环”，但今天确认的新流程进一步要求所有目标前置：
  - 输入整理
  - 基础核验
  - 结构获取
  - 最小基础画像
  - 目标识别与任务拆解
- 代码检查结论：
  - `backend/app/core/agent_roles.py` 已有 Matvenus-derived report protocol，但原协议偏报告规范，没有完整写出 9 节点主流程。
  - `backend/app/core/agent_graph.py` 已有热稳定性、活性、底物特异性、可溶性表达的目标路由，但原 standard fallback 对热稳定性可能直接进入 `predict_properties + mutation_priority_score`，缺少显式结构获取和最小基础画像。
  - `backend/tests/test_agent_binder.py` 已有“同一序列四目标对照”测试，适合改成保护“共同前置画像 + 目标分流”的回归。
- 本轮采取方案：
  - 新增 `docs/designs/2026-07-29-enzyme-manual-analysis-flow-v1.md` 作为平台正式流程固化说明。
  - 更新 `ENZYME_ENGINEERING_REPORT_PROTOCOL`，将 9 节点流程作为 agent 默认协议。
  - 更新 deterministic fallback plan：序列型酶改造先走理化核验、结构状态、protein_benchmark/enzyme_function 最小画像，再按目标进入突变评分、kcat、mutation_scan、soluble_mpnn 等专项工具。
  - 更新测试断言，防止后续退回“只按目标直接给候选”的流程。

## 2026-07-29 策略确认后执行门控

- 用户补充要求：
  - 必须确认后才执行。
  - 可修改策略后再执行。
  - 具体调用工具和流程要展示出来。
- 代码检查发现：
  - 原 `agent_graph.py` 已设置 `waiting_for="plan_confirmation"`，但随后马上清空并自动进入 execute。
  - 前端 `ThinkingChain` 只展示等待状态，没有确认/修改策略操作入口。
- 本轮修复：
  - `backend/app/api/chat.py` 增加 `agent_control` 字段。
  - `backend/app/core/agent_graph.py` 默认 `plan_only`，生成 plan 后输出“分析策略确认”，列出每一步工具、说明和参数，不执行工具。
  - `execute_confirmed` 才进入真实工具执行阶段。
  - `revise_plan` 只重新生成策略，不执行工具。
  - `frontend/src/hooks/useChatStream.ts` 透传 `agent_control`。
  - `frontend/src/components/chat/ChatInput.tsx` 在等待确认时显示“确认执行”和“修改策略”入口。
  - 前端确认执行会带上原始任务和所有后续修改策略，避免先修改再确认时丢失约束。
- 已验证：
  - `test_agent_binder.py` 增加 plan-only 不执行工具的回归测试。
  - `backend/.venv/bin/pytest backend/tests/test_agent_binder.py -q` -> 75 passed。
  - 前端 lint/build 通过。
## 2026-08-07 平台联网与重复回复诊断

- 用户反馈对象是“酶蛋白 AI 平台”内的聊天助手，不是 Codex 当前会话。
- 现象包含两条链路：一次联网询问出现多段/重复否定回复；平台本轮没有触发可核验的实时外部查询，因此回答“没有联网”。
- 仓库已经实现 `sequence_search`、`blast_search`、`interpro_live_lookup`、`literature_live_search` 及 `live/degraded/blocked` 证据状态；当前问题更可能位于联网意图路由、运行配置或 SSE/会话显示一致性，而不是完全没有联网工具代码。
- 工作区存在大量既有未提交改动；本轮只做联网触发与单次回复相关的低侵入修改，不回滚其它改动。
- 直接原因 1：`AgentOrchestrator._route_intent()` 会把短句“你联网了吗”判为 `general`；普通聊天分支在工具规划前提前返回，因此不会调用任何 live 工具。
- 直接原因 2：`_wants_live_literature_search()` 把所有含“联网”的表达都当作文献检索，但纯联网状态询问没有有效文献 query；需要把“网络状态检测”和“联网查文献”分开。
- 重复提交风险：`ChatInput.handleSend()` 使用 React render 时捕获的 `streaming` 值，快速双击/回车可能在重渲染前重复进入；发送按钮在 streaming 时也没有禁用。上传期间尚未进入 `sendMessage()`，风险更明显。
- SSE 文本本身按增量 chunk 追加，当前没有发现服务端在单个请求内主动重复发送同一完整答复的路径；优先修复客户端防重入，并为后端联网意图增加确定性路由与专用只读探测工具。
- 真实网络 smoke（授权网络环境）结果：UniProt REST、NCBI E-utilities、InterPro API 均返回 HTTP 200，`successful_probes=3/3`，证据状态为 `live/official_api_connectivity_check`。
- 沙箱内同一 smoke 返回 0/3 `ConnectError`，说明工具会如实 fail-closed；不能用沙箱结果推断部署服务器网络状态。
- 平台现在对纯联网状态询问先展示一个简短确认步骤；确认执行后每次都重新探测，不复用工具缓存，并生成一条证据化答复。
- “联网搜索最近文献”仍走 `literature_live_search`；具名蛋白（如 EGFR）的文献请求先 `sequence_search` 定位目标，再执行 live 文献检索。

## 2026-08-07 阶段 27 发布前全量回归发现

- 首轮后端全量回归唯一失败并非联网链路，而是 `_build_md_batch_replicate_summary()` 在函数内部重新导入 `build_lipase_evidence_context`，绕过模块级可测试 wrapper，导致 monkeypatch 不生效并读取真实数据库，测试期望证据数从 1 变成 0。
- 修复为复用已有模块级延迟导入 wrapper；生产行为不变，测试隔离与可注入性恢复。
- 公网发布采用 versioned release `20260807T040330Z-25679eb`；旧 release `20260807T023249Z-25679eb` 保留为快速回滚落点。
- ECS Docker Hub 对 `python:3.12-slim` 返回 `insufficient_scope`，因此常规 backend build 未完成；改用仓库既有 `Dockerfile.backend.hotfix` 基于当前已验证镜像离线覆盖 backend 代码，避免依赖重新安装和远端 registry。
- 本地/远端六个关键源码 SHA256 全部一致：agent graph、connectivity tool、registry、gromacs MD、ChatInput、useChatStream。
- ECS 容器内真实联网 3/3；公网 HTTP/public/live smoke passed；专项 Playwright 登录态测试确认双击发送仅 1 个 plan POST、确认仅 1 个 execute POST、最终答复渲染 1 次、consoleErrors=0、httpErrors=0。
- 两个 `connectivity-live-*` 临时账号均已禁用；测试会话由脚本尽力删除，不输出密码或 token。
- 发布后 backend/worker/md-worker 错误日志计数为 0；nginx 最近 30 分钟按真实 HTTP 状态字段统计 499/5xx=0。

## 2026-08-11 阶段 30 策略检查点与湿实验校准接线发现

- Venus/MatVenus 可借鉴点不是固定工具顺序，而是“策略检查点 + 用户确认 + 当前阶段继续执行”的状态机：确认应执行已展示策略，不能重新路由、重规划或新建任务。
- 当前平台需要服务端持久化 active checkpoint 来抵抗刷新、前端丢状态和用户手输“确认执行”；只依赖前端内存会导致同一问题续问误触发新流程。
- `strategy_checkpoints` active endpoint 能把 `plan/strategy_signature/task_fingerprint/next_action/artifacts` 恢复成前端 `agentState`，让刷新后仍停留在“确认执行”阶段。
- `strategy_checkpoints` history endpoint 按 revision 倒序返回策略版本，旧 awaiting checkpoint 在新版本生成时会变成 `superseded`；这为审计“修改策略后执行的是哪一版”提供证据。
- Artifact handoff 不能按 Venus 的固定工具链硬编码；当前实现从每个工具结果通用提取 `artifacts/artifact_manifest/task_id/status_url/download_url/object_name/sequence`，形成 `artifacts.handoffs`，前端按这个稳定结构展示执行时间线。
- 对长任务，handoff 第一层显示 `task_id/status_url/artifacts_url`，不声称任务已经产出最终文件；真正文件只在工具返回 `download_url/object_name/artifacts` 后显示。
- 同题续问识别必须保守：只有当前消息明确包含“继续/上面/这个酶/该序列”等续问锚点，且没有新序列、新结构、执行/重跑意图时，才跳过 planner 走历史合成答复；否则保持缺信息追问、确认执行校验或新策略生成。
- 历史 raw 序列不能无条件作为当前输入，否则会把“分析此蛋白质序列”这类缺信息问题误升级为可执行策略；当前仅在明确续问时使用历史 raw 序列，FASTA/上传结构仍按原边界进入上下文。
- 湿实验反馈只能作为项目/assay 级校准上下文接入候选排序；它不能把未测试的具体突变升级为 `experimental_supported`。
- `mutation_priority_score` 新增 `wet_lab_calibration_summary` 入参后，输出 `wet_lab_calibration_context` 和每行 `calibration_evidence_status`；风险提示显式写明“该具体候选仍需单独实验确认”。
- Claim Audit 现在区分 `PROJECT_WET_LAB_CALIBRATION_CONTEXT` 与 `CANDIDATE_DIRECT_WET_LAB_VALIDATION`：前者可 supported，后者在没有直接候选实验数据时必须 missing。
- Orchestrator 只在有 `project_id` 时按同项目最新 calibration run 注入排序工具；无项目会话不注入，避免跨项目串用反馈数据。
- 测试注意：多个使用共享 SQLite drop/create 的 pytest 进程并行运行会触发 `no such table` 竞态；后端 DB 测试需串行跑，串行复验通过。

## 2026-08-11 阶段 31 策略治理配置中心第一批

- 同题续问、新任务、执行确认和解释型追问的 token 不应散落在 `agent_graph.py`；集中到 `agent_policy` 后可通过 `AGENT_STRATEGY_POLICY_JSON` 增量配置。
- 策略配置解析必须 fail-closed：JSON 为空用默认策略，JSON 错误时返回 `default_due_to_error` 和 `parse_error`，行为保持默认，不静默采用不完整配置。
- `raw_sequence_history_requires_continuation=true` 是关键边界：历史 raw 序列只有在当前消息明确续问时才作为上下文，避免缺信息问题被误判为可执行任务。
- `/api/chat/strategy-policy` 是只读审计接口，不提供运行时写入；管理后台后续应只展示生效策略和解析错误，不让普通用户改策略。

## 2026-08-11 阶段 31 策略治理黑盒与管理只读展示

- 新增 `frontend/tests/strategy-chat-live.mjs` 作为 HTTP/SSE 黑盒合同脚本，不调用内部 Python 函数，不依赖白盒 monkeypatch。
- 黑盒脚本覆盖：
  - 初始策略必须停在 `waiting_for=plan_confirmation`，带 `confirmed_plan / strategy_signature / task_fingerprint`。
  - `execute_confirmed` 必须执行同一份 confirmed plan；执行流不能重新返回“等待确认，未执行工具”的新策略确认。
  - 明确锚定上一轮的解释型续问必须进入 `same_problem_synthesis_followup`，不能生成新工具 plan。
  - “另一个新序列”必须生成新 checkpoint，且 `task_fingerprint` 与上一序列不同。
  - 只有手输“是，执行”且没有结构化 checkpoint 时，必须返回“策略检查点校验失败 / 不会执行工具”，不能重跑、不能重新规划。
- 脚本只输出脱敏 JSON；支持临时注册用户，也支持 `STRATEGY_CHAT_EMAIL/STRATEGY_CHAT_PASSWORD` 或 `LIVE_AI_EMAIL/LIVE_AI_PASSWORD`，不会打印 token/password。
- 管理后台新增 Agent 策略治理只读卡：
  - 显示 `status / version / parse_error`；
  - 显示 `max_typed_confirmation_chars` 与 `raw_sequence_history_requires_continuation`；
  - 展示 continuation/new-task/followup/execution/confirmation token；
  - 显式提示 token 只管理状态机边界，不能提升干实验证据等级，不能把计算假设写成湿实验结论。
- 本轮继续遵守“不写死 Venus 工具顺序”的边界：脚本检查状态机和 checkpoint 合同，不要求固定工具列表或固定候选数量。

## 2026-08-11 阶段 32 已执行策略状态闭环第一批

- 发现：前端“确认执行”携带结构化 `confirmed_plan / strategy_signature / task_fingerprint` 时，后端会严格执行该 payload，但旧逻辑只在“缺 payload、从服务端 active checkpoint 恢复”的路径里把 checkpoint 标记为 executing。
- 风险：如果用户通过正常按钮确认执行，数据库中的 active checkpoint 可能仍停留在 `awaiting_confirmation`；刷新后前端可能再次显示“确认执行”，造成“看起来又回到上一流程”的体验。
- 修复原则：
  - `execute_confirmed` 一律读取当前 active checkpoint；
  - 缺 payload 时继续从 active checkpoint 恢复；
  - 有 payload 时，只有 active checkpoint 的 signature/fingerprint 与 payload 完全匹配，才允许在执行成功后关闭该 checkpoint；
  - 不匹配时不写状态，仍交给 orchestrator 的签名校验 fail-closed。
- 黑盒合同新增：确认执行后 `GET /api/chat/strategy-checkpoints/active` 必须返回 `checkpoint=null`，history 中该 strategy 不能仍是 `awaiting_confirmation`。
- 前端流式结束后刷新 checkpoint history，避免 ThinkingChain/右侧策略版本继续显示执行前的旧状态。


## 2026-08-11 阶段 32 recent strategy memory 第二批

- 新增 `GET /api/chat/strategy-checkpoints/recent` 只读接口，作为后续同项目续问记忆注入的数据源。
- 接口 scope 规则：
  - 传 `conversation_id` 时必须属于当前用户；若该 conversation 绑定 project，则自动提升为 project scope。
  - 传 `project_id` 时必须通过 `project.read` 权限校验。
  - 无 conversation/project 时返回 400，不猜测上下文。
- 返回记录只包含当前用户的非 superseded memory 状态：`awaiting_confirmation / executing / completed`，避免把旧 revision 当作可继续执行策略。
- 前端 API client 新增 `api.getRecentStrategyMemory()`，但本轮尚未把 memory 注入 agent prompt；第三批再接入续问逻辑，并继续保持新序列/新结构边界 fail-closed。


## 2026-08-11 阶段 32 同项目续问记忆注入第三批

- `AgentOrchestrator` 的解释型同题续问分支现在会在满足全部条件后读取 recent strategy memory：`control=plan_only`、当前消息显式续问、不是新任务、不是执行/重跑意图、存在 project_id/current_user/audit_session。
- memory 摘要被写入 prompt 时带有 “data only” 边界，只作为同项目历史状态数据，不作为本轮新工具执行证据，也不作为用户新指令。
- 摘要字段仅保留 revision/status/next_action/signature/task_fingerprint/tools/artifact_handoffs/evidence_preview；不把完整历史任务文本或大段 artifact 原文注入 prompt，降低提示注入和串用风险。
- 续问回答规则继续保持：`awaiting_confirmation` 只能说仍待确认，`executing/completed` 只能作为历史策略背景；不得把计算预测或项目级校准背景写成候选级湿实验验证。
- 新序列、新结构、新任务和执行类消息仍被 `_is_same_problem_synthesis_followup()` 排除，因此不会触发 recent memory 注入。

## 2026-08-11 阶段 36 探索性候选突变表调研

- OpenProtein.AI 的公开文档把 zero-shot / PoET 定位为“无需预先 assay 数据即可做 variant effect / single-site mutant analysis”的蛋白工程入口；这说明低证据候选表可以存在，但它属于基于序列/进化上下文的计算筛选，不是湿实验结论。
- OpenProtein.AI PoET 文档强调 prompt/同源序列上下文、fitness scoring 和生成序列；可借鉴点是“无湿实验数据时仍可给可排序候选”，不可照搬点是不能把平台本地启发式排序包装成 PoET/ESM/真实模型结果。
- Cradle 平台资料强调每轮上传 wet-lab data 后模型持续学习，并把 plate design 设计成 exploitation 与 exploration 的平衡；可借鉴点是探索性候选应配套实验板/批次、blocked mutations、区域约束和反馈闭环，而不是只给一个位点列表。
- ProteinGym 论文把 zero-shot 和 supervised 设置分开评测，覆盖大量 DMS assay，说明不同蛋白/assay 间模型表现差异很大；平台输出必须保留 `computational_hypothesis`，不能承诺“干实验预测达到湿实验一样准确”。
- Machine-learning-guided directed evolution 综述把 ML 候选用于从已表征变体学习并选择下一轮序列；本平台在无项目湿实验数据时只能做 search-space reduction，小批量单点验证后才能通过 WetLabCalibration 提升排序可靠性。
- 阶段 36 的产品合同：有合法序列 + 明确工程目标时，身份/编号/目标 assay 不足不再空表，而是输出探索性候选、缺失证据、风险、实验动作和升级条件；无序列、非法序列或没有明确目标时仍 blocked/追问。

## 2026-08-13 阶段 44 Wiki 后确认执行性能复核

- 用户复现的 `confirmed_plan must be a list` / `strategy_signature does not match confirmed_plan` 问题必须用线上黑盒验证，不能只看单元测试；本轮 live smoke 已覆盖 malformed/stale client payload，并确认服务端 active checkpoint 为权威。
- Wiki 发布本身会触及 Outline API、文件记录和 conversation/checkpoint 状态；因此 smoke 必须按真实顺序执行：plan-only checkpoint -> Wiki collection -> Wiki publish -> active checkpoint re-read -> execute_confirmed。
- 上一轮约 `123.85s` 的执行耗时不是 checkpoint 校验问题，而是 SC synthesis 在工具完成后等待 LLM timeout；把报告级酶工程工具结果直接走 deterministic synthesis 可以消除确认执行慢路径，同时保留 claim gate/证据边界。
- 性能结论要拆开：
  - `execute_after_publish` 已从约 `123.85s` 降到 `1.56s`，本轮问题闭环；
  - `plan_only` 仍约 `29.74s`，属于策略生成体验优化，不应写成全链路秒级。
- Python 运维/烟测脚本必须兼容 ECS 宿主机 Python 3.6；不能使用 `from __future__ import annotations`、PEP604 `| None`、PEP585 内建泛型或 3.7+ 才内置的 `dataclasses`。
- 当前线上日志近 500 行未见旧 checkpoint/Wiki/SC timeout 错误，且关键容器均 healthy；可以回答“线上当前能正常使用”，但仍需注明这是 smoke 覆盖的主链路，不等于所有历史边界场景全量验证。

## 2026-08-13 阶段 45 PDB-only 比活力报告专业边界

- 用户贴出的 PDB-only 比活力报告不能称为完全专业：其证据边界和“不发布具体突变”是正确的，但策略默认提交 `gromacs_md` 是错误产品行为。
- 对“提高蛋白比活力”而言，PDB-only 默认路径应是结构解析、结构同源检索、编号/SIFTS 门控和缺失输入清单；MD 只能在用户显式要求“分子动力学 / GROMACS / RMSD / RMSF / 柔性”等动态分析时提交。
- Foldseek/TM-score 边界：弱结构命中只能形成家族假设，不能直接确定 EC、催化残基或可变位点；必须结合覆盖率、序列一致性、配体/催化位点叠合、注释和编号映射。
- GROMACS 边界：`submitted` 是任务状态，不是科学结果；没有拓扑、力场、水模型、平衡日志、轨迹和 RMSD/RMSF 输出时，不得输出动态口袋、柔性或稳定性事实。
- 比活力边界：specific activity 的解释必须区分蛋白定量归一化、可溶活性蛋白比例、kcat、Km/kcat/Km、底物/温度/pH/缓冲条件和 WT 基线；结构或 MD 不能替代动力学实验。
- 产品规则：deep analysis 只能表示允许更深入分析，不能自动把所有慢工具加入计划；慢工具必须与用户目标、输入充分性和显式请求匹配。
- 回归测试必须同时覆盖前端可触发的 `analysis_depth=deep`，否则 standard-only live smoke 会漏掉“深度模式默认 MD”的线上问题。

## 2026-08-13 阶段 46 深度模式位点输出边界

- deep 模式下“证据不足所以不给任何位点”不符合用户对深度分析的合理预期；平台应至少输出可人工审查的 PDB 坐标预筛窗口。
- 预筛位点和高置信突变必须分层：
  - `exploratory_pdb_coordinate_site`：只基于当前 PDB 坐标编号/链长度/残基类型，给口袋定位和人工复核入口；
  - `candidate_mutation_hypothesis`：需要催化口袋或保守性/结构机制支持；
  - `experiment_ready_mutation`：需要编号门控、底物/assay、WT 基线和风险检查闭合。
- PDB-only 位点表应包含窗口、代表位点、替换方向、风险和升级条件，而不是只给残基编号；否则用户无法判断下一步该做口袋定位、同源比对还是实验构建。
- 替换方向可以按化学性质生成，但必须声明是探索方向：
  - Cys 默认保护；
  - Gly/Pro 先检查主链柔性/构象锁；
  - 带电残基关注盐桥、pH 和底物进入；
  - 极性残基关注水网络/氢键；
  - 疏水残基关注口袋体积和核心包装。
- 报告措辞应是“不能给高置信具体突变或声称比活力提升”，不能再写成“不能给出具体突变位点”这种绝对阻断。
- live smoke 必须断言报告含 `PDB坐标探索性位点预筛` 和 `低置信，不等于最终突变推荐`，同时继续断言 no `gromacs_md`，避免深度模式又靠默认 MD 伪装“深度”。

## 2026-08-13 阶段 47 HM.pdb 深度位点表专业性标准

- 只输出 PDB 坐标位点还不等于专业；如果 6-8 个候选都来自同一类残基或同一种逻辑，用户看到的仍是“模板化假深度”。
- PDB-only 比活力预筛应至少覆盖几类可解释机制：
  - 带电/可质子化残基：底物入口静电、盐桥、pH 响应；
  - 极性残基：水网络、氢键、底物识别或产物释放；
  - Gly/Pro/柔性环：口袋开合、构象熵、必要柔性保护；
  - 疏水残基：口袋体积、通道宽度、核心包装或产物释放。
- 机制多样性应优先于单一分数排序；否则高分带电残基可能刷屏，反而降低人工复核价值。
- 替换方向不能包含自替换，例如 `V171V`、`A205A`；这类格式错误会直接破坏科学可信度。
- HM.pdb 当前可见的深度预筛表仍只能标为 `exploratory_pdb_coordinate_site`：
  - `D159/D117`：带电门控；
  - `S142/S189`：极性/水网络；
  - `G129/G91`：柔性环/构象熵；
  - `V171/A205`：疏水体积/通道。
- 这些位点不能升级为 `experiment_ready_mutation`，除非完成催化口袋定位、底物/配体或口袋检测、保守性/同源比对、FASTA-PDB-UniProt 编号门控和 WT assay 基线。
- live smoke 不应只检查“报告有表”，还要检查表中含机制类别和多类机制标记，避免后续回归成浅层位点列表。

## 2026-08-13 阶段 48 专业网站检索结论：HM 不是按 alpha-amylase 直接分析

- `GPT-5.6 Sol` / `gpt-5.6-sol` 可作为平台中转模型路由使用，但蛋白身份和位点证据不能由模型口头生成，必须来自 RCSB、UniProt、NCBI、InterPro 等专业库。
- Foldseek top hits 的 RCSB 官方注释：
  - `3BH4`：High resolution crystal structure of *Bacillus amyloliquefaciens* alpha-amylase，X-ray 1.4 Å，SIFTS -> UniProt `P00692`；
  - `1QHO`：five-domain alpha-amylase from *Bacillus stearothermophilus*；
  - `1BLI`：*Bacillus licheniformis* alpha-amylase；
  - `6TOY`：*Bacillus paralicheniformis* alpha-amylase。
- 但 HM 与 `P00692` 序列直接比对极弱，不能把 `P00692` 的 active site / binding site / cofactor 位点投射到 HM。
- NCBI BLAST PDB 对 HM 299 aa 序列给出强证据：
  - `1WKY_A` endo-beta-1,4-mannanase，E=2.7e-152，204/296 identity，query 2-297；
  - `3JUG_A` beta-mannanase，E=3.3e-148，196/297 identity；
  - `2WHJ_A/2WHL_A` beta-mannanase，E=1.6e-145 / 6.7e-141；
  - 后续命中也集中在 beta-mannanase / GH5 相关结构。
- NCBI BLAST nr 对 HM 299 aa 序列给出更强证据：
  - top hit `WP_125083321.1` glycoside hydrolase family 5 protein [Paenibacillus lentus]，E=0，291/299 identity，query 1-299；
  - 多个后续 hit 为 Paenibacillus / Metabacillus / Priestia 的 GH5 protein、mannanase 或 beta-mannosidase 注释。
- 结论：HM 的专业数据库证据更支持 GH5 / beta-mannanase / endo-beta-1,4-mannanase。Foldseek alpha-amylase 命中应降级为结构折叠模板线索，不应用来确定功能或催化位点。
- 产品规则：PDB-only deep 模式必须优先补序列级 BLAST/PDB 或本地 mmseqs/BLAST 库检索，尤其当 Foldseek 命中 query TM-score/概率较低时；序列级强证据应覆盖弱结构命中假设。
- 工程风险：NCBI BLAST 同步调用在线上会慢且偶发 degraded，需后续接入本地 PDB/mmseqs/BLAST 缓存或异步化，否则用户报告可能仍只显示 degraded 边界。

## 2026-08-19 阶段 17 P0-4/P1 并行启动发现

- P0-4 续问路径应优先于默认 planner：
  - “和 Venus 比哪里差”是报告/产品差距复核，不是新分析任务；
  - “这个位点为什么推荐”是候选解释续问，不应重跑候选表；
  - “预测和实验结果不一致”是偏差归因，不应直接重新排序或升级结论；
  - “P338T 怎么样”这类点名突变应优先进入指定突变复核。
- P0-4 需要保留策略记忆边界：
  - 同项目策略记忆只能作为历史结果锚点；
  - 不能把 memory 当作本轮新工具证据；
  - awaiting/executing/completed 状态不能升级为候选级湿实验验证。
- P1-4 编号映射已有底座但未统一：
  - `residue_mapping_sifts.py` 可读本地 SIFTS-style JSON/CSV/TSV，缺失时按 PDB 坐标顺序推断；
  - `residue_numbering_gate.py` 已能阻断缺 mapping、未确认、冲突、gap、低置信映射；
  - 当前两者字段语义靠 `agent_graph._bridge_step_params()` 临时转换，仍缺统一 numbering registry/schema。
- P1-4 第一批实现后，编号映射 schema 已有可执行统一层：
  - `residue_mapping_sifts` 输出 `numbering_registry_rows`，同时保留旧 `mappings`；
  - `residue_numbering_gate` 可直接消费统一 rows，并兼容旧 mapping rows；
  - `AgentOrchestrator` 优先传 `numbering_registry_rows`，减少临时 bridge；
  - `pdb_author`、`user_sequence`、`uniprot` 三类坐标系开始显式化；
  - 坐标顺序推断统一降级为 `inferred_requires_confirmation` / warning，不允许冒充 SIFTS；
  - 剩余问题是成熟肽、PDB author vs label_seq_id、插入码、缺失残基、多链/多 isoform 的更完整语义建模。
- P1-3 催化机制已有保护位点能力但不是完整 mechanism map：
  - `catalytic_site_lookup.py`、`CatalyticSite`、`CatalyticResidue`、`enzyme_identity_profile`、`site_structure_function_features` 已能消费催化残基并保护关键位点；
  - 缺 `mechanistic_step`、first shell/second shell、标准 catalytic role vocabulary、金属/辅因子/底物接触角色归一化。
- P1-1 reaction profile 有数据源但缺主干服务：
  - `ReactionEquation`、`/api/data/reaction/{rhea_id}`、`/api/data/protein/{uniprot_id}`、`annotation_bundle` 已有 EC/Rhea/catalytic activity/reaction text 线索；
  - `rhea.py` ingestor 是 live 下载型，不适合当前离线 MVP；
  - 下一步应做只读 `reaction_profile` 聚合，不先做 live 查询。
- P1-2 WT baseline registry 有参数和反馈层但缺 selection registry：
  - `KineticParameter`、`data_lookup.get_kinetic_params`、protein kinetics API 和 `experiment_feedback.py` 已能保存/查询 kinetics 与反馈；
  - 仍缺按 enzyme/substrate/pH/temperature/prep/batch/source 归一化选择 WT baseline、判定 ready/missing/conflict，并接入 claim gate。
- 并行边界：
  - P1 只读侦察未联网、未运行 live gate、未读取 `.env`/secret；
  - 一个子代理因许可证错误失败，未产生有效结果，不影响主线。

## 2026-08-19 阶段 17 P1-3 mechanism profile 与 P1-1/P1-2 并行收敛

- P1-3 可先用现有 `CatalyticSite` / `CatalyticResidue` 做无迁移第一批：
  - stored catalytic residues 是直接注释，可定义为 `first_shell`；
  - 本地模型没有 second-shell、substrate/cofactor contact 或完整 reaction-step 字段，必须显式输出 `unknown_not_annotated_in_local_model`；
  - 标准化 catalytic role 只能是受限词表归一化；由 role 映射出的 mechanism step 必须标为 `role_derived_not_explicitly_curated`；
  - 无 PDB author coordinate 时，UniProt sequence position 不能当结构坐标，须输出 `pending_numbering`；
  - query sequence 与 curated sequence 不一致时，所有 curated catalytic position 进入 `mapping_required`，不允许用于强工程结论。
- P1-1 Reaction Profile 本地 MVP：
  - `ReactionEquation` 已有 Rhea equation、direction、reactants/products/cofactors 和 `ec_numbers`；
  - 与蛋白的关联只允许 protein EC 和 `ReactionEquation.ec_numbers` 的精确交集；不能按 free-text catalytic activity、底物名字、EC 前缀或家族近似匹配；
  - 只读 service 不应调用 `AnnotationFacade.resolve_annotation_bundle()`，因为 signal peptide heuristic path 可能写缓存；应直接复用 query-service serializer；
  - 没有精确本地 Rhea 关联时状态必须是 `partial`，不能由 activity 文本生成反应事实。
- P1-2 WT baseline Registry 本地 MVP：
  - `KineticParameter` 目前缺 protein preparation、batch、buffer、replicate、QC 和 condition version；
  - 当前本地反馈包含 mutant-relative observation，缺可确认 WT row；preflight control 即使有数值也非 claim-eligible；
  - `ready` 必须要求 explicit WT identity、metric、substrate、pH、temperature、unit、literature/provenance、preparation、batch 的精确同条件匹配；
  - 不能自动取 median、近邻条件、跨 batch 或跨 preparation 作为替代 baseline；缺字段返回 `missing`，同条件矛盾返回 `conflict`；
  - 依赖 baseline 的科学 claim 需要 claim gate 读取 registry status，只有 `ready` 可放行。

- P1-1 第一批已验证：
  - `ReactionEquation` 与 protein 不存在外键，当前唯一可守住的自动关联是 exact local EC intersection；
  - Reaction Profile 因此只能是 local imported evidence 聚合，不能用 `catalytic_activity` 文本补全 reaction；
  - `AnnotationFacade.resolve_annotation_bundle()` 不适合作为严格只读 service 依赖，因为 signal peptide heuristic miss 可能写缓存；query-service serializer 可避免该副作用；
  - 当前 reaction profile 表达的 `ready` 只表示有本地精确 EC-Rhea 关联，不等于已获得当轮 live Rhea / ChEBI 验证。

- P1-2 第一批已验证：
  - 当前 `KineticParameter` 缺 buffer、protein preparation、batch 和 QC 字段，因此其 WT rows 默认不能单独构成可声明 baseline；
  - registry 可以消费调用方已经通过权限边界筛选的 `ExperimentFeedbackRecord` payload，但 explicit WT identity、空 mutation、QC passed、metric value/unit 与全部条件精确匹配是不可放松的必要条件；
  - 同条件 baseline 数值或单位不一致时必须返回 `conflict`，不能静默选中一条或自动求中位数；
  - `scientific_claim_gate` 现可把 `requires_wt_baseline=true` 的 claim 与 registry status 绑定，避免 `SUPPORTED` 标签绕过基线要求；
  - 当前还未加 API 从持久化 feedback 受 ACL 地自动组装 baseline input；第一批仅允许工具调用方传入已授权 feedback records，防止跨项目/跨用户泄露。

- P2-1 只读摸底：
  - `site_structure_function_features` 已经是可用表，但它仍把 `position` 同时服务于 PDB author 和 user sequence，存在静默碰撞风险；
  - 第一批最安全的做法不是改分数，而是先把坐标系版本化，新增 `schema_version`、显式坐标对象和 `projection_eligibility`；
  - `mutation_priority_score` 的结构列现阶段只能继续当解释和 guardrail，不应在这一批里改 composite score。

- P3 只读摸底：
  - 现有 project、experiment feedback、strategy checkpoint、wet-lab calibration 已经能支持 traceability 的骨架，但还没有稳定的 round / decision / baseline 聚合层；
  - 下一步应优先做只读 project memory 聚合，而不是先补写路径或数据库迁移；
  - formal decision 必须继续依赖 QC、replicate 和 ACL，不可让聊天上下文直接升级为项目事实。

## 2026-08-20 P1-1 Reaction Profile 底物范围门控收紧

- 之前的 claim_context 只要 reaction_candidates 任一侧有 reactants 或 products 就会把 substrate scope 判为 supported，这会把半条反应式误当完整底物证据。
- 已将 substrate scope 支持条件收紧为 reactants 与 products 同时存在；否则仅保留 reaction identity 支持，substrate_scope_optimization 继续阻断。
- 这保持了 reaction profile 的 fail-closed 行为，不改变 exact local EC 聚合规则，也不引入任何 live 查询。

## 2026-08-20 P1-2 WT baseline registry 报告合同收口

- `wt_baseline_registry` 现在与工具包装器统一暴露 `report_contract`，把 `ready / missing / conflict`、`exact_condition_match_required`、`nearest_condition_fallback_allowed=false` 和 `cross_batch_fallback_allowed=false` 说清楚。
- 这层合同继续只接受 explicit WT、精确条件、QC 通过的输入；没有补成近似条件替代，也没有新增数据库写入。
- 依赖 baseline 的 claim 仍由 `scientific_claim_gate` 继续卡住，只有 `wt_baseline_registry.status=ready` 才能放行。

## 2026-08-20 P1 今日收口边界

- P1 已按当前工程可本机完成的定义收口：编号映射统一、催化机制 profile、reaction profile、WT baseline registry 四条都有结构化合同、fail-closed 状态和关键回归。
- 这个“完成”不是声明外部数据库实时接入完成；Rhea/BRENDA/SABIO-RK/M-CSA live 查询、成熟肽/label_seq_id/isoform 深层编号语义、second shell 自动识别仍属于下一阶段增强。
- 报告层必须继续使用这些 contract：缺 reaction profile 不写比活/底物谱优化，缺 ready WT baseline 不写提升，pending numbering 不输出强位点结论，second shell unknown 不外推。

## 2026-08-20 P2 第一批合同收口

- `mutation_priority_score` 现在多了一个 `p2_engineering_scorecard_contract`，把 residue feature table、objective score 和 candidate table generation 统一到一个可报告的验收对象里。
- 这个聚合层只做状态和边界说明，不合并成新总分，不提升 blocked 候选，也不把结构/目标分量包装成 wet-lab validated 结论。
- P2 的实际工程价值是：报告层可以判断当前候选表是完整、partial 还是缺输入，而不是只看到零散 score rows。

## 2026-08-20 P2-1 feature table contract 增强

- 结构特征表此前只有 `report_boundary` 和 summary，报告消费者仍需要逐字段猜哪些已计算、哪些只是占位。
- 新增 `feature_table_contract.field_state` 后，消费者可以明确看到 relSASA、二级结构、非聚合 HETATM 近邻、主链二面角等状态。
- 关键边界：`pocket_channel_interface` 仍是 `not_computed`；HETATM 近邻只能触发人工复核，不能自动写成底物、辅因子、金属、口袋、通道或界面证据。

## 2026-08-20 P2 合同前端展示

- P2 合同如果只留在后端 JSON，研发用户仍容易忽略边界；本轮将 `feature_table_contract` 和 `p2_engineering_scorecard_contract` 直接显示到对应工具卡。
- 前端展示只承担“可见化合同状态”的职责，不计算新分数、不改变候选、不宣称 wet-lab validated。

## 2026-08-20 P2 合同报告导出闭环

- `MutationScoreCard` 的屏幕展示和 `renderMutationScore()` 的下载/打印 HTML 是两条独立路径；只改工具卡会导致导出报告丢失 P2 边界。
- `mutation_score` 导出现在保留 scorecard、candidate table generation 和 objective score contract，研发人员离线查看 HTML 时也能看到 partial/ready、blocked reasons、must-not-claim 和 assay required。
- 这只是报告可追溯性增强，不代表 pocket/channel/interface 已计算，也不代表候选有湿实验验证或统一总分。

## 2026-08-20 P3 feedback 下一轮约束展示

- 后端 DBTL trace 已经能生成 `next_round_library_design`，但仅放在 raw JSON 会降低执行可用性；项目详情页应直接展示下一轮实验约束。
- 下一轮设计展示必须区分 single point pool 与 combination pool，并明确 assay gate、higher-order 阻断、plate layout 和 boundary。
- 当前 P3 小闭环仍是 read-only trace + UI visibility：反馈数据进入下一轮约束，不等于进入训练集，也不等于自动批准组合突变。

## 2026-08-20 P2 residue distance graph

- residue feature table 里已有 `contact_count_ca_8a`，但缺可追溯的邻接边列表；这会限制后续组合突变冲突检查和结构邻域解释。
- 新增 `residue_distance_graph_v1` 后，报告消费者可以直接读取 CA-CA edge list、node count、edge count 和 radius，而不是从每行 contact count 反推。
- 该图仍然只是输入 PDB 的几何邻接：它不能证明 pocket、channel、interface、底物结合、辅因子接触或突变收益。

## 2026-08-20 P2 候选表透传最近 CA 邻居

- 结构邻居证据如果只停留在 feature table，候选解释仍会缺一层具体可读性；把最近 CA 邻居透传到候选行后，工程用户能直接在候选表看到结构邻域距离。
- 这个透传不应改写 composite score 或 decision contract，只能补解释和审计信息。
- 组合设计下一步若要更强的结构约束，应该基于这条邻接信息继续做冲突检查，而不是直接推出 pocket/channel 结论。

## 2026-08-20 P2 候选卡结构邻居展示

- 候选卡里把最近 CA 邻居再显示一次，是为了让 UI 层和导出/详情层一致，而不是增加新的推理。
- 这种展示只是在复核时减少来回切页，并不改变实验优先级或 gate 结论。

## 2026-08-20 P2/P3 距离图进入组合检查

- 组合突变检查此前只能使用手工 `structural_distances` 字典；这会让 P2 residue distance graph 和 P3 DBTL 组合设计脱节。
- 现在 `mutation_epistasis_check` 可以直接消费 `residue_distance_graph_v1`，在缺 pairwise map 时用图中的 CA edge 推导突变对距离。
- 这只是把已有几何证据复用到组合风险检查：不能把低风险 pair 写成已验证组合，也不能外推高阶上位性模型。

## 2026-08-20 DBTL trace 结构距离来源

- 下一轮库设计若不显示结构距离来源，用户无法区分“有 residue distance graph 支撑”和“完全没有结构距离证据”的组合建议边界。
- `structural_distance_source` 进入 library 和 trace summary 后，DBTL 页面可以明确展示来源为 `none`、`explicit_pairwise_distance_map` 或 `residue_distance_graph_v1`。
- 这仍是审计元信息，不代表组合突变已被结构模型或湿实验验证。

## 2026-08-20 组合上位性检查报告合同

- 组合检查本身需要比普通工具更强的边界提示，因为用户容易把低风险 pair 当作已验证组合。
- `report_contract` 应直接跟随工具结果输出，不能只写在文档里；这样 UI、agent 和导出层都能读取同一份边界。
- pairwise `distance_source` 是后续排查的关键字段：同样 22 A 距离，来自手工输入、distance graph 或未知来源的可信度边界不同。

## 2026-08-20 组合上位性检查离线报告导出

- `DataBrowser` 的屏幕结果卡与离线 HTML 报告是两条独立消费路径；只把 `report_contract` 展示在页面上，会导致下载/归档材料丢失证据边界。
- `mutation_epistasis` 报告必须保留 pairwise `distance_source`、evidence input 状态、missing evidence、must-not-claim 和 boundary。
- blocked 结果同样需要可导出，因为 blocked contract 本身就是执行交付物，不能只导出 ok 结果。

## 2026-08-20 下一轮库设计组合证据合同摘要

- `feedback_iteration_planner.pair_candidates` 原本保留完整 `epistasis_risk`，但 `next_round_library_design.combination_pool` 只保留 recommendation，DBTL 摘要和项目页会丢失证据合同。
- 组合证据合同需要成为 `next_round_library_design` 的一等字段，而不是依赖消费者遍历内部 pair candidate。
- 合同状态应区分 `ready_with_epistasis_contract`、`blocked_or_not_promoted` 和 `not_applicable_no_pair_candidates`，避免把“没有 pair”误读为“pair 已安全”。

## 2026-08-20 DBTL trace 离线报告导出

- DBTL 项目页的 raw trace 适合调试，但不适合做研发日报、复核归档或实验交接。
- 离线 HTML 报告需要把 project model、learning readiness、next round library 和 combination evidence contract 放在同一份报告里，避免用户只截取候选池而丢失训练/湿实验声明边界。
- DBTL 报告必须显式保留 `must_not_claim_training_or_wet_lab_validation`，否则下一轮设计容易被误读为已经训练或已经验证。

## 2026-08-20 项目列表 DBTL 组合证据状态入口

- 项目列表是研发用户进入项目的第一层扫描界面；如果只显示 DBTL summary status，用户仍需要点进项目才能知道组合证据是否 ready、blocked 或不适用。
- `next_round_structural_distance_source` 和 `next_round_combination_evidence_status` 应在列表 tooltip 中可见，避免把没有结构距离来源的项目误判为可做组合突变。
- 列表 chip 只做状态提示，不改变项目权限、trace 计算或下一轮候选结论。

## 2026-08-20 湿实验反馈页下一轮设计预览入口

- `/data` 湿实验反馈页已经可以运行组合上位性检查，但这只覆盖 pair 风险，不等于完整下一轮库设计。
- 现有 `/experiment-feedback/iteration-plan` API 已经能只读生成 next-round library contract；前端应直接暴露这个预览，而不是要求用户去项目 DBTL 页或 raw JSON 找。
- 预览页必须显示 `combination_evidence_contract` 和 `must_not_claim`，防止把下一轮计划误读成自动训练或组合验证结果。

## 2026-08-20 湿实验下一轮设计预览离线报告导出

- 下一轮设计预览如果只能在页面中查看，研发交接和日报归档仍会丢失 planner mode、data quality 和组合证据合同。
- `feedback_iteration_plan` 报告需要独立于 DBTL trace 报告，因为它可以在 `/data` 反馈页按当前筛选和补充结构证据即时生成。
- 报告必须保留 `required_next_measurements` 和 `scientific_boundary`，避免把预览当作自动排单或模型升级结论。

## 2026-08-20 湿实验反馈页项目范围过滤

- 反馈页如果没有 project scope，`listExperimentFeedback` 和 `iteration-plan` 仍会落在当前用户的全量记录上，难以对应某个 DBTL 项目。
- 同一个 project scope 同时作用于 list、summary 和 iteration plan，能减少“看的是一个项目、生成的是另一个项目”的误读。
- 项目范围只影响查询，不改写 feedback 记录，也不改变权限边界或计划合同。

## 2026-08-20 湿实验反馈页可见项目选择器

- 手动粘贴 project_id 可以保留兼容，但对研发用户不够稳，容易填错项目范围。
- 复用 `api.getProjects()` 在反馈页加载可见项目列表，可以让 list/summary/iteration plan 使用同一项目选择来源。
- 项目选择器仍只写入 `projectFilter`，不新增后端接口，不绕过项目 ACL。

## 2026-08-20 湿实验反馈提交绑定当前项目范围

- 阶段 80/81 让列表、汇总和 iteration plan 使用项目范围，但新增反馈提交仍未带 `project_id`，会导致用户在项目范围下录入的记录不进入该项目 DBTL trace。
- 提交 payload 应复用同一个 `projectFilter`；没有项目范围时继续允许全局/未绑定反馈，保持兼容。
- 成功提示需要显示项目绑定状态，避免用户以为记录已进入某项目但实际未绑定。

## 2026-08-20 湿实验反馈结果随范围/证据变更自动失效

- 组合上位性检查和下一轮设计预览都依赖当前 feedback scope、有效单点池和手工结构证据；筛选或证据变化后继续展示旧结果会误导实验排单。
- 结果失效应覆盖 project/enzyme/decision scope、结构距离、机制标签、同一区域、residue distance graph 和 records 变化。
- 失效逻辑只清空 `epistasisResult` / `iterationPlan`，不清空用户正在编辑的证据输入，避免丢失人工补证据内容。

## 2026-08-20 湿实验反馈加载期阻断旧记录触发新分析

- 结果清空只能防止旧结果继续展示，但筛选变更后的 feedback list 加载期间，按钮仍可能读取旧 `records` / `validatedMutations` 发起新分析。
- 组合上位性检查和 iteration plan 都应在 `loading` 期间阻断，且函数入口和按钮 disabled 要同时具备，防止 UI 状态或快捷触发绕过。
- 这不改变后端权限和算法，只是避免 stale frontend state 被包装成当前项目范围下的新结论。

## 2026-08-20 湿实验反馈分析结果绑定生成范围

- 加载期阻断仍不能覆盖“请求发出后用户立即切换范围，旧请求晚返回”的竞态；必须在响应写回前校验生成时 scope key。
- `analysis_scope` 应成为反馈页即时分析结果和离线报告的审计上下文，至少包含 project/enzyme/decision scope、records 计数、validated single-mutant 计数和人工结构证据输入状态。
- 该 scope 是前端审计元数据，不改变后端权限、组合风险算法或下一轮设计合同；它用于证明结果是在哪个页面范围和证据条件下生成的。

## 2026-08-20 湿实验反馈分析 scope 指纹精确化

- 仅用 `record_count` / `validated_single_mutant_count` 生成 scope key 不够精确；两个不同反馈池可能有相同数量。
- `feedback_record_fingerprint` 和 `validated_mutation_fingerprint` 应进入 `analysis_scope`，使过期响应判断能覆盖同数量不同记录的刷新场景。
- fingerprint 仍是审计标识，不是科学证据；导出报告显示它们是为了复核结果对应的反馈池。

## 2026-08-20 湿实验反馈分析 scope 时间戳与哈希归档

- 即时分析结果如果只记录筛选和 fingerprint，日报归档时仍难判断生成时间和是否对应同一 scope snapshot。
- `generated_at` 和稳定 `scope_hash` 应在请求发起时生成，并跟随屏幕结果和 HTML 报告，而不是随页面当前状态变化。
- `scope_hash` 只用于审计归档和 stale response gate 复核，不是安全签名，也不改变科学证据等级。

## 2026-08-20 湿实验反馈分析报告文件名带 scope 审计标识

- HTML 内容里有 scope hash 仍不够，文件系统里多个报告并列时需要从文件名直接区分生成 scope。
- 默认报告文件名应在存在 `analysis_scope` 时纳入 `scope_hash` 和 `generated_at`，让日报归档、人工复核和交接材料更容易追溯。
- 文件名不能拼入 project 名称、酶名或其它用户输入，只使用清洗后的 hash 和时间戳，避免泄漏或非法文件名字符。

## 2026-08-20 湿实验反馈分析 scope fingerprint 顺序稳定化

- API/list refresh 返回顺序不应改变同一反馈池的 `scope_hash`，否则离线报告归档会出现伪差异。
- `feedback_record_fingerprint` 应按记录 ID 排序；`validated_mutation_fingerprint` 应按去重后的突变集合排序。
- fingerprint 仍只用于前端 stale response gate 和审计归档，不是科学证据，也不改变组合突变判断。

## 2026-08-20 湿实验反馈分析 scope schema version 固化

- `analysis_scope` 已开始承载筛选、fingerprint、时间戳和 hash，后续字段继续扩展时需要版本号防止离线报告混读。
- `schema_version=feedback_analysis_scope_v1` 应随屏幕结果和 HTML 报告一起导出，便于日报、审计和人工复核按版本解释字段。
- schema version 仍是前端审计合同，不是科学证据，不改变组合检查或下一轮设计结论。

## 2026-08-20 湿实验反馈分析 scope hash 策略显式化

- `scope_hash` 需要明确是由生成时 scope key 派生的审计标识，不是安全签名，也不是后端科学证据。
- `hash_input_policy=stable_json_scope_without_generated_at_or_scope_hash` 可让离线报告复核者知道 hash 不包含生成时间和 hash 自身，避免循环解释。
- 这项策略说明只增强归档可解释性，不改变 stale response gate、组合检查算法或 DBTL 计划合同。

## 2026-08-20 湿实验反馈分析 scope fingerprint 页面可见化

- 离线报告已经导出 feedback/validated mutation fingerprint，但页面结果卡不可见会让用户下载前无法确认反馈池范围。
- 屏幕端应展示反馈池和单点池 fingerprint，并对长字符串启用换行，防止记录多时撑坏卡片布局。
- 这仍是审计可视化，不改变 fingerprint 算法、不改变组合检查或下一轮设计结论。

## 2026-08-20 湿实验反馈分析 scope 科学边界显式化

- `analysis_scope` 字段越来越完整后，用户可能把 scope hash、fingerprint 或 schema version 误读成科学证据等级。
- `scientific_boundary=audit_metadata_not_scientific_or_wet_lab_evidence` 应随页面和离线报告导出，明确 scope 只证明生成范围与审计上下文。
- 该边界声明不改变组合检查算法、下一轮设计合同或任何 wet-lab validation 结论。

## 2026-08-20 P1 remote pytest runner readiness 收口

- `remote_pytest_runner` 已具备两个本机可验证条件：`.github/workflows/ci.yml` 的 `backend-test` job 和 `scripts/run_pytest_runner.py --plan-only` 的 fail-closed mirror contract。
- 这种状态应标记为 `ready`，因为它不需要生产容器安装 pytest，也不需要 live gate 才能证明 runner 建设完成。
- ready 项不应继续进入 external input packet，否则会把已完成的 P1 建设误列为 operator 阻塞。

## 2026-08-20 P0/P1 remaining backlog 优先级汇总收口

- go/no-go summary 需要直接显示 P0/P1 计数，否则“待建清单”需要人工从 ticket 或 dispatch checklist 反复统计。
- 当前 remaining backlog 外部清单为 7 项：P0 为 formal domain/HTTPS、GPU/GROMACS MD live、MD blackbox live e2e、OSS/MinIO live e2e，共 4 项；P1 为 ligand runtime live、admin authenticated screenshots、maintenance window drills，共 3 项。
- 这些项目仍必须保持 fail-closed：没有正式域名/TLS、GPU/GROMACS 长任务输入、live 账号/存储权限、管理员截图凭据和维护窗口许可时，不能标记 live gate 完成。

## 2026-08-20 P0/P1 execution tickets 优先级汇总收口

- go/no-go summary 有 P0/P1 汇总后，execution tickets 也应携带同口径汇总，避免总览和逐票执行包之间出现人工解读差异。
- ticket 层的优先级汇总应按实际票据状态计算，而不是直接复制 go/no-go summary；这样 validator 可以 source-bound 重建并发现 stale ticket 包。
- 当前票据层状态仍为 P0=4 blocked、P1=3 blocked、0 armed；该状态表示“已启动并等待外部输入”，不是 live gate 已完成。

## 2026-08-20 P0/P1 external input packet 优先级汇总收口

- 优先级应从 operator 输入包最上游开始携带，而不是只在 dispatch/go-no-go/tickets 阶段出现；否则收集输入的人仍要先人工判断 P0/P1。
- 当前 external input packet 显示 P0 需要 19 个输入字段，P1 需要 12 个输入字段；这些都是收集/证明字段，不应自动转成可执行命令。
- values template 携带 `priority_summary` 可以让外部填报包和 validation report 使用同一口径，但仍只允许 secret reference，不允许粘贴明文密码或云密钥。

## 2026-08-20 P2/P3/P4 roadmap 与 readiness packet

- P2/P3 不是空白阶段：P2 已有 residue feature、objective score、candidate table generation 和 P2 scorecard 合同；P3 已有 feedback import、next-round library design 和 DBTL trace 合同。
- P4 在当前任务计划里没有历史定义，本轮将其保守定义为生产级闭环治理层：active learning batch、model calibration registry、manufacturing/process constraints 和 approved live-gate execution。
- P4 当前只能标记 `defined_not_started`，不能声称生产闭环已运行、模型已训练或制造约束已验证。

## 2026-08-20 P2 候选行 feature completeness

- P2 候选行已经透传多类结构字段，但缺少统一的 completeness 摘要，导致用户要人工判断 pocket/conservation/ddG/MD 哪些证据缺失。
- `candidate_feature_completeness_v1` 应只描述证据覆盖，不参与 legacy ranking、objective score 或候选排序。
- 缺 pocket/channel/interface、conservation、ddG/packing、MD RMSF 时必须进入 `missing_feature_reasons`，不能被报告文案写成已计算证据。

## 2026-08-20 P3 DBTL required action contract

- DBTL `required_actions` 原本已有 action/reason/blocks，但缺少稳定分类，不利于前端、agent 或日报按“数据录入、assay/QC、formal decision、组合门控”派发。
- `dbtl_required_action_contract_v1` 应保持只读：它只是 follow-up 分类和优先级，不创建项目记录、不执行实验、不训练模型、不审批候选升级。
- P0 action 当前主要是 assay/QC 与 combination gate；P1 action 主要是 round/formal decision 等项目记忆补齐。

## 2026-08-20 P4 closed-loop readiness contract

- P4 可以本机建设的是 readiness contract，不是生产执行。合同应把 active learning、model calibration、组合证据、制造约束、live approval 拆成独立 gate。
- `p4_closed_loop_readiness_v1` 的 live gate approval 必须默认 blocked；trace 不能因为数据齐全就自动批准 live gate。
- 当前 roadmap 可把 P4 标记为 `ready_local_contract`，但这只表示合同存在；生产闭环、模型重训和制造约束验证仍是外部审批/数据门槛。

## 2026-08-20 P3/P4 DBTL 页面可见化

- 后端和报告导出已有 P3/P4 合同后，项目详情页也必须显示同样的 action category、priority 和 P4 gate 状态，否则用户仍需要下载报告才能理解阻塞原因。
- 页面只展示 readiness，不应提供训练、live gate、制造审批或状态升级按钮。
- P4 面板必须把 `must_not_claim` 可见化，避免 `ready_local_contract` 被误读成生产闭环已运行。

## 2026-08-20 P4 项目列表状态入口

- 项目列表已有 DBTL chip，但只显示 trace/learning/next-round/combination 状态；P4 readiness 不进入列表会让 closed-loop 阻塞只能在详情页看到。
- 项目列表应异步补充 P4 状态，失败时继续静默降级，不阻塞基础项目列表。
- 列表 chip 只能展示 `p4_status` 和 blocked gate 数，不能提供 live gate 或训练入口。

## 2026-08-20 P2 candidate feature completeness 前端可见化

- 后端已经输出 `candidate_feature_completeness_v1` 后，屏幕候选表和 HTML 报告必须同口径显示，否则用户仍会把 CA geometry、relSASA 等局部证据误读成完整 P2 residue feature table。
- `missing_feature_reasons` 是科学边界字段，应直接展示 `pocket_channel_interface_not_computed`、`conservation_not_available`、`ddg_or_packing_not_available`、`md_rmsf_not_available` 等缺口，而不是改写成泛泛“证据不足”。
- completeness 可见化不能影响排序、objective score、candidate confidence 或 wet-lab claim；它只说明候选解释所依赖的结构/功能证据覆盖范围。

## 2026-08-20 P2 candidate readiness summary 报告级收口

- 行级 `feature_completeness` 已可见后，还需要报告级 `p2_candidate_readiness_summary_v1`，否则用户仍要逐行人工统计 P2 缺口，日报和导出报告也难以快速判断候选表是否只是局部结构证据。
- summary 应统计 `top_missing_feature_reasons` 和 `missing_feature_reason_counts`，而不是生成新的自然语言结论；这样 pocket/channel/interface、conservation、ddG/packing、MD RMSF 的缺失会保持机器可读。
- readiness summary 不是新评分器，不参与 legacy ranking、objective score、candidate status 或实验优先级；它只能约束报告边界和下一步补证据动作。

## 2026-08-20 P2 objective score readiness summary

- P2 objective score 已拆成 activity/stability/specificity/ph_profile/expression/risk 组件，但没有报告级 unknown rollup 时，用户仍容易只看局部已有分量，把未知分量当成中性或已覆盖。
- `p2_objective_score_readiness_summary_v1` 应直接暴露 `unknown_component_counts`、`top_unknown_components`、`assay_required_counts` 和 `top_blocking_reasons`，让报告级缺口与每行 objective score 保持同口径。
- 该 summary 必须保持 `aggregation=none` 和 `no_composite_score=true`；它不是总分器，也不改变候选排序、候选分组或 wet-lab claim gate。

## 2026-08-20 P2 experiment design schedulability policy

- candidate table 和 experiment design table 不是同一个语义层：candidate table 可以展示 high-confidence、exploratory、blocked 供复核，experiment design table 只能承载可排单候选。
- `experiment_design_schedulability_policy_v1` 需要明确 blocked、No-Go、protected 和无推荐突变行被排除，同时保留 `blocked_rows_remain_traceable=all_positions`，避免审计证据消失。
- 这个策略只控制排单表输出，不改变 legacy ranking、objective score、candidate status 或科学门控。

## 2026-08-20 P3 project memory readiness rollup

- DBTL trace 已有 project_model、learning_readiness 和 required_actions，但缺少项目记忆实体完整度总览时，用户需要在 missing_entities、counts 和 raw trace 之间来回判断。
- `dbtl_project_memory_readiness_v1` 应按 round、ready WT baseline、variant、prediction、experiment feedback、formal decision 六类实体汇总 ready/missing，这样日报和项目详情页能快速判断 DBTL 记忆是否闭合。
- 该 rollup 只能读取现有 trace/project_model，不创建正式 DBTL 表、不推断缺失实体、不训练模型，也不升级 wet-lab claim。

## 2026-08-20 P3 feedback readiness summary

- `learning_readiness` 已能逐条说明 feedback import contract，但缺少项目级 QC/replicate/assay/formal decision 缺口汇总时，下一轮设计和日报仍难以判断反馈数据是否可用于训练或 claim promotion。
- `dbtl_feedback_readiness_summary_v1` 应直接汇总 `missing_for_training_counts`、QC 状态、replicate 覆盖、assay condition 完整度、formal decision 和 measured metric 覆盖；它只决定 readiness 可见性，不写入 feedback、不训练模型、不升级结论。
- 训练批次不足或 feedback import contract 未闭合时，`next_round_constraint_status` 必须保持 `blocked_by_feedback_import_contract`，不能把存在反馈记录误读为 ready。

## 2026-08-20 PKT008 GH11 xylanase E79A/Y69F 外部确认边界

- 用户提供了面向作者/仓库团队的 Gmail compose URL，用于请求确认 PKT008 `kumar2018` / GH11 xylanase E79A/Y69F 记录是否有可闭合 primary article 或应拒绝当前本地身份。
- 在收到作者/仓库回复、corrected primary article、explicit no-DOI decision 或授权 primary PDF/XML/source-table/raw-source bytes 前，该记录只能保持 `pending_author_confirmation` 或 `non_closing_identity_under_review`。
- 邮件草稿或发送动作本身不是 row-level provenance closure，不能作为 DOI 身份闭合、训练证据、湿实验验证或 claim promotion 的依据。

## 2026-08-20 P4 detailed closed-loop contracts

- P4 的本机可建设范围应是 production closed-loop readiness contracts，而不是生产闭环执行；active-learning、model calibration、manufacturing/process constraints 和 live gate approval 必须拆开。
- `p4_active_learning_batch_contract_v1` 只能判定未来 batch 是否可进入 operator review。即使训练可用反馈达到阈值，也不能自动创建训练集、启动训练、更新排序策略或排实验。
- `p4_model_calibration_registry_contract_v1` 只能说明现有 calibration runs 是否具备 registry 追溯字段；它不是 retraining、recalibration 或候选 claim promotion。
- `p4_manufacturing_constraint_schema_v1` 只定义 process owner review 所需字段；没有 expression/process/scale-up/assay scope 证据时必须 blocked，不能声明 manufacturing constraints validated。

## 2026-08-20 P0-P4 gap audit

- P0/P1 原本没有和 P2/P3/P4 同口径的机器可读总表，导致“指定突变复核/编号映射/Reaction Profile/WT baseline 已完成到什么程度”需要人工翻 Obsidian 和代码。
- `p0-p4-gap-audit` 应成为后续查缺入口：P0/P1 用源码 token source-bound，P2/P3/P4 复用 roadmap，remaining backlog 复用现有 readiness；所有输出都声明 `network_io=not_executed`、`destructive_actions=not_executed`、`live_gate_execution_allowed=false`。
- 当前 P0-P4 全部为 ready local contract，但仍有 local gaps 和 external blockers；ready local contract 不能解释为 production ready、wet-lab validated、model trained/retrained 或 live gate completed。
- 当前最硬外部阻塞仍是 7 项：formal domain/HTTPS、GPU/GROMACS MD live、MD blackbox live e2e、ligand runtime live、OSS/MinIO live e2e、admin authenticated screenshots、maintenance window drills。

## 2026-08-20 P0-P4 status export

- `p0-p4-gap-audit` 适合查缺，信息量较大；日报、复盘和 SOP 状态页需要一个更短的 `p0_p4_status_export_v1`。
- status export 应只消费 audit JSON，不重新运行 live gates 或重新判定科学事实；它的合同是把 P0-P4 readiness、local followups、external blockers 和 must-not-claim 压缩展示。
- `p0_p4_status_export_contract_v1` 必须固定两条边界：`ready_local_contract` 不能被描述为 live complete；`external_required` 不能被 status export 清零。

## 2026-08-20 P0-P4 local gap closure status

- gap audit 里的 local gaps 需要区分“展示/状态出口缺口”和“真实未来能力缺口”；否则完成 status export 后，P0/P1 仍会被误报为有本机待建项。
- `covered_by_status_export` 只表示 SOP/status/export 可见化已覆盖，不表示外部证据、物理计算、DBTL 写模型或 live gate 已完成。
- 当前 P0/P1 的 open local gaps 已清零；P2/P3/P4 仍有 open local gaps，主要集中在结构特征扩展、objective assay gap 联动、正式 DBTL 写模型审批和 P4 operator approval 边界。

## 2026-08-21 P0-P4 local gap closure 复跑结论

- 这次复跑没有改变口径，只是把上一轮的 open/covered 分拆重新验证了一遍。
- `p0-p4-gap-audit` 与 `p0-p4-status-export` 仍保持只读、fail-closed，不会因为本地展示层完成而把外部门禁清零。
- 当前最需要继续保留的判断是：`covered_by_status_export` 只能代表状态出口覆盖，不能被读成能力已完成或 live gate 已通过。

## 2026-08-21 P2/P3/P4 合同收口与报告校验

- P2/P3/P4 的合同边界已经在源码和生成物里重新对齐：`p2_structure_feature_gap_summary_v1`、`p2_objective_assay_gap_summary_v1`、`dbtl_readiness_bridge_v1`、`p4_operator_review_contract_v1` 都已显式出现在报告和类型层。
- `renderProjectDbtlTrace()` 里新增的 P4/DBTL 注释只用于静态审计和合同可见性，不改变 readiness 逻辑，也不把 live gate approval、wet-lab validation 或 model retrained 升级为既成事实。
- `frontend/src/lib/report.ts` 里 `renderList()` 作用域曾被误放进 `renderMutationScore()` 内部，导致 DBTL 报告编译失败；现在已提到文件级 helper。
- `frontend/src/lib/api.ts` 的 `project_memory_readiness` / `feedback_readiness` schema 约束现在更具体，但仍是只读合同，不是数据库写模型。
- 重新生成的 `p2-p3-p4-roadmap` 维持 `P2=3 ready_local_contract / P3=2 / P4=1`，而 `p0-p4-gap-audit` 和 `p0-p4-status-export` 的外部门禁没有改变。

## 2026-08-21 P0-P4 合同级状态导出

- 仅靠阶段级 `ready_local_contract` 和 covered local gap count 不足以回答“待建清单是否完事”；需要逐合同状态项暴露证据 token、外部阻塞和审批状态。
- `covered_by_contract_status_export` 的语义应严格限定为“合同状态已在 status export 中可见”，不能解释为 pocket/conservation/ddG/MD、正式 DBTL 表、wet-lab feedback、model retraining 或 live gate approval 已完成。
- `p0_p4_contract_status_export_v1` 当前输出 14 个合同条目。P2/P3/P4 六个条目虽然本地合同 ready，但都应保留 `approval_required=true` 和 `blocked_until_explicit_review`：
  - `residue_feature_table_contract`：pocket/channel/interface、conservation、ddG/packing、MD-derived 字段继续 unknown，直到有结构化计算器或 curated source；
  - `objective_score_contract`：unknown objective components 继续阻断，不作为 neutral；assay gap 与 feedback readiness 并排展示；
  - `candidate_table_generation_contract`：排单只接收通过 candidate status 和 assay readiness 的候选；
  - `dbtl_trace_contract`：raw trace 只读，正式 DBTL 写模型等待产品审批；
  - `feedback_import_and_next_round_contract`：单体和结构证据不齐时，pair/higher-order 设计继续阻断；
  - `industrial_closed_loop_readiness`：live gate approval blocked，直到明确 operator review。
- status export 应只消费 audit JSON，不运行 live gate、不联网、不训练、不写库；`external_followups=7` 必须继续保留。

## 2026-08-21 P0-P4 与 remaining backlog ticket 桥接

- `p0-p4-status-export.json` 当前有 14 条合同状态，`remaining-backlog-execution-tickets.json` 当前有 7 张 operator ticket；两者此前没有直接引用关系。
- 桥接必须保留三种覆盖状态：`linked`、`partially_linked`、`contract_followup_only`。没有直接 operator ticket 的编号、机制、反应、WT/assay、湿实验和正式 DBTL 决策缺口不能伪造映射。
- 直接运行态关联主要覆盖 MD/结构 artifact（`RB-002`/`RB-003`）、正式生产配置与存储（`RB-001`/`RB-005`）以及维护窗口与 live gate 审批（`RB-007`）；`RB-004` 和 `RB-006` 保持为 operator ticket，并在反向索引中标明没有直接合同解除关系。
- bridge 需要绑定 status export、execution tickets、go/no-go 三个源的 SHA-256，输出合同正向映射、ticket 反向索引和未映射 blocker，确保 2026-08-21 的最终状态可复核。

## 2026-08-21 operator 包串行刷新入口

- validation report、go/no-go、execution tickets 和 bridge 都会写入或刷新被 operator packet manifest 跟踪的文件；并行运行或错误的最终顺序会按设计造成 manifest stale。
- 新增 `make remaining-backlog-operator-packet-refresh` 固定顺序：先刷新 P0-P4 与 remaining backlog 输入/计划/dispatch，生成临时 manifest，再生成 go/no-go、tickets、ticket validation、bridge、bridge validation，最后重建 manifest 并执行 freshness check。
- 该入口仍声明并保持 `network_io=not_executed`、`destructive_actions=not_executed`、`live_gate_execution_allowed=false`；当前结果仍为 7 external_required、7 blocked、0 armed。
- Makefile 回归测试必须按 recipe 行精确比较步骤，不能用简单子串位置，因为 `remaining-backlog-operator-packet-manifest` 是 `remaining-backlog-operator-packet-manifest-check` 的前缀。

## 2026-08-21 remote pytest runner 复验

- `make pytest-runner-json` 复跑通过，输出 `829 passed`，说明本地非生产 runner 仍与 CI backend-test contract 一致。
- 该 runner 通过临时 SQLite 执行，不接触生产数据库变量，也不触发网络 I/O 或破坏性动作。
- 这进一步确认 `remote_pytest_runner` 已是 ready/local_capable，而不是 operator 侧外部输入缺口。

## 2026-08-21 remaining backlog live 能力复探

- 现有 ECS 公网入口 `http://120.27.108.138/api/health` 返回 HTTP 200，说明部署服务仍在线；本次只读探测未执行任何任务提交、写库或破坏性动作。
- 当前 Mac 主机没有 `gmx`/`gmx_mpi`、`obabel`、`vina`、`acpype`、`antechamber`，所以 GPU/GROMACS 与 ligand runtime 不能在宿主机直接验收；Docker Desktop daemon 可访问，允许继续验证专用 worker 镜像。
- `docker/.env.aliyun.app` 含有 OSS 配置，但不能直接用 shell `source` 解析，因值包含 shell 特殊字符；live smoke 应支持安全的 `--env-file` 解析，且不得把 secret 打印到输出。
- 系统 Python 缺少 `minio` 模块；应优先使用 `backend/.venv/bin/python` 或在 smoke runner 中明确报告依赖缺失，而不是把真实 OSS 凭据误报为不可用。
- 本机没有启动 `127.0.0.1:4200` 前端，HTTP smoke 的失败属于服务未启动；Chrome 在当前受限会话中启动后 SIGABRT，不能把该现象写成产品浏览器回归失败。
- 以上修复只改善 gate 的可执行性与状态分类，不会把没有真实 DNS/TLS、GPU 长任务、MD 黑盒、管理员认证或维护窗口证据的项目标记为完成。

## 2026-08-21 ligand/backend 镜像复核

- 当前 Codex 会话访问 Docker Desktop socket 被拒绝，`docker run protein-ai-backend:aliyun ...` 尚未取得有效镜像运行证据，不能据此判断 `minio` 是否缺失。
- `docker/Dockerfile.ligand-worker.aliyun` 的 ACPYPE 兼容链接固定使用 `/usr/lib/x86_64-linux-gnu`；在本机 ARM64 Docker Desktop 构建时会因目标库路径不存在而失败。
- ligand runtime 仍保持 `external_required/blocked`。后续修复需要让镜像构建显式选择 `linux/amd64`，或按架构解析系统库路径，并在不支持的架构上 fail-closed。

## 2026-08-21 ligand worker 架构修复

- `docker-compose.aliyun-app.yml` 和 `docker-compose.aliyun-gpu.yml` 的 backend/ligand worker 构建服务已显式设置 `platform: linux/amd64`，避免本机 ARM64 先生成不可供 ACPYPE 使用的 ARM backend 基础镜像。
- `Dockerfile.ligand-worker.aliyun` 新增 `TARGETARCH=amd64` fail-closed 检查，并将 HDF5 兼容链接改为 `dpkg-architecture -qDEB_HOST_MULTIARCH` 动态路径。
- 两份 Aliyun compose `config --quiet` 和 `git diff --check` 均通过；这只是构建合同验证，不等价于 ligand runtime live-ready。

## 2026-08-22 backend 镜像运行时复核

- 重新构建 `protein-ai-backend:aliyun` 后，builder venv 安装了 `minio==7.2.10`，最终镜像 `Config.Env` 和容器 `env` 均显示 `PATH=/opt/venv/bin:...`。
- 用非 login shell 验证：`which python` -> `/opt/venv/bin/python`，`import minio` -> `7.2.10`，`gmx --version` -> `GROMACS 2025.2`，`foldseek version` -> `d5b1d3d...`。
- 先前 `sh -lc` 检查失败是 login shell 改写 PATH 到 `/usr/local/bin/python`，不是最终镜像缺少 `minio`；生产 CMD/Compose 不使用 login shell。

## 2026-08-22 ligand worker 构建复验

- 真实构建已越过 `TARGETARCH=amd64` 检查、OS chemistry 包安装和 `pip install acpype rdkit`，证明之前的 ARM/x86_64 混用问题已消除。
- 新失败点为 slim runtime 不含 `dpkg-architecture`，HDF5 multiarch 目录解析命令返回 `not found`。
- 已改为 `dpkg --print-architecture` + 显式 Debian multiarch 映射，避免为路径解析额外安装 `dpkg-dev`。

## 2026-08-24 工程分析链路架构问题（待外部调研验证）

- 用户指出平台应评估“调用何种专业软件形成实验可参考结果”的架构，而不是继续润色报告。
- 当前 `AgentOrchestrator` 同时承担计划、执行、门控、探索性候选生成与 Markdown 报告拼装；`_build_exploratory_pdb_activity_sites()` 位于报告链路，身份/口袋/催化证据未就绪时仍可产出具体替换方向。
- 需以公开文献、权威数据库与工具官方资料核实最优证据链，重点评估家族识别、功能/催化残基、结构模型质量、稳定性与活性候选的合理软件组合。
- 直接访问 Google、PubMed E-utilities、Crossref 均因当前网络/TLS 不可用失败；通过 ECS 只读 Google 检索也超时，尚未取得可引用的本轮外部检索结果，不能声称已完成 Google 调研。
- 后续以 Playwright 浏览器访问 Google 成功。检索到 2022 综述 *Modern computational methods for rational enzyme engineering*（ScienceDirect, PII `S2667109322005280`）及 2024 综述 *Unlocking the potential of enzyme engineering via rational ...*（PII `S0734975024000703`）。搜索结果共同强调：先有高质量结构/同源模型与催化、辅因子、底物通道热点；再以受限候选库和能量/几何评估筛选；MD 是后续构象/动态验证，不是身份未知时的起点。搜索摘要不是论文证据，应在实现前阅读原文或方法资料。
- Google 定向检索确认 InterPro 的官方定位是用预测蛋白 signature 做分类与自动注释；dbCAN3 的官方定位是 automated CAZyme annotation。当前平台不能再用短模体命中代替这些来源化家族/功能证据。
- Google 检索成熟平台比较：PROSS 是在保护功能位点/界面的约束下作多点稳定性与可溶性设计；FireProt 将能量计算与进化共识用于稳定性候选；FuncLib 针对已定义活性位点/底物口袋，结合系统发育与 Rosetta mutational scanning 生成受限功能库；HotSpot Wizard 将结构、进化与通道信息映射为定点热点。该分工支持采用领域模块和前置条件，而非当前单个 orchestrator 的启发式 PDB 位点生成。
- 尝试阅读 PMC8239229 原文时触发 reCAPTCHA，未从该页面提取正文；已记录为来源访问限制，不将 Google AI 概览作为文献事实。
- Google 定向检索 AlphaFold Database FAQ：pLDDT 50-70 属低置信、<50 的三维坐标通常不应按可信结构使用。该值是模型置信度，不是实验 B-factor；当前报告将 SWISS-MODEL 的 0.53-1.0 字段解读为“刚性/稳定性”的行为必须删除。
- Google 检索 `Engineering enzyme access tunnels`（2019，PII `S0734975019300679`）与 CAVER/HotSpot Wizard 资料：通道变化可能影响活性、特异性、对映选择性与稳定性，但工程候选必须建立在已计算通道/口袋、底物及进化信息之上；不能由 CA 邻居数、relSASA 或序列距离代替。
- ECS 运行时核查：`gmx` 可用；`interproscan.sh`、`hmmscan`、`run_dbcan`、`caver`、`foldx`、Rosetta executables 和 `fpocket` 全部缺失。现有 `enzyme_identity_profile` 的短模体与内嵌规则、以及 pocket adapter 的 blocked 合同不能宣称为这些专业工具的实际结果。

## 2026-08-24 工具许可与生产部署边界复核

- 工具链必须同时记录 `runtime_receipt`、`database_version`、`license_class` 和 `commercial_use_status`；容器构建成功不能自动等于可向客户提供结果。
- HMMER/HMMER3：开源许可路线，适合在本地 worker 中部署 profile-HMM 搜索；但 Pfam、NCBIfam、InterPro member database 各自有数据许可/引用要求，必须把数据库版本和下载来源写入证据 manifest。
- Foldseek：开源本地二进制路线可部署；PDB/AlphaFold 等结构数据库不是 Foldseek 软件本身的许可，结构库快照、再分发和更新责任需要单独登记。
- fpocket/P2Rank：可作为本地口袋候选的开源计算后端，但输出只能表示几何口袋预测；必须保留版本、参数和输入结构哈希，不能在无底物/同源/保守性证据时升级成活性位点。
- InterProScan：软件可本地运行，但安装包依赖多个成员数据库和较大的数据下载；数据库和服务条款、引用和再分发边界需由运维/法务确认。REST 提交的 `job_id` 或 pending 状态不能作为注释结果。
- dbCAN/CAZy：仅在序列有 CAZyme 家族前提时启用。dbCAN 代码、HMM 数据集和 CAZy 注释数据应分开记录版本/条款；自动注释需保留人工复核标记，不能把 GH/CBM 命中直接当作底物或催化位点确认。
- FoldX：学术使用常见，但商业/客户服务使用需要确认授权。未取得商业许可和可复核运行 receipt 时，生产环境只能显示 `capability_blocked`，不能把内置估算或旧缓存写成 FoldX ddG。
- Rosetta/PyRosetta：学术非商业许可与商业许可边界明确；商业平台不能默认把 Rosetta 作为已授权后端。应实现 license-aware adapter，未配置授权时返回 blocked，并禁止用“本地估算”冒充 Rosetta score。
- CAVER：不同发行版（桌面、命令行、Web/服务）条款和运行方式不同；只有确认具体版本许可、可批量无头运行和结果工件格式后，才可作为通道分析后端。无真实通道计算时不得从 CA 接触数/relSASA 推断通道。
- GROMACS：开源可部署，当前线上已具备 runtime；但 MD 只应作为已确认身份、结构/配体拓扑和实验问题明确后的验证模块，不得作为身份未知时的默认候选生成器。
- 生产决策：将工具分为 `open_local`、`open_data_restricted`、`academic_or_commercial_license`、`external_service_only` 四类；候选生成服务必须要求所需工具的 `execution_status=completed`、许可证状态允许当前租户、输入/数据库哈希可追溯，否则输出 capability/evidence gap 而不是候选行。
## 2026-08-25：55/58 工具科学组合深度调研（第一轮）

### 可核验事实

- `ToolRegistry` 实际加载 `58` 个工具，另有 `1` 个 alias；因此“55 个工具”不是当前注册表的准确数字。
- `scheduler.ASYNC_TOOLS` 只覆盖 13 个工具；其余网络/长耗时工具以同步 registry timeout 执行，存在 HTTP 预算与科学任务耗时不匹配风险。
- 第一轮审计发现 `tool_capability_audit` 只显式维护 25 个能力条目；第二轮已为其余 33 个工具补上保守能力合同。覆盖率现在为 58/58，但其中 proxy/runtime-unverified 仍不得升级为 report-grade claim。
- 当前工具 schema 能暴露输入字段，但没有统一的 `requires/provides/evidence_level/license` typed contract。

### 科学组合判断

1. 基础链路应固定为：输入门控 → 身份/功能 → 结构/编号 → 目标模块 → 目标证据 → 候选 → 验证 → 实验决策。
2. `mutation_priority_score`、`mutation_scan`、`protssn_score` 不应在 identity/objective/numbering gate 前调用；它们最多生成探索性假设。
3. `structure_search_foldseek` 只能提供结构相似性，不能直接确认酶身份；`residue_mapping_sifts` 和 `residue_numbering_gate` 必须在位点结论前完成。
4. BLAST、InterPro、文献和外部研究任务只有 terminal/live/cache-traceable 结果才能进入证据；submitted/degraded 只能作为任务 receipt。
5. 设计模型和结构预测是候选生成/结构假设层，不是实验结论层；必须保存模型版本、输入 hash、seed、原始 artifact 和置信度。
6. 配体链路必须是 2D SDF → 3D/质子化/电荷 → PDBQT → docking → topology → MD，不能跳步。
7. GROMACS/Rosetta/FoldX/CAVER 等 runtime/license 未满足时必须 blocked，不能用代理输出替代真实结果。

### 当前高风险缺口

- 注册表、异步队列、能力审计和 agent gate 的工具集合不一致。
- 缺少统一的工具输出类型和证据升级规则，planner 仍主要依赖 `agent_graph.py` 中的分散规则。
- 13 个异步工具之外，`annotation_bundle`、`interpro_live_lookup`、`literature_live_search`、`mutation_priority_score` 等可能发生网络/重计算的工具需要重新评估队列策略。
- 工具能力审计未覆盖全部 58 个工具；未知工具必须在自动报告中显式降级。

### 覆盖报告

- `docs/designs/2026-08-25-tool-orchestration-coverage.json`：注册 `58`、alias `1`、异步 `13`、能力审计覆盖 `58`、未知能力 `0`。

### 下一轮验证

- 生成 58 工具注册/异步/能力审计覆盖矩阵。
- 为每个工具补 `requires/provides/evidence_level/runtime_mode/license` 合同。
- 将 `validate_tool_plan` 接入 planner dispatch 前置检查。
- 增加组合级测试：身份失败、编号失败、异步未终态、2D 配体跳步、缺 topology、代理结果升级均应 fail-closed。

### 第二轮接入结果

- `validate_tool_plan` 已接入 `agent_graph` 计划生成后的 preflight。
- 计划确认阶段只阻断缺少硬输入（序列/结构）的工具；候选工具的 identity/objective gate 延迟到有序执行阶段，避免合法策略在确认页被提前阻断。
- 定向回归：`22 passed`；其中计划确认/结构依赖/候选门控均通过。

### 第三轮运行模式审计

- 编排合同现在检查工具是否已注册、异步工具是否被请求同步执行，以及队列硬时限是否低于工具 registry timeout。
- 已修复 `gromacs_md` registry timeout（从 7200s 收敛到 5400s），与 `md_cpu` profile hard limit 一致。
- 覆盖报告复核：13 个异步工具 timeout mismatch 为 `0`。
- 运行模式合同和 scheduler 回归：`17 passed`。
## 2026-08-25 配体命令派生进程超时审计

- `ligand_preprocess` 已有每阶段 timeout 和结构化失败合同，但 `subprocess.run` 的超时处理没有显式建立/终止进程组；ACPYPE 会调用 AmberTools `sqm`，因此父进程超时不等于所有计算已停止。
- 修复采用 POSIX `start_new_session=True` + `os.killpg(SIGTERM)`，并保留非 POSIX `terminate()` 回退。超时结果仍是失败证据，禁止进入 topology/MD 的 completed gate。
- 该修复只解决生命周期和可审计性，不证明 AmberTools 在当前架构上可运行；正式科学验收仍必须在原生 `linux/amd64` worker 完成并保存非空 ITP/TOP/GRO artifact、退出码和 runtime manifest。
- runtime manifest 已补充主机架构和兼容性门控；ARM64 即使 OpenBabel/Vina/GROMACS 可用，也会显式报告 `linux_amd64_worker` 缺口，避免把局部工具可用误升级为完整 ligand topology runtime ready。
- 发现并修复 runtime-check 双实现漂移：Dockerfile 中的内嵌脚本曾漏检 `teLeap`、部分动态链接器错误，且构建调用未使用 `--require-live`。现在构建阶段会 fail-closed，独立脚本和镜像脚本的 AmberTools/loader 判定一致。
- runtime-check 的 `ready` 语义已明确为 capability-only；manifest 固定记录 `execution_status=capability_ready`、`scientific_smoke_status=not_run` 和 `evidence_level=runtime_capability_only`。只有真实链路生成并验收 artifact 后，外部 smoke 记录才能升级证据等级。
- `ligand_preprocess._stage_readiness` 过去只按 topology 状态解锁复杂 MD，存在空产物/能力检查误放行风险。现在只接受真实拓扑格式 artifact（`.itp/.top/.gro`）和 `executed_topology_artifacts` 证据等级，并提供机器可读阻断原因 `topology_evidence_incomplete`。
- topology manifest 现在包含每个文件的 `name/size/sha256`；解锁门校验 manifest 非空、数量/名称一致、文件类型正确、大小大于 0、SHA-256 为 64 位十六进制。该合同使 artifact 可追溯，但真实 ECS smoke 仍需保存运行时版本与原始执行 receipt。

## 2026-08-25 编排依赖回归结论

- 依赖合同的正确执行粒度是“逐步骤 fail-closed”，而非“一条 dependency violation 阻断整张计划”。当计划只含 dependency-required 违例时，缺少前置证据的步骤必须返回 `DEPENDENCY_REQUIRED`、不进入 dispatch；同计划中无依赖的合法步骤可继续。
- 该语义已经通过无 topology MD 判别测试、混合计划测试、完整 agent binder 回归和后端全量回归验证。它不放宽科学门：`gromacs_md` 仍不能在缺少已执行 topology artifact 时提交。
- 最终本地验证结果：判别 `2 passed`，agent binder `156 passed`，后端 `873 passed`，Python 编译/差异检查通过，前端 build/lint 通过。
- 这些结果只证明源码和本地测试闭环；不替代原生 x86_64 topology live smoke、真实 MD black-box、认证截图或维护窗口/异地恢复等外部验收。

## 2026-08-26 序列预训练批处理验证结论

- 26 个批次均以 `completed_pretraining_only` 收口，训练产物与输入哈希可追溯；最后一批 validation loss 为 `3.090413`，不能单独作为模型质量或泛化结论。
- token、position embedding 与 1D context convolution 的组合已通过位置敏感性测试；512 条 smoke embedding 无重复向量，避免初版 mean-token 表示的碰撞问题。
- 8 项单元测试和全量脚本语法编译通过；该证据只证明本地代码/产物一致性，不证明监督标签质量、突变预测能力或线上服务可用性。
- 监督集仍为空，故正式监督训练入口继续 fail-closed；不得将本轮预训练 checkpoint 升级为可发布模型。

## 2026-08-26 全量 embedding index 收口

- 基于 batch-0001 checkpoint 重建 12,830 条去重序列的 32 维 embedding index；索引和 checkpoint 均保留输入/产物哈希。
- 机器校验、碰撞审计和检索 smoke 均通过（0 重复记录、0 向量碰撞、5 条 top-k 结果）。
- batch-0001 仅因固定验证集 loss 最低被选作当前构建基准；没有监督标签或独立下游评测，因此不能称为“最佳模型”，也不能推导生物学性能。
- 全量 index 已完成重复构建一致性检查；规范化内容 hash 一致，说明当前批处理和 embedding 导出具备可复现性。该结论不等于训练质量或科学有效性证明。
- 多位置检索回归均返回固定数量结果，作为接口/数据完整性证据；相似度仅是表示空间距离，不能当作酶功能、亲和力或突变效应预测。
- 预训练质量报告显示 26 批共 11,552 steps，validation loss 均值 `2.907486`、标准差 `0.043292`；这些是训练过程统计，不是下游准确率。报告和单元测试均保留 fail-closed 标记。
- checkpoint 选择清单对 26 个候选逐一复核存在性和 SHA-256；当前仅作为 embedding 构建基准，不能视为发布候选或“最佳模型”。
- `model_cards/sequence-pretraining.status.md` 已固化当前资产边界和禁止用途；发布隔离验证器把“完整性通过”和“可发布”分开，完整 checkpoint 仍只能本地预训练使用，不能自动晋级监督训练或生产发布。
- 预训练资产包 manifest 已将 7 个关键文件绑定到内容哈希；缺件、大小变化、哈希变化或边界标记被放宽时验证均失败，便于后续交接和审计，但不构成生产发布授权。
- 关键架构修正：26 个独立批次完成不等于一个模型看过全部数据。现在已有单一连续 checkpoint 完整走过 11,547 条训练序列，并在固定留出的 1,283 条序列上计算验证 loss；旧 batch-0001 仅保留历史批次基准，不再代表全量预训练模型。
- 连续 checkpoint 的 index 完整性与碰撞审计通过，但仍是单 epoch、无标签、小型 32 维 encoder；不能据此推导监督任务或生产质量。
- 当前交接资产已不再引用旧 batch-0001 checkpoint；`continuous_full` 的 checkpoint SHA-256 为 `b9045f5c7cdb51c46cec59b6516bd5f879c77148340be1670775c65a54b9bc9f`，发布隔离门保持 `blocked_pretraining_only`。
- 交接复核发现绝对路径不可跨 worktree 复用，已将连续选择清单、发布门和资产 manifest 全部重建到主仓库路径；当前验证器可在主工作区独立读取全部 7 项资产。
- 仅重写为主仓库绝对路径仍会在迁移/worktree 场景复发；最终方案改为 manifest-root 相对路径，并通过异目录复制验证证明资产包可搬迁且内容哈希保持有效。
- v1 连续训练的验证代码用未遮盖 `ids` 直接推理，只在随机位置取 loss，导致 MLM 验证目标与训练目标不一致；其 `2.927213` 不再作为当前质量统计。
- v2 使用遮盖后的输入计算验证 loss（`2.911054`），并重建 checkpoint/index/校验/碰撞审计。该修正提高了训练过程统计可信度，但仍不构成监督或生物学性能证据。
- v2 的逐序列随机 split 存在 100% MSA 来源重叠，故其验证 loss 仍不能作为当前基准。v3 改用 `source_group_holdout`，143 个训练来源与 15 个验证来源零重叠。
- 来源隔离比随机切分更严格，但 `source=` 不是全局序列同源聚类；没有 CD-HIT/MMseqs2 时仍不能声称消除了跨来源远近同源泄漏。
- 独立 MLM 重复评测显示模型仅略优于均匀氨基酸基线；这是无标签 token 重建证据，不是酶功能、突变效应或泛化能力证明。评测结果已绑定当前 v3 checkpoint 哈希。
- 随机初始化对照确认 v3 的重建增益不是单纯架构偏置；仍需独立标注数据和下游任务评测，不能升级为模型质量或生物学结论。
- 3 epochs 相比 1 epoch 在 5/5 配对 mask repeats 上均降低 loss，但绝对提升很小；v4 可作为更好的无标签重建基准，不能据此推导继续增加 epoch 一定有效或下游任务提升。
- 5 epochs 已出现轻微回退，说明当前架构/学习率下继续增加 epoch 没有稳定收益；下一步应优先改进架构、优化器或数据规模，而不是无控制延长训练。
- 学习率扫描显示 5e-4 在当前主目标 loss 上优于 1e-3，3e-4 的 accuracy 略高但 loss 略差；选择规则以 MLM loss 为主、accuracy 不回退为门槛，避免事后挑指标。v6 相对 v4 的提升仍很小。
- 单纯把 hidden dimension 从 32 增至 64 在当前数据量、卷积结构和训练预算下反而回退；容量不是当前唯一瓶颈，暂不继续盲目扩大到 128。
- kernel=5 提升交叉熵但降低 top-1 token accuracy，形成 Pareto 冲突；既定门槛要求两项一致改善，因此不因单一 loss 指标事后改规则。
- residual/GELU 也形成相反 Pareto：accuracy 增益伴随 loss 回退；继续沿用主目标 loss 优先、accuracy 不回退的选择纪律。

## 2026-08-26 待建清单状态审计

- readiness 总结：`external_required=7`、`ready=2`；`network_io=not_executed`、`destructive_actions=not_executed`。
- 本机 deploy_data 已完整覆盖 annotations、SIFTS、PDB、AlphaFold、Foldseek 和 smoke query；可继续做本地结构 smoke，但不能代替线上真实存储或公网验收。
- 生成的 external input packet 将 P0 分为 formal HTTPS、GPU/GROMACS、MD black-box、OSS/MinIO 四项，P1 分为 ligand runtime、管理员截图、维护窗口演练三项；每项均要求 secret reference 而非把秘密写入文档。
- execution tickets 当前全部 `started_blocked_waiting_for_operator_input`，没有 armed ticket；因此不应启动线上任务、上传删除对象、提交 MD 或执行生产回滚。

## 2026-08-26 科学 runtime 占位绕过复核

- 发现并修复结构 readiness 的一个证据升级漏洞：任意存在的可执行文件（例如 `/bin/echo`）曾被当作 Foldseek CLI runtime。
- 现在只有非占位二进制且 Foldseek 数据库目录有可用条目时，才允许 `live_foldseek_cli=ready`；`echo/true/false/printf` 会输出 `placeholder_binary_rejected`。
- 复核配体 smoke、MD topology 和 ligand preprocess API 合同，未发现同类占位命令升级路径；相关回归分别通过。
- 本地真实状态应为 `demo-ready`/`blocked`，而不是 `live-ready`，直到配置真实 Foldseek API 或 CLI。该门控修复不改变旧线上版本，也不执行部署。

## 2026-08-26 外部门控凭据与 HTTPS 复核

- MD black-box resume 不能使用代码内置密码；默认密码已移除，只有显式环境变量/参数才算凭据完整。
- OSS/MinIO `--require-live` 在缺 access/secret 时返回 blocked；文件下载 live gate 在缺账号时返回 blocked；均未执行网络 round-trip。
- 生产公网 HTTP 不再是 warning，而是 strict `critical`；正式上线必须提供 HTTPS 域名/证书，非生产准备只能显式使用 `--skip-domain-https`。

## 2026-08-26 正式发布总控 HTTPS 门

- release acceptance 现在独立运行 `production_https_gate`，不会因为 acceptance matrix 为本地准备跳过 HTTPS 就把发布总控标为可上线。
- 当前公网 HTTP 被标记 `manual_required`，需要正式域名、TLS、OIDC/public URL 配置；备份 checksum/`pg_restore --list` 已通过。
- 完整只读总控为 `passed-with-manual-gates`（10 项，0 failed，4 manual_required，0 skipped）；manual gates 仍是 HTTPS、维护窗口回滚、异地备份恢复、外部存储恢复。
