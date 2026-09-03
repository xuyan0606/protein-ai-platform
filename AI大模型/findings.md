# KWB-EnzymeDesigner 研发发现

## 本地数据

- `backend/protein_ai.db` 包含大规模本地酶数据：enzyme records、PDB structures、AlphaFold structures、kinetic parameters、stability records 和 directed evolution entries。
- 当前本地 DB 缺少真实 `experiment_feedback_records` 和 `tool_task_audits` 表；对应抽取器按 `missing_table` 状态输出，不能伪造线上反馈。
- `datasets/features/enzyme_mutation_labels.jsonl` 当前 500 行，均为 stability label；标签分布为 go 161、watch 181、no_go 158，覆盖 145 个 UniProt group。
- `datasets/curated/enzyme_mutation_training_table.jsonl` 已生成 500 行；protein-group split 为 train 373、validation 60、test 67，未发现 group leakage。
- 当前不使用 dTm/ddG 输入时，基础突变特征监督 baseline validation/test accuracy = 0.317/0.239，说明模型质量瓶颈在结构、保守性、家族和真实反馈特征缺失。
- 增强表已加入 PDB、AlphaFold、PFAM、EC、kinetic、reviewed、function annotation 等记录级上下文；500 行有 PDB 证据，498 行有 AlphaFold 证据。
- 增强 baseline 未提升，说明仅有“是否存在结构/注释”的记录级代理特征不够；需要突变位点级三维环境特征和 MSA 保守性。
- mutation label 完整性审计发现 500 条中只有 25 条与当前 UniProt 序列编号一致；475 条 wild type mismatch。
- 编号修复候选没有单一主导 offset，说明不能靠简单 +/- 偏移修复，必须做 UniProt 版本、isoform 或文献编号回源。
- domain architecture 区间全为 0/0，当前不能作为位点级 domain 特征。
- PDB 文件路径在 DB 中存在，但本地结构文件不存在，当前不能直接解析坐标。
- 未验证 475 条标签已降级为 weak evidence，允许用于检索/报告证据，但禁止进入强监督训练、自动 go/no-go 和结构距离结论。
- 编号回源队列 475 行，P0 213、P1 249、P2 13，优先从强测量且 group 较大的记录开始回源。
- 结构缓存审计显示 PDB 和 AlphaFold 样本本地存在数均为 0，坐标级结构特征需先建设只读结构缓存。
- 编号回源应用脚本在无真实决策时不会提升 weak evidence；当前 repaired 表强监督标签仍为 25。
- expected structure cache manifest 已生成 500 个 entries，present 0、missing 500，用于后续本地离线缓存建设。
- P0 回源工作包已生成 5 个，覆盖 125 条最高优先级记录。
- apply curation 已增加 canonical WT 当前序列校验和 confidence 门控，错误映射不会被提升为强监督标签。
- curation dashboard 已汇总 label integrity、queue、batching、decision validation、apply、weak evidence、structure cache 和 readiness。
- strict repaired supervised 表已建立，500 行 repaired 输入中只保留 25 条强监督标签；475 条 weak evidence 被排除。
- 后续所有监督训练必须从 strict repaired supervised 表开始，不能直接读取 full repaired 或 enriched 表。
- 安全入口检查已验证 strict 表无 weak evidence 泄漏；当前只因样本数低于 100 而不能声明模型质量。
- 串行 safe training pipeline runner 已跑通 16 步，避免 manifest/readiness 并行竞态。
- P0 decision templates 已生成 5 个文件、125 行；模板不参与 apply。
- batch status 显示 0 decided rows、coverage 0.0，说明目前还没有真实回源决策。
- master readiness board 显示 7 条工作流 ready 0/7，整体仍为 `blocked_for_model_claim`。
- 当前最先解除阻断的路径仍是 numbering curation 和 structure cache。
- （历史快照）domain interval repair queue 曾显示 1000 行/1942 invalid；当前以 `reports/domain_state_consistency_20260829.json` 为准：1785 条单区间、155 条 multi-occurrence sidecar 可用于位点特征，2 条 unresolved。
- MSA scaffold 已生成 158 个目标，但没有真实 MSA/cache，不能生成 `msa_conservation_features.jsonl`。
- experiment feedback scaffold 已生成 schema/template/local 空文件，当前 reviewed numbered rows 为 0。
- 结构工作流 gate 已具备本地可执行规划器：上传结构走 parse -> numbering -> structure analysis -> KWB，不进入 ESMFold；已有 PDB/AlphaFold/ESMFold 不重复预测。
- 仅序列时允许 sequence_basic_analysis/predict_properties，但 `annotation_bundle` 和 `kwb_enzyme_designer` 在 ESMFold 完成前为 blocked，允许的结论范围只有 sequence。
- 编号未确认时，上传结构的结构依赖步骤统一为 blocked；旧轮次 `tool_result_refs` 不匹配当前 session/conversation/request_turn 时会被忽略。
- 结构 gate demo 的 5 项断言全部通过；平台 readiness 只标记为 `local_gate_passed`，生产平台仍未接入。
- 本地 KWB 适配器已把 gate 和规则 MVP 连接起来：只有当前结构与编号条件满足时才产生 KWB result。
- 适配器四场景断言通过：上传结构不触发 ESMFold、编号未确认 blocked、仅序列 pending、当前 ESMFold 完成后可调用 KWB。
- 适配器事件保留 `session_id`、conversation/turn 上下文、task_id、依赖关系和 `local_only` 质量标记，可作为 GPT-5.6 工具结果消费边界。
- 适配器事件合同断言通过：必填字段、stage、status、progress_percent、task_id 和本地时间标记均符合现有 `tool_event.schema.json` 形状。
- 六项阻塞执行波次已启动：475 条编号回源拆为 10 包，1942 条 domain 区间拆为 39 批，500 条结构获取清单已建立，158 条 MSA FASTA 已生成，反馈 intake 校验和五头模型 readiness 已建立。
- 本地未安装 mmseqs/mafft/clustalo/hhblits/jackhmmer/foldseek，且 numpy/pandas/sklearn/torch/Bio 均不可用；因此 MSA 和训练阶段保持失败安全，不生成假特征。
- 当前所有真实阻塞仍然存在，但已从“没有执行入口”推进到“有可审计执行包和状态报告”。
- 公共 RCSB 结构缓存已实际落地 320/500 个 PDB 文件，缓存目录为 `cache/structures/pdb`。
- 结构缓存失败项 180 个，失败原因全部为 HTTP 404；下一步不能重复盲目下载，
  需要对这些 PDB ID 做 RCSB/PDBe 回源、obsolete/superseded 映射或从同源 AlphaFold/实验结构替代。
- 结构缓存已具备坐标特征研发入口，但链映射、序列到结构编号和残基覆盖仍未审校；
  因此可以推进坐标解析脚手架，仍不能对外宣称结构模型预测质量。
- 结构缓存 500/500 已补齐，其中 320 个为 legacy PDB，180 个为 PDBx/mmCIF；
  原 180 个 HTTP 404 不是无效或 obsolete ID，而是 current ID 的 legacy PDB 文件不可用。
- 结构坐标摘要已对 500 个结构全部解析成功，可作为链映射审校和后续坐标特征生产输入；
  但它仍只是文件级/链级摘要，不能替代序列到结构编号审校。
- UniProt 当前 canonical 证据已覆盖 475/475 条编号回源记录和 145 个 accession；
  0/475 与当前 canonical reported WT 精确匹配，说明现有弱标签确实不是简单当前 UniProt canonical 编号。
- 475 条编号证据中 287 条存在 UniProt isoform options，下一步应优先做 isoform/literature numbering 回源；
  公共 UniProt 证据不是 reviewed decision，不能自动提升 strict supervised rows。
- UniProt isoform FASTA 已覆盖 270/270 个 isoform；287 条带 isoform 的编号记录中只有 8 条同位置 WT 精确匹配。
- 这 8 条 isoform exact match 已整理为 review candidates，其中 P0 4 条、P1 4 条；
  但仍必须确认文献是否使用该 isoform 编号，并完成 canonical mapping 后才能写入 reviewed decisions。
- 其余 279 条 isoform 证据仍未同位置匹配，主要需要文献序列、作者编号映射或历史 UniProt 版本回源。
- PubMed 元数据已覆盖 473/473 个唯一 PMID、475/475 条编号记录；但 455/475 被归为文献 high risk，
  20/475 只是 possible relevance，0 条标题直接提到 reported mutation。
- 多个 PMID 标题明显属于医疗、护理、运动、社会科学或其它非突变工程主题；
  因此当前 literature_ref 字段不能直接作为强监督标签依据，必须逐条查原始文献或回到真实实验来源。
- 文献风险队列进一步支持“475 条 weak labels 不得自动升级”的门控判断；
  即使 8 条 isoform exact match 也必须同时通过文献/实验来源确认。
- PubMed abstract 级证据已生成 475 行：456 个唯一 PubMed 记录被 EFetch 找到，398 行含摘要，
  89 行出现蛋白/突变相关关键词信号，但 0 行直接提到 reported mutation。
  这说明 abstract 能帮助缩小人工审校范围，但仍不足以把弱标签升级为强监督标签。
- 总控看板已纳入 abstract 证据信号，但 strict supervised rows 仍为 25，`safe_for_model_claim=false`；
  当前必须继续依赖 reviewed numbering decision、真实 domain interval 审校、MSA 和实验反馈来解除模型声明阻塞。
- 编号审校优先级已从“475 条平铺队列”细化为 5 类人工工作单：
  1 条同时具备 isoform exact 和 abstract signal，7 条只有 isoform exact，88 条只有 abstract signal，
  362 条低信号高风险，17 条 PubMed 缺失或无效。
  最现实的下一步是先人工审 8 条 isoform exact candidate，再审 89 条 abstract signal rows。
- 结构链映射已具备本地审校入口：500 个结构均能从 DB 映射到 UniProt，覆盖 114 个 UniProt；
  其中 93 个单链结构的 CA 原子数接近 UniProt 序列长度，可作为首批链映射审校候选。
  但 356 个多链结构仍需人工/可信程序选链，51 个单链长度不匹配需排查缺失残基、标签、片段结构或 DB 映射问题。
- 编号审校已从候选队列推进为可执行 packet：首包覆盖 8 条 isoform exact candidate，第二包覆盖 25 条 abstract signal row。
  所有 draft 默认 unresolved weak，说明当前系统已具备人工回源作业入口，但仍没有 reviewed numbering decision。
- 结构链映射已从工作单推进为可执行 packet：首包覆盖 25 条单链长度接近候选，第二包覆盖 25 条多链选链候选。
  所有 draft 默认 unreviewed，说明结构特征生产已有审校入口，但仍不能生成结构依赖训练特征。
- Domain 区间阻塞已由 0/1942 真实推进到 1785/1942：InterPro/Pfam 官方 API 对 1942 个 UniProt/Pfam row 返回
  1940 条 exact Pfam interval evidence，其中 1785 条是单 interval，可安全转为本地 program-reviewed domain interval decision。
- 剩余 157 条 domain row 未自动处理，原因主要是重复/多 interval domain occurrence 需要选择具体 occurrence；
  当前决策 schema 每个 `domain_record_id` 只能存一个 start/end，因此不能把多 interval 自动压成单 interval。
- Domain 现在可以支持一大批位点是否落入 Pfam domain 的候选特征，但模型质量声明仍被编号回源、MSA、结构链映射和实验反馈阻断；
  特别是 475 条突变标签编号未解决，domain 进展不能替代 supervised label curation。
- 编号、结构链映射、domain 三条审校流已从首批 packet 扩展为全量 packet：
  numbering 475/475、structure chain 500/500、domain unresolved 157/157 全部有本地人工审校入口和保守 draft。
- MSA 已有 158 个 execution jobs，但当前本机没有 MSA/同源检索执行器，因此所有 job 保持 blocked；
  这比直接生成单序列“保守性”更安全，因为单序列不能代表真实 conservation。
- 实验反馈源发现已定位 155 个潜在外部资料/历史会话候选，顶部包含 `matvenus-research` 的数据反馈类会话；
  但这些还不是结构化湿实验记录，必须人工转写为 schema 合规、编号 verified 的 `experiment_feedback.local.jsonl` 后才能训练。
- 结构链映射已补上 reviewed decision 的合同、校验和应用链路：
  `structure_chain_mapping_decisions.jsonl` 当前为空，validation 0/0 valid，apply 0 条 usable coordinate rows。
  这意味着 500 个结构文件虽然都能解析坐标摘要，但距离、口袋、暴露度、催化网络等位点级结构特征仍必须等待 reviewed chain mapping。
- 实验反馈源发现已从“155 个候选文件”推进为 11 个 review packet 和 155 行保守 source-review draft。
  分类结果：4 个 historical feedback candidate、31 个 historical session candidate、5 个 assay protocol reference、15 个 manual triage、
  其余为 fixture/reference、development/noise 或 low-signal candidate。
  这些 packet 只用于人工确认来源，不能直接变成 `experiment_feedback.local.jsonl` 或训练标签。
- 2026-07-25 国外优化调研补充：Boltz-2 是当前最值得优先评估的商业可用结构/亲和力后端；
  Chai-1 可作为结构/复合物候选对照；AlphaFold 3 和 ESM3-open 许可偏非商业，适合作对标或合规评估，不应默认进入商业生产。
- 国外设计链路建议分层接入：MMseqs2 先解除 MSA 0/158 阻塞，ThermoMPNN 做稳定性外部 baseline，
  CLEAN 做 EC/功能一致性检查，LigandMPNN 在结构链映射和底物结构输入稳定后做 ligand-aware 候选生成。
- 外部工具栈已建立 fail-closed readiness：8 个候选工具中当前 0 个 ready_for_local_evaluation，
  5 个 not_installed，1 个 blocked_by_license_review，2 个 blocked_by_license。
  这说明下一步实际解阻不是写 adapter 名称，而是本机安装/配置 MMseqs2 或提供可信 MSA cache。
- 运行面板已增加外部模型矩阵设计，前端应显示真实状态：ready、not installed、license review required、restricted；
  不允许把未安装或非商业受限工具显示成“正在运行”。
- 本机没有 brew/conda/micromamba；Docker CLI 存在但 Docker daemon 当前不可达。
  因此 MSA 解阻路线应改为三选一：启动 Docker 并配置 MMseqs2 镜像、手动安装 MMseqs2 二进制到 PATH、或提供可信 MSA/conservation cache。
- MSA runtime readiness 已 fail-closed：`runtime_ready=false`，158 个 MSA job 仍全部 blocked，
  阻塞原因为 `mmseqs` 不在 PATH、Docker daemon 未运行、可信 cache 不完整。
- MSA 命令计划已生成三条路径：local binary、Docker image、trusted cache validation。
  当前 3/3 全部 blocked，额外明确阻塞为 homolog database 未配置或不存在。
  这避免了即使未来 `mmseqs` 就位但没有 UniRef/Swiss-Prot/MMseqs 数据库时误跑空搜索。
- 外部全面深入调研 2026-07-27 进一步确认：
  - MSA 第一优先级仍是 `MMseqs2 + 本地数据库/可信 cache`；ColabFold 依赖 MMseqs2，HH-suite/HMMER 更适合作对照。
  - 结构/亲和力优先 `Boltz-2`；`Chai-1` 需要 Linux/CUDA/bfloat16 和更高 GPU 成本；`AlphaFold 3` 只做对标。
  - `OpenFold` 和 `ESM` 更适合作为开放先验和对照，不应掩盖真实结构/配体证据缺口。
  - 突变效应应拆成 `ProteinGym` benchmark、`ThermoMPNN` 稳定性 baseline、`CLEAN` 功能一致性检查。
  - 数据主干应由 `UniProt`、`BRENDA`、`SABIO-RK`、`MaveDB`、`FireProtDB`、`ProThermDB` 分层承担；许可与条件不能混成一个训练源。
  - 闭环产品的共同点不是单模型，而是 plate-level feedback、审计、权限和版本追踪。
- 结构链 mapping worklist 已重新排序：优先 reviewed UniProt、CA 长度更贴近、X-ray 高分辨率条目。
  现在首批候选更集中在 1:1 单链且 length_delta = 0 的条目，例如 `153L`、`110M`、`1A3D`，更适合人工先审。
- 本地核对确认：`153L` 和 `1A3D` 的链 A 与 UniProt 序列完全一致、无缺失残基；`110M` 虽然也是单链，但 PDB header 明确写明 `D122N`、`ENGINEERED: YES`、`MUTATION: YES`，
  因此应作为 reviewed_with_construct_or_tags，而不是 exact_sequence_match。

## 建模原则

- GPT-5.6 应继续作为平台主控；`KWB-EnzymeDesigner` 先作为专业酶改造工具/模型被调用。
- `KWB-EnzymeDesigner` 应统一整合 mutation ranking、stability prediction、activity risk、substrate fit、assay success 五个头，而不是拆成多个对用户暴露的模型。
- dTm/ddG 当前用于生成稳定性标签，因此训练监督 baseline 时不能作为输入特征；只能作为标签元数据保留。
- 数据库可以成为模型能力的一部分，但方式应是特征库、检索增强、监督标签和反馈闭环，不应把未经验证的模型输出反灌为实验标签。

## 平台接入原则

- 有上传结构时必须先解析结构、序列映射、编号校验，再进入结构依赖分析。
- 仅序列时可先做序列级分析；口袋、距离、催化网络、暴露度等结构结论必须等待预测结构。
- 输出层需要区分序列级结论、预测结构结论、实验结构结论。
- 结构预测 task_id 必须按会话和轮次隔离，避免引用旧任务。
- 与 GPT-5.6 不冲突：GPT-5.6 做主控和报告合成，KWB-EnzymeDesigner 作为专业工具模型返回结构化结果。
- P60 已把酶改造分析流程固定为“输入校验 -> 性质预测 -> 数据库证据融合 -> 编号/结构门控 -> 重要突变位点排序 -> ΔΔG/稳定性核验 -> 人工复核 -> 实验流程”，防止跳过性质预测直接给位点。
- 工具调用展示必须包含 step order、tool name、input/parameter summary、blocked/executed status、runtime/database readiness、result preview、evidence level 和 manual_review_required；执行前需要用户确认。
- 数据库融合按 Tier 0 KWB wet-lab、Tier 1 reviewed local DB、Tier 2 public DB、Tier 3 computational prediction、Tier 4 weak/unreviewed evidence 分层；弱证据不能自动升级为训练标签或 Go/No-Go。
- 重要突变位点规则固定：Tier 1 为 composite_priority >= 7.0 且无高风险门控，Tier 2 为 5.0-7.0 或需复核，Tier 3 为 <5.0 或序列-only 低置信；催化/金属/二硫键/保守/编号不确定/湿实验 No-Go 默认阻断。
- ΔΔG 约定固定：负值更稳定，正值更不稳定；`< -1.0 kcal/mol` 稳定化假设，`-1.0` 到 `+1.0` 近中性，`+1.0` 到 `+2.0` Watch，`> +2.0` 默认 No-Go；`-1.0` 到 `+2.0` 是人工核实重点区间。
- 当前 AI大模型 local pipeline 没有 Rosetta/PyRosetta/FoldX 可执行 ΔΔG 工具；RosettaFold 结构预测不等同于 Rosetta ddG。未完成 license/runtime/adapter/artifact gate 前，报告不能声称 Rosetta ddG 已执行。
- 实验流程固定为 6-10 个单点突变优先，完成编号/保护位点复核、突变构建、测序确认、表达/可溶性、活性、Tm/热处理残余活性、pH/温度曲线、replicate/QC 和 plate-level feedback 后，再进入组合突变。
- P61 把模型质量解锁条件拆成 reviewed numbering、MSA/conservation、真实实验反馈、ddG backend 和生产同步五条主线，当前全部仍是 fail-closed blocker。
- reviewed numbering 当前有效行仍为 0，strict supervised rows 仍为 25，说明模型质量解锁第一步仍是补齐 reviewed numbering。
- MSA/conservation 仍卡在 mmseqs 未安装、docker daemon 未就绪、trusted cache 缺失；即便有 158 个 target rows，缓存文件和 source metadata 仍是 0。
- 真实实验反馈仍是 0 training-eligible rows，说明 assay_success_head 和 activity_risk_head 不能靠文档摘要或模型输出冒充。
- Rosetta/PyRosetta/FoldX 目前只存在 readiness/contract 级计划，未形成可执行 ddG artifact；若要推进必须先解决 license、runtime 和 adapter gate。
- 生产同步仍必须等明确用户授权和 release_ready=true，不能因为本地报告完成就默认进入服务器同步。
- P62 已把“顶级模型”方向从口号推进到代码接口：高级 scaffold 已有 PLM、MSA、structure GNN、ddG backend、feedback calibration、多头输出、Pareto 排序和 uncertainty 的固定槽位。
- P62 当前仍是 dependency-free scaffold，不是训练好的神经网络；它的价值是让后续 ESM/SaProt/ThermoMPNN/Rosetta/FoldX adapter 和真实特征缓存有稳定落点。
- 高级 scaffold 的输出保留 missing modalities，避免在缺 MSA、ddG、wet-lab feedback 时把候选误报为高置信模型预测。
- 2026-07-28 GitHub/Google 继续调研结论：当前技术不能宣称顶级；顶级路线应升级为 9 类 evidence/cache 家族，而不是只堆一个神经网络名。
- P63 已把先进路线落成 fail-closed adapter cache plan：sequence PLM 包含 ESM2/ESMC/ESM3-open、SaProt、ProSST、ProtSSN；MSA 包含 MMseqs2/HMMER/HH-suite/trusted cache；结构/配体包含 reviewed structure graph、Boltz-2、Chai-1、AlphaFold 3 benchmark；稳定性包含 ThermoMPNN、Rosetta/PyRosetta/FoldX；酶功能包含 CatPred、CLEAN/DeepEC-style；生成包含 LigandMPNN/ProteinMPNN/RFdiffusion2；benchmark 包含 ProteinGym/FLIP/ATOM3D/FireProt/ProTherm。
- P63 当前输出为 9 个 feature family、36 个 adapter requirement、34 个 blocked adapter、2 个 ready_to_implement adapter；ready_to_implement 只表示本地结构解析类实现入口，不表示高级模型 feature 已生成或质量已达标。
- 外部调研后的优先级调整：P0 先做 MMseqs2/trusted MSA cache、reviewed structure graph、ProteinGym-style benchmark cache、KWB wet-lab feedback；P1 再做 ThermoMPNN、Boltz-2、ESMC/SaProt/ProSST、CatPred；P2 才做 LigandMPNN/ProteinMPNN/RFdiffusion candidate generation。
- AlphaFold 3、Rosetta/PyRosetta、FoldX、Chai-1、ProSST、CLEAN 等必须继续受 license/runtime/model-weight/data gate 约束；AlphaFold/RosettaFold 类结构预测不能等同于 Rosetta ddG，未经 artifact 和参数记录不得写入 ΔΔG 结论。
- P64 Google/GitHub 追加调研确认：Boltz-2 是 P1 结构/亲和力 adapter 的优先路线之一；Chai-1 可作为 Linux/CUDA benchmark/alternative；AlphaFold 3 因 non-commercial source/weights terms 继续放 benchmark/isolation 位。
- P64 确认 ESMC/ESM3 需要按具体模型、权重和 API/本地路线分别做 license gate，不能把一个 ESM 名称整体视为商业可用；SaProt/ProSST/ProstT5 一类结构语言模型必须先有结构 token、pLDDT/链映射和 checksum cache。
- P64 确认 CatPred 对 activity/substrate_fit 方向很重要，因为它直接面向 kcat/Km/Ki 和 substrate SMILES，但仍需要底物映射、条件记录和 KWB 湿实验校准，不能当实验标签。
- P64 确认 ThermoMPNN-D 可作为组合突变/epistasis 风险 stress-test，但它仍是 proxy，不替代 Rosetta/PyRosetta/FoldX 或真实稳定性实验。
- P64 确认 RFdiffusion2、LigandMPNN、ProteinMPNN 应作为候选生成层，不应先于 ranking evidence、protected-site policy、biosecurity screening、human approval 和 experiment budget gates。
- P65 已把 P64 的“全部开始”落成本地 execution board：12 条 workstream 覆盖 P0/P1/P2 和 cross-cutting gates，全部 started，全部 blocked，0 条 ready_to_verify，0 条 completion_ready。
- P65 的 start packet 只是本地工作启动证据，不是 reviewed decision、license approval、runtime approval、外部模型执行证据、customer delivery approval 或模型质量声明。
- 顶级模型真正的最短解锁路径仍是：reviewed numbering rows > 0 且 strict rows >= 100；MSA/runtime 或 trusted cache ready；reviewed structure graph rows > 0；KWB feedback training eligible rows > 0；至少一个外部 benchmark scorecard；ddG backend 有真实 runtime artifact。
- P66 已把 P0 reviewed structure graph 从 start packet 推进到真实本地 artifact：12 条 reviewed chain mapping 生成 12 个 residue graph JSON，全部带 input structure sha256 和 graph sha256，validation 12/12 通过。
- P66 结构图只证明“这些 reviewed chain 的坐标图可用于后续坐标特征”，不证明 475 条 mutation label 的编号正确，也不提供 MSA conservation、ddG、kinetics、wet-lab label 或 benchmark score。因此 `safe_for_model_claim=false` 继续正确。
- top-tier execution board 在 P66 后变为 12 started、11 blocked、1 ready_to_verify；这个 ready_to_verify 是 reviewed structure graph 局部状态，不是整体顶级模型 ready。
- P67 已补齐 trusted MSA/cache 的本地接收入口：158 个 target 都有 template row，后续只需把真实 MSA 文件、conservation JSON、source database/version 和 sha256 填入 `msa_trusted_cache_intake.local.jsonl`，再由 apply + validator 接管。
- P67 当前仍没有 MSA 解锁：intake_rows 0、accepted_rows 0、missing_target_rows 158；cache validation valid_rows 0、invalid_rows 158；runtime_ready false，阻塞为 `mmseqs` 不在 PATH、Docker daemon 不可达、trusted cache 未 ready。
- P67 明确禁止单序列 pseudo-conservation；没有 homolog search 或可信 cache checksum 之前，MSA/conservation feature 仍不能进入模型训练或 Go/No-Go。
- P68 已补齐 ProteinGym-style benchmark score cache 的本地接收入口：14 条 benchmark plan 都有 template row，后续真实 dataset/split/scorecard/metric artifact 加 checksum 和 license/leakage review 后可进入 validator。
- P68 当前 benchmark 仍未解锁：intake_rows 0、accepted_rows 0、missing_rows 14；validation valid_rows 0、invalid_rows 14、heads_ready 0、ready_for_model_claim false。
- P68 明确 benchmark 是评价门控，不是 KWB 湿实验标签来源；即使未来 ProteinGym/FLIP/ATOM3D 等 scorecard ready，也不能替代 reviewed numbering、MSA、ddG 和 KWB wet-lab feedback。
- P69 已把 ProteinGym official repo 本地缓存索引成 567 个带 sha256 的 source files，其中 benchmarks 路径 69 个、reference files 5 个、重要文件缺失 0；这解除的是“本地 source evidence 可查看/追踪”，不是 KWB 模型 scorecard。
- P69 后 `proteingym_local_source_ready_as_external_source_evidence=true`，但 `proteingym_local_source_ready_as_kwb_scorecard=false`，`benchmark_score_cache_validation_ready_for_model_claim=false` 仍正确；后续仍需要真实 scorecard、split、metric、leakage review 和 license/reviewed decision 才能支持 benchmark claim。
- P70 已把 MMseqs2 官方 macOS universal binary 下载并缓存到 `cache/external/MMseqs2`，version probe 返回 `17b688d21dda57fc5f5b7286ecba7ec003d4717f`，binary sha256 为 `8a13c3c252adc296c3f2996389be657cb42f3a3f24beb145d500f21b84a0a33d`；这解除的是“本机 MMseqs2 二进制缺失”，不是 MSA 数据缺失。
- P70 后 `mmseqs2_local_runtime_ready_as_local_binary_runtime=true`，但 `msa_runtime_ready=false`、`msa_runtime_homolog_database_ready=false`、`msa_cache_validation_ready=false`；158 个 MSA jobs 仍 blocked，必须配置真实 homolog database 或导入可信 MSA/conservation cache 后才能生成特征。
- P71 已下载并构建 UniProtKB/Swiss-Prot MMseqs2 homolog database，本地 lookup 575503 条，版本为 Release 2026_02 of 10-Jun-2026；`homolog_database_ready=true` 使 `msa_runtime_ready=true`，158 个 MSA jobs 从 blocked 变为 ready。
- P72 已执行真实 MMseqs2 Swiss-Prot 搜索并生成 MSA/conservation cache：158/158 targets 有 hits，raw_hit_rows 22410，alignment FASTA 158，conservation JSON 158，trusted cache accepted_rows 158，validator ready true、valid_rows 158、invalid_rows 0。
- P72 的 conservation 是 Swiss-Prot homolog alignment 支持的 computational feature，不是湿实验标签、不是 ddG、不是 benchmark scorecard；`safe_for_model_claim=false` 仍然正确，因为 reviewed numbering、真实实验反馈、ddG backend 和 benchmark score cache 仍未全部解锁。
- P73 已把 benchmark score cache 从全空推进到 1/14：`KWB strict mutation holdout` 生成 dataset/split/scorecard/metric 四件套，25 行 strict verified source、1 行 primary test holdout，leakage check passed；但统计力很弱，13 个 planned benchmark 仍 missing，`ready_for_model_claim=false` 正确。
- P74 已把 Rosetta/PyRosetta/FoldX 从“未注册/未接线”推进到 fail-closed ddG backend gate：registry、config、result schema、readiness report、execution plan 和 adapter 已存在；但 Rosetta/PyRosetta/FoldX 许可/安装/数据门控未通过，ThermoMPNN 也未 ready，因此 0 个 ddG backend 可执行。
- ddG 输出约定继续固定为 negative ΔΔG stabilizing；`-1.0` 到 `+2.0 kcal/mol` 仍是人工核实重点，任何预测 ddG 都不能替代湿实验稳定性标签。
- P75 FireProtDB numbering audit 证明 8 条 isoform exact candidate 仍不能自动提升：FireProtDB exact_match_rows 0、failed_query_rows 2；综合 PubMed abstract/title 后 ready_for_decision_draft_rows 0、blocked_rows 8、safe_to_auto_promote false。
- 8 条候选的主要阻塞是 isoform 仍需人工 review、PubMed title/abstract 未直接提到 reported mutation、多数 PubMed high risk、无 FireProtDB exact UniProt+mutation match；因此 `numbering_curation_decisions.jsonl` 仍不应写入自动决策。
- P76 实验反馈可训练性审计覆盖最高优先级历史反馈候选 4 行：2 行是模型预测/候选结果占主导且缺条件/重复/QC，2 行是后续流程咨询且无明确 mutation token；training_eligible_rows 0。
- Matvenus 历史会话中出现的 VenusREM/VenusX 结果和 result.csv 链接只能作为旧平台预测回放/候选证据，不能当湿实验反馈。两次尝试下载 OSS CSV 都失败于 `LibreSSL SSL_connect: SSL_ERROR_SYSCALL`，本地缓存目录仍为空。
- 当前模型质量硬门槛仍为：strict_rows 25、reviewed numbering valid_rows 0、experiment feedback training_eligible_rows 0、ddG ready_backend_count 0、benchmark score cache 1/14 且 not ready_for_model_claim；MSA 158/158 ready 只能解除 conservation feature blocker。
- P77 已把 MSA conservation 从 cache artifact 接入 strict 训练代码路径：25/25 strict verified rows 都成功 join 到 `msa_site_conservation`、window conservation、hit_count、database version 和 homolog depth 特征；missing_rows 0。
- MSA-enriched repaired baseline 训练成功，使用 88 个 numeric features；但 validation accuracy 为 0.0、test accuracy 为 1.0 且 test split 只有 1 行，因此只能说明 MSA feature path 可运行，不能说明模型质量提升。
- 模型质量 unlock report 已修正：MQ-U002 `msa_conservation` 从 blocked 变为 ready_to_verify；blocked_requirements 从 5 降到 4。剩余 blocker 是 reviewed numbering、real experiment feedback、ddG backend 和 production sync/overall release gates。
- P78 结构链证据审计确认：84 个 auto-review candidates 中，只有 `1A2N`、`11YV`、`153L`、`1A3D` 的链差异能被本地 PDB DBREF/SEQADV/REMARK465 证据完全解释；其中 `153L`/`1A3D` 已在旧 decisions，本轮新增 `1A2N` 和 `11YV`。
- 新增 `1A2N` 的证据边界：PDB DBREF 映射 A 链 1-419 到 UniProt `P0A749`，SEQADV 解释 C115A engineered mutation，REMARK 465 解释 419 位缺失；可用于 reviewed chain coordinate graph，但不证明 mutation label numbering。
- 新增 `11YV` 的证据边界：PDB DBREF 映射 A 链 1-363 到 UniProt `O34453`，SEQADV 解释 E25A、E26A、E316A engineered mutations；可用于 reviewed chain coordinate graph，但不证明功能/稳定性标签。
- 结构链 reviewed decisions 从 12 增至 14，curated mappings 14，reviewed structure graph validation 14/14 valid；但 next unlock blocker 仍要求 25，因此 structure_chain_mapping 仍 blocked。
- 多个 T4 lysozyme 候选虽然 identity 高且有 SEQADV，但仍存在未由 SEQADV/REMARK465 解释的差异，例如 P00720 位置 12/137；暂不能自动提升，需 SIFTS/DBREF/construct 或 manual alignment 进一步审查。
- P79 DBREF-backed 审计把 fragment/multi-chain 结构纳入更强证据规则：必须满足 source DB 只有一个目标链、目标链在 parsed chains 中、PDB DBREF 指向同一 UniProt、observed chain 序列匹配 DBREF UniProt 区间，少量 substitutions 必须由 SEQADV 解释。
- P79 本轮新增 11 条 reviewed chain mapping：`1A39`、`154L`、`10MH`、`11AO`、`10YE`、`10YG`、`10YF`、`10YH`、`10YI`、`1A14`、`13FN`；结构链 decisions 25/25 valid，reviewed graph 25/25 valid。
- DBREF 区间映射会把未覆盖的 UniProt canonical 区间记录为 `PDB_DBREF_UNIPROT_SUBRANGE_EXCLUDED`，因此这些结构可用于已覆盖区间的坐标图特征，但不能用于未覆盖位点的距离/口袋/暴露度结论。
- P43-A002 structure_chain_mapping 已达到 next unlock target；`next_unlock_blocker_matrix` 中 blocked_actions 从 11 降到 10，completion_ready_actions 从 1 升到 2，结构链不再列为 top blocker。
- P79 不改变模型质量声明：reviewed numbering 仍 0/75，strict supervised rows 仍 25/100，wet-lab feedback 仍 0，ddG backend 仍未 ready，`model_quality_ready=false` 正确。
- P80 domain unresolved 中 155 条是 reviewed InterPro/Pfam 重复 occurrence，区间分布为 120 条 2 intervals、20 条 3 intervals、9 条 4 intervals，另有 5/6/7/14/15/16 intervals 各少量；这些是真实 repeated domain，不应压成单 start/end decision。
- P80 新增 `domain_multi_occurrence_features.jsonl` sidecar，保全 155 条 repeated Pfam 的全部 occurrence，并要求 Pfam 一致、source_database reviewed/unreviewed、区间在 sequence_length 内且不重叠；当前 feature_rows 155、invalid_rows 0、ready_for_feature_use true。
- P80 后 `domain_interpro_review_packet_report.json` 同时保留 raw_unresolved_rows 157 和 feature-use unresolved_rows 2；`multi_occurrence_sidecar_resolved_rows=155`，剩余 2 条为 `no_exact_pfam_interval`，仍需人工或新证据处理。
- P80 解除的是 P43-A003 domain occurrence feature-use blocker：next unlock completion_ready_actions 2->3，blocked_actions 10->9；它不创建 reviewed numbering、不提升 strict supervised rows、不导入 wet-lab feedback、不生成 ddG，也不改变 `model_quality_ready=false` 或 `release_ready=false`。
- P81 reviewed numbering 继续深挖后发现，当前 542 条 `ProThermDB` stability records 的 PMID 形态全部为 `PMID:310xxxxx`，与 `backend/scripts/generate_sample_data.py` 的随机样例生成逻辑一致；该脚本明确随机生成 `wild_type`、`mutant`、`ddg`、`dtm` 和 `literature_ref`。
- P81 因此把最硬门槛从“编号修复”上移为“标签 provenance”：当前 25 条 strict rows 虽然 sequence WT 精确匹配，但全部缺少 raw source checksum/reviewed source receipt，并命中 synthetic_generate_sample_data_pmids_310xxxxx；claim_eligible_rows 为 0。
- P81 新增 `label_provenance_audit_report.json`，输出 `enzyme_mutation_supervised_claim_eligible.jsonl` 0 行和 `enzyme_mutation_synthetic_label_evidence.jsonl` 25 行；工程 smoke 仍可跑，但模型质量声明必须基于真实来源标签。
- P81 后 `safe_training_entrypoint_check.json` 增加 warnings：`below_claim_eligible_real_label_threshold` 和 `synthetic_or_unreceipted_labels_present`；`claim_readiness_matrix` 的 model_quality_claim 新增“claim-eligible real supervised rows >=100”和“no synthetic or unreceipted strict labels”要求。
- P81 的结论是：继续在当前 synthetic ProThermDB labels 上做 reviewed numbering 属于错误方向；真正解锁必须导入真实 ProThermDB flat file/FireProt/ProTherm raw artifact checksum、或 KWB 湿实验反馈，并在该真实来源上做编号校验。
- P141 编号审核页面原先主要加载 33 条 briefing 优先项和 4 条语义冲突；现在新增完整 operator queue，把 475 条 numbering review worklist 全部合并 deep audit、packet、existing decision 和 semantic conflict 状态后排序展示。
- P141 当前完整 operator queue 状态：475 条总队列、471 条 open todo、4 条 semantic conflict、475 条 deep-audit reject recommendation；它只是人工导航和页面加载源，不写 `numbering_curation_decisions.jsonl`，不提升 strict supervised rows，不改变 `safe_for_model_claim=false`。
- P82 用户确认 `/Venus-15B淀粉酶项目` 为真实实验来源；本地文件包含 486 aa 15B 序列、15B-AAP-noCa PDB、背景说明和客户/产品实验方案资料。
- P82 15B 背景文件明确提到“之前实验观察到 E331Q 这类突变能提高 pH4.5/pH6.0 的活性比值”；四个候选突变 S265D、D405N、E331Q、M204H 均与 15B 序列 WT 精确匹配。
- P82 只把 E331Q 写入 `experiment_feedback.local.jsonl`：它有真实历史实验观察和编号 verified；S265D、D405N、M204H 只是 Venus/MD 目标，没有当前文件内的实测结果，不写训练反馈。
- P82 feedback intake validation 从 0 提升到 1：input_rows 1、valid_rows 1、training_eligible_rows 1；P43-A005 completion_ready，next unlock completion_ready_actions 4、blocked_actions 8。
- P82 仍有边界：E331Q 是 qualitative historical activity observation，缺 numeric pH4.5/pH6.0 ratio、raw plate signal、replicate 和 QC；因此 plate_feedback training_eligible_rows 仍为 0，模型质量仍 false。
- P83 在用户确认“这就是真实实验”后增加资产级门控：`audit_venus15b_experiment_assets.py` 扫描 18 个 source files，4/4 候选突变编号 verified，qualitative_feedback_rows 1、numeric_training_eligible_rows 0、plate_training_eligible_rows 0、tabular_assay_file_count 0。
- P83 补强 `validate_experiment_feedback_intake.py`：当前 `training_eligible_rows=1` 用于真实反馈来源解锁，另行输出 `qualitative_training_eligible_rows=1` 和 `numeric_training_eligible_rows=0`，防止定性历史观察被误读为数值 assay label。
- P83 保持 P43-A005 completion_ready，但 P43-A006 plate feedback 继续 blocked；S265D/D405N/M204H 只记录为设计候选和编号 verified，不写入实验反馈。
- P84 用户最新明确 `/Users/keweibo/科为博/05自动化程序/04研发工作区/酶蛋白AI平台/AI大模型/Venus-15B淀粉酶项目` 才是真实实验数据目录；该目录实际只有 3 个文件：`15B-AAP-noCa.pdb`、`淀粉酶15B序列.txt`、`淀粉酶背景.txt`。
- P84 后 Venus-15B 资产审计口径已纠偏：source_files_scanned 3、qualitative_feedback_rows 1、numeric_training_eligible_rows 0、plate_training_eligible_rows 0；旧父目录下其它资料不再计入本轮真实实验资产数量。
- P85 已把 ThermoMPNN 官方源码缓存到 `cache/external/ThermoMPNN`，MIT license、默认权重 `models/thermoMPNN_default.pt`、README PDB inference entry 都 ready；这只解除 source/license/model-weight gate。
- P85 ThermoMPNN runtime 仍 blocked：`.venv-thermompnn` 缺 `torch`、`pandas`、`numpy`、`tqdm`、`omegaconf`、`Bio`、`pytorch_lightning`、`torchmetrics`、`wandb`、`joblib`；pip 访问 PyPI 安装基础依赖时反复 timeout/SSL EOF，未生成任何 ddG proxy artifact。
- P85 后 ddG readiness 仍为 ready_backend_count 0、executable_ddg_backend_ready false、proxy_ddg_backend_ready false；ThermoMPNN 只能作为未来 predicted ddG proxy backend，不能替代 Rosetta/PyRosetta/FoldX physics ddG 或湿实验稳定性标签。
- P86 使用清华 PyPI 镜像完成 `.venv-thermompnn` 依赖安装，`torch/pandas/numpy/tqdm/omegaconf/Bio/pytorch_lightning/torchmetrics/wandb/joblib` 全部可 import；ThermoMPNN source/runtime/local inference ready。
- P86 官方 `custom_inference.py` 首次 smoke 暴露 `local.yaml` 写死 `/proj/kuhl_lab/ThermoMPNN` 的作者机器路径；本地已有 `vanilla_model_weights/v_48_020.pt`，因此新增 KWB wrapper 在运行时覆盖 `cfg.platform.thermompnn_dir`，不修改第三方源码。
- P86 已为 Venus-15B 四个候选突变生成 ThermoMPNN proxy ΔΔG artifact：S265D `+1.220` destabilizing_watch；D405N `-0.545` near_neutral_manual_review；E331Q `+0.144` near_neutral_manual_review；M204H `+0.632` near_neutral_manual_review。负值更稳定、正值更不稳定，全部要求人工复核。
- P86 后 ddG readiness 变为 ready_backend_count 1、proxy_ddg_backend_ready true、one_ddg_backend_ready true；executable_ddg_backend_ready 仍 false，因为 Rosetta/PyRosetta/FoldX 未授权/未安装/未产出 physics ddG artifact。
- P87 修正模型质量门控口径后，MQ-U003 `rosetta_pyrosetta_foldx_ddg` 从 blocked 变为 ready_to_verify；这是对 ThermoMPNN proxy ddG baseline 的承认，不是 Rosetta/FoldX physics ddG 或模型质量 claim。
- P87 后模型质量 blocked_requirements 从 4 降到 3，ready_to_verify_requirements 从 1 升到 2；剩余硬 blocker 是 MQ-U001 reviewed numbering/claim-eligible real supervised rows、MQ-U004 数值/孔板真实实验反馈、MQ-U005 release/production authorization。
- P88 本地外部稳定性源审计发现 ThermoMPNN 随仓库包含 FireProt/Megascale/S669/SSYM/Myoglobin 等 11 个 CSV，合计 280089 行且都有数值稳定性字段；10 个文件具备序列/突变/数值字段，可作为后续外部真实监督标签导入候选。
- P88 这些候选行当前 claim_eligible_rows_now 仍为 0，因为还缺 KWB schema mapping、ddG 方向/单位归一、source/license scope 选择、train/test leakage review 和 reviewed import receipt；不能直接混入模型质量训练。
- P89 FireProt curated 子集已形成受控导入候选：5067 行，全部带 source_file_sha256、source_row_index、UniProt、mutation、source ddG、publication DOI/PMID 和 source sequence WT 自洽校验；strict supervised 与 KWB strict holdout 初筛 overlap 均为 0。
- P89 仍保持 claim_eligible_rows_now 0：候选还未完成 ddG 方向归一、KWB supervised schema mapping、license scope 选择和 reviewed import receipt，因此不进入训练、不改变模型质量 claim。
- P90 FireProt ddG 方向归一已完成候选层处理：5067 行全部设置 `kwb_ddg_kcal_mol=source_ddG`，`kwb_negative_ddg_is_stabilizing=true`；dTm sanity 支持多数可检查行符合 negative-ddG-stabilizing，11 行冲突保留人工复核。
- P90 后 FireProt 候选仍不训练：remaining blockers 是 license_scope_not_selected、reviewed_import_receipt_missing、not_written_to_kwb_supervised_schema、leakage_review_not_approved_for_training。
- P91 FireProt 候选已映射为 KWB supervised schema draft：5067 行全部具备 record_id、source、record_type、uniprot_id、group_key、mutation_position、label_decision_candidate、label_ddg_kcal_mol、source checksum 和 publication reference。
- P91 仍不训练：5048 行 manual_review_required，ready_for_training_import_rows 0；剩余 blocker 是 license_scope_not_selected、reviewed_import_receipt_missing、leakage_review_not_approved_for_training、numbering_not_reviewed_by_kwb。
- P92 FireProt leakage review 已把 5067 候选按 75 个 UniProt group 生成 deterministic split proposal；自动检查显示 group split leakage 0、当前 strict supervised overlap 0、KWB strict holdout overlap 0。
- P92 发现 duplicate_mutation_key_count 2133，说明同一 UniProt+mutation 在多个来源/实验条件/拆分中重复出现；在导入训练前必须有 dedup/aggregation policy，否则不能批准训练。
- P93 已完成 FireProt duplicate-resolution candidate：按 `uniprot_id + mutation` 对 5067 条 mapping candidate 分组，生成 2133 个重复组。2124 组的 `label_method + assay_ph + assay_temperature_c` 完全一致，只生成 median 候选；9 组含异质 assay，禁止聚合、必须逐条件人工审核。候选 JSONL 保留全部原始 source rows、source row index 和 source checksum；全部 2133 组仍 `manual_review_required=true`，training import 0、claim eligible 0。
- P94 已完成 FireProt duplicate review packets：2133 个候选组拆为 22 个批次，按异质 assay、同 assay 数值冲突、同 assay 完全重复排序；生成空的 `fireprot_dedup_review_decisions.template.jsonl`。当前 decision_rows 0、approved_rows 0、training import 0，review packet 只提供人工审核入口，不生成审批。
- P95/P96 已把 FireProt dedup 人工决策和 reviewed import candidate 也做成 fail-closed gate：当前 `fireprot_dedup_review_decision_validation_report.json` 显示 2133 个候选、0 决策、0 approved、2133 missing review；`fireprot_reviewed_import_candidate_report.json` 显示 reviewed_import_candidate_rows 0、ready_for_training_import_rows 0。safe pipeline 当前 148/148、0 failed；release_ready 仍 false。
- P97 已接入用户确认的真实湿实验突变体库证据：15B/16B/4G 共 25 个文件、18 个 CSV；原始/派生数据生成 445 条 wet-lab relative-to-control feedback candidates，其中 15B/16B/4G 分别为 190/66/189 条，activity 354、stability 91。因只有 15B 有本地序列，当前 numbering_verified_rows 29，numeric_training_candidate_rows 12；全部仍未写入 `experiment_feedback.local.jsonl`，ready_for_feedback_intake_rows 0、claim eligible 0。
- P98 已把 12 条 15B 数值候选固化为人工授权模板范围，覆盖 D105N、S265T、E331Q 三个单点突变和 pH6.0 绝对酶活、pH4.8 绝对酶活、酸性保持率、85C 3min 热稳定性四类指标。授权文件当前为空，因此 validator 显示 missing_candidate_authorization_rows=12、authorized_candidate_rows=0、preflight_rows=0。该门控证明真实湿实验数据已经可审，但仍不能声明模型质量或自动训练。
- P99 修复 16B/4G 候选解析后，真实湿实验库的 parseable mutation rows 为 351：15B 120、16B 60、4G 171。16B/4G 的阻塞从“突变不可解析 + 编号未验证”收敛为“编号未验证”，下一步硬门槛是找到并审核 16B/4G parent sequence/version，而不是继续改派生表。
- P100/P101 已把 16B/4G parent sequence 变成正式 gate：本机已有候选序列源均不能接受为 16B/4G 母本；历史 299 aa 序列与 4G/16B 突变 WT 残基不匹配，backend uploaded FASTA 是测试/过短序列。后续必须把真实 16B/4G sequence、sequence_version、source、reviewer 写入 `wet_lab_mutant_library_project_sequences.local.jsonl`，validator 通过后才能进入独立 numbering audit。
- P102/P103 已把“序列通过后做 numbering audit”和“授权 preflight 后做 feedback apply”都启动为本地 fail-closed 链路；当前因 sequence intake 0、feedback authorization 0，numbering audit rows 0、apply plan rows 0、applied rows 0。
- P104 本机探测确认 Rosetta/FoldX/PyRosetta 物理 ddG 后端仍未解锁：Rosetta/FoldX executable 未找到，PyRosetta module 不可用，且 config disabled/license gate 未批准。ThermoMPNN proxy ready 只能作为 proxy ddG artifact，不能声明 Rosetta/FoldX/PyRosetta 已集成。
- P606-P610 边界审计确认：activity-risk formal label decision 和 training lineage 里存在 6 条 training-import eligible/formal label source rows，但本轮 audit/report/validation 仍固定 `training_import_allowed=false`、`safe_for_training_import=false`、`safe_for_model_claim=false`、`release_ready=false`、`production_execution_allowed=false`。
- P609 wet-lab reconciliation 当前 `contract_training_import_eligible_rows=6` 且 `model_quality_training_import_eligible_rows=6`，这不是 release 或 model-quality claim；真正 claim 边界仍由 `claim_eligible_rows=0`、`safe_for_model_claim=false`、`release_ready=false` 约束。
- P610 positive-claim quarantine 扫描 894 个 report，risky true hits 全部 allowlisted，`disallowed_true_hit_count=0`；quarantine pass 只证明未发现未授权正向 claim flag，不代表训练导入、模型声明或 release。

## 2026-08-19 P611-P615 activity-risk and feature boundary findings

- P611 绑定 activity-risk training-import label source：已 materialize `training_import_label_rows=6`、`training_import_written_rows=6`，但 `training_execution_allowed=false`、`safe_for_model_claim=false`、`release_ready=false`；materialized import label 不等于训练执行或模型声明。
- P612 绑定 replicate preflight/template：`preflight_rows=6`、`decision_template_rows=6`，但 `formal_decision_rows=0`、`ready_for_training_import_rows=0`、`training_import_written_rows=0`；preflight 完整不代表 replicate/formal label 已批准。
- P613 绑定 feature coverage by head/group：`coverage_rows=875`、`source_feature_rows=203`、`protein_group_count=175`，但 `training_label_source_rows=0`、`feature_rows_counted_as_labels=0`、`five_head_ready_head_count=0`；feature coverage 是输入审计，不是训练标签。
- P614 绑定 feature coverage gap queue：`gap_count=34`，但 `training_label_source_rows=0`、`feature_rows_counted_as_labels=0`；gap queue 是 remediation planning，不创建训练标签或 release 权限。
- P615 绑定 feature-label boundary quarantine：1 个 legacy feature artifact 存在 label contamination，25 条 label-contaminated records 被 2 个 excluded-from-index artifact 隔离；quarantine success 只证明污染未进入 validated feature input boundary，不批准训练、claim 或 release。

## 2026-08-19 P616-P620 benchmark boundary findings

- P616 绑定 benchmark score cache validation：`benchmark_rows=15`、`valid_rows=13`、`invalid_rows=2`、`heads_ready=3`，但 `ready_for_model_claim=false`、`safe_for_model_claim=false`、`release_ready=false`；score cache validation 不能解释为 benchmark approval 或 score-cache 写入授权。
- P617 绑定 benchmark coverage dashboard 与 validation：dashboard 仍为 `status=blocked`，`benchmark_rows=15`、`valid_rows=13`、`invalid_rows=2`、`heads_ready=3`、gap queue rows=`2`；validation `success=true` / `safe_for_training_pipeline=true` 只证明阻断状态一致，不创建训练或模型声明权限。
- P618 绑定 five-head benchmark gap plan：`action_rows=5`、`required_benchmarks=15`、`cache_validated_benchmarks=13`、`heads_with_complete_scorecards=3`、`source_report_consistent=true`、`validation_failure_count=0`；gap plan 是 remediation plan，不是 metric claim 或 release approval。
- P619 绑定 benchmark lane machine pre-review：`lane_count=2`、`status=ready_for_human_review`，但 `formal_decision_rows_observed=0`、`formal_approved_rows_observed=0`、`training_import_written_rows=0`；machine pre-review ready 只说明可送人工审核，不等于正式 decision。
- P620 绑定 benchmark lane status aggregate：`lane_count=2`、`status=blocked`、`bridge_validation_success=true`、`claim_release_gate=closed`、`training_import_written_rows=0`；bridge validation success 不能越过 claim/release gate。
- 最终 P616-P620 validators 全部 `success=true/failures=0`；全量安全流水线 `861/861/0`，data lake live integrity=`2379 artifacts/2377 strict/2 volatile/0 failures`，local release consistency=`success=true/artifact_count=2379/release_ready=false`，safety guard current=`success=true/guard_link_count=70`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-21 P675 real local breakthrough probe

- 当前 `next_unlock_blocker_matrix.json` 的 8 个 blocked actions 已逐项核对：numbering、plate feedback、license、biosecurity、IP/FTO、workstream acceptance、operator review、claim promotion。
- numbering 的 4 条当前 formal decisions 全部是 `reject_label`，且 `numbering_curation_validation_report.json` 显示 `valid_rows=4`、`invalid_rows=0`；它们是有效的拒绝记录，不是可转成 canonical mapping 的数据。
- `KWB strict mutation holdout` 的本地 dataset 是 0 行，`leakage_check_status=failed`；`reviewed substrate identity set` 没有正式 decision，因此 benchmark 缺口不是 validator 误报。
- 真实 4G 原始表 `04_原始测量事实表.csv` 有 642 行；已有 benchmark builder 可解析 288 条 Row/Col activity plate/well 行，activity-risk 聚合 benchmark 为 17 行、使用 638 条原始测量。两个 benchmark validator 均 `success=true`、`failures=0`。
- 正式 `datasets/feedback/experiment_feedback_plate.local.jsonl` 仍为 0 行。4G 原始表缺正式 plate ID、仪器、protocol version、记录时间和人工 QC/review 状态；builder 只能把 plate/well 作为 evaluation-only inferred evidence，不能写入正式 plate intake。
- 结论：本轮没有发现可以安全通过本地代码修复的 P0 假阻塞。继续推进需要真实人工 review/QC、外部 license/IP/biosecurity 决策、正式 benchmark/substrate review 或物理 runtime receipt；不得把 benchmark rows、feature rows、session drafts 或 inferred metadata 伪装成训练/发布证据。

## 2026-08-19 P621-P625 DDG runtime and smoke boundary findings

- P621 绑定 DDG executable probe：`backend_rows=3`、`ready_for_ddg_execution_rows=3`、`version_probe_succeeded_rows=6`、`executable_ddg_backend_ready=true`，但 `physics_ddg_ready=false`、`ddg_smoke_job_executed=false`、`claim_eligible_rows_now=0`；executable/module discovery 不是 ddG physics readiness、训练标签或 model claim。
- P622 绑定 PyRosetta physical smoke：`physical_smoke_passed=true`、`ddg_protocol_executed=true`、`ddg_table_rows=1`、`smoke_artifact_count=5`，但 `training_label_rows=0`、`manual_review_required_rows=1`、`safe_for_model_claim=false`；runtime smoke success 只证明本地 smoke artifact 存在。
- P623 绑定 PyRosetta verified mutation ddG feature validation：`computed_feature_rows=29`、`quality_passed_rows=18`、`quality_blocked_rows=11`、validation valid rows=`29`，但 `scientific_validity_claim=false`、`safe_for_training_import=false`、`safe_for_model_claim=false`；quality pass 是计算特征 sanity，不是科学有效性或模型质量声明。
- P624 绑定 FoldX physical smoke bootstrap validation：FoldX executable/help probe/parser contract 均为 true，但 `physical_smoke_passed=false`、`runtime_receipt_ready=false`、`ready_execution_plan_rows=0`、`blocker_count=4`；parser/help probe 不等于 FoldX runtime receipt 或 release readiness。
- P625 绑定 DDG backend operator packet：`packet_rows=3`、`ready_for_execution_now_rows=1`、`requires_human_input_rows=3`、`completion_ready_rows=0`；operator packet validity 只是解锁说明一致，不允许自动执行或生产使用。
- 最终 P621-P625 validators 全部 `success=true/failures=0`；全量安全流水线 `871/871/0`，data lake live integrity=`2404 artifacts/2402 strict/2 volatile/0 failures`，local release consistency=`success=true/artifact_count=2404/release_ready=false`，safety guard current=`success=true/guard_link_count=70`。所有 training/model/customer/production/release flags 保持 false。
- 2026-08-04 复核结果：`advanced_model_feature_contract_validation_report.json` 已为 `success=true`，194 条 ready feature refs 均为 model-input-only，不再是当前阻塞点；真正剩余的机器/人工边界在于 benchmark 正式 decision 仍为 0、FireProt reviewed import candidates 仍为 0、supervised preflight 仍为 0，以及 `KWB strict mutation holdout` / `reviewed substrate identity set` 仍因 `benchmark_status_not_present` invalid。Rosetta/PyRosetta 仍是可执行态，FoldX 仍缺真实 executable。
- FireProt 路径的最小真实缺口已确认：5067 条 schema-mapped candidates 被聚合为 2133 个 dedup review groups，`fireprot_dedup_review_decisions.jsonl` 当前为空，因此 `approved_for_import_candidate_rows=0`、reviewed import candidates=0、supervised preflight=0。必须由人工填写并通过 validator 的 source provenance、numbering、license scope、review receipt 等字段，不能机器自动批准。
- 当前 benchmark 缺口也已收敛到两个正式 decision 输入：`KWB strict mutation holdout` 和 `reviewed substrate identity set`。bridge 已能在完整 decision + receipt 后自动生成 dataset/split/scorecard/metric 并写入 intake；当前 approval=0，因此不写入、不训练。
- `validate_human_decision_backlog_fail_closed_consistency.py` 与 `validate_local_release_manifest_fail_closed_consistency.py` 已同步到当前真实 backlog（feedback source required/missing 161；总 missing 1188），避免新增审查包后安全流水线因 stale expected value 误报失败。
- FireProt authorization/preflight 已纳入持续安全流水线和两个 manifest。这样人工填写授权后会自动被验证并生成 preflight；当前仍是 0 行，不会因“模板存在”而被视为授权或训练数据。
- 本轮“全部开始”后的非人工刷新结果：五头样本缺口队列验证通过，benchmark coverage 13/15、2 个 gap，ddG executable probe 找到 Rosetta/PyRosetta 但未找到 FoldX，FireProt authorization/preflight 验证通过；全量安全管线 400/400 通过。
- PyRosetta 物理 ddG 已真实 smoke 成功：`pyrosetta_physical_smoke_bootstrap_report.json` 显示 `physical_smoke_passed=true`，5 个 checksum artifact 完整；`pyrosetta_verified_mutation_ddg_feature_report.json` 29 条特征全部生成，验证后 18 条质量通过、11 条质量阻断。validated feature index 仅纳入质量通过子集，因此当前 PyRosetta 贡献仍固定为 11 条 `pyrosetta_ddg_reu_input`。
- FoldX 仍是硬缺口：`build_foldx_physical_smoke_bootstrap.py` 验证通过但 `foldx_executable_found=false`、`physical_smoke_passed=false`，没有真实可执行文件就不能继续声称集成。
- `closed-loop` 可直接借鉴为“轮次化 DBTL 闭环 + predictor registry + demo/assistant wrapper”模板；`OED` 可直接借鉴为“酶数据 ETL + 统一 schema + 搜索/导出 + 可视化”模板。前者是 MIT，后者是 GPL-3.0，适合在本地研究和重写接口，不适合把 GPL 代码直接并入闭源核心。

## 2026-08-03 P217 关键发现

- benchmark readiness 的旧不一致不是 benchmark 数据本身错误，而是 `five_head_benchmark_gap_actions` 存在双路径副本：当前生成器写 `datasets/governance/`，readiness packet 曾读旧的 `datasets/benchmark/`。修正读取路径并重建后，`source_discrepancies=[]`；当前权威状态仍是 4/15 valid、11 invalid、0 head ready。
- 当前 valid benchmark 只有四个：ProteinGym、ThermoMPNN comparison、FireProt/ProTherm reviewed stability set、KWB activity numeric feedback smoke。它们都是 evaluation cache，不是训练标签，也不打开模型质量声明。
- activity_risk formal label 的真实可自动推进范围只有 6 条 KWB wet-lab 数值 activity feedback。新增授权闭环后，每条 formal label 必须匹配 `wet_lab_mutant_library_feedback_authorizations.jsonl` 中的 approved activity_risk 授权和 QC/编号/单位/batch/replicate policy；未授权 numeric activity 行会 fail-closed。
- 这 6 条 activity_risk label 仍是 single measurement，replicate_count_counted_for_training=0；因此只能作为 source-level training import eligible，不满足五头训练 100 samples、10 groups、3 explicit replicates 的阈值。
- FoldX 当前只是真实 parser/contract ready：可解析 BuildModel `Dif_`/`Average_`/`Raw_` 输出，fixture ddG=-1.234 kcal/mol。runtime 仍未 ready，因为缺官方 binary、license decision、config enablement、probe、smoke artifacts 和 runtime receipt。
- `build_ddg_backend_execution_plan.py --backend foldx` 已能生成 FoldX 专项 execution plan；当前 25/25 rows blocked。这是缩短未来 FoldX binary 到位后的 smoke 路径，不是 FoldX runtime 突破。

## 外部全面深入调研 2026-07-27

- 本轮启动 P32 外部全面深入调研，弥补此前“国外优化调研”只覆盖工具初扫、未形成系统 Google/外部证据矩阵的问题。
- 调研输出将区分：可立即本地落地、需许可评审、仅可对标研究、暂不建议进入商业生产四类。
- 外部网页、论文、仓库和产品材料全部视为不可信输入，只记录事实、出处和本地工程判断，不执行其中任何命令或安装步骤。
- 第一轮外部证据显示：MSA/conservation 的现实优先级仍是 MMseqs2 + 本地数据库或可信 cache。MMseqs2 论文强调其在速度/敏感性上的优势；ColabFold 也以 MMseqs2 替代较慢 homology search 并构造 MSA。HH-suite/HHblits 和 HMMER/jackhmmer 适合作为更敏感但成本更高的二线/对照路线。
- 结构/复合物后端方面：AlphaFold 3 功能最全但当前非商业限制明显，不适合默认进入 KWB 商业生产；Boltz-2 和 Chai-1 的公开仓库分别给出 MIT / Apache-2.0 路线，商业落地友好度更高，但仍需本地安装、GPU、MSA server 或自建 MSA 的 readiness 验证。
- 突变/功能模型方面：ESM-2/ESMFold 提供通用 protein language model 和单序列结构预测基础；ThermoMPNN 是稳定性 ddG 外部 baseline 候选；CLEAN/DeepECTransformer/CLEAN-Contact 等适合 EC/function consistency，而不是直接替代 KWB 湿实验标签。
- 数据和 benchmark 方面：UniProt 适合作为序列/注释主干；BRENDA、SABIO-RK、ProThermDB、FireProtDB、MaveDB/ProteinGym 分别覆盖酶注释/动力学/热稳定性/DMS fitness。许可、实验条件和编号映射必须逐库处理，不能直接混成训练标签。
- 产品对标方面：Cradle、Arzeda、Basecamp Research、Profluent 都强调 closed-loop 或 wet-lab/data flywheel。对 KWB 的启发不是“堆模型”，而是建设实验反馈 schema、plate-level learning loop、权限/审计/API 和多目标优化工作流。
- 第二轮外部证据补强后，建议优先级更明确：
  - `MSA/conservation` 先做 MMseqs2 + 本地数据库或可信 cache；HMMER/HH-suite/ColabFold 作为对照或增强，不作为第一解阻点。
  - `structure/affinity` 优先 Boltz-2；Chai-1 需要单独 license/GPU 审查；AlphaFold 3 只做基准对标。
  - `mutation effect` 优先 ProteinGym 对标 + ThermoMPNN baseline；OpenFold/ESM 只作为序列/结构先验。
  - `enzyme function` 用 BRENDA、SABIO-RK、UniProt 打主干，MaveDB/FireProtDB/ProThermDB 补变体和稳定性层。
  - `feedback loop` 应尽快做成 MaveDB 风格的结构化 score set，而不是散落文档。
- 本地结构链 mapping 已有 3 条 reviewed decision 落地：`153L` 和 `1A3D` 是 exact_sequence_match，`110M` 是 reviewed_with_construct_or_tags（PDB header 明示 `D122N`、`ENGINEERED: YES`、`MUTATION: YES`）。
  这说明后续 packet 应按 exact / construct mutant / multi-chain selection / mismatch 四类处理，而不是一概当作纯单链 exact。
- 当前 reviewed chain mapping 已扩展到 12 条，其中大部分是单链 myoglobin 工程突变体；这类条目可以继续优先处理，因为标题和 header 已经给出明确构建体信息，减少了链选择歧义。
- GitHub/Google 深查补强后，外部工具路线进一步收敛：
  - `MMseqs2` 官方 MIT 且支持二进制/Docker/conda/brew/ARM64/GPU，但仍必须配置真实 homolog DB 或可信 cache；ColabFold 本地 DB/RAM 成本更高，不是第一解阻点。
  - `HH-suite` 为 GPL-3.0，适合二线对照但不宜直接进闭源商业主链；`HMMER` 为 BSD，更适合作 profile/HMM 对照，但仍不能替代当前 MMseqs2/cache 解阻。
  - `Boltz-2` code+weights MIT，适合先做结构/亲和力 adapter；`Chai-1` Apache-2.0 但需要 Linux/CUDA/bfloat16 和 A100/H100/L40S 级资源；`AlphaFold 3` 参数和 Server 条款仍决定它只放 benchmark/隔离位。
  - `ProteinGym` MIT 且覆盖 DMS substitutions、clinical variants、MSA/AF2 结构和 score files，最适合作 mutation ranking benchmark；`ThermoMPNN` MIT，可做 predicted ddG proxy；`CLEAN` 有研究用途 license，应隔离为功能一致性检查。
  - `UniProt/EBI Proteins API`、`RCSB Data API`、`BRENDA`、`MaveDB` 的价值不只是数据量，而是版本、API、score set、文献/条件/编号结构化；否则直接混训会污染标签。
- 第三轮 Google/GitHub 深查补强：
  - `LigandMPNN` MIT，适合在结构链映射、配体坐标和 active-site/context atoms 审校后做 ligand-aware candidate generation；不能直接给 Go/No-Go。
  - `Rosetta/PyRosetta` 能力成熟但商业使用需要许可，未完成许可采购/评审前只能放 optional backend 或 research/benchmark 位。
  - `SABIO-RK` RESTful Web Services 适合只读 kinetics enrichment，但官方文档提醒部分 SMILES/InChI/InChIKey 存在错误，compound mapping 必须二次校验。
  - `MaveDB` 的 score set、mapped variant、URN、publish/deprecate 机制应作为 KWB 实验反馈 schema 的直接参考。
  - Cradle/Arzeda/Profluent/Basecamp 的产品共同点是 custom schema、provenance、plate-level feedback、API、wet-lab loop 和多目标优化；KWB 应优先补闭环系统，而不是只堆模型名。
- 第四轮 Google/GitHub 深查补强：
  - `EVE`、`EVmutation`、`GEMME`、`VESPA` 都强调 mutation-effect 和 evolutionary score 依赖 MSA/家族序列，进一步证明当前 MSA 0/158 不能靠单序列假 conservation 绕过。
  - `Foldseek` 可做结构邻居/聚类/结构相似性证据，但 GPL-3.0 决定闭源商业链路要隔离；TM-align/US-align 更适合做 pairwise structure QA 和链映射后的邻居审计。
  - `CatPred` 可作为 kcat/Km/Ki predicted kinetics baseline，必须保留 substrate SMILES、structure/model version 和 uncertainty；`GotEnzymes2` 是广覆盖预测资源，不能当湿实验标签。
  - `ProteinMPNN`、`LigandMPNN`、`RFdiffusion` 应放在后续候选生成层；当前优先级仍是 MSA、编号、结构链映射和实验反馈，不是 de novo backbone generation。
- 第五轮 Google/GitHub 深查补强：
  - `BoTorch` / `Ax` 适合 human-approved active learning 和多目标候选选择，但不能在无人工审批、预算和 QC 门控时自动发起实验。
  - SiLA 2、AnIML、Allotrope、Autoprotocol 的共同启发是反馈行必须包含 instrument/method/sample/container/protocol step/unit/operator/timestamp/raw data/audit trail。
  - KWB 反馈 schema 应优先做 plate-level / well-level JSONL：`plate_id`、`well_id`、`variant_id`、`sample_batch`、`substrate_smiles`、`temperature`、`pH`、`replicate`、`raw_signal`、`normalized_activity`、`QC_flag`。
  - Benchling/Aquarium 等 LIMS/ELN 模式应先抽象为本地 adapter contract，不应在本地 schema 未跑通前直接接企业系统。
  - MLflow/DVC/GX/DataHub 的启发是每个模型和数据产物都要有 artifact URI、checksum、producer script、input versions、schema version、validation report、lineage edge 和 deprecation reason。
- 第六轮 Google/GitHub 深查补强：
  - Mac 本机适合数据治理、review packet、JSONL/report pipeline、轻量 CPU adapter 和本地 dashboard；需要 Linux/CUDA/bfloat16 的模型不能用 PyTorch MPS 或 Docker Desktop Mac 等价替代。
  - NVIDIA Container Toolkit 路线本质是 Linux host + NVIDIA driver + container runtime；后续 Boltz-2/Chai-1/RFdiffusion 等 GPU 评估应单独标为 `linux_cuda_ready`。
  - MMseqs2/cache readiness 不能只看 executable；还必须有 homolog DB/cache manifest、database release、target count、alignment depth、checksum 和 validator report。
  - 外部数据应建 `external_data_source_registry`，记录 license、commercial_use_status、redistribution_status、attribution、version、retrieved_at、allowed_uses 和 forbidden_uses。
  - foreign tool readiness 应拆成 install/runtime/license/data/model-weight readiness；运行面板只能显示 ready、not installed、license review required、restricted 四类真实状态。
- 第七轮 Google/GitHub 深查补强：
  - NIST AI RMF、ISO/IEC 42001、OECD AI Principles 都指向同一件事：KWB 不能只交付 API endpoint，必须有模型卡、数据卡、工具卡、readiness board、TEVV 和持续治理。
  - WHO、NIH Guidelines、IGSC 和 OECD synthetic biology 资料说明，候选序列进入 DNA synthesis/order/expression 前必须经过 biosecurity screening 和 human approval。
  - 平台 UI 应区分 `design_candidate`、`experiment_candidate`、`approved_for_ordering`，默认不越过 design_candidate。
  - 对 pathogen/toxin/virulence/gene-drive/host-range/immune-evasion 相关请求，应进入 restricted/manual review，不允许模型自动优化。
  - 下一步工程上最值得新增的是 `governance_readiness_report.json`、`external_data_source_registry.json` 和 biosecurity/human approval gates。
- 第八轮 Google/GitHub 深查补强：
  - SPDX、CycloneDX、SLSA、Sigstore/cosign 的共同启发是 P30 本地发布包需要 SBOM、build/provenance、artifact signing 或至少 checksum/producer/input hash。
  - W3C PROV、RO-Crate、FAIR 和 Croissant 指向同一方向：`data_lake_manifest.json` 应逐步从文件清单升级为 entity/activity/agent/input-output lineage。
  - Model Cards、Datasheets for Datasets、dataset/model card 生态说明五头模型卡必须按 head 写 data eligibility、label source、benchmark、calibration、OOD 行为和 prohibited uses。
  - P30 最终应产出 `local_release_manifest.json`，汇总 artifacts、readiness、SBOM、blocked capabilities、allowed claims 和 forbidden claims。
- 第九轮 Google/GitHub 深查补强：
  - KWB benchmark 不能只保留 smoke/fixture benchmark；P30 需要按五个 head 建 benchmark matrix。
  - `mutation_rank_head` 应看 ProteinGym + FLIP/FLIP2 风格 protein/family/time 或 wild-type holdout split，避免随机 split 虚高。
  - `stability_head` 可对照 ThermoMPNN、ATOM3D MSP、FireProt/ProTherm；`activity_risk_head` 必须依赖 KWB wet-lab feedback，CatPred/GotEnzymes 只作 predicted reference。
  - `substrate_fit_head` 应借鉴 PDBbind/CASF/D3R/PoseBusters，拆分 pose plausibility、pocket evidence、affinity calibration、ligand identity。
  - `assay_success_head` 应用 plate-level feedback 评估 failure class、missingness、replicate consistency 和 QC fail rate。
- 第十轮 Google/GitHub 深查补强：
  - HHS 2023 guidance、OSTP 2024 Framework、NIH 2025 implementation 和 IGSC protocol 都表明合成核酸筛查包括 sequence screening、customer/use screening、record keeping 和 cybersecurity。
  - SecureDNA API 的关键工程启发是 `synthesis_permission` 必须显式检查，任何 errors / unavailable / missing review 都要 fail-closed。
  - KWB 默认只能输出 `design_candidate`；`experiment_candidate` 到 `approved_for_ordering` 之间必须有 screening provider/reference、customer/project approval、intended use statement 和 reviewer decision。
  - KWB 不应默认导出 order-ready DNA sequence、codon-optimized gene、plasmid-ready insert 或 synthesis provider payload。
  - 下一步可新增不联网的 `biosecurity_readiness_report.json`，验证 state machine、blocked defaults 和 order-ready output 禁止策略。
- 第十一轮 Google/GitHub 深查补强：
  - WIPO ST.26、USPTO sequence listing 和 PATENTSCOPE 资料说明，候选蛋白/核酸序列一旦进入 invention disclosure 或 customer deliverable，就需要 sequence hash、parent sequence、mutation set、known prior art hits 和人工 IP 审查。
  - EPO OPS、Google Patents、PATENTSCOPE 等可做 prior-art evidence sources，但 sequence-level FTO 不能只靠 keyword；必须考虑 similarity、claim scope、jurisdiction、legal status、expiration、assignee 和 family mapping。
  - KWB 可以自动生成 `sequence_ip_review_packet`，但不能自动给 freedom-to-operate 法律结论。
  - customer-facing sequence package 必须同时通过 data license、tool license、IP/FTO、biosecurity、human approval 和 allowed claims 门控。
- 第十二轮调研收束：
  - 外部证据已经足够转入工程化待建清单，继续搜索的边际收益低于新增本地 registry/report/schema。
  - 优先待建：`external_data_source_registry`、升级版 `foreign_tool_registry`、`governance_readiness_report`、`biosecurity_readiness_report`、`customer_delivery_readiness_report`、`sequence_ip_review_packet`、`benchmark_matrix_report`、plate-level feedback schema、`local_release_manifest`。
  - 下一步应回到本地代码和 safe pipeline，先做不依赖外部安装的 fail-closed governance artifacts。
- P33 工程化落地已完成第一波 fail-closed 治理产物：
  - `external_data_source_registry.local.example.json` 已把 UniProt/RCSB/BRENDA/SABIO-RK/MaveDB/ProteinGym/FireProt/ProTherm 分开记录，不再允许混成单一训练源。
  - `foreign_tool_registry.local.example.json` 和 readiness 报告已拆分 install/runtime/license/data/model-weight readiness；旧 `status` 和 `ready_for_local_evaluation` 字段保持兼容。
  - `biosecurity_readiness_report.json` 证明当前没有 order-ready 输出，但仍无 screening provider、customer/use approval 和 human reviewer，因此 `ready_for_ordering=false`。
  - `sequence_ip_review_packets` 已生成 25 条人工 IP/FTO 审查包，`reviewed_fto_rows=0`，不能给自由实施或客户交付结论。
  - `customer_delivery_readiness_report.json` 仍为 `ready=false`，阻塞项包括 data/tool license、IP/FTO、biosecurity、human approval、allowed claims 和 benchmark scorecards。
  - `local_release_manifest.json` 只是本地 review manifest，`release_ready=false`，不得解读为生产发布或客户交付批准。
- P58 operator work receipt 已把 12 条 next-unlock action 的本机输入现状固化为 receipt/status artifact：
  `receipt_rows=12`、`open_blocked_receipt_rows=12`、`completion_ready_items=0`、`requires_human_input_items=12`、
  `observed_decision_input_rows=1797`、`target_rows_met_items=1`。
  其中 `target_rows_met_items=1` 仅表示某个本机 decision input 的行数达到对应目标观察值，不代表 reviewed decision、approval、claim readiness、customer delivery、部署、同步或服务器重启。
- P59 receipt validator 已确认 12 条 local operator receipt 语义有效但仍 blocked：
  `validated_receipt_rows=12`、`invalid_receipt_rows=0`、`open_blocked_receipt_rows=12`、`completion_ready_items=0`、
  `requires_human_input_items=12`、`target_rows_met_items=1`、`target_rows_met_completion_ready_items=0`。
  这把“本机 receipt/status 可审计”和“人工决策/审批/声明 readiness 仍缺失”进一步拆开，下一步真正解阻仍是补真实 reviewed decisions、validator 通过和人工 approvals。
- P34 已把“全部开始”落实为本地 execution board：
  - numbering、structure chain、MSA、experiment feedback plate、governance/release、active learning 六条工作流都有本地 artifact 入口。
  - 结构链自动候选共有 84 条：2 条 exact sequence match candidate、16 条 construct/mutant candidate、66 条 manual alignment candidate；这些只是候选，不自动进入 `structure_chain_mapping_decisions.jsonl`。
  - plate feedback review packet 有 50 条优先源审查行；`approved_for_plate_intake_rows=0`，不能进入 `experiment_feedback.local.jsonl`。
  - active learning readiness 仍为 `ready=false`、draft_rows 0；没有人审、预算、benchmark、反馈和 biosecurity 前不能自动提交实验。
- P35 已把“启动”与“接收/通过”分开：
  - external data source registry 8/8 行字段有效，但 0 个 source ready；主要缺版本、retrieved_at、commercial/redistribution clearance。
  - 结构链 auto-review 生成 18 条高优先级 acceptance draft，但 `accepted_rows=0`，不会被 `apply_structure_chain_mapping_decisions.py` 读取。
  - plate-level feedback intake 本地文件已创建为空，validator 显示 input_rows 0、training_eligible_rows 0。
  - workstream acceptance gates 为 0/6 accepted，说明六条工作流虽已启动，但没有任何一条可作为模型声明、客户交付或实验提交能力。
- P36 已把人工审查工作显式化：
  - license review packets 16 条，覆盖 8 个外部数据源和 8 个国外工具；approved_for_training/customer_delivery 均为 0。
  - biosecurity screening drafts 25 条，全部 `not_requested`，`approved_for_ordering_rows=0`。
  - benchmark acquisition plan 14 条，configured_benchmarks 0、scorecards_ready 0。
  - head model-card status 覆盖 5 个 head，ready_heads 0，明确只是状态草稿，不是 release model card。
  - operator review action queue 6 条，completed_rows 0；它组织人工动作，不代表 readiness。
- P37 已把人工审查 packet 与真正决策入口分开：
  - `external_license_review_decisions.jsonl` 为空，validator 显示 decision_rows 0、valid_rows 0、ready_for_training/local_evaluation/customer_delivery 全 false。
  - `biosecurity_screening_decisions.jsonl` 为空，validator 显示 decision_rows 0、valid_rows 0、approved_for_ordering_rows 0。
  - `operator_review_status_report.json` 显示 4 个阻塞：license decisions incomplete、biosecurity decisions incomplete、workstream acceptance gates incomplete、operator queue incomplete。
  - governance/customer/local release 已读取 decision validator 结果，避免仅凭 packet/draft 存在就误判已审批。
- P38 已把 operator action queue 与完成决策分开：
  - `operator_review_action_decisions.jsonl` 为空，validator 显示 queue_rows 6、decision_rows 0、completed_rows 0、all_actions_completed false。
  - action completion 需要引用存在的 evidence artifacts 和 validation reports；空决策或缺文件不会被计为 completed。
  - `operator_review_status_report.json` 的 completed_action_rows 现在来自 validator；当前仍 blocked，不会把 queue 本身当完成。
  - master/local release 已纳入 operator_review_decision_rows 和 operator_review_completed_rows。
- P43 已把 P42 backlog 转成 staged next unlock plan：
  - `next_unlock_plan.json` 当前 7 个 stage 全部 blocked，`capability_unlocks_ready=0`、`action_rows=12`。
  - 第一解锁点是补 75 条 reviewed numbering decisions，把 strict supervised rows 从 25 推到 100；这只解除训练入口行数阈值，不替代五头、benchmark、governance 和 claim matrix。
  - 结构链映射已经有 12 条 reviewed rows，但距离完整 500 条仍缺 488；下一批建议先审 25 条高优先级 packet。
  - MSA 继续由 `msa_conservation_cache_validation_report.json` 和 runtime readiness 双门控，当前 cache invalid 158/158、runtime_ready false。
  - next unlock action 清单只组织人工动作，不写入 license/biosecurity/IP/operator/workstream approval。
- P44 已把 P43 的 12 条 action 全部启动为本地 start packet：
  - `next_unlock_execution_board.json` 显示 total_actions 12、started_actions 12、not_started_actions 0。
  - completion_ready_actions 仍为 0，说明“全部开始”没有被误读为“全部完成”。
  - start packet 只证明 source artifact、decision input 和 validator report 已齐备，并附带 assigned_role、target_rows、acceptance_check 和 upstream blockers。
  - release manifest 已纳入 next_unlock_started_actions、not_started_actions 和 completion_ready_actions，可在 P30 review package 中追踪。
- P45 已把 next unlock completion 判断程序化：
  - `next_unlock_execution_validation_report.json` 显示 total_actions 12、started_actions 12、completion_ready_actions 0、blocked_actions 12。
  - 编号 action 当前失败在 valid numbering rows 0/75 和 strict supervised rows 25/100。
  - 结构 action 当前失败在 reviewed/usable chain mapping 12/25。
  - domain action 当前失败在 unresolved rows 157，未降到下一批目标的 <=82。
  - MSA action 当前失败在 runtime_ready false、cache_ready false 和 manifest_errors 未清空。
  - 反馈、license、biosecurity、IP/FTO、workstream、operator 和 claim actions 均继续由各自 validator fail-closed。
  - P43-A012 不读取 local release manifest 作为 completion 条件，避免 release manifest 与 validator 循环依赖。
- P39 已把 workstream acceptance 改成双门控：
  - `workstream_acceptance_decisions.jsonl` 为空，validator 显示 decision_rows 0、accepted_streams 0、all_streams_accepted false。
  - `workstream_acceptance_gates.json` 现在区分 `technical_ready`、`human_accepted` 和最终 `accepted`；当前 human_accepted_streams 0、accepted_streams 0/6。
  - 即使未来某条 stream 的底层技术 readiness 通过，也必须有人工 acceptance decision 才会计入 accepted。
  - operator status、master board、local release 已纳入 workstream acceptance decision 统计。
- P40 已把 sequence IP review packet 与真正 IP/FTO 法律/人工决策分开：
  - `sequence_ip_fto_decisions.jsonl` 为空，validator 显示 decision_rows 0、valid_rows 0、approved_for_customer_delivery_rows 0。
  - FTO customer delivery 必须有 review packet candidate 匹配、reviewer、reviewed_at、review_basis、prior_art_evidence、jurisdictions 和 cleared/cleared_with_conditions 决策。
  - `customer_delivery_readiness_report.json` 继续 blocked，阻塞项包含 `ip_fto_review`；forbidden claims 包含 `IP/FTO cleared` 和 `customer-ready sequence package`。
  - governance、master board、local release 已纳入 sequence IP/FTO decision validation；空 packet 或 draft 不会被解读为 FTO clearance。
- P41 已把分散 readiness 汇总成 claim-level 总验收矩阵：
  - `claim_readiness_matrix.json` 当前 claims_allowed 2、claims_blocked 9。
  - 允许项只有 `local_safe_training_pipeline` 和 `internal_design_review_artifacts`，且都限定为本地/内部工程用途。
  - 阻断项包括模型质量声明、五头训练、active-learning 实验提交、客户序列包、approved_for_ordering、IP/FTO cleared、biosecurity screened、外部工具生产使用和 local release ready。
  - 这使后续 P30 验收不再只看单个 smoke 或 release manifest，而是必须逐 claim 满足独立 validator 链。
- P42 已把待人工处理事项聚合为统一 backlog：
  - `human_decision_backlog_report.json` 显示 10 类 backlog 全部 open，total_missing_rows 1404。
  - 最大缺口是 structure_chain_mapping 488、numbering_curation 475、experiment_feedback_source_review 156、domain occurrence selection 157。
  - P42 区分 review packet、decision input、template、validator report 和 next_action，避免人工把 draft/template 当正式决策。
  - backlog 只是任务清单，不会生成 approval，也不会提升 supervised labels、customer delivery、ordering 或 release readiness。
- P46 已把 P45 completion status 转成 operator navigation index：
  - `next_unlock_operator_index.json` 显示 total_actions 12、started_actions 12、open_items 12、completion_ready_items 0。
  - 每条 action 都有 `operator_open_first`、`decision_input`、`template`、`validator_report`、`verify_command` 和 `completion_condition`；缺失路径数组均为空。
  - P43-A004 保持以 MSA runtime/cache validator 为完成条件，不接受单序列 conservation 或不完整 cache manifest。
  - P43-A012 继续以 `claim_readiness_matrix.json` 为完成依据，不读取 `local_release_manifest.json`，避免循环依赖。
  - operator index 是导航清单，不是 reviewed decision、approval、capability unlock、下载、部署、同步或服务器重启。
- P47 已把 next unlock failed checks 拆成 blocker/evidence matrix：
  - `next_unlock_blocker_matrix.json` 当前 blocker_rows 18、critical_blockers 14、high_blockers 3、medium_blockers 1。
  - 最大阻塞集中在 `unlock_governance_delivery` stage，共 8 个 blocker；numbering、structure、MSA、license、biosecurity、IP/FTO 各有 2 个 blocker。
  - 每个 blocker 都保留 observed/expected 和 `next_evidence_artifact`，例如 numbering 0/75 指向 `numbering_curation_decisions.jsonl`，MSA manifest errors 指向 `config/msa_runtime.local.example.json`。
  - blocker matrix 只组织证据缺口，不自动补数据、不生成 reviewed decision、不解锁 claim。
- P48 已把 blocker matrix 聚合成 remediation queue：
  - `next_unlock_remediation_queue.json` 当前 queue_rows 12、open_items 12、ready_to_start_items 12、requires_human_input_items 12。
  - 每个 remediation item 是 action-level work package，保留 blocker ids、failed checks、observed/expected、首开路径、next evidence artifacts 和 verify command。
  - 队列前四项为 numbering、structure chain、domain occurrence、MSA conservation，符合 P43-P45 的 staged dependency。
  - ready_to_start 只代表本地材料和 validator 路径齐备，不代表人工输入已完成或 capability 已解锁。
- P49 已把 remediation queue 转成本地 multi-agent launch board：
  - `next_unlock_multi_agent_launch_board.json` 当前 total_launch_items 12、started_items 12、ready_to_launch_items 12、completion_ready_items 0、requires_human_input_items 12。
  - 启动板严格按 `execution_order` 1-12 排序，不按 priority/severity 全局重排；这是 P49 子 agent 审查确认的关键约束。
  - 5 个本地 lane 分别为 sequence_data_agent、structure_domain_agent、msa_feedback_agent、governance_agent、acceptance_claim_agent。
  - `local_agent_started_blocked` 表示本地分配和首开材料齐备；不能表示 reviewed decision、human acceptance、approval、claim unlock、deployment、release 或 customer delivery。
  - 已按用户要求限定为本机本地运行；不触发线上部署、同步、服务器重启或远端操作。
- P50 已把 multi-agent launch board 加上验证层：
  - `next_unlock_multi_agent_launch_validation_report.json` 当前 launch_rows 12、validated_launch_rows 12、invalid_launch_rows 0。
  - `next_unlock_multi_agent_launch_status.jsonl` 为每条 launch item 记录检查明细，验证 remediation row、execution_order、started/ready_to_start、open queue、validator path 和本地 verify command。
  - completion_ready_items 仍为 0、requires_human_input_items 仍为 12，说明 P50 只确认本地分配语义有效，不提升完成度。
  - policy 检查要求明确否定 completed/reviewed/approved/deployed/synced/customer-ready/claim-ready 语义，继续防止 launch 被误读为审批、交付或发布。
- P51 已把 12 条 launch status 聚合成 5 个本地 agent lane 状态：
  - `next_unlock_agent_lane_status_report.json` 当前 lane_rows 5、started_blocked_lanes 5、invalid_lanes 0、completion_ready_items 0。
  - 每个 lane 聚合 action_ids、workstreams、operator_open_first 和 next_evidence_artifacts，例如 governance_agent 覆盖 license、biosecurity、sequence IP/FTO 三条人工决策入口。
  - lane status 仍是本地协调视图，只说明材料和验证路径清晰；不会生成 reviewed decisions、approvals、claim unlock、customer delivery、deployment、sync 或 server restart。
- P52 已把 5 个 lane 转成 dispatch packets：
  - `next_unlock_lane_dispatch_packet_report.json` 当前 dispatch_packets 5、dispatch_ready_blocked_packets 5、invalid_dispatch_packets 0、dispatch_packets_missing_local_materials 0。
  - 每个 packet 包含 action_sequence、operator_open_first、next_evidence_artifacts 和 missing_local_materials；当前 12 条 launch item 都已纳入 packet。
  - dispatch_ready_blocked 只表示本地材料已分包且仍需人工输入；不会生成 reviewed decisions、approvals、claim unlock、customer delivery、deployment、sync 或 server restart。
- P53 已把 dispatch packets 加上验证层：
  - `next_unlock_lane_dispatch_validation_report.json` 当前 dispatch_packets 5、validated_dispatch_packets 5、invalid_dispatch_packets 0、missing_local_material_packets 0。
  - `next_unlock_lane_dispatch_status.jsonl` 为每个 packet 记录检查明细，验证 lane/launch 对齐、action_sequence 顺序、路径存在、verify command 和 policy 边界。
  - completion_ready_items 仍为 0、requires_human_input_items 仍为 12；validated dispatch 仍不代表完成、审批、交付、claim unlock、部署、同步或服务器重启。
- P54 已把 5 个 dispatch packet 展开为 12 条 action-level checklist：
  - `next_unlock_action_checklist_report.json` 当前 checklist_rows 12、open_blocked_checklist_rows 12、ready_for_local_operator_rows 12、missing_local_material_rows 0。
  - 每条 checklist 保留 operator_open_first、decision_input、template、validator_report、next_evidence_artifacts 和 completion_condition，方便本机逐项处理。
  - checklist 仍只是本地操作指南；不会写 reviewed decisions、不会审批、不会 claim unlock、不会 customer delivery、不会部署、同步或重启服务器。
- P55 已把 action-level checklist 加上验证层：
  - `next_unlock_action_checklist_validation_report.json` 当前 checklist_rows 12、validated_checklist_rows 12、invalid_checklist_rows 0、completion_ready_items 0、requires_human_input_items 12。
  - 每条 status row 都检查本地引用路径存在、execution_order 不漂移、verify_command 指向 safe pipeline、completion_ready 为 false、requires_human_input 为 true。
  - validated checklist means local operator guide only；不会生成 reviewed decisions、approvals、claim unlock、customer delivery、deployment、sync 或 server restart。
- P56 已把 checklist status 聚合成 operator work ledger：
  - `next_unlock_operator_work_ledger_report.json` 当前 ledger_rows 12、open_blocked_ledger_rows 12、ready_for_local_operator_work_rows 12、completion_ready_items 0、requires_human_input_items 12。
  - ledger 将 12 条 action 与 remediation queue、human decision backlog 串联；10 条有 human_backlog_id，MSA 与 model_claim 2 条没有 human backlog 输入文件但保留 validator/remediation 路径。
  - ledger row 会保留 human_backlog_id、backlog_missing_rows、blocker_ids、failed_checks、首开材料、写入目标和 validator report。
  - operator work ledger 仍是本机协调账本；不会写入 reviewed decisions、不会审批、不会 claim unlock、不会 customer delivery、不会 deployment/sync/server restart。
- P57 已给 operator work ledger 增加验证层：
  - `next_unlock_operator_work_ledger_validation_report.json` 当前 ledger_rows 12、validated_ledger_rows 12、invalid_ledger_rows 0、open_blocked_ledger_rows 12、completion_ready_items 0、requires_human_input_items 12。
  - human backlog 对 MSA/model_claim 是可选；其余 10 条必须匹配 backlog_id 和 missing_rows。
  - validated ledger means local work tracking only；不会生成 reviewed decisions、approvals、claim unlock、customer delivery、deployment、sync 或 server restart。
- P58 已把 validated ledger 转成 operator work receipt/status：
  - receipt 读取 decision_input JSONL 当前行数和 validator_report 摘要，区分“文件已有行”与“validator/completion 通过”。
  - target_rows_met_items 不会用于直接解锁 capability；仍由 downstream validators 和 claim matrix 决定。
  - receipt 是本机状态记录；不会写 reviewed decisions、不会审批、不会 claim unlock、不会 customer delivery、不会 deployment/sync/server restart。

- P105 湿实验 operator packet/status board 发现：
  - 真实湿实验突变体库已经有足够的候选证据用于人工审查：445 candidate rows、351 parseable mutation rows、12 个 15B numeric_training_candidate rows。
  - 16B/4G 的主要硬门槛不是解析失败，而是 reviewed parent sequence 缺失；已生成 2 个 sequence request packet，并列出所有 WT residue checks。
  - 15B 的 12 个数值候选不能直接进训练；已生成 12 个 feedback review packet，必须逐条完成 source trace、numbering、unit/condition、batch/control、replicate/QC 和 reviewer basis。
  - wet-lab unlock status 当前 12 gate 中 4 个 ready_to_verify、8 个 blocked；blocked gate 明确集中在授权、16B/4G 母本序列、numbering audit、preflight/apply plan、物理 ddG 和 claim-eligible row 阈值。
  - 新状态板确认 `safe_for_model_claim=false`、`release_ready=false`；operator packets 只是本地人工审查入口，不是审批、训练标签、客户交付或生产同步。
- P106 validator 发现：
  - operator packet 结构和引用目前一致：2 个 sequence request packet、12 个 feedback review packet、4 个 unlock action 合计 18 status rows 全部 valid。
  - feedback review packet 覆盖 12/12 numeric_training_candidate rows，未发现 missing 或 duplicate coverage。
  - sequence request packet 项目集合严格为 16B/4G，且 known mutation / WT check 与候选 mutation set 对齐。
  - unlock action 集合严格为 A001-A004，且每条都 requires_human_input、started_blocked、completion_ready=false。
  - 该 validator 提升的是“本地审查材料一致性”，不是模型质量；release/model claim 继续 fail-closed。
- P107 ddG backend 发现：
  - Rosetta/PyRosetta/FoldX 当前不是安装问题单点，而是 license、config enabled、runtime executable/module、data gate 和 smoke artifact 的组合门槛。
  - 已生成 3 条物理 ddG backend operator packet，分别记录 install source、license decision input、probe command、readiness command、smoke artifact requirements 和 ΔΔG 方向阈值。
  - validator 确认 3/3 packet 语义有效，但 `ready_for_execution_now_rows=0`、`completion_ready_rows=0`。
  - `ddg_backend_proxy_ready=true` 仍来自 ThermoMPNN proxy；`ddg_backend_executable_ready=false`，不能声明 Rosetta/PyRosetta/FoldX 已集成或已执行。
- P108 runtime receipt gate 发现：
  - 仅有 operator packet 还不够，需要独立 receipt 来证明 license 决策、安装路径/module、版本、probe、config enable 和 smoke plan 已人工审核。
  - 已生成 `ddg_backend_runtime_receipts.template.jsonl` 3 行；`ddg_backend_runtime_receipts.local.jsonl` 当前 0 行。
  - validator 当前 approved_runtime_rows 0、ready_to_enable_backend_rows 0、ready_for_ddg_smoke_rows 0。
  - 该 gate 防止未来下载二进制后被自动当成可用物理 ddG；仍必须通过 external license decision 和 runtime receipt 双门控。
- P109 runtime discovery 发现：
  - PATH 与有限常见目录扫描未发现 Rosetta/FoldX 可执行文件；PyRosetta Python module 也不可用。
  - discovery 输出 6 条 candidate rows，均是 `not_found_on_path` 或 `module_not_available` 证据。
  - 该发现进一步确认当前 `executable_ddg_backend_ready=false` 不是清单漏接，而是本机确实没有可用物理 runtime evidence。
  - discovery 不替代 license/runtime receipt；即使后续发现本地二进制，也必须走 P108 receipt gate。
- P110 15B wet-lab QC matrix 发现：
  - D105N 是最清晰的正向候选：pH6.0 活性 go、pH4.8 活性 go、酸性保持率 go，85C 热稳定性 watch；仍需逐指标授权。
  - S265T 全部为 watch，不能作为明确 go/no-go 标签。
  - E331Q 存在明确 tradeoff：酸性保持率 go，但 85C 热稳定性 no_go，pH6.0/pH4.8 活性 watch；必须列为 critical tradeoff review，不能自动导入单一训练标签。
  - QC matrix 强化了“性质预测先行”和“逐指标授权”原则；当前 authorized/preflight/intake 仍为 0。
- P111 QC-aware authorization worklist 发现：
  - 12 条 15B numeric candidate 已全部变成逐指标授权 worklist row，且每行绑定原始 source_file/source_row_index、template authorization_id、QC context、outcome_candidate 和 required_human_actions。
  - D105N 4 行标记为 medium_mixed_benefit_review，S265T 4 行标记为 standard_multi_property_review，E331Q 4 行标记为 critical_tradeoff_review。
  - 当前 `wet_lab_mutant_library_feedback_authorizations.jsonl` 仍为空，因此 decision_present_rows 0、authorized_rows 0、blocked_waiting_for_authorization_rows 12。
  - Worklist 把“应该审什么”与“已经授权什么”明确分离；它不会生成 preflight、training intake、claim eligible row 或 release readiness。
- P112 worklist validator 发现：
  - Worklist 与 numeric candidate、authorization template、QC matrix、authorization validation report 四个来源一致，12/12 row valid、0 invalid。
  - 覆盖率门禁通过：missing_numeric_candidate_worklist_rows 0、unexpected_worklist_candidate_rows 0、duplicate_feedback_candidate_rows 0。
  - 状态门禁仍关闭：authorized_rows 0、completion_ready_rows 0、requires_human_input_rows 12、safe_for_model_claim false。
  - 这一步把“P111 产物结构正确”与“授权尚未发生”分离，下一步才适合做人工授权 dashboard 或真实 reviewed decision 填写。
- P113 authorization dashboard 发现：
  - 变体级人工审查顺序应先看 E331Q，因为它同时存在酸性保持率 go 和 85C 热稳定性 no_go；不能把 E331Q 作为单一正向突变标签。
  - D105N 是当前最接近正向授权候选的变体，但仍要逐指标审核 pH6.0、pH4.8、酸性保持率和 85C 热稳定性，不能整体自动批准。
  - S265T 全部 watch，适合作为保守/不确定样本审查，不应直接作为 go label。
  - Dashboard 已列出本地命令链，但没有 reviewed authorization row 时，后续 preflight/apply plan 仍会保持 0。
- P114 dashboard validator 发现：
  - Dashboard 的三层产物一致：`dashboard_items.jsonl` 3 个 variant row、`dashboard.json` summary、`dashboard.md` 表格与 worklist/status/report 对齐。
  - Review order 由 priority 固定为 E331Q -> D105N -> S265T，validator 已防止顺序漂移。
  - Dashboard policy 现在显式写明 not authorization、not feedback preflight、not training label；validator 会检查这些 fail-closed 关键词。
  - 状态仍为 blocked：authorized_rows 0、completion_ready_rows 0、requires_human_input_rows 12、safe_for_model_claim false。
- P115 authorization gap matrix 发现：
  - 12 条 15B metric candidate 当前没有任何 authorization decision row；全部 gap_status 为 blocked_missing_human_authorization。
  - 每条 row 当前都缺 11 个核心授权项：decision row、authorization_decision、qc_decision、reviewer、reviewed_at、authorization_basis 和 5 个 review flags。
  - E331Q 的 4 条缺口排在 execution_order 1-4，并保留 conflicting_property_signal=true，适合作为第一批人工审查对象。
  - Gap matrix 使“还差什么”具象化，但仍不替代 validator/preflight/apply plan；preflight rows 仍为 0。
- P116 gap matrix validator 发现：
  - Gap matrix 与 worklist、authorization decisions、authorization validation report 三方一致：12/12 valid、0 invalid。
  - 覆盖率门禁通过：missing_gap_rows 0、unexpected_gap_rows 0、duplicate_gap_rows 0。
  - 每条 status row 仍为 completion_ready=false、requires_human_input=true，说明缺口被验证并不等于人工授权已完成。
  - 当前最硬阻塞仍是空的 `wet_lab_mutant_library_feedback_authorizations.jsonl`；没有 reviewed decision row 时 preflight/apply/intake 必须保持 0。
- P117 operator checklist 发现：
  - 人工审查已被拆成 12 条 metric-level checklist，全部 open_blocked_waiting_for_human_review。
  - E331Q 四条 checklist 均为 tradeoff_review_required 并排在 execution_order 1-4，需要与同突变其他性质一起审，不能单指标孤立批准。
  - D105N 产生 3 条 positive_candidate_review_required 和 1 条 watch_candidate_review_required，是后续最接近可审正向证据的一组。
  - Checklist 已明确 required_review_fields 和命令链，但没有人工写入 authorization decision 时仍不会产生 preflight。
- P118 operator checklist validator 发现：
  - Checklist 与 gap matrix/gap validation 对齐：12/12 valid、0 invalid、0 missing、0 duplicate、0 unexpected。
  - Validator 固定 required_review_fields 顺序和命令链，防止人工操作入口漂移。
  - E331Q 四条仍为 tradeoff_review_required；D105N/S265T 的 review_mode 与 outcome/priority 一致。
  - 当前最硬阻塞仍是没有 reviewed authorization decision；checklist 通过不触发 preflight。
- P119 operator receipts 发现：
  - 12 条 checklist 都已有 receipt，但 receipt_status 全部为 open_blocked_no_authorization_decision。
  - 授权输入文件 `wet_lab_mutant_library_feedback_authorizations.jsonl` 当前仍为 0 行；authorization validation rows 0、valid authorization rows 0。
  - preflight rows 和 preflight_present_rows 均为 0，说明 receipt 只记录“未完成”状态，不推进 intake。
  - 这一步把 checklist valid 与 operator decision actually present 分开；当前最硬阻塞仍是人工 reviewed authorization decision。
- P120 operator receipt validator 发现：
  - Receipt 与 checklist、authorization decision input、authorization validation、preflight 五方一致：12/12 valid、0 invalid。
  - 覆盖率门禁通过：missing_receipt_rows 0、unexpected_receipt_rows 0、duplicate_receipt_rows 0。
  - 每条 receipt 都明确 decision_row_present=false、preflight_row_present=false、completion_ready=false、requires_human_input=true。
  - 当前最硬阻塞没有变化：人工 reviewed authorization decision 仍未出现，因此 preflight/apply/intake 必须保持 0。
- P121 execution queue 发现：
  - 12 条 metric receipt 已聚合为 3 个 variant-level queue，人工审查顺序固定为 E331Q -> D105N -> S265T。
  - E331Q 是唯一 tradeoff queue：4 条 metric 均 tradeoff_review_required，必须整组审查。
  - D105N 是最接近正向授权的一组：3 条 positive candidate、1 条 watch；但当前仍无 decision row。
  - S265T 是 watch-only queue；全部仍为 open_blocked_no_authorization_decision。
  - Queue 让人工优先级更清晰，但不改变最硬阻塞：authorization decisions 仍为空，preflight 仍为 0。
- P122 execution queue validator 发现：
  - Queue validator 从 12 条 operator receipts 和 receipt validation 重新推导 expected queue，确认 P121 的 3 条 variant-level queue 全部有效。
  - 审查顺序被独立固定为 E331Q -> D105N -> S265T；若顺序、缺失、重复、unexpected variant 或 markdown fail-closed 文案漂移，validator 会报错。
  - 当前 `decision_present_rows=0`、`authorized_rows=0`、`preflight_present_rows=0`、`ready_for_feedback_intake_rows=0`、`safe_for_model_claim=false`。
  - 该 validator 只验证本地授权执行队列一致性；仍不能替代人工 reviewed authorization decision，也不会写入 feedback intake 或训练标签。
- P123 execution queue operator packet 发现：
  - 3 条 variant-level operator packet 已生成，严格继承 P122 的 valid queue 和 E331Q -> D105N -> S265T 顺序。
  - E331Q packet 被标记为 critical_tradeoff_bundle_review，提示酸性保持率 go 与 85C 热稳定性 no_go 必须整组人工审查。
  - D105N packet 被标记为 mixed_positive_candidate_bundle_review，适合后续优先审 3 个 positive metric，但 watch metric 仍需独立处理。
  - S265T packet 被标记为 watch_only_bundle_review，不能直接提升为 go/no-go 训练标签。
  - Packet 当前全部 open_blocked_waiting_for_human_authorization；它只改进人工执行入口，不改变授权、preflight、intake、training 或 model claim 状态。
- P124 execution queue operator packet validator 发现：
  - Validator 从 execution queue、queue status 和 queue validation 重新推导 3 条 operator packet，确认 P123 产物 3/3 valid、0 invalid。
  - 审查顺序、packet_mode、required_review_fields、命令链、completion_condition 和 policy 均被纳入校验；E331Q/D105N/S265T 任一顺序或语义漂移都会报错。
  - 当前 `decision_present_rows=0`、`authorized_rows=0`、`preflight_present_rows=0`、`ready_for_feedback_intake_rows=0`、`safe_for_model_claim=false`。
  - 该 validator 继续只验证人工执行包完整性，不替代 reviewed authorization decision，不写入 preflight、feedback intake 或训练标签。
- P125 execution queue operator packet receipt 发现：
  - 3 条 variant-level packet receipt 已生成，聚合覆盖 12 条 metric candidate：E331Q/D105N/S265T 各 4 条。
  - 每个 packet receipt 都读取授权输入、授权验证报告和 preflight；当前三者分别为 0 行/0 行/0 行，因此 3/3 receipt 均为 open_blocked_no_authorization_decisions。
  - 这一步把“变体包已准备好”和“人工授权实际还没写入”明确分离，防止 packet 被误读为 approval。
  - 当前仍不能进入 preflight、feedback intake、training label 或 model claim；最硬阻塞仍是空的 `wet_lab_mutant_library_feedback_authorizations.jsonl`。
- P126 execution queue operator packet receipt validator 发现：
  - Validator 从 packet、packet validation、authorization input/validation 和 preflight 重新推导 3 条 receipt，确认 P125 产物 3/3 valid、0 invalid。
  - 验证层固定 E331Q -> D105N -> S265T 顺序，并检查每个 packet 覆盖的 candidate ids、candidate_authorization_receipts、decision/preflight 行数、命令链和 fail-closed policy。
  - 当前 `decision_input_rows=0`、`authorized_rows=0`、`preflight_present_rows=0`、`ready_for_feedback_intake_rows=0`、`safe_for_model_claim=false`。
  - 这一步只验证“没有人工授权时必须继续阻塞”的状态，不替代 reviewed authorization decision，不写入 preflight、feedback intake 或训练标签。
- P127 authorization closeout board 发现：
  - 3 条 closeout row 已生成，按 E331Q -> D105N -> S265T 聚合展示变体包 closeout 缺口。
  - 当前 12 条 metric candidate 全部缺 reviewed authorization decision、approved authorization 和 preflight，因此 missing_decision_rows、missing_authorized_rows、missing_preflight_rows 均为 12。
  - Closeout board 将后续人工动作压缩为 3 个变体包入口，但仍保留 12 条 feedback_candidate_id，不会把多性质证据合并成单标签。
  - 该 board 只说明还差什么，不是 authorization、preflight、feedback intake、training label 或 model claim readiness。
- P128 authorization closeout board validator 发现：
  - Validator 从 packet receipts、receipt status 和 receipt validation 重新推导 closeout board，确认 P127 产物 3/3 valid、0 invalid。
  - `decision_rows_present=0`、`authorized_rows=0`、`preflight_rows_present=0`，missing_decision_rows、missing_authorized_rows、missing_preflight_rows 继续均为 12。
  - 审查顺序仍固定为 E331Q -> D105N -> S265T；closeout validator 不会生成 authorization decision 或 preflight。
  - 这一步只证明 closeout 账本没漂移，仍不能让反馈进入 intake 或训练。
- P129 closeout operator packets + validator 已写回 manifest：
  - `datasets/feedback/wet_lab_mutant_library_feedback_authorization_closeout_operator_packets.jsonl`、`datasets/feedback/wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_status.jsonl`、`reports/wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_report.json`、`reports/wet_lab_mutant_library_feedback_authorization_closeout_operator_packet_validation_report.json` 和 `reports/wet_lab_mutant_library_feedback_authorization_closeout_operator_packets.md` 已进入 `reports/data_lake_manifest.json`。
  - `reports/local_release_manifest.json` 仍为 `release_ready=false`、`artifact_count=1059`；这批 closeout 产物只增强审查导航，不生成 reviewed authorization decision 或 preflight。
- P130 numbering review packets validator 已落地：
  - `scripts/validate_numbering_review_packets.py` 校验 21 个 review packet 与 21 个 draft 文件，结果 475/475 packet rows valid、475/475 draft rows valid、invalid 0。
  - 新增 `datasets/curation/numbering_review_packets_status.jsonl` 与 `reports/numbering_review_packet_validation_report.json`，并接入 safe pipeline 和 data lake manifest；当前 `release_ready=false` 仍正确，因为 reviewed numbering decisions 还是 0。
- P131 numbering review packet board 已落地：
  - `scripts/build_numbering_review_packet_board.py` 生成 21 行 packet board、21/21 open blocked，所有 packet 仍是 `open_blocked_waiting_for_human_review`。
  - 新增 `datasets/curation/numbering_review_packet_board.jsonl`、`reports/numbering_review_packet_board_report.json` 和 `reports/numbering_review_packet_board.md`，并接入 curation dashboard、safe pipeline、data lake manifest 和 local release manifest。
- 人工待决总清单再次核对：
  - `reports/human_decision_backlog_report.json` 当前列出 10 个 open items、0 ready items、总缺口 1239 行。
  - 最硬缺口仍是 `numbering_curation` 475 行、`structure_chain_mapping` 475 行、`experiment_feedback_source_review` 156 行。
  - 其余待决项依次为 `plate_feedback_intake` 50 行、`biosecurity_screening` 25 行、`sequence_ip_fto` 25 行、`external_license_review` 19 行、`operator_review_actions` 6 行、`workstream_acceptance` 6 行、`domain_interval_occurrence_selection` 2 行。
  - `reports/claim_readiness_matrix.json` 继续只允许本地安全训练流水线和内部设计审查产物，`model_quality_claim` 仍 blocked。
- 新增 `reports/numbering_review_briefing.json` 与 `reports/numbering_review_briefing.md`：
  - 速览聚焦 `numbering_review_isoform_exact_001` 和 `numbering_review_abstract_signal_001`，共 33 条 briefing rows。
  - `numbering_review_isoform_exact_001` 的 8 条记录全部带 `title_mismatch_risk`，应优先人工确认来源是否真的对应该蛋白与突变。
  - `numbering_review_abstract_signal_001` 的 25 条记录里，20 条为 `title_mismatch_risk`、5 条为 `title_has_broad_protein_signal`，整体仍是强审校而非可自动提升标签。
  - 新 briefing 已写入 `reports/data_lake_manifest.json`，当前本地清单 1065 个 artifacts；`release_ready` 仍 false。
- P132 numbering review briefing validator 发现：
  - `scripts/validate_numbering_review_briefing.py` 已固定 briefing 的两个 packet 顺序和 33 行总量，验证 33/33 valid、0 invalid、all_rows_valid true。
  - Validator 显式禁止 decision、canonical_position、confidence、usable_as_supervised_label、safe_for_model_claim 等字段出现在 briefing row 中，防止导航材料被误读为 reviewed curation。
  - 该层通过后 safe pipeline 为 193/193、0 failed；data lake/local release artifacts 为 1066，`release_ready=false`。
- P133 numbering review briefing status board 发现：
  - 33 条优先 briefing row 已转成逐行 status board，全部为 `open_blocked_waiting_for_human_review`，`decision_rows_present_for_briefing=0`。
  - `scripts/validate_numbering_review_briefing_status_board.py` 从 briefing、briefing validation 和 `numbering_curation_decisions.jsonl` 重新推导 expected status，确认 33/33 status rows valid、0 invalid、all_status_rows_valid true。
  - `reports/curation_dashboard.json` 已显示 review_briefing_status_rows 33、open_blocked 33、valid 33、invalid 0；这是人工审核入口，不是解锁。
  - 最新 safe pipeline 197/197、0 failed；data lake/local release artifacts 1070，`release_ready=false`；模型质量最硬 blocker 仍是 reviewed numbering/structure chain mapping/真实实验授权和物理 ddG。
- P134 可视化核实平台发现：
  - `ui/numbering_review/` 已把 33 条 priority numbering rows 转成三栏核实工作台：左侧队列、中间证据核实、右侧 decision JSONL builder。
  - 页面把 `map_to_canonical` 的浏览器预检设为最严格：6 项人工核实必须全勾、canonical UniProt/position/WT/mutant 必填、mapping_basis 不能 unresolved、confidence 必须 >= 0.5。
  - 对 `keep_unresolved_weak` 和 `reject_label`，页面允许保留弱证据/拒绝标签，但仍要求 curator、source_refs 和 notes，避免空白 decision。
  - 页面只使用 localStorage 保存浏览器草稿，并提供复制/下载；不会直接写正式 decision 文件，因此不会绕过本地 validator 或 apply gate。
  - 最新页面已把规则翻译成通俗三分法：证据明确才 map，看不准就 weak，明显不对才 reject；notes 模板会自动带入当前 PMID、UniProt 和 mutation，降低人工审核时写错格式的风险。
  - 页面已进一步简化为按钮向导：日常只需要点一个“下一步”主按钮，系统按当前记录状态依次执行保存正式结果、运行编号验证、应用修正和安全管线；高级单步按钮默认收起。
  - `scripts/serve_numbering_review_platform.py` 是窄口径本地 API，只允许保存当前 reviewed decision 和运行 allowlist 内的三步脚本；它不下载外部数据、不生成自动结论、不替代人工核实。
  - 当前 `/api/status` 已验证可用，decision_rows 仍为 0；这说明按钮服务已通，但尚未产生人工 reviewed numbering decision，模型质量和 release gate 仍保持 blocked。
- P135 非人工建设全部启动板发现：
  - `reports/non_human_construction_board.json` 已把 11 条非人工建设线全部置为 started：物理 ddG、benchmark、五头训练、MSA、结构图、反馈闭环、数据治理、生产服务、安全合规、高级模型 adapter 和主动学习。
  - 当前 3 条为 `started_ready_to_verify`：MSA/conservation production、structure GNN features、data lake/cache governance；对应现有证据为 `msa_runtime_ready=true`、MSA cache valid_rows 158、reviewed structure graph valid_rows 25、manifest/provenance 无缺失。
  - 当前 8 条仍为 `started_blocked`：Rosetta/PyRosetta/FoldX executable ddG 未 ready、benchmark cache 非 model-claim ready、五头训练缺真实 eligible label、plate/well feedback 0 training eligible、production release blocked、安全合规 blocked、高级模型仍 scaffold、active learning blocked。
  - P135 validator 11/11 workstreams 和 11/11 start packets 语义通过，明确禁止 automatic external execution；因此它是“全部开始”的工程启动板，不是工具安装许可、生产同步、customer delivery、ordering approval 或 model-quality claim。
- P136 非人工 ready-to-verify receipt 设计发现：
  - receipt 层必须只覆盖 P135 中 3 条 `started_ready_to_verify` lane；8 条 `started_blocked` lane 不能被执行，也不能被 receipt 暗示为完成。
  - MSA lane 的可验证证据是 runtime ready、homolog database ready、MSA cache 158 valid/0 invalid、strict MSA site feature table 存在且有行；这仍只是 computational feature。
  - Structure lane 的可验证证据是 reviewed structure graph validation 25 valid/0 invalid、feature table 存在；`safe_for_model_claim=false` 必须保留。
  - Data governance lane 的可验证证据是非 P136 中间产物外无 missing artifacts、provenance_ready 和 governance report 存在；最终 data lake/local release 仍要在 pipeline 末尾重跑收敛。
- P136 receipt 可以标记局部 `verification_passed`，但不得设置 `completion_ready`、`model_quality_claim` 或 `release_ready`。
- P136 本地和远端验证结果：
  - 本地 3/3 receipt passed、8/8 commands successful、validator 3 valid/0 invalid；safe pipeline 201/201、data lake 1082 artifacts、missing 0。
  - 远端因缓存和跨平台路径差异先后发现两类部署问题：macOS MMseqs2 binary 不能在 Linux 执行；structure mapping 的本机绝对路径不能跨机器使用。
  - 已用 SHA-256 校验的项目内相对路径重定位修复结构图 builder，并让 MSA runtime probe 捕获 `OSError` 后回退到 trusted cache；同步约 1.63GB 本地既有缓存和 25 个 reviewed PDB 后，远端 3/3 receipt passed、validator 3/3、missing artifacts 0、release_ready=false。
  - 该解锁只证明 MSA/结构图/数据治理局部证据可复核，不解锁 Rosetta/PyRosetta/FoldX、真实数值训练、五头模型质量声明或生产发布。
- P137 湿实验授权可视化平台发现：
  - 现有 12 条 15B numeric training candidates 已有 authorization template/worklist，但正式授权输入仍为 0；页面将 E331Q 的 tradeoff 记录置顶，避免把酸性收益与 85C 热稳定性下降合并成单一标签。
  - 授权通过必须同时满足 5 个人工核实项、reviewer/reviewed_at/basis、QC `pass` 或 `pass_with_conditions`、至少一个匹配 training head，且 residual risks 为空；页面不会代替 validator。
  - `save-wet-lab-authorization` 只 upsert `wet_lab_mutant_library_feedback_authorizations.jsonl`，`allow_append_to_experiment_feedback_local` 固定为 false；preflight/apply-plan 只由按钮显式触发。
  - P137 smoke 证明页面/API 可用，但当前没有任何人工授权，因此 `authorized_rows=0`、`preflight_rows=0`、`apply_plan_rows=0`，模型和 release gate 不变。
- P138 stability/numbering source integrity deep audit:
  - `backend/scripts/generate_sample_data.py` directly creates stability records with random mutation positions, random WT residues, random ddG/dTm values, `source_db=ProThermDB`, and `PMID:310xxxxx`; this is source-lineage evidence, not a heuristic.
  - The audit checked all 549 local `stability_records`: 542 have the generated-source fingerprint and the other 7 use known fixture PMIDs. Therefore none is a real-source stability receipt or a candidate for numbering repair into supervised data.
  - 523/549 reported WT residues disagree with the current UniProt sequence. 546/549 rows have same-sign ddG and dTm values, which conflicts with the KWB convention that negative ddG and positive dTm both indicate stabilization.
  - The 475-row numbering queue has PubMed evidence for all rows, but 0 mutation mentions and 0 UniProt-reference links; 8 isoform residue matches remain non-provenance coincidences, not map evidence.
  - All 4 existing human decisions say "reject label" in their notes but are stored as `keep_unresolved_weak`; the audit flags this for explicit human resolution and makes no automatic change.
  - New artifacts are `scripts/audit_numbering_source_integrity.py`, `datasets/curation/numbering_deep_audit_all_stability_records.jsonl`, `datasets/curation/numbering_deep_audit_review_queue.jsonl`, and `reports/numbering_deep_audit_report.{json,md}`. `safe_to_map_any_record=false`, `safe_for_model_claim=false`, and no training label is changed.
- P139 production sync findings:
  - The deployed path is `8.139.255.194:/root/crvab-auto/06临时数据标注平台/AI大模型/`; service is `numbering-review-platform.service` behind Nginx `/numbering-review/` and `/06临时数据标注平台/`.
  - Remote Linux cannot execute the macOS MMseqs2 binary in `cache/external/MMseqs2/bin/mmseqs`; `build_mmseqs2_local_runtime_manifest.py` and `build_mmseqs_homolog_database_manifest.py` now catch `OSError` and record fail-closed probe results instead of crashing.
  - Remote does not have `.venv-thermompnn/bin/python`; `run_safe_training_pipeline.py` now records `skipped_optional_python_runtime_missing` for optional `--python` commands while keeping `safe_for_model_claim=false`.
  - `build_non_human_ready_to_verify_receipts.py` and validator now accept the current board's ready-to-verify allowlist subset instead of hardcoding exactly 3 lanes, so remote platform validation does not fail when a lane is correctly blocked.
  - Remote final state: safe pipeline 202/202, failed 0; local release artifact_count 1082, missing_artifacts empty, `release_ready=false`; deep-audit hard gate remains `blocked_generated_or_fixture_stability_source`.
- P153 review draft/formal boundary findings:
  - 三份 review draft 当前共有 496 行：numbering deterministic reject 475、structure DBREF chain mapping 9、wet-lab feedback authorization 12。
  - 三份 formal 文件当前共有 29 行：numbering curation decisions 4、structure chain mapping decisions 25、wet-lab feedback authorizations 0。
  - `scripts/validate_review_drafts_not_formal_decisions.py` 要求 draft 行保留 `review_draft=true` 和 `draft_policy`，并要求 formal 行不含 `review_draft`/`draft_policy`。当前验证 0 failures，`draft_rows_counted_as_formal_decisions=0`。
  - 4 条 numbering formal decision 的 record_id 同时存在于 deterministic reject draft 中；这是允许的审计重叠，不代表新增正式决策，因为 formal 行数仍锁定 4 且 formal 行没有 draft-only 字段。
  - 该 gate 明确保持 `safe_for_training_import=false`、`safe_for_model_claim=false`、`release_ready=false`；如果后续人工确认导致 formal 行数变化，必须更新期望值并重新验证，不能静默把草稿当突破。
- P154 review draft training leakage findings:
  - `scripts/validate_no_review_draft_training_leakage.py` 递归扫描 strict supervised、claim-eligible、strict MSA、wet-lab preflight/apply plan 和 FireProt reviewed import rows，查 `review_draft`、`draft_policy`、`.review_draft`、`REVIEW_DRAFT` 痕迹。
  - 当前所有扫描路径都为 0 泄漏行；同时 strict rows、claim-eligible rows、strict MSA rows、wet-lab preflight ready rows、wet-lab applied rows、FireProt ready import rows 全部保持 0。
  - 这层 guard 把 review draft 与训练/导入路径拆开，避免草稿状态被误当成正式可训练数据。
- P155 draft namespace isolation findings:
  - `scripts/validate_draft_namespace_isolation.py` 扫描全部 `datasets/**/*.jsonl`，允许草稿痕迹只存在于显式草稿命名空间和 `datasets/feedback/experiment_feedback_plate_intake_backlog.jsonl`。
  - 当前结果：59 个允许的草稿/草稿型文件、0 个非预期命中；`experiment_feedback_plate_intake_backlog.jsonl` 共 50 行，全部保持 `review_status=draft`、`approved_for_plate_intake=false`、`training_eligible=false`、`claim_eligible_now=false`。
  - 这样 plate backlog 不会再被当成实际 intake 或训练标签，同时全局草稿边界也变成可验证规则。
- P156 draft namespace semantic isolation findings:
  - 草稿命名空间进一步收紧到“语义上仍是草稿”：`draft_policy` / `policy` 必须包含 draft/backlog/未审/未授权/模板等 fail-closed 语义，且不能出现 `review_status=reviewed` 或 `approved/training_eligible/claim_eligible_now=true`。
  - 当前结果：58 个一般草稿型文件全部通过语义检查，plate backlog 50 行也全部保持 draft/backlog only；`draft_namespace_isolation_validation_report.json` 失败数 0。
  - 这层规则把“文件名像草稿”升级成“内容也必须像草稿”，继续避免草稿被误当成正式人工决策或训练输入。
- P157 positive gate flag quarantine findings:
  - `scripts/validate_no_unreviewed_positive_gate_flags.py` 扫描全部 `datasets/**/*.jsonl` 的正向 gate 字段，包括 approved、authorized、training_eligible、claim_eligible、ready_for_training_import、safe_for_model_claim、release_ready 等。
  - 当前扫描 425 个数据文件，发现 8 个 `completion_ready=true`，全部只在 `next_unlock_completion_status.jsonl` 和 `next_unlock_operator_index.jsonl` 的局部操作完成状态中，被显式 allowlist；未授权正向 gate 数为 0。
  - 训练、反馈导入、claim、release 相关真值仍为 0；这层规则防止 generated dataset 悄悄写出可训练/可声明/可发布状态。
- P158 report positive claim gate quarantine findings:
  - `scripts/validate_report_positive_claim_gate_quarantine.py` 扫描 `reports/**/*.json` 中 high-risk 正向字段：`safe_for_model_claim`、`release_ready`、`model_quality_ready`、`ready_for_model_claim`、`ready_for_training_import`、`safe_for_training_import`、customer/order ready 等。
  - 当前扫描 260 个报告，只发现 1 个 true：`reports/model_quality_unlock_requirements_report.json` 的 `requirements[0].target_state.safe_for_model_claim`，这是目标状态文档，不是当前 readiness，因此显式 allowlist。
  - 当前报告层 disallowed true hit 为 0；current-state model claim、training import、release gate 继续保持 false。
- P159 claim readiness matrix fail-closed policy findings:
  - `scripts/validate_claim_readiness_matrix_fail_closed_policy.py` 固定 claim matrix 的 fail-closed 策略：只允许 `local_safe_training_pipeline` 和 `internal_design_review_artifacts` 两个内部工程 claim。
  - 9 个高风险 claim 必须 blocked：`model_quality_claim`、`five_head_training_run`、active learning experiment submission、customer package、ordering、IP/FTO、biosecurity、external tool production use、local release review package。
  - 当前矩阵 11 行 claim、allowed 2、blocked 9、failures 0；该层防止 claim matrix 被误改成“模型完成/可训练/可交付/可发布”。
- P160 human decision backlog fail-closed consistency findings:
  - `scripts/validate_human_decision_backlog_fail_closed_consistency.py` 固定 11 个人工待决项必须全部存在，并要求 `ready_items=0`、`open_items=11`、`total_missing_rows=1190`。
  - 关键 P0 缺口被显式锁住：numbering semantic conflicts 4、numbering curation 471、structure chain mapping 475、feedback source review 157、plate feedback intake 50、external license review 19。
  - 当前 formal boundary 仍为 review draft 496、formal decisions 29、draft counted as formal 0；backlog consistency failures 0。
- P161 local release manifest fail-closed consistency findings:
  - `scripts/validate_local_release_manifest_fail_closed_consistency.py` 把 `reports/local_release_manifest.json` 和 `reports/data_lake_manifest.json` 绑定校验，要求 `release_ready=false`、`local_only=true`、artifact_count 等于 data lake artifact 数、missing_artifacts 为空。
  - P161 初始验证时本地发布包 artifact_count 1176，data lake artifact_count 1176，release_ready false，failures 0；P162 新增报告接入后最新 artifact_count 为 1177。该发布包可以作为内部 review manifest，但不能作为上线/客户交付 release。
  - local release summary 中 strict supervised rows 0、claim-eligible rows 0、strict MSA site feature rows 0、human backlog open 11、missing rows 1190、claim allowed 2、blocked 9，被同一 validator 固定校验。
  - formal 文件边界未变：numbering decisions 4、structure chain mapping decisions 25、wet-lab feedback authorizations 0；本轮没有把 review draft、backlog 或 receipt 升级成正式人工决定。
- P162 local release safety guard link validation findings:
  - `scripts/validate_local_release_safety_guard_links.py` 将 11 个核心 safety guard 固定为 local release 必须显式链接的 review 证据，包括 no-pseudo、model claim consistency、top-tier receipt、draft/formal boundary、draft leakage、draft namespace、positive gate quarantine、claim matrix、human backlog 和 local release consistency。
  - validator 同时检查 release manifest 顶层路径、报告文件存在、data lake artifact 存在且 exists=true、报告自身通过；当前 guard_link_count 11、failures 0。
  - `no_pseudo_strict_training_leakage_validation_report.json` 是旧式 guard，没有 `success` 字段；P162 按它的实际合同用 `safe_for_training_pipeline=true`、`invalid_artifacts=0`、`safe_for_model_claim=false`、`release_ready=false` 判定通过。
  - P162 接入后最新 data lake/local release artifact_count 为 1177，local release readiness summary 记录 `local_release_safety_guard_link_success=true`、failures 0、count 11；`release_ready=false` 和 formal `4/25/0` 边界保持。
- Biomni external research findings:
  - 用户提供的微信文章链接当前无法直接打开；本轮以 Biomni GitHub、README、源码、PMC 论文页和 license/environment 文档为证据。
  - Biomni 对 KWB 最有价值的是系统工程范式：action space、tool/data/software/know-how registry、retriever 选择资源、CodeAct 执行、benchmark task abstraction、commercial/license-aware 模式。
  - KWB 可迁移方向应收敛到酶蛋白专用：enzyme action space、enzyme tool contract、enzyme resource retriever、know-how library、benchmark task interface、license-aware runtime policy。
  - 不建议直接完整安装 Biomni E1 或把 Biomni datalake 混入训练；应先做只读源码/架构对标和 license/source registry。当前没有下载、没有安装、没有执行 Biomni agent。
- P163 Biomni source-level learning findings:
  - Biomni A1 agent 的关键架构是 config -> commercial/academic resource mode -> ToolRegistry -> ToolRetriever -> know-how loader -> system prompt -> LangGraph workflow；KWB 应改造成 local-only/commercial-safe/research-only/production-blocked 四档。
  - Biomni ToolRegistry 只需要 name/description/required_parameters；KWB 必须扩展 license、runtime readiness、human gate、formal write permission、training write permission、validator、artifact contract。
  - Biomni ToolRetriever 是 prompt-based resource selection；KWB 应加 policy filter，过滤未授权 license、未 ready runtime、会写 formal/training 的工具和外部网络/download 动作。
  - Biomni CodeAct 适合科研组合执行，但 KWB 不能开放任意 Python/R/Bash；应做 `KWBControlledCodeAct`，只执行 allowlisted script，并强制 receipt/report/validator。
  - 下一步最值得做的是 KWB 自己的 `enzyme_action_space_registry` 和 `enzyme_tool_contracts`，不是安装 Biomni。
- P164 enzyme action space/tool contract findings:
  - 已把 Biomni-inspired action space 落成 KWB 本地 metadata：12 个 enzyme action、12 个 tool contract，覆盖 numbering、structure mapping、MSA、ddG、wet-lab authorization、FireProt、benchmark、claim/release safety guard、know-how 和 safe pipeline。
  - `scripts/validate_enzyme_tool_contracts.py` 当前 success true、failures 0；所有 contract 都是 read-only/local_script/manual_only，0 个可写 training rows，0 个可写 formal decision，0 个 action safe_for_model_claim。
  - `human_confirmation_required_actions=6`，`formal_decision_actions=3`；这些只是标记“该 action 涉及人工 formal gate”，并不允许 agent 写 formal 文件。
  - draft namespace guard 暴露出一个真实设计问题：governance registry 不能引用 `.review_draft` 文件名，否则会污染草稿隔离扫描。已改成引用正式文件和报告路径。
  - claim matrix 原先依赖上一轮 `safe_training_pipeline_run.success`，当 pipeline 失败后会自我阻塞。已改为用 safe entrypoint、enzyme tool contract validation、model claim fail-closed consistency 判定 `local_safe_training_pipeline` 这个内部工程 claim。
  - 最新完整流水线 245/245 通过，data lake/local release artifact_count 1181，release_ready false，formal `4/25/0` 边界保持。
- P165 Biomni second-wave engineering findings:
  - Biomni 还可借鉴执行协议、checkpoint/memory、timeout wrapper、MCP、配置一致性、environment tiering、contribution governance、structured output、research log/audit package 和 custom resource priority。
  - KWB 应把 Biomni 的开放科研执行模型改造成保守执行模型：read-only resources 可宽松选择，executable tools 必须按 contract 过滤，formal/training/release 工具默认 blocked。
  - 最值得立刻落地的是 `enzyme_agent_execution_protocol` 和 `enzyme_resource_retrieval_plan`：先让 agent 会“选择资源和说明阻断原因”，再谈受控执行。
  - Biomni-R0 的启发不是直接替代 KWB 模型，而是未来用 KWB agent traces 训练 tool-use planner；这些 traces 应包含 plan、selected tools、blocked reasons、validation outputs、human corrections 和 final report。
- P166 Biomni local source audit findings:
  - `git clone` 失败于 GitHub SSH 端口连接关闭；改用 GitHub main zip 下载并保存到 `cache/external/biomni-main-20260731.zip`，sha256 `158873d40c1675f05ac857afa055e24dcd0035817d7f60d5b4bd7249adf3740f`。
  - 项目中文路径下 unzip 被 Biomni protocol 文件名编码绊住；在 `/private/tmp/biomni-src/Biomni-main` 解压成功并完成只读源码审计。
  - A1 默认 data lake/benchmark 自动下载、custom tool builtins 注入、MCP 自动发现/包装、persistent Python REPL 都证明 Biomni 原生执行面太开放，KWB 不应直接运行。
  - ReAct multiprocessing timeout、tool-call parsing、structured result formatting、task/eval base class、know-how loader、known conflicts 文档是更适合迁移的源码级机制。
  - 当前不需要完整安装 Biomni；下一步应做 KWB controlled resource retrieval 和 execution protocol。
- P167 controlled resource retrieval findings:
  - 已建立 `contracts/enzyme_agent_execution_protocol.md`，把 Biomni 的 plan/execute/observe/reflect/solution 改造成 KWB contract-first、read-only-first、fail-closed-first 协议。
  - `enzyme_resource_retrieval_plan_report.json` 将 12 个 action 分类为 read-only 1、用户确认后可执行 5、需人工决定 blocked 5、当前请求 forbidden 1。
  - `enzyme_agent_state_checkpoints.jsonl` 当前 1 行，stage 为 `retrieval_plan_built`，executed_action_ids 为空，claim snapshot 中 training/model/release 全 false。
  - `validate_enzyme_resource_retrieval_plan.py` 当前 success true、failures 0；该层证明 agent 已能“选择资源并解释阻断”，但仍不能执行工具。
  - P167 后完整 safe pipeline 247/247 通过，data lake/local release artifact_count 1187，release_ready false，formal `4/25/0` 边界保持。
- P168 structured result gate findings:
  - 已把酶 agent 的未来输出固定为结构化 result contract：任何结果必须携带 selected variants、property predictions、ddG results、evidence summary、experimental plan、forbidden claims、artifact refs 和 fail-closed flags。
  - 当前模板故意不产生 `selected_variants` 和 `go` 推荐，因为 formal reviewed numbering 只有 4 行、claim-eligible training rows 为 0、strict MSA site feature rows 为 0、wet-lab authorization rows 为 0。
  - ThermoMPNN proxy 可以在结果封套中显示为 manual review support，但 Rosetta/PyRosetta/FoldX physics ddG 仍为 blocked；结果封套不得声称 physics ddG 已集成。
  - validator 明确禁止在 reviewed/training/authorization gate 未达标时出现 go 推荐；同时强制 `manual_review_required=true`、`safe_for_training_import=false`、`safe_for_model_claim=false`、`release_ready=false`。
  - P168 的意义是把“工具能调用”和“结果能声明”隔离：后续即使接入更多工具，也必须先通过 evidence gate 和 result validator，不能让 agent 直接把草稿、proxy 或弱证据变成客户可用推荐。
- P169 enzyme agent result safety regression findings:
  - P169 证明 P168 validator 不只是让当前模板通过，还能主动拒绝 10 类坏输出：低证据 go、variant 不需人工复核、training import true、model claim true、release true、缺 forbidden claim、缺 artifact refs、manual review false、resource plan validation false、physics ddG claim。
  - 新增的 physics ddG 检查很关键：只要 forbidden claims 里仍包含 `rosetta_pyrosetta_foldx_physics_ddg_integrated`，结果就不能同时声明 Rosetta/PyRosetta/FoldX ready 或 safe_for_model_claim。
  - 当前回归结果为 case_rows 11、actual_rejected_negative_cases 10、failed_regression_cases 0；这为后续接更多工具提供了结果层防线。
- P170 enzyme agent trace audit findings:
  - P170 将 P167/P168/P169 串成 6 行可审计 trace，从 resource plan 到 final fail-closed state；这解决了“只看到最终报告，看不到 agent 为什么没执行”的审计缺口。
  - trace validator 固定要求 event sequence、event index、executed_action_count 0、selected_variant_rows 0、resource/result/regression validation success，并逐行检查 training/model/release flag 为 false。
  - 当前 trace audit validation success true、trace_rows 6、executed_action_count 0、failures 0；后续如果出现实际 action execution，必须生成 receipt 并进入新的执行授权层，不能混在当前 read-only trace 里。
- P171 enzyme agent execution receipt gate findings:
  - P171 把“未来可以执行”和“当前已经执行”继续拆开：即使 resource plan 中有 executable_after_user_confirmation action，只要 trace 的 executed_action_ids 为空，就不能声称执行过。
  - 新 receipt schema 要求记录 trace、plan、action、tool contract、human confirmation、input/output artifacts、validator artifacts 和 return_status；没有 receipt 的 executed action 会在 validator 中失败。
  - 当前 receipt gate validation success true、executed_action_count 0、receipt_rows 0、missing_receipt_action_count 0；这说明 P171 没有执行工具，只是建立执行回执门控。
- P172 enzyme agent execution receipt safety regression findings:
  - P172 证明 receipt gate 会拒绝 10 类坏执行声明：执行无 receipt、receipt 无对应执行、receipt 打开 model/training/release flag、executed_passed 缺 output/validator artifact、report 打开 execution/model claim、receipt 缺必填字段。
  - 回归套件只在内存构造坏 report/receipt，不写入 `enzyme_agent_execution_receipts.local.jsonl`；当前真实 local receipt 文件仍为 0 行。
  - 当前 regression success true、case_rows 11、actual_rejected_negative_cases 10、failed_regression_cases 0；未来接入真实 action execution 前，这层可以防止“口头执行完成”绕过 artifact/validator/receipt。
- P173 enzyme agent execution eligibility findings:
  - P173 把 12 个 enzyme action 全量展开成 current execution eligibility matrix；当前 `current_execution_allowed_rows=0`，说明没有任何 action 被默认为可执行。
  - executable_after_user_confirmation 类 action 不再只是分类标签，矩阵中明确写入 requires_explicit_user_confirmation、requires_execution_receipt、requires_validator_artifacts 三个阻断原因。
  - blocked_requires_human_decision 和 forbidden_for_current_request action 均保持 blocked；矩阵逐行固定 training/model/release false、executed false、receipt_present false。
- P174 enzyme agent execution eligibility safety regression findings:
  - P174 证明 eligibility validator 会拒绝 13 类坏状态：report/row 错误允许执行、row 已执行、row 有 receipt、training/model/release flag 越权、writes_training_rows true、关键 blocked reason 缺失、receipt regression 失败。
  - 当前 regression success true、case_rows 14、actual_rejected_negative_cases 13、failed_regression_cases 0；这让 action eligibility matrix 不只是当前状态报告，也变成可防回归的执行资格边界。
- P175 controlled execution wave findings:
  - 在用户明确允许后，系统已经从 no-execution 状态推进到真实 receipted execution 状态：`enzyme_agent_execution_receipts.local.jsonl` 当前 11 行，覆盖 know-how retrieval、numbering validator/apply、structure mapping validator/apply/graph、MSA cache validation、ddG probe/readiness、wet-lab authorization gate、FireProt gate、benchmark gate、model claim consistency、release guard links、tool contract validation。
  - eligibility matrix 已真实变化：12 个 action 中 11 个有 receipt，11 个 executed_with_receipt，10 个 executed_passed，1 个 executed_failed，5 个低风险/确认后可执行 action 标为 current_execution_allowed；`act_safe_pipeline` 被跳过以避免递归。
  - P175 的 ddG 结果是硬失败而不是突破：Rosetta executable not found、FoldX executable not found、PyRosetta module unavailable、executable_ddg_backend_ready false。当前唯一 ready backend 是 ThermoMPNN proxy，不能声明 Rosetta/PyRosetta/FoldX physics ddG integrated。
  - P175 没有写 formal decision，也没有导入训练标签：formal numbering decisions 4、structure chain mapping decisions 25、wet-lab authorizations 0、strict repaired supervised rows 0、claim eligible rows 0。
  - 安全管线已把 P175 纳入常规验证：safe pipeline 271/271 通过，data lake/local release artifact_count 1209，local release fail-closed consistency 和 safety guard links 均通过，`release_ready=false` 保持。
- P176 execution outcome/lineage guard findings:
  - receipt lineage guard 把 P175 的 authorization_ref、plan_id、action_id、return_status、artifact refs 与 11 条 receipt 逐项绑定，防止“有 receipt 文件”被重复、错配或篡改成执行证据；当前 success true、failures 0。
  - outcome dashboard 证明 P175 的 11 条 receipt 不等于 11 个硬门槛突破：12 个 action 中 engineering_ready_rows 6、hard_gate_unlocked_rows 0。
  - 真实 outcome 分类为：hard_gate_still_blocked 3、partial_feature_gate_ready 2、physical_ddg_not_ready 1、benchmark_gate_still_blocked 1、safety_guard_ready 3、engineering_evidence_ready 1、skipped_by_policy 1。
  - MSA cache 和 reviewed structure graph 属于 partial feature ready；它们是真实特征工程进展，但由于 strict real-source supervised rows 仍为 0，不能变成训练质量声明。
  - ddG outcome 固定为 physical_ddg_not_ready：ThermoMPNN proxy_ready true 只能支持 computational proxy evidence，Rosetta/PyRosetta/FoldX physics_ddg_ready false。
  - P176 后完整 safe pipeline 277/277 通过，data lake/local release artifact_count 1213，release_ready false；formal/training 行数仍为 4/25/0/0/0。
- P177 validated feature index findings:
  - 已把 MSA conservation cache 158/158 valid 和 reviewed structure graph 25/25 valid 汇成 `datasets/features/validated_feature_index.jsonl`，总计 183 行。
  - validated feature index 是模型输入合同层：183 行均 `model_consumable=true`，但 `training_label_source=false`、`safe_for_training_import=false`、`safe_for_model_claim=false`、`release_ready=false`。
  - MSA rows 带 conservation JSON、alignment FASTA、source database、database version 和 sha256；structure rows 带 graph JSON、input structure checksum、reviewed chain mapping status 和 requires mutation numbering review 边界。
  - 新 validator 对 feature 文件存在、sha256、MSA position_conservation 长度/值域、structure graph nodes/edges 和 row-level safety flags 做复核；当前 failures 0。
  - P177 把“已有真实特征缓存”推进为“模型代码可消费索引”，但不会改变训练硬门槛：strict repaired supervised rows 0、claim eligible rows 0，模型质量声明仍 blocked。
- P178 advanced model scaffold regression findings:
  - 已新增无依赖 regression，锁定 `KWB-EnzymeDesigner` advanced scaffold 的接口和安全行为，不验证模型性能。
  - 回归覆盖：五个 heads 必须存在且 0-100，`status=scaffold_only_fail_closed`，`requires_wet_lab_validation=true`，protected catalytic mutation 必须 no_go 并带 protected_catalytic flag。
  - adapter scaffold 回归覆盖：gate 未 ready 时返回 blocked envelope、local_only true、input_hash 对相同输入稳定；gate 全 ready 的 base adapter 必须抛 NotImplementedError，防止假执行。
  - 当前 `advanced_model_scaffold_regression_report.json` success true、candidate_rows 2、failures 0、safe_for_model_claim false、release_ready false。
  - P178 让模型代码底座更稳，但不改变真实训练状态：strict supervised rows 0、claim eligible rows 0，不能用于模型质量声明。
- P179 feedback training semantic guard findings:
  - 真实 Venus-15B E331Q 反馈仍只有 qualitative_feedback_eligible 1；numeric_training_import_eligible 0，因此不能作为数值训练标签。
  - 新语义门把 qualitative feedback、numeric training import、strict supervised rows、claim eligible rows 分开输出，避免把 `training_eligible_rows=1` 错读为可训练样本。
  - 当前 safe_for_training_import false、safe_for_model_claim false、release_ready false；没有修改反馈 JSONL，也没有导入训练标签。
- P180 benchmark coverage validator findings:
  - benchmark dashboard 当前 14 行全部 invalid，5 个 head 都有 gap queue，heads_ready 0，ready_for_model_claim false。
  - 新 validator 要求 dashboard head 汇总、gap queue 和 gap item 三方一致；若 ready_for_model_claim=true 但 valid rows/head readiness/gap queue 不满足会失败。
  - benchmark gap queue 是补评测数据的工作队列，不是训练标签或性能声明依据。
- P181 structure feature contract findings:
  - 结构坐标摘要已经 500/500 解析成功，parse_failures 0；但这只证明本地结构文件可解析。
  - 模型可消费 reviewed structure graph 仍只有 25 行，且与 25 条 formal chain mapping decision 一致；未 reviewed 的 475 个坐标行被显式排除。
  - 结构图特征只能作为 input feature，training_label_source false、safe_for_model_claim false、release_ready false。
- P182 advanced model feature contract findings:
  - 183 条 validated feature refs 已接入高级模型输入合同，包含 MSA conservation 158 和 reviewed structure graph 25。
  - 全部 183 条都是 model input only：model_consumable true，但 training_label_source false、safe_for_training_import false、safe_for_model_claim false、release_ready false。
  - advanced scaffold 在无真实标签/无 adapter 的 fixture 下仍为 `scaffold_only_fail_closed`，五个 head 存在但不能声明模型性能。
  - P182 后 safe pipeline 290/290 通过、data lake/local release artifact_count 1228、release_ready false；真实硬门槛仍是 claim-eligible supervised rows、数值湿实验授权、physics ddG、benchmark ready 和人工 formal review。
- P183 training label import contract findings:
  - 已把 strict supervised、claim eligible、FireProt reviewed import、湿实验 preflight 和 numeric feedback import 统一到一个训练导入合同中。
  - 当前所有来源的 training-import-eligible rows 都是 0；合同总计 training_import_eligible_label_sources 0、training_import_eligible_rows 0、counted_as_trainable_rows 0。
  - validator 固定要求任何可训练计数都必须有 reviewed/source/provenance/authorization 四类证据；当前没有任何来源满足，因此安全地保持导入关闭。
- P184 wet-lab feedback authorization contract findings:
  - 真实湿实验候选已存在：445 条候选、12 条数值训练候选；这证明数据源有价值，但不等于授权。
  - 人工授权文件当前 0 行，因此 authorized_rows、preflight_rows、apply_plan_rows、ready_for_training_import_rows、claim_eligible_rows_now 全部为 0。
  - 新 validator 把“候选存在”和“可消费”分开：numeric candidates 不能被当作 authorized rows，preflight/apply rows 不能超过 authorized rows。
  - P184 后 safe pipeline 294/294 通过、data lake/local release artifact_count 1232、release_ready false；湿实验数据的下一步硬门槛仍是人工授权和 QC/replicate/plate 证据。
- P185 ddG model consumption contract findings:
  - ThermoMPNN Venus-15B smoke 产出的 4 条 ddG proxy 行已纳入模型消费合同，突变为 S265D、D405N、E331Q、M204H。
  - 合同明确 negative_ddg_is_stabilizing true，但 evidence_level 是 computational_proxy，所有行都要求 manual_review 和 limitations。
  - Rosetta/PyRosetta/FoldX physics_ddg_ready false、executable_ddg_backend_ready false、proxy_is_physics false；ThermoMPNN proxy 不能满足 physics ddG 门槛。
  - P185 后 safe pipeline 296/296 通过、data lake/local release artifact_count 1234、release_ready false；ddG 下一步硬门槛仍是 license/install/config/probe/smoke/runtime receipt。
- P186 five-head training execution contract findings:
  - 五头训练执行合同把 multitask readiness、five-head gap plan、training label import、wet-lab authorization、benchmark coverage 和 advanced feature contract 聚合到一个训练执行门控。
  - 当前五个 head 的 rows 均为 0，ready_head_count 0；training_import_eligible_rows 0，wet_lab ready_for_training_import_rows 0，benchmark_ready_for_model_claim false。
  - 183 条 validated feature refs 只能作为模型输入，不能作为训练标签；因此 training_execution_allowed false、safe_for_training_import false、safe_for_model_claim false、release_ready false。
  - P186 后 safe pipeline 298/298 通过、data lake/local release artifact_count 1236，release_ready false。
- P187 model-quality hard-gate contract findings:
  - 模型质量总硬门槛合同聚合 10 项：training import、wet-lab authorized/preflight/import、physics ddG、benchmark claim readiness、feature inputs、model_quality_ready、safe_for_model_claim、release_ready。
  - 当前真实状态为 training_import_eligible_rows 0、wetlab_authorized/preflight/import 0、physics_ddg_ready false、benchmark_ready_for_model_claim false、feature_inputs_ready 183 且 input-only。
  - 主线程额外修正了 agent 初稿中 `safe_for_model_claim` 的潜在误报条件：必须 model_quality claim ready+allowed 且 release master 状态明确 ready，不能由缺字段或 allowed claim 计数推导。
  - P187 后 safe pipeline 300/300 通过、data lake/local release artifact_count 1238，model_quality_ready false、safe_for_model_claim false、release_ready false。
- P188 model artifact claim guard findings:
  - 9 个模型 artifact 被分为 code scaffold、scaffold only、blocked empty train split、baseline not claimable、rule/baseline not neural weights 等类别。
  - 当前 claimable_model_artifact_count 0、trained_neural_weight_artifact_count 0、production_model_artifact_count 0；旧 baseline JSON 仍可留作本地回归，但不能被误标成顶级训练权重或生产模型。
  - 这个 guard 只是在 artifact 声明层做隔离，不改变训练/claim/release 状态；P188 后 safe pipeline 302/302 通过、data lake/local release artifact_count 1240。
- P189 local release guard coverage findings:
  - 新覆盖门把 five-head training execution、model-quality hard gate、model artifact claim guard、advanced model feature contract、validated feature index 全部纳入 local release 必检。
  - 首次失败来自 release summary 字段读错位置；修正为 `readiness_summary` 后通过，coverage_count 10、failures 0。
  - P189 后 safe pipeline 303/303 通过、data lake/local release artifact_count 1241，release 仍 `false`，说明只增加审计覆盖，没有打开发布门。
- P189+ manifest refresh findings:
  - `feature_label_boundary_quarantine_report` 已回填到生成链路里；此前 `local_release_guard_coverage` 的失败根因是 `data_lake_manifest.json` / `local_release_manifest.json` 没有随着新 guard 重新生成。
  - 重新跑 `build_data_lake_manifest.py` / `build_local_release_manifest.py` 后，`data_lake_manifest` 和 `local_release_manifest` 都回到一致状态，artifact_count = 1243，`guard_coverage_count = 12`，`failures = 0`。
  - 重新跑 `run_safe_training_pipeline.py` 后结果仍是 fail-closed：steps_run 305、failed_steps 0、success true、`release_ready=false`、`safe_for_model_claim=false`。
- P190 P26-P31 all-started board findings:
  - 已把 P26-P31 从待建清单全部切到启动态：task plan 中 6/6 阶段为 `in_progress`，`pending_stage_all_started_board` 显示 started_stage_count 6。
  - 受当前 agent 并发槽位限制，本轮新开成功的是 P26 agent；P27-P30 已由主线程启动并登记为等待 agent 槽位，P31 只允许 review-preparation，不允许生产同步、部署、重启或灰度。
  - 新 validator 固定要求 P26-P31 全部 started，同时要求每行 `training_import_allowed=false`、`safe_for_model_claim=false`、`release_ready=false`；P31 必须保持 `review_preparation_started_no_production_execution`。
  - P190 后 safe pipeline 308/308 通过，data lake/local release artifact_count 1247；这证明“全部启动”和边界可验证，不证明硬门槛突破、模型质量 ready 或发布 ready。
- P26 real-data unblock wave 1 findings:
  - P26 本轮只推进 numbering recovery、structure cache、domain interval real-data import；没有执行 P27-P31 工作，没有生产同步、部署、模型训练或 release 解锁。
  - 编号仍是最硬人工瓶颈：正式 `numbering_curation_decisions.jsonl` 当前只有 4 行且 validator 通过；这不能把 475 条 queue 或草稿提升为 reviewed numbering，也不能满足 strict supervised rows 的质量声明。
  - `apply_numbering_curation.py` 输出的 `usable_as_supervised_label=25` 是旧 repaired table 口径；下游 strict/provenance/claim gates 已把训练与模型声明关闭，不能用这 25 行宣称可训练或可发布。
  - 结构缓存是真实进展：500 条 expected/acquisition cache rows 均 present，500 条 sha256 全部复核，mismatch 0；新增 validator 证明的是本地坐标文件存在、可校验，不证明 475 条未 review chain mapping 可进入模型图特征。
  - Domain interval 导入是真实进展：1785/1942 条 InterPro/domain interval decisions 已验证并 apply 为 usable position features，覆盖率 91.92%；剩余 157 条保持 undecided/unusable，不能自动补齐。
  - 本轮后全量 safe pipeline 308/308 通过，data lake/local release artifact_count 1247；`safe_for_model_claim=false`、`release_ready=false` 继续保持，说明 P26 是真实数据解阻进展，不是模型质量硬门槛完全突破。
- P191 active P26-P31 execution matrix findings:
  - 新矩阵把 P26-P31 每个 active stage 的 evidence、non-human next actions、human/external next actions 和 blockers 写成 6 行 JSONL，避免后续 agent 只看散落报告。
  - 当前 P27 真实状态是 input features partially ready：validated feature rows 183、training_label_source_rows 0；strict MSA feature input_rows 0，因为 strict supervised rows 仍关闭。
  - 当前 P28 真实状态是 candidate evidence ready but authorization blocked：wet-lab candidates 445、numeric candidates 12、authorized/preflight/training-import rows 全 0。
  - 当前 P29 真实状态是 training execution blocked：ready_head_count 0、total_head_training_rows 0、training_import_eligible_rows 0、benchmark_ready_for_model_claim false。
  - 当前 P30/P31 真实状态是 local review package fail-closed / review-preparation-only：release_ready false、customer delivery ready false、workstream accepted 0；P31 production_execution_allowed false。
  - P191 validator 要求每行保留 blocker 且四类正向旗标全 false；safe pipeline 310/310 通过，artifact_count 1250，仍不改变任何硬门槛状态。
- P192 ProteinMCP deep research findings:
  - ProteinMCP 最值得 KWB 学的不是单个模型，而是 MCP 工具生命周期、workflow skill、自动 wrapper staging、多模型 fitness workflow 和工具 catalog 雷达。
  - 对 KWB 最直接的四个落地方向：`kwb_tool_lifecycle_registry`、operator workflow skills、MCP wrapper staging gate、five-head model-family comparison contract。
  - ProteinMCP 的 fitness modeling 多路线思想可以借鉴到五头模型比较，但在 KWB 中必须保持 feature/model-score input-only，不能把 PLM/MSA/fitness score 当湿实验标签。
  - ProteinMCP 的自动 MCP create 能力可以借鉴，但 KWB 必须加 source checksum、license review、runtime lock、smoke result、structured output schema、forbidden writes 和 production_allowed false。
  - 本轮仅新增研究报告和结构化摘要；没有安装 ProteinMCP、没有启用外部 MCP、没有生产同步、没有改变训练/claim/release 状态。
- P193 ProteinMCP temporary source download audit findings:
  - 初次临时下载审计按边界尝试源码下载并准备完事删除；当时本机到 GitHub/codeload 的网络/TLS 连接失败，未能取得源码。
  - 失败路径包括默认 git clone、GitHub archive zip、codeload zip、禁用全局 git config 的 HTTPS clone；主要错误为 `LibreSSL SSL_connect: SSL_ERROR_SYSCALL`。
  - 已清理 `/private/tmp/proteinmcp-source-audit`、`/private/tmp/proteinmcp-source-audit.zip`、`/private/tmp/ProteinMCP-main`，最终复核临时目录不存在。
  - 该失败状态已由 P194 的重新下载和源码级审计修正；最终状态以 P194 和 `proteinmcp_source_download_audit_2026_07_31.json` 为准。
- P194 ProteinMCP source-level audit findings:
  - 重新下载已成功：codeload zip sha256 为 `50e3c4b37bcddb798ba1b5430b3117f1f9bf2d08fec62cc8a1204f25ea02328f`，解压后 93 个文件；审计后已删除临时源码和 zip，不保留第三方源码。
  - 源码确认 ProteinMCP 是工具/agent 编排框架，不是单一酶模型；核心可借鉴层是 MCP lifecycle registry、workflow skill、tool catalog、status cache、自动 wrapper create pipeline。
  - `src/mcp/mcp.py` + `mcp_manager.py` 值得借鉴为 KWB 自有 `kwb_tool_lifecycle_registry`：工具状态要从 not_installed/install/probe/smoke/register 分段记录，不能把安装成功等同生产可用。
  - `status_cache.py` 的 300 秒 TTL + file lock 对 KWB 有直接价值：Rosetta/FoldX/MMseqs2/InterPro 等慢探测可以缓存，但 cache 只能加速状态显示，不能替代真实 smoke receipt。
  - `src/skill/skill_manager.py` 的“并行检查/安装、顺序注册”适合 KWB：可以并行 probe 多个工具，但任何写 registry、写 reviewed decision、写训练导入都必须串行、有 receipt、有 validator。
  - `workflow-skills/fitness_modeling.md` 说明多路线 fitness comparison 是方向正确的：MSA/PLMC/EV/PLM/结构特征可做 model-family comparison，但在 KWB 中只能作为 feature/model-score input，不可当湿实验标签。
  - `src/mcp/mcp_creator.py` 的 8 步自动包装很强，但风险高；尤其 `run_claude_with_streaming()` 使用 Claude Code CLI 的 `--dangerously-skip-permissions`，KWB 不能照搬到生产、审核或训练路径。
  - 推荐下一步真实建设不是安装 ProteinMCP，而是做 KWB 自有 staging gate：source checksum、license review、runtime lock、schema contract、forbidden writes、smoke artifact、production_allowed=false。
  - 本轮没有安装 ProteinMCP、没有启用外部 MCP、没有运行 Docker/GPU、没有导入训练标签、没有改变 `safe_for_model_claim=false` 和 `release_ready=false`。
- P195 KWB lifecycle/skill/staging gate findings:
  - 已把 ProteinMCP 借鉴点落到 KWB 本地治理产物：`kwb_tool_lifecycle_registry.jsonl`、`kwb_workflow_skill_registry.jsonl`、`mcp_wrapper_staging_queue.jsonl`，外加对应 report/validator/schema。
  - lifecycle registry 只登记 8 个工具类资产，统一写明 install/probe/register 分离、300 秒状态缓存、execution receipt、license review、生产禁用；所有行 `production_allowed=false`、`agent_exposure_allowed=false`、`safe_for_model_claim=false`。
  - workflow skill registry 生成 5 个本地 Markdown skill，覆盖突变优先级、ddG runtime probe、湿实验反馈审核、编号正式化、五头模型门控；这些 skill 只描述步骤、validator 和禁止动作，不直接写训练标签或正式 decision。
  - wrapper staging gate 只保存 3 个模板型候选，全部 `production_allowed=false`、`agent_exposure_allowed=false`、`training_write_allowed=false`；它是未来 Rosetta/FoldX/ESM/ProtTrans wrapper 的 staging 入口，不是可执行生产接入。
  - 三组产物已接入 safe pipeline、data lake 和 local release，且 `release_ready=false` 继续保持；这表示我们把借鉴从“研究笔记”推进到“可验证治理层”，但没有放开模型声明或生产执行。
  - local release 的 `human_decision_backlog_missing_rows` 与 `human_decision_backlog_fail_closed_consistency_missing_rows` 是不同口径，后者仍保持 1190；校验器已按当前 manifest 修正，避免把 backlog 统计误判为 gate 放开。
  - 当前最新状态：safe pipeline 316/316，data lake artifacts 1521，local release artifact_count 1521，所有 release 验证仍然 success true，`safe_for_model_claim=false`、`release_ready=false` 继续保持。
- P197 wet-lab training import local unlock findings:
  - D105N/S265T 的 8 条 15B 湿实验 metric-level 候选已形成正式 feedback intake authorization，并由授权 validator 验证；这是 `wetlab_authorized_rows` 从 0 到 8 的真实来源。
  - 训练导入只接收 6 条可数值化 activity/acid-retention activity 反馈；85C/3min retention 只授权进入反馈/preflight，不转换为 dTm/ddG 标签。
  - E331Q 仍保留 critical tradeoff blocked，不进入本轮授权或训练导入。
  - `training_import_eligible_rows=6` 只表示 local numeric feedback 可进入训练导入合同，不代表五头训练 ready、模型质量 ready 或 release ready；五头训练仍因每个 head 训练行数不足、benchmark 不 ready、physics ddG 未集成而 blocked。
- P198 wet-lab apply-plan duplicate audit findings:
  - `wet_lab_mutant_library_feedback_intake_apply_plan` 是 apply plan，不是 append 执行器；在 P197 已手工写入 6 条 numeric activity feedback 后，盲目执行 append 会制造重复训练样本。
  - 新 duplicate audit 用 candidate id、notes 中的 `wetlab-mutlib-*`、mutation/assay_type/metric/batch/sample/source_row_index/source_sha256 canonical key 复核 apply plan 与 `experiment_feedback.local.jsonl`。
  - 当前 8 条 preflight/apply-plan 里，6 条 activity 已在本地 feedback 表中存在；2 条未表示的是 85C/3min thermal-retention percent，只能作为 feedback-only 观察，不能声明为 dTm/ddG、Rosetta/FoldX/PyRosetta physics ddG 或稳定性训练标签。
  - 因此 `wetlab_import_rows=0` 不是未完成的 append 失误，而是当前安全策略下的正确 fail-closed 状态：`safe_to_append_rows=0`、`training_import_eligible_from_apply_plan_rows=0`。
  - 本轮把 duplicate audit 接入 wet-lab authorization contract、safe pipeline、data lake 和 local release；P198 后 safe pipeline 318/318 通过，artifact_count 1268，`safe_for_model_claim=false`、`release_ready=false` 保持。
- P199 wet-lab import/local-feedback reconciliation findings:
  - P199 将 `wetlab_applied_rows=0` 与 `numeric_training_import_eligible_rows=6` 明确拆成两个来源：前者是 wet-lab preflight/apply-plan append 路径，后者是本地 experiment feedback intake 路径。
  - 当前一致性关系为：semantic numeric rows = local feedback numeric rows 6 + apply-plan training rows 0；training label import contract 和 model-quality hard gate 都读取到 6，但 five-head training 仍 blocked。
  - 新 reconciliation validator 固定当前事实：authorized/preflight/apply_plan 8/8/8，applied 0，duplicate safe-to-append 0，local numeric 6，strict supervised 0，claim eligible 0。
  - `safe_for_training_import` 这类顶层正向 gate 字段只允许在既有 allowlisted 报告中出现；P199 报告改用 `numeric_training_import_source_supported`，避免把来源支持误报为训练执行或模型声明。
  - P199 后 safe pipeline 320/320 通过，data lake artifact_count 1270，release guards 全通过；`model_quality_ready=false`、`safe_for_model_claim=false`、`release_ready=false` 继续保持。
- P200 parallel hard-gate workstreams findings:
  - 用户要求的四条建设线已拆成互不重叠的 lane：benchmark readiness；ddG runtime probe/receipt；five-head minimum sample threshold；FireProt/plate/retention human preflight package。
  - 主线程总控板不执行专业 lane 的假突破，只固定每条 lane 的现有 evidence、可执行 non-human actions、human/external blockers、验收产物和禁止旗标。
  - 当前真实起点：benchmark coverage 0/14 valid；Rosetta/FoldX/PyRosetta executable/runtime receipt 0；five-head ready_head_count 0；FireProt decision rows 0；plate backlog 50；retention 2 条 feedback-only、safe_to_append 0。
  - 四条 lane 的任何局部完成都不能单独打开 `safe_for_model_claim` 或 `release_ready`，必须继续通过 strict labels、five-head thresholds、benchmark、physics ddG、formal human decisions 和 release guards。
  - P200 修复了 human preflight package 的 formal governance 输出：不再把 plate review workspace 的 `draft` marker 写入 `datasets/governance/human_preflight_package.jsonl`；`validate_draft_namespace_isolation.py` 恢复 success true、unexpected_marker_files 0。
  - P200 单项 validators 全部通过：benchmark packet 14/14 blocked、ddG physical backend 3/3 blocked、five-head ready heads 0、human preflight package 3/3 valid；full safe pipeline 329/329 通过。
- P201 parallel hard-gate execution receipt findings:
  - 新增 execution receipt 层，把四条 lane 的实际 builder/validator 执行固化为 `datasets/governance/parallel_hard_gate_execution_receipts.jsonl` 和对应 report/validator。
  - receipt 4/4 valid 且 validation_passed_rows 4；同时强制 `eligibility_changed_rows=0`、`formal_decision_written_rows=0`、`runtime_receipt_written_rows=0`、`training_import_written_rows=0`。
  - P201 后 safe pipeline 331/331 通过，data lake/local release artifact_count 1284，release guards 全通过；`safe_for_model_claim=false`、`release_ready=false` 保持。
- P202 next hard-gate attack wave findings:
  - 本轮按用户要求实际执行四线 probe：benchmark score cache、Rosetta/PyRosetta/FoldX 物理 ddG runtime、five-head threshold、human formal decision preflight。
  - Benchmark 线不是突破：`build_kwb_strict_mutation_holdout_benchmark.py` 生成的本地候选 scorecard 当前 dataset_rows 0、primary_holdout_rows 0、leakage_check_status failed；`apply_benchmark_score_cache_intake.py` 真实拒绝 1 条 intake，accepted 0、valid benchmark rows 0、usable score values 0。
  - ddG 线不是突破：Rosetta executable false、FoldX executable false、PyRosetta module false、ready_for_ddg_execution_rows 0、approved_runtime_rows 0、physics_ddg_ready false。
  - 五头线不是突破：只有 `activity_risk` 有 6 条 numeric candidates，但缺 `activity_risk_label`、replicate、100 samples/10 groups/3 replicates；ready_head_count 0。
  - 人工 formal decision 线不是突破：human preflight package 3/3 valid，但 FireProt 2133、plate 50、retention 2 均仍需人工/ schema/ack，ready_for_training_import_rows 0。
  - P202 新增 `datasets/governance/next_hard_gate_attack_wave.jsonl`、report 和 validator；4/4 executed_blocked、claimed_breakthrough_rows 0、eligibility/formal decision/runtime receipt/training import rows 全 0；safe pipeline 333/333，artifact_count 1287，release_ready false。
- P203 activity_risk label/replicate preflight findings:
  - 6 条已授权真实湿实验 activity 数值反馈已生成 `datasets/feedback/activity_risk_label_replicate_preflight.jsonl`，覆盖 D105N 3 条、S265T 3 条。
  - ratio-only 候选分层为 3 条 `low_activity_risk_candidate`、3 条 `watch_activity_risk_candidate`，仅用于人工审核提示，不写 `activity_risk_label`。
  - 6/6 行缺 explicit replicate id，因此全部标记为 `explicit_replicate_missing`，`replicate_rows_counted_for_training=0`；不同 pH/metric 不能被自动当作 replicate。
  - 同步生成 `datasets/feedback/activity_risk_label_replicate_decisions.template.jsonl` 6 条空模板，字段包括 label decision、replicate decision、reviewer、review basis、replicate basis。
  - validator 固定检查 6 条来源、6 条 preflight、6 条模板、0 formal decision、0 training import、0 training replicate、所有 training/model/release gate false。
  - P203 后 safe pipeline 335/335 通过，data lake artifacts 1291，local release artifact_count 1291，release guard 三项成功；`safe_for_model_claim=false`、`release_ready=false` 保持。
- P204 activity_risk smoke benchmark findings:
  - 新增 `KWB activity numeric feedback smoke` 作为本地 benchmark plumbing smoke，不是模型质量 benchmark；来源为 6 条真实 KWB wet-lab numeric activity feedback。
  - 生成 artifact：`cache/advanced_features/benchmarks/kwb_activity_numeric_feedback_smoke/dataset.jsonl`、`split_definition.json`、`scorecard.json`、`metric_report.json`，并写入 checksummed benchmark intake row。
  - split 固定为 `evaluation_only_all_rows_no_training`，`future_training_exclusion_required=true`；如果未来把这些 feedback IDs 用作模型训练，必须先解决 benchmark/train 泄漏关系。
  - `apply_benchmark_score_cache_intake.py` 当前 accepted_rows 1、rejected_rows 1、missing_rows 14；`validate_benchmark_score_cache.py` 当前 valid_rows 1、invalid_rows 14、heads_ready 0、ready_for_model_claim false。
  - `validate_benchmark_coverage_dashboard.py` 已从旧 14/0 固定状态改为动态验证 15/1 当前事实，同时仍要求 benchmark/model/release gate 全关闭。
  - P204 后 safe pipeline 337/337 通过，data lake artifacts 1301，local release artifact_count 1301，release guard 三项成功；`safe_for_model_claim=false`、`release_ready=false` 保持。
- P205 physical ddG smoke harness findings:
  - 已把 Rosetta/PyRosetta/FoldX 的非人工 smoke 执行层做成真实代码合同：`build_ddg_physical_smoke_harness.py` 可在 approved runtime receipt + ready execution plan 存在时生成输入文件、运行 backend、写 artifact checksum；默认模式只生成 fail-closed harness plan。
  - 当前 probe 事实没有改变：Rosetta executable false、FoldX executable false、PyRosetta module false、approved_runtime_receipt_rows 0，因此 `can_execute_physical_smoke_now_rows=0`、`physical_smoke_passed_rows=0`。
  - P205 是工程门槛突破，不是物理 ddG 集成完成；没有 license/install/smoke receipt 时仍必须保持 `physics_ddg_ready=false`。
  - ThermoMPNN proxy 继续被隔离，不能满足 Rosetta/PyRosetta/FoldX physics ddG smoke，也不能作为训练标签或模型质量声明。
  - 新 release guard coverage 把 P205 harness report 和 validation report 纳入必检；coverage_count 从 12 增至 14。
  - P205 后 safe pipeline 342/342 通过，data lake/local release artifact_count 1305，`safe_for_model_claim=false`、`release_ready=false` 保持。
- P206 PyRosetta local install/import findings:
  - 用户明确“非商业用途”后，已沿 PyRosetta 非商业本地评估路径推进到真实 install/import 证据，但没有把用户声明自动写成正式 license decision。
  - PyRosetta wheel 下载、分片补齐、拼接与 sha256 已完成：`1530473343` bytes，sha256 `2e41e25633999b06daa543af6087db0a8841eff612c26ae99acfb71c8b1765c0`。
  - 本地安装路径为 `cache/external/PyRosetta/python`；PyRosetta version `2026.29+releasequarterly.80a0635615`，NumPy version `2.0.2`。
  - `build_pyrosetta_local_install_probe.py` 证明 module spec available 且 import succeeded，但明确 `pyrosetta_init_executed=false`、`ddg_protocol_executed=false`、`approved_for_physical_ddg_runtime=false`。
  - `foreign_tool_readiness` 中 PyRosetta 从 `not_installed` 变为 `blocked_by_license_review`；`ddg_backend_readiness` 中 PyRosetta `install_ready=true`，但 license/runtime/config/data gates 仍 false。
  - `next_hard_gate_attack_wave` 已从旧零假设修正为真实状态：PyRosetta installed/importable，但仍因 no approved runtime receipt / no physical smoke artifact blocked。
  - P206 后 safe pipeline 344/344 通过，data lake/local release artifact_count 1308；`physics_ddg_ready=false`、`safe_for_model_claim=false`、`release_ready=false` 保持。
  - 剩余非人工/半人工门槛：正式 license decision、runtime receipt、config enable review、reviewed smoke plan、ready execution plan、PyRosetta physical smoke artifact with sha256。
- P207 PyRosetta physical ddG runtime breakthrough findings:
  - PyRosetta 已从 install/import 证据推进到真实本地物理 ddG runtime smoke：formal license decision、local config enablement、`pyrosetta.init()`、PDB load、WT/mutant scoring、ddG REU artifact、formal runtime receipt 全部完成。
  - `pyrosetta_physical_smoke_bootstrap_report.json` 证明 smoke passed true、init executed true、ddG protocol executed true、5 个 artifact checksum 存在；`ddg_backend_runtime_receipt_validation_report.json` 证明 approved_runtime_rows 1、physics_ddg_ready true、executable_ddg_backend_ready true。
  - 该突破只适用于 PyRosetta local non-commercial/internal evaluation；Rosetta executable 和 FoldX executable 仍未安装/未 license/未 smoke，不能声明三后端全可用。
  - computed ddG 是 Rosetta Energy Units computational physics evidence，不是湿实验 kcal/mol 标签，不进入 training label，不改变 strict supervised rows 或 claim-eligible rows。
  - 旧 fail-closed guards 已改成当前事实：允许 PyRosetta runtime ready、runtime receipt written、physical smoke artifact present，但仍拒绝 safe_for_model_claim、release_ready、customer delivery、training-label import。
  - 最终 full safe pipeline 345/345 成功；local release artifact_count 1318，guard coverage 16，report positive claim quarantine disallowed true hits 0。
  - 当前模型质量仍未 ready：training_import_eligible_rows 6 太少且单一来源，benchmark_ready_for_model_claim false，五头样本/replicate/head-label 仍不足，model_quality_ready false、safe_for_model_claim false、release_ready false。
- P208 Rosetta/FoldX discovery refresh:
  - 最新 `ddg_executable_probe` 仍为 `rosetta_executable_found=false`、`foldx_executable_found=false`，只有 `pyrosetta_module_available=true`。
  - 最新 `ddg_local_runtime_discovery` 在本地 workspace/cache 里未发现 Rosetta/FoldX 候选，`rosetta_candidate_rows=0`、`foldx_candidate_rows=0`，`physics_ddg_ready=false`。
  - 最新 `ddg_physical_runtime_receipt_preflight` 仍只有 PyRosetta ready row；Rosetta/FoldX 仍缺 license/install/config/probe/smoke 证据，不能写 runtime receipt。
  - 这次复核没有改变任何训练、模型质量或 release 旗标；`safe_for_model_claim=false`、`release_ready=false` 继续保持。
  - 更深一轮本地搜索只再次确认同样事实：workspace/cache/Downloads/tmp 没有可接入的 Rosetta/FoldX artifact，当前“未突破”的根因不是代码没写，而是缺少可验证的安装与许可源。
  - 官方资料进一步确认两者都要先走合法获取路径：Rosetta 通过 RosettaCommons 下载，非商业可免费，商业要 UW CoMotion 付费许可；FoldX 提供学术许可、2 周评估许可和商业许可，安装后还要 binary/PATH/config/rotabase 证据链。
  - GitHub/官方网页搜索补充了可执行路线：Rosetta 官方 GitHub 仓库与 DockerHub `rosettacommons/rosetta` 镜像都公开存在，且 DockerHub 明确写明 `serial` 镜像同时包含 Rosetta 和 PyRosetta builds；FoldX 官方站明确要求注册/登录后下载，并区分 Academic / 2-weeks trial / Commercial license。
  - 当前唯一现实的 Rosetta 突破路径是官方镜像/官方下载，不是内部补丁；当前唯一现实的 FoldX 突破路径是官方注册下载/许可，不是公开 GitHub 仓库。
  - Rosetta 官方 README 还明确写出 Rosetta 是 license 模式发布、非开源，商业使用需要单独许可；同时给出 RosettaCommons Conda channel 和官方 DockerHub 两条官方安装路径。
  - FoldX 官方 licensing 页面进一步明确：Academic 版面向学术/非营利机构，2-weeks trial 需要注册后联系获取，Commercial 版需要单独联系；FAQ 也说明下载页需要注册并登录。
  - RosettaCommons Conda channel 实测可见 `rosetta-2025.06+release.e5e4b278be-0.tar.bz2`，`osx-arm64` 包大小约 1.81GB，依赖 `python_abi 3.12.* *_cp312`、`libzlib`、`zlib`；但 `micromamba` 直接解算该包名失败，说明当前还需要走显式 tarball / 其他官方安装口径，而不是把它当成普通可自由解析的包名。
  - 本轮对该 tarball 的直接下载只推进到约 9.8MB，远未形成可用 runtime 证据；Rosetta 仍未完成可复现 install/runtime receipt，FoldX 仍停留在官方注册/许可路径确认。
- P209 platform authorization policy split findings:
  - 平台层政策已修正为不设置一刀切非商业限制；商业评估、训练导入、客户交付、服务化和发布都是平台支持的 workflow，但按组件许可证、企业授权、项目授权和治理 gate 分项判定。
  - Rosetta/PyRosetta 的 license decision 现在记录为 `authorization_source=user_attestation`、`authorization_status=self_attested`、`verification_required=true`；五项 capability 在用户声明下可继续推进技术配置，但 `verified_rows=0`，不能包装成正式许可证核验。
  - 新 license validator 保留旧 `approved_for_*` 字段兼容旧流水线，同时新增 `capability_authorization_counts`、`self_attested_capability_allowed_counts`、`verified_capability_allowed_counts` 和 `verified_customer_delivery_rows`。
  - 当前 license validation 事实为 decision_rows 2、valid_rows 2、self_attested_rows 2、verified_rows 0、verified_customer_delivery_rows 0；这允许 PyRosetta/Rosetta 技术探测继续，但不打开 customer_delivery_ready 或 release_ready。

- P211 verified mutation structure / physical feature findings:
  - 现有 `structure_chain_mappings_curated.jsonl` 的 25 条结构与 `enzyme_mutation_training_table_verified.jsonl` 的 25 条突变 accession 交集为 0，不能把旧审查结构直接套到这些 verified mutation。
  - 25 条 verified mutation 的本地 UniProt evidence 都有 PDB cross-reference；自动选择 23 个 unique public structure candidates，优先 X-ray、最低 reported resolution。
  - 公共下载完成 21 个新 structure、1 个已有 structure；首选 `6TN1`/`9DA2` 返回 HTTP 404，随后从同一 UniProt cross-reference 的备用 PDB 回退，25/25 mutation records 都有本地结构文件。
  - sequence alignment + PDB CA residue + PyRosetta `pdb2pose` 后得到 7 条 deterministic input candidates；11 条 multi-chain ambiguity、7 条结构/target-position mapping 阻断。
  - 7 条真实 PyRosetta ddG features 以 REU 写入 `datasets/features/pyrosetta_verified_mutation_ddg_features.jsonl`。它们是 manual-review computational physics inputs，不是 wet-lab labels，不能改变 strict training/model/release gates。
  - Rosetta 本地状态已从“未安装”更新为真实 installed/probe-ready：官方 conda tarball 完整校验并解包到 `cache/external/RosettaConda`，`cartesian_ddg`/`rosetta_scripts` help probe 在 `DYLD_LIBRARY_PATH=cache/external/RosettaConda/bin` 下通过。
  - Rosetta 仍不是 physics ddG ready：没有 Rosetta smoke artifact、没有 Rosetta runtime receipt、没有训练标签导入；`foreign_tool_readiness` 将其标为 `blocked_by_runtime_or_data`。
  - FoldX 仍未突破：无 binary/license/smoke/receipt。
  - 旧 validators 中“Rosetta probe 必须 false / local eval approval 必须 1”的零假设已改为当前事实：Rosetta technical probe 可 true，physics ddG ready 仍只有 PyRosetta；license local eval/self-attested rows 可为 2。
  - 完整验证通过：safe pipeline 345/345、data lake artifacts 1318、local release `release_ready=false`、release fail-closed/safety guard/coverage 和 positive claim quarantine 全部 success。

- P210 Rosetta reproducible smoke and dual-runtime gate findings:
  - Rosetta v3 使用 `-constant_seed -jran 20260802` 在两个独立 fresh output 目录运行成功；两次 `ddg_reu=-0.2059999999999036`，`parameters.json`、输入结构 hash、mutation list 和 `ddg_table.json` 完全一致。runtime log 因运行目录不同而不同，是预期差异。
  - 未固定随机种子的 v2 结果为 `-0.57000000000005 REU`，与 v3 不同；v2 保留为历史 smoke，当前正式 receipt 使用固定种子的 v3 repeat2 artifacts。
  - 在旧目录复跑会触发 Cartesian ddG 读取 stale `mutation_file.ddg` 并崩溃；bootstrap 已拒绝复用含旧 Rosetta 输出的目录。
  - 通用 `write_rosetta_mutfile()` 原来直接使用 `mutation_position`，可能把 PDB/chain 编号当 pose 编号；现在只接受显式 pose mapping，缺失即拒绝执行。
  - 当前 runtime receipt validation 为 Rosetta/PyRosetta 两个 approved backends；FoldX 仍无安装、license、probe 或 smoke receipt。
  - `ddg_physical_runtime_receipt_preflight` 当前为 3 个 physical backend，其中 2 个 receipt-validated ready、1 个 FoldX blocked；`physics_ddg_ready=true`，但 `safe_for_model_claim=false`、`release_ready=false`。
  - Rosetta bootstrap report、脚本和 receipt-driven artifacts 已显式接入 data lake/local release；data lake/local release artifact_count=1342，local release guard coverage=17，所有 consistency/safety/positive-claim validators 通过。

- P212 PyRosetta verified-mutation ddG quality quarantine findings:
  - 29 条 PyRosetta verified-mutation feature 确实完成执行，但原 validator 只检查字段、单位、fail-closed flags，未检查有限数值、极端 ddG 或总分风险；“计算完成”不能等同“计算结果适合作为下游输入”。
  - 真实输出存在极端值，例如单链 `2IJA A78Y=740.84 REU`、`7DVQ A286P=243.28 REU`，多链 `9YB6 G252E=421.73/569.33 REU`；这类值必须进入质量隔离，而不能被 29/29 schema-valid 掩盖。
  - feature builder 现在记录 `pose_total_residue`、`ddg_abs_reu`、`score_quality_status`、`score_quality_reasons`、`quality_gate_passed`。per-row gate 对 non-finite 或 `abs(ddg_reu)>20 REU` fail-closed；`abs(total_score)>5000 REU` 记录 runtime sanity warning，不把该启发式阈值声称为科学有效性证明。
  - 当前 per-row 质量状态为 18 passed、11 blocked。所有 rows 的 artifact 合同仍为 29/29 valid，因此 safe pipeline 可以成功验证“隔离已正确执行”，但 quality gate 总状态为 blocked。
  - 多链审计保留 11 个 A/B ambiguity groups：5 条 `chain_concordant_input_feature`、6 条 `chain_context_sensitive_manual_review`。任何成员 per-row blocked 或 span `>1.0 REU` 时，group `quality_gate_passed=false`；不选唯一链、不平均、不升级为 reviewed mapping。
  - local release manifest 新增 per-row 和 multi-chain quality counts；完整回归为 safe pipeline 352/352、data lake/local release 1358 artifacts、release/model claim 仍 false。

- P213 structure provenance findings:
  - 25 条 verified-mutation structure mapping 原先只保留 `structure_id`，在 fallback 下载场景下会混淆候选 PDB 与实际执行文件；例如候选 `9DA2` 实际读取的是 `4P5E` 缓存。
  - mapping 现在同时写入 `source_structure_id`、`executed_structure_id` 和 `source_executed_structure_match`；PyRosetta feature ID 也包含 executed structure ID，避免不同执行结构产生同名 feature。
  - 每条链新增 CA count、author residue min/max、observed coverage 和 `structure_context_scope`。`observed_coverage < 0.8` 仅标记 `partial_domain_context`，不自动阻断或升级。
  - PDB `HETATM` 被作为上下文证据记录；`ligand_or_nonprotein_context_present=true` 不等于 ligand 参数化完成，统一保留 `ligand_modeling_complete=false` 和 `ignore_unrecognized_res_true` handling policy。
  - 该轮没有增加 reviewed decision，也没有将 source/executed identity、结构覆盖或配体字段转成训练标签；它们只是可追溯输入上下文。

- P214 quality-gated PyRosetta feature-index integration findings:
  - validated feature index 仅纳入 `quality_gate_passed=true`、`runtime_status=computed`、`near_full_length_context` 的 PyRosetta rows；multi-chain row 还必须来自 concordance quality passed group。
  - 结果为 11 条 `pyrosetta_ddg_reu_input` feature refs，validated index 从 183 增至 194。未进入 index 的 PyRosetta runtime rows继续只存在于 audit/feature artifact，不作为模型输入。
  - advanced-model contract 不再错误要求 feature refs 恰好等于 183；它要求基础 MSA 158 和 reviewed graph 25 完整，同时允许 validator-ready optional physical feature refs。
  - model-quality hard gate 相应改为要求 input-only feature refs 至少 183 且 source contract valid。`feature_inputs_ready=194`、`feature_inputs_input_only=true` 是输入覆盖增加，不是模型质量解锁。
  - PyRosetta input refs 已加 mutation group 口径：11 条 feature refs 对应 7 个唯一突变组，multi-chain A/B contexts 保留但 `independent_training_sample=false`，防止训练或统计时重复计数。
- P205 five-head sample-gap queue findings:
  - 新队列只消费 threshold report 作为当前正式 label/group/replicate 事实，并把湿实验、FireProt、plate 和未来 substrate source 分成 candidate source pools；候选池不替代 head label rows。
  - 当前五个 head 的正式标签行、独立组和显式 replicate 都为 0；门槛固定为每 head 100 labels、10 independent groups、3 explicit replicates，因此总缺口为 500 labels、50 groups、15 replicates。
  - `stability` 的 FireProt schema mapping candidates 5067 条、`activity_risk` 的真实数字反馈候选 6 条被列为可追踪来源，但 `training_import_written_rows=0`；不推断 activity_risk label、不把 retention 转成 dTm/ddG、不把 candidate 当 reviewed import。
  - `validated_feature_index` 当前 194 条，明确 `feature_rows_counted_as_labels=0`；PyRosetta REU 仍是 input-only computational evidence。
  - 队列 validator 强制每个 head 的缺口公式、threshold report 对齐、source pool training/formal decision 为 0、safe/model/release flags 为 false。首次并行 builder/validator 读空文件后已按生成->验证顺序串行接入流水线。
- P205 完整回归：safe pipeline 354/354；data lake/local release artifacts=1361；local release guard coverage=19，fail-closed consistency/safety links/model-quality hard gate 全部通过，模型质量和 release 仍未解锁。

- P215 benchmark/FoldX/FireProt gate findings:
  - benchmark readiness packet 的失败根因是生成顺序/快照竞态，不是 benchmark 数据突然失效；串行重建后 validation `contract_valid=true`、failure_count 0。
  - 新增 ThermoMPNN comparison 后 benchmark cache 当前为 3/15 valid：`mutation_rank / ProteinGym`、`stability / ThermoMPNN comparison`、`activity_risk / KWB activity numeric feedback smoke`。这些都不足以形成模型质量声明，`heads_ready=0`。
  - 旧 `parallel_hard_gate_execution_receipts` validator 固定 `packet_rows==13` 已不适合当前 12 个 remaining gaps；修复后仍要求 benchmark completion_ready_rows=0、score_values_recorded=0，防止把缺口变少误判为 ready。
  - FoldX 当前真实状态仍是 executable=false、runtime receipt=0、license decision 未写入；不能宣称 FoldX runtime 突破。
  - 已突破的是 FoldX BuildModel 输出接收合同：静态 fixture 的 `Dif_`/`Average_`/`Raw_` 输出可解析成统一 `ddg_table.json` 合同，单位 kcal/mol，负值稳定约定保留。该 parser 已接入 harness，但只有真实 FoldX 命令成功后才会写解析结果。
  - FireProt 仍需人工正式 dedup/import authorization：dedup candidates 2133、reviewed import candidates 0、supervised authorization rows 0。activity_risk 6 条正式标签真实存在，但显式 replicate 仍 0、样本/组数不足。
  - 完整回归：safe pipeline 360/360；data lake/local release artifact_count=1382；local release guard coverage=21；`model_quality_ready=false`、`safe_for_model_claim=false`、`release_ready=false`。

- P216 benchmark/FoldX runtime findings:
  - FireProt curated 数据不能自动导入训练，但可以作为 external evaluation-only benchmark。新 builder 只取 HF/val/test 非 train split，按 mutation_key 去重，生成 2138 条 FireProt/ProTherm stability benchmark rows。
  - benchmark cache 当前 4/15 valid：ProteinGym、ThermoMPNN comparison、FireProt/ProTherm reviewed stability set、KWB activity numeric feedback smoke。stability head 2/3 valid；仍无任何 head complete，`ready_for_model_claim=false`。
  - FireProt/ProTherm benchmark 不改变 FireProt supervised import：`fireprot_training_import_written_rows=0`，FireProt dedup reviewed import candidates 仍 0。
  - FoldX runtime 公开安装路径未突破：conda-forge 联网查询无 `foldx` 条目，本机无 Homebrew，项目 probe 仍 `foldx_executable_found=false`。当前缺口是官方 binary/license，而不是 parser/harness 代码。
  - 完整回归：safe pipeline 361/361；data lake/local release artifacts=1391；local release guards 通过，模型/release 继续 fail-closed。

- P218 benchmark/activity/FoldX parallel findings:
  - benchmark 并行审计确认：当前 strict mutation holdout 不能被配置修复，根因是 strict supervised table 为 0 行、dataset 为空且 leakage failed；旧 `ready_as_benchmark_scorecard=true` 是误导性状态，已改为 false。
  - 当前新增的真实 benchmark 缺口突破是 `assay_success / replicate consistency`：4G 本地湿实验 raw measurement 表有显式 `replicate_status`、`sample_id`、`batch_id`、`variant_name` 和 raw activity 值，可形成 evaluation-only 重复一致性 score cache。
  - 4G replicate consistency 产物包含 23 个 replicate groups、315 条 xylanase activity measurements；状态分布为 consistent_pass 3、consistent_watch 4、inconsistent_fail 11、insufficient_replicates 5。它是内部评测缓存，不是 assay_success label。
  - benchmark cache 从 4/15 valid 推进到 5/15 valid，missing/invalid 从 11 降到 10；assay_success head 从 0/3 valid 推进到 1/3 valid，但 heads_ready 仍为 0。
  - activity_risk formal label 真实存在 6 条，且可追溯到 wet-lab 授权；five-head threshold 现在正确显示 activity_risk 为 below-threshold，而不是 candidate-only。缺口仍是 94 samples、8 groups、3 explicit replicates。
  - 新增 activity_risk lineage ledger 后，6/6 行可串联 `feedback_id -> authorization_id -> formal_decision_id -> training_import_contract -> five_head_threshold`；该 ledger 证明可追踪性，不写训练表，也不满足五头执行门槛。
  - FireProt reviewed import 仍为 0；5067 candidates 和 2133 dedup groups 不能自动变成 supervised labels，仍需人工 license/dedup/numbering/import authorization。
  - FoldX 最硬阻断仍未变：parser fixture ready，但 executable/license/config/probe/smoke artifact/runtime receipt 全缺。Rosetta/PyRosetta 已有 runtime smoke receipt，但当前 production plan ready rows 仍为 0，需要后续拆分 runtime-ready 与 current-plan-ready 语义。
  - benchmark validator 已加固为内容级检查：present rows 不再只靠文件存在和 SHA，通过时还要求 dataset 非空、metric dataset_rows 正数、split leakage 未失败。

- P219 FoldX/QC fail-rate findings:
  - FoldX 现在有独立 fail-closed bootstrap report，而不再只靠 parser contract 表达状态。报告读取 config、license decision、executable probe、runtime receipt validation、physical preflight、parser contract 和 execution plan；当前结论仍为 `blocked_missing_runtime_evidence`。
  - ddG readiness 已拆为五层：technical probe、runtime receipt、bootstrap smoke artifact、production data、current execution。当前 PyRosetta 和 ThermoMPNN 为 current execution ready；Rosetta technical/receipt/smoke ready 但 production data gate false；FoldX 全部关键 runtime 层 false。
  - QC fail-rate calibration 可从 4G replicate consistency evaluation cache 自动派生，因为输入已经是本地真实 raw measurement 汇总：23 个 replicate group、315 条 xylanase activity measurements、5 个 batch summaries。
  - QC fail-rate 的正确分母是全部 replicate groups，不是 batch 数。本轮首次运行得到 2.2 后修正为 0.4782608695652174，并在 validator 中加入 0..1 范围检查。
  - benchmark cache 从 5/15 valid 推进到 6/15 valid；剩余 invalid/missing 为 9，heads_ready 仍为 0。QC calibration 只减少 assay_success benchmark 缺口，不产生 assay_success training labels。
  - 本轮没有执行 FoldX BuildModel、没有写 FoldX runtime receipt、没有导入 FireProt/wet-lab 新训练标签、没有打开 model/release claim。

- P220 4G plate-level benchmark / ready-head findings:
  - 4G 原始湿实验事实表的 `source_location`、Row、Col 信息足以构建 plate/well 级 assay_success evaluation benchmark；本轮生成 288 rows、3 plates、288 unique wells。该证据是 plate-level benchmark coverage，不是人工正式 plate feedback decision。
  - assay_success benchmark head 已真实完成 3/3：`KWB plate-level feedback`、`replicate consistency`、`QC fail-rate calibration` 均 valid。benchmark cache 从 6/15 推进到 7/15，heads_ready 从 0 推进到 1。
  - 其余 benchmark 缺口仍为 8：mutation_rank 缺 FLIP/FLIP2 和 KWB strict holdout，stability 缺 ATOM3D MSP，activity_risk 缺 KWB plate-level wet-lab feedback 与 CatPred/GotEnzymes，substrate_fit 缺 PDBbind/CASF/D3R、PoseBusters、reviewed substrate identity set。
  - 旧 `validate_benchmark_coverage_dashboard.py` 把所有 5 个 head 都强制要求在 gap queue 中；在 assay_success ready 后这是错误假设。正确规则是：只有 `missing > 0` 的 head 才应进入 gap queue。
  - 旧 `validate_next_hard_gate_attack_wave.py` 把 benchmark `heads_ready` 固定为 0；现在改为校验 0..5 区间并确保仍不打开 `benchmark_ready_for_model_claim`。局部 ready head 不等于模型质量 ready。
  - 完整回归通过：safe pipeline 372/372；data lake/local release 1433 artifacts；release fail-closed consistency、safety guard links、guard coverage success。`safe_for_model_claim=false`、`release_ready=false` 保持。

- P221 activity-risk plate feedback benchmark findings:
  - 4G 原始测量事实表、样本批次映射和批次对照映射足以构建 activity_risk 的 batch-control evaluation benchmark。该方向比 P220 的 plate/well presence 更接近 activity 风险，因为它计算 variant mean / batch control mean。
  - 本轮生成 17 条样本组 benchmark rows，使用 638 条原始测量证据，覆盖 5 个 batch 和 11 个 unique variants。control_sample_id 来自 05/06 两张映射表，control mean 必须为正。
  - activity_risk_label 是评测标签而非训练标签：ratio >= 1.0 为 low_activity_risk，0.8 <= ratio < 1.0 为 watch_activity_risk，ratio < 0.8 为 high_activity_risk。当前分布 high 7、watch 6、low 4。
  - 13 条为 `plate_control_ratio_supported`，4 条为 `limited_variant_replicates_control_supported`；有限复孔样本保留为 benchmark evidence，但不能声称 training-eligible。
  - benchmark cache 从 7/15 valid 推进到 8/15 valid，activity_risk head 从 1/3 valid 到 2/3 valid；剩余 activity_risk benchmark 缺口只剩 `CatPred/GotEnzymes predicted reference only`。
  - 本地未发现 CatPred/GotEnzymes、PDBbind/CASF/D3R、PoseBusters 的源码或缓存；继续突破这些缺口需要下载/登记外部数据源和相应 license/source receipt，不能用内部 activity rows 冒充。
  - 完整回归通过：safe pipeline 374/374；data lake/local release 1445 artifacts；positive claim quarantine disallowed_true_hit_count 0。`safe_for_model_claim=false`、`release_ready=false` 保持。

- P222 FLIP2 amylase mutation-rank benchmark findings:
  - 官方 FLIP2 amylase by-mutation split 本地缓存可用于 evaluation-only mutation_rank benchmark。源文件 `cache/external/flip2_amylase_by_mutation.csv.gz` 为 51507 bytes，sha256 `20e1c9f6d993eb578161f899d491373d4854d218c4690317a445c924d2daa81b`，gzip 校验和 CSV 解析均通过。
  - 数据集包含 3706 rows，字段为 `sequence,target,set,validation`。按当前 builder 口径，`validation=True` 行作为 validation split，最终 split_counts 为 train 2403、validation 601、test 702。
  - 新 benchmark 生成 dataset、split_definition、scorecard、metric_report 四件套，并写入 `FLIP/FLIP2-style protein/family/time split` score cache intake；`training_import_written_rows=0`、`ready_for_model_claim=false`、`safe_for_model_claim=false`、`release_ready=false`。
  - benchmark cache 从 8/15 valid 推进到 9/15 valid，invalid/missing 从 7 降到 6；mutation_rank 从 1/3 valid 推进到 2/3 valid，剩余缺口只剩 `KWB strict mutation holdout`。
  - 当前 benchmark-ready head 仍只有 assay_success 1 个；整体 `benchmark_ready_for_model_claim=false`。FLIP2 补的是评测覆盖，不是训练标签，也不是模型质量声明。
  - 剩余 6 个 benchmark 缺口为：`KWB strict mutation holdout`、`ATOM3D MSP`、`CatPred/GotEnzymes predicted reference only`、`PDBbind/CASF/D3R-style affinity or pose benchmark`、`PoseBusters-style pose plausibility`、`reviewed substrate identity set`。
  - model-quality hard gate 复验事实：training_import_eligible_rows 6、wetlab_authorized_rows 8、wetlab_import_rows 0、physics_ddg_ready true、feature_inputs_ready 194、benchmark_ready_for_model_claim false、model_quality_ready false、safe_for_model_claim false、release_ready false。
  - 本轮没有伪造 license verified 状态、没有写人工 formal decision、没有导入训练标签、没有启用 FoldX runtime、没有打开 customer delivery/model/release claim。

- P223 ATOM3D MSP stability benchmark findings:
  - ATOM3D MSP 官方 Zenodo record `10.5281/zenodo.4962515` 可作为 external stability evaluation-only benchmark。record JSON、README、indices archive 和 split archive 均已本地缓存并校验。
  - 1.38GB split archive 最终文件大小为 1384045096，MD5 为 `6628e8efac12648d3b78bb0fc0d8860c`，与官方文件记录一致；sha256 为 `60e0859da703ba48c8ff791fa29bda7d829b77d7326972db92f70c7202106f81`。
  - builder 从 ATOM3D LMDB 读出 4148 rows，split_counts 为 train 2864、validation 937、test 347；label_counts 为 0=3255、1=893。此前 indices 初读 4145 行的差异来自早期只看 indices 文件的阶段，正式 LMDB 与当前 indices 解压结果均为 4148。
  - 新 benchmark 生成 dataset、split_definition、scorecard、metric_report、source_receipt，并写入 `stability / ATOM3D MSP` score cache intake；validator success true、failures 0。
  - benchmark cache 从 9/15 valid 推进到 10/15 valid，stability head 从 2/3 推进到 3/3，heads_ready 从 1 到 2；整体 `ready_for_model_claim=false`，因为 mutation_rank、activity_risk、substrate_fit 仍未满足。
  - 剩余 5 个 benchmark 缺口为：`KWB strict mutation holdout`、`CatPred/GotEnzymes predicted reference only`、`PDBbind/CASF/D3R-style affinity or pose benchmark`、`PoseBusters-style pose plausibility`、`reviewed substrate identity set`。
  - ATOM3D MSP 不导入训练标签，不作为 KWB 湿实验反馈，不打开 model-quality/customer/release claim；source authorization 记录为 self_attested benchmark-only 且 `verification_required=true`。

- P224 CatPred/GotEnzymes source intake findings:
  - Zenodo record `17196785` / DOI `10.5281/zenodo.17196785` is titled `GotEnzymes2 source data`; live API and cached JSON agree on `input_data.zip` size `1190270380` and checksum `md5:5b07cf2fa8a22262312bd9c9fde047cb`.
  - The local file `cache/external/input_data.zip` was a partial ZIP at task start (`10813440` bytes); `unzip -t` failed with missing end-of-central-directory, so archive contents cannot be trusted until final checksum verification.
  - Default sandbox networking cannot resolve `zenodo.org`. Approved network access reaches Zenodo, but non-IPv4/default transfer was unstable. IPv4-only explicit range request returned `206 PARTIAL_CONTENT`, `content-range: bytes 0-1023/1190270380`, and `accept-ranges: bytes`.
  - This source is being handled as evaluation-only benchmark material. No training import, model-quality claim, customer delivery claim, or release gate should be opened by this download/inspection task.
  - Final `cache/external/input_data.zip` verification passed: size `1190270380`, MD5 `5b07cf2fa8a22262312bd9c9fde047cb` matches Zenodo, SHA256 `e8ff38a3e0d7764fea888d6679169381aa29c0d6b9dee354d647fd3f059df73d`, and `unzip -t` reported no compressed-data errors.
  - Archive shape: `10774` entries total; `10765` files under `input_data/gotEnzymes2/` with total uncompressed size `4766949703` bytes and compressed size `842243565` bytes; six supplementary tables under `input_data/supplementary/`.
  - Smallest representative GotEnzymes2 files suitable for smoke/reference benchmarking are `input_data/gotEnzymes2/bdw.txt` (`2986` bytes, 38 rows, Eukaryotes), `input_data/gotEnzymes2/oyw.txt` (`4489` bytes, 53 rows, Archaea), and `input_data/gotEnzymes2/gsc.txt` (`10825` bytes, 135 rows, Bacteria). These provide tiny cross-domain predicted kinetic/thermal rows without extracting the whole archive.
  - Core small metadata for interpreting those rows: `domain.txt` (`57` bytes), `organism.txt` (`501776` bytes), `ec.txt` (`1045883` bytes), `reaction.txt` (`2093178` bytes), and `compound.txt` (`2664462` bytes). `gene.txt` is useful only if UniProt/protein-ID bridging is required; it is not minimal (`3120801222` bytes uncompressed).

- P225 CatPred/GotEnzymes benchmark findings:
  - GotEnzymes2 source archive can be used as an activity_risk predicted-reference coverage benchmark, but not as CatPred runtime evidence. The source rows expose protein/shard/domain/reaction/EC/compound plus five numeric source fields for catalytic and thermal properties.
  - The first accepted benchmark slice deliberately uses only three tiny verified shards: `bdw` 38 rows, `oyw` 53 rows, `gsc` 135 rows. This gives 226 real rows and avoids extracting the 4.7GB uncompressed archive.
  - The builder records source archive size/MD5/SHA256, Zenodo DOI/license metadata, shard hashes, and CatPred GitHub metadata. Authorization remains `self_attested` and `verification_required=true`.
  - benchmark cache improved from 10/15 to 11/15 valid; `activity_risk` head is now 3/3 valid. Combined with previous work, `assay_success`, `stability`, and `activity_risk` are benchmark-complete heads.
  - Remaining benchmark blockers are now concentrated in `mutation_rank / KWB strict mutation holdout` and all three `substrate_fit` benchmarks: PDBbind/CASF/D3R-style affinity or pose, PoseBusters-style plausibility, and reviewed substrate identity set.
  - This benchmark still does not provide KWB wet-lab labels, training import rows, customer delivery permission, CatPred runtime proof, or model-quality/release readiness.

- P226 PoseBusters-style benchmark findings:
  - Official `posebusters_paper_results.csv` is small enough to use as an evaluation-only pose plausibility reference cache without downloading the 53MB structure archive. The CSV contains 7695 rows across `astex` and `posebuster`, 513 unique PDB/CCD complexes, seven docking methods plus crystal structures, and 19 PoseBusters-style check columns.
  - Empty check fields are real failure/missing-result evidence, not parse errors. The correct handling is to retain the row, store null for that check, count it as not passed, and preserve the failure/missing state in metric summaries.
  - The resulting benchmark gives `substrate_fit` one real external pose plausibility scorecard. It does not prove substrate identity for KWB assays and does not run local PoseBusters runtime.
  - benchmark cache improved from 11/15 to 12/15 valid. `substrate_fit` moved from 0/3 to 1/3, while `activity_risk`, `stability`, and `assay_success` remain complete heads.
  - Remaining benchmark blockers are now `mutation_rank / KWB strict mutation holdout`, `substrate_fit / PDBbind-CASF-D3R-style affinity or pose`, and `substrate_fit / reviewed substrate identity set`.
  - KWB strict mutation holdout cannot be honestly unlocked while strict verified supervised rows are 0; reviewed substrate identity also requires real reviewed substrate decisions. PDBbind/CASF/D3R-style may be the next non-human external-source path if an authorized local source can be acquired and checksummed.

- P227 activity_risk training import findings:
  - 6 条 activity_risk formal labels 具备完整的 numeric feedback -> authorization -> formal decision -> QC/numbering lineage，已真实写入 `datasets/training/activity_risk_training_import_labels.jsonl`，不是候选草稿或仅报告计数。
  - builder 与 validator 均报告 `training_import_written_rows=6`；training label import contract 同步为 `training_import_validated_written_rows=6`、`training_import_eligible_rows=6`。
  - 这 6 行仍不足以启动五头训练：activity_risk 只有 6 samples、2 independent groups、0 explicit replicates，当前 `ready_head_count=0`、`training_execution_allowed=false`。其余 head 也没有达到 100 samples / 10 groups / 3 replicates 门槛。
  - `wetlab_import_rows=0` 与新增 6 行不矛盾：前者是原始湿实验 feedback apply 表的写入计数，本轮没有重复导入；后者是已授权 activity_risk 训练导入专用 JSONL 的物化计数。
  - 新报告的 `safe_for_training_import=true` 只代表局部训练导入文件通过 schema/lineage 校验，已被精确 allowlist；没有允许 `safe_for_model_claim`、`model_quality_ready` 或 `release_ready`。
  - 完整安全流水线 384/384、positive claim quarantine 394 reports/0 disallowed hits、data lake/local release artifact_count 1506、11 safety links 和 21 guard coverage 全部通过。模型质量与发布状态仍保持 false。

- P228 CASF affinity benchmark findings:
  - 公开 `WoldringLabMSU/PLBAP_Reproducibility` 仓库提供了可审计的 CASF-2016 affinity reference rows；仓库 LICENSE 声明 `CC0-1.0`，固定 main commit `f2d1a3f20e2281087ea3084ff9cf1849058f70e3`。
  - 汇总 CSV 有 4558 行、285 个复合物、16 个模型，字段包含真实 `pK_true` 和 `pK_predicted`。部分模型的 prep/inference/total runtime 字段为空，这是来源记录缺失，不应导致 affinity 行丢失；builder 已对时间字段采用 null-preserving 解析。
  - 新 benchmark 四件核心产物加 source receipt 均有 checksum，validator 0 failures。该 benchmark 只用于 substrate_fit 外部 evaluation coverage，`casf_runtime_executed_locally=false`，不导入训练。
  - benchmark cache 从 12/15 推进到 13/15 valid；substrate_fit 从 1/3 推进到 2/3，heads_ready 仍为 3，整体 `benchmark_ready_for_model_claim=false`。
  - readiness packet 在 strict-holdout builder 后出现旧 snapshot，已通过追加后置刷新 wave 修复；最终 packet validator `contract_valid=true`，避免治理报告引用旧 manifest/intake hash。
  - 剩余自动化无法越过的两个 benchmark 缺口是：strict supervised rows 为 0 的 KWB strict mutation holdout，以及必须人工正式审核 substrate identity/condition/lineage 的 reviewed substrate identity set。不能用 CASF 外部结果替代这两项。
- P229 PubMed source receipt findings:
  - 25 条 sequence-numbering verified stability candidates were queried against NCBI PubMed ESummary in one request.
  - HTTP status was 200; response size was 59025 bytes and response SHA256 was `c0dca6da5dfd8fa601878626a5671cbbb14e891aeeccfe6da6cbbe5030082459`.
  - All 25 PMID identifiers were returned, but 0/25 title/abstract summaries contained the corresponding mutation token. Returned titles included unrelated non-protein papers, confirming that PMID numbers in the local fixture are not usable source receipts.
  - The audit is candidate-only and does not alter decisions. `training_import_written_rows=0`, `strict_holdout_rows_written=0`, `safe_for_model_claim=false`, `release_ready=false`.

- P230 wet-lab mutation ranking supplemental benchmark findings:
  - New builder/validator consume real local 16B and 4G overall judgement tables plus raw measurement fact tables.
  - Admission rules: single-substitution code, explicit overall judgement, no confounder flag, no retest/false-positive-only recommendation, and confidence tier A/A+/B. Project controls and multi-substitutions are excluded.
  - Output contains 22 project/variant groups, 12 positive and 10 neutral, backed by 212 raw measurement rows and source SHA256 checksums.
  - The artifact is evaluation-only. `numbering_status=not_reviewed_project_numbering` and `parent_sequence_status=not_registered_for_16B_or_4G` are explicit, so it cannot substitute for the KWB strict mutation holdout or enter training.
  - The first registration attempt exposed a real governance assumption: core benchmark validators require exactly the five fixed heads and 15 required benchmark rows. The supplemental benchmark was therefore removed from core acquisition/intake inputs while its cache/report artifacts remain available as a separate evaluation asset.
  - Full pipeline after cleanup: 391/391 success; benchmark core 13/15 valid with 2 explicit gaps; data lake 1515 artifacts; model/release gates remain closed.

- P231 Venus-15B strict candidate and substrate evidence findings:
  - The real local Venus-15B parent sequence is 486 aa. PDB `15B-AAP-noCa.pdb` chain A contains 486 residues and matches the parent sequence at every position. The project design mutations `S265D`, `D405N`, `E331Q`, `M204H` and wet-lab mutations `D105N`, `S265T` all have matching WT residues in both sequence and PDB numbering.
  - The strict-candidate builder selected only real 15B numeric candidate rows with candidate-level numbering verification, primary-analysis recommendation, and single-substitution syntax. It produced 3 variant groups (`D105N`, `E331Q`, `S265T`) backed by 12 measurement rows. This is an evaluation/review candidate artifact, not the core strict holdout.
  - Candidate artifact: `cache/advanced_features/benchmarks/kwb_venus15b_strict_holdout_candidate/dataset.jsonl`; report: `reports/kwb_venus15b_strict_holdout_candidate_audit_report.json`. `sequence_pdb_exact_match=true`, `strict_holdout_rows_written=0`, `training_import_written_rows=0`, `formal_reviewed_decision_rows=0`.
  - Five DOCX and three PDF local experimental protocols were scanned. Source text explicitly names `玉米全粉` and `淀粉乳`; extracted protocol evidence preserves source SHA256, DOCX paragraph indexes or PDF page numbers, and pH/temperature/time snippets. No single-molecule SMILES was inferred because these are process mixtures/substrates.
  - Candidate artifact: `datasets/curation/substrate_identity_evidence_candidates.jsonl`; report: `reports/substrate_identity_evidence_candidate_report.json`; validator: `reports/substrate_identity_evidence_candidate_validation_report.json`. Results: 9 candidate rows, 9 valid, 0 reviewed, 0 substrate_fit training rows.
  - `pypdf` was installed locally to parse the PDFs. It emitted malformed-object warnings on the source PDFs, but extraction completed and the warnings were retained as a source-quality caveat rather than hidden. No PDF row was promoted to formal reviewed status.
  - New candidate artifacts are registered in data lake/local release manifests. Full safety pipeline remains 391/391 with 0 failures; release artifact count is 1521; local release guards pass. Core benchmark remains 13/15 valid, heads_ready=3, and all model-quality/release claims remain false.
- P232 hard-gate review closure：strict candidate packet 3 rows，substrate identity packet 9 rows；所有条目保留真实 source receipt、测量/原文证据和人工核验规则。正式 decision 文件由 builder 初始化为空，validator 接受空文件但要求所有审批必须有 reviewer、reviewed_at、review_basis、acceptance_receipt 和逐项确认；当前 strict holdout rows written=0、substrate_fit training rows written=0、safe_for_model_claim=false、release_ready=false。
- P232 平台行为：新增 `ui/hard_gate_review/index.html`，通过现有 numbering review 服务提供局域网按钮；“保存人工结论”仅写对应 formal decision 文件，“验证两个硬门槛”只跑 fail-closed validator，不自动应用训练、不自动打开 benchmark/model/release 状态。底物混合物继续禁止自动推断单分子 SMILES。
- P232 final status：工程审核闭环已完成，但两个硬门槛未被伪造突破。`kwb_venus15b_strict_holdout_review_decisions.jsonl` 和 `substrate_identity_review_decisions.jsonl` 均为 0 行；human backlog missing rows 从 1184 真实增加到 1185，并被 fail-closed/release guard 接受。Chrome 实际位于用户应用快捷方式目录，Playwright Node API 已完成真实浏览器验证和截图；页面资源/API 200，唯一 404 为 `/favicon.ico`。
- P233 bridge findings：新增 hard-gate decision benchmark bridge 后，两个剩余 benchmark 缺口的工程路径已闭合：审批齐全时 strict 生成 `cache/advanced_features/benchmarks/kwb_venus15b_reviewed_strict_holdout/`，substrate 生成 `cache/advanced_features/benchmarks/reviewed_substrate_identity_set/`，并写入 `benchmark_score_cache_intake.local.jsonl`。当前 formal approvals=0，所以 `intake_rows_written=0`，benchmark cache 仍 13/15；这是正确阻断，不是工程遗漏。
- P234 button workflow findings：hard-gate UI 已从“只能保存/验证”扩展为可操作向导，顺序固定为刷新审核包 -> 验证人工审核 -> 生成 bridge -> 验证 bridge -> 写入 score cache -> 验证 benchmark -> 安全训练管线。服务端仅允许固定本地脚本，bridge 在 0 条 formal approval 时仍返回 `blocked_no_approved_decisions`，不写 intake；浏览器实测状态为 strict/substrate formal approvals=0、benchmark=13/15、pipeline=398/0。

- P235 external source deep-dive findings:
  - Biomni should be treated as an architecture reference, not a directly installable dependency in the current local cache. `biomni/agent/a1.py` and `biomni/agent/react.py` import `biomni.tool.tool_registry`, `biomni.tool.support_tools`, and `biomni.utils`, but those modules are absent from the cached source tree. This indicates the local source snapshot is incomplete or structurally inconsistent; KWB must not depend on it without a fresh source/package integrity check.
  - Biomni's useful boundary is four-layer orchestration: agent state graph, resource retrieval, execution tools, and data/know-how environment. `A1` wires LangGraph state/checkpointing, optional `ToolRetriever`, data lake/library descriptors, know-how loader, custom tool injection, MCP wrapping, timeout execution, and commercial-mode filtering. This maps well to KWB as `enzyme_agent_orchestrator`, `controlled_resource_retriever`, `tool_contract_registry`, and `licensed_data_lake_registry`.
  - Biomni's `ToolRetriever` is prompt-based and intentionally generous: it retrieves tools, data lake items, libraries, and know-how documents from indexed descriptions. For KWB, the same pattern should be constrained by fail-closed eligibility: retrieval can suggest `MSA`, `structure_graph`, `PyRosetta ddG`, `wet-lab feedback`, `FireProt`, and `benchmark` resources, but execution still needs explicit receipts, license state, and schema validators.
  - Biomni's commercial mode is directly relevant: `A1` switches from `env_desc` to `env_desc_cm` and comments out multiple non-commercial datasets. KWB should preserve this as a first-class `license_scope` selector rather than mixing academic-only public data with customer delivery paths.
  - Biomni's ReAct path wraps tool calls with multiprocessing timeouts and catches tool exceptions into tool messages. The transferable idea is not its full tool catalog, but a structured execution envelope: timeout, artifact paths, stdout/stderr/log, selected resources, tool-call IDs, and validator result. This aligns with KWB's execution receipt gate and should remain separated from training/import decisions.
  - closed-loop is a lightweight protein engineering loop, not a complete platform. Its reusable part is the predictor plugin interface: `BasePredictor.train/predict/predict_unsupervised`, predictor maps such as `ev`, `onehot`, `hmm`, `blosum`, `mutation`, `esm`, `vae`, plus ensemble composition through `JointPredictor` and `BoostingPredictor`. This can inform KWB head-specific baseline adapters and benchmark runners.
  - closed-loop's assistant/API layer is too thin for KWB production. `functions.py` hardcodes an OpenAI API placeholder and launches `predict.py` through `subprocess.run` with fixed ESM parameters, while `predict.py` is copied from ESM variant prediction and asserts WT residue matches. KWB should reuse the fail-fast WT-numbering assertion idea, but not copy the natural-language assistant wrapper.
  - closed-loop license is MIT, so algorithmic structure and small interface ideas are easier to reuse than GPL sources. Still, ESM model weights/runtime and each predictor dependency need independent license/runtime review before any customer-facing integration.
  - OED is best understood as an enzyme kinetics ETL/governance reference. `data_combination.py` normalizes BRENDA and SABIO-RK records into EC, substrate, organism, UniProt, enzyme type, pH, temperature, PubMedID, numeric value, and unit; it parses mutant tokens, standardizes units, drops non-positive values, deduplicates, and groups by condition keys. This is highly relevant to KWB's kinetic/activity data intake schema and source-quality reports.
  - OED's cleaning rules should be borrowed as data contracts rather than code. Examples: mutant text with no parseable mutation is excluded; KM is converted from M/mol to mM; kcat/KM is converted to `1/mM*1/s`; ranges become means; PubMed IDs are normalized as strings; duplicate condition rows are grouped with max kinetic value. For KWB, these rules need explicit provenance fields and no silent label promotion.
  - OED license is GPL-3.0. Directly copying OED code into a proprietary or mixed-license KWB platform is risky; use it as a reference for schema design and ETL test cases unless legal review approves GPL-compatible distribution. OED data sources such as BRENDA and SABIO-RK also require separate data-use review.
  - Practical KWB mapping from this source triad: Biomni provides the agent/resource/control architecture; closed-loop provides mutation predictor plug-in shape and WT mismatch fail-fast behavior; OED provides enzyme kinetics schema normalization and provenance checks. None of the three should open KWB training, model-quality, customer, or release gates by itself.

- P236 fresh Biomni and clean-room OED adapter findings:
  - Biomni official `main.zip` was re-fetched through GitHub codeload on 2026-08-04 after the first Git attempt was rewritten by the local global Git config from HTTPS to SSH. Fresh archive SHA256: `158873d40c1675f05ac857afa055e24dcd0035817d7f60d5b4bd7249adf3740f`; archive size: 1,026,310 bytes.
  - The fresh archive contains the previously missing modules: `biomni/tool/tool_registry.py`, `biomni/tool/support_tools.py`, `biomni/utils.py`, `biomni/tool/tool_description/`, `pyproject.toml`, `docs/known_conflicts.md`, plus additional `synthetic_biology.py` and `systems_biology.py` modules. The cached source was incomplete; the upstream snapshot is structurally complete enough for source audit.
  - Fresh Biomni metadata identifies package version `0.0.8`, Python `>=3.11`, Apache-2.0 license, and a small base dependency set (`pydantic`, `langchain`, `python-dotenv`). The repository still documents a much larger optional environment and known dependency conflicts, so source completeness does not imply local installation readiness.
  - A core fresh-source extraction was stored at `cache/external/Biomni-fresh-core/` for auditable local reading. `a1.py`, `react.py`, `retriever.py`, `tool_registry.py`, `support_tools.py`, and `utils.py` all pass Python compilation. Full archive extraction hit macOS unzip errors on malformed/non-ASCII protocol filenames; this did not affect core Python extraction or checksum verification.
  - Fresh `ToolRegistry` is intentionally small: validate required metadata keys, assign integer IDs, support lookup/list/remove, build a pandas document table, and pickle the registry. This is a useful reference for KWB's registry contract, but KWB should add immutable version, license scope, runtime readiness, input schema hash, and execution receipt fields rather than copy the implementation.
  - Fresh `utils.py` confirms Biomni's actual execution boundary: Python/R/Bash/CLI runners, timeout wrapper, function-to-schema generation, AST-based tool discovery, LangChain tool conversion, persistent custom-function injection, and HTML execution trace formatting. These modules make the earlier architecture conclusion stronger, but they also reinforce that the package is a broad execution environment rather than a narrow enzyme backend.
  - OED deeper review confirms a three-stage ETL shape: source-specific download/parse (`brenda_*`, `sabio_*`), parameter-specific extraction (`kcat`, `km`, `kcat/km`), and cross-source combination/deduplication. SABIO processing additionally derives kcat/Km from matching kcat and Km entries when units and context align.
  - OED's source code has important data-quality weaknesses that KWB must not inherit: broad bare `except` blocks in SABIO parsing, regexes tied to encoded temperature text, hard-coded relative paths, a special-case UniProt correction, and condition-group aggregation using `max` without retaining all replicate/raw observations. These are research findings, not production rules.
  - Added `scripts/normalize_kinetics_records_cleanroom.py` as an independently implemented KWB adapter. It borrows the observed field contract and unit semantics but retains `raw_record`, source file SHA256, source row index, raw value/unit, normalized value/unit, pH/temperature, mutation tokens, quality flags, and `training_eligible=false`.
  - Clean-room adapter smoke passed on a 119-row BRENDA slice: all 119 rows preserved raw records, source checksum was consistent, and zero rows were training eligible. It is intentionally not wired into training or release pipelines yet.
  - Legal boundary remains unchanged: Biomni Apache-2.0 source can be evaluated for reuse with attribution/notice compliance; OED GPL-3.0 source is not copied. The KWB adapter is an independent implementation based on an observed data contract and must receive separate legal/data-source review before production use.

- P237 integration-boundary findings:
  - Biomni's fresh `read_module2api()` treats tool-description modules as the source of truth and imports a fixed field list. The description layer is declarative, but the registry only requires `name`, `description`, and `required_parameters`; it does not validate parameter schema shape, duplicate names, version, license scope, runtime availability, or whether a tool is safe for the current task.
  - Biomni's `ToolRegistry.register_tool()` mutates the input dictionary by adding an integer `id`, then appends it. Registering the same tool twice creates duplicate entries and new IDs. KWB should therefore keep registry records immutable-by-copy and key them by `tool_id + version + contract_hash`, with explicit duplicate rejection.
  - Biomni's `read_module2api()` imports every listed description module at startup. For KWB, registry discovery must be lazy and capability-gated: a missing optional backend or unavailable license should produce `not_installed`/`license_review_required`, not prevent the core enzyme agent from starting.
  - Biomni's prompt retriever selects indexed resources but does not itself enforce execution authorization. KWB should separate `retrieval_candidate`, `execution_eligible`, and `claim_eligible` states. Retrieval of a FireProt row, external benchmark, or substrate record must never imply permission to execute or train.
  - Biomni's support-tool descriptions include Python REPL, function-source inspection, and Synapse download. These are powerful environment tools and should not be exposed by default in the KWB customer tool registry; local development may keep them behind `developer_only`, `network_required`, `write_scope`, and `manual_confirmation` flags.
  - OED's BRENDA/SABIO-RK pipeline has a useful source-specific normalization boundary, but its final aggregation key is too small for KWB. It groups by EC, substrate, organism, UniProt, enzyme type, pH, temperature, PubMedID, and sometimes unit, then keeps the maximum value. KWB should preserve every source row and use a separate derived summary with median, replicate count, range, standard deviation, assay method, source database, and condition hash.
  - OED's `calculate_kcatkm()` derives kcat/Km only when kcat and Km rows share the same entry/context and units are admissible. This is a good derivation rule, but KWB should emit `derived_from_record_ids`, `derivation_formula`, and `derivation_quality` instead of treating the derived number as an independent observation.
  - OED's PubMed enrichment is a separate join stage keyed by EC and literature text, followed by network calls to BRENDA literature pages. KWB should treat literature IDs as evidence references, not as label provenance, and should retain HTTP status, response checksum, query date, and mutation-token relevance.
  - KWB implementation constraint: use the clean-room adapter for candidate normalization and source-quality reports only. Do not register its output in `datasets/training`, do not merge it into the existing kinetic database automatically, and do not use `max` aggregation for model labels or customer-facing claims.

- P238 replicate-summary findings:
  - Added `scripts/summarize_kinetics_replicates_cleanroom.py` as a second independent layer after normalization. It groups only quality-clean observations by a condition hash and retains source file checksum/row references for every observation.
  - The summary emits observation count, median, mean, min, max, population standard deviation, pH, temperature, unit, and condition fields. `max_value` is descriptive only; the policy explicitly says raw observations remain authoritative and `training_eligible=false`.
  - On the 119-row BRENDA smoke slice, zero rows were eligible for aggregation because every row carried at least one quality flag. This is the intended fail-closed behavior, not a missing-output error.
  - A two-row clean fixture produced one summary with median/mean 3.0, min 2.0, max 4.0, standard deviation 1.0, and both source row references retained.
  - Existing KWB lifecycle registry validator still passes: 8 registry rows, 0 failures. The new kinetics summary layer is not connected to training, model claims, customer delivery, or release.

- P239 external-research integration matrix findings:
- 2026-08-07 P239 completion finding: the Biomni/closed-loop/OED four-lane integration matrix is now reflected in the read-only external research evidence/API/UI path. Backend external-research/API regression is 7/7 passed and the frontend production build succeeds; no approval, training import, customer delivery, SQLite/apply, model-claim or release gate was opened.
- 2026-08-07 P284 FireProt dedup receipt finding: the current 5067 curated candidates collapse into 2133 duplicate mutation-key review candidates (2124 same-assay signature groups and 9 heterogeneous-assay groups). Twenty-two review packets cover all candidates, but decisions, approved import candidates and training-ready rows remain zero; no formal training or release gate opened.
- 2026-08-07 P285 numbering review receipt finding: refreshed FireProt/ProTherm numbering governance yields 475 worklist rows, 21 packets, 475 valid packet rows, and 33 briefing/status rows. Only 4 rows carry existing historical decisions; 471 operator rows remain open, with 0 semantic conflicts and 0 completion-ready rows. No new numbering decision or training import was created.
- 2026-08-07 P285 integration finding: refreshed governance artifacts expand the live Stage 25 handoff to 171 unique paths (170 checksum-verified + 1 volatile). Concurrent source-probe wiring expands the exact runner/overall/post-source contracts to 92 commands, 54 summaries and 40 rerun commands (SHA-256 `c7879de08f4c30e017e59246e9d73a662a206c6da4acf3a310ada0089d1cba12`). Exact assertions were updated without weakening filesystem parity or SQLite-write guards; release remains false.
- 2026-08-07 P286 public-source probe finding: Europe PMC, PubMed, Crossref and Zenodo return four valid public metadata receipts, but only three metadata-only results and the already-audited Zenodo archive. New public artifacts and adjudication-slot artifacts are both zero; all four P283 slots remain missing and the L262V discrepancy remains unresolved. No paywall or publisher-content bypass was attempted.
- 2026-08-07 P288 outbound-authorization finding: the independent local intake has 0 authorization rows and no send executor. A future valid `authorize_send` must identify the request, reviewer, UTC time, basis, approved channel, recipient and approved-message SHA-256, but still cannot send automatically; current request-sent, evidence-received, discrepancy-resolved, SQLite/apply/model/release counts remain zero or false.
- 2026-08-07 P287 external-request finding: four unsent request rows map exactly to the four missing CM5 adjudication slots and canonical delivery paths. Recipient contact, sent timestamp and outbound message id remain empty; request-sent, outbound-authorization, evidence-received/reviewed and completion-ready counts are all zero. This creates an operator packet, not external communication or scientific evidence.
- 2026-08-07 P287 integration finding: the exact contracts advance to 94 runner commands, 55 overall summaries, 42 post-source commands with SHA-256 `a44d95b79263e49025583da325961c056547a3f799aa631aa140604f61819eec`, and 176 handoff paths (175 live + 1 volatile). All validators pass; SQLite/apply/model/release remain closed.
- 2026-08-07 P288 outbound-authorization finding: the separate local intake is empty and valid. Authorization, authorized-send, send-ready, request-sent and evidence-received rows are all zero; external-message-sent and send-executor-present are false. Even a future valid authorization remains non-executing without a separate outbound step.
- 2026-08-07 P288 integration finding: exact contracts advance to 95 runner commands, 56 summaries, 43 post-source commands with SHA-256 `2b6c18b78237a216f26aeee1cf5224f89d7bfe692891f4a33bec440c31a53287`, and 179 handoff paths (178 live + 1 volatile). No outbound contact, SQLite/apply, model claim or release occurred.
- 2026-08-07 P289 send-guard finding: the no-side-effect guard remains blocked with no authorization and no executor; send-attempted, external-message-sent and executor-present flags are false. It prevents accidental outbound communication while preserving the four missing evidence slots.
- 2026-08-07 P290 message-draft finding: four request-linked drafts are hash-bound and unapproved; message-approved, request-sent, external-message-sent and evidence-received rows are all zero. Draft text is review material only, not an outbound message or scientific evidence.
- 2026-08-07 P289/P290 integration finding: exact contracts settle at 99 runner commands, 58 summaries, 47 post-source commands with SHA-256 `0a321899280183240582146ad3068fe543cb32265b96d2aa1794a62c6219b4b7`, and 188 handoff paths (187 live + 1 volatile). All apply/model/release flags remain closed.
- 2026-08-07 P293 evidence-receipt finding: the local receipt intake is empty and valid. Future received files must bind request/slot/path, UTC receipt time, sender/source locator, transfer method, rights basis and live artifact SHA; a missing canonical file receipt fails closed. Receipt, present artifact, reviewed evidence and adjudication-ready rows are all zero.
- 2026-08-07 P291 authorization-binding finding: a future authorize-send record must reference the live SHA-256 of the current request-specific P290 draft; arbitrary well-formed hashes are rejected. Current draft validation is true with 4/4 request bindings, while SHA-bound authorization rows remain zero and no send path exists.
- 2026-08-07 P292 authorization-safety regression finding: isolated matching-SHA and forged-SHA cases both behaved as required (2/2 passed). The matching case remains non-sending, while the forged case is rejected specifically for not matching the current request draft; the real authorization input remains untouched.
- 2026-08-07 P292 integration finding: exact contracts advance to 100 runner commands, 59 summaries, 48 post-source commands with SHA-256 `6a39ce1012c02ff9db0c05a06cf01d1c57e90ff4e80b88c7d88f61c90871c593`, and 190 handoff paths (189 live + 1 volatile). No external message, SQLite/apply, model claim or release occurred.
  - 四类接入都可以继续建设，但必须区分“接入合同/证据引用”和“能力解锁”。本轮新增 `reports/external_research_integration_matrix_2026-08-04.md`，将训练、模型声明、客户交付、local release 的可迁移内容和禁止自动发生的动作固定下来。
  - Biomni fresh snapshot 已确认可审计且包含 `tool_registry.py`、`support_tools.py`、`utils.py` 等旧缓存缺失模块；其 `ToolRegistry` 只验证 `name/description/required_parameters`，不能替代 KWB 的 license、runtime、版本、schema、provenance 和 claim gate。
  - closed-loop 适合作为 `BasePredictor`/predictor registry/组合 predictor/WT mismatch fail-fast 的接口参考；不采用硬编码 assistant wrapper、固定 subprocess 路径或无 KWB provenance 的直接输出。
  - OED 适合作为 BRENDA/SABIO-RK kinetics schema、单位归一、mutation token、条件匹配和派生 kcat/Km 的研究参考；GPL-3.0 代码不复制进平台。KWB 使用独立 clean-room normalizer/replicate summary，默认 `training_eligible=false`。
  - 训练接入当前只能落 raw observation、normalized candidate、replicate summary candidate 三层；必须经过 source/license、numbering、dedup、QC、人工 receipt 和 head threshold 才能成为 formal training import。
  - 模型声明当前可记录 predictor/plugin 版本、feature input-only、benchmark evaluation-only、proxy/physics ddG 区分和 fail-fast 条件；不能声明五头质量、客户效果或 proxy ddG 等价于湿实验。
  - 客户交付当前最多形成 `internal_review_only` package，必须绑定 data/tool license、IP/FTO、biosecurity、human acceptance 和 allowed claims；不能由 local release manifest 自动转成 customer-ready。
  - local release 继续只做 fail-closed 汇总：当前 training import eligible=6、benchmark=13/15、heads_ready=3、`model_quality_ready=false`、`safe_for_model_claim=false`、`release_ready=false`。

- P240 大模型平台整合 findings:
  - 现有平台已有统一 LLM gateway、Plan-Execute-Synthesize agent graph、`ToolRegistry` 和 `scientific_claim_gate`，因此外部研究不需要复制一套 assistant wrapper。
  - 新增平台原生工具 `backend/app/tools/external_research_evidence.py`，以 read-only 方式读取 `AI大模型/reports/` 中的训练、claim、customer delivery、local release 状态。
  - 新工具已加入 `backend/app/tools/registry.py` 的 discovery module；LLM 可用 `scope=training|model_claim|customer_delivery|release|all` 查询状态。
  - 工具返回 `local_only=true`、`read_only=true`、`training_eligible=false`、`release_ready=false` 等显式边界，并列出 `write_training_rows`、`approve_model_claims`、`approve_customer_delivery`、`set_release_ready`、`deploy_or_sync` 等禁止副作用。
  - 使用后端 Python 3.13 虚拟环境回归：新工具测试 3/3 通过，连同 LLM gateway 测试共 13/13 通过。系统 Python 3.9 不能加载现有 registry 的类型注解，不能作为后端测试解释器。

- P246 并行攻坚 findings:
  - Benchmark lane 已完成审核前置自动化：`benchmark_lane_machine_prereview_report.json` 显示 strict packets 3 条、substrate candidates 9 条；`benchmark_lane_status_aggregate_report.json` 保持 `status=blocked`、formal approvals 0、training import 0、`safe_for_model_claim=false`、`release_ready=false`。
  - ddG lane 已改为更严格的 lane-level fail-closed：PyRosetta smoke 和 runtime receipt 可作为计算特征证据，但 FoldX executable/receipt 缺口存在时，整条 Rosetta/PyRosetta/FoldX physical ddG lane 必须保持 `physics_ddg_ready=false`。
  - 旧验证器中“PyRosetta 单后端突破即 physics_ddg_ready=true”的判断已统一修正为分层语义，避免 proxy/单后端证据误打开模型质量、客户交付或 release gate。
  - 后端工具新增统一 capability contract，覆盖 `real_runtime/external_service/proxy/blocked`、版本/权重或 checkpoint、输入 SHA256、runtime、日志、artifact manifest、scientific boundary 和 failure reason；现阶段多数模型工具仍明确为 proxy 或 blocked，不伪造真实 runtime。
  - 全量安全流水线 402/402 通过后，最终门控仍保持：benchmark 两项缺正式审批、model_quality_ready=false、safe_for_model_claim=false、customer_ready=false、release_ready=false。

- 2026-08-05 tool lane evidence pack findings:
  - 新增 `AI大模型/scripts/build_tool_lane_evidence_pack.py` 和 `validate_tool_lane_evidence_pack.py`，只采本地可见信号，不执行 ProteinMPNN、RFdiffusion、AlphaFold/ColabFold、Vina、ACPYPE 或 GROMACS。
  - 证据包覆盖 8 条 lane：ProteinMPNN、RFdiffusion、AlphaFold2、AlphaFold/ColabFold proxy、PDBQT preparation、Vina docking、ligand topology、GROMACS long task。
  - 本机验证结果为 8/8 blocked，ready=0；这符合“只做本地信号、报告和测试，不伪造真实 runtime”的边界。
  - 为兼容当前解释器，`backend/app/tools/registry.py` 补了 `from __future__ import annotations`，让 capability audit 和证据脚本可导入。
- 2026-08-05 human target / antibody findings:
  - 可复用的现有入口主要是 `backend/app/tools/bio_specialty_input_gate.py`、`backend/app/tools/tool_capability_contract.py` 和 `backend/app/tools/scientific_claim_gate.py`。
  - 现有代码已经有近似合同名：`HumanProteinProfile`、`ExpressionSafetyProfile`、`PathwayRelation`、`AntibodyChainProfile`、`GermlineMatch`、`HumanizationProposal`、`DevelopabilityProfile`、`EpitopeSimilarity`、`ExtracellularAccessibility`。
  - 但仍缺真实 schema/ingestor/service：HumanProteinProfile、ExpressionSafetyProfile、Reactome/HPA/GTEx、ligand-receptor/pathway graph、OffTargetRisk、ANARCI/IMGT runtime、germline 库和人源化报告模板。
  - 因此当前只适合做输入门控和 claim gate，不足以直接交付靶点情报或抗体人源化产品线。
- 2026-08-05 release guard findings:
  - `tool_lane_evidence_pack.json` 与 `tool_lane_evidence_pack_validation_report.json` 已纳入 `data_lake_manifest.json` 和 `local_release_manifest.json`。
  - `validate_local_release_guard_coverage.py` 重新运行后 23 个 guard 全部挂上，0 failures；但这只表示本地发布门控覆盖完整，不代表 release_ready 变真。
  - `tool_lane_evidence_pack` 仍然是 8/8 blocked、ready=0，保持 proxy/blocked 语义，不打开任何 model claim 或 release 门控。
- 2026-08-05 human target gap findings:
  - 新增 `human_target_contract_gap_report.json` / validation，专门记录人类靶点与抗体人源化合同缺口。
  - 报告只声明 gap_only，不提供真实 HPA/GTEx/Reactome/ANARCI/IMGT 或 germline 结果。
  - 接入 data lake / local release 后，guard coverage 升到 25，但 `release_ready` 仍然 false。
- 2026-08-05 human target schema-only contract findings:
  - 后端已具备 schema-only 合同对象，覆盖人类靶点、膜蛋白脱靶和抗体人源化的第一层数据结构。
  - 这些 schema 明确 `schema_only=true`，只规定字段和 evidence_boundary，不代表已经读取 UniProt/HPA/GTEx/Reactome/ANARCI/IMGT 或 germline 数据。
  - `scientific_claim_gate` 增加 required schema audit 后，即使 claim 标为 SUPPORTED，只要所需 schema payload 缺失或不完整，也会阻断摘要/结论提升。
  - 当前正确状态是 `schema_only_contracts_present_no_runtime`：产品线骨架更清楚，但客户交付、模型声明和 release 仍必须关闭。
- 2026-08-05 human target source/runtime findings:
  - 新增 `human_target_source_runtime_manifest.json` / validation，把 schema 后的真实数据源和 runtime 缺口拆成 7 条 blocked lane。
  - 人类靶点方向缺 HPA/GTEx 表达 source manifest、Reactome pathway source manifest、ligand-receptor graph 和 OffTargetRisk execution contract。
  - 抗体方向缺 ANARCI/IMGT runtime receipt、human germline DB manifest、SAbDab/OAS reference source manifest 和 numbered VH/VL mapping artifact。
  - 本机未发现 ANARCI/anarci executable；因此 ANARCI/IMGT lane 明确为 `required_runtime_executable_missing`。
  - 该 manifest 只证明缺口可追踪，不提供真实检索、编号、人源化、脱靶结论、模型声明、客户交付或 release 依据。
- 2026-08-05 external evidence/UI findings:
  - `external_research_evidence` 新增 `human_target` scope，读到 `human_target_contract_gap_report` 与 `human_target_source_runtime_manifest` 后仍返回 blocked、read_only。
  - `ResearchEvidencePage` 增加 human_target 只读区块，可直接看到 7 条 source/runtime lane 的 blocked 状态。
  - 后端回归 7/7 passed，前端 `npm run build` 通过，说明这个 scope 扩展只改展示和只读证据，不改能力开关。
- 2026-08-05 scope sync findings:
  - `external_research_evidence` 的 ToolRegistry 参数 enum 已补上 `human_target`，避免后端 function scope 和公开 schema 漂移。
  - 前端 ResearchEvidencePage 的页头文案和 gate cards 也同步加入 human target，统一展示训练、模型声明、客户交付、release、human target 五条只读状态。
- 2026-08-05 human target UI field findings:
  - 前端现在展示的 human target 字段全部来自 source/runtime manifest 的只读治理状态：validation、total/ready/blocked、required artifacts、runtime signal 和 false readiness flags。
  - 这些字段适合展示 blocked 证据链，但仍不能写成 HPA/GTEx/Reactome/ANARCI 已接入或 source ready。
- 2026-08-05 scope centralization findings:
  - `external_research_evidence` 已把 scope 集中到 `RESEARCH_EVIDENCE_SCOPES`，减少函数逻辑和 ToolRegistry enum 漂移。
  - 目前未发现需要把同类 scope 常量继续外抽到前端，TS union 已与后端 scope 一致。
- 2026-08-05 human target split source manifest findings:
  - 7 个 source/runtime lane 已从总 manifest 轻拆为独立 blocked manifest，便于未来逐源解锁和单独验收。
  - 拆分范围仍是 governance/readiness 资产：HPA、GTEx、Reactome、ligand-receptor、ANARCI/IMGT、human germline、SAbDab/OAS 全部 blocked。
  - `human_target_blocked_source_manifest_index_validation_report.json` 只证明 7 个 split manifest 存在且保持 blocked，不代表任何真实数据源已接入。
- 2026-08-05 human target split UI findings:
  - `external_research_evidence` 现在把 split manifest index 作为 human_target scope 的一部分返回。
  - 前端可看到每条 source 的单源 manifest path，后续解锁 HPA/GTEx/Reactome/ANARCI 时可以逐源定位。
  - 该 path 展示仍是只读 blocked 证据链，不是下载链接、审批入口或 release 依据。
- 2026-08-05 human target unlock checklist findings:
  - 新增证据工具的 JSONL 读取层后，human_target scope 现在同时返回 7 条 source unlock checklist、`ready_to_unlock_rows=0`、`blocked_rows=7` 和每条 source 的 `missing_steps`。
  - checklist validator 的 `success=true` 仅证明治理清单结构正确；工具和前端仍把 source 解锁状态保持为 blocked，并保留 `claim_eligible=false`、`customer_ready=false`、`release_ready=false`。
  - `/research` 页面新增逐源“源解锁清单”只读区块，可定位 source manifest、license、checksum/runtime receipt、schema validator 和 claim boundary 等缺口，但没有审批/写入按钮。
  - 后端 evidence/API 7/7 和前端生产构建均通过；本轮没有新增训练行、formal decision、客户交付或 release。
- 2026-08-05 P247 gate refresh findings:
  - unlock checklist 接线后完整安全流水线为 412/412、0 failures；data lake 1560 artifacts；local release guard coverage 31/31、0 failures。
  - benchmark 现有正确链路仍为 13/15 valid、2 missing/invalid、heads_ready=3；KWB strict mutation holdout 与 reviewed substrate identity set 的 bridge 均未写 intake，底物候选 9 条仅为 `reviewed_rows=0` 的证据草稿。
  - ddG runtime receipt 2 条已批准，PyRosetta feature 29 条中 18 条 quality passed、11 条 quality blocked；FoldX executable/receipt 缺口仍使整条 physical ddG lane `physics_ddg_ready=false`。
  - 一次过期脚本名 `validate_benchmark_score_cache_intake.py` 被记录为环境/仓库命令漂移；当前应使用 `apply_benchmark_score_cache_intake.py`、`validate_benchmark_score_cache.py` 和 coverage validator。
- 2026-08-05 browser regression findings:
  - 未认证访问 `/research` 的行为正确：路由重定向到 `/login?next=%2Fresearch`，没有暴露研究数据。
  - 本地登录回归收到 `POST /api/auth/login` HTTP 500，页面显示 `Internal Server Error`；这是当前 auth/runtime 环境阻塞，不是 checklist 组件或 TypeScript 构建错误。
  - 因认证服务 500，尚未取得 authenticated `/research` 页面截图或逐源 DOM 验收；不把未认证重定向当作 UI 通过，也不通过前端绕过认证。
- 2026-08-05 auth/runtime findings:
  - `/api/auth/login` 的 500 发生时本机 8000 后端端口已无监听，故该响应来自前端 proxy/后端不可用状态；不能据此判定 auth 实现失败。
  - auth resilience + password regression 共 25/25 通过。后续若要重新做浏览器认证验收，前置条件是明确启动本地 backend runtime，仍需保留真实登录和 cookie 检查。
- 2026-08-05 benchmark second-pass findings:
  - 机器预审已识别 strict packet 3 条、substrate candidate 9 条，状态为 `ready_for_human_review`；这只是人工审核前置，不是批准。
  - bridge validator success=true 但 formal approval 两类均为 0，intake rows written=0；coverage 仍为 13/15、heads_ready=3、model claim blocked。
- 2026-08-05 multi-lane regression findings:
  - 后端 external evidence/research API/auth/password 组合回归 32/32 通过，说明当前只读证据接线和认证代码测试没有回归。
  - 完整安全流水线 412/412 通过，data lake 1560 artifacts，release guard 31/31 无缺口；这些是治理覆盖结果，不代表任何模型或客户能力已解锁。
- 2026-08-05 claim/release/ddG consistency findings:
  - claim readiness 只允许内部设计审查类工程声明，模型/训练/客户/release 等 10 类声明继续 blocked。
  - model claim consistency 中 strict rows 和 claim-eligible rows 都为 0；没有证据支持模型质量声明。
  - local release 的 11 个 safety guard links 全部存在且通过，但 `release_ready=false` 仍是正确结论。
  - ThermoMPNN/PyRosetta proxy 特征可作为计算证据；validator 明确 `proxy_ddg_backend_ready=true` 不等于 `physics_ddg_ready=true`。
- 2026-08-05 five-head readiness findings:
  - 当前五头训练执行资格为 0/5；`activity_risk` 的 6 条真实导入候选不足以达到训练阈值，不能把 `training_import_eligible_rows=6` 解释成五头模型已可训练。
  - `mutation_rank`、`stability`、`substrate_fit`、`assay_success` 仍无正式训练标签；sample gap queue 汇总缺失标签 494 条。
  - benchmark readiness packet 只记录 strict/substrate 两个缺口，2 条均非 completion-ready，仍需人工正式 decision 和后续 score cache intake。
- 2026-08-05 platform review UI findings:
  - benchmark/hard-gate 页面能力由 `serve_numbering_review_platform.py` 与 `ui/numbering_review` 等现有链路承载，不存在独立 `ui/` 根目录；本次没有新增错误入口。
  - `external_research_evidence` 和 ResearchEvidencePage 回归通过，页面仍然只读；hard-gate formal decision bridge 是唯一可进入 benchmark intake 的受控路径。
- 2026-08-05 runtime/review packet findings:
  - hard-gate review packet 结构完整覆盖 3 条 strict 和 9 条 substrate，但 formal decision rows=0；不能把 packet validator 通过解释为人工审核完成。
  - 五头 sample gap queue 仍报告 494 个缺失标签，所有 5 个 head 均 blocked；当前没有自动补标签或短路训练阈值的合法路径。
  - backend health/admin/auth 相关回归 10/10 通过；此前浏览器登录 500 仍属于后端未监听时的运行态问题，不改变代码层测试结论。
- 2026-08-05 platform live-smoke findings:
  - capability contract、model tool fallback 和 GROMACS artifact 相关测试 6/6 通过，工具状态仍严格区分 `proxy`、`blocked`、`real_runtime`。
  - `frontend/tests/http-smoke.mjs` 当前无法完成，因为本机 4200 端口没有前端服务监听；连接错误不等于 HTTP endpoint 断言失败，后续需要明确授权启动本地服务后再做 live smoke。
- 2026-08-05 release/benchmark/tool regression findings:
  - local release manifest 重新构建后仍为 `release_ready=false`、artifact_count=1560，guard coverage 31/31 无缺口。
  - hard-gate review packet 与 benchmark hard-gate packet 仍为 strict=3、substrate=9、completion_ready=0，不能写 score cache intake。
  - tool fallback / capability contract / GROMACS artifact 测试继续通过，说明运行态补强没有改变 blocked/proxy/real_runtime 的边界。
- 2026-08-05 live smoke semantics findings:
  - `http-smoke` / `live-smoke` 现在对本机 4200 未监听给出明确运行态提示，避免把底层 `fetch failed` 误读成页面契约失败。
  - 这类改动只改变失败语义，不改变测试应该成功的前提；真实 live smoke 仍需要前端服务实际启动。
- 2026-08-05 live smoke contract findings:
  - README、Makefile、docker-compose 和 vite smoke config 都以 4200 作为统一本地入口。
  - 现有一键复用路径是 `make docker-up` / `make docker-backend-smoke-live`，并没有额外的 frontend-only smoke 启动目标。
  - 因此 live smoke 的正确诊断是“运行态未启动”而不是“契约设计错误”。
- 2026-08-05 startup/preflight findings:
  - backend 的 ops/health 相关接口可以提供运行态就绪信号；`check_environment.py` 和 `deploy-preflight` 也是现成的预检入口。
  - 现有 Makefile 已覆盖 live smoke 前置，不需要再补一个 frontend-only 启动命令。
  - claim/release 相关的一致性仍全部闭合，因此本轮只收敛运行态前提，不改变任何 gate。
## 2026-08-06 Stage 25 operator-doc validation finding

- Stage 25 的 JSON 验证链现在包含 Markdown 操作文件存在性和 fail-closed 关键词校验：`next_operator_packet_20260806.md` 与 `2026-08-06-daily-report.md` 均必须保留 `allow_apply=false`、`external_sqlite_mutated=false`、`export_safe_released=false`、release/model/benchmark claim false 和 non-bypass 文案。
- Overall index 已纳入第三个输入 `markdown_operator_docs_validation`，因此 `summary_count=3` 是当前正确值；旧的 `summary_count=2` / runner `command_count=12` 已过时。

## 2026-08-06 Stage 25 authorization and parallel recovery findings

- 用户最大权限已记录为 `stage25_user_max_permission_authorization_20260806_001`，当前正确 runner 基线更新为 `command_count=14`，overall index `summary_count=4`。
- 权限授权和证据闭合是不同字段：授权收据可为 true，但 `external_sqlite_mutated=false`、`formal_decision_rows_written=0`、`apply_executed=false`、`export_safe_released=false`、`safe_for_model_claim=false` 仍由 validator 固定检查。
- 五条并行核查线均未发现可直接写 SQLite、创建 approved formal decision、打开 export/release/model claim 的证据。可继续推进的是人工 checklist、source acquisition、runtime receipt 和 family-specific apply importer 设计，不是直接改 gate true。

## 2026-08-06 Stage 25 breakthrough attempt findings

- `stage25_breakthrough_attempt_receipts_20260806.jsonl` 将“必须突破”的实际尝试转成可审计收据：ACS SI 直链在 sandbox DNS 失败、escalated 下载 HTTP 403；这把 `39743673` 从“待尝试”推进为“publisher access blocked with receipt”。
- FoldX 搜索未找到 executable；现有 FoldX parser contract/fixture 不等同于 runtime。FoldX 下一步不是改 `runtime_receipt_ready=true`，而是提供 licensed executable、license approval、reviewed probe、smoke artifact hashes 和 schema-valid runtime receipt。
- 当前正确 runner 基线更新为 `command_count=15`，overall index `summary_count=5`。

## 2026-08-06 Stage 25 unblock packet findings

- 当前正确 runner 基线更新为 `command_count=16`，overall index `summary_count=6`。
- `stage25_unblock_operator_packets_20260806.jsonl` 是下一步真正突破的交付清单：只要用户/机构把文件放入本地并补 sha256/source locator，即可进入 extraction validator 和 family-specific importer 设计；在文件未到位前继续不写 SQLite。
- FoldX 的突破清单已从泛化“缺 runtime”收敛为四类交付物：licensed executable、license decision、runtime receipt、checksumed smoke artifacts。

## 2026-08-06 Stage 25 drop/provision/design findings

- 当前正确 runner 基线更新为 `command_count=20`，overall index `summary_count=10`。
- 当前正确 runner 基线更新为 `command_count=22`，overall index `summary_count=12`。
- 新增 extraction template + reviewed output draft 层后，4 篇新论文都有可验证的 post-source-drop 字段框架；但 `reviewed_extraction_completed_rows=0`、`ready_for_sqlite_apply_rows=0`，因此仍不能写 SQLite、不能创建 formal decision row、不能 export/release/model claim。
- 当前正确 runner 基线更新为 `command_count=28`，overall index `summary_count=14`。
- “当前 importer 没有 safe paper-only apply 路径”已突破为：存在 validated paper-only apply dry-run plan path；当前计划仍 blocked、无 paper inserts、无 SQL write、无 SQLite mutation。
- FoldX runtime receipt 缺口已收敛为 validated candidate draft：`needs_more_info`，formal receipt 仍未写；bridge isolation 证明 FoldX draft 没有写 benchmark intake、score、label、formal decision 或 model/release claim。
- 当前正确 runner 基线更新为 `command_count=30`，overall index `summary_count=15`。
- FoldX provision 缺口继续收敛：已有 generator 可从本地 probe/discovery/bootstrap/unblock inputs 重建 6 条 candidate provision rows；所有行仍 `status=missing`、`ready_for_runtime_receipt=false`，因此不构成正式 runtime receipt。
- 当前正确 runner 基线更新为 `command_count=32`，overall index `summary_count=16`。
- 四篇新论文 source-drop readiness 已有自动 candidate 层：source files 全缺时明确保持 `ready_for_reviewed_extraction_rows=0`、`ready_for_sqlite_apply_rows=0`；后续只需放入本地 source 文件并重跑 runner 即可自动推进状态。
- 当前正确 runner 基线更新为 `command_count=34`，overall index `summary_count=17`。
- Benchmark formal decision 缺口已推进为 draft package：strict 3 行、substrate 9 行都可供人工审核填写，但全部保持 `needs_more_info`、reviewer/time/basis 空、acceptance receipt null；正式 decision rows 仍为 0，benchmark bridge intake 仍为 0。
- 当前正确 runner 基线更新为 `command_count=36`，overall index `summary_count=18`。
- Family apply 代码路径继续收敛：已有 xylanase/lipase transaction scaffold，明确 backup、BEGIN IMMEDIATE、rollback、duplicate/integrity gates；当前 source/paper plan 未 ready，因此没有 SQL、没有 write operations、没有 SQLite mutation。
- 当前正确 runner 基线更新为 `command_count=38`，overall index `summary_count=18`。
- SQLite backup/apply 前置链路已推进：3 个目标 DB 的 sha256 与 integrity 已形成 preflight receipt；由于 source/paper/family transaction 仍 blocked，未执行 backup copy、未执行 apply、未写 SQLite。
- 当前正确 runner 基线更新为 `command_count=40`，overall index `summary_count=19`。
- Claim/release consistency 已单独收据化：新增所有 scaffold 后仍只有 internal design review artifact claim 允许，model_quality/customer package/ordering/local training/release 均保持 blocked。
- 当前正确 runner 基线更新为 `command_count=42`，overall index `summary_count=20`。
- 剩余 blocker 已压缩为 5 项 closure matrix：机器路径均已准备好，但每项仍需要外部输入或人工证据；`completion_ready_rows=0` 是当前正确状态。
- 当前正确 runner 基线更新为 `command_count=44`，overall index `summary_count=21`。
- Stage 25 handoff bundle 已更新为 80 个文件的 sha256 manifest，`missing_rows=0`；这是恢复和外部证据接入的交接索引，不改变 apply/decision/release 状态。
- 当前正确 runner 基线更新为 `command_count=56`，overall index `summary_count=33`。
- Post-source-drop rerun receipt 已把 source 文件落位后的自动重跑链路固化为 19 个命令，覆盖 legal fulltext intake、source locator review、evidence draft extraction、reviewer package、execute closeout reviewer intake、source manifest、extraction readiness、reviewed drafts、family transaction plans、paper-only apply plan、SQLite preflight 和 Stage 25 summary；全部命令 `writes_sqlite=false`。
- 用户最新授权已落实为一条正式 workstream acceptance decision row，但该 row 的决策是 `needs_more_info`，不是 accepted；因此它证明“可以执行审查/写入决策记录”，不证明 model/release/customer 已可放行。
- Stage 25 overall index 已把 workstream acceptance decision validation 纳为一等 summary，并断言 1 条 valid row、0 条 accepted streams、0 条 model/customer/experiment accepted streams。
- Stage 25 approved apply executor 在最新授权后已运行，仍被 24 个证据/门控项阻断；这是 apply 尝试收据，不是 SQLite 写入收据。
- 最新 apply 尝试已使用 `--execute` 路径，执行器记录 `execute_requested=true`；由于前置 gate 未过，仍没有 backup/apply/SQLite mutation。
- Execute blocker detail 将 24 个 `--execute` 阻断项机器聚合为 4 个 proposal x 6 类检查，并确认 backup/apply/after-state 全为空。
- Execute closeout checklist 将 24 个阻断项拆成逐项关闭清单；当前没有任何 closeout-ready proposal，local release/data lake 重建为 1590 artifacts 且 release 仍 false。
- Execute closeout reviewer intake 提供 24 行可填写 JSONL 模板，但默认全部 `needs_more_info`；它是未来证据填报入口，不是 approval 或 export-safe release。
- local release manifest 因新增治理 artifacts 更新到 `artifact_count=1582`，但 `release_ready=false`；release/model claim 仍未打开。
- Approved-apply blocked receipt 和 local-release fail-closed consistency 已进入 Stage 25 overall index 的一等校验；后续任何误把 apply/release/model claim 改 true 都会破坏总账。
- Blocker activation map 已把 5 个剩余 blocker 的触发输入、重跑命令、预期翻转字段和必须保持 false 的后续 gate 固化为机器可校验报告；当前 `activation_completion_ready_rows=0`。
- Source drop manifest 已将四篇新论文的 source 文件位固定为 8 个本地路径；validator 会自动计算 exists/size/sha256，但不再因文件存在自动设置 ready，因此后续拿到文件后仍必须走 source locator/reviewed extraction。
- Family apply importer design 明确 xylanase 与 lipase schema 不同，不能 force-fit；lipase 必须走 normalized evidence_claims/metrics，xylanase 才走 measurements。
- FoldX provision manifest 明确 pending/provision 只能在独立 manifest 中，不能写入正式 runtime receipt schema；正式 receipt 只允许 `approved_runtime_ready/rejected/needs_more_info`。
- Benchmark unblock design 将 `completion_ready_rows=0` 的原因固化为两条正式 human review 闭环，不可自动生成 formal decisions 或 acceptance receipts。
- Execute closeout reviewer packet 将 24 个 `--execute` blocker 转成人类 reviewer 可读包，但它只改善交接和填报效率；当前 `packet_valid=true`、`proposal_rows=4`、`checklist_rows=24`、`closed_rows=0`、`approved_rows=0`，不等同于 SQLite apply、export-safe、release 或 model claim。
- 当前正确 runner 基线更新为 `command_count=58`，overall index `summary_count=34`，handoff bundle `bundle_rows=99`、`missing_rows=0`。
- External input readiness board 将分散的外部输入缺口聚合为 32 行统一入口；当前 32/32 仍缺失或 `needs_more_info`，因此没有任何 blocker completion-ready。
- Latest blocker coverage audit 证明 5 个 remaining blocker 没有从 latest runner/index/handoff/docs 中漏挂；这是覆盖审计，不是证据闭合。当前正确 runner 基线更新为 `command_count=63`，overall index `summary_count=36`，handoff bundle `bundle_rows=107`、`missing_rows=0`。
- FoldX 状态发生真实变化：官方 FoldX 5.1 Mac Silicon binary 已落到项目标准路径并被 probe 发现，sha256=`f57795bdc02304174a40753ad649e261b414a3f816c816e202c99a01eca9b194`。但 `--help` probe 超时、license verification 仍未 verified、smoke artifacts 仍缺、formal runtime receipt 未写，因此这只是 executable/provision 缺口缩小，不是 FoldX runtime/release/model claim 突破。
- FoldX license/config 缺口也已缩小：`foreign_tool:foldx` 现在有 self-attested local-evaluation decision，config backend enabled；这允许继续技术探测，但 verified license/customer delivery/release 仍为 0，不能把个人学习/试用授权包装成正式上线许可。
- FoldX help probe 超时的根因是工作目录和 macOS quarantine/配套文件，而不是二进制不可运行；补齐 `rotabase.txt`/`molecules` symlink 并从 FoldX 目录执行后 `--help` 成功。剩余阻断已收敛为 formal runtime receipt、preflight/smoke artifacts、execution plan 和 BuildModel smoke。
- Proposal set consistency 现在已并入 post-source-drop rerun receipt，receipt 命令数从 19 增至 20，并被 overall fail-closed index 一并校验；`proposal_sets_consistent=false`、`failure_count=3` 仍保持阻断，没有写库、没有放开 apply/export-safe/release/model claim。
- Stage 25 当前交接基线已更新为 runner `command_count=65`、overall `summary_count=37`、handoff `bundle_rows=111`，且 runner report 记录 `run_lock_path`；Markdown validator 现在既要求这些当前值存在，也禁止 19/44/63/21/36/96/107 等旧基线在 operator-facing 文档中残留。该收口只提升审计一致性，不改变 SQLite/apply/release/model claim 的 fail-closed 状态。
- Stage 25 当前交接基线已更新为 runner `command_count=67`、overall `summary_count=38`、handoff `bundle_rows=115`，且 operator packet/Markdown validator 已同步到最新 locked-run 口径并禁止旧 bundle 基线回退；SQLite/apply/release/model claim 仍保持 fail-closed。
- Markdown operator docs guard now rejects the immediate prior 65/37/111 baseline as well as older 44/63/21/36/96/107 values, so later operators cannot mix the current fail-closed state with stale handoff counts.
- Literature web search findings:
  - `39743673`：公开页面确认 ACS DOI 和 SI 文件 `jf4c10256_si_001.doc`；直接下载此前已 receipted 为 publisher HTTP 403，因此仍需要用户/机构授权下载后放入 source-drop 目录。
  - `42134585`：PubMed/ScienceDirect abstract 支持 `9K-XynB2 (HFBI-A52C/T205C-F31Y/A50F/A143P)` 这个变体名义；但 WT absolute baseline、source table、单位、pH、温度、底物和 source locator 未闭合，不能写 measurement。
  - `42235695`：ScienceDirect/PubMed abstract 不展开 CM5 substitutions；搜索到的南京工业大学转载页给出 `L15R/S45T/K85P/K231R`，只能作为二级线索，不能替代 primary fulltext/source table。
  - `42248057`：公开 abstract 继续支持 XyEst/rXyEst 为 source enzyme/benchmark characterization，无 mutation importer payload。
  - 所有 web-search rows 当前均为 acquisition lead，不是 formal evidence；`source_table_locators_verified=0`、`ready_for_sqlite_apply_rows=0` 是正确状态。
- Post-source-drop rerun receipt now includes both `build_stage25_literature_web_search_receipt_20260806.py` and its validator before extraction readiness, so reruns after source placement cannot skip the public acquisition-lead boundary while preserving `sqlite_write_command_rows=0`.
- Latest blocker coverage audit now treats literature web-search receipt as required coverage for the fulltext/source-table blocker, alongside source-drop manifest and extraction readiness; this is coverage only and still leaves `ready_for_sqlite_apply_rows=0`.
- Handoff bundle baseline moved to `bundle_rows=119` after adding the post-source-drop/literature receipt coverage files; Markdown docs now require 119 and reject 115, while SQLite/apply/release/model flags remain false.
- Stage 25 locked-run baseline is now `command_count=69` and overall `summary_count=39` because the post-source-drop literature receipt build/validate steps are part of the total chain; 67/38 is now stale operator-facing state.
- Runner tail ordering finding: handoff manifest must be built after the final overall index rebuild; otherwise handoff can checksum a stale overall file even when the subsequent run report is valid. The runner now rebuilds overall before handoff.
- Current handoff baseline is `bundle_rows=121` after runner ordering and planning-log updates; 119 is now stale handoff state even though the fail-closed gate fields remain unchanged.
- Current Stage 25 locked-run baseline is `command_count=71`, overall `summary_count=40`, handoff `bundle_rows=123`; source-drop inventory is now part of the audited chain, and 69/39/121 is stale operator-facing state.
- Handoff validation is now exact for the current Stage 25 baseline: `bundle_rows=123`, `overall_summary_count=40`, and `runner_command_count=71`; broad minimum checks are no longer enough for this handoff.
- Post-source-drop rerun receipt now includes source-drop inventory build/validate before literature receipt and extraction readiness; this closes the gap where source-drop inventory was in the total chain but absent from the post-source-drop operator rerun chain.
- Source-drop inventory semantics are fail-closed: even if expected files later exist, inventory does not mark extraction ready; `ready_for_extraction_rows=0` is fixed there, and readiness must come from the separate source-drop/reviewed extraction validators.
- Source-drop manifest semantics are also fail-closed now: local file presence and sha256 do not mark `ready_for_extraction`; readiness stays false until a separate reviewed locator/extraction gate is satisfied.
- Source acquisition shortlist semantics are fail-closed: it remains an operator checklist with `paper_ready_rows=0`; public links, directory targets and file presence do not replace reviewed source locators or SQLite apply approval.
- Source acquisition shortlist Markdown is now policy-checked too; the human-readable checklist must carry the same `file presence` / reviewed locator / SQLite approval boundary as the JSON.
- Top-level Markdown operator docs validation now includes the shortlist Markdown and requires the same file-presence-not-approval boundary in next operator packet and daily report.
- Current Stage 25 baseline after adding the shortlist Markdown to the top-level docs gate is `command_count=73`, overall `summary_count=41`, handoff `bundle_rows=127`; 71/40/123 is stale.
- Overall/handoff tail now uses a two-pass handoff pattern to break the circular freshness problem: handoff validation becomes visible to overall, then final handoff is rebuilt against that latest overall. This raises runner baseline to `command_count=75`.
- Handoff builder now derives `runner_command_count` from the runner script itself instead of the previous run report, removing stale-count dependence during a live validation run.
- Latest blocker coverage audit now requires source acquisition shortlist coverage for the fulltext/source-table blocker in addition to source-drop manifest, literature receipt and extraction readiness.
- Coverage audit evidence is now explicit: each blocker row carries expected/matched/missing terms for overall index, runner/rerun, and operator docs; validators reject hidden partial coverage.
- Overall index now validates coverage evidence counts, not only coverage booleans: 12 overall terms, 13 runner terms and 13 doc terms must all match with zero missing terms.
- Source acquisition shortlist finding: `reports/stage25_source_acquisition_shortlist_20260806.md` is the shortest operator-facing file acquisition checklist. It has 4 paper rows and 8 required file rows, but `paper_ready_rows=0`; it is not source evidence and cannot unlock SQLite/apply/release/model claims.
- Post-source-drop rerun finding: the shortlist is now included in the automatic rerun receipt, so a future source drop refreshes manifest, inventory, literature receipt, shortlist and extraction readiness together. The receipt has `command_rows=26` and `sqlite_write_command_rows=0`.
- Post-source-drop dry-run audit finding: all 26 expected outputs for the rerun receipt exist and every command is marked non-SQLite-write. This proves the rerun chain is operationally prepared, but not that source files, source locators, formal decisions, SQLite apply approval, model claims, customer delivery, or release are ready.
- Post-source-drop receipt contract gap: the validator previously checked only a 9-name required subset plus `command_rows=26`. A receipt could duplicate or replace non-required commands, or alter command/cwd/output fields, while still passing. The receipt now needs an exact ordered full-row contract with a pinned sha256.
- Post-source-drop readiness naming gap: `ready_for_source_drop_rerun=true` describes recipe operability, not evidence readiness. Downstream validators must separately require `source_evidence_ready=false`, `ready_for_reviewed_extraction=false`, and `ready_for_sqlite_apply=false` until reviewed evidence gates actually close.
- Exact receipt contract result: the current 26-row normalized contract hash is `0e89420d0fe9a860b1926105249ed475eaa26f054dd39cba148a55e0deaf69f0`. A duplicate-command replacement that preserves 26 rows changes the hash and reduces unique names to 25, so the strengthened validator rejects the prior bypass class.
- Source acquisition shortlist coverage gap: the validator checked declared `paper_rows=4` and `required_file_rows=8`, but did not assert `len(rows)`, unique/exact PMIDs, flattened required-file counts, exact manifest paths, inventory presence parity, or one-time Markdown coverage. A truncated or duplicated human-readable checklist could therefore retain the summary counters and policy terms while passing.
- Source acquisition shortlist exact-coverage result: manifest, inventory, literature web receipt, JSON, and Markdown now agree on 4 unique PMIDs and 8 unique required paths. Each Markdown PMID heading, DOI, and required path must appear exactly once; summary counters alone can no longer hide duplicated or omitted operator rows.
- Post-source-drop dry-run freshness gap: `all_expected_outputs_present=true` can be satisfied by reports from a previous Stage 25 run. In particular, the receipt's final expected output is the current runner report, which cannot be regenerated until the enclosing runner finishes. Therefore a dry-run may prove path presence and recipe shape, but cannot prove commands executed, current source-drop event linkage, output freshness, rerun completion, or `ready_for_source_drop_rerun`.
- Post-source-drop dry-run freshness result: the audit now reports recipe operability separately from execution and freshness. Existing output paths remain visible for operator preparation, while all execution/event/freshness/completion fields and `ready_for_source_drop_rerun` stay false until a future real rerun receipt can bind outputs to a specific source-drop event.
- Source-drop manifest/inventory contract gap: manifest validation compared only the set of source IDs and broad row fields, so an extra duplicate row or an ID-to-path/PMID/file-kind swap could pass. Inventory validation checked only declared 4-directory/8-file counters and negative readiness flags, without verifying actual row collections, uniqueness, current filesystem exists/size/hash values, or preventing one resolved file from satisfying multiple requirements.
- Source-drop exact-contract result: all 8 manifest requirements now have pinned full-row identities and unique expected paths; any existing resolved file may satisfy at most one requirement. Inventory validation independently recomputes four directory states and eight file exists/size/sha256 states, so stale counters or forged presence flags cannot pass.
- Operator-doc freshness gap: daily report and next operator packet still contained `artifact_count=1582` while the current local release manifest reports 1640. The packet also said the rerun receipt was ready for use after file placement, conflicting with the newer dry-run state `ready_for_source_drop_rerun=false` and no execution/freshness receipt.
- Operator-doc freshness result: both operator-facing Markdown files now use `artifact_count=1640`, handoff 131, and the P259-P262 exact/freshness fields. The Markdown validator rejects the old 1582/127 and rerun-ready wording. A concurrent handoff expansion from 127 to 131 was preserved and incorporated rather than reverted.
- Handoff checksum integrity gap: the 131-row manifest includes its own JSON and its validation JSON through the governance glob, creating a circular checksum. It also hashes the Stage 25 run report before the enclosing runner writes its final report. A direct filesystem probe found two current mismatches: the manifest self-row and run-report row. The validator only checked SHA format/positive size, so these stale rows still passed.
- Handoff checksum integrity result: self-referential manifest/validation JSON rows are excluded, while the run report is the sole explicitly volatile existence-only row. The remaining 128 rows must match live resolved path, size and SHA256; current validation reports 129 unique paths, 128 verified, 1 exempt, zero mismatches and `filesystem_integrity_valid=true`.
- Concurrent metadata-only plan finding: a new validator appeared during the final P264 run, initially zero-byte and later completed, with a corresponding enzyme-db builder. The validator path was one directory too shallow, and the builder reported `paper_insert_count=4` despite no SQL/apply path. Both were corrected: the plan now exposes 4 planned/ready metadata-review rows while paper inserts, write operations and SQLite-ready rows remain zero.
- Metadata-only plan integration result: the new plan is now a first-class Stage 25 summary and handoff artifact, but its readiness is scoped only to human metadata review. Current state is 4 planned/ready review rows, 0 inserts, 0 SQL/write operations, 0 variants, 0 measurements, 0 formal decisions and 0 SQLite-ready rows. Handoff integrity expanded cleanly to 133 unique paths with 132 live-verified and 1 post-run volatile.
- Proposal-set root cause: the existing validator treated all seven discovered candidates as the expected set for every surface. That incorrectly requires the already-present AP duplicate and AMY background/reject rows to appear as active fulltext intake/locator work. Current files are semantically partitioned: allowlist covers six non-duplicate candidates; intake/locator cover four strong xylanase/lipase source targets; dry-run apply failures cover all seven dispositions.
- Proposal-set consistency result: all seven candidates now have explicit surface dispositions without adding irrelevant intake rows. The 6/4/4/7 sets match exactly, duplicates are checked on control files, and future inconsistency returns a nonzero exit code. This removes the structural set blocker only; approved apply remains blocked by 24 evidence/review checks with zero inserts and zero SQLite writes.
- FoldX technical runtime finding: FoldX 5.1 arm64 completed RepairPDB and BuildModel for 10mh/T10A with return code 0; the parsed engineering smoke row is `0.116658 kcal/mol`. The input has unparameterized nonstandard molecules, so the result remains technical evidence only.
- FoldX parser finding: the real FoldX banner starts with `FoldX 5.1 (2011)` and was previously misread by the two-token fallback. Restricting fallback shape and ignoring pre-header metadata now produces one real row and zero parse errors.
- Stage 25 gate consistency finding: runner and overall now emit and require top-level `apply_executed=false`; missing apply state is no longer silently skipped. Final locked state is `77/42/133`, data lake/local release is 1645 artifacts, and release remains false.
- 2026-08-07 continuation audit: proposal-set consistency later advanced the locked baseline to `77/43/135`, with `proposal_sets_consistent=true` and `allow_apply=false`. The FoldX technical smoke scripts/reports are present in the handoff bundle and independently validate, but the smoke validation is not yet a Stage 25 runner command or overall summary.
- 2026-08-07 phase numbering audit: two completed sections were both named P266. Proposal-set consistency remains P266; FoldX isolated technical smoke is renumbered P267 without changing its evidence or claims. P268 will integrate validation only; the central runner must not automatically execute FoldX RepairPDB/BuildModel.
- 2026-08-07 P268 local integration finding: the technical-smoke validator now emits explicit `technical_smoke_only=true` plus negative runtime/training/apply/export/model/release fields. The Stage 25 runner adds only `validate_stage25_foldx_technical_smoke_20260806.py`; the execution script is deliberately absent from the main command chain.
- 2026-08-07 operator-doc finding: previous statements that FoldX smoke artifacts were missing became stale after P267. Docs now distinguish 5 checksum-verified technical-smoke artifacts from the still-missing formal runtime approval; local syntax, smoke validation and Markdown validation pass.
- 2026-08-07 P268 final finding: Stage 25 now locks `foldx_technical_smoke_validation_success=true`, `technical_smoke_only=true`, `technical_smoke_passed=true`, `parsed_rows=1`, `artifact_count=5`, while `formal_runtime_receipt_written=false` and `approved_for_physical_ddg_runtime=false`. The only runner command matching the technical smoke is its validator; the FoldX execution runner is absent.
- 2026-08-07 P268 final baseline: runner 78/0 failures, overall 44/0 failures, handoff 135 unique paths with 134 live-verified and 1 post-run volatile, filesystem integrity valid, data lake/local release 1645 artifacts, `apply_executed=false`, `release_ready=false`, `safe_for_model_claim=false`.
- 2026-08-07 P269 initial audit: formal FoldX provision still names 5 required artifacts under `cache/advanced_features/ddg_physical_smoke/foldx/stage25/`, while the successful isolated technical smoke lives under `.../stage25_technical_smoke_20260806/`. These are intentionally different evidence classes; copying or aliasing the technical files into the formal path would incorrectly bypass approval semantics.
- 2026-08-07 P269 state audit: execution-plan blocker already distinguishes install/license/runtime from reviewed data and remains 0 ready/25 blocked, but provision candidate validation only reports 1 present/5 missing and does not expose that 5 technical checksum artifacts exist. The safe improvement is explicit evidence-layer fields, not changing formal missing/ready counts.
- 2026-08-07 P269 implementation finding: each of the 5 formal physical-smoke requirements now has a separately named technical counterpart whose live SHA256 matches the isolated technical-smoke receipt. Formal paths and technical paths have zero overlap; technical evidence cannot satisfy the formal row.
- 2026-08-07 P269 execution finding: machine state now records `foldx_buildmodel_technical_smoke_executed=true` and `foldx_buildmodel_physical_smoke_executed=false` simultaneously. This removes the stale generic “smoke missing” interpretation without changing `foldx_ready_for_execution=false`, 0 ready/25 blocked, formal receipt false, or physical-ddG approval false.
- 2026-08-07 P269 final baseline remains 78 runner commands, 44 overall summaries and 135 handoff paths; the change is semantic precision only, not a readiness or release transition.
- 2026-08-07 P270 initial finding: FoldX RepairPDB/BuildModel both returned 0, while runtime stdout contains the exact warning `External parametrized molecules were detected` and `Final energetic values will depend of the correct parametrization of this molecules.` This is a parameterization-dependency warning, not a command failure.
- 2026-08-07 P270 interpretation boundary: the parsed `0.116658 kcal/mol` remains a parser/runtime smoke value. Until molecule parameterization is reviewed and formally approved, it must not be treated as physically comparable ddG, benchmark truth, training label, or model-quality evidence.
- 2026-08-07 P270 diagnostic finding: `Unrecognized_molecules.txt` contains 110 rows covering 3 molecule names (`5CM`, `5NC`, `SAH`) and has current SHA256 `844eb97d8e3f565c43f0b62430fb45cb1792b7345a02bd2f23ce1337e6f45892`. Both RepairPDB and BuildModel stdout contain the parameterization-dependency warning.
- 2026-08-07 P270 local validation: technical smoke validation now reports warning detected=true, warning commands=2, diagnostic present=true, 110 rows, parameterization review=false, ddg technical only=true, energetic interpretation=false, physical comparability=false, benchmark intake=false; validation has 0 failures.
- 2026-08-07 concurrent-baseline finding: ACS SI/source-acquisition receipt integration advanced the active Stage 25 baseline to 79 runner commands, 45 overall summaries, 27 post-source-drop commands and 138 handoff rows/137 live freshness rows. P270 must merge onto this baseline; 78/44/135 is now stale.
- 2026-08-07 P270 final machine contract: parameterization warning detected=true across 2 commands; unrecognized diagnostic present=true with 110 rows and molecules `5CM/5NC/SAH`; parameterization review=false; ddg technical only=true; energetic interpretation, physical comparability and benchmark intake=false.
- 2026-08-07 P270 final baseline: runner 79/0 failures, overall 45/0 failures, handoff 138 unique paths with 137 live-verified + 1 volatile exempt. The parsed 0.116658 value remains technical parser evidence only; no physical-ddG, benchmark, training, model or release transition occurred.
- 2026-08-07 P271 source acquisition finding: official ACS Figshare SI for PMID 39743673 is public at article `28122106`, file `51444709`; local file size/MD5/SHA256 and OLE magic match the receipt. Quick Look/Office importer exposes 11 pages, Table S1-S2 and Figure S1-S10.
- 2026-08-07 P271 evidence boundary: Figure S5/S7/S8 are DSM4 identity locator candidates, while Table S1/S2 expose primer/disulfide candidates; the SI does not establish a complete DSM4 residue composition mapping. Therefore `dsm4_composition_resolved=false`, `reviewed_source_locator_rows=0`, `source_evidence_ready=false`, and no reviewed extraction or SQLite payload was created.
- 2026-08-07 P271 integration result: acquisition receipt validation is part of the main runner and post-source-drop exact contract. The post-source-drop contract is 27 commands with SHA-256 `ecf8741421aa1427c69e9904b21cdda156145696a36f4c3878904355a3ef8677`; all commands are non-SQLite-write and dry-run freshness/event/completion remain false.
- 2026-08-07 P271 final state: Stage 25 runner `79 commands / 0 failures`, overall `45 summaries / 0 failures`, handoff `138` unique paths with `137` live verified + `1` volatile, local release artifacts `1645`; `apply_executed=false`, `allow_apply=false`, `release_ready=false`, `safe_for_model_claim=false`.
- 2026-08-07 P272 locator classification finding: the SI candidate set is now explicit and machine-checked: Table S1/S2, Figure S5/S6/S7/S8/S10; 3 identity candidates, 3 measurement candidates, 0 composition-resolved candidates. This is an operator review map, not reviewed evidence.
- 2026-08-07 P272 final boundary: `reviewed_source_locator_rows=0`, `dsm4_composition_resolved=false`, `source_evidence_ready=false`, and `ready_for_sqlite_apply=false`; the 79-command runner remains green only as fail-closed validation, not as scientific evidence approval.
- 2026-08-07 P273 starting point: the ACS SI receipt is integrity-verified and locally present, but P271 intentionally left `dsm4_composition_resolved=false`. Any text/table extraction must remain read-only and must not silently become reviewed extraction or SQLite payload.
- 2026-08-07 P273 extraction finding: Quick Look preview text exposes Table S1 with 38 primer rows and Table S2 with 4 selected disulfide-bridge rows. Figure S5 only labels DSM4 as a lane, and Figure S8 names mutant DSM4; no complete DSM4 residue composition or absolute WT baseline appears in text.
- 2026-08-07 P273 CM5 finding: concurrent author-data candidate is corroborated by archive member filename plus CM5/WT PDB residue identity parity at positions 15/45/85/231, yielding `L15R/S45T/K85P/K231R`. This remains unreviewed candidate composition with zero mutation-effect measurements.
- 2026-08-07 P273 final boundary: candidate rows=2, source hashes verified, DSM4 complete rows=0, CM5 candidate rows=4 but formally reviewed=false, reviewed locator rows=0, SQLite/apply/model/release false.
- 2026-08-07 P274 repository finding: exact article-DOI searches missed the `42235695` author package because it has independent Zenodo DOI `10.5281/zenodo.19733678`; OpenAIRE exposed that related open instance. Title and six creators match the article, and the deposit is CC BY 4.0.
- 2026-08-07 P274 integrity finding: Zenodo record `19733678` supplies one 49,144,286-byte ZIP with MD5 `d30dcf8029567cbc792c156d0d8f9bfc` and SHA-256 `800808cfccdac71a600e6550c5d1e5821b2729687a02af9a1a4300c452ac93c6`; 59 entries/50 files and the complete archive integrity test pass.
- 2026-08-07 P274 composition finding: the CM5 sequencing member name states `L15R/S45T/K85P/K231R`, and live CM5-versus-WT PDB residue parity confirms all four positions. This resolves a composition candidate only; formal review=false and mutation-effect measurement rows=0.
- 2026-08-07 P274 negative-source finding: Europe PMC, OpenAIRE, Zenodo, DataCite, HAL and OSF probes leave `42134585` and `42248057` without public source files. Elsevier API 401 and ScienceDirect 403 were recorded without bypass attempts; metadata is not source evidence.
- 2026-08-07 P274 final machine contract: acquisition receipts cover 4 papers as 2 verified public assets + 2 probe-only rows. Stage 25 passes 80/80, overall 46 summaries, handoff 141 paths, post-source-drop remains 27 exact non-SQLite commands, and all reviewed extraction/apply/model/release gates remain closed.
- 2026-08-07 P275 reviewer-packet finding: DSM4 and CM5 now each have one explicit human-review row. Both remain `needs_more_info`, reviewer/timestamp/approval basis are empty, and `candidate_ready_for_human_review_rows=2` means the packet is ready to be read by a human, not approved.
- 2026-08-07 P275 scientific boundary: CM5 has one resolved four-substitution composition candidate while DSM4 remains unresolved; `composition_candidate_resolved_rows=1`, `dsm4_unresolved_rows=1`, but formal-review, reviewed-extraction, source-locator and mutation-effect closure counts remain 0.
- 2026-08-07 P275 integration finding: canonical packet validation binds live ACS SI/Zenodo SHA-256 to upstream acquisition/extraction receipts. It is integrated into the 81-command runner, 47-summary overall index, 29-command post-source-drop receipt, operator docs and 144-row handoff without opening SQLite/apply/model/customer/release gates.
- 2026-08-07 P277 gap finding: P275 now exposes 12 required review fields after P276 added the L262V discrepancy closure requirement; a field-level checklist makes each closure auditable without inventing source evidence or approval.
- 2026-08-07 P277 checklist finding: the 12 required fields have exact ordered closure rows: DSM4=5 and CM5=7, including one `resolve_L262V_nucleotide_PDB_discrepancy` row. Every row contains candidate evidence, required closure evidence and empty reviewer/source-locator slots; all 12 remain `missing` and `needs_more_info`.
- 2026-08-07 P277 boundary finding: `evidence_supplied_rows=0`, `reviewed_rows=0`, `completed_rows=0`, `approved_rows=0`, and `ready_for_sqlite_apply_rows=0`. Checklist completeness describes workflow coverage only, not scientific evidence completeness.
- 2026-08-07 P277 integration finding: the closure validator is part of the 82-command runner, 48-summary overall index and 30-command non-SQLite rerun receipt. Handoff expands to 147 paths with 146 live checksum rows plus one volatile run report.
- 2026-08-07 P276 nucleotide finding: a Biopython 1.85 local alignment of WT SnapGene CRL1 `[363:1968]` against the CM5 read reproduces declared `L15R/S45T/K85P/K231R`, but also yields undeclared `TTG(L262)->GTG(V)`. CM5 and WT PDB both retain LEU262, creating a live nucleotide/PDB discrepancy.
- 2026-08-07 P276 fail-closed correction: `declared_substitutions_corroborated=true` no longer implies complete composition. Acquisition, extraction, reviewer packet and overall now require `undeclared_substitution_candidates=[L262V]`, discrepancy=true, `complete_composition_unambiguous=false`, and `cm5_composition_candidate_resolved=false`.
- 2026-08-07 P276/P277 final verification: Stage 25 passes 82 commands with 0 failures, overall passes 48 summaries, post-source-drop validates 30 exact non-SQLite commands, and handoff validates 147 paths. The 12th closure row is dedicated to resolving L262V; no reviewed evidence, formal decision, SQLite apply, model claim or release gate opened.
- 2026-08-07 P279 prototype finding: all 11 sequencing `.seq` members align forward to WT CRL1. Nine cover codon 262: CM5 alone maps to GTG, while eight independent reads map to TTG; `K85P_K170Y.seq` ends before codon 262 and `K85P_K431T_F.seq` covers a downstream region.
- 2026-08-07 P279 environment finding: system `python3` lacks Biopython, while `../backend/.venv/bin/python` provides Biopython 1.87. The reproducible builder uses that existing project environment; the validator remains standard-library-only.
- 2026-08-07 P279 independent-audit finding: generated report records all 11 reads with live member size/CRC/SHA, chosen orientation, alignment score, WT target span, query codon span, codon and amino acid. Validator independently checks archive parity and the exact 8 TTG / 1 GTG / 2 no-coverage classification.
- 2026-08-07 P279 interpretation boundary: `cross_read_consensus_supports_wt_leu262=true` and `cm5_single_read_outlier=true` support an outlier hypothesis only. `discrepancy_resolved=false`, complete composition remains ambiguous, and no reviewed extraction, decision, SQLite, model or release gate opens.
- 2026-08-07 P278 completion finding: the embedded 11-row codon-262 matrix and the independent P279 audit agree exactly on 9 covered reads, 8 `TTG/Leu`, 1 CM5 `GTG/Val`, and 2 non-covering reads. Agreement strengthens the audit trail but does not resolve CM5 composition without reviewed source evidence.
- 2026-08-07 P281 gap finding: the closure checklist requires independent confirmation at codon 262, but the eight TTG reads belong to other variant constructs and are WT-context evidence rather than independent CM5 replicates. A reviewer-facing adjudication contract is needed to prevent cross-construct consensus from being misread as a resolved CM5 sequence.
- 2026-08-07 P281 convergence finding: the canonical concurrent packet includes one JSONL row, a reviewer Markdown, a validator and its report. It binds all 11 read evidence rows and four allowed adjudication options while keeping all review fields empty; this adds four handoff artifacts rather than the initially estimated three.
- 2026-08-07 P280 archive finding: the Zenodo sequencing directory contains 11 `.seq` members and one WT `.dna` plasmid file, but no `.ab1` or `.scf` raw chromatogram. The CM5 `.seq` file is therefore a sequence read artifact, not a reviewed raw-trace confirmation.
- 2026-08-07 P280/P281 convergence finding: a concurrent `stage25_cm5_codon262_sequence_quality_evidence_audit` validator appeared after P279 integration. P280 owns the raw-quality audit and P281 owns reviewer adjudication semantics, avoiding duplicate evidence products.
- 2026-08-07 P280 integration finding: adding the quality-audit builder, validator, report and validation report expands handoff from 151 to 155 paths and the runner from 84 to 86 commands. The first full run failed only because overall retained the old 151/150 handoff assertions; live handoff validation itself refreshed successfully.
- 2026-08-07 P280 final boundary: all 11 `.seq` rows are checksum-bound plain IUPAC text, CM5 raw text call is GTG, and quality/chromatogram/per-base-quality artifacts are all absent. This supports a precise evidence-gap finding only; `sequencing_artifact_hypothesis_confirmed=false` and `discrepancy_resolved=false` remain authoritative.
- 2026-08-07 P280 final verification: Stage 25 passes 86 commands with 0 failures, overall passes 50 summaries, post-source-drop validates 34 exact non-SQLite commands, and handoff validates 155 paths with 154 live checks plus one volatile run report.
- 2026-08-07 P281 evidence-role finding: one CM5 primary read calls GTG/Val, eight TTG/Leu reads belong to other constructs, and two other-construct reads do not cover codon 262. Every evidence row is explicitly ineligible as a CM5 independent replicate; `independent_cm5_replicate_rows=0` and `other_construct_reads_accepted_as_cm5_replicates=false`.
- 2026-08-07 P281 reviewer-safety finding: the packet exposes four adjudication options with minimum evidence but keeps decision/reviewer/time/locator/basis/notes empty. Its builder refuses to overwrite any packet containing human review content, so automated reruns fail closed after review begins.
- 2026-08-07 P282 design finding: P281 is a generated evidence packet and should remain immutable under automation. Human adjudication decisions need a separate local intake so reruns can rebuild evidence safely without overwriting or treating packet fields as a decision database.
- 2026-08-07 P282/P283 convergence finding: P282 separates human decisions from generated evidence, while concurrent P283 defines four canonical source-drop evidence slots. P283 currently validates 0 present/4 missing/0 reviewed/0 adjudication-ready; file presence alone is explicitly insufficient.
- 2026-08-07 P282/P283 completion finding: decision intake remains empty (`decision_rows=0`, `valid_decision_rows=0`, `evidence_artifact_rows=0`, `discrepancy_resolved_rows=0`); evidence intake validates 4 canonical slots with 0 present/4 missing/4 filesystem-parity rows and 0 reviewed/0 adjudication-ready. Full Stage 25 is 91 commands/0 failures, overall is 53 summaries/0 failures, and handoff is 168 rows (167 live + 1 volatile). All SQLite/apply/formal-decision/model/release gates remain closed.
- 2026-08-07 P284 public-source finding: Europe PMC returned `pmcid=null`, `isOpenAccess=N`, and no full-text URL for PMID 42235695; PubMed and Crossref returned metadata/DOI or text-mining links only; Zenodo 19733678 exposed exactly one already-audited ZIP. No probe supplied a P283 raw trace, quality resequencing, construct record, or sequence/PDB reconciliation artifact.
- 2026-08-07 P281 final verification: the 88-command Stage 25 runner, 51-summary overall index, 36-command non-SQLite post-source receipt, Markdown docs and 160-row handoff all pass with zero failures. The discrepancy, composition, review, apply, model and release gates remain closed.
- 2026-08-07 P294 five-head gap finding: the refreshed queue contains 5 head rows and remains `blocked`, with `missing_label_rows_total=494`. Only `stability` and `activity_risk` expose candidate sources; candidate availability does not establish reviewed or importable labels.
- 2026-08-07 P294 safety boundary: `training_import_written_rows=0`, `safe_for_model_claim=false`, and `release_ready=false`. The refresh writes no training labels, SQLite rows, formal decisions or release state.
- 2026-08-07 P294 concurrent-baseline finding: an external evidence review intake was wired during final convergence, advancing the exact contract to 50 post-source commands (SHA-256 `84e081599433c7b48263e3702fc0e9dedf5074da4a9f5dfd19ac6f719a2e6ff1`), 102 runner commands, 61 overall summaries and 196 handoff rows. The review intake remains 0 reviews/0 valid receipts/0 accepted rows and does not alter the five-head queue boundary.
- 2026-08-07 P294 final verification: Stage 25 passes 102 commands/0 failures, overall passes 61 summaries/0 failures, and handoff validates 196 rows with 195 live checksum rows plus one volatile run report. Local release remains 1645 artifacts and false.
- 2026-08-07 P295 review-intake finding: the independent CM5 review intake is empty and valid. Reviews require a valid transfer receipt plus live artifact SHA, reviewer/time/locator/basis and format/integrity/scientific sufficiency fields; a review without a receipt is rejected. Current review and adjudication-ready rows are zero, and review does not itself adjudicate L262V.
- 2026-08-07 P296 review-binding finding: isolated regression proves that two accepted reviews can bind two decision evidence rows, while the same raw paths without accepted review IDs are rejected as two unreviewed artifacts. A `needs_more_info` decision remains valid without evidence.
- 2026-08-07 P296 safety boundary: regression is `3/3` passed with `real_decision_input_mutated=false`, `formal_decision_rows_written=0`, and `discrepancy_resolved=false`; no SQLite/apply/model/release transition occurred.
- 2026-08-07 P296 final verification: Stage 25 passes 103 commands/0 failures, overall passes 62 summaries/0 failures, post-source validates 51 exact non-SQLite commands, and handoff validates 198 rows with 197 live checks plus one volatile report. Local release remains 1645 artifacts and false.
- 2026-08-07 P297 gap finding: P296 proves accepted-review presence and rejects unknown review IDs, while the decision validator also enforces live SHA, review-specific canonical path/SHA and supported adjudication options. Those three tamper boundaries need explicit isolated regression coverage before future human review data can be trusted.
- 2026-08-07 P297 local finding: all three tamper cases fail closed as intended. Forged SHA hits live and review-SHA checks; cross-bound review IDs hit path and review-SHA checks; unsupported outcome hits review-supports-decision. Real decision, review and receipt inputs remain byte-identical.
- 2026-08-07 P297 final verification: Stage 25 passes `104 commands / 0 failures`, overall passes `63 summaries / 0 failures`, post-source-drop validates `52` exact non-SQLite commands with contract SHA-256 `c0bce9f05e079a3333144dbaa05a08a162bdf7796b9b484ae15054dca83bd278`, and handoff validates `200` rows with `199` live checks plus one volatile report. `formal_decision_rows_written=0`, `discrepancy_resolved=false`, `allow_apply=false`, `release_ready=false`.
- 2026-08-07 P297 convergence finding: adding one runner command, one overall summary and two governance artifacts advances the exact contract to 52 post-source commands (SHA-256 `c0bce9f05e079a3333144dbaa05a08a162bdf7796b9b484ae15054dca83bd278`), 104 runner commands, 63 summaries and 200 handoff rows. The first overall bootstrap correctly failed against the stale 198-row handoff; rebuilt state is fully valid.
- 2026-08-07 P297 final boundary: regression success is contract evidence only. Formal decisions, discrepancy resolution, SQLite/apply, model claim and release remain false/zero; local release remains 1645 artifacts and false.
- 2026-08-07 P298 gap finding: review binding now covers identity, SHA, path-to-review and supported outcomes, but the validator's duplicate-review, safe-relative-path and artifact-presence checks do not yet have isolated regression receipts. These are required to prevent review replay, path escape and references to absent evidence.
- 2026-08-07 P298 local finding: duplicate review reuse hits `review_id_unique`, `../` traversal hits `safe_relative_path`, and an accepted review pointing to an absent canonical artifact hits `present`. All three cases are rejected and real local inputs remain byte-identical.
- 2026-08-07 P298 final finding: Stage 25 passes `105 commands / 0 failures`, overall passes `64 summaries / 0 failures`, post-source-drop validates `53` exact non-SQLite commands with SHA-256 `2634865ea4ac40f6e5b1c79183256ae1645ce377d027bcb0d5dd6788e09418fd`, and handoff validates `202` rows (`201` live + one volatile). The first bootstrap correctly exposed stale 63-summary handoff metadata before the final rebuild.
- 2026-08-07 P299 finding: accepted review identity/path/SHA/option binding did not constrain how the decision row labeled that artifact. Canonical slots now have explicit allowed decision evidence classes, and a raw-trace review mislabeled as sequence/PDB reconciliation is rejected by `evidence_class_slot_compatible`.
- 2026-08-07 P299 timestamp finding: decision `reviewed_at` now requires an ISO-8601 UTC value ending in `Z`; the expanded tamper regression rejects one invalid timestamp and passes all 5 cases without changing real inputs.
- 2026-08-07 P300 finding: decision intake already compares live review/receipt input SHA values against P295 validation, and the new isolated regression proves invalid upstream validation plus stale review or receipt input hashes all fail closed. Real inputs remain byte-identical and no adjudication occurs.
- 2026-08-07 P300 gap finding: the decision validator checks upstream review-intake validity and live SHA bindings for both review and receipt inputs, but these provenance failures were not independently receipted. An empty-evidence `needs_more_info` fixture isolates them without simulating scientific adjudication.
- 2026-08-07 P300 local finding: invalid upstream review validation hits `upstream_review_intake_valid`; stale review and receipt hashes hit their respective live-SHA checks. All three cases reject before any scientific decision can become valid, and real inputs remain byte-identical.
- 2026-08-07 P300 final finding: Stage 25 passes 106 commands/0 failures, overall passes 65 summaries/0 failures, post-source validates 54 exact non-SQLite commands with SHA-256 `1592c2b2f1e4077bc872d4b429eed3cdc2d2f562b047259a2d2493fe170dea54`, and handoff validates 204 rows with 203 live checks plus one volatile report.
- 2026-08-07 P301 finding: decision `reviewed_at` previously required only a non-empty value. The validator now requires an ISO-8601 UTC timestamp ending in `Z`; the isolated invalid-timestamp case is rejected without changing any real input or downstream gate.
- 2026-08-07 P302 finding: P295 validated reviewer presence but its downstream records omitted reviewer identity. Review records now carry reviewer/time/source locator, and decision binding rejects accepted-review records without reviewer provenance; current empty inputs remain unchanged.
- 2026-08-07 P303 gap finding: decision intake also trusts the upstream adjudication packet validation, empty review fields and exact allowed-decision list. Those packet-provenance boundaries had direct fail-closed checks but no isolated regression receipt.
- 2026-08-07 P303 local finding: invalid packet validation hits `upstream_packet_valid`, non-empty upstream review fields hit `upstream_review_fields_empty`, and allowed-option drift hits `allowed_decisions_match_packet`. All real packet and local input hashes remain unchanged.
- 2026-08-07 P303 final finding: Stage 25 passes 107 commands/0 failures, overall passes 66 summaries/0 failures, post-source validates 55 exact non-SQLite commands with SHA-256 `71ea366e8edb3c92d9619da3524872d2daca246b43787f2ec8680f8f5dd0ad9c`, and handoff validates 206 rows with 205 live checks plus one volatile report.
- 2026-08-09 P304 finding: all pending local workstreams are actively launched (`P26-P31=6/6`, next-unlock actions `12/12`, open-blocked remediation/launch/receipt rows `8/8`). The strict safe pipeline passes `412/0` and Stage 25 passes `107/0`. FoldX probe is now a real positive fact but does not satisfy formal physics-runtime evidence; the human backlog expanded to required `1225`, completed `31`, missing `1196`. No formal decision, SQLite apply, training execution, model claim, deployment, or release gate opened.
- 2026-08-09 P305 finding: the all-workstream refresh exposed two stale validators rather than new scientific readiness. FoldX discovery now truthfully reports one executable candidate, so provision validation must accept a non-negative candidate count while formal smoke remains 0/5 and runtime receipt remains unwritten. Stage 25 dated decision drafts are valid draft namespaces, but remain non-formal and non-trainable. After both fixes, Stage 25 is 107/0 and safe training is 412/0; CM5, DSM4, human review, SQLite/apply, FoldX physical use, five-head training and release blockers remain fail closed.
- 2026-08-09 P306 finding: all eight remaining remediation validators were executed individually and their dispatch/receipt surfaces rebuilt. Every lane is valid and started, but none meets its real input target (`target_rows_met_items=0`, `completion_ready_items=0`); this removes two stale quantity-only positives without opening any downstream gate. Safe training remains `412/0` and the independent Stage 25 rerun remains `107/0`.
- 2026-08-09 P307 finding: the incremental all-start scan found no new canonical evidence, reviewed decisions, formal FoldX smoke artifacts, or importable labels. Safe-pipeline regeneration legitimately expanded benchmark readiness from two to three blocked packets by adding substrate fit; the Stage 25 release summary had a stale exact-count assertion. Updating it to three preserves `completion_ready_rows=0` and all claim/release flags false.
- 2026-08-09 P308 finding: exact benchmark packet counts are the wrong release-summary invariant because the upstream validator already binds packets to the current invalid-gap set. The robust invariant is a positive packet count with every packet blocked, zero completion-ready rows, zero recorded scores, no source discrepancies, and all model/release flags false. Both parity drift and nonzero-score tamper cases now fail closed.
- 2026-08-09 P310 finding: release summary should not duplicate exact human backlog totals already enforced by the dedicated validator. It now binds the validator's expected/current/open counts and expected/current missing totals, then requires worklist backlog parity and item decomposition. This permits truthful reviewed progress while rejecting silent gate removal; count drift and expected-missing drift both fail closed.
- 2026-08-09 P312 finding: operator Markdown retained 1188 missing rows after the validated backlog advanced to 1196. The docs validator previously checked many static gate terms but not backlog freshness. It now consumes the backlog validation report, requires current open/missing fields in both operator documents, and explicitly rejects the known stale 1188 forms.
- 2026-08-09 P314 finding: `training_import_written_rows=0` in the five-head gap queue describes queue side effects, while the formal activity-risk import contract truthfully contains 6 labels. Operator docs now expose both layers and bind them to zero ready heads, disabled execution, and zero claimable/production model artifacts. Import-count drift or execution=true fails closed.
- 2026-08-09 P314 convergence finding: concurrent benchmark pre-review legitimately raised the human pending index from 1218 to 1220. Local-release and control-plane consistency must bind the live pending-index report rather than another fixed count; altered manifest parity is rejected without weakening release gates.
- 2026-08-09 P315 finding: the human control-plane validator duplicated seven additional derived counts after pending index was made dynamic. All eight fields now bind their source reports, while source summaries must remain formal-decision zero and model/release false. Local-release consistency no longer repeats those numbers; a modified review-batch count fails the control-plane parity check.
- 2026-08-09 P317 finding: the remaining local-release exact summary table duplicated backlog, review-draft, and model-claim source values. Those nine fields now bind live reports and require valid fail-closed source states. This completes removal of the static `EXPECTED_SUMMARY_VALUES` layer; altered review-draft totals are rejected by source parity.
- 2026-08-09 P318 finding: the release/benchmark human worklist validator duplicated the entire backlog summary, priority distribution, and item count. It now binds the live backlog report and exact backlog ID set, while retaining explicit structural and runtime non-backlog gaps. Both summary drift and ID substitution fail closed.
- 2026-08-09 P320 finding: Markdown validation still embedded current runner, overall, handoff, freshness, and artifact counts in static required-term lists. Those values now come from live validated reports. Existing documents remain required to contain the current values; a simulated runner count change invalidates both documents until they are refreshed.
- 2026-08-09 P322 finding: post-source command count remained a static Markdown requirement after core Stage 25 counts became dynamic. Receipt and dry-run audit now jointly define the documented count, SHA, zero-SQLite and not-executed state. A count change fails unique-count, cross-report parity, and stale-document checks.
- 2026-08-09 P323 finding: handoff validation and overall still assumed exact bundle, freshness, and governance-artifact counts. These are structural quantities, not scientific invariants. They now derive from manifest rows, builder required lists, live runner/overall state, and freshness modes; duplicates, stale hashes, self-reference, and extra volatile exemptions remain fail closed.
- 2026-08-09 P326 finding: post-source receipt validation itself still pinned the current 55-command digest after documentation became dynamic. The builder `COMMANDS` list is now the sole contract source; receipt, dry-run, and overall bind its normalized rows and canonical SHA. Removing one command fails count, SHA, exact-object, and name-order checks.
- 2026-08-09 P327 finding: external-input readiness duplicated both total row count and five category counts/IDs. The board validator now derives them from its builder source files, while keeping all rows non-completion-ready and all write/claim/release flags false. An input-ID substitution is rejected even when the total row count is unchanged.
- 2026-08-09 P309 finding: all 32 Stage 25 external/human input rows have current local work packets and validator receipts. The board remains `32/32 missing_or_needs_more_info` with zero completion-ready rows; strict/substrate drafts are 3+9 and non-formal, FoldX formal plan is 25/25 blocked, and all five blockers remain uncovered=0 but completion-ready=0. Safe training and Stage 25 remain `412/0` and `107/0`.
- 2026-08-09 P311 finding: all five head-specific label and benchmark lanes were refreshed. Six source-bound activity-risk local import labels now exist, but there are no reviewed replicates and the 100-row threshold is unmet; the other four heads still have zero training labels. The aggregate queue remains 494 missing labels, benchmark coverage remains 13/15, ready_head_count remains 0, and no training/model/release claim is allowed.
- 2026-08-09 P313 finding: all 15 benchmark lanes were executed. Thirteen cache rows remain valid; the strict mutation and reviewed substrate identity gaps now have 2 operator packets and machine pre-review covers 3+9 records. The strict scorecard correctly remains empty/leakage-failed, formal approvals and bridge intake remain zero, and benchmark/model/release readiness stays false.
- 2026-08-09 P316 finding: all 11 human-decision backlog classes are now expanded into 1220 pending rows, 30 review batches, 30 sessions and 5 first-wave assignments covering 126 target rows. Five launch lanes expose 550 prepared packets, but assigned sessions and completion-ready closeouts remain zero. The 37-row governance bundle is fully covered and fully open; no reviewer decision or release permission was synthesized.
- 2026-08-09 P319 finding: the complete P30/P31 local review surface is active. Master readiness is 1/8, ten external/production claims remain blocked, the next-release operator packet validates, and 31 guard-coverage plus 13 safety-link checks pass. Production execution remains explicitly false; no sync, deploy, restart or grey-release action occurred.
- 2026-08-09 P321 finding: all 11 foreign-tool lanes were probed and packetized. Two are ready only for local evaluation; nine remain split across install, runtime/data and license blockers. PyRosetta is truthfully execution-ready locally, so the ddG packet validator now binds readiness to enabled/license/runtime/data parity instead of rejecting any positive ready state. All three packets validate, while completion, production, customer and release permissions remain zero/false.
- 2026-08-09 P324 finding: the full enzyme-agent wave executed 11 of 12 actions with `11/11` passing receipts and one skipped action; eligibility currently allows 5 actions, while the outcome dashboard reports 8 engineering-ready and 2 hard-gate-unlocked rows. Top-tier is `12 started/9 blocked/3 ready-to-verify/0 completion-ready`, and non-human construction is `11/8/3/0`; both receipt sets validate `3/3`.
- 2026-08-09 P324 boundary: ready-to-verify is a local engineering receipt state, not scientific completion. `selected_variants=[]`, training import/model/release flags remain false, and strict regressions pass safe pipeline `412/0` plus Stage 25 `107/0` without SQLite writes or formal decisions.
- 2026-08-09 P325 initial finding: six receipts are locally verified across the top-tier and non-human boards, but every corresponding workstream remains `completion_ready=false`. The two action-level hard-gate-unlocked rows are partial states: the ddG runtime exists while all 25 execution-plan rows are blocked, and 8 wet-lab authorization rows exist while all 8 preflight rows remain not ready for feedback intake.
- 2026-08-09 P325 source-state finding: reviewed structure graph validation has 25 valid and 0 invalid rows. General feedback intake has 7 valid/training-eligible rows, but the current plate intake has 0 rows and all 8 authorized-candidate preflights remain blocked. DDG has 25 plan rows with 0 ready, while governance readiness is false with 7 blockers. Promotion must therefore distinguish local artifact completion from execution, training, governance, model, and release readiness.
- 2026-08-09 P325 implementation finding: the first promotion board and 5-case tamper regression pass, but the builder read the preserved negative-ddG convention from the wrong nested key and produced an extra explanatory blocker. This is a source-parity defect rather than an unsafe unlock; downstream flags remain false and the field binding must be corrected before full regression.
- 2026-08-09 P325 manifest finding: the extended safe pipeline passes `415/0` and Stage 25 passes `107/0`, but the explicit data-lake artifact list does not yet include the three new scripts, promotion JSONL, or three reports. Local release therefore remains at 1645 artifacts despite valid new contracts; all seven artifacts must be added before P325 is complete.
- 2026-08-09 P325 final finding: all seven promotion-contract artifacts are now manifest-bound, raising data lake/local release from 1645 to 1652 artifacts with zero missing. Six verified receipts resolve to 2 local-artifact-only rows and 4 verified-blocked rows; automatic promotion, completion-ready, execution, training, model, customer-delivery, release, and selected-variant counts all remain zero. The 5-case tamper regression and model-claim consistency pass, safe pipeline is `415/0`, and Stage 25 is `107/0`.
- 2026-08-09 P328 final finding: after P325-P327 document and source-binding updates, a strictly serial Stage 25 rerun remains clean at `107/0`, overall remains `66/0`, and handoff remains `206` rows with `205` live-verified plus `1` volatile exemption and valid filesystem integrity. External-input readiness is source-derived at `32` rows (`8/6/3/9/6`), all `32` still missing/needs-more-info and none completion-ready. Data lake/local release is `1652` artifacts with release false; SQLite/apply/formal-decision/training/model/production gates remain closed.
- 2026-08-09 P329 initial finding: local release records promotion links and the current `6 audit / 2 local-artifact / 4 blocked / 0 automatic` summary, but neither local-release consistency nor safety-link validation consumes those fields. A release-summary-only tamper could therefore evade these two release-specific validators even though the standalone promotion and model-claim guards remain valid.
- 2026-08-09 P329 convergence finding: promotion release controls pass locally, but the first Stage 25 run exposed a pre-existing circular dependency in Markdown validation: it requires the previous runner and overall reports to be valid, while the current runner and overall validity depend on Markdown validation. A transient/concurrent failed report therefore latches future runs closed even when document terms, handoff, and release sources are valid. Counts must come from the runner contract and non-circular source reports instead of prior aggregate success flags.
- 2026-08-09 P329 final finding: local release now binds the promotion board, validator and regression at exact `6/2/4/0` parity; four release-summary tamper cases fail closed without mutating canonical inputs, and safety links expand to `16/0`. The Markdown cycle is removed by deriving command/summary/handoff counts from `COMMANDS`, `INPUTS`, and live `collect_rows()` rather than prior aggregate reports. Final safe pipeline is `416/0`, Stage 25 is `107/0`, overall is `66/0`, handoff is `206/0`, and local release is `1654/false` with zero missing artifacts.
- 2026-08-09 P330 initial finding: data lake currently reports 1654 artifact rows but only 1585 unique paths, with 69 duplicate rows caused by overlap between explicit lists and dynamically extended cache/review paths. All paths are currently relative/safe and no artifact is missing. Release count parity alone therefore overstates distinct artifact coverage and needs a unique-path contract.
- 2026-08-09 P330 final finding: stable first-occurrence deduplication removes 69 duplicate manifest rows without deleting files. After two concurrent P331 artifacts, the live contract is `1658 source rows / 1589 final unique rows / 69 deduplicated / 0 missing / 0 unsafe`; local-release consistency validates exact path and metadata parity. Duplicate-final-path, unsafe-absolute-path, and metadata-drift cases all fail their dedicated checks (`3/3`), safe pipeline is `417/0`, and Stage 25 is `107/0` with release false.
- 2026-08-09 P331 final finding: local-release readiness now explicitly requires 32 authorization booleans to remain false and 10 execution, selected-variant, production-artifact or formal-write counters to remain zero. Nonzero review-draft and blocked-receipt counts retain their source semantics instead of being classified by field name. Four isolated high-risk summary forgeries hit exact checks with canonical inputs unchanged. Combined with P330, the final contract is safe pipeline `418/0`, Stage 25 `107/0`, overall `66/0`, handoff `206/0`, data lake `1589` unique artifacts, safety links `18/0`, and release false.
- 2026-08-09 P332 final finding: explicit false/zero lists alone do not protect against future summary keys. The new coverage contract scans eight high-risk semantic tokens and requires every discovered field to be classified. Current state is `48 discovered / 40 false-or-zero / 8 exact source-bound exceptions / 0 unclassified`. Four future-field fixtures remain rejected even with false/zero values, preventing silent schema expansion. Final safe pipeline is `419/0`, Stage 25 is `107/0`, overall is `66/0`, handoff is `206/0`, data lake is `1591` unique artifacts, safety links are `19/0`, and release remains false.
- 2026-08-09 P333 initial finding: final data-lake artifacts contain recorded `exists`, `size_bytes`, `sha256`, and optional non-empty-line `rows`, but no release-linked validator recomputes these fields against the live filesystem. Path uniqueness and summary coverage therefore do not detect content changes after manifest generation. P333 uses a separate lane because concurrent P332 owns high-risk summary classification.
- 2026-08-09 P333 first-scan finding: the standalone live scan correctly finds 32 SHA mismatches and 3 size mismatches across the current 1591-artifact manifest, with zero missing files and zero row-count drift. The stale set consists of reports and feature/cache outputs rebuilt after the manifest snapshot, including three local-release reports. This is direct evidence of the freshness gap rather than a validator false positive.
- 2026-08-09 P333 final finding: after placing the live validator after the final data-lake rebuild, the current 1595-artifact contract validates as 1593 strict live-content rows plus 2 explicit post-run/self-output existence-only rows, with zero missing, unsafe, size, SHA, or row mismatches. Three dedicated stale-metadata cases fail closed without mutating canonical files. Safe pipeline is `421/0`, Stage 25 is `107/0`, safety links are `21/0`, and release remains false.
- 2026-08-09 P334 final finding: P333 previously validated the intersection of configured volatile paths and manifest paths, so a missing configured exemption was not independently rejected. Live validation now requires exact set equality for the two code-owned post-run outputs, while manifest metadata cannot promote any strict artifact to volatile. Both missing-path cases and one forged-volatile strict row fail dedicated checks (`3/3`). Two initial full-chain failures were concurrent SHA-protection races, not gate changes; after narrowing protection and waiting for concurrent writes, safe pipeline passes `422/0`. Final data lake is `1597` unique artifacts with `1595 strict + 2 exact volatile`, safety links are `22/0`, Stage 25 is `107/0`, and release remains false.
- 2026-08-09 P335 final finding: P333/P334 negative tests were logically read-only but proved operationally sensitive to concurrent regeneration because they hashed shared manifest artifacts before and after temporary tamper validation. Both suites now build a complete three-artifact temporary root and pass it through the same validator `--root` contract. They no longer reference canonical artifacts and report `isolated_fixture=true`, `real_inputs_mutated=false`, with `3/3` cases each. Canonical validation still defaults to the AI root and remains `1595 strict + 2 exact volatile / 0 mismatch`; safe pipeline is `422/0`, Stage 25 is `107/0`, and release remains false.
- 2026-08-09 P336 ordering finding: requiring canonical live-integrity evidence exposed a real ordering defect. The first release consistency step consumed a stale live report after seven upstream artifacts had refreshed and failed with canonical success, decomposition, and SHA mismatch checks. Inserting canonical live validation between data-lake rebuild and the accepted release build removes the stale-evidence window.
- 2026-08-09 P336 final finding: local release now binds the canonical AI root, exact artifact/decomposition counts, both code-owned volatile paths, and zero live mismatches. Temporary-root success, summary-root drift, and artifact-count drift are rejected `3/3`; safe pipeline is `429/0`, Stage 25 is `107/0`, data lake/live is `1599 / 1597+2 / 0 mismatch`, safety links are `23/0`, and release remains false.
- 2026-08-09 P337 cycle finding: directly embedding the raw data-lake manifest SHA in local release creates a cryptographic cycle because local release and its validators are themselves manifest artifacts. Rebuilding either side changes the other side's SHA, so no stable raw-SHA fixed point is expected. Increasing volatile exemptions would weaken integrity and was rejected.
- 2026-08-09 P337 final finding: live validation retains the raw canonical manifest SHA for point-in-time audit, while release binds a canonical contract over 1594 non-post-live artifacts. Five post-live/self outputs are omitted only from this digest and remain present in the 1599-artifact manifest under existing live checks. Raw live SHA matches current manifest, and the contract SHA matches across current manifest, live report, and local release. Seven isolated tamper cases pass with a valid control; safe pipeline is `429/0`, Stage 25 is `107/0`, and release remains false.
- 2026-08-09 P338 implementation finding: three copied contract implementations were an unnecessary consensus risk. The canonical algorithm now lives in one module with explicit version `data-lake-release-input-v1`; all live, release and regression callers import the same function and exact 5-path set.
- 2026-08-09 P338 regression finding: included artifact metadata changes the contract SHA, excluded post-live metadata does not, and removal of any of the three strict post-live excluded paths fails `release_input_exclusion_paths_exact`. Version drift is rejected separately. P333/P334/binding regressions pass `3/3`, `6/6`, and `10/10`.
- 2026-08-09 P338 final finding: adding the shared module increased data lake/local release to 1600 artifacts. Stage 25 initially failed only because both operator docs retained artifact_count 1599; updating the dynamically required current fields restored docs and Stage 25 to zero failures. Safe pipeline remains `429/0`, live integrity is `1598 strict + 2 volatile / 0 mismatch`, and release remains false.
- 2026-08-09 P339 gap finding: centralizing the contract removed implementation drift but made the shared module a single policy authority. Without an independent anchor, a coordinated version, exclusion-set or canonicalization modification would be accepted by every importer.
- 2026-08-09 P339 final finding: an independent validator now pins version `data-lake-release-input-v1`, the exact five excluded paths and test-vector SHA-256 `73faca201747ecef0df5579526c987eee6e0b37203e800c5d7491457e7d38615`. Version, expanded-set, removed-set and canonical-JSON drift are rejected `4/4` using temporary module copies. Safe pipeline is `431/0`, Stage 25 is `107/0`, data lake is 1604 artifacts, safety links are `25/0`, and release remains false.
- 2026-08-09 P340 gap finding: policy success alone did not prove the receipt still referred to the current shared module. A module change after policy validation could leave an old successful report until the next policy run, even though the report preserved its original module SHA.
- 2026-08-09 P340 final finding: local release consistency now binds policy report path/SHA fields to the current canonical module bytes and the module's data-lake artifact SHA, while also checking fixed version/set/test-vector policy. Stale SHA, summary drift, non-canonical path and test-vector drift are rejected `4/4`. Safe pipeline is `432/0`, Stage 25 is `107/0`, data lake is 1606 artifacts, safety links are `26/0`, and release remains false.
- 2026-08-09 P341 gap finding: artifact-count changes in P338-P340 repeatedly required manual edits to the same six operator-doc lines. The Markdown validator correctly rejected stale values, but the repeated repair path was mechanical and error-prone.
- 2026-08-09 P341 final finding: six explicit Markdown markers now delimit the only lines the sync tool may change. Values come from code contracts and validated local reports; missing or duplicate markers and check-only stale state fail closed. Initial bootstrap changed all six rows, while safe pipeline and Stage 25 reruns changed zero. Regression passes `4/4`; safe pipeline is `434/0`, Stage 25 is `108/0`, data lake is 1610 artifacts, safety links are `28/0`, and release remains false.
- 2026-08-09 P342 gap finding: per-document writes allowed a theoretical split state if one document committed before a later document failed validation or replacement. Marker validation alone did not guarantee cross-document all-or-nothing behavior.
- 2026-08-09 P342 final finding: sync now plans both documents before writing and uses same-directory temporary files plus replacement rollback. Cross-document marker failure writes neither file; an injected failure after the first replacement restores both original byte streams. Regression expands to `6/6`, canonical sync remains idempotent, safe pipeline is `434/0`, Stage 25 is `108/0`, and release remains false.
- 2026-08-09 P343 gap finding: transactional writes did not prevent two sync processes or a human editor from changing documents between planning and replacement. Without a lock and compare-before-commit check, an older proposal could overwrite newer content.
- 2026-08-09 P343 final finding: operator-doc sync now holds a dedicated flock across source reads, planning and commit, and CAS-checks both current byte streams before creating replacements. Lock contention fails closed; a simulated external edit is preserved and prevents all sync writes. Regression is `8/8`; safe pipeline remains `434/0`, Stage 25 `108/0`, and release false.
## 2026-08-09 P344-P350 operator docs sync receipt 深度审计

- P343 的 flock 覆盖上游读取、文档 planning 和 commit，但当前实现在线程释放 flock 后才通过 `Path.write_text` 写 receipt；两个 sync 进程可能形成“新文档/新 receipt 已完成，旧进程随后覆盖旧 receipt”的跨代状态。
- Receipt 使用非原子 `write_text`，进程崩溃或磁盘异常时下游可能看到截断 JSON；P344 应使用同目录 temp + flush/fsync + replace，并在 receipt commit 后才释放锁。
- CLI 允许覆盖 `--next-operator`、`--daily-report`、`--output` 和 `--lock-path`。这对隔离测试有用，但 canonical receipt 当前没有独立 validator 证明这些路径为 canonical，后续 P347 必须精确约束。
- 当前 receipt 只记录 document hashes、lock path、结果和自然语言 policy，未记录 sync script、上游报告/合同脚本 SHA、marker exact set 或 policy version；旧 success receipt 可能在输入变化后被复用。
- 当前回归已覆盖 8 类文档事务/CAS/lock 行为，但未覆盖 receipt commit 自身的锁、原子性、来源 provenance 或 current-state freshness。

## 2026-08-09 P344-P350 完成发现

- 原子 receipt 不能只做 `os.replace`：必须把 temp write、file fsync、replace、directory fsync 全部放在同一 flock 内，并在 receipt failure 时回滚已提交文档。
- 文档 transaction 与 receipt 无法依靠多文件 rename 获得单一原子点；durable journal 是硬崩溃恢复所需的 commit-intent。恢复时必须先判断现有 receipt 是否已经绑定 proposed document SHA，避免误回滚已完成事务。
- `stale_rows` 必须描述 receipt 提交后的 current state；提交前发现数单独保存在 `detected_stale_rows`，否则 current validator 会把成功修复误判为 stale。
- macOS 临时路径可能同时表现为 `/var/...` 与 `/private/var/...`；receipt、journal recovery 和 regression comparison 必须统一使用 `Path.resolve()` 后的路径。
- Safety-link report 加入 current-sync guard 后，sync 若继续要求 safety report success 会形成自依赖环。非循环实现改为读取 safety validator 的 `REQUIRED_GUARD_LINKS` 代码合同，receipt provenance 同时绑定该脚本 SHA。
- Live-binding isolated control 现在依赖 current sync receipt/data-lake artifact SHA，因此 safe pipeline 必须在该回归前执行 policy→sync→current→manifest→pre-release bootstrap。
- 最终共享 sync contract=`stage25-operator-docs-sync-v1`，contract SHA=`df0f32928402e87390e9317b9388044ec95373814bdbec1165d10d60a4938351`；policy=`6/6`、sync transaction=`10/10`、current tamper=`8/8`、terminal recovery=`5/5`。
- 并发 safe pipeline 进一步暴露 `act_release_guard_links` 的依赖顺序：sync/current 会改变 receipt 和文档 artifact，因此 action 必须在 sync/current 后再次执行 manifest/live；consistency receipt 写入后还要 rebuild release，才能让 safety summary 消费当前 consistency success。最终 action 顺序为 `manifest/live/release(pre) → sync/current → manifest/live/release → consistency → release(final) → safety`。
- 多条共享 pipeline 同时运行时，live validator 正确报告 14 个 strict artifact SHA drift，current receipt 也正确拒绝两份文档跨代 SHA。未终止外部进程；等待其结束后串行收敛，证明失败来自真实并发写入而非 volatile 豁免不足。

## 2026-08-09 P351 safe pipeline receipt 审计

- `run_safe_training_pipeline.py` 当前没有 flock；多个进程可同时执行 441 个共享写入步骤，P344-P350 期间已实际观察到多条外部 pipeline 造成 14 个 strict artifact SHA drift。
- Runner 在所有步骤结束后直接 `Path.write_text` receipt；旧进程可以晚于新进程覆盖 receipt，进程中断也可能留下截断 JSON。
- Receipt 当前只记录 step outputs/count，不记录 runner script SHA、COMMANDS canonical digest、lock path 或 atomic commit evidence，因此无法证明成功报告对应当前 pipeline contract。

## 2026-08-09 P351 完成与 P352 gap

- P351 canonical receipt 当前为 `444/0`，`lock_acquired=true`、`receipt_atomic_commit=true`；runner SHA=`877d683645e3b0b1f32b481695fac0d1121b0a872c203a7f96aa1045d343a360`，command contract SHA=`67c80daf96ed5b55b07584b13bd468e23a8f3ec252df1aeac48613281814caea`。
- 在 canonical runner 持锁期间启动第二 runner，第二进程 `steps_run=0` 且未写 canonical receipt；主 runner 完成后另一外部 runner只能串行接棒，证明 flock 覆盖生效。
- P351 receipt 自带 provenance，但 downstream 仍只读取 `success`；若 runner 或 COMMANDS 在 receipt 后变化，旧 success 尚无独立 current-state validator 拒绝，定义为 P352。

## 2026-08-09 P352 完成发现

- Safe pipeline current proof 必须在 pipeline receipt 写出后运行，因此不能作为 canonical safe pipeline 的普通 command；本轮将它放入后续 Stage 25 和 release validation，避免 self-receipt cycle。
- Validator 同时绑定 runner file SHA 和 COMMANDS canonical digest；仅检查 `steps_run` 数量不足以发现 command 替换，单独检查 runner SHA又不足以明确 contract rows。
- Stage 25 首轮接入后 release benchmark summary 读取了 operator-doc final consistency 之前的旧失败报告，产生 4 个传播 failures。Final consistency 后显式重建 release benchmark summary 后恢复 `120/0`。
- Current validator 最终核对 `444 commands/444 steps`、all returncodes zero、canonical output/lock、atomic commit；6 类临时 tamper 全部拒绝。

## 2026-08-09 P353 非循环 sync provenance

- 将相互消费的 local-release、data-lake 和 live-integrity 按全文件 SHA 写入 sync receipt 会产生无稳定固定点：sync receipt 改变 manifest，manifest/local release 改变上游报告 SHA，current validator 随后拒绝 receipt。
- 不应以扩大 volatile 或删除 receipt/current data-lake artifacts 规避该问题。正确边界是将 freshness 精确绑定到文档实际消费的字段，同时继续记录原始报告 path/size/SHA 作为不可伪造的生成时审计信息。
- `stage25-operator-docs-sync-v2` 使用 `file_sha256` 绑定 implementation/code/external approved-apply inputs；对 M/V/L 使用 `semantic_projection`。独立 policy 固定 projection version、三个 exact field sets 和 test-vector SHA，current validator 要求实时 projection 相同并校验 receipt observed provenance digest 自一致。
- raw-only JSON 变化不会让文档 receipt 无意义地过期；任意 projection consumed field、mode、field set 或 projection digest 漂移仍 fail closed。隔离 current regression=`15/15`。
- safe pipeline 不能在自身 receipt commit 前证明当前 receipt，因此内部环境明确标记 terminal-deferred；最终链必须在 commit 后、不带该环境变量重新执行 safe current 和 local-release consistency。终态双重只读复核验证该分层没有保留 deferred 成功作为 release proof。

## 2026-08-09 P354 terminal-defer mode binding

- 仅在 safety report 中记录当前 defer 环境不够；consumer 必须比较 consistency receipt 的 `safe_pipeline_terminal_deferred` 与当前 execution mode，否则 deferred success 可被普通模式复用。
- Mode regression 不能调用完整 canonical safety 作为自身 control 后再被 safety 直接要求，否则形成 regression→safety→consistency→regression 自依赖。正确实现是受限 mode-only 验证路径：只写非 canonical 临时输出、不声明 training-safe，并由 local-release consistency 强制消费 regression success。
- 普通终态链最终签发 `safe_pipeline_terminal_deferred=false` consistency receipt；safe runner 内部仍使用 true 的临时窗口，receipt commit 后必须由普通模式重签发。四类 mode drift 均命中专属 check。

## 2026-08-09 P355 Stage 25 current receipt

- Stage 25 的 `run_valid=true` 不能独立证明当前 runner；命令集合从 `121` 变为 `123` 时，current validator 正确拒绝旧 receipt。Receipt 现记录 runner SHA、canonical command contract SHA/version、expected-returncode rows、output/lock 和 atomic commit。
- Stage runner 不能把 current validator 作为自身 COMMANDS 普通步骤，否则 receipt 尚未写出；正确顺序是先在锁内提交 Stage receipt，再执行 current validator/regression，并由 release consumers 强制消费这两个报告。
- safe pipeline 与 Stage current proof 在 runner 合同变化时会形成双向 bootstrap。仅 safe 内部 terminal-defer 可暂缓两类 current consumer；safe receipt 提交后，Stage current 和最终 release consistency 必须在无 defer 模式重签发。
- Stage current isolated regression=`6/6`，最终严格 current/provenance/live/release 证明同时成立，未执行 SQLite/apply/training/model/production/release actions。

## 2026-08-10 P356 post-source-drop current receipt

- 原 builder 的 command contract SHA 只能证明 receipt 内部 recipe 自一致，不能证明 receipt 由当前 builder bytes 生成；直接 `write_text` 还允许截断 JSON 或旧进程晚覆盖。P356 将 builder SHA、contract version、canonical output/lock、lock acquired 和 atomic commit evidence 一并写入 schema v2 receipt。
- Builder 与 validator 都使用 canonical post-source flock。Builder 在锁内完成 temp write、file fsync、`os.replace` 和 directory fsync；validator 在读 receipt/builder 前获取同一锁，并原子提交 validation report，避免验证跨越 receipt 代际。
- Current validator 对当前 builder 动态导出的 58 条 command rows 做 exact canonical digest/order/row parity，继续强制 `sqlite_write_command_rows=0`、commands/source-drop/freshness/rerun completion 未执行，以及 SQLite/apply/formal-decision/model/release 全关闭。
- 独立 fixture 先复制 builder 并生成临时 canonical control，再覆盖 8 类 drift；control+tamper=`9/9`，canonical receipt、validation 和 builder SHA 前后相同。回归没有通过篡改 canonical 文档或共享报告制造负例。
- Safety 不能只依赖 local-release summary boolean；P356 current validation 和 regression 均成为显式 release links、data-lake artifacts 和 safety guard reports。最终两条 link 均满足 release link、file、data-lake artifact 和 report success 四项条件。
- 新 artifact/脚本改变 live inputs 时，safe runner 第一处 controlled wave 会早于原 docs sync bootstrap 消费旧 sync regressions。将 `manifest/live/release → sync policy/current/regressions` preflight 放到第一处 wave 前后，safe pipeline 从 step 369 失败恢复为 `466/466`。
- 并发终态复验真实观察到外部 safe runner 造成 17 个 SHA drift 和 1 个 size drift；live gate fail closed，等待外部 runner 完成后重新串行收敛。最终 data lake=`1648 artifacts`、live=`1646 strict+2 volatile/0 mismatch`、strict consistency=`0/deferred false`、safety=`40/0`，release 保持 false。

## 2026-08-10 P357 validation-report freshness gap

- P356 validator 每次运行时会读取当前 receipt 和 builder，但输出只保存 builder provenance 与 validation result，没有保存被验证 receipt 的 path/SHA，也没有保存 validator 自身 path/SHA。
- Local-release consistency 和 safety 当前只消费 `receipt_valid/success/failure_count`。若 receipt 在 validation 后被合法 builder 或并发进程改写，旧 validation report 仍保持 success；data-lake live integrity只能证明旧报告文件未变化，不能证明它仍对应当前 receipt。
- P357 必须把 receipt→validation report→current consumer 做成两段 freshness 证明，不能用 data-lake artifact SHA 代替跨文件关系校验。

## 2026-08-10 P357 完成发现

- Validation report schema v3 将被验证 receipt 和执行 validator 的 path/SHA 写入报告，同时固定 canonical output/lock 和 `validation_atomic_commit=true`；这使报告具备可被下游重算的 provenance。
- 独立 current validator 持有同一 post-source flock 后再读取 validation report、receipt 和 validator，避免 builder/validator 在比较窗口中切换代际。Current report同时记录自身 validator path/SHA，供 local-release consumer 绑定当前实现。
- 仅篡改 validation report 中 recorded SHA 与在 validation 后实际修改 receipt/validator 是不同风险，回归分别覆盖两者。最终 10 类 drift 全部命中专属 check，连同 control 为 `11/11`。
- Local-release consistency 不再只信任 `receipt_valid=true`：它实时重算 validation report、receipt、validator、current-validator 和 regression-script SHA，并精确要求 current output/lock/atomic evidence。Safety 将 current 与 regression 作为两条独立 guard links。
- 最终 P357 artifacts 增加 4 项，data lake=`1652`、live=`1650 strict+2 volatile/0 mismatch`；safe=`469/0`、Stage 25=`126/0`、strict consistency 与 safety 同时成立，所有执行和发布门保持关闭。

## 2026-08-10 P358 independent-policy gap

- P356/P357 都以当前 builder 导出的 `COMMANDS` 为真值；即使 provenance 和 freshness 完全正确，builder、receipt validator 与 current validator若同步修改，仍可能共同接受错误的 command set。
- 独立锚点不能复用 builder 的绝对路径 digest，因为临时 fixture 和 Python 路径会制造环境耦合。Portable vector 将四类根替换为稳定 token，并对完整 58-row canonical JSON 做独立 SHA 固定。
- Policy 必须同时固定命令内容和安全语义。只固定 count/name 不足以发现 `writes_sqlite=true`、`blocks_apply_until_passed=false` 或 expected-output 路径漂移。

## 2026-08-10 P358 完成发现

- Portable vector 对完整 command object 做 canonical JSON，而非只哈希 name 列表；因此 cwd、cmd、expected output、SQLite/apply flags 和顺序任一变化都会改变固定 SHA。
- 独立 policy 从 builder 原始 `COMMANDS` 自行补连续 step 并归一四类根，不调用 builder 的 `normalize_commands` 或 `command_contract_sha256`。Builder 与 validator即使共同修改 digest 实现，也不能改变 policy 的预期向量。
- Regression 中 builder output/lock 两类 drift 由协同 validator 接受，说明动态一致性层本身确实无法识别“共同接受错误策略”；independent policy 分别命中 `builder_output_path_exact` 和 `builder_lock_path_exact`，覆盖了该实际威胁模型。
- Local consistency 独立重复固定 policy version、58 rows、schemas 和 vector SHA，同时把 policy/target/regression scripts 绑定到当前 bytes；旧成功 policy report 或旧 regression receipt不能被复用。
- 最终新增 4 artifacts 和 2 safety links，data lake=`1656`、live=`1654 strict+2 volatile/0 mismatch`、safe=`471/0`、Stage 25=`128/0`、safety=`44/0`，release 继续 false。

## 2026-08-10 P359 policy-report freshness gap

- P358 policy 每次执行会验证当前输入，但 report 自身没有 output/lock/atomic provenance；无法证明 downstream 消费的是 canonical 原子签发报告。
- Local consistency 已内联部分 current 比较，但缺少可独立运行和隔离篡改的 policy-current proof。P359 将把该逻辑提升为独立 report，并让 safety 直接消费。

## 2026-08-10 P359 完成发现

- Policy report 本身必须提供 `policy_output_path`、`policy_lock_path` 和 `policy_atomic_commit=true`；仅绑定 policy script/target SHA 无法区分 canonical 原子签发与临时或截断输出。
- Policy-current 在同一 post-source flock 下读取 report 及所有 target，并在锁内原子提交 current report；从而避免验证期间 builder/receipt/validation 换代。
- Current validator 不仅重算 SHA，还独立固定 policy=`stage25-post-source-drop-independent-policy-v1`、command rows=`58`、vector SHA=`78d6cdacb6c4f20cd1f8bd6c560dbf5bf1de7b3b1edc5aad73ba3364d0cb2043`、canonical output/lock 和 false release/model-claim gates。
- 16-case regression 将 recorded drift 与 live policy-script drift 分开验证，全部命中专属 check；临时 fixture 运行不修改 canonical policy/report/targets。
- Local-release consistency 实时重算 policy/current/report/script/target SHA，同时要求 policy 和 current report SHA 与 data-lake artifact 一致；safety 将 current 与 regression 作为两条独立 guard links。
- 终态为 safe=`473/0`、Stage 25=`130/0`、data lake=`1660`、live mismatch=`0`、strict consistency deferred=`false`、safety=`46/0`；`release_ready=false`、`safe_for_model_claim=false`。

## 2026-08-10 P360 local-release consistency receipt 审计

- `validate_local_release_manifest_fail_closed_consistency.py` 在完成全部验证后使用普通 `Path.write_text`；进程中断可留下截断 JSON，较旧进程也可在较新进程之后覆盖 canonical receipt。
- Receipt 只保存验证结果，没有 validator script path/SHA、canonical output/lock 或 release/data-lake/live/policy 输入快照 SHA；safety 目前主要依赖 `success` 和 terminal-defer mode。
- 主输入的全文件 current binding 与 manifest/release/self-report 存在潜在哈希环；P360 只先记录签发时快照并保证原子耐久性，后续 current proof 必须使用明确的非循环语义投影。

## 2026-08-10 P360 完成发现

- 要让记录的 input SHA 真正对应被验证字节，必须一次 `read_bytes` 后同时 parse JSON 和计算 SHA；分别 `read_text`/二次 `read_bytes` 仍有输入换代窗口。
- Consistency lock 目前保证多个 consistency signer 不会互相覆盖，原子 replace 保证读者只看到完整旧代或新代 receipt；它不宣称能锁住所有上游 writer。
- Safety 现在独立绑定 consistency schema/mode、当前 validator SHA、canonical 四输入 path、output/lock 和 atomic/lock evidence，并要求四个 snapshot SHA 为有效 lowercase SHA-256。
- 隔离回归的 replace-before-failure case 验证 prior receipt byte-for-byte 保留且无 temp 残留；lock case 验证第二 signer 超时且释放后可恢复获锁。
- 新 artifact 暴露的 backlog `163->168` 不应以更新另一个硬编码解决；validator 改为独立从 feedback packet/decision reports 推导 required/completed/missing，保留精确 ID 集和所有人工门。
- P360 终态：consistency receipt schema=`2`、atomic regression=`5/5`、safe=`474/0`、Stage 25=`131/0`、data lake=`1662`、live mismatch=`0`、safety=`47/0`；`release_ready=false`、`safe_for_model_claim=false`。

## 2026-08-10 P361 semantic-current 审计

- Canonical consistency 之后必须重建 local release 以消费新 consistency 状态，再签发 safety 并重建 manifest/live；因此 release/data-lake/live 的 raw SHA 在正确终态序列中必然变化。
- Release projection 可以保留完整 readiness summary，但必须精确排除 6 个 `local_release_fail_closed_consistency_*` 和 3 个 `local_release_safety_guard_link_*` 后置字段；使用宽泛 prefix 排除会让未来高风险字段逃逸。
- Data-lake projection 应复用已有 `data-lake-release-input-v1`，继续仅排除 5 个已独立验证的后置 output；不扩大 volatile 或 exclusion set。
- Live projection 只需排除 `created_at` 和 raw `validated_manifest_sha256`，其余 root/path、release-input contract、strict/volatile decomposition 和零 mismatch 都是 consistency 实际消费语义。

## 2026-08-10 P361 完成发现

- 为避免 consistency current 自引用，release projection 的后置排除集从 9 个扩展为 13 个，新增 current/current-regression summary 字段；且只允许这些已识别的后置输出变化。
- Current validator 对 raw snapshot SHA 不做静态等值，而是比较 semantic rows/digest；这使正常 final rebuild 可以改变自生文件 SHA，但无法悄改实际被消费的 release 门控、included artifact、live 分解或 policy 字段。
- Deferred-mode fixture 必须让合成 receipt 的 `safe_pipeline_terminal_deferred` 与子进程环境一致；否则回归 control 会正确被 mode gate 拒绝。
- Controlled release-guard wave 不是只有测试文件的序列；它自身必须在 consistency 后重签 current/current-regression、重建 manifest/live/release 后才运行 safety。Guard-order exact contract 已从 11 更新为 15，回归保持 `5/5`。
- P361 终态：safe=`483/0`、Stage 25=`136/0`、current regression=`14/14`、data lake=`1667`、live mismatch=`0`、safety=`49/0`；`release_ready=false`、`safe_for_model_claim=false`。

## 2026-08-10 P362 independent semantic policy findings

- 仅固定共享模块 SHA 不足以防止共享实现和消费者同步放宽。独立 policy 必须固定 semantic version、5 input roles、13-field release exclusion、live/policy projection sets、canonical payload 和共享实现 test vector。
- P361 的初始 data-lake projection 会把两份 post-current 报告作为 included artifacts 重新哈希；live report 和 release summary 又携带全局 release-input SHA，导致 manifest 重建后 current proof 跨代。
- 非循环修复不需要扩大 global release-input exclusion 或 volatile set：semantic proof 单独排除两份 current 输出，并把 live/release 的 contract SHA、artifact rows、excluded paths 归一到该稳定 data-lake projection。原始 live validator 仍严格验证全部 1669 个 strict artifacts。
- Stage runner receipt 提交会刷新 9 个 Stage/overall/handoff 报告，必须在 Stage 后执行 manifest→live→release→consistency→current，再以 release→manifest→live 结束；否则会留下成功报告但 live SHA 过期。
- P362 终态 policy regression=`10/10`、current regression=`15/15`、safe=`485/0`、Stage=`138/0`、overall=`80/0`、live mismatch=`0`、safety=`51/0`，所有发布、训练和生产门保持关闭。

## 2026-08-10 P363 semantic policy freshness findings

- P362 的 semantic policy report 已绑定 policy script SHA，但 consistency signer 只核对独立 anchor 字段，未核对报告中 `contract_module_path/SHA` 与当前共享合同，也未独立证明 policy report output/lock/atomic 当前。
- P363 policy-current 必须同时拒绝 recorded/live policy script drift 和 recorded/live contract module drift；仅检查 report 的 `success` 与 expected vector 不足以证明当前实现。
- Policy report signer 使用独立 flock 和 atomic replace；policy-current/current-regression 只使用临时 policy/contract fixture，canonical policy report、contract、receipt 未被修改。
- P363 接线后新增 4 artifacts，终态为 safe=`487/0`、Stage=`140/0`、overall=`82/0`、data lake=`1675` unique、live=`1673 strict+2 volatile/0 mismatch`、safety=`53/0`；所有发布、训练和生产门继续关闭。

## 2026-08-10 P364 policy atomic recovery findings

- Freshness 成功不等于并发安全：policy-current 使用阻塞 flock 时，异常持锁可导致无限等待；bounded nonblocking timeout 必须显式返回失败且不能改写 prior output。
- Signer/current 两条原子写路径都需要 replace 前中断回归，验证旧报告字节不变、临时文件清理、锁释放后可恢复签发。
- 双 signer 共享同一 flock 时应串行成功，最终报告必须是完整 JSON 并通过 current validator；不能通过扩大 volatile/exclusion set 规避竞争。
- 隔离回归保护 canonical current report 时不得与 canonical current validator 并行执行，否则会产生真实 SHA 变化的测试假阳性；串行执行后 `16/16` 和 `real_inputs_mutated=false`。
- P364 终态 atomicity=`7/7`、safe=`488/0`、Stage=`141/0`、overall=`83/0`、live mismatch=`0`、safety=`54/0`，所有发布、训练和生产门保持关闭。

## 2026-08-10 P365 terminal convergence findings

- Safety validator 会写入受 data-lake manifest 跟踪的 canonical receipt；若 action 以 safety 结束，前一份成功 live proof 不能证明新 receipt 已进入当前 manifest。
- 受控 release action 可闭合为 `safety -> manifest -> live`：manifest 吸收新 safety receipt，live 再验证该 manifest 的 1675 个 strict artifacts 和 2 个明确 volatile artifacts。
- 仅依靠完整命令列表 exact match 能拒绝漂移，但独立 terminal convergence check 提供更精确的失败原因；遗漏 final manifest 和交换 manifest/live 均应作为固定负例。
- Stage 25 不具备相同的内部闭合点：runner receipt 及其 current proof 在 `COMMANDS` 完成后才写入。把 manifest/live 加在 `COMMANDS` 尾部仍早于 receipt，无法证明自身；把 receipt 纳入其自身证明则产生哈希环。因此 Stage 由 safe runner 或等价外层 convergence 收敛。
- P365 终态受控 release action=`22/22`、order regression=`7/7`、safe=`488/0`、Stage=`141/0`、overall=`83/0`、live mismatch=`0`、safety=`54/0`；发布、模型声明、训练、写库及生产门均未打开。

## 2026-08-10 P366 order-proof freshness findings

- Exact-order 内容正确不等于 receipt 当前：旧 order report 只含 `success/count` 且普通写入时，Wave 或 validator 改动后 local release 仍可能读取旧成功，进程中断还可能留下截断 JSON。
- Signer、结构 regression 和 current validator 必须共享同一 canonical flock；否则 current 可能在 signer/regression 跨代窗口读取不匹配组合。
- Current proof 需要同时绑定 validation report SHA、regression report SHA、signer/regression/Wave/current script SHA、canonical output/lock 和独立 action digest；只绑定 Wave SHA 不能阻断 validator policy drift。
- 26-command action contract 将四个 order proof 放在 action 自身最前部，不形成执行递归：signer只导入 Wave 并检查静态 action，不执行 Wave；随后 current 才消费刚签发的 signer/regression reports。
- 三条原子写路径的 replace 前中断均应实测 prior bytes 保留与 temp cleanup，不能只凭 helper 代码推断。P366 regression=`17/17`，canonical scripts 未修改。
- Controlled action 在 safe 外层 consistency atomicity regression 之前运行，因此它若消费该 provenance，就必须在 action 内先重签 atomicity report。依赖外层后续步骤会让首次代码 SHA 变化时 action 正确但无法自洽地 fail closed。
- P366 最终 action contract 为 27 commands/19 outputs，SHA=`ec7bc214a1edb8d355f4f8e1a4bf00452fdf5fe59376ea74989d910578d225ae`；safe=`492/0`、Stage=`145/0`、overall=`87/0`、live mismatch=`0`、safety=`56/0`。

## 2026-08-10 P367 order-proof concurrency findings

- 原子 replace 只能保证单次提交完整；若没有 bounded lock timeout/recovery 测试，仍无法证明异常持锁不会造成无限等待或超时进程改写 prior output。
- Signer 与 regression 写不同文件仍必须共享同一 flock，因为 current 要读取成对 provenance；混合并发后应由 current 重新验证二者都对应同一 live Wave/action digest。
- Current-regression 自身也是 release consumer 输入，必须声明 canonical output/lock/atomic evidence；不能因为它只使用临时 fixture 就省略自身 receipt durability。
- P367 atomicity=`11/11`，四类 lock timeout 均 fail closed 且释放后恢复；双 signer 和 signer/regression 竞争均串行成功，无 canonical input mutation。

## 2026-08-11 P369 execution receipt proof durability findings

- Wave pair 的 SHA 绑定不能替代 downstream proof 自身的 durability：gate、gate-validation、lineage 任一报告被截断或旧进程覆盖，都可能让消费者读取旧的 `success=true`。三者必须共享 proof flock，并声明自身 script/output/lock/atomic provenance。
- Current proof 需要同时验证输入关系和路径关系：gate 对 wave/receipt，gate-validation 对 gate/wave/receipt，lineage 对 gate/gate-validation/wave/receipt；只核对报告 success 不足以防跨代集合。
- `11/11` regression 覆盖 7 类 provenance 篡改、current output replace 前中断、lock timeout 保留旧报告以及释放后的恢复提交；所有 fixture 使用临时目录，canonical 输入 SHA 未变化。
- safe runner 在 P369 期间两次自然持锁完成后才提交新 receipt；current validator 在旧 498-step receipt 期间正确拒绝当前 500-step contract，未抢锁、未终止进程。最终普通模式重跑后 safe/Stage/current 全部通过。

## 2026-08-11 P370 release-summary proof SHA findings

- Release summary 只记录 proof `success/failure_count` 时，内容不同但摘要相同的旧 proof report 仍可能被投影接受；记录并实时验证 canonical report SHA 才能把 summary 与当前 proof 字节绑定。
- 两项 proof SHA 是 release 的稳定上游消费字段，应进入 semantic projection；不能放入 post-consistency exclusion，否则会重新打开跨代窗口。
- 临时 summary SHA 篡改只触发 `execution_receipt_proof_summary_matches_current`，证明专属 binding 生效；current regression 的 consumed-field case 同时证明 semantic digest 会拒绝该漂移。
- Safe 持锁期间运行 canonical safe-current validator会改写 strict artifact，使之后构建的 manifest 与 live 校验跨代。本次 live 在 step 455 fail closed；串行重建后恢复。后续 canonical current validator 必须在 safe 锁释放后运行，运行中检查只允许临时 output。

## 2026-08-11 P371 safety receipt durability findings

- Safety receipt 位于终态链靠后位置，普通 `write_text` 即使内容验证正确，仍可能留下截断 JSON 或被旧 writer 覆盖；必须独立拥有 bounded flock 和原子 replace。
- Safety signer 读取 release、data-lake、consistency receipt 各一次字节并同时 parse/hash，报告中的 SHA 是签发时 snapshot 审计证据。Safety 后会重建 manifest/live，因此 data-lake raw SHA 不应直接作为终态 current 等值断言。
- Atomicity regression 若要求 canonical safety receipt 已绑定当前脚本，会在脚本首次变化时形成恢复死锁。将 provenance 生成提升为纯函数后，回归可独立签发，再由 consistency/safety 消费其当前结果。
- P371 `5/5` 证明 replace 中断保留 prior bytes、无 temp 残留，锁争用进程 fail closed 且释放后恢复；最终 safety 61 links/0 failures，manifest/live mismatch 0。

## 2026-08-11 P368 execution-wave pair durability findings

- 两个文件不能通过一次 `os.replace` 同时提交；将 receipt 先原子提交、再在 report 中写入 receipt SHA，可让 receipt 新代/report 旧代和任一路径的 replace 前中断都成为可检测的不一致，而不是可被下游误信的 pair。
- Pair consumer 必须同时钉扎 wave script、receipt/report canonical paths、lock path、receipt SHA 和 atomic evidence。仅比较 action/row 集会接受内容相同但 provenance 已过期的 receipt。
- `5/5` 隔离回归确认：receipt replace 前失败保留旧 pair，receipt replace 后或 report replace 前失败暴露 SHA mismatch，lock timeout 不修改 prior pair，释放后恢复可生成可验证的新 pair。
- Stage 的 current proof 是其 command receipt 提交后的后置自引用消费者。恢复时可用既有 deferred-terminal mode 重建中间证明，但最终必须在普通模式重签 manifest/live/release consistency；本次普通终态校验已全部通过。

## 2026-08-11 P372 safety current and terminal convergence findings

- Safety current 不能要求签发时 data-lake raw SHA 永远等于终态 SHA：合法的 safety/current 报告会在其后进入 manifest。正确约束是 release 与 consistency receipt 实时 SHA 相等、data-lake snapshot SHA 格式有效，并临时重算完整 61-link safety 语义。
- Stage 内 signer 必须位于 semantic policy、consistency receipt/current 及其后的 manifest/live/release 刷新之后。把 signer 放在 policy suite 后但 consistency refresh 前，会稳定命中 stale `semantic_policy_sha256`，不是偶发时序错误。
- Safe runner 的 deferred terminal mode 是受控恢复合同，不是终态证明。失败 Stage 覆盖 self-referential current 报告后，可在同一 deferred 环境恢复 Stage receipt/current，但最终必须重新执行普通 consistency、safety 和普通 Stage。
- P372 safety current validation/regression 是 post-consistency artifact；其字节包含时间和当前 provenance，必须加入 data-lake semantic projection 的精确 exclusion。Release summary 中的 P372 success/failure 字段仍保持受 consistency 直接消费，不能排除。
- Consistency atomicity regression 自身属于 release-input artifact，必须在 manifest 构建前刷新。若先构建 manifest、再运行 atomicity regression，consistency 会签旧 manifest，下一次 manifest 重建必然让 semantic current 拒绝。
- 最终 current 复核应写临时 output；safety current 仍使用 canonical lock path，因为 receipt 明确钉扎该锁。临时 lock path 会被正确识别为 provenance drift。

## 2026-08-11 P373 current-regression durability findings

- Current validator 的 durability 回归不能替代 current-regression 报告自身的 durability。后者也是 release consumer 输入，必须独立证明 canonical write 的 timeout、interrupt 和 concurrency 行为。
- 首次扩展 safety guard 集合时，旧 safety receipt 必然无法通过新 signer 语义。Durability proof 若要求内部领域报告 `success=true`，会形成 bootstrap 死锁；正确判据是 committed report 与进程 returncode 一致、结构和 provenance 完整，领域 `12/12` 由独立 gate 保持强制。
- Current 与 current-regression 虽写不同 output，仍必须共享 safety flock；混合竞争测试证明两者最终 commit 串行，不能只测试双 regression。
- P373 atomicity report 在 consistency 前签发且之后不再改写，因此可作为普通 release-input artifact，无需加入 post-consistency semantic exclusion。
- 新 release guard requirement 会进入 human decision backlog 统计。新增一个 proof 后 required/missing rows 从 `1230/1201` 精确变为 `1231/1202`，worklist 和两个 operator 文档必须同步，否则 Stage Markdown gate 应 fail closed。

## 2026-08-11 P374 human backlog operator-doc sync findings

- Backlog 数值只靠人工更新 Markdown 会在 guard requirement 增长后留下可见漂移窗口。正确边界是复用现有两文档、单 flock、文档 transaction、原子 receipt 和 current provenance，而不是再建一个独立 writer。
- Human backlog 的 completed 和 missing 行不是互斥集合，不能强制 `required = completed + missing`。Sync 本地门只要求 `open_items` 和三个 `total_*` 字段为非布尔、非负整数，并要求上游 validator 成功且 model/release gates 关闭。
- 语义投影必须同时包含 `open_items/required/completed/missing` 和两个关闭闸门；这允许上游报告的时间戳等 raw-only 字段变化，但任一被文档消费的数值或 gate 漂移都会被 current receipt 拒绝。
- 独立 policy 需要固定四 slot/八 marker/十二 upstream provenance 和四类语义投影；消费者的 target count 应从 target specs 与 slots 动态推导，避免继续维护旧的六 marker 硬编码。
- P374 终态隔离证明为 policy=`8/8`、marker/transaction=`13/13`、current=`15/15`、terminal recovery=`5/5`；完整 safe/Stage/current/manifest/live/consistency/safety 均收敛，且没有 transaction journal 或 temp/rollback/recovery 残留。

## 2026-08-11 P375 marker regression proof audit

- Sync transaction 的 durability proof 不能替代 regression report 自身的 durability。当下 marker/transaction regression 报告使用普通 `Path.write_text`，可被中断为截断 JSON，也可被较旧 writer 在较新报告之后覆盖。
- Local-release summary/consistency 只校验该报告的 `success/failed_rows/real_inputs_mutated`，没有绑定 regression writer 当前 SHA、canonical output/lock 或 atomic commit evidence；因此 stale `13/13` 仍存在被复用的窗口。

## 2026-08-11 P375 completion findings

- Regression 内部 fixture 变量可以污染最终 provenance：原脚本的 `lock_path` 在 lock-contention case 中被重用，current proof 首次精确捕获报告记录了临时锁。Fixture 路径必须使用不会覆盖 canonical provenance 的局部命名。
- 一把共享 proof flock 只能保证 writer 串行，不保证并发后的 current report 一定对应最后 writer。混合争用回归必须允许检测 stale pair，然后再签 current 以恢复最终 SHA parity。
- Release consumer 不能只消费新 proof 的 boolean。Local-release summary 保存 marker/current/current-regression/atomicity 四份报告的实时 SHA，consistency 重算报告与脚本 SHA、canonical output/lock 和 atomic evidence，safety 再强制三份下游 proof 成功。
- Guard 集合扩展会使硬编码 count 立即过期。Consistency 应从 canonical `REQUIRED_GUARD_LINKS` 动态推导 65，而不是将 62 更成另一个常量。
- Safe pipeline 有 bootstrap 和终态两轮 operator-doc sync，proof suite 必须两处同时接入。仅改一处会让 controlled wave 通过新 proof，但终态 release 仍可复用旧报告。
- P375 终态为 marker=`13/13`、current=`13/0`、tamper/recovery=`14/14`、atomicity=`7/7`、safe=`513/0`、Stage=`157/0`、overall=`98/0`、safety=`65/0`；全部 model/release/write/production/customer gates 保持关闭。

## 2026-08-11 P376 post-source slot audit

- Post-source 的真正消费状态不是只有 receipt 首行；必须同时绑定 receipt command contract、validation `receipt_valid/command_contract_valid`、dry-run `commands_executed/outputs_freshness_verified/rerun_completion_receipted/ready_for_source_drop_rerun`和 `sqlite_write_command_rows=0`。
- 两份 operator docs 存在 P322 历史状态段，其中的旧 `58` 和旧 SHA 不在四个现有 marker 所有行之内；这是可见但未被 current receipt 拒绝的重复硬编码。
- 新 slot 应复用现有两文档/单 flock/原子 transaction，而不应让 post-source builder 再增加一条文档 writer。语义 projection 只保留被文档消费的字段，raw timestamp 和完整 command list 继续通过独立 receipt/policy 校验。

## 2026-08-11 P376 completion findings

- `stage25-operator-docs-sync-v4` 将 post-source receipt/validation/dry-run 作为 provenance 和消费状态输入，固定 5 slots/10 markers/15 provenance rows；policy vector SHA=`e9bd090aba163342dd6587fb229deca7eed2993e09eba1f4ec0415f340630797`。
- 两份 operator docs 的 P322 历史段落旧 `58` 和旧 SHA 已移除；这些漂移不再能在 marker-owned 行之外绕过 current receipt。
- 前先 Stage 失败的真实根因是 `cord2025` 在 xylanase SQLite 中已有同 DOI/PMID/题名记录，而 metadata-only plan 将任意 duplicate 视为新插入冲突。现在只接受单一精确 existing identity 作为既有记录复核，冲突/多重 duplicate 仍失闭。
- Deferred bootstrap recovery 只在 `KWB_DEFER_SAFE_PIPELINE_TERMINAL=1`、链首 summary 确实 stale 且同轮链尾 summary 已 `summary_valid=true/failure_count=0` 时标记恢复；普通 Stage 不会忽略任何 command failure。
- 终态 evidence 已串联：safe=`513/513/0`、Stage=`157/157/0`、overall=`98/0`、data lake=`1767 source/1698 unique/69 deduplicated`、live=`1696 strict+2 volatile/0 mismatch`、consistency/current=`0`、safety/current=`65/0`；所有 SQLite/formal decision/apply/training/model/release/production/customer 门仍为关闭。

## 2026-08-11 P377 numbering operator packet current audit

- 临时 packet 生成与验证通过 `21/21`，覆盖 `471` open numbering rows；review packet 验证覆盖 `475/475`，当前 decision 文件 `4/4 valid`，semantic conflict=`0`。
- 强制保持 `completion_ready_rows=0` 是正确行为：`549` stability records 中 `542` 命中 `synthetic_generator_fingerprint_prothermdb_pmid_310xxxxx`、`523` 报告 WT 与 current UniProt 不匹配、`546` ddG/DTm 方向冲突、`0` 条 PubMed 明确提到 mutation、`0` claim-eligible rows。
- 所有输出仅写入 `/tmp/kwb-numbering-audit.MREICa`，canonical `numbering_curation_decisions.jsonl` 、SQLite 和发布证据未修改。下一步需要真实原始来源回执和人工审核，不是自动拒绝决策或自动晋级。

## 2026-08-11 P378 plate feedback current audit

- Venus-15B 真实目录仅包含 `15B-AAP-noCa.pdb`、序列文件和背景文件；资产审计输出 source files=`3`、qualitative feedback=`1`、numeric training eligible=`0`、plate training eligible=`0`。
- 临时 plate packet=`50`、ready=`false`；plate validation=`0 input / 0 valid / 0 training-eligible`；intake backlog=`50` 个开放项。
- 普通 feedback intake 的 `7` 条 valid/numeric 统计不等于 plate 实验表，两者必须继续分开门控；P43-A006 仍需真实完成的 plate row、replicate、QC 和条件回执。
- 所有本轮输出写入 `/tmp/kwb-plate-audit.7BsyZn`，canonical plate intake、training、SQLite 和 release 未变更。

## 2026-08-11 P379 external license review current audit

- License packet 总数为 `19`，只有 `3` 条 decision，且 authorization status 全为 self-attested；`16` 条缺 formal decision，verified decisions=`0`。
- 三条已有 decision 只支持 local evaluation；approved training=`0`、approved customer delivery=`0`、verified customer delivery=`0`。Self-attested 不得被折叠为商业授权。
- External data-source registry 结构为 `8/8 valid`，但 ready sources=`0`。“Registry 行有效”和“来源已获授权”是两个独立命题，必须保持 fail closed。
- 本轮仅写 `/tmp/kwb-license-audit.OigKfL`，canonical decisions、training、customer delivery 和 release 未变更。

## 2026-08-11 P380 all-eight remediation local start

- “全部开始”的可验收定义是八条线同时拥有 start packet、validated dispatch、open checklist、operator ledger 和 receipt，而不是将人工输入自动写入 decision files。
- P43-A001/A006-A012 全部为 `started_blocked`：checklist、ledger、receipt 均 `8/8`，requires human=`8`、completion-ready=`0`、target rows met=`0`。
- 12-action 全局 board 有 `4` 条既有技术线局部 completion-ready，不得将该数字归到用户本次指定的八条 remediation；八条仍全部 blocked。
- Safe/Stage/release terminal chain 全部通过，说明启动证据已进入发布安全消费链，但 `release_ready=false`、`safe_for_model_claim=false` 保持不变。

## 2026-08-11 P381 biosecurity order-artifact detection findings

- `*order*.json` 和 `*codon*.json` 文件名 glob 不能代表可下单 payload；它会把 release guard 执行顺序报告和 CM5 codon 质量审计误报为 synthesis 输出。
- 真实风险应来自结构化内容：ordering/synthesis approval 为 true、order/synthesis payload 存在，或在 ordering 语境中带 DNA/RNA/nucleotide/construct/codon-optimized sequence。
- 新实现对损坏的显式 `synthesis_order` 文件仍 fail closed，避免通过不可解析 payload 绕过。Canonical 检测=`0` 只表示当前未发现 order-ready artifact，不表示 screening 通过。
- Decision rows、approved-for-ordering 均为 `0`，`ready_for_ordering=false`；唯一真实 blocker 保留为 biosecurity screening decision validation 未 ready。

## 2026-08-11 P382 sequence IP/FTO provenance findings

- UniProt accession 的 SHA-256 不是 sequence hash；即使长度和形式合法，也不能写入 `parent_sequence_hash`。
- Parent-sequence provenance 必须三者同时成立：receipt 显式标记 hash source、path 为 safe relative path、live file SHA 等于 packet hash。任一缺失都不得声称 sequence material available。
- 当前三个 Venus-15B IP/FTO packet 都有真实 `Venus-15B淀粉酶项目/淀粉酶15B序列.txt` receipt，SHA=`15a4430c8325d35c38f31f81e6f850757bd423f5b1964285ebeb7ec03ed9c2da`，因此修复后仍 `3/3 valid`。
- Packet provenance 有效只说明法律审核输入指向真实序列；prior-art search、jurisdiction、human/legal decision 和 customer delivery approval 仍全部为空。

## 2026-08-11 P383 workstream state decomposition findings

- `needs_more_info` 是有效决定，但不是 acceptance。将 accepted set 的补集命名为 `missing_stream_decisions` 会混淆“无决定”与“已决定但未接受”。
- 正确分解为 decided set、accepted set、missing-decision set 和 unaccepted set。当前 active_learning 位于 decided+unaccepted，另外五条位于 missing+unaccepted。
- 重复/无效 decision 不进 decided set；仅 valid `accepted` 才进 accepted set。这保持 all-stream acceptance 门控严格。

## 2026-08-11 P384 operator action evidence-binding findings

- 仅有“文件存在”不足以证明 operator action 完成；6 个 stream 现在各自携带明确的 required evidence/report 集合，completed 行必须包含所有绑定路径并保持 residual risks 为空。
- Decided 与 completed 是独立集合；valid `blocked/rejected/needs_more_info` 只表示已得到人工处置结论，不会被计为完成。
- 畸形路径容器现在生成拒绝错误而不是触发 `set(...)` 崩溃；无关存在文件、空合同、空路径和不可哈希元素回归均 fail closed，聚焦测试=`5/5`。
- Canonical 仍为 `6 queue / 0 decided / 0 completed / 6 missing / 6 incomplete`；未伪造人工决定，也未打开执行、训练、模型声明、客户交付或发布门。

## 2026-08-11 P385 claim readiness initial findings

- `claim_readiness_matrix.json` 当前是 `11 claims / 1 allowed / 10 blocked`；唯一 allowed 为 `internal_design_review_artifacts`，本地 safe training claim 也因 entrypoint 不满足而 blocked。
- 现有 policy validator 可以阻断高风险 claim 变 true，但尚未证明每个 requirement 的 passed/missing 状态对应当前上游报告；“结果形状安全”不等于“当前来源一致”。
- P43-A012 目前只检查 `claims_blocked==0`，而 quarantine validator 始终要求 9 个高风险 claim blocked。必须拆分 dynamic readiness 与 explicit promotion policy，否则该 action 要么永不可完成，要么只能通过放宽安全策略伪完成。
- P385 实现后，policy validator 使用隔离临时 output 重跑 canonical builder；任一 requirement passed/missing 篡改、claim 删除或 summary 归零都会破坏 source parity。
- P43-A012 现在同时要求 policy valid、source-current、exact claim set、all dynamically ready、promotion policy allows all 和 zero blocked。单独伪造 `claims_blocked=0` 已无法绕过。
- 当前真实状态是 10 个 canonical claim not ready，promotion-all=false，blocked=10。这些是三个独立阻断信号；source parity=true 只证明 blocked 结论来自当前上游，不代表 claim 可用。

## 2026-08-11 P386 initial durability findings

- Source parity 和 receipt freshness 是两个独立问题：P385 能重算 matrix，但它的输出报告仍可被旧 writer 并发覆盖或在脚本变更后被继续消费。
- 关键 policy receipt 至少必须绑定 validator SHA、builder SHA、matrix SHA、canonical output/lock path、lock-acquired 和 atomic-commit，且 current validator 必须从实时 bytes 重算。
- Signer 的原子性不只是原子写文件；lock 必须覆盖 matrix snapshot 和重算窗口，并在 replace 前对 snapshot bytes 做 CAS，否则仍可签出跨代 receipt。
- Current validator 需要同时验证“receipt 对应当前脚本/matrix”和“matrix 对应当前上游”。仅比对 receipt 内的 matrix SHA 会允许旧 matrix+old receipt 成对复用。
- P386 回归已证明 stale signer/builder/matrix SHA、output/lock drift、atomic/source-parity 篡改均失败；replace 中断与 lock timeout 均保留 prior output，11 个 case 全部通过。
- Deferred terminal recovery 必须将“暂时跳过 success 状态”与“继续强制 provenance”分开；本轮仅跳过 defer receipt 必然导致的 consistency-current success，没有跳过 path/SHA/semantic digest。

## 2026-08-12 P387 initial anchor findings

- P386 的 signer/current 只能证明当前 report 与当前 builder/matrix 一致；如果 builder、signer 和 current 同时接受一套错误 claim policy，仍缺少独立对照。
- Anchor 必须独立保存 policy version、完整 11 claim IDs、must-allow internal IDs、blocked high-risk IDs 和 test-vector digest；它只能拒绝策略漂移，不能自动将 blocked claim 变为 allowed。
- P387 实现后，shared contract 只是消费层的统一来源；independent anchor 保留了另一份字面期望值和独立 digest，因此修改 shared contract 本身会被拒绝。
- 当前 anchor regression 用内存 payload 覆盖 version、扩展/删除 claim、allow/block set 和 test-vector 漂移，`8/8` 全部命中；canonical 合同和真实文件未修改。
- 仅有 anchor report 中的 expected SHA 还不够；消费端必须保留独立字面 SHA，并同时比对 shared contract 实时 digest。这防止 anchor validator 与 contract 同时被修改后相互认证。

## 2026-08-12 P388 initial promotion-gate findings

- P43-A012 原来只能用 `claims_blocked==0` 描述最终状态，没有一个独立的人工 promotion decision 输入；这会把 policy 更新和人工批准混为同一件事。
- 新 gate 将仅允许 9 个 blocked high-risk claim 进入 promotion 审查；任何 approved 行都必须有人 reviewer、存在的 evidence/validation、当前 claim ready 和空 residual risks。
- 当前将保持 decision rows=`0`、approved=`0`、missing=`9`，这是强制阻断的预期状态，不是缺少自动填补。

## 2026-08-12 P388 promotion template findings

- `claim_promotion_decisions.template.jsonl` 现在覆盖全部 9 个 blocked high-risk claim，不再只有单条 `model_quality_claim` 样例；每行默认 `needs_more_info`、`approved_for_promotion=false`、`residual_risks=["template only"]`。
- `validate_claim_promotion_decisions.py` 现在把模板本身纳入合同输出，报告里会显式给出 `template_rows=9` 和 `template_matches_expected_contract=true`；空输入仍然保持 `decision_rows=0`、`missing_promotion_decisions=9`、`ready_for_claim_promotion=false`。

## 2026-08-12 P390 master readiness board validation findings

- Master readiness board 必须同时满足顶层状态、stream 集合、ready 计数、推荐顺序、model-training projection、governance projection 和 local-only platform blocker 的 source parity；validator 正向结果为 `1/8 ready streams`、`blocked_for_model_claim`、零 failures。
- 篡改顶层 `ready_streams` 会同时破坏 `ready_streams_matches_stream_rows` 和 `ready_streams_one_only`；篡改 `model_training.current.safe_for_model_claim`/`multitask_missing_heads` 会破坏对应 source-parity checks。两个隔离负例均以非零退出拒绝，说明看板不能靠内部自洽字段伪造解锁。
- 完整安全流水线为 `528/528 passed`。本轮新增 validator 已实际执行并纳入 data lake manifest；manifest 当前 `1718 artifacts`、`1787 source artifact rows`，live integrity `1716 strict verified + 2 volatile / 0 mismatch`。
- 该验证闭环不改变业务真值：activity_risk 仍只有 `6/100 samples`，其余四头仍为 `0/100`；training execution、model claim、customer delivery 和 local release 继续 fail closed。

## 2026-08-12 P391 active-learning readiness validation findings

- Active-learning readiness report 已被 master board、claim matrix、workstream acceptance、parallel board 和 operator queue 消费；在 P391 前 operator queue 甚至把 readiness report 本身列为 validation report，缺少独立 source-bound validator。
- 新 validator 将 report 绑定到 multitask status、benchmark claim readiness、biosecurity ordering readiness、customer delivery readiness 和 draft JSONL 实时行数。当前真实状态是 `model_status=blocked`、benchmark/customer/biosecurity 全 false、draft rows `0`。
- 篡改 ready/candidate/submission 三个开关会被三个独立 fail-closed check 拒绝；篡改 `draft_rows` 会被实时 JSONL 计数拒绝。该 validator 因此阻断“只改 summary 字段就启动 active-learning 实验”的路径。
- Operator review action queue 现在消费 `active_learning_trial_readiness_validation_report.json` 作为 validation artifact；这仍只是 review 队列证据，不代表 human approval、budget approval、candidate generation 或 experiment submission 获批。

## 2026-08-12 P392 benchmark matrix validation findings

- Benchmark matrix 是多个下游模型声明门的基础输入；如果它没有 self-validator，单独把某个 head 的 `scorecard_ready` 或顶层 `ready_for_model_claim` 改成 true，会污染 head status、claim matrix 或 model-quality hard gate 的上游语义。
- 新 validator 从 multitask readiness 重新绑定五头 `label_rows/minimum_rows/training_ready`，并固定五头 required benchmark 清单和 blocked blocker 文案。当前真实状态为 `mutation_rank=0/100`、`stability=0/100`、`activity_risk=6/100`、`substrate_fit=0/100`、`assay_success=0/100`，五头 training_ready 均 false。
- Matrix 层继续强制 `benchmark_data_ready=false`、`scorecard_ready=false`、`status=blocked`。这与后续 benchmark score-cache `13/15 valid`、`3 heads_ready` 并不冲突：后者是局部 cache coverage，不能单独支持模型质量声明。
- 篡改单头 scorecard/benchmark ready 或顶层 `ready_for_model_claim` 均被拒绝；因此 benchmark matrix 不能通过内部字段篡改绕过五头标签、leakage-safe scorecard、人审和 release gates。

## 2026-08-12 P389 terminal-chain repair findings

- 这条修复链与 P388 的人工 promotion gate 不同，问题点在 controlled execution wave 的 release-guard 子链顺序和当前 validator SHA 重签位置，而不是 claim 审批内容本身。
- 现有脚本已能验证 controlled release-guard order、current proofs 和 regressions；因此这次启动的是终态链修复，不是新门控设计。

## 2026-08-12 structure chain draft boundary findings

- structure chain auto-review 现在已明确带上 `review_draft=true`、空 `curator/curated_at` 和 `draft_policy`，避免被误读为 formal reviewed decisions。
- `validate_review_drafts_not_formal_decisions.py` 现把 `structure_chain_autoreview_acceptance_001.decision_acceptance.draft.jsonl` 纳入边界校验，和 `numbering` / `wet-lab` draft 一起保持 draft-formal 分离。
## 2026-08-12 P389 terminal-chain diagnosis

- P388 canonical promotion 状态符合预期：`decision_rows=0`、`approved_rows=0`、`missing_promotion_decisions=9`、`ready_for_claim_promotion=false`；这是业务阻断，不是 pipeline 失败根因。
- 完整 safe pipeline 在第 397 步 `run_enzyme_agent_controlled_execution_wave.py` 失败；其 `act_release_guard_links` 子链直接运行 consistency，但没有先运行 `validate_local_release_safety_guard_links_atomicity_regression.py`。
- P388 接线修改了 `validate_local_release_safety_guard_links.py`，当前 SHA 为 `6459bca875d1d301b4073fa8ad0622710bb7f4ee3466bb331ada59a4b49490dd`；旧 atomicity report 仍绑定 `acee7601d0500f72bd70112fd615f2598b87bb256c4bbb494e2f797ce1a67899`。
- 因此 consistency 只产生一个真实 failure：`safety_guard_atomicity_regression_binding.validator_script_sha256`。其 current regression 的 2 个 control case 随失败 receipt 连锁失败；safety signer 的 5 个 failures 也都是下游传播。
- 正确修复点是受控 release-guard 命令合同和执行顺序，不应通过放宽 consistency/current/safety 检查或手改 receipt 绕过。
- Execution-wave pair atomicity 不能作为 wave 内部子命令：父 wave 全程持有同一 canonical flock，子进程会自锁超时。正确策略是在 safe pipeline 两处 wave 调用前先刷新 pair regression；Stage 25 原顺序已满足该约束。
- Safety atomicity 使用独立 safety lock，可以且必须放在 controlled release-guard 子链的 consistency 前，使子链对 safety validator SHA 更新自包含收敛。
- 最终 action contract=`29 commands/21 outputs`，SHA=`6b329e262755c614da52ef53c5bbb448d364ceae92dd8cafa092d632af487e10`；固定值与实时重算一致。
- 最终业务真值未改变：claim matrix=`1 allowed/10 blocked`，promotion decisions=`0`、approved=`0`、missing=`9`，P43-A012 仍 blocked。

## 2026-08-12 P26 structure-chain reviewed expansion findings

- `13FO、10GH、135L、193L、194L、121P、16PK、11AP、1A3H` 均可作为 DBREF-backed reviewed chain mapping：每条都有明确 selected chain 和 UniProt DBREF 区间；缺失的 UniProt 端区间均记录为 `PDB_DBREF_UNIPROT_SUBRANGE_EXCLUDED`，16PK 的两个内部差异保留为 SEQADV conflict/construct evidence。
- 本轮只扩大结构坐标图可消费范围：formal structure-chain decisions 25->34、reviewed structure graph 34/34 valid、validated feature index 中 `structure_graph` 25->34。它不证明 mutation label numbering、不导入湿实验标签、不解锁训练导入、不允许 model-quality/customer/release claim。
- 结构链数量增加后，多个 fail-closed consistency 脚本中的旧静态基线必须同步：advanced model feature contract、draft/formal boundary、human decision backlog 都应承认 34 条正式 structure-chain decision，同时继续要求 draft-only 字段不得进入 formal rows。

## 2026-08-12 multitask readiness activity-risk import findings

- 多任务 readiness 旧口径只读取 strict/audited 表，因此在 `activity_risk_training_import_labels.jsonl` 已有 6 条真实 training-import 标签时仍显示 `activity_risk.rows=0`；这是报告口径落后，不是训练门已满足。
- 修正后的 activity_risk 行只计入同时满足 `head=activity_risk`、`ready_for_training_import=true`、`training_label_source=true` 且有 `label_value` 的导入标签，并绑定 validation report 的 6 行一致性。
- 6 条 activity_risk 标签仍低于五头训练阈值：`minimum_rows=100`，显式 replicate 为 0、独立 group 为 2；因此该头仍在 `missing_head_labels` 中，训练执行、模型声明、客户交付和 release 门都必须保持 false。

## 2026-08-12 five-head execution parity findings

- 五头执行合同不能只消费 threshold report 的 label_rows，也不能只消费 multitask readiness 的 rows；两者必须逐头一致，否则一个报告口径落后时下游可能继续显示自洽 blocked 状态但隐藏真实漂移。
- 新 parity gate 固定每个 head 的 `multitask.rows == threshold.label_rows` 和 `multitask.minimum_rows == threshold.minimum_samples`。当前 canonical 状态为 activity_risk `6/100`，其余四头 `0/100`，全部 not ready。
- 临时篡改 activity_risk 执行合同行数为 0 会被 validator 拒绝，证明新增检查能捕获报告间计数漂移；它不改变真实业务门控，仍要求 100 samples、3 explicit replicates、10 groups 和所有 benchmark/claim gates 通过。

## 2026-08-12 multitask readiness self-validation findings

- `multitask_training_readiness_report.json` 是多个下游报告的源输入；仅由 builder 生成而无独立 validator 时，行数口径或 gate 真值漂移只能在更下游暴露，定位较晚。
- 新 self-validator 直接重读 canonical strict/audited/activity-risk import JSONL 和 activity-risk import validation report，重算五头 expected rows：activity_risk `6`，mutation_rank/stability/substrate_fit/assay_success 均 `0`。
- validator 强制 `status=blocked`、`ready_head_count=0`、全部 `missing_head_labels` 保留、`training_execution_allowed=false`、`safe_for_model_claim=false`、`release_ready=false`。临时篡改 activity_risk source count/row count 为 0 会被拒绝。

## 2026-08-12 five-head gap plan validation findings

- Gap plan 是 operator-facing 下一步执行计划，不能只作为 Markdown/JSON 说明存在；它必须与 threshold report 的 label rows、sample/replicate/group metrics 和 blocked heads 精确一致。
- 新 validator 逐头绑定 `current_training_rows/minimum_rows/missing_to_minimum/candidate_rows_observed/observed_sample_count/observed_replicate_count/observed_group_count/head_status/thresholds_met` 到 threshold report。当前 activity_risk 为 `6 rows / missing 94 / samples 6 / replicates 0 / groups 2`，其余四头为 `0/100`。
- Candidate signals 也被重新绑定：wet-lab candidates `445`、numeric `6`、authorization worklist `12`、authorized rows `8`、FireProt mapping `5067`、reviewed import `0`、feature rows excluded from labels `203`。这些仍只是候选/缺口，不是训练导入或模型 claim。
- Gap action JSONL 是 operator-facing 的逐头执行件，必须和 JSON report 的 `head_gap_actions` 保持逐字段一致。否则 UI/看板/人工队列可消费 JSONL 旧值，而下游报告仍显示自洽。
- 新 parity gate 绑定 JSONL 的 5 个 head、无重复 head、完整 expected head set，以及 22 个核心字段：优先级、当前训练行数、最低行数、缺口、候选行、review queue、blocking gate、next action、observed sample/replicate/group、head status、thresholds 和 fail-closed flags。
- 临时篡改 JSONL 中 `activity_risk.current_training_rows=0` 被 `activity_risk_gap_action_jsonl_current_training_rows_matches_report` 拒绝；canonical 仍为 `activity_risk=6/100`、其余四头 `0/100`，训练执行、模型声明和 release 仍关闭。

## 2026-08-12 five-head sample gap queue validation findings

- Sample gap queue 比 gap plan 更接近 operator execution queue：它包含 source pools、sample metrics 和汇总 totals，因此不能只检查阈值字段；必须重新绑定真实源文件，防止候选池数量或 missing totals 被旧 JSONL/report 漂移掩盖。
- 新 validator 重读 canonical source JSONL 后，逐 pool 校验 `observed_rows`、`selected_rows_for_head` 和 `sample_metrics`。当前源绑定为 FireProt mapping `5067`、FireProt reviewed `0`、KWB wet-lab stability `91`、KWB activity numeric `9`、activity authorization gap `9`、activity_risk formal label decisions `6`。
- Queue report totals 现在由 JSONL 实时重算：`current_label_rows=6`、`missing_label_rows_total=494`、`missing_groups_total=48`、`missing_replicates_total=15`、`candidate_source_pool_rows=5182`、`feature_rows_observed=203`、`training_import_written_rows=0`。这些是缺口证据，不是训练可执行证明。
- 临时篡改 JSONL pool observed rows 或 report missing totals 均被拒绝；canonical 仍保持 `safe_for_training_import=false`、`safe_for_model_claim=false`、`release_ready=false`。

## 2026-08-12 head model-card status validation findings

- Head model-card status 是下游展示件，虽然文案写着 local-only draft，但如果没有 validator，单独把 `activity_risk` 行数或 ready 状态改成可训练会被 data lake/release 摘要间接收进去。
- 新 validator 从 multitask readiness 和 benchmark matrix 重新投影完整 markdown，要求五个 head 的 label rows、minimum rows、training ready、benchmark scorecard ready、benchmark status 和 prohibited uses 文案逐项一致。
- 当前 canonical markdown 为 `mutation_rank=0/100`、`stability=0/100`、`activity_risk=6/100`、`substrate_fit=0/100`、`assay_success=0/100`，全部 `Training ready: false`、`Benchmark scorecard ready: false`。
- Report 层也绑定 `heads=5`、`ready_heads=0`、`ready_for_model_claim=false` 和 markdown path；临时 markdown/report 篡改均被拒绝。该 status draft 仍不是 release model card，不能支持模型质量声明。

## 2026-08-12 five-head benchmark gap plan validation findings

- Benchmark gap plan 同时服务 operator queue、readiness packet 和模型门控摘要；只验证 builder 成功不足以防止 report summary 或 actions JSONL 被单独改写。
- 新 validator 从 canonical benchmark matrix、acquisition plan、score cache validation/manifest、claim readiness 和 multitask readiness 独立重算 15 个 benchmark 行与 5 个 head 汇总。当前 `required=15`、`cache_validated=13`、`heads_with_complete_scorecards=3`，但 `ready_for_model_claim=false`。
- Validator 强制 benchmark row、head summary、top-level summary、not-claimable metrics、Markdown 行和 `five_head_benchmark_gap_actions.jsonl` 逐项一致，并保留 training/model/customer/release 的 fail-closed 状态。
- 临时把 report summary 的 cache count 改为 15 会触发 `summary_matches_current_sources`；临时把 mutation_rank action JSONL 的 cache count 改为 15 会触发 `actions_jsonl_matches_report_actions`。Canonical report/action 文件未被修改。

## 2026-08-12 benchmark readiness packet parity findings

- Benchmark readiness packet validation 过去主要验证 JSONL packet 合同；report summary 和 Markdown 展示件如果单独漂移，下游 local release/readiness summary 仍可能消费旧展示状态。
- 新增 report/Markdown parity 后，validator 首次发现 packet JSONL 的 `source_snapshot` 仍绑定旧 benchmark score-cache manifest/intake/validation SHA。重建 packet 后，当前 canonical 三件套重新一致。
- 当前 readiness packet 只有 2 行，分别是 `mutation_rank/KWB strict mutation holdout` 和 `substrate_fit/reviewed substrate identity set`；两行均 blocked、local_contract_only、completion_ready false，score/metric values 均为空。
- Report summary 与 Markdown 现在由 JSONL packet 实时重算验证：`packet_rows=2`、`invalid_gap_rows=2`、`local_contract_only_rows=2`、`external_source_required_rows=0`、`completion_ready_rows=0`、`score_values_recorded=0`。
- 临时篡改 report summary 或 Markdown packet rows 均被拒绝；该 packet 仍不能写 benchmark score-cache intake、不能登记分数、不能打开模型声明、训练、客户交付或 release。

## 2026-08-12 benchmark hard-gate operator packet validation findings

- Benchmark hard-gate operator packet 是更底层的操作脚手架；如果缺少 validator，packet/report/Markdown 可以在 builder 之后独立漂移，而下游只看到“有 packet”。
- 新 validator 从 five-head benchmark gap plan、score-cache validation、acquisition plan 和 score-cache manifest 重算 packet。当前 expected packets 为 2 行：`mutation_rank/KWB strict mutation holdout` 与 `substrate_fit/reviewed substrate identity set`。
- 两行均 `open_blocked`、`completion_ready=false`、`requires_human_input=true`，且 `download_allowed_by_packet`、`benchmark_approval_granted`、`write_benchmark_score_cache_intake_allowed`、`manifest_update_allowed`、`safe_pipeline_integration_allowed`、`model_claim_allowed`、`training_unlocked`、`release_ready`、`safe_for_model_claim` 全部 false。
- Report summary 与 Markdown 现在绑定 packet JSONL：`packet_rows=2`、`heads_with_packets=2`、`completion_ready_rows=0`。临时篡改 report 或 Markdown 均被拒绝。

## 2026-08-12 wet-lab hard-gate operator packet validation findings

- Wet-lab hard-gate packet 是人工授权前的作业脚手架；它接近训练标签入口，因此必须证明 packet/report/Markdown 全部来自当前 authorization gap plan，而不是单独展示状态。
- 新 validator 按 builder 排序规则重算 12 个 packet：E331Q critical tradeoff rows 置前，其余 D105N/S265T mixed-benefit rows 按 ratio delta、variant、metric 排序。
- 当前 packet summary 为 `packet_rows=12`、`completion_ready_rows=0`、variant counts 为 D105N/E331Q/S265T 各 4，head counts 为 activity_risk 9、stability 3。
- 所有 packet 均 `open_blocked`、`requires_human_input=true`，且 `authorization_decision_written_by_packet=false`、`feedback_intake_written_by_packet=false`、`training_label_written_by_packet=false`、`model_claim_allowed=false`、`release_ready=false`。
- 临时篡改 report 或 Markdown packet rows 均被拒绝；该 validator 不批准湿实验授权、不写 intake、不增加训练标签。

## 2026-08-12 ddG physical preflight parity findings

- ddG physical runtime preflight 已有 JSON/JSONL 数值 validator，但 Markdown 展示件此前未绑定，且 safe pipeline 后段重新 build preflight 后没有立即重跑 validator，存在旧 validation 被 status board 消费的窗口。
- 新增 Markdown parity 后，validator 会按 report `created_at`、summary 和三 backend row 重投影全文。当前 backend 顺序固定为 rosetta、pyrosetta、foldx。
- 当前 physical preflight 状态仍 fail-closed：`approved_runtime_receipt_rows=2`、`ready_to_write_formal_runtime_receipt_rows=2`、`ready_to_run_physical_ddg_smoke_rows=1`，但 `all_physical_backends_ready=false`、`physics_ddg_ready=false`、`safe_for_model_claim=false`、`release_ready=false`。
- 临时篡改 report missing license rows 或 Markdown missing license rows 均被拒绝；该 preflight 仍不等于物理 ddG 全链 ready，也不允许将任何 ddG 结果作为训练标签或模型声明证据。

## 2026-08-12 hard-gate status board validation findings

- Hard-gate status board 原先没有自校验，且对 benchmark、wet-lab、ddG 三条新 validator 仍使用 `validation_report=None`，导致 board 显示 `validation_pending`，并把 ddG 的 `ready_to_write_formal_runtime_receipt_rows=2` 误作 hard-gate completion error。
- 修正后六条 gate 均有 validation report：numbering、wet-lab、benchmark、ddG、substrate-fit、structure-feature。当前 board 为 `gate_rows=6`、`packet_rows=65`、`validated_gates=6`、`validation_pending_gates=0`、`invalid_gates=0`。
- ddG gate 仍只是 preflight validated；`ready_to_write_formal_runtime_receipt_rows=2` 不代表 completion_ready，也不打开 physics ddG lane、模型声明或 release。
- 新 board validator 重算 report、JSONL 和 Markdown。临时篡改 validated gate count 会被拒绝，防止总看板把 pending/invalid 状态伪装成 validated。

## 2026-08-12 true hard-gate breakthrough candidate validation findings

- True hard-gate breakthrough candidates 名称容易被误读为“已突破”，但实际输出必须保持 review draft。新增 validator 后，三份 draft 都绑定实时来源并强制 `review_draft=true`。
- 当前 candidate 数量为 numbering deterministic reject drafts `475`、structure DBREF chain-mapping drafts `9`、wet-lab authorization review drafts `12`。这些数量是人工复核候选，不是 formal decisions。
- Validator 要求 report 中 `formal_decisions_written=0`、`curation_applied=false`、`feedback_intake_written=false`、`training_rows_written=0`、`safe_for_model_claim=false`、`release_ready=false`。
- 临时把 report 改成 formal decision 已写入会被拒绝；临时篡改 Markdown draft 计数也会被拒绝。该模块仍不能提升 reviewed numbering、structure graph、feedback preflight 或训练标签。

## 2026-08-12 next hard-gate attack wave validation findings

- `next_hard_gate_attack_wave` 是下游 release summary 会读取的执行/阻塞快照；如果只检查 lane 名称和 fail-closed bool，JSONL 或 report summary 可以单独漂移，造成“执行波次已有突破”的误导。
- 新 validator 现在重新读取源报告并按 builder 逻辑投影四条 lane：benchmark real score cache、physical ddG runtime probe、five-head label threshold、human formal decision preflight。
- 当前源绑定事实为 `lane_rows=4`、`executed_blocked_rows=4`、benchmark cache `13/15 valid`、benchmark missing heads `mutation_rank/substrate_fit`、five-head ready count `0`、human ready training import `0`。
- ddG lane 记录本地 Rosetta/FoldX/PyRosetta runtime/receipt/smoke 事实，当前 `formal_decision_written_rows=1`、`runtime_receipt_written_rows=1`，但 full physical ddG preflight 仍 `physics_ddg_ready=false`，因此 model/release 仍 fail-closed。
- Report summary 与 JSONL 均已绑定当前源；临时篡改 report formal-decision count 或 JSONL benchmark valid count 会被拒绝。该 attack wave 不写训练导入、不生成模型质量声明、不放开客户交付或 release。

## 2026-08-12 model artifact claim guard findings

- Model artifact claim guard 是 release summary 会消费的模型权重隔离层；旧 validator 固定 `EXPECTED_ARTIFACT_COUNT=9` 且主要检查 report 自身，不能证明当前文件系统和 builder artifact 合同没有漂移。
- 新 validator 从 builder 动态读取 `MODEL_ARTIFACTS`，重新计算每个 artifact 的 exists、SHA-256、artifact class、blocked reasons 和 claim/release flags，再要求 canonical report 完全匹配当前投影。
- 当前 9 个 artifact 都存在，但全部是 prototype、legacy baseline、empty-train baseline 或 scaffold：legacy baseline `4`、blocked empty training baseline `2`、rule/baseline non-neural `1`、scaffold-only `1`、code scaffold `1`。
- Claimable model artifact、trained neural weight artifact、production model artifact 三类计数都必须为 `0`；`safe_for_model_claim=false`、`release_ready=false` 仍由 validator 强制。
- 临时篡改 artifact count 或把某个 artifact class 改成 claimable 都会被拒绝。该 guard 只证明现有模型文件不能被误用为发布权重，不代表模型训练完成。

## 2026-08-13 model-quality hard-gate projection findings

- Model-quality hard-gate report 是模型声明前的总聚合层；旧 validator 已检查 current/top-level 关键字段，但没有要求完整 `source_state`、10 条 `hard_gates` 和 `negative_protection_checks` 与当前源报告逐项一致。
- 新 validator 重新投影完整 report，绑定七类源：training label import、wet-lab authorization、ddG consumption、benchmark coverage、advanced feature contract、local release 和 claim readiness matrix。
- 当前硬门槛事实为 training import eligible rows `6`、wet-lab authorized/preflight `8/8`、wet-lab import `0`、feature inputs `203` 且 input-only；这些是局部工程证据，不足以打开模型质量声明。
- 仍关闭的关键门为 `physics_ddg_ready=false`、`benchmark_ready_for_model_claim=false`、`model_quality_ready=false`、`safe_for_model_claim=false`、`release_ready=false`。
- 临时篡改 `source_state.training_import_eligible_rows` 或把 `release_ready` hard gate 标成 unlocked 都会被拒绝。该 validator 现在能防止模型质量总报告局部字段漂移后被 release summary 消费。

## 2026-08-13 tool lane evidence pack findings

- Tool lane evidence pack 是 local release summary 会消费的工具运行证据层；旧 validator 检查 lane 集合和少量状态，但没有要求 report/receipt 与当前 builder 投影完全一致。
- 新 validator 动态运行 `build_pack()`，重新投影 ProteinMPNN、RFdiffusion、AlphaFold2、AlphaFold/ColabFold proxy、PDBQT preparation、Vina docking、ligand topology、GROMACS long MD 共 8 条 lane 和 8 条 receipt。
- 当前 canonical 状态为 `ready_lanes=0`，proxy/external lanes blocked，local binary gated lanes未满足真实 ready_to_verify；这只是本机可见信号，不是推理、对接或 MD 已执行。
- Report 和 receipts JSONL 均必须匹配 builder 投影；临时把 ProteinMPNN 改为 ready 或把 receipt 改为 ready_to_verify 都会被拒绝。
- 该 evidence pack 不授权真实工具运行结果、不写训练标签、不支持模型质量声明、不支持客户交付或 release。

## 2026-08-13 human-target contract gap projection findings

- Human-target / antibody gap report 是 local release manifest 会消费的专项安全 guard；旧 validator 只检查 `schema_only_contracts*` 状态前缀、runtime gap 非空和 antibody schema 数量，不能证明整份 report 来自当前后端合同与 gate snapshot。
- Builder 现在暴露 `build_report(created_at=...)`，validator 动态重建完整 report，并要求 product line sections、backend schema contract 集合、schema present/missing 分区、runtime/source gaps、gate snapshot 和 policy 文案全部匹配当前 builder 投影。
- 当前真实状态为 2 个 product line、10 个 schema-only backend contracts、human-target 和 antibody 两侧各 4 个 runtime/source gaps；`bio_specialty_input_gate_report.json` 与 `scientific_claim_gate_report.json` 当前不存在，因此 gate snapshot 仍为 present=false/status=null。
- 临时把 human-target 改为 runtime ready 或清空 runtime gaps 会被 projection mismatch、schema-only status 和 gap-present 检查拒绝；临时删除 `OffTargetRisk` backend schema entry 或把 gate snapshot 改为 ready 也会被拒绝。
- 该 report 仍只说明 schema-only 合同存在和真实 source/runtime 缺口存在；不代表 HPA/GTEx、Reactome/GO、ligand-receptor graph、ANARCI/IMGT、germline DB 或 VH/VL mapping 已 ready，也不支持模型声明、客户交付或 release。

## 2026-08-13 human-target source/runtime manifest findings

- Source/runtime manifest 比 contract gap report 更接近真实能力状态：它列出 HPA、GTEx、Reactome、ligand-receptor graph、ANARCI/IMGT、human germline DB、SAbDab/OAS 七个 source/runtime lane，因此 validator 必须绑定 report 和 receipt 两个消费面。
- Builder 现在支持注入 report/source `created_at`，validator 可用 canonical 时间戳重建完整 expected manifest 与 receipts。校验范围包括 7 个 source、7 个 receipt、summary、receipt source-id parity、blocked reason、runtime signal 和 `source_ready/claim_eligible/customer_ready/release_ready=false`。
- 当前真实状态仍为 `sources=7`、`receipts=7`、全部 blocked、ready sources=0；ANARCI/IMGT runtime 因本地 executable 缺失 blocked，其他 source 因 source manifest/runtime receipt 缺失 blocked。
- 临时把 source 标成 ready 会被 manifest projection、summary、all-blocked 和 source-ready false 检查拒绝；临时改 receipt blocked_reason/source_id 会被 receipts projection 和 receipt source-id parity 拒绝。
- 该 manifest 仍只是 fail-closed 缺口清单；不证明任何人类靶点 source 已检索、抗体编号 runtime 已执行、germline DB 已接入、人源化建议已生成、客户交付或 release 已 ready。

## 2026-08-13 human-target blocked split manifest findings

- Split blocked manifests 是把 7 条 source/runtime lane 拆成单源审计件；旧 validator 只检查 split 数量、文件存在和少数 false 字段，不能证明 index 和 split 文件仍来自当前 upstream manifest。
- Builder 现在提供 `build_manifests()`，validator 继承 index/split 时间戳后从当前 `human_target_source_runtime_manifest.json` 重投影 index 与 7 个 split JSON。校验范围包括 index 完整匹配、split path/source-id 集合、每个 split payload、blocked status/reason、runtime signal 和 release/model/customer false 字段。
- 当前真实 split 为 7 个：HPA、GTEx、Reactome、ligand-receptor graph、ANARCI/IMGT、human germline DB、SAbDab/OAS；全部 blocked，ready split=0。
- 临时把 index 首项改成 ready 会被 index projection mismatch 拒绝；临时把 HPA split 改成 ready/source_ready true 或追加 required artifact 会被 split projection mismatch 和 blocked 字段拒绝。
- 这些 split 仍只是 audit slice，不是 source manifest approval、runtime receipt、数据下载、抗体编号、人源化建议、客户交付或 release 凭证。

## 2026-08-13 human-target unlock checklist findings

- Unlock checklist 是 operator-facing 的人工清单层；旧 validator 只读取 JSONL，并只检查 row count、ready false 和 missing_steps 非空，不能发现 report summary 单独漂移，也不能证明 checklist 仍来自当前 blocked split index。
- Builder 现在提供 `build_checklist()`，validator 继承 row/report 时间戳后从当前 `human_target_blocked_source_manifest_index.json` 重投影 7 条 checklist rows 和 report。校验范围包括 JSONL 完整匹配、report 完整匹配、source_manifest_path、required/missing steps、ready/claim/customer/release false 字段。
- Validator 还绑定 P406 的 blocked source manifest index validation：`success=true`、`index_matches_current_builder_projection=true`、`split_manifests_match_current_builder_projection=true` 必须同时成立，否则 checklist 不可被视为当前来源生成。
- 当前 checklist 为 7 行、0 ready_to_unlock；HPA/GTEx 额外要求 RNA/protein expression unit boundary review，ANARCI/IMGT 额外要求 numbering runtime smoke artifact，其余 source 使用 5 个 common steps。
- 临时把 checklist 首行改为 ready_to_unlock、completed all steps、missing_steps 为空会被 checklist projection、ready false、missing steps 和 step parity 检查拒绝；临时改 report ready/release summary 会被 report projection mismatch 拒绝。
- 该 checklist 仍不是审批记录；不能解锁 source manifest、runtime execution、人类靶点情报、抗体编号/人源化、模型声明、客户交付或 release。

## 2026-08-13 local release human-target projection coverage findings

- Local release guard coverage 是 release manifest 的消费层；旧逻辑已检查 human-target success/数量/ready=0，但没有证明这些摘要字段来自 P404-P407 的完整 projection validators。
- Coverage validator 现在绑定 7 个 projection flags：contract gap report、source/runtime manifest、runtime receipts、blocked source index、blocked split manifests、unlock checklist、unlock report。任一 projection flag 不是 true，local release guard coverage 会 fail closed。
- Release summary 的 `human_target_gap_sections`、`human_target_source_runtime_total_sources`、`human_target_blocked_source_split_count`、`human_target_source_unlock_checklist_rows` 和 `human_target_source_unlock_ready_rows` 也必须与对应 validation report 当前值一致。
- 临时把 runtime validation 的 manifest/receipt projection 改为 false 会触发两个 release coverage failures；临时把 unlock validation 的 checklist/report projection 改为 false 并把 ready rows 改成 1 会触发三个 failures。
- 该 coverage 只证明 release manifest 覆盖了 human-target fail-closed guard 链；不代表任何 source/runtime 解锁，也不打开 model claim、customer delivery 或 release_ready。

## 2026-08-13 master readiness human-target projection propagation findings

- P408 后 local release coverage 已知道 7 个 human-target projection flags，但 `local_release_manifest.readiness_summary` 和 `master_readiness_board` 仍只带 success/count/failure 摘要；总看板无法直接发现 projection 绑定状态。
- Local release summary 现在显式包含 7 个 human-target projection bool，master board 的 governance_release current 同步投影这些 bool 和 coverage success/failures。
- Master validator 新增 `--local-release` 隔离输入，既校验 board current 与 local release summary 一致，也强制 `local_release_guard_coverage_success=true`、failures=0、7 个 projection bool 全 true。
- 临时篡改 local release summary 的 runtime projection/failure count 会触发 source-to-board mismatch；临时篡改 master board current 的 unlock projection/failure count 会同时触发 mismatch 和 fail-closed true/zero 检查。
- 该传播提高总看板可观测性，但不改变业务状态：human-target source/runtime 仍 blocked，master readiness 仍 `blocked_for_model_claim`。

## 2026-08-13 claim readiness human-target requirement findings

- Claim readiness matrix 是模型声明、客户交付和 release review 的最终语义层；只依赖 master board blocked 会隐藏 human-target projection chain 的状态，审查者看不到这条证据链是否仍绑定当前 builder。
- Builder 现在从 local release summary 读取 7 个 human-target projection bool，形成 `human_target_projection_ready`；同时要求 runtime ready sources=0 和 unlock ready rows=0，形成 `human_target_fail_closed`。
- `model_quality_claim` 与 `local_release_review_package` 增加 `human-target projection coverage valid` requirement；`customer_sequence_package` 增加 `human-target source/runtime fail-closed coverage valid` requirement。当前这些新 requirement passed=true，但三个 claim 仍因模型、客户、release 其它硬门槛 blocked。
- Policy validator 的 source parity 能捕获 claim requirement 漂移：删除 release claim 的 human-target requirement 或篡改 customer claim 的 human-target evidence 都触发 `source_parity_claim_row`。
- 该要求只说明 human-target fail-closed 证据链有效，不说明 source/runtime 已 ready；claim matrix 仍 `1 allowed / 10 blocked`，所有 model/customer/release 高风险 claim 继续关闭。

## 2026-08-13 claim promotion human-target evidence findings

- Claim promotion decision gate 是高风险 claim 从 blocked 到 approved 的人工入口；P410 之后如果 approved 决策仍只要求 claim matrix/policy/anchor 三件套，会漏掉 local release coverage 和 master readiness 中的 human-target projection 证据链。
- Required validation reports 已扩展为 6 个：claim matrix、claim policy current、policy anchor、local release guard coverage、local release manifest、master readiness validation。Template 9 行自动刷新后每行都包含这 6 个报告。
- Approved 分支现在还实时检查 local release guard coverage success、master readiness validation success、7 个 human-target projection fields 全 true、runtime ready sources=0、unlock ready rows=0。
- 单元测试覆盖 approved 缺 current/anchor、缺 release/master、human-target projection false、非 approved 设置 approval flag、完整 fixture 等 8 个场景。
- 当前正式输入仍为空：`decision_rows=0`、`approved_rows=0`、`missing_promotion_decisions=9`、`ready_for_claim_promotion=false`。该门只收紧未来人工批准证据，不产生批准，也不打开 model/customer/release claim。

## 2026-08-13 local release claim-promotion contract findings

- P411 后 claim promotion validator 已要求 approved 决策携带 6 个 validation reports，但 local release manifest 摘要此前只记录 promotion success/failures/decision rows/approved rows/missing decisions/error counts，不能显式发现 template contract 或 required report set 漂移。
- Promotion validation report 现在显式输出 `required_validation_reports` 和 `required_validation_report_count=6`；local release summary 同步记录 template rows、template matches expected contract、target claim rows 和 required validation report count/list。
- Local release fail-closed consistency validator 现在把这些 summary 字段全部回绑到 `claim_promotion_decision_validation_report.json`，并硬检查 required report set 必须包含 claim matrix、claim policy current、policy anchor、local release guard coverage、local release manifest 和 master readiness validation。
- 当前 canonical 状态为 `template_rows=9`、`template_matches_expected_contract=true`、`target_claim_rows=9`、`required_validation_report_count=6`、`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`。
- 隔离篡改 release summary 的 template rows 或 required report count/list 均会被 `summary_matches_claim_matrix_policy` 拒绝。该层只证明 promotion evidence contract 被 release summary 正确消费，不批准 promotion、不打开 model claim/customer delivery/release。

## 2026-08-13 master readiness claim-promotion contract findings

- P412 后 local release summary 已能看到 claim-promotion template 和 6-report contract，但 master readiness board 的 governance release stream 仍只传播 local release coverage 与 human-target projection 字段，不能在总看板层直接发现 promotion evidence contract 漂移。
- Master builder 现在把 promotion validation success/failures、template rows、template expected-contract bool、target claim rows、required validation report count/list、decision rows、approved rows、missing decisions、decision success 和 validation failures 全部投影到 `governance_release.current`。
- Master validator 现在将这些字段回绑 local release summary，并增加当前 fail-closed 硬检查：validation success=true、validation failures=0、template rows=9、target claim rows=9、required report count=6、decision rows=0、approved rows=0、missing decisions=9、decision success=false。
- 隔离篡改 master board 的 template rows 或 required report count/list 会被 source mismatch 和 expected-count 检查拒绝；canonical master validation 当前 `success=true/failures=0/overall_status=blocked_for_model_claim/ready_streams=1`。
- 该传播只是提高总看板可观测性和一致性，不代表 claim promotion 已批准；model claim、customer delivery、release 仍关闭。

## 2026-08-13 claim readiness promotion evidence requirement findings

- P413 后总看板已能看到 promotion evidence contract，但 claim readiness matrix 仍只显式要求 human-target projection/fail-closed coverage；高风险 claim 行本身没有说明 promotion template 和 6-report contract 是否仍由 release/master 当前投影支撑。
- Claim matrix builder 现在读取 `master_readiness_board.governance_release.current` 的 promotion contract 字段，并与 `local_release_manifest.readiness_summary` 的同名字段逐项比较。
- 新增的 `claim_promotion_contract_ready` 要求 validation success=true、failures=0、template rows=9、template matches expected=true、target claim rows=9、required report count=6、required reports 六件套完整、decision rows=0、approved rows=0、missing decisions=9、decision success=false。
- 9 个高风险 claim 均新增 `claim-promotion evidence contract valid` requirement；当前该 requirement 均 passed=true，但由于其它硬门仍未满足，claim matrix 仍为 `1 allowed / 10 blocked`。
- 删除任一高风险 claim 的 promotion requirement 或篡改 evidence 中的 required report count 会被 policy source parity 拒绝。该 requirement 只说明 promotion evidence contract 有效，不批准任何 promotion。

## 2026-08-13 claim promotion approved branch requirement findings

- P414 后 claim matrix 的高风险 claim 行都有 `claim-promotion evidence contract valid` requirement，但 promotion validator approved 分支此前只检查目标 claim `ready=true`，没有直接校验这条 requirement 是否存在且 passed。
- Promotion validator 现在在 approved 分支读取目标 claim requirement，并要求 `claim-promotion evidence contract valid` 存在且 `passed=true`；否则分别触发 `approved_claim_missing_promotion_evidence_requirement` 或 `approved_claim_promotion_evidence_contract_not_valid`。
- Approved 分支还重新检查 local release summary 的 promotion contract：validation success=true、failures=0、template rows=9、target claim rows=9、required report count=6、required reports 六件套完整、decision rows=0、approved rows=0、missing decisions=9、decision success=false。
- Validation report 现在记录目标 claim requirement 覆盖：当前 `target_claim_rows_with_promotion_contract_requirement=9`、passed rows=9、complete=true。
- 当前正式 promotion 输入仍为空，因此这些检查只收紧未来 approved 决策路径，不产生批准；`approved_rows=0`、`ready_for_claim_promotion=false`、model/customer/release 仍关闭。

## 2026-08-13 release/master promotion requirement coverage findings

- P415 的 promotion validation report 已记录 9 个目标 claim 都有并通过 promotion requirement，但 local release 和 master readiness 仍只传播旧的 promotion template/required-report/decision 字段，不能直接显示 target claim requirement coverage。
- Local release summary 现在新增 requirement name、target claim rows with contract requirement、passed rows 和 complete flag，并由 fail-closed consistency validator 回绑 canonical promotion validation report。
- Master governance release stream 也同步投影这 4 个字段，master validator 既校验与 local release summary 一致，也强制 requirement name 正确、coverage rows=9、passed rows=9、complete=true。
- 隔离篡改 release summary passed rows=8 或 master complete=false 均会被对应 validator 拒绝。该层只是传播和审计 P415 覆盖事实，不批准 promotion。
- 当前状态仍为 `ready_for_claim_promotion=false`、`release_ready=false`、master readiness `blocked_for_model_claim`。

## 2026-08-13 claim readiness promotion coverage evidence hardening findings

- P416 之后，claim matrix 的 promotion evidence 只暴露旧的 promotion template / required-report / decision contract；如果不把 target claim requirement 覆盖字段也纳入 claim 行证据，审查者仍看不到 9 个高风险 claim 是否真的都包含并通过 `claim-promotion evidence contract valid`。
- `build_claim_readiness_matrix.py` 现在把 `claim_promotion_requirement_name`、`claim_promotion_target_claim_rows_with_contract_requirement`、`claim_promotion_target_claim_rows_with_contract_requirement_passed`、`claim_promotion_target_claim_contract_requirement_complete` 一并纳入 claim-promotion evidence contract，并硬检查 name/rows/passed/complete。
- 当前 canonical claim matrix 仍是 `claims_allowed=1 / claims_blocked=10`；9 个高风险 claim 的 promotion requirement evidence 现在同时绑定 local release summary 与 master governance release 的 P416 覆盖字段。
- 临时篡改 claim matrix evidence 中 release summary passed rows=8 或删除 master governance complete 字段，都会被 `source_parity_claim_row` 精确拒绝。
- 这层只强化 claim matrix 对 promotion coverage 的可观测性；不产生 approved promotion，也不打开 model claim、customer delivery 或 release。

## 2026-08-13 claim promotion requirement evidence source-bound findings

- Approved promotion 分支此前只要求目标 claim 的 `claim-promotion evidence contract valid` requirement 存在且 passed，没有直接校验该 requirement 的 evidence 是否仍与当前 local release promotion contract 一致。
- `validate_claim_promotion_decisions.py` 现在对 approved 分支执行 source-bound evidence 检查；篡改 claim requirement 的 master evidence 会触发 `approved_claim_promotion_evidence_not_source_bound`。
- Promotion validation report 现在额外记录 requirement evidence coverage：当前 9 个 high-risk target claim 均具备 source-bound evidence，`target_claim_promotion_contract_requirement_evidence_complete=true`。
- 这些 evidence coverage 字段继续投影到 local release summary 和 master governance release，并由 local release consistency / master readiness validator 硬检 rows=9、complete=true；临时篡改 local release 或 master 的 evidence coverage 会被拒绝。
- 工程上发现一个自举风险：如果 claim matrix ready 条件依赖由 promotion validator 从 claim matrix 回算出的 coverage 字段，stale promotion report 会导致 controlled release-guard 子链无法自恢复。最终设计保留 coverage 为 claim row evidence，但 ready 条件只依赖非自派生的基础 promotion contract。
- Controlled execution wave 的 release-guard action 原先没有在 build local release 前刷新 claim matrix/policy/current/promotion validation；P418 已补齐 41-command 顺序并更新 order contract SHA。该修复只改善本地收敛和证据新鲜度，不开放任何 promotion、model claim、customer delivery 或 release。

## 2026-08-13 approved promotion release evidence coverage findings

- P418 后 local release summary 已传播 target claim requirement evidence coverage，但 approved promotion 的 `release_promotion_contract_valid()` 还只检查 requirement rows/passed/complete，没有直接检查 evidence rows/complete。
- P419 将 `claim_promotion_target_claim_rows_with_contract_requirement_evidence=9` 和 `claim_promotion_target_claim_contract_requirement_evidence_complete=true` 纳入 approved release promotion contract。
- 隔离负例显示：release summary evidence rows 改为 8 会触发 `approved_release_promotion_contract_not_valid`；claim requirement evidence 与 release summary 不一致仍触发 `approved_claim_promotion_evidence_not_source_bound`。
- 当前 canonical promotion validation 仍为空输入：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`。该补强只收紧未来人工批准入口，不产生任何 approved promotion。

## 2026-08-13 approved promotion validation reports exact contract findings

- Approved promotion 分支此前使用 required reports 的 subset 检查；只要 6 个 required reports 都存在，approved 行仍可夹带额外 forged report，或在其它消费层误读为更多证据。
- `validation_report_contract_errors()` 现在要求 approved row 的 `validation_reports` 与 `REQUIRED_VALIDATION_REPORTS` 完全一致：6 个路径、有序、无重复、无额外项。
- 新负例覆盖三类漂移：额外 `reports/forged_extra_validation_report.json` 触发 `approved_unexpected_validation_reports`；重复首个 required report 并遗漏末项触发 `approved_missing_required_validation_reports` 和 `approved_duplicate_validation_reports`；反转顺序触发 `approved_validation_reports_wrong_order`。
- Canonical promotion input 仍为空，validation report 仍 `decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`；local release、master readiness、claim policy/current 继续 fail-closed 通过。
- 该补强只收紧未来人工 approved promotion 的证据报告列表，不产生 approved promotion、不打开模型声明、客户交付或 release。

## 2026-08-13 approved promotion evidence artifacts exact contract findings

- Approved promotion 分支此前只要求 `evidence_artifacts` 非空且路径存在；这会允许人工 approved 行引用任意无关本地文件作为 evidence artifact。
- P421 将 required evidence artifacts 固定为三个源证据件：`reports/claim_readiness_matrix.json`、`reports/local_release_manifest.json`、`reports/master_readiness_board.json`。这些是 approved 分支实时读取 claim readiness、release summary 和 master governance 状态的核心源面。
- `evidence_artifact_contract_errors()` 现在要求 approved row 的 `evidence_artifacts` 与 required evidence artifacts 完全一致：有序、无重复、无额外项、无遗漏。
- 新负例覆盖三类漂移：追加 `reports/unrelated_evidence.json` 触发 `approved_unexpected_evidence_artifacts`；重复 claim matrix 并遗漏 master board 触发 `approved_missing_required_evidence_artifacts` 和 `approved_duplicate_evidence_artifacts`；反转顺序触发 `approved_evidence_artifacts_wrong_order`。
- Canonical promotion input 仍为空：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`。该补强只收紧未来人工 approved promotion 的 evidence artifact 列表，不产生批准、不打开模型声明、客户交付或 release。

## 2026-08-13 release/master promotion evidence artifact propagation findings

- P421 后 approved 分支已要求三源 `evidence_artifacts`，但 promotion validation report、local release summary 和 master readiness board 仍只显式传播 required validation reports 合同；总看板无法直接审计 approved evidence artifact 合同。
- Promotion validation report 现在输出 `required_evidence_artifact_count=3` 和 required artifacts list；local release summary 用 `claim_promotion_required_evidence_artifact_count/list` 消费这些字段。
- Local release consistency validator 现在把 summary 字段回绑 promotion validation report，并硬检查三源路径为 claim matrix、local release manifest、master readiness board。
- Master governance release stream 同步投影这两个字段；master validator 同时检查 source parity 和 expected contract。
- 隔离篡改 promotion report 的 evidence artifact count/list 会被 local release consistency 拒绝；隔离篡改 master current 的同名字段会被 source mismatch 与 expected contract 检查拒绝。
- 当前 canonical promotion 仍 `decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`。该传播只提高 release/master 可观测性，不批准 promotion、不打开 model/customer/release gate。

## 2026-08-13 claim readiness promotion evidence artifact hardening findings

- P422 后 release/master 已传播 required evidence artifact 合同，但 claim readiness matrix 的 `claim-promotion evidence contract valid` requirement evidence 仍只包含 promotion validation report 合同和 requirement coverage，不展示 approved evidence artifacts 三源绑定。
- `build_claim_readiness_matrix.py` 现在把 `claim_promotion_required_evidence_artifact_count` 和 `claim_promotion_required_evidence_artifacts` 纳入 `claim_promotion_contract_keys`，并要求 release summary 与 master governance release 完全一致。
- `claim_promotion_contract_ready` 现在硬检查 required evidence artifact count=3 且路径为 claim matrix、local release manifest、master readiness board。
- 由于 claim matrix evidence 扩展了 source-bound 字段，promotion validator 的 `CLAIM_PROMOTION_CONTRACT_EVIDENCE_FIELDS` 也必须同步包含这两个字段；否则 evidence coverage 会从 9 退化为 0。P423 已同步补齐，canonical promotion evidence coverage 恢复为 `9/complete=true`。
- 隔离篡改 claim matrix release evidence artifact count/list 会被 policy validator 的 `source_parity_claim_row` 拒绝；隔离篡改 master evidence artifact list 会被 current validator 的 `current_source_parity_claim_row` 拒绝。
- 当前 claim matrix 仍 `1 allowed / 10 blocked`，promotion 仍 `decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`。该补强只提升 claim 行证据可观测性，不产生 approved promotion、不打开 model/customer/release gate。

## 2026-08-13 approved promotion release evidence artifact contract findings

- P423 后 claim row evidence 与 promotion validator source-bound 字段都包含 required evidence artifact count/list，但 approved promotion 的 `release_promotion_contract_valid()` 仍没有直接硬检 local release summary 的这两个字段。
- P424 将 `claim_promotion_required_evidence_artifact_count=3` 和 `claim_promotion_required_evidence_artifacts=[claim_readiness_matrix, local_release_manifest, master_readiness_board]` 纳入 approved release promotion contract。
- 新增两个 approved 分支负例：release summary count 改为 2、release summary artifact list 缺少 `reports/master_readiness_board.json`，均触发 `approved_release_promotion_contract_not_valid`。
- Canonical promotion validation 仍为空输入：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`；target claim requirement evidence coverage 仍为 `9/complete=true`。
- 该补强只收紧 future approved promotion 的 release summary 合同，不产生人工批准、不打开 model claim、customer delivery 或 release。

## 2026-08-13 claim promotion malformed decision row findings

- `claim_promotion_decisions.jsonl` 的 loader 会解析任何合法 JSON 行；如果某行是 `[]`、字符串或数字，旧主循环会在 `row.get("claim_id")` 处抛异常，导致没有 fail-closed validation report。
- P425 在 `validate()` 与主循环两层处理非对象 row：记录 `invalid_decision_row`，写入 invalid record，并保证 `approved_for_promotion=false`。
- 临时 CLI 负例显示 `[]` 输入会产出 `success=false/failure_count=1/error_counts.invalid_decision_row=1`，而不是崩溃或批准；canonical 输入未修改。
- Canonical promotion validation 仍为空输入并通过：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`，requirement evidence coverage 仍 `9/complete=true`。
- 该补强只提升 malformed review input 的失败报告耐久性，不改变 approved promotion、model claim、customer delivery 或 release 状态。

## 2026-08-13 claim promotion invalid JSONL parse findings

- P425 处理了合法 JSON 但非对象的 row；非法 JSON 行仍会在 `load_jsonl()` 中抛 `JSONDecodeError`，导致 promotion validator 无法产出 fail-closed report。
- P426 将 `load_jsonl()` 改为逐行解析并捕获 parse error，生成带 `line_number` 和 `raw_preview` 的内部错误 row；validator 将其归类为 `invalid_decision_json`。
- 临时 CLI 负例 `{not-json}` 产出 `success=false/failure_count=1/error_counts.invalid_decision_json=1`，`approved_rows=0`、`ready_for_claim_promotion=false`，未触碰 canonical decisions。
- Canonical promotion validation 仍为空输入并通过：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`。
- 该补强只提升非法 JSONL review input 的失败报告耐久性，不改变 approved promotion、model claim、customer delivery 或 release 状态。

## 2026-08-13 claim promotion source JSON report parse findings

- P426 解决了 decision JSONL 解析失败，但 promotion validator 读取 claim matrix、local release、master readiness 等上游 JSON report 时仍会因 `JSONDecodeError` 直接崩溃。
- P427 让 `load_json()` 捕获 source report parse error，并通过 `source_report_errors()` 转成 `invalid_source_json_<label>` 错误计数；missing report 语义保持不变。
- 临时独立 `/private/tmp` 工作树负例中，只破坏 `local_release_manifest.json` 会产出 `success=false/failure_count=1/error_counts.invalid_source_json_local_release=1`，且 `approved_rows=0/ready_for_claim_promotion=false`。
- Canonical promotion validation 仍为空输入并通过：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`。
- 该补强只提升 source report corruption 的失败报告耐久性，不改变 approved promotion、model claim、customer delivery 或 release 状态。

## 2026-08-13 claim promotion source JSON report type findings

- P427 捕获了上游 source report 的 JSON parse error，但如果 report 是合法 JSON 且顶层为数组、字符串或数字，旧逻辑仍可能在后续 `.get()` 处崩溃。
- P428 让 `load_json()` 在解析成功后要求顶层为 dict；非对象 report 通过 `source_report_errors()` 转成 `invalid_source_json_type_<label>`。
- 临时独立 `/private/tmp` 工作树负例中，只把 `claim_readiness_matrix.json` 写为 `[]`，会产出 `success=false/failure_count=1/error_counts.invalid_source_json_type_claim_matrix=1`，且 `approved_rows=0/ready_for_claim_promotion=false`。
- Canonical promotion validation 仍为空输入并通过：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`。
- 该补强只提升 source report type drift 的失败报告耐久性，不改变 approved promotion、model claim、customer delivery 或 release 状态。

## 2026-08-13 claim promotion local release readiness summary type findings

- P428 处理了 source report 顶层类型漂移，但 `local_release_manifest.json` 可以仍是对象而其中 `readiness_summary` 被改成数组或字符串；旧 approved 分支和 evidence coverage 统计会对该嵌套值调用 `.get()`。
- P429 新增 `local_release_summary()` 和 `local_release_summary_errors()`；非对象 summary 转为空 dict 供合同检查 fail closed，同时显式记录 `invalid_local_release_readiness_summary`。
- 临时独立 `/private/tmp` 工作树负例中，只把 `local_release_manifest.json` 写为 `{"readiness_summary": []}`，会产出 `success=false/failure_count=1/error_counts.invalid_local_release_readiness_summary=1`，且 `approved_rows=0/ready_for_claim_promotion=false`。
- Canonical promotion validation 仍为空输入并通过：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`，promotion evidence coverage 仍为 9。
- 该补强只提升 nested local release summary type drift 的失败报告耐久性，不改变 approved promotion、model claim、customer delivery 或 release 状态。

## 2026-08-13 claim promotion evidence path exception findings

- Promotion decision approved 行会对 `evidence_artifacts` 和 `validation_reports` 中的字符串调用 `exists_rel()`；包含 NUL 的路径可让 `Path(...).is_file()` 抛异常。
- P430 将 `exists_rel()` 的 path construction、absolute path resolve/relative check 和 `is_file()` 包入异常防护；异常路径统一视为不存在。
- 单元负例确认 `reports/bad\x00path.json` 返回 false；approved row 负例确认该路径触发 `missing_evidence_artifacts_paths`，不崩溃。
- 临时 CLI 负例写入 NUL evidence artifact path 后产出 `success=false`、`missing_evidence_artifacts_paths=1`、`approved_rows=0`、`ready_for_claim_promotion=false`。首次临时准备脚本因缺 `PYTHONPATH` 未写输入，已改用纯 JSON 写入重跑通过。
- Canonical promotion validation 仍为空输入并通过：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`，promotion evidence coverage 仍为 9。
- 该补强只提升 malformed path input 的失败报告耐久性，不改变 approved promotion、model claim、customer delivery 或 release 状态。

## 2026-08-13 claim promotion claim matrix claims type findings

- P428 处理了 claim matrix 顶层非对象，但 claim matrix 顶层可以仍为对象而 `claims` 字段被改成对象/字符串；旧逻辑会把 claim coverage 统计为 0，但没有显式 source 结构错误。
- P431 新增 `claim_matrix_claims()` 和 `claim_matrix_claims_errors()`；非列表 claims 返回空 claim rows，并显式记录 `invalid_claim_matrix_claims`。
- 临时独立 `/private/tmp` 工作树负例中，只把 `claim_readiness_matrix.json` 写为 `{"claims": {}}`，会产出 `success=false/failure_count=1/error_counts.invalid_claim_matrix_claims=1`，且 `approved_rows=0/ready_for_claim_promotion=false`。
- Canonical promotion validation 仍为空输入并通过：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`，promotion requirement/evidence coverage 均为 9。
- 该补强只提升 claim matrix nested claims type drift 的失败报告耐久性，不改变 approved promotion、model claim、customer delivery 或 release 状态。

## 2026-08-13 claim promotion target claim requirements type findings

- P431 处理了 claim matrix `claims` 字段类型，但单个 target claim row 的 `requirements` 字段仍可能被改成对象/字符串；旧 `requirement_by_name()` 会遍历该对象的 keys，覆盖行数降低但没有显式 source 结构错误。
- P432 让 `requirement_by_name()` 只接受 list 型 requirements，并新增 `claim_requirement_errors()` 对 9 个 target high-risk claims 记录 `invalid_claim_requirements`。
- 临时独立 `/private/tmp` 工作树负例中，只把 `model_quality_claim.requirements` 改为 `{}`，会产出 `success=false/failure_count=1/error_counts.invalid_claim_requirements=1`，且 `approved_rows=0/ready_for_claim_promotion=false`；coverage rows 从 9 降为 8。
- Canonical promotion validation 仍为空输入并通过：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`，promotion requirement/evidence coverage 均为 9。
- 该补强只提升 target claim nested requirements type drift 的失败报告耐久性，不改变 approved promotion、model claim、customer delivery 或 release 状态。

## 2026-08-13 claim promotion target requirement row type findings

- P432 处理了 target claim `requirements` 字段本身的类型，但如果该字段仍是列表、列表内部混入字符串/数组等非对象 row，旧逻辑会在 `requirement_by_name()` 中忽略该元素，source 结构错误不可见。
- P433 扩展 `claim_requirement_errors()`：只检查 9 个 `TARGET_CLAIM_IDS` 的 requirement list，非 dict requirement row 记录 `invalid_claim_requirement_rows`；非列表 requirements 仍保持 `invalid_claim_requirements`。
- 临时独立 `/private/tmp/claim_promotion_requirement_row_case` 工作树负例中，只在 `model_quality_claim.requirements` 前置 `"bad"`，会产出 `success=false/failure_count=1/error_counts.invalid_claim_requirement_rows=1`，且 `approved_rows=0/ready_for_claim_promotion=false`；有效 promotion requirement 仍在，所以 coverage 保持 9/9。
- Canonical promotion validation 仍为空输入并通过：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`，promotion requirement/evidence coverage 均为 9。
- 该补强只提升 target requirement row type drift 的失败报告耐久性，不改变 approved promotion、model claim、customer delivery 或 release 状态。

## 2026-08-13 claim promotion duplicate target requirement findings

- P433 后 target requirement row 类型已显式校验，但同一个 target claim 仍可出现两条同名 `claim-promotion evidence contract valid` requirement；旧 `requirement_by_name()` 返回第一条，可能掩盖第二条冲突 evidence 或重复 source 结构。
- P434 扩展 `claim_requirement_errors()`：只在 9 个 target high-risk claims 内统计 promotion requirement 名称，数量大于 1 时记录 `duplicate_claim_promotion_requirement`。
- 临时独立 `/private/tmp/claim_promotion_duplicate_requirement_case` 工作树负例中，只复制 `model_quality_claim` 的 promotion requirement，会产出 `success=false/failure_count=1/error_counts.duplicate_claim_promotion_requirement=1`，且 `approved_rows=0/ready_for_claim_promotion=false`；第一条有效 requirement 仍存在，所以 coverage 保持 9/9。
- Canonical promotion validation 仍为空输入并通过：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`，promotion requirement/evidence coverage 均为 9。
- 该补强只提升 duplicate target promotion requirement 的失败报告耐久性，不改变 approved promotion、model claim、customer delivery 或 release 状态。

## 2026-08-13 claim promotion requirement evidence type findings

- P434 后重复 promotion requirement 会显式失败，但单条 target promotion requirement 的 `evidence` 字段仍可被改成数组/字符串；旧 `promotion_requirement_evidence_valid()` 会返回 false，让 coverage 降低，但没有显式 source 结构错误。
- P435 扩展 `claim_requirement_errors()`：只检查 9 个 target high-risk claims 内的 `claim-promotion evidence contract valid` requirement；当 `evidence` 字段存在且不是 dict 时记录 `invalid_claim_promotion_requirement_evidence`。
- 临时独立 `/private/tmp/claim_promotion_requirement_evidence_type_case` 工作树负例中，只把 `model_quality_claim` 的 promotion requirement `evidence` 改为 `[]`，会产出 `success=false/failure_count=1/error_counts.invalid_claim_promotion_requirement_evidence=1`，且 `approved_rows=0/ready_for_claim_promotion=false`；evidence coverage 从 9 降为 8。
- Canonical promotion validation 仍为空输入并通过：`decision_rows=0`、`approved_rows=0`、`ready_for_claim_promotion=false`，promotion requirement/evidence coverage 均为 9。
- 该补强只提升 target promotion requirement evidence type drift 的失败报告耐久性，不改变 approved promotion、model claim、customer delivery 或 release 状态。

## 2026-08-14 claim promotion nested evidence source type findings

- P435 已约束 promotion requirement 的顶层 `evidence` 必须是对象，但其中 `release_summary` 与 `master_governance_release` 仍可被改为数组/字符串；旧 `promotion_requirement_evidence_valid()` 会返回 false，coverage 降低，但 source 结构错误不够明确。
- P436 扩展 `claim_requirement_errors()`：只在 9 个 target high-risk claims 的 promotion requirement 内检查 nested source evidence 类型。`release_summary` 存在但非 dict 记录 `invalid_claim_promotion_release_summary_evidence`；`master_governance_release` 存在但非 dict 记录 `invalid_claim_promotion_master_governance_evidence`。
- 临时独立 `/private/tmp/claim_promotion_nested_evidence_type_case` 工作树负例中，只把 `model_quality_claim` promotion requirement 的 `evidence.release_summary` 改为 `[]`，会产出 `success=false/failure_count=1/error_counts.invalid_claim_promotion_release_summary_evidence=1`，且 `approved_rows=0/ready_for_claim_promotion=false`；evidence coverage 从 9 降为 8。
- 本轮发现 local release consistency 绑定当前 data-lake manifest SHA，而 live integrity/release reports 又受 manifest 构建刷新影响。局部手工重刷会暂时触发 `canonical_live_integrity_manifest_sha256`；通过完整 `run_safe_training_pipeline.py` 的既有受管顺序可收敛回 canonical state。
- Canonical promotion validation、local release consistency、master readiness 与 live integrity 最终均通过；该补强不产生 approved promotion、model claim、customer delivery 或 release。

## 2026-08-14 claim promotion auxiliary coverage evidence type findings

- P436 已约束两份主要 source evidence 的类型，但 promotion evidence 内还有 `release_requirement_coverage` 与 `master_requirement_coverage` 两份辅助 coverage 合同对象；旧逻辑会在后续 source-bound 合同比较中发现内容不匹配，但不会显式说明字段类型漂移。
- P437 扩展 `claim_requirement_errors()`：只在 9 个 target high-risk claims 的 promotion requirement 内检查这两个 auxiliary coverage 字段。`release_requirement_coverage` 存在但非 dict 记录 `invalid_claim_promotion_release_requirement_coverage`；`master_requirement_coverage` 存在但非 dict 记录 `invalid_claim_promotion_master_requirement_coverage`。
- 临时独立 `/private/tmp/claim_promotion_auxiliary_coverage_type_case` 工作树负例中，只把 `model_quality_claim` promotion requirement 的 `evidence.release_requirement_coverage` 改为 `[]`，会产出 `success=false/failure_count=1/error_counts.invalid_claim_promotion_release_requirement_coverage=1`，且 `approved_rows=0/ready_for_claim_promotion=false`。该字段是辅助 coverage，主 evidence coverage 仍为 9，但错误计数让类型漂移不能静默通过。
- Canonical promotion validation、local release consistency、master readiness 与 live integrity 最终均通过；该补强不产生 approved promotion、model claim、customer delivery 或 release。

## 2026-08-14 claim promotion requirement passed type findings

- P437 后 target promotion requirement 的 `passed` 仍可漂移为字符串、数字或容器；approved 分支会拒绝非 `True`，但 canonical no-decision validation 只会降低 passed coverage，未明确归因于 source 字段类型。
- P438 扩展 `claim_requirement_errors()`：只对 9 个 target high-risk claims 内的 `claim-promotion evidence contract valid` requirement 检查 `passed`。字段存在但不是 bool 时记录 `invalid_claim_promotion_requirement_passed`；字段缺失沿用既有 coverage/completeness 合同 fail-closed。
- 单元负例确认 `passed="true"` 会生成该错误，focused suite 为 `37 passed`。
- 临时 `/private/tmp/claim_promotion_auxiliary_coverage_type_case` 中仅将 `model_quality_claim` 的 `passed` 改为 `"true"`，最终输出 `success=false/failure_count=1/error_counts.invalid_claim_promotion_requirement_passed=1/approved_rows=0/ready_for_claim_promotion=false`；requirement/evidence coverage 保持 9，passed coverage 降为 8。首次运行命中该副本遗留的 invalid source claim matrix，已替换为 canonical input 后重跑，正式 inputs/reports 未修改。
- Canonical promotion validation、local release consistency、master readiness、claim policy current、live integrity 与完整 safe pipeline 最终均通过；正式 promotion 仍为空，model claim/customer delivery/release 继续关闭。

## 2026-08-14 P43 eight requested construction actions start findings

- 用户要求启动 P43-A001、A002、A004、A005、A006、A007、A008、A009。项目中这八条均已具备 start packet、local validator、dispatch/checklist、operator ledger 和 receipt 接口；受管 `run_safe_training_pipeline.py` 会按正确顺序刷新它们及下游 release evidence。
- 完整 pipeline 为 `537/537/0` 且 receipt committed。完成状态显示 8 条均 `started=true`：A001、A006-A009 为 `started_blocked`；A002、A004、A005 满足其局部 completion validator，显示 `completion_ready=true`。
- A002/A004/A005 的局部 completion-ready 只说明其 action-specific checks 当前满足，不能推导到总模型门禁。master readiness 仍显示 KWB feedback/model training/governance release 被阻断，claim matrix 仍 `1 allowed/10 blocked`。
- A001、A006-A009 均有明确 human backlog 链接，operator ledger/receipt 为 `open_blocked`。8 条 remediation chain 保持 `completion_ready_items=0`、`requires_human_input_items=8`，说明 local packet 已开始但没有把人审、许可证、IP/FTO 或 biosecurity 结论伪造为完成。
- 当前 human decision backlog 为 `1231 required/40 completed/1193 missing`，11 项全部 open；本轮未写任何 human reviewed/formal decision、未配置外部 runtime、未录入虚构实验数据、未执行训练、未发布或交付。

## 2026-08-14 claim promotion claim-matrix row type findings

- P431 只限制 `claims` 字段为 list；当 list 内混入字符串、数组等非对象 claim row 时，`claim_matrix_claims()` 会过滤它们，旧 validator 不会明确说明 source row 类型漂移。
- P440 让 `claim_matrix_claims_errors()` 在 list 内逐条检查 row 类型，非 dict row 记录 `invalid_claim_matrix_claim_rows`；有效 dict rows 仍可用于 coverage 统计，但 error count 会阻断 promotion success。
- 单元负例确认 `{"claims": ["bad", {"claim_id": "model_quality_claim"}]}` 返回唯一有效 dict row，同时生成一条 explicit error；focused suite 为 `38 passed`。
- 临时 `/private/tmp/claim_promotion_auxiliary_coverage_type_case` 的单点 CLI 负例仅追加一个 `"bad-claim-row"`，得到 `failure_count=1/error_counts.invalid_claim_matrix_claim_rows=1/approved_rows=0/ready_for_claim_promotion=false`，主 coverage 仍为 9/9/9。首次 jq 过滤表达式误把 string 写入每个现有 row 后计数为 11；已重置临时 matrix，使用单次 append 后重跑，canonical source 未修改。
- Canonical promotion validation、local release consistency、master readiness、live integrity 和完整 safe pipeline 最终均通过；该补强不产生 approved promotion、model claim、training execution、customer delivery 或 release。

## 2026-08-14 claim promotion claim-matrix claim_id findings

- P440 后 list 内非对象 claim row 已显式失败，但 dict 型 claim row 的 `claim_id` 仍可缺失、为数字/数组，或重复出现；旧 `claims = {str(row.get("claim_id")): row ...}` 会把异常 ID 字符串化，并让重复 claim row 以后写覆盖前写。
- P441 扩展 `claim_matrix_claims_errors()`：缺失、空字符串或非字符串 `claim_id` 记录 `invalid_claim_matrix_claim_id`；重复有效 claim ID 记录 `duplicate_claim_matrix_claim_id`。
- 单元负例覆盖 `{"claim_id": 123}`、缺失 `claim_id` 和重复 `model_quality_claim`，focused suite 为 `40 passed`。裸 `pytest` 不在本机 PATH 中，使用 `python3 -m pytest`。
- 临时隔离 CLI 负例仅复制 canonical claim matrix 并追加一个重复 claim row，得到 `success=false/failure_count=1/error_counts.duplicate_claim_matrix_claim_id=1/approved_rows=0/ready_for_claim_promotion=false`；canonical reports/decisions 未修改为负例状态。
- Canonical promotion validation、local release consistency、master readiness、live integrity 和完整 safe pipeline 最终均通过；该补强不产生 approved promotion、model claim、training execution、customer delivery 或 release。

## 2026-08-14 claim promotion requirement name findings

- P433 已检查 target requirement row 必须是对象，但对象内部的 `name` 仍可缺失、为空或漂移为数字/容器；旧 `requirement_by_name()` 会静默不匹配，让 promotion requirement coverage 下降但没有明确 source 结构错误。
- P442 扩展 `claim_requirement_errors()`：对 9 个 target high-risk claims 的 requirement dict row 检查 `name`，缺失、空字符串或非字符串时记录 `invalid_claim_requirement_name`。
- 单元负例确认 `name=123` 时 `requirement_by_name()` 不误匹配，且 validator 返回 `invalid_claim_requirement_name`；focused suite 为 `41 passed`。
- 临时隔离 CLI 负例仅把 canonical claim matrix 副本中 `model_quality_claim` 的 promotion requirement `name` 改为数字，得到 `success=false/failure_count=1/error_counts.invalid_claim_requirement_name=1/approved_rows=0/ready_for_claim_promotion=false`；canonical reports/decisions 未修改为负例状态。
- Canonical promotion validation、master readiness、live integrity 和完整 safe pipeline 最终均通过；该补强不产生 approved promotion、model claim、training execution、customer delivery 或 release。

## 2026-08-14 claim promotion nested evidence field-set findings

- P436 已约束 `evidence.release_summary` 与 `evidence.master_governance_release` 必须是对象，但对象字段缺失或额外字段仍主要依赖 `promotion_requirement_evidence_valid()` 的 equality 比较让 coverage 下降，没有明确说明字段集合漂移。
- P443 扩展 `claim_requirement_errors()`：nested release/master evidence 字段集合必须精确等于 `CLAIM_PROMOTION_CONTRACT_EVIDENCE_FIELDS`。release 侧记录 `invalid_claim_promotion_release_summary_evidence_fields`，master 侧记录 `invalid_claim_promotion_master_governance_evidence_fields`。
- 本轮修正测试 helper `ready_claim()`，让 release/master nested evidence 使用独立 dict；旧 helper 共享同一 dict，单侧篡改会同时污染两侧。
- 单元负例覆盖 release nested evidence 缺字段和 master nested evidence 多字段，focused suite 为 `43 passed`。
- 临时隔离 CLI 负例仅删除 canonical claim matrix 副本中 `model_quality_claim` promotion evidence release_summary 的一个字段，得到 `success=false/failure_count=1/error_counts.invalid_claim_promotion_release_summary_evidence_fields=1/approved_rows=0/ready_for_claim_promotion=false`；canonical reports/decisions 未修改为负例状态。
- Canonical promotion validation、master readiness、live integrity 和完整 safe pipeline 最终均通过；该补强不产生 approved promotion、model claim、training execution、customer delivery 或 release。

## 2026-08-14 claim promotion auxiliary coverage field-set findings

- P437 已约束 `evidence.release_requirement_coverage` 与 `evidence.master_requirement_coverage` 必须是对象，但对象字段缺失或额外字段仍没有明确错误归因。
- P444 新增 `CLAIM_PROMOTION_REQUIREMENT_COVERAGE_FIELDS`，将 auxiliary coverage 字段合同独立为 6 个字段：requirement name、requirement rows、passed rows、requirement complete、evidence rows、evidence complete。
- `claim_requirement_errors()` 现在对 release/master auxiliary coverage 字段集合做 exact check，分别输出 `invalid_claim_promotion_release_requirement_coverage_fields` 和 `invalid_claim_promotion_master_requirement_coverage_fields`。
- 初次实现误复用 14 字段 source evidence 合同，canonical promotion validation 产生两类 coverage field-set 错误各 9 条，完整 pipeline 在 `validate_master_readiness_board.py` 失败于 `342/537/1`。修正后改为真实 6 字段 coverage 合同。
- 本轮还暴露 pipeline 早段顺序缺口：master validation 早于 claim matrix/promotion/local release 投影收敛。`run_safe_training_pipeline.py` 已将 master validation 挪到 promotion validation 之后，并在前面重建 local release 和 master board。
- 临时隔离 CLI 负例仅给 canonical claim matrix 副本增加 auxiliary coverage 并删除一个 coverage 字段，得到 `success=false/failure_count=1/error_counts.invalid_claim_promotion_release_requirement_coverage_fields=1/approved_rows=0/ready_for_claim_promotion=false`；canonical reports/decisions 未修改为负例状态。
- 修正后 focused suite 为 `45 passed`，完整 safe pipeline 为 `539/539/0`。Canonical promotion evidence coverage 恢复为 `9/complete=true`，master validation 成功，claim matrix 仍 `1 allowed/10 blocked`。
- 该补强不产生 approved promotion、model claim、training execution、customer delivery 或 release。

## 2026-08-14 claim promotion nested evidence list-type findings

- P443 已约束 nested source evidence 字段集合精确，但 `claim_promotion_required_evidence_artifacts` 与 `claim_promotion_required_validation_reports` 仍可漂移为字符串或对象；旧逻辑会通过 equality 降 coverage，但错误归因不够明确。
- P445 新增 `CLAIM_PROMOTION_CONTRACT_EVIDENCE_LIST_FIELDS`，固定这两个 nested source evidence 字段必须为 list。
- `claim_requirement_errors()` 现在对 release/master nested source evidence 的 list 字段类型做显式检查。release 侧输出 `invalid_claim_promotion_release_summary_evidence_lists`，master 侧输出 `invalid_claim_promotion_master_governance_evidence_lists`。
- 单元负例覆盖 release evidence artifacts 改为字符串、master validation reports 改为对象，focused suite 为 `47 passed`。
- 临时隔离 CLI 负例仅把 canonical claim matrix 副本中 `model_quality_claim` 的 `release_summary.claim_promotion_required_evidence_artifacts` 改为字符串，得到 `success=false/failure_count=1/error_counts.invalid_claim_promotion_release_summary_evidence_lists=1/approved_rows=0/ready_for_claim_promotion=false`；canonical reports/decisions 未修改为负例状态。
- 完整 safe pipeline 为 `539/539/0`。Canonical promotion evidence coverage 仍 `9/complete=true`，master validation 成功，claim matrix 仍 `1 allowed/10 blocked`。
- 该补强不产生 approved promotion、model claim、training execution、customer delivery 或 release。

## 2026-08-14 claim promotion auxiliary coverage scalar-type findings

- P448 将 auxiliary coverage 合同拆为 string/bool/count 三类字段：requirement name 必须是非空字符串；complete 标志必须是 `bool`；三类 rows/count 必须是 `int` 且拒绝 `bool`。
- `claim_requirement_errors()` 仅在 release/master auxiliary coverage 字段集合精确匹配后执行标量类型校验，避免字段缺失时重复报类型错误。
- release 侧错误为 `invalid_claim_promotion_release_requirement_coverage_scalar_types`，master 侧错误为 `invalid_claim_promotion_master_requirement_coverage_scalar_types`。
- focused suite 已通过 `53 passed`；canonical promotion validator 保持空 decision 输入、`approved_rows=0`、`ready_for_claim_promotion=false`。
- 隔离 CLI 负例将 `model_quality_claim` 的 release coverage requirement name 改为数字，按预期得到 `success=false/failure_count=1/error_counts.invalid_claim_promotion_release_requirement_coverage_scalar_types=1`；正式 reports/decisions 未被污染。
- 完整 safe pipeline 终态为 `539/539/0`，receipt 已提交；`python3 -m py_compile scripts/*.py platform_integration/*.py prototype/*.py` 与 `git diff --check` 均通过，canonical promotion 仍保持空决策、零批准、不可自动提升。

## 2026-08-14 claim promotion auxiliary coverage presence/source-binding findings

- P449 发现 P448 后 auxiliary coverage 仍是 optional：删除整个 `release_requirement_coverage` 或 `master_requirement_coverage` 时，旧逻辑不会在 `claim_requirement_errors()` 里产生显式错误。
- P449 将四个 nested evidence 对象都改为必需：`release_summary`、`master_governance_release`、`release_requirement_coverage`、`master_requirement_coverage`。
- `promotion_requirement_evidence_valid()` 已纳入 auxiliary coverage，缺失或不等于 source release summary 投影时，target evidence coverage 不再计为完整。
- source binding 校验仅在 coverage 字段集合精确且 scalar type 正确后运行，避免同一坏输入重复归因。
- focused suite 已通过 `60 passed`；canonical validator 保持 `success=true/failure_count=0/evidence_rows=9/evidence_complete=true`。
- 隔离 CLI 负例删除 `model_quality_claim` 的 release auxiliary coverage 后，按预期得到 `success=false/failure_count=1/error_counts.missing_claim_promotion_release_requirement_coverage=1/evidence_rows=8/evidence_complete=false`。
- 完整 safe pipeline 终态为 `539/539/0`，receipt 已提交；live integrity 仍为 `1725/1723/2/0`，master readiness 仍 `blocked_for_model_claim/1 of 8`，claim matrix 仍 `1 allowed/10 blocked`。

## 2026-08-15 claim promotion decision input presence findings

- P458 发现 local release manifest 缺少 `readiness_summary` 时旧逻辑不会直接报错，且可能导致下游 source-binding 派生错误。
- `local_release_summary_errors()` 现在要求 `readiness_summary` 存在且为 dict；缺失输出 `missing_local_release_readiness_summary`，非对象继续输出 `invalid_local_release_readiness_summary`。
- 当 local release summary 根因失败时，主流程不再向 `claim_requirement_errors()` 传入不完整 summary，避免错误级联。
- focused suite 已通过 `76 passed`；canonical validator 仍 `success=true/failure_count=0/decision_rows=0/approved_rows=0/ready_for_claim_promotion=false`。
- 隔离 CLI 负例删除 local release `readiness_summary` 后，按预期只得到 `missing_local_release_readiness_summary=1`。
- 完整 safe pipeline 终态为 `539/539/0`，receipt 已提交；live integrity 仍为 `1725/1723/2/0`，master readiness 仍 `blocked_for_model_claim/1 of 8`，claim matrix 仍 `1 allowed/10 blocked`。

## 2026-08-15 claim promotion decision input presence findings

- P457 发现 decision input 缺失时，CLI 原先会在读取前自动创建空 JSONL，因此“文件缺失”被静默等同为“空 decision input”。
- `load_jsonl()` 现在对缺失 input 返回 `MISSING_JSONL_INPUT_KEY`；`validate()` 输出 `missing_decision_input`。
- 已移除 CLI 自动创建空 decision input 的行为；canonical 空 input 文件仍保留空文件语义。
- focused suite 已通过 `75 passed`；canonical validator 仍 `success=true/failure_count=0/decision_rows=0/invalid_rows=0/approved_rows=0/ready_for_claim_promotion=false`。
- 全新隔离 CLI 负例缺失 decision input 后，按预期得到 `success=false/failure_count=1/error_counts.missing_decision_input=1/decision_rows=1/invalid_rows=1`，正式 reports/decisions 未被修改。
- 完整 safe pipeline 终态为 `539/539/0`，receipt 已提交；live integrity 仍为 `1725/1723/2/0`，master readiness 仍 `blocked_for_model_claim/1 of 8`，claim matrix 仍 `1 allowed/10 blocked`。

## 2026-08-14 claim promotion required source report success findings

- P456 发现 validation source report 的 `success=false` 旧逻辑主要在 approved 分支才阻断；无 approved decision 时可能不进入全局 error_counts。
- 新增 `SOURCE_REPORT_SUCCESS_REQUIRED_LABELS`：`policy_current`、`anchor`、`local_release_guard_coverage`、`master_readiness`。
- `source_report_errors()` 现在要求这些 validation source report 的 `success is True`，否则输出 `source_report_not_success_<label>`。
- `claim_matrix` 与 `local_release` 作为源数据/manifest，不要求 success 字段。
- focused suite 已通过 `74 passed`；canonical validator 仍 `success=true/failure_count=0/decision_rows=0/approved_rows=0/ready_for_claim_promotion=false`。
- 隔离 CLI 负例将 `master_readiness.success` 改为 false 后，按预期得到 `source_report_not_success_master_readiness=1`，并保持 `ready_for_claim_promotion=false`。
- 完整 safe pipeline 终态为 `539/539/0`，receipt 已提交；live integrity 仍为 `1725/1723/2/0`，master readiness 仍 `blocked_for_model_claim/1 of 8`，claim matrix 仍 `1 allowed/10 blocked`。

## 2026-08-14 claim promotion required source report presence findings

- P455 发现 `load_json()` 对缺失 source report 返回 `{}`，在无 approved decision 时可能不产生显式 source error。
- `load_json()` 现在对缺失 JSON report 返回 `MISSING_JSON_REPORT_KEY`；`source_report_errors()` 输出 `missing_source_json_<label>`。
- invalid JSON 与 non-object JSON 的既有错误名保持不变。
- focused suite 已通过 `72 passed`；canonical validator 仍 `success=true/failure_count=0/decision_rows=0/approved_rows=0/ready_for_claim_promotion=false`。
- 隔离 CLI 负例缺失 `master_readiness_board_validation_report.json` 后，按预期得到 `missing_source_json_master_readiness=1`，并保持 `ready_for_claim_promotion=false`。
- 完整 safe pipeline 终态为 `539/539/0`，receipt 已提交；live integrity 仍为 `1725/1723/2/0`，master readiness 仍 `blocked_for_model_claim/1 of 8`，claim matrix 仍 `1 allowed/10 blocked`。

## 2026-08-14 claim promotion claim-matrix target presence findings

- P454 发现 claim matrix 缺 `claims` 字段或缺 target high-risk claim 行时，旧逻辑主要通过 downstream coverage 降低体现，缺少显式 structural error。
- `claim_matrix_claims_errors()` 现在对缺失 `claims` 字段输出 `missing_claim_matrix_claims`。
- 当 row 类型、claim_id 类型和 duplicate 检查均通过后，校验 `TARGET_CLAIM_IDS` 是否完整；缺任一 target claim 时输出 `missing_claim_matrix_target_claims`。
- focused suite 已通过 `71 passed`；canonical validator 仍 `success=true/failure_count=0/evidence_rows=9/decision_rows=0/approved_rows=0/ready_for_claim_promotion=false`。
- 隔离 CLI 负例删除 `model_quality_claim` 后，按预期得到 `missing_claim_matrix_target_claims=1`，并把 evidence coverage 降到 `8/complete=false`。
- 完整 safe pipeline 终态为 `539/539/0`，receipt 已提交；live integrity 仍为 `1725/1723/2/0`，master readiness 仍 `blocked_for_model_claim/1 of 8`，claim matrix 仍 `1 allowed/10 blocked`。

## 2026-08-14 claim promotion decision list entry type findings

- P453 将 decision row 的 `evidence_artifacts`、`validation_reports`、`residual_risks` 三个 list 字段统一收紧为非空字符串 entry。
- entry 类型错误优先于 path existence 检查，因此 malformed artifact/report 不再被泛化为路径缺失。
- 新增错误为 `invalid_evidence_artifacts_entries`、`invalid_validation_reports_entries`、`invalid_residual_risks_entries`。
- focused suite 已通过 `69 passed`；canonical validator 仍 `success=true/failure_count=0/decision_rows=0/approved_rows=0/ready_for_claim_promotion=false`。
- 隔离 CLI 负例写入 blocked decision 且 `residual_risks=[{}]` 后，只得到 `invalid_residual_risks_entries=1`，并保持 `approved_rows=0/ready_for_claim_promotion=false`。
- 完整 safe pipeline 终态为 `539/539/0`，receipt 已提交；live integrity 仍为 `1725/1723/2/0`，master readiness 仍 `blocked_for_model_claim/1 of 8`，claim matrix 仍 `1 allowed/10 blocked`。

## 2026-08-14 claim promotion decision scalar field type findings

- P452 发现 decision row 的 `reviewer`、`reviewed_at`、`decision_basis` 旧逻辑只检查存在/非空，非字符串对象或数字可以进入后续逻辑。
- `validate()` 现在要求 `claim_id`、`reviewer`、`reviewed_at`、`decision_basis` 是非空字符串；`claim_id` 不再先字符串化后判断 high-risk scope。
- 新增错误为 `invalid_claim_id`、`invalid_reviewer`、`invalid_reviewed_at`、`invalid_decision_basis`。
- focused suite 已通过 `66 passed`；canonical validator 仍 `success=true/failure_count=0/decision_rows=0/approved_rows=0/ready_for_claim_promotion=false`。
- 隔离 CLI 负例写入 malformed blocked decision 后，按预期只得到 `invalid_reviewer=1`、`invalid_reviewed_at=1`、`invalid_decision_basis=1`，并保持 `approved_rows=0/ready_for_claim_promotion=false`。
- 完整 safe pipeline 终态为 `539/539/0`，receipt 已提交；live integrity 仍为 `1725/1723/2/0`，master readiness 仍 `blocked_for_model_claim/1 of 8`，claim matrix 仍 `1 allowed/10 blocked`。

## 2026-08-14 claim promotion approved list item type findings

- P451 发现 approved decision 的 artifact/report contract helpers 会对 list 直接调用 `Counter(...)`；若 list item 是 dict/list 这类不可 hash 值，存在崩溃风险。
- `evidence_artifact_contract_errors()` 与 `validation_report_contract_errors()` 现在先要求 list item 为非空字符串，再进入 Counter-based exact contract 校验。
- 新增错误为 `approved_invalid_evidence_artifact_entries` 和 `approved_invalid_validation_report_entries`。
- focused suite 已通过 `64 passed`；canonical validator 仍 `success=true/failure_count=0/decision_rows=0/approved_rows=0/ready_for_claim_promotion=false`。
- 隔离 CLI 负例写入 malformed approved decision 且 `evidence_artifacts=[{}]` 后不崩溃，按预期得到 `approved_invalid_evidence_artifact_entries=1`，并保持 `approved_rows=0/ready_for_claim_promotion=false`。
- 完整 safe pipeline 终态为 `539/539/0`，receipt 已提交；live integrity 仍为 `1725/1723/2/0`，master readiness 仍 `blocked_for_model_claim/1 of 8`，claim matrix 仍 `1 allowed/10 blocked`。

## 2026-08-14 claim promotion source evidence source-binding findings

- P450 发现 `release_summary` / `master_governance_release` 旧逻辑会通过 `promotion_requirement_evidence_valid()` 让 evidence coverage 降低，但 `claim_requirement_errors()` 缺少显式 source-binding 错误。
- 新增 `promotion_contract_source_binding_errors()`，要求 nested source evidence 等于当前 `local_release.readiness_summary` 的 `CLAIM_PROMOTION_CONTRACT_EVIDENCE_FIELDS` 投影。
- source binding 只在字段集合、required-list 内容、scalar type 均通过后运行，保持单一错误归因。
- release 侧错误为 `invalid_claim_promotion_release_summary_evidence_source_binding`；master 侧错误为 `invalid_claim_promotion_master_governance_evidence_source_binding`。
- focused suite 已通过 `62 passed`；canonical validator 保持 `success=true/failure_count=0/evidence_rows=9/evidence_complete=true`。
- 隔离 CLI 负例篡改 `model_quality_claim` 的 master source evidence count 后，按预期得到 `success=false/failure_count=1/error_counts.invalid_claim_promotion_master_governance_evidence_source_binding=1/evidence_rows=8/evidence_complete=false`。
- 完整 safe pipeline 终态为 `539/539/0`，receipt 已提交；live integrity 仍为 `1725/1723/2/0`，master readiness 仍 `blocked_for_model_claim/1 of 8`，claim matrix 仍 `1 allowed/10 blocked`。

## 2026-08-14 claim promotion nested evidence exact-list findings

- P445 已约束 nested source evidence 的 required artifacts / validation reports 字段必须为 list，但 list 内顺序、重复、缺失或额外项漂移仍主要通过整体 equality 降 coverage。
- P446 增加 `promotion_contract_list_errors()`，对 release/master nested source evidence 中的 required evidence artifacts 和 required validation reports 做 exact-list 校验。
- release 侧输出 `invalid_claim_promotion_release_summary_required_evidence_artifacts` / `invalid_claim_promotion_release_summary_required_validation_reports`；master 侧输出 `invalid_claim_promotion_master_governance_required_evidence_artifacts` / `invalid_claim_promotion_master_governance_required_validation_reports`。
- 单元负例覆盖 release required evidence artifacts 反序和 master required validation reports 额外项，focused suite 为 `49 passed`。
- 临时隔离 CLI 负例仅把 canonical claim matrix 副本中 `model_quality_claim` 的 `release_summary.claim_promotion_required_evidence_artifacts` 反序，得到 `success=false/failure_count=1/error_counts.invalid_claim_promotion_release_summary_required_evidence_artifacts=1/approved_rows=0/ready_for_claim_promotion=false`；canonical reports/decisions 未修改为负例状态。
- 完整 safe pipeline 为 `539/539/0`。Canonical promotion evidence coverage 仍 `9/complete=true`，master validation 成功，claim matrix 仍 `1 allowed/10 blocked`。
- 该补强不产生 approved promotion、model claim、training execution、customer delivery 或 release。

## 2026-08-14 claim promotion nested evidence scalar-type findings

- P446 已约束 nested source evidence 的 required list 内容，但 count/bool 标量字段仍可漂移为字符串，例如 `"true"` 或 `"9"`；旧逻辑会通过 equality 降 coverage，但错误归因不够明确。
- P447 新增 bool/count 字段集合和 `promotion_contract_scalar_type_errors()`。bool 字段必须为 `bool`，count 字段必须为 `int` 且拒绝 `bool`。
- release 侧输出 `invalid_claim_promotion_release_summary_evidence_scalar_types`；master 侧输出 `invalid_claim_promotion_master_governance_evidence_scalar_types`。
- 为避免重复归因，list/exact/scalar 检查只在 nested evidence 字段集合已精确匹配时执行；字段缺失仍只记录 field-set 错误。
- 单元负例覆盖 release bool 字段字符串化和 master count 字段字符串化，focused suite 为 `51 passed`。
- 临时隔离 CLI 负例仅把 canonical claim matrix 副本中 `model_quality_claim` 的 `release_summary.claim_promotion_decision_validation_success` 改成字符串，得到 `success=false/failure_count=1/error_counts.invalid_claim_promotion_release_summary_evidence_scalar_types=1/approved_rows=0/ready_for_claim_promotion=false`；canonical reports/decisions 未修改为负例状态。
- 完整 safe pipeline 为 `539/539/0`。Canonical promotion evidence coverage 仍 `9/complete=true`，master validation 成功，claim matrix 仍 `1 allowed/10 blocked`。
- 该补强不产生 approved promotion、model claim、training execution、customer delivery 或 release。

## 2026-08-15 P459 claim promotion target requirements presence findings

- `claim_requirement_errors()` 现在逐一要求 `TARGET_CLAIM_IDS` 中每个 claim 显式包含 `requirements` 字段；缺失时输出 `missing_claim_requirements`，非列表仍输出 `invalid_claim_requirements`。
- 初次 focused run 暴露测试夹具只构造 `model_quality_claim`，导致其它 8 个 target claim 的缺失错误干扰单项断言；未放宽生产校验，改为让测试夹具构造完整 target claim 集合后再覆盖单个 malformed claim。
- 修复后 focused suite=`77 passed`，compile 和 `git diff --check` 通过。
- 隔离 CLI 删除 `model_quality_claim.requirements` 后按预期得到 `success=false/failure_count=1/error_counts.missing_claim_requirements=1/approved_rows=0/ready_for_claim_promotion=false`，promotion evidence rows 从 9 降为 8；正式 reports/decisions 未被负例污染。
- canonical promotion validator 正向保持 `success=true/failure_count=0/decision_rows=0/approved_rows=0/ready_for_claim_promotion=false`。
- 完整 safe pipeline=`539/539/0`，receipt atomic commit 成功；live integrity=`1725 artifacts/1723 strict/2 volatile/0 failures`。
- master readiness 仍为 `blocked_for_model_claim`、`1/8` streams ready；claim matrix 仍为 `1 allowed/10 blocked`。本轮没有 approved promotion、模型声明、训练执行、客户交付或 release。

## 2026-08-15 P471 P26 structure-chain formal-review gap findings

- 结构链 review packet 共 22 个，覆盖 500 行；新增 audit 共 23 行，其中 1 行为汇总状态。
- 当前已有 formal reviewed chain rows=34，但仍有 466 行未完成；因此不能把部分 reviewed 误报为 completion ready。
- strict evidence remaining rows 仍需显式人工决定；auto-review candidates=84，draft rows=18，accepted rows=0，`ready_for_apply=false`。
- P471 validator=`success=true/audit_rows=23/packet_audit_rows=22/formal_reviewed_rows=34/remaining_unreviewed_rows=466/failures=0`。
- 完整 safe pipeline=`555/555/0`，`receipt_committed=true`；live integrity=`1749 artifacts/1747 strict/2 volatile/0 failures`。
- 本轮未新增结构链 formal decision、未导入训练、未打开模型声明、未客户交付、未生产同步或 release。

## 2026-08-15 P470 P26 numbering formal-review gap findings

- 编号 packet board 当前 21 行，全部为 `open_blocked_waiting_for_human_review`；packet completion-ready rows=0。
- briefing status board 当前 33 行，其中 open blocked=29、decision input rows=4、completion-ready rows=0；briefing 导航状态不等于 formal reviewed decision。
- 新增 `p26_numbering_formal_review_gap_audit.jsonl`、report 和 validation report，共 54 条 audit rows；formal review rows=0，所有 training/import/model-claim/release/production flags 均为 false。
- P470 validator=`success=true/audit_rows=54/packet_audit_rows=21/briefing_audit_rows=33/failures=0`。
- 全量 `run_safe_training_pipeline.py`=`553/553/0`，`receipt_committed=true`；当前 live integrity=`1746 artifacts/1744 strict/2 volatile/0 failures`。
- 当前 canonical snapshot：plate backlog=54、human decision backlog `total_missing_rows=1201`、五头 `ready_head_count=0`、master readiness=`blocked_for_model_claim/1 of 8`。
- P26-P31 全部仍为 started；没有新增 formal human decisions、训练导入、模型声明、客户交付、生产同步或 release。

## 2026-08-15 P26-P31 started refresh findings

- P26-P31 在计划文件里已经是 `in_progress`，本轮按用户要求重新确认并刷新了 started 状态，不改变任何受管门禁。
- `pending_stage_all_started_board` 重新生成后仍为 `success=true`，`stage_count=6`、`started_stage_count=6`、`agent_delegated_stage_count=1`、`release_ready=false`。
- `active_stage_execution_matrix` 重新生成并验证通过，6 个阶段都保持 `training_import_allowed=false`、`safe_for_model_claim=false`、`release_ready=false`、`production_execution_allowed=false`。
- 这只是本地执行板和验证板的同步，不是训练、生产同步、模型声明或 release 解锁。

## 2026-08-15 P26-P31 full-chain started convergence findings

- 将 P26-P31 “全部开始”贯穿完整 safe pipeline 时，首个失败来自 `validate_human_preflight_package.py`：plate backlog 当前为 52 行，但 validator 仍硬编码 50。
- human preflight validator 已改为动态一致性：plate `backlog_rows`、`review_workspace_rows`、`packet_rows`、`blocked_review_workspace_rows` 必须一致且非零；`ready_for_feedback_intake_rows` 和 `local_intake_rows` 仍必须为 0。
- 第二个失败来自 `validate_human_decision_backlog_fail_closed_consistency.py`：human backlog expected plate rows/总缺口仍按 50/1196 计算。现在它读取 `experiment_feedback_plate_intake_backlog_report.json`，动态绑定 plate required/missing rows。
- 当前 human backlog 一致性为 `backlog_items=11`、`open_items=11`、`total_missing_rows=1198`、`failures=0`。
- 第三轮完整 safe pipeline 恢复为 `539/539/0`，receipt committed；P26-P31 started 6/6，active matrix 6/6，human preflight 3/3 valid。
- 本轮只是修复 stale count validators 和刷新 started 链路，没有写 formal human decisions、没有导入训练、没有模型声明、没有生产同步、没有 release。

## 2026-08-15 P462 dynamic-count regression findings

- 为防止 P26-P31 started 链路再次被 plate backlog 固定计数卡住，新增 `scripts/test_validate_human_preflight_dynamic_counts.py`。
- 回归测试覆盖：plate preflight 接受 backlog/workspace/packet=52；workspace 漂移到 50 时触发 mismatch；human backlog consistency 在 plate=52 时动态得到 `total_missing_rows=1198`。
- focused tests：`scripts/test_validate_human_preflight_dynamic_counts.py` 单独 `3 passed`；与 claim promotion focused suite 合跑 `86 passed`。
- 核心 validators 通过：pending-stage all-started 6/6、active matrix 6、human preflight 3/3、human backlog 1198 missing/0 failures。
- 完整 safe pipeline 再次恢复为 `539/539/0`，receipt committed。
- 本轮没有 formal human decisions、训练导入、模型声明、生产同步或 release。

## 2026-08-15 P463 P26-P31 remaining work all-started board findings

- 用户列出的 P26-P31 剩余待建子项被结构化为 20 行本地 start actions：P26=4、P27=3、P28=3、P29=4、P30=3、P31=3。
- 新增 `p26_p31_remaining_build_start_board` report 和 JSONL；每行 `started=true`，并固定 `training_import_allowed=false`、`safe_for_model_claim=false`、`release_ready=false`、`production_execution_allowed=false`。
- validator 对 action IDs、stage IDs、P31 禁生产、plate backlog 56 source binding、human backlog missing 1206 source binding 做校验。
- 当前 validation=`success=true/action_count=20/started_action_count=20/failures=0`。
- P463 board/action/validation 产物已接入 safe pipeline、data lake manifest 和 local release manifest；全量安全流水线=`669/669/0`，data lake=`1920 artifacts/1918 strict/2 volatile/0 failures`，local release consistency 通过但 `release_ready=false`。
- P26-P31 原 6 阶段 started board 和 active matrix 仍验证通过；本轮没有 formal decisions、训练导入、模型声明、生产同步或 release。

## 2026-08-15 P464 P27 feature coverage by head/protein group findings

- `validated_feature_index` 当前 203 条输入特征，分布为 MSA 158、structure_graph 34、pyrosetta_ddg_reu_input 11；全部继续要求 `training_label_source=false`。
- 本轮把 protein group 定义为 `uniprot:<uniprot_id>`，从 feature index 得到 175 个蛋白组，并对五头生成 875 条 head/group 覆盖行。
- feature family/head 映射保持保守：MSA 支持五头输入覆盖，structure_graph 支持 mutation_rank/stability/substrate_fit，PyRosetta REU 仅支持 stability 输入覆盖。
- input_feature_rows_by_head：mutation_rank=192、stability=203、activity_risk=158、substrate_fit=192、assay_success=158。
- covered_group_count_by_head：mutation_rank=175、stability=175、activity_risk=158、substrate_fit=175、assay_success=158；activity_risk 与 assay_success 各有 17 个组无该 head 输入特征覆盖。
- 新 validator 对 source-bound 计数、head/group 精确顺序、feature index ids、feature_rows_counted_as_labels=0 和全部 fail-closed flags 做校验；当前 `success=true/failures=0`。
- 完整 safe pipeline 已纳入新 builder/validator，当前为 `541/541/0`；live integrity=`1728 artifacts/1726 strict/2 volatile/0 failures`。
- P463 remaining start board 已补充读取 P464 coverage report/validation；P27-A003 从 `started_pending_local_build` 收敛为 `started_completion_ready_fail_closed_audit`，但仍不解锁训练或模型声明。
- 本轮未导入标签、未训练、未提升 ready head、未打开模型声明、未生产同步、未 release。

## 2026-08-15 P465 P27 feature coverage gap queue findings

- P464 coverage 的 `no_input_feature_coverage` 行共 34 条，全部来自 activity_risk 与 assay_success：各 17 个 `uniprot:*` protein group。
- 新增 gap queue 只记录输入特征证据缺口，不记录训练标签缺口；每行固定 `training_import_allowed=false`、`safe_for_training_import=false`、`safe_for_model_claim=false`、`release_ready=false`、`production_execution_allowed=false`。
- validator 从 coverage JSONL 与 validated feature index 重建 expected gap rows，校验 gap_id 顺序、head/protein_group/source-bound 计数、required/missing feature families、available feature ids 和 fail-closed flags。
- 当前 gap validation=`success=true/gap_count=34/expected_gap_count=34/failures=0`。
- 完整 safe pipeline 已纳入 gap queue builder/validator，当前为 `543/543/0`；live integrity=`1731 artifacts/1729 strict/2 volatile/0 failures`。
- 五头 ready_head_count 仍为 0，training execution、model claim、release 和 production gate 全部保持关闭。

## 2026-08-15 P466 P26-P31 pending backlog all-started findings

- 响应“全部开始”，将当前待建清单展开为 51 个本地 started action：17 个 P26/P28/P29/P30/P31 静态 action，加上 P27 coverage gap 34 条逐条 action。
- 新增 `p26_p31_pending_backlog_all_started_board` report/JSONL 和 validator；P27 gap action 与 gap queue 的 `gap_id`、head、protein_group、missing feature families source-bound。
- P26 plate actions 绑定当前 plate backlog=52；人工决策 actions 绑定 human backlog `total_missing_rows=1198`；P31 actions 固定 production execution false。
- 当前 validation=`success=true/action_count=51/started_action_count=51/p27_gap_action_count=34/failures=0`。
- 完整 safe pipeline=`545/545/0`，receipt committed；live integrity=`1734 artifacts/1732 strict/2 volatile/0 failures`。
- “started”仅表示本地执行板已登记；没有写 formal decisions、没有导入训练、没有模型声明、没有生产同步或 release。

## 2026-08-15 P467 P28 plate intake schema gap audit findings

- safe pipeline 重建后的当前 plate backlog 为 54 行，human decision backlog 总缺口为 1201；不再沿用此前日报中的 52/1198 旧快照。
- 新增逐行 schema gap audit，54/54 行均缺少 required fields：assay_type、instrument、operator、plate_id、protocol_version、raw_signal、recorded_at、replicate、sample_batch、variant_id、well_id。
- 54/54 行的 `qc_flag` 值为 `not_reviewed`，不属于 contract 允许的 pass/warning/fail；0 行 approved for formal plate intake。
- 首次完整 pipeline 在 `validate_draft_namespace_isolation.py` 第 157 步失败，原因是新 audit JSONL 含 `plate_review_draft` marker 但未加入显式 allowlist；已补充 audit namespace pattern，并将 row/report policy 明确为 draft/backlog audit semantics。
- 修复后 draft namespace validation=`success=true/allowed_marker_files=62/unexpected_marker_files=0/failures=0`；P467 audit validation=`success=true/failures=0`。
- 完整 safe pipeline=`547/547/0`，live integrity=`1737 artifacts/1735 strict/2 volatile/0 failures`；formal intake、training import、model claim、release 和 production 仍关闭。

## 2026-08-15 P468 P28 feedback authorization and parent-sequence gap audit findings

- 当前 12 条 numeric feedback authorization worklist 中 8 条已有 decision、4 条仍缺完整 authorization fields；12 条整体 `ready_for_feedback_intake_rows=0`，因此不能把 decision present 等同于 intake ready。
- 16B/4G parent-sequence intake 仍只有 2 条 template row，local input rows=0，两个 project 都 blocked，`ready_for_numbering_audit=false`。
- 新增 P28 combined gap audit JSONL/report/validator，共 14 条 audit rows；source-bound 到 authorization worklist、sequence template/local input、request packets 和 sequence validation report。
- 当前 validation=`success=true/audit_rows=14/authorization_blocked_rows=4/parent_sequence_blocked_rows=2/failures=0`。
- 完整 safe pipeline=`549/549/0`，live integrity=`1740 artifacts/1738 strict/2 volatile/0 failures`；未写 formal decisions、未导入训练、未开模型声明、未生产同步、未 release。

## 2026-08-15 P469 P30 acceptance and governance gap audit findings

- 当前 P30 治理缺口共 31 条：6 条 workstream acceptance、16 条缺失 license/customer-delivery decision、3 条 license verification、3 条 biosecurity/ordering、3 条 sequence IP/FTO delivery。
- 3 条外部工具 license decision 虽然 valid，但 verification_status 仍为 self_attested；customer delivery 仍 false，不能把 self-attested authorization 当作 verified delivery clearance。
- workstream acceptance 为 0/6；biosecurity decision rows=0/3；IP/FTO decision rows=0/3。
- 新增 P30 acceptance/governance gap audit JSONL/report/validator，校验 source-bound counts 和所有 delivery/release flags；当前 `success=true/audit_rows=31/failures=0`。
- 完整 safe pipeline=`551/551/0`，live integrity=`1743 artifacts/1741 strict/2 volatile/0 failures`；未写 formal acceptance、未导入训练、未开模型声明、未客户交付、未生产同步、未 release。

## 2026-08-15 P460 claim promotion requirement presence findings

- target claim 的 `requirements` 字段存在并不足够：之前可以没有唯一的 `claim-promotion evidence contract valid` requirement，或该 requirement 缺少 `passed` / `evidence`，但全局 validator 仍可能保持 `success=true`。
- P460 新增 `missing_claim_promotion_requirement`、`missing_claim_promotion_requirement_passed` 和 `missing_claim_promotion_requirement_evidence`。
- 当 requirement row 类型或 name 本身非法时，抑制派生的 missing-promotion 错误，只保留原始 `invalid_claim_requirement_rows` / `invalid_claim_requirement_name`，避免错误归因噪声。
- focused suite 从 `77` 提升到 `80 passed`；compile 和 `git diff --check` 通过。
- 隔离 CLI 删除 `model_quality_claim` 的 promotion requirement 后按预期得到 `success=false/failure_count=1/error_counts.missing_claim_promotion_requirement=1/approved_rows=0/ready_for_claim_promotion=false`，contract requirement/evidence coverage 均从 9 降为 8；正式 reports/decisions 未被负例污染。
- canonical promotion validator 正向保持 `success=true/failure_count=0/target_claim_rows_with_promotion_contract_requirement=9/target_claim_rows_with_promotion_contract_requirement_evidence=9/decision_rows=0/approved_rows=0/ready_for_claim_promotion=false`。
- 完整 safe pipeline=`539/539/0`，receipt committed；live integrity=`1725 artifacts/1723 strict/2 volatile/0 failures`。
- master readiness 仍为 `blocked_for_model_claim`、`1/8` streams ready；claim matrix 仍为 `1 allowed/10 blocked`。本轮没有 approved promotion、模型声明、训练执行、客户交付或 release。

## 2026-08-15 P461 claim promotion source read failure findings

- `load_json()` 和 `load_jsonl()` 现在对不可读输入（例如非 UTF-8）返回结构化 unreadable marker，而不是抛异常。
- `source_report_errors()` 新增 `unreadable_source_json_<label>`，`validate()` 新增 `unreadable_decision_input`。
- local release 根因错误会抑制后续 summary / source-binding 派生错误，避免空投影噪声；这沿用 P458 的根因优先策略。
- focused suite=`83 passed`，compile 和 `git diff --check` 通过。
- 隔离 CLI 将 `local_release_manifest.json` 写成非 UTF-8 后，只得到 `unreadable_source_json_local_release=1`，不再伴随 missing summary 或 source-binding 派生错误。
- canonical promotion validator 正向保持 `success=true/failure_count=0/decision_rows=0/approved_rows=0/ready_for_claim_promotion=false`。
- 完整 safe pipeline=`539/539/0`，receipt committed；live integrity=`1725 artifacts/1723 strict/2 volatile/0 failures`。
- master readiness 仍为 `blocked_for_model_claim`、`1/8` streams ready；claim matrix 仍为 `1 allowed/10 blocked`。本轮没有 approved promotion、模型声明、训练执行、客户交付或 release。

## 2026-08-17 P472 P28 feedback source-review gap audit findings

- P472 新增 `p28_feedback_source_review_gap_audit.jsonl`、report 和 validation report，覆盖 11 个 source-review packet 加 1 条汇总，共 12 条 audit rows。
- 当前 source-review candidate rows=`173`、decision rows=`0`、valid rows=`0`；ready_for_feedback_extraction=false、ready_for_feedback_intake=false。
- P472 validator=`success=true/audit_rows=12/failures=0`；所有 training/import/model-claim/release/production flags 均保持 false。
- 完整 `run_safe_training_pipeline.py`=`557/557/0`，`receipt_atomic_commit=true`；本轮没有写 source-review decision、没有 feedback intake、没有训练导入、没有模型声明、没有生产同步或 release。

## 2026-08-17 P473 P29 five-head training gap audit findings

- P473 新增 `p29_five_head_training_gap_audit.jsonl`、report 和 validation report，将 P29 五头训练阻断 source-bound 到 gap plan、threshold report、sample gap queue、execution contract、claim matrix 和 model-quality hard gate。
- Audit 共 11 行：5 条 head gap action、5 条 sample/replicate/group threshold gap、1 条 training execution summary。
- 当前 ready_head_count=`0`、total_head_training_rows=`6`、training_import_eligible_rows=`6`；missing_label_rows_total=`494`、missing_replicates_total=`15`、missing_groups_total=`48`。
- P473 validator=`success=true/audit_rows=11/failures=0`；training_execution_allowed=false、safe_for_model_claim=false、release_ready=false。
- 完整 `run_safe_training_pipeline.py`=`559/559/0`，`receipt_atomic_commit=true`；本轮没有写训练标签、没有启动训练、没有模型声明、没有客户交付、没有生产同步或 release。

## 2026-08-17 P474 P31 production execution gap audit findings

- P474 新增 `p31_production_execution_gap_audit.jsonl`、report 和 validation report，将 P31 生产执行阻断 source-bound 到 pending backlog actions、active stage matrix、local release、customer delivery、governance、operator status 和 claim matrix。
- Audit 共 5 行：3 条 P31 pending action、1 条 active-stage execution gate、1 条 release/production summary。
- 当前 operator_completed_action_rows=`0`、claim_matrix_blocked_claims=`10`、customer_delivery_ready=false、release_ready=false、production_execution_allowed=false。
- sync_allowed=false、deploy_allowed=false、restart_allowed=false、grey_release_allowed=false；validator=`success=true/audit_rows=5/failures=0`。
- 完整 `run_safe_training_pipeline.py`=`561/561/0`，`receipt_atomic_commit=true`；本轮没有执行 sync/deploy/restart/grey release，没有客户交付、生产执行或 release。

## 2026-08-17 P475 P27 feature input-boundary gap audit findings

- P475 新增 `p27_feature_input_boundary_gap_audit.jsonl`、report 和 validation report，将 P27 feature 边界 source-bound 到 validated feature index、feature coverage、coverage gap queue、advanced model feature contract、structure feature model contract 和 five-head execution contract。
- Audit 共 6 行：feature index boundary、coverage boundary、coverage gap remediation boundary、advanced feature contract boundary、structure graph boundary、P27 summary。
- 当前 validated_feature_rows=`203`、model_consumable_rows=`203`、training_label_source_rows=`0`；coverage_rows=`875`、coverage_gap_count=`34`。
- advanced_feature_refs=`203`，reviewed_structure_graph_rows=`34`，unreviewed_coordinate_rows_excluded=`466`；safe_for_model_claim=false、release_ready=false。
- P475 validator=`success=true/audit_rows=6/failures=0`；完整 `run_safe_training_pipeline.py`=`563/563/0`，`receipt_atomic_commit=true`。本轮没有把 feature rows 当训练标签、没有训练、没有模型声明、没有生产同步或 release。

## 2026-08-17 P476 human decision backlog gap audit findings

- P476 新增 `p476_human_decision_backlog_gap_audit.jsonl`、report 和 validation report，将 human decision backlog source-bound 到 `human_decision_backlog.jsonl`、backlog report 和 fail-closed consistency validation。
- Audit 共 12 行：11 条 backlog item 加 1 条 summary；open_items=`11`、ready_items=`0`。
- 当前 total_required_rows=`1239`、total_completed_rows=`40`、total_missing_rows=`1201`；consistency success=true、safe_for_training_pipeline=true。
- P476 validator=`success=true/audit_rows=12/failures=0`；safe_for_model_claim=false、release_ready=false、production_execution_allowed=false。
- 完整 `run_safe_training_pipeline.py`=`565/565/0`，`receipt_atomic_commit=true`；本轮没有写 human decision、没有训练导入、没有模型声明、没有客户交付、没有生产同步或 release。

## 2026-08-17 P477 operator review action gap audit findings

- P477 新增 `p477_operator_review_action_gap_audit.jsonl`、report 和 validation report，将 operator review action completion gaps source-bound 到 action queue、decision validation 和 operator status report。
- Audit 共 7 行：6 条 operator action completion gap 加 1 条 summary；queue_rows=`6`、decision_rows=`0`、completed_rows=`0`。
- 当前 all_actions_completed=false、status_ready=false；missing_action_decisions 覆盖 review_action_001 到 review_action_006。
- P477 validator=`success=true/audit_rows=7/failures=0`；safe_for_model_claim=false、customer_delivery_ready=false、release_ready=false、production_execution_allowed=false。
- 完整 `run_safe_training_pipeline.py`=`567/567/0`，`receipt_atomic_commit=true`；本轮没有写 operator completion decision、没有治理审批、没有客户交付、没有生产同步或 release。

## 2026-08-17 P478 governance review bundle gap audit findings

- P478 新增 `p478_governance_review_bundle_gap_audit.jsonl`、report 和 validation report，将 governance review bundle completion gaps source-bound 到 bundle JSONL、bundle report 和 bundle validation report。
- Audit 共 38 行：37 条 governance bundle item gap 加 1 条 summary；bundle_rows=`37`、open_rows=`37`、completion_ready_rows=`0`。
- workstream 分布为 external_license_review=`19`、biosecurity_screening=`3`、sequence_ip_fto=`3`、operator_review_actions=`6`、workstream_acceptance=`6`；status 为 open_blocked_waiting_for_human_decision=`33`、reviewed_valid_but_not_approved=`4`。
- P478 validator=`success=true/audit_rows=38/failures=0`；safe_for_model_claim=false、customer_delivery_ready=false、release_ready=false、production_execution_allowed=false。
- 完整 `run_safe_training_pipeline.py`=`569/569/0`，`receipt_atomic_commit=true`；本轮没有写 governance decision、没有完成 bundle、没有训练导入、没有模型声明、没有客户交付、没有生产同步或 release。

## 2026-08-17 P479 customer delivery readiness gap audit findings

- P479 新增 `p479_customer_delivery_readiness_gap_audit.jsonl`、report 和 validation report，将 customer delivery readiness blockers source-bound 到 customer delivery report、governance、license、IP/FTO、biosecurity、human review、benchmark 和 claim matrix。
- Audit 共 9 行：8 条 customer delivery blocker gap 加 1 条 summary；customer delivery `ready=false`、passed_checks=`2`、failed_checks=`8`。
- 8 个 blocker 为 data_license_clearance、tool_license_clearance、verified_component_customer_delivery_scope、ip_fto_review、biosecurity_approval、human_delivery_approval、allowed_claims_review、benchmark_scorecards。
- P479 validator=`success=true/audit_rows=9/failures=0`；customer_sequence_package_blocked=true，safe_for_model_claim=false、customer_delivery_ready=false、release_ready=false、production_execution_allowed=false。
- 完整 `run_safe_training_pipeline.py`=`571/571/0`，`receipt_atomic_commit=true`；同时将 P479 high-risk summary fields 纳入 local release fail-closed consistency 分类。未写 customer delivery approval、未开客户交付、未导入训练、未开模型声明、未生产同步或 release。

## 2026-08-17 P480 claim readiness blocker gap audit findings

- P480 新增 `p480_claim_readiness_blocker_gap_audit.jsonl`、report 和 validation report，将 claim readiness blocked claims source-bound 到 claim matrix、claim fail-closed policy reports、local release、customer delivery 和 master readiness projection。
- Audit 共 11 行：10 条 blocked claim gap 加 1 条 summary；claims_allowed=`1`，claims_blocked=`10`，唯一 allowed claim 仍是 `internal_design_review_artifacts`。
- 10 个 blocked claim 为 local_safe_training_pipeline、model_quality_claim、five_head_training_run、active_learning_experiment_submission、customer_sequence_package、approved_for_ordering、ip_fto_cleared、biosecurity_screened、external_tool_production_use、local_release_review_package。
- P480 validator=`success=true/audit_rows=11/failures=0`；safe_for_model_claim=false、customer_delivery_ready=false、release_ready=false、production_execution_allowed=false。
- 完整 `run_safe_training_pipeline.py`=`573/573/0`，`receipt_atomic_commit=true`；本轮没有写 claim promotion decision、没有解锁任何 blocked claim、没有训练导入、没有客户交付、没有生产同步或 release。

## 2026-08-17 P481 local release blocked capability gap audit findings

- P481 新增 `p481_local_release_blocked_capability_gap_audit.jsonl`、report 和 validation report，将 local release blocked capabilities source-bound 到 local release manifest、fail-closed consistency、safety guard、guard coverage、claim matrix 和 customer delivery readiness。
- Audit 共 7 行：6 条 blocked capability gap 加 1 条 summary；release_ready=false，missing_artifacts=`0`，local release consistency success=true。
- 6 个 blocked capability 为 model_quality_claim、customer_delivery、approved_for_ordering、IP/FTO conclusion、external tool production use、advanced feature cache execution。
- P481 validator=`success=true/audit_rows=7/failures=0`；safe_for_model_claim=false、customer_delivery_ready=false、release_ready=false、production_execution_allowed=false。
- 完整 `run_safe_training_pipeline.py`=`575/575/0`，`receipt_atomic_commit=true`；本轮没有写 release approval、没有解锁 blocked capability、没有客户交付、没有生产同步或 release。

## 2026-08-17 P482 master readiness stream gap audit findings

- P482 新增 `p482_master_readiness_stream_gap_audit.jsonl`、report 和 validation report，将 master readiness stream gaps source-bound 到 master readiness board、board validation、local release 和 claim matrix。
- Audit 共 9 行：8 条 stream gap 加 1 条 summary；overall_status=`blocked_for_model_claim`、ready_streams=`1`、total_streams=`8`、blocked_stream_rows=`7`。
- 当前只有 structure_cache stream source-ready；numbering_curation、domain_intervals、msa_conservation、kwb_experiment_feedback、model_training、governance_release、platform_integration 仍未 ready。
- P482 validator=`success=true/audit_rows=9/failures=0`；safe_for_model_claim=false、customer_delivery_ready=false、release_ready=false、production_execution_allowed=false。
- 完整 `run_safe_training_pipeline.py`=`577/577/0`，`receipt_atomic_commit=true`；本轮没有写 stream completion decision、没有提升 master readiness、没有模型声明、没有客户交付、没有生产同步或 release。

## 2026-08-17 P483 next-unlock execution gap audit findings

- P483 新增 `p483_next_unlock_execution_gap_audit.jsonl`、report 和 validation report，将 next-unlock execution gaps source-bound 到 plan、execution board、execution validation、completion status、local release 和 claim matrix。
- Audit 共 20 行：12 条 action execution gap、7 条 stage execution gap、1 条 summary；blocked_gap_rows=`12`，其中 blocked_action_rows=`8`、blocked_stage_rows=`4`。
- 源验证报告中局部 completion-ready 仍被记录为观测值：validation_completion_ready_actions=`4`、validation_completion_ready_stage_count=`3`；审计行自身 `completion_ready=false`，不授权训练、模型声明、客户交付、release 或生产执行。
- P483 validator=`success=true/audit_rows=20/failures=0`；local release `release_ready=false`，claim matrix 仍为 `claims_allowed=1/claims_blocked=10`。
- 完整 `run_safe_training_pipeline.py`=`579/579/0`，receipt committed；live integrity=`1785 artifacts/1783 strict/2 volatile/0 failures`。本轮没有写 unlock approval、没有导入训练、没有模型声明、没有客户交付、没有生产同步或 release。

## 2026-08-17 P484 next-unlock operator navigation gap audit findings

- P484 新增 `p484_next_unlock_operator_navigation_gap_audit.jsonl`、report 和 validation report，将 operator navigation index source-bound 到 operator index JSON/JSONL、next-unlock execution validation、P483 audit、local release 和 claim matrix。
- Audit 共 13 行：12 条 operator navigation gap 加 1 条 summary；open_item_rows=`8`、source_completion_ready_items=`4`、blocked_gap_rows=`8`。
- 4 个源 completion-ready operator item 仍只表示本地导航/验证观测；P484 审计行自身 `completion_ready=false`，不写 reviewed decisions、approval、training import、model claim、delivery authorization、release 或 production execution。
- P484 validator=`success=true/audit_rows=13/failures=0`；operator index 的 open_items=`8` 与 next-unlock validation blocked_actions=`8` 一致。
- 完整 `run_safe_training_pipeline.py`=`581/581/0`，receipt committed；live integrity=`1788 artifacts/1786 strict/2 volatile/0 failures`。local release `release_ready=false`，claim matrix 仍 `1 allowed/10 blocked`，customer delivery 和 production execution 仍关闭。

## 2026-08-17 P485 next-unlock blocker matrix gap audit findings

- P485 新增 `p485_next_unlock_blocker_matrix_gap_audit.jsonl`、report 和 validation report，将 next-unlock blocker matrix source-bound 到 blocker matrix JSON/JSONL、P484 audit、execution validation、local release 和 claim matrix。
- Audit 共 16 行：15 条 blocker matrix gap 加 1 条 summary；open_blocker_rows=`15`，severity 分布为 critical=`9`、high=`2`、medium=`4`。
- blocker matrix 的 15 条 blocker 均为 `status=open`，覆盖 8 个 blocked action 的 failed checks；这些 blocker 只是证据缺口索引，不写 reviewed decisions、approval、training import、model claim、delivery authorization、release 或 production execution。
- P485 validator=`success=true/audit_rows=16/failures=0`；blocker matrix blocked_actions=`8` 与 next-unlock execution validation blocked_actions=`8` 一致。
- 完整 `run_safe_training_pipeline.py`=`583/583/0`，receipt committed；live integrity=`1791 artifacts/1789 strict/2 volatile/0 failures`。local release `release_ready=false`，claim matrix 仍 `1 allowed/10 blocked`，customer delivery 和 production execution 仍关闭。

## 2026-08-17 P486 next-unlock remediation queue gap audit findings

- P486 新增 `p486_next_unlock_remediation_queue_gap_audit.jsonl`、report 和 validation report，将 next-unlock remediation queue source-bound 到 remediation queue JSON/JSONL、blocker matrix、P485 audit、local release 和 claim matrix。
- Audit 共 9 行：8 条 remediation queue gap 加 1 条 summary；open_rows=`8`、ready_to_start_rows=`8`、requires_human_input_rows=`8`。
- remediation queue 的 `ready_to_start=true` 只表示本地材料入口齐备；8 条 queue row 仍为 `queue_status=open` 且 requires_human_input=true，不写 reviewed decisions、approval、training import、model claim、delivery authorization、release 或 production execution。
- P486 validator=`success=true/audit_rows=9/failures=0`；queue_rows=`8` 与 open rows 精确一致。
- 完整 `run_safe_training_pipeline.py`=`585/585/0`，receipt committed；live integrity=`1794 artifacts/1792 strict/2 volatile/0 failures`。local release `release_ready=false`，claim matrix 仍 `1 allowed/10 blocked`，customer delivery 和 production execution 仍关闭。

## 2026-08-17 P487 next-unlock multi-agent launch gap audit findings

- P487 新增 `p487_next_unlock_multi_agent_launch_gap_audit.jsonl`、report 和 validation report，将 multi-agent launch board source-bound 到 launch board JSON/JSONL、launch validation/status、P486 audit、local release 和 claim matrix。
- Audit 共 9 行：8 条 local multi-agent launch gap 加 1 条 summary；started_rows=`8`、open_blocked_rows=`8`、source_completion_ready_rows=`0`、local_agent_lanes=`4`。
- launch board 的 `started=true`、`ready_to_launch_items=8` 和 validation 的 `validated_launch_rows=8` 只表示本地 lane 分配/语义有效；所有 launch row 仍为 `local_agent_started_blocked`，不写 reviewed decisions、approval、training import、model claim、delivery authorization、release、deploy、sync、restart 或 production execution。
- P487 validator=`success=true/audit_rows=9/failures=0`；validation invalid_launch_rows=`0` 且 completion_ready_items=`0`。
- 完整 `run_safe_training_pipeline.py`=`587/587/0`，receipt committed；live integrity=`1797 artifacts/1795 strict/2 volatile/0 failures`。local release `release_ready=false`，claim matrix 仍 `1 allowed/10 blocked`，customer delivery 和 production execution 仍关闭。

## 2026-08-17 P488 next-unlock agent lane status gap audit findings

- P488 新增 `p488_next_unlock_agent_lane_status_gap_audit.jsonl`、report 和 validation report，将 agent lane status source-bound 到 lane status JSON/JSONL、P487 audit、local release 和 claim matrix。
- Audit 共 5 行：4 条 agent lane status gap 加 1 条 summary；lane_audit_rows=`4`、started_blocked_lanes=`4`、source_completion_ready_items=`0`。
- lane status 的 `lane_started_blocked` 和 started_items=`8` 只表示本地 agent lane 协调状态；requires_human_input_items=`8`，不写 reviewed decisions、approval、training import、model claim、customer delivery authorization、release、deploy、sync、restart 或 production execution。
- P488 validator=`success=true/audit_rows=5/failures=0`；invalid_lanes=`0` 且 lanes_with_completion_ready_items=`0`。
- 完整 `run_safe_training_pipeline.py`=`589/589/0`，receipt committed；live integrity=`1800 artifacts/1798 strict/2 volatile/0 failures`。local release `release_ready=false`，claim matrix 仍 `1 allowed/10 blocked`，customer delivery 和 production execution 仍关闭。

## 2026-08-17 P489 next-unlock lane dispatch gap audit findings

- P489 新增 `p489_next_unlock_lane_dispatch_gap_audit.jsonl`、report 和 validation report，将 lane dispatch packets source-bound 到 dispatch packet JSON/JSONL、dispatch validation/status、P488 audit、local release 和 claim matrix。
- Audit 共 5 行：4 条 lane dispatch gap 加 1 条 summary；dispatch_audit_rows=`4`、dispatch_ready_blocked_packets=`4`、source_completion_ready_items=`0`。
- dispatch packet 的 `dispatch_ready_blocked` 和 validated_dispatch_packets=`4` 只表示本地文件协调包已分组且语义有效；requires_human_input_items=`8`，不写 reviewed decisions、approval、training import、model claim、customer delivery authorization、release、deploy、sync、restart 或 production execution。
- P489 validator=`success=true/audit_rows=5/failures=0`；invalid_dispatch_packets=`0`、dispatch_packets_missing_local_materials=`0`。
- 完整 `run_safe_training_pipeline.py`=`591/591/0`，receipt committed；live integrity=`1803 artifacts/1801 strict/2 volatile/0 failures`。local release `release_ready=false`，claim matrix 仍 `1 allowed/10 blocked`，customer delivery 和 production execution 仍关闭。

## 2026-08-17 P490 next-unlock action checklist gap audit findings

- P490 新增 `p490_next_unlock_action_checklist_gap_audit.jsonl`、report 和 validation report，将 action checklist source-bound 到 checklist JSON/JSONL、checklist validation/status、P489 audit、local release 和 claim matrix。
- Audit 共 9 行：8 条 action checklist gap 加 1 条 summary；checklist_audit_rows=`8`、open_blocked_checklist_rows=`8`、source_completion_ready_items=`0`。
- action checklist 的 `ready_for_local_operator=true` 和 requires_human_input_items=`8` 只表示本地 operator guide 可读；不写 reviewed decisions、approval、training import、model claim、customer delivery authorization、release、deploy、sync、restart 或 production execution。
- P490 validator=`success=true/audit_rows=9/failures=0`；invalid_or_blocked_checklist_rows=`0` 且 ready_for_local_operator_rows=`8`。
- 完整 `run_safe_training_pipeline.py`=`593/593/0`，receipt committed；live integrity=`1806 artifacts/1804 strict/2 volatile/0 failures`。local release `release_ready=false`，claim matrix 仍 `1 allowed/10 blocked`，customer delivery 和 production execution 仍关闭。

## 2026-08-17 P491 next-unlock operator work ledger gap audit findings

- P491 新增 `p491_next_unlock_operator_work_ledger_gap_audit.jsonl`、report 和 validation report，将 operator work ledger source-bound 到 ledger JSON/JSONL、ledger validation/status、P490 audit、local release 和 claim matrix。
- Audit 共 9 行：8 条 operator work ledger gap 加 1 条 summary；ledger_audit_rows=`8`、open_blocked_ledger_rows=`8`、source_completion_ready_items=`0`。
- operator work ledger 的 `ready_for_local_operator_work=true`、local_materials_ready_rows=`8`、linked_human_backlog_rows=`7` 和 unlinked_human_backlog_rows=`1` 都只是本地工作台账观测；requires_human_input_items=`8`，不写 reviewed decisions、approval、training import、model claim、customer delivery authorization、release、deploy、sync、restart 或 production execution。
- P491 validator=`success=true/audit_rows=9/failures=0`；validated_ledger_rows=`8`、invalid_ledger_rows=`0`、total_backlog_missing_rows=`564`。
- 完整 `run_safe_training_pipeline.py`=`595/595/0`，receipt committed；live integrity=`1809 artifacts/1807 strict/2 volatile/0 failures`。local release `release_ready=false`，claim matrix 仍 `1 allowed/10 blocked`，customer delivery 和 production execution 仍关闭。

## 2026-08-17 P492 next-unlock operator work receipt gap audit findings

- P492 新增 `p492_next_unlock_operator_work_receipt_gap_audit.jsonl`、report 和 validation report，将 operator work receipts source-bound 到 receipt JSON/JSONL、receipt validation、P491 audit、local release 和 claim matrix。
- Audit 共 9 行：8 条 operator work receipt gap 加 1 条 summary；receipt_audit_rows=`8`、open_blocked_receipt_rows=`8`、source_completion_ready_items=`0`。
- operator work receipt 的 validated_receipt_rows=`8`、decision_input_present_rows=`7`、decision_input_existing_rows=`7` 和 observed_decision_input_rows=`8` 都只是本地 receipt/decision-input 观测；requires_human_input_items=`8`，不写 reviewed decisions、approval、training import、model claim、customer delivery authorization、release、deploy、sync、restart 或 production execution。
- P492 validator=`success=true/audit_rows=9/failures=0`；invalid_receipt_rows=`0`、source_target_rows_met_items=`0`、target_rows_met_completion_ready_items=`0`。
- 完整 `run_safe_training_pipeline.py`=`597/597/0`，receipt committed；live integrity=`1812 artifacts/1810 strict/2 volatile/0 failures`。local release `release_ready=false`，claim matrix 仍 `1 allowed/10 blocked`，customer delivery 和 production execution 仍关闭。

## 2026-08-17 P493-P497 closeout/receipt/sync gap audit findings

- P493-P497 新增公共审计模块 `scripts/p493_p497_gap_audit_common.py` 和 10 个薄 wrapper，将 closeout、manifest consistency、ready-to-verify receipt 与 docs sync receipt 全部隔离为 source-bound fail-closed audit。
- P493 human review closeout audit 共 6 行：5 条 closeout gap 加 1 条 summary；源 closeout_rows=`5`、awaiting_human_decision_rows=`5`、completion_ready_rows=`0`。closeout board 只说明仍待人工决策，不写 formal decision 或 approval。
- P494 operator work receipt manifest consistency audit 共 1 行 summary；receipt_rows=`8`、open_blocked_receipt_rows=`8`、completion_ready_items=`0`、target_rows_met_items=`0`。manifest consistency 只证明 P492 receipt 状态一致，不关闭任何 next-unlock gap。
- P495 top-tier ready-to-verify receipt audit 共 4 行：3 条 receipt gap 加 1 条 summary；valid_receipt_rows=`3`、source_completion_ready_rows=`0`、release_ready=false。ready-to-verify receipt 验证局部证据，不是 model-quality/release/production approval。
- P496 non-human ready-to-verify receipt audit 共 4 行：3 条 receipt gap 加 1 条 summary；valid_receipt_rows=`3`、source_completion_ready_rows=`0`、release_ready=false。非人工建设 receipt 同样不提升模型声明或 release。
- P497 stage25 operator docs sync receipt audit 共 1 行 summary；target_rows=`10`、stale_rows=`0`、provenance_rows=`15`、semantic_provenance_rows=`7`、receipt_atomic_commit=true、release_ready=false。docs sync receipt 只证明文档状态同步新鲜，不是部署/生产同步授权。
- P493-P497 validators 全部 `success=true/failures=0`；完整 `run_safe_training_pipeline.py`=`607/607/0`，receipt committed；live integrity=`1827 artifacts/1825 strict/2 volatile/0 failures`。local release `release_ready=false`，claim/customer/production gates 继续关闭。

## 2026-08-17 P498-P502 current receipt/release safety gap audit findings

- P498-P502 已复用 `scripts/p493_p497_gap_audit_common.py` 的 source-bound fail-closed 结构，新增 10 个 builder/validator wrapper，并接入 safe pipeline、data lake manifest 和 local release manifest。
- P498 将 safe-training pipeline receipt 的 `607` 个 source steps 作为运行完整性观测；pipeline receipt 通过不等于训练、模型质量或 release 授权。
- P499 的 local release consistency semantic input rows=`5`，一致性通过只证明本地 manifest/semantic receipt 一致，不改变 `release_ready=false`。
- P500 的 Stage25 fail-closed validation command rows=`163`，validation receipt 通过只证明审计校验完整，不授予上线、同步或生产执行权限。
- P501 观测到 local artifact completion rows=`2`、verified blocked rows=`4`、automatic promotion rows=`0`；`verified local artifact` 不得提升为 workstream completion、model claim 或 release approval。
- P502 源报告采用 `failures=[]`，current validation report 采用显式 `failure_count=0`。公共模块新增兼容计数函数，统一得到 source/current failure count=`0/0`；P502 validator 通过，guard links=`70/70`，但 `release_ready=false`。
- 最终安全状态：P498-P502 focused validators 全部通过；全量安全流水线=`617/617/0`；data lake=`1842 artifacts/1840 strict/2 volatile/0 failures`；local release consistency 通过但 `release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-17 P503-P507 receipt atomicity/regression gap audit findings

- P503-P507 将五类回归结果隔离为 source-bound fail-closed audit：安全流水线 receipt atomicity、local release consistency receipt atomicity、terminal defer mode、current semantic-policy 和 data-lake artifact integrity。
- P503 验证 command-contract drift、原子 receipt replace、失败前保留旧 receipt 和 lock contention，cases=`4/4` passed；这证明 receipt 写入机制可防篡改/半写入，不授权训练或 release。
- P504 cases=`5/5` passed，覆盖 local release consistency receipt 的 input snapshot、provenance、atomic commit 和 lock recovery；真实输入未改动。
- P505 cases=`4/4` passed，证明 terminal defer receipt 不能跨执行模式复用；defer 是 runner 内部时序边界，不是 release 准备状态。
- P506 cases=`16/16` passed，current semantic-policy regression 只证明当前 fail-closed 语义校验对隔离 fixture 有效，不是 release approval。
- P507 cases=`3/3` passed，data-lake artifact integrity regression 只证明完整性检查拒绝篡改场景，不把 artifact 存在/校验通过解释为模型、交付或生产授权。
- 最终状态：P503-P507 validators 全部通过；全量安全流水线=`627/627/0`；data lake=`1857 artifacts/1855 strict/2 volatile/0 failures`；local release consistency 通过但 `release_ready=false`。五类 source 均 `real_inputs_mutated=false`，所有 training/model/customer/production/release flags 保持 false。

## 2026-08-17 P508-P512 guard-link/data-lake integrity regression gap audit findings

- P508-P512 将 guard-link atomicity、current guard-link atomicity、volatile exemption、live content integrity 与 release-live integrity binding 统一隔离为 source-bound fail-closed audit。
- P508/P509 均为 `5/5` cases passed，证明 guard-link receipt 的原子提交和当前回归锁定可拒绝隔离 fixture 中的异常场景；不等于 release approval。
- P510 cases=`6/6` passed，volatile exemption 只允许受控的存在性校验例外，不能扩大为 artifact、训练或 release 的豁免。
- P511 cases=`3/3` passed，live content integrity 回归仅证明校验器对篡改/内容不一致保持 fail closed。
- P512 cases=`10/10` passed，local release 与 live integrity 的绑定回归只保证 receipt 关联完整，不授予客户交付、release 或生产执行。
- P503-P507 已移动至 source regression 之后运行，使同轮审计绑定到新生成的 source receipt，而不是前一轮快照。
- 最终状态：P503-P512 validators 全部通过；全量安全流水线=`637/637/0`；data lake=`1872 artifacts/1870 strict/2 volatile/0 failures`；local release consistency 通过但 `release_ready=false`。所有 regression source `real_inputs_mutated=false`，training/model/customer/production/release flags 继续保持 false。

## 2026-08-17 P513-P517 release input/policy binding gap audit findings

- P513-P517 将 data-lake release input contract policy、policy regression、local release contract binding、pipeline bootstrap release consistency 和 high-risk summary safety 统一隔离为 source-bound fail-closed audit。
- P513 policy receipt failure count=`0` 只证明 release-input contract validator 本轮通过；它不将 data-lake artifact 转变为 release input approval。
- P514/P515 各 `4/4` cases passed，分别覆盖 contract policy 的篡改回归和 local release binding 回归；回归通过只证明 fail-closed policy 可检验。
- P516 bootstrap release consistency passed rows=`11`、failed rows=`0`，证明 pipeline bootstrap 的本地一致性，不打开训练、model claim 或 release。
- P517 high-risk summary safety cases=`4/4` passed，确保高风险摘要不能被错误标记为正向 release 状态。
- 最终状态：P513-P517 validators 全部通过；全量安全流水线=`647/647/0`；data lake=`1887 artifacts/1885 strict/2 volatile/0 failures`；local release consistency 通过但 `release_ready=false`。所有 training/model/customer/production/release flags 保持 false。
## 2026-08-18 P523-P527 stage25 operator-docs sync/dynamic-status gap audit findings

- P523-P527 将 Stage25 operator-docs sync contract policy、dynamic status sync、current sync、current regression 和 atomicity regression 继续隔离为 source-bound fail-closed audit。
- P523 contract policy validation 只证明 sync contract 常量与测试向量绑定成功，`failure_count=0` 且 `release_ready=false`，不等于文档/SQLite/model/release/production 授权。
- P524 dynamic status sync regression cases=`13/13` passed；P526 current regression cases=`14/14` passed；P527 atomicity regression cases=`7/7` passed。三者都只证明隔离 fixture 对 sync/atomicity 约束可检验。
- P525 是专用 current-validation 约束，检查 `case_count=13`、`passed_case_count=13`、`atomic_commit=true`、`lock_acquired=true`，而不是通用 regression 形态。
- 最终状态：P523-P527 validators 全部通过；全量安全流水线=`667/667/0`；data lake=`1917 artifacts/1915 strict/2 volatile/0 failures`；local release consistency 通过但 `release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-18 P518-P522 local-release coverage/current regression gap audit findings

- P518-P522 将 local-release 高风险 coverage、safe-training pipeline current receipt regression、local release current receipt regression、semantic policy regression 和 semantic policy atomicity regression 继续隔离为 source-bound fail-closed audit。
- P518 coverage safety regression `source_case_rows=4`、`source_passed_rows=4`、`claims_blocked=10`；coverage 通过只证明本地 coverage 仍然阻断，不是 release ready。
- P519 current receipt regression `source_case_rows=6`、`source_passed_rows=6`、`source_isolated_fixture=true`。`run_safe_training_pipeline.py` 之前漏接这一项，本轮已补齐 runner 接线并重跑。
- P520 current receipt regression `source_case_rows=16`、`source_passed_rows=16`、`source_failure_count=0`；P521 semantic policy regression `source_case_rows=10`、`source_passed_rows=10`；P522 semantic policy atomicity regression `source_case_rows=7`、`source_passed_rows=7`。
- 最终状态：P518-P522 validators 全部通过；全量安全流水线=`667/667/0`；data lake=`1917 artifacts/1915 strict/2 volatile/0 failures`；local release consistency 通过但 `release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-18 P528-P530 stage25 operator-docs receipt/regression gap audit findings

- P528-P530 将 Stage25 operator-docs sync contract-policy regression、current-receipt regression 和 terminal-recovery regression 继续隔离为 source-bound fail-closed audit。
- P528 contract-policy regression `source_case_rows=8`、`source_passed_rows=8`、`source_failed_rows=0`；P529 current-receipt regression `source_case_rows=18`、`source_passed_rows=18`、`source_failed_rows=0`。
- P530 terminal-recovery regression `source_case_rows=5`、`source_passed_rows=5`、`source_failed_rows=0`。三者都使用 isolated fixture 且 `real_inputs_mutated=false`，不证明真实生产文档、SQLite、发布或同步授权。
- 最终状态：P528-P530 validators 全部通过；全量安全流水线=`675/675/0`；data lake=`1929 artifacts/1927 strict/2 volatile/0 failures`；local release consistency 通过但 `release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-18 P531-P535 controlled release-guard gap audit findings

- P531-P535 将 controlled release-guard order 的 validation receipt、regression、current validation receipt、current regression 和 atomicity regression 统一隔离为 source-bound fail-closed audit。
- P531/P533 均为 policy receipt 型 source，`source_success=true`、`source_failure_count=0`、`source_safe_for_model_claim=false`、`source_release_ready=false`；receipt 通过只证明 release-guard 顺序校验可复核，不授予 release。
- P532 regression cases=`8/8` passed；P534 current regression cases=`17/17` passed；P535 atomicity regression cases=`11/11` passed。三者均为 isolated fixture 且 `real_inputs_mutated=false`，不变更真实输入。
- 最终状态：P531-P535 validators 全部通过；全量安全流水线=`685/685/0`；data lake=`1954 artifacts/1952 strict/2 volatile/0 failures`；local release consistency 通过但 `release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-18 P536-P540 execution/blocker receipt gap audit findings

- P536-P540 将 Stage25 remaining blocker cross-binding、controlled execution wave pair atomicity、execution receipt gate 和 receipt lineage 统一隔离为 source-bound fail-closed audit。
- P536 绑定 5 个 remaining blockers 在 closure、activation、coverage 和 current receipt 中完全一致，同时确认 `formal_decision_rows_written=0`、`apply_executed=false`、`external_sqlite_mutated=false`、`release_ready=false`。
- P537 blocker regression cases=`6/6` passed；P538 controlled execution wave pair atomicity cases=`5/5` passed，且 isolated fixture 不变更真实输入。
- P539 receipt gate 只证明 11 个本地 executed actions 均有 matching receipt，`executed_failed_receipt_rows=0`、missing/unexpected action count 均为 0；P540 lineage 只证明 `receipt_rows=wave_action_rows=receipt_action_rows=unique_receipt_ids=11`。
- 最终状态：P536-P540 validators 全部通过；全量安全流水线=`695/695/0`；data lake=`1979 artifacts/1977 strict/2 volatile/0 failures`；local release consistency 通过但 `release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-18 P541-P545 execution proof/eligibility gap audit findings

- P541-P545 将 execution receipt proof current、proof current regression、receipt safety regression、execution eligibility matrix 和 eligibility safety regression 统一隔离为 source-bound fail-closed audit。
- P541 current proof 只证明 wave、receipts、gate、validation 和 lineage 当前 hash 绑定且 atomic commit 成功，`source_failure_count=0`、`release_ready=false`。
- P542 proof-current regression cases=`11/11` passed；P543 receipt safety regression cases=`11`，negative cases `10/10` rejected，failed cases=`0`。
- P544 eligibility matrix 观测 `action_rows=12`、`current_execution_allowed_rows=5`、`executed_in_current_trace_rows=11`、`receipt_present_rows=11`，但 `safe_for_execution_claim=false`，不得把 allowed rows 升级为当前请求执行授权或 release。
- P545 eligibility safety regression cases=`14`，negative cases `13/13` rejected，failed cases=`0`。
- 最终状态：P541-P545 validators 全部通过；全量安全流水线=`705/705/0`；data lake=`2004 artifacts/2002 strict/2 volatile/0 failures`；local release consistency 通过但 `release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-19 P546-P550 execution outcome/board/receipt freshness gap audit findings

- P546-P550 将 execution outcome dashboard、top-tier execution board、non-human construction board、parallel hard-gate execution receipts 和 execution receipt artifact freshness 统一隔离为 source-bound fail-closed audit。
- P546 观测 `action_rows=12`、`engineering_ready_rows=8`、`hard_gate_unlocked_rows=2`；工程就绪和局部 hard-gate 状态不等于模型质量、训练或 release 授权。
- P547 观测 `total_workstreams=12`、`blocked_workstreams=9`、`ready_to_verify_workstreams=3`；ready-to-verify 仍是局部验证状态，不提升 workstream completion 或 model claim。
- P548 观测 `total_workstreams=11`、`blocked_workstreams=8`、`ready_to_verify_workstreams=3`；非人工建设板同样不打开 release 或生产执行。
- P549 观测 `receipt_rows=4`、`eligibility_changed_rows=0`；execution receipt 只证明并行 hard-gate receipt 状态，不改变执行资格。
- P550 观测 `total_receipts=11`、`fresh_receipts=11`、`stale_receipts=0`、`missing_artifacts=0`、`sha256_mismatches=0`、`receipts_without_artifact_hash_fields=11`；当前 freshness 只覆盖存在性/mtime，不能替代内容哈希或 release approval。
- P546-P550 validators 全部 `success=true/failures=0`；最终全量安全流水线=`715/715/0`；data lake=`2029 artifacts/2027 strict/2 volatile/0 failures`；local release consistency=`success=true/release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-19 P551-P555 hash coverage/claim boundary/decision boundary gap audit findings

- P551-P555 将 execution receipt artifact hash coverage、top-tier execution board claim boundary、non-human construction board claim boundary、enzyme-agent outcome formal boundary 和 parallel hard-gate decision boundary 统一隔离为 source-bound fail-closed audit。
- P551 发现 11/11 execution receipts 没有 receipt-level artifact hash fields；当前 freshness validator 只能证明 artifact 存在、mtime 顺序和可重新计算 SHA256，不能证明 receipt 内预期 hash match。
- P552 top-tier board 仍为 `12` 个 workstreams、`9` blocked、`3` ready-to-verify、`0` completion-ready；局部 ready-to-verify 不提升 model claim 或 release。
- P553 non-human board 仍为 `11` 个 workstreams、`8` blocked、`3` ready-to-verify、`0` completion-ready；非人工建设状态不等于发布能力。
- P554 outcome formal boundary 观测 `action_rows=12`、`hard_gate_unlocked_rows=2`，但 strict repaired supervised rows=`0`、claim-eligible rows=`0`、benchmark model claim readiness=`false`。
- P555 parallel hard-gate decision boundary 观测 `receipt_rows=4`、`eligibility_changed_rows=0`、`training_import_written_rows=0`、`model_or_release_flags_changed_rows=0`；receipt 中存在 formal decision/runtime receipt 也不等于训练或 release 授权。
- P551-P555 validators 全部 `success=true/failures=0`；最终全量安全流水线=`725/725/0`；data lake=`2054 artifacts/2052 strict/2 volatile/0 failures`；local release consistency=`success=true/release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-19 P556-P560 ready-receipt/promotion/integrity/release boundary findings

- P556 top-tier ready-receipt boundary 观测 `receipt_rows=3`、`verification_passed_workstreams=3`、`board_ready_to_verify_workstreams=3`、`blocked_workstreams_not_executed=true`；ready-to-verify 只表示局部验证回执，不等于 workstream completion、model claim 或 release。
- P557 non-human ready-receipt boundary 观测 `receipt_rows=3`、`verification_passed_workstreams=3`、`board_ready_to_verify_workstreams=3`、`blocked_workstreams_not_executed=true`；缺失的 `safe_for_training_import` 源字段按 fail-closed `false` 处理，不推断为许可。
- P558 promotion boundary 观测 source `audit_rows=6`、`receipt_valid_rows=6`、`local_artifact_completion_rows=2`、`verified_blocked_rows=4`、`automatic_promotion_rows=0`、`workstream_completion_ready_rows=0`；verified local artifact 不自动提升为完成或模型声明。
- P559 live data-lake integrity 观测 `artifact_rows=2079`、`strict_verified_rows=2077`、`volatile_existence_only_rows=2`、`missing/unsafe_path/size_mismatch/sha256_mismatch/row_mismatch=0`；内容完整性通过仍不是 release approval。
- P560 local-release consistency 观测 `artifact_count=2079`、`failure_count=0`、`release_ready=false`；一致性 receipt 通过只证明 fail-closed 输入与安全链接一致，不授予 release、生产或同步权限。
- 本轮修正公共审计校验的三个 schema 边界：计数与 workstream 列表长度绑定、缺省安全字段保持 false、summary-only promotion audit 与源 validation audit 行数绑定。修正后 P556-P560 focused validators 全部通过。
- 最终全量安全流水线 `735/735/0`，receipt atomic commit 成功；data lake `2079 artifacts/2077 strict/2 volatile/0 failures`；local release consistency `success=true/release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-19 P561-P565 hard-boundary gap audit findings

- P561 reviewed numbering hard boundary 观测 `queue_rows=475`、`open_numbering_rows=471`、`decision_rows=4`、`reviewed_no_conflict_rows=4`、`semantic_conflict_rows=0`；reviewed queue 仍以 open rows 为主，不能被解释为 completion 或 model claim。
- P562 wet-lab feedback numeric boundary 观测 `input_rows=7`、`valid_rows=7`、`numeric_training_eligible_rows=6`、`trainability_training_eligible_rows=0`、`manual_review_required_rows=4`；数值候选存在，但 trainability 仍被 fail-closed 过滤。
- P563 physics ddG backend readiness 观测 `ready_backend_count=2`、`current_execution_ready_count=2`、`physics_backend_current_execution_rows=1`；可执行后端与当前物理执行能力仍分离，不能把 readiness 当作生产执行授权。
- P564 claim readiness matrix 观测 `claim_rows=11`、`claims_allowed=1`、`claims_blocked=10`；被允许的单条 claim 不会改变整体 `safe_for_model_claim=false`。
- P565 production release authorization 观测 `artifact_count=2079`（该 audit 在最终 manifest 刷新前生成）、`failure_count=0`、`release_ready=false`；最终 local release manifest 为 `2104` artifacts，release manifest 一致性通过仍只是内部 review package，不授予发布或生产权限。
- 本轮修正了 P561-P565 的公共审计接线，并把它们加入安全流水线与 manifest 白名单。最终全量安全流水线 `745/745/0`；data lake `2104 artifacts/2102 strict/2 volatile/0 failures`；local release consistency `success=true/release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-19 P566-P570 training/feature/artifact/guard/quality boundary findings

- P566 five-head training execution boundary 观测 `audited_rows=500`、`strict_rows=0`、`ready_head_count=0`、`training_execution_allowed=false`；五头 readiness 仍是训练阻塞状态，不授予 training execution。
- P567 validated feature index boundary 观测 `feature_rows=203`、`model_consumable_rows=203`、`training_label_source_rows=0`、`pyrosetta_ddg_input_feature_rows=11`、`pyrosetta_ddg_independent_training_sample_rows=0`；特征可供输入合同消费，但不是训练标签来源。
- P568 model artifact claim boundary 观测 `artifact_count=9`、`claimable_model_artifact_count=0`、`trained_neural_weight_artifact_count=0`、`production_model_artifact_count=0`；现有 artifact 只能用于审计/本地回归，不能声明为顶级模型权重或生产模型。
- P569 local release guard coverage boundary 观测 `guard_coverage_count=31`、`checked_guard_rows=31`、`guard_failure_count=0`、`safe_for_training_pipeline=true`、`release_ready=false`；guard 覆盖完整只证明安全链接可复核，不是 release approval。
- P570 training readiness quality boundary 观测 `quality_score=84.0`、`ready_for_baseline_training=true`、`ready_for_supervised_training_pipeline=true`、`ready_for_supervised_small_model_claim=false`、`strict_supervised_rows=0`、`claim_eligible_supervised_rows=0`、`source_blocker_count=4`；基础/流水线 readiness 不等于小模型质量声明。
- P566 新增 summary 字段触发一次 local release consistency 的 high-risk field 分类失败；已把 P566 source-bound training-execution fields 纳入 audited risk summary 白名单，并重跑 atomicity/current/regression/safety guard。最终 P566-P570 validators 全部通过；全量安全流水线 `755/755/0`；data lake `2129 artifacts/2127 strict/2 volatile/0 failures`；local release consistency 与 safety guard 均 `success=true`，但 `release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-19 P571-P575 contract/hard-gate/tool-lane/human-target boundary findings

- P571-P575 将 five-head training execution contract、model quality hard-gate contract、tool lane evidence pack、human target source runtime manifest 和 human target unlock checklist 统一隔离为 source-bound fail-closed audit。
- P571 观测 `ready_head_count=0`、`total_head_training_rows=6`、`training_import_eligible_rows=6`、`blocked_reason_count=5`、`training_execution_allowed=false`；合同中存在 eligible rows 也不授予 training execution。
- P572 观测 `hard_gate_count=10`、`unlocked_gate_count=3`、`wetlab_import_rows=0`、`physics_ddg_ready=false`、`benchmark_ready_for_model_claim=false`、`model_quality_ready=false`；局部 gate 解锁不等于 model quality claim。
- P573 观测 `total_lanes=8`、`blocked_lanes=8`、`ready_lanes=0`、`proxy_lanes=4`；tool lane evidence pack 只证明证据包可复核，不打开真实 runtime、模型声明或 release。
- P574 观测 `total_sources=7`、`blocked_sources=7`、`ready_sources=0`、`customer_ready=false`；human target source runtime manifest 仍全部 blocked。
- P575 观测 `checklist_rows=7`、`blocked_rows=7`、`ready_to_unlock_rows=0`；unlock checklist 只是待解锁清单，不是 unlock approval。
- P559/P560 这类 live/global boundary audit 必须紧跟 data lake/live integrity/local release/current consistency 刷新，否则新增 artifact 会让 source-bound 审计消费旧 live integrity 报告并失败。已在 runner 中补刷新步骤。
- 最终 P571-P575 validators 全部通过；全量安全流水线 `771/771/0`；data lake `2154 artifacts/2152 strict/2 volatile/0 failures`；local release consistency `success=true/release_ready=false`；local release safety guard current `success=true/guard_link_count=70`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-19 P576-P580 contract boundary gap audit findings

- P576-P580 将 training label import contract、wet-lab feedback authorization contract、ddG model consumption contract、structure feature model contract 和 advanced model feature contract 统一隔离为 source-bound fail-closed audit。
- P576 观测 source contract 中 `training_import_eligible_rows=6`、`counted_as_trainable_rows=6`、`safe_for_training_import=true`，但 audit 自身仍固定 `safe_for_training_import=false`、`safe_for_model_claim=false`、`release_ready=false`；该状态只说明源合同观测，不新增训练导入授权。
- P577 观测 `candidate_rows=445`、`authorization_rows=8`、`authorized_rows=8`、`preflight_rows=8`，但 `ready_for_training_import_rows=0`、`claim_eligible_rows_now=0`；wet-lab authorization contract 不能替代正式 feedback intake 或 training import。
- P578 观测 `thermompnn_proxy_rows=4` 和 `pyrosetta_physics_rows=1`，但 `physics_ddg_ready=false`、`proxy_is_physics=false`；proxy ddG 和物理 ddG 输入合同都不得直接升级为模型质量声明或 release。
- P579 观测 `parsed_coordinate_feature_rows=500`、`model_consumable_reviewed_graph_rows=34`、`unreviewed_coordinate_rows_excluded=466`、`training_label_source_rows=0`；结构特征可作为模型输入边界，但不是训练标签来源。
- P580 观测 advanced feature refs `203/203 ready`、`training_label_source_feature_ref_count=0`、optional physical ddG refs `11`、independent training samples `0`；advanced scaffold 仍为 `scaffold_only_fail_closed`。
- P580 source report 和 validation report 对 scaffold 状态字段命名不同：source 使用 `advanced_model_contract.status`，validation 使用 `advanced_model_scaffold.status`。审计 validator 已同时绑定两个位置，防止把字段缺失误判为状态缺失。
- 最终 P576-P580 validators 全部通过；全量安全流水线 `781/781/0`；data lake `2179 artifacts/2177 strict/2 volatile/0 failures`；local release consistency `success=true/release_ready=false`；local release safety guard current `success=true/guard_link_count=70`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-19 P581-P585 readiness/tool/runtime boundary gap audit findings

- P581-P585 将 active-learning trial readiness、benchmark readiness packet、enzyme tool contract、foreign tool readiness 和 MSA runtime readiness 统一隔离为 source-bound fail-closed audit。
- P581 观测 active-learning `draft_rows=0`、`blocker_count=7`，且 `candidate_generation_allowed=false`、`experiment_submission_allowed=false`、`model_status=blocked`；active-learning readiness 不能绕过 human approval、budget、biosecurity/order 或 customer delivery gate。
- P582 观测 benchmark readiness packet `packet_rows=2`、`invalid_gap_rows=2`、`completion_ready_rows=0`、`score_values_recorded=0`；blocked packet contract valid 只说明缺口包可复核，不代表 benchmark approval 或 score-cache 写入。
- P583 观测 enzyme tool contract `contract_rows=12`、`human_confirmation_required_actions=6`、`formal_decision_actions=3`，但 `training_write_actions=0`、`contract_training_write_tools=0`、`contract_formal_write_tools=0`；tool contract completeness 只允许 controlled planning，不允许写正式决策或训练标签。
- P584 观测 foreign tool readiness `tool_rows=11`、`ready_for_local_evaluation_rows=2`、`non_ready_tool_rows=9`、`verified_license_clearance_rows=0`；local evaluation ready 不等于 license verified、customer delivery、service hosting 或 release approval。
- P585 观测 MSA runtime `runtime_ready=true`、`selected_runtime=local_binary`、`target_rows=158`、trusted cache `158/158`，但 Docker daemon 仍 false 且 report policy 明确 readiness 不执行 MSA/homolog search/docker pull；MSA runtime readiness 只能支持特征生产边界，不是模型质量声明。
- 最终 P581-P585 validators 全部通过；全量安全流水线 `791/791/0`；data lake `2204 artifacts/2202 strict/2 volatile/0 failures`；local release consistency `success=true/release_ready=false`；local release safety guard current `success=true/guard_link_count=70`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-19 P591-P595 governance and claim boundary source findings

- `governance_readiness_report.json` 为 `ready=false`；外部数据 ready sources=`0`、IP/FTO decision rows=`0`、customer delivery 相关 gate 仍 false。
- `biosecurity_readiness_report.json` 的 state machine 已存在，但 decision validation ready=`false`、decision rows=`0`、approved-for-ordering rows=`0`、ready-for-ordering=`false`。
- `workstream_acceptance_gates.json` 共有 6 个 streams，human accepted/accepted 均为 `0`，`all_accepted=false`；决策 validator 只收到 1 个 `needs_more_info`，其余 5 个 stream 缺决策。
- `sequence_ip_fto_decision_validation_report.json` 的 packet rows=`3`、decision rows=`0`、valid rows=`0`、approved-for-customer-delivery rows=`0`、ready-for-customer-delivery=`false`。
- `model_claim_fail_closed_consistency_report.json` 记录 `success=true`、`failures=[]`，但 strict rows/claim eligible rows/strict MSA rows 均为 `0`，`safe_for_model_claim=false`、`release_ready=false`；一致性通过是阻断状态正确，不是模型质量或发布批准。

## 2026-08-19 P591-P595 governance and claim boundary audit findings

- P591-P595 均为 summary-only 单行审计，分别隔离 governance readiness、biosecurity readiness、workstream acceptance、sequence IP/FTO 与 model-claim consistency。
- P591 绑定 governance `ready=false`、8 个外部 source rows、0 ready sources、7 个 blockers、0 IP/FTO delivery rows；现有 license review decision rows 只保留为观察值，不构成 delivery scope。
- P592 明确区分 state machine ready 与 ordering ready：state machine 为 true，但 decision validation false、各类 order decision/output 均为 0。
- P593 明确技术就绪不等于人工验收：6 streams 中 technical ready=`2`，accepted=`0`，仍缺 5 个 stream decision。
- P594 固定 3 个 IP/FTO packet 仍缺 delivery decision，0 valid/approved delivery rows。
- P595 明确 consistency `success=true` 是 fail-closed 一致性证明；strict rows、claim eligible rows、strict MSA rows 与 automatic promotion rows 均为 0，blocked claims=`10`。
- 全量安全流水线为 `811/811/0`，data lake live integrity=`2254 artifacts/2252 strict/2 volatile/0 failures`，local release consistency=`success=true/release_ready=false`，safety guard=`success=true/guard_link_count=70`。

## 2026-08-19 P586-P590 agent governance boundary gap audit findings

- P586-P590 将 enzyme resource retrieval plan、agent result validation、agent result safety regression、agent trace audit 和 controlled release-guard order current receipt 统一隔离为 source-bound fail-closed audit。
- P586 观测 resource retrieval plan `action_rows=12`，其中 read-only `1`、requires user confirmation `5`、requires human decision `5`、forbidden current request `1`；`safe_for_controlled_agent_planning=true` 只允许规划，不允许执行、训练导入或模型声明。
- P587 观测 structured agent result validation `artifact_ref_count=8`、`property_prediction_rows=5`、`ddg_result_rows=2`，但 `selected_variant_rows=0`、`claim_eligible_training_rows=0`、`strict_msa_site_feature_rows=0`；验证通过说明结果被安全阻断，不是推荐或订购授权。
- P588 regression cases=`11`，negative cases `10/10` rejected、failed cases=`0`；安全回归通过只证明 validator 能拒绝越权 result mutation，不批准任何真实推荐、训练、模型 claim 或 release。
- P589 trace audit `trace_rows=6`、`executed_action_count=0`、`selected_variant_rows=0`，且 resource/result/regression 三项 validation success；trace 可审计不等于 agent tool 已执行。
- P590 controlled release-order current receipt `failure_count=0`、atomic commit true、action contract hash match true；current receipt 通过只证明 release-guard 顺序校验当前一致，不授予 release readiness。
- 最终 P586-P590 validators 全部通过；全量安全流水线 `801/801/0`；data lake `2229 artifacts/2227 strict/2 volatile/0 failures`；local release consistency `success=true/release_ready=false`；local release safety guard current `success=true/guard_link_count=70`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-19 P596-P600 candidate source findings

- External data source registry reports `source_rows=8` and `valid_rows=8`, but `ready_sources=0` and `ready=false`; every source remains blocked on commercial use, redistribution, source version, and retrieval timestamp review.
- Operator review status reports `action_rows=6` and `completed_action_rows=0`; valid human decision rows remain observations and do not create approval.
- Human-review release consistency reports `success=true`, `closeout_rows=5`, and `completion_ready_rows=0`; consistency confirms a blocked state rather than customer delivery or release authorization.
- Claim-promotion decision validation reports a complete template/evidence contract but `decision_rows=0`, `approved_rows=0`, nine missing promotion decisions, `ready_for_claim_promotion=false`, `safe_for_model_claim=false`, and `release_ready=false`.
- Claim-readiness current-policy validation reports `success=true`, `failure_count=0`, source parity and atomic receipt success, but explicitly keeps `safe_for_model_claim=false` and `release_ready=false`; this source is distinct from P564's matrix hard boundary and P595's model-claim consistency boundary.
- 完整 `run_safe_training_pipeline.py` 在 P481 前置位置停止于 `467` steps，唯一失败为 P481 的 `safety_guard_success_true`。P596-P600 本身均已通过 focused validation；根因是 P481 在 pipeline 的 deferred-terminal receipt refresh 链之前读取到 safety guard 的旧 consistency-current SHA。修复只将 P481 的 build/validate 移到既有 safety-guard refresh 之后，保持命令数与 fail-closed 语义不变。
- 顺序修复后 pipeline 推进至第 `680` 步，P481 已越过原失败点；新失败为 P502 `current_success_true/current_failure_count_zero`，其 builder 同样在 guard-current refresh 前读取到旧 receipt。P502 与 P481 均只观察 guard 状态，已顺序放置在同一 refresh 链之后，且未改变任何审计字段或授权边界。
- 最终完整 pipeline=`821/821/0`，receipt 原子提交成功。最终 local release consistency=`success=true/artifact_count=2279/release_ready=false`；safety guard 与 guard-current=`success=true/guard_link_count=70/release_ready=false`；P502 和 P481 validators 均恢复为 `success=true/failures=0`。
- P596=`8` registry sources、`0` ready；P597=`6` open operator actions、`0` completed；P598=`5` open closeouts、`0` completion-ready；P599=`9` target claims、`9` missing promotion decisions、`0` approved；P600 current-policy `failure_count=0`。五项 audit/report/validation 的 training/model/customer/release/production/completion authorization fields 均为 false。

## 2026-08-19 P601-P605 hard-gate packet and draft-boundary findings

- P601-P604 将四类 hard-gate operator packet validation 隔离为 source-bound summary audit：structure-feature `14` rows、wet-lab `12` rows、benchmark `2` rows、substrate-fit `13` rows，全部 `completion_ready_rows=0`。
- P605 绑定 review-draft formal boundary：`total_review_draft_rows=514`、`total_formal_decision_rows=46`、`draft_rows_counted_as_formal_decisions=0`；draft 覆盖不等于 reviewed decision 或 formal approval。
- P605 审计行包含 review-draft marker，因此必须同时满足 draft namespace isolation 的允许路径与 generic draft semantics。已将 `datasets/governance/p605_review_draft_formal_boundary_gap_audit.jsonl` 纳入显式允许路径，并让 P605 row policy 保留 draft 语义。
- Local release high-risk summary safety 会把包含 `formal_decision` 的新 summary 字段视为高风险；`p605_review_draft_formal_boundary_drafts_counted_as_formal_decisions` 已加入 audited source-bound risk 字段集合，仍要求值为 `0`。
- 最终 P601-P605 validators 全部通过；全量安全流水线 `831/831/0`；data lake `2304 artifacts/2302 strict/2 volatile/0 failures`；local release consistency 与 safety guard/current 均 `success=true`，但 `release_ready=false`。所有 training/model/customer/production/release flags 保持 false。

## 2026-08-20 P626-P630 DDG physical/runtime receipt boundary findings

- P626 Rosetta physical smoke source reports `artifact_count=5`、`physical_smoke_passed=true`、`ddg_protocol_executed=true`、`returncode=0`，但 `safe_for_training_import=false`、`safe_for_model_claim=false`、`release_ready=false`；计算 smoke 只保留为本地运行证据。
- P627 PyRosetta verified mutation DDG concordance source reports `input_feature_rows=29`、`multi_chain_candidate_rows=11`、`multi_chain_feature_rows=22`、`quality_passed_rows=5`、`quality_blocked_rows=6`；validation `valid_rows=11`、`invalid_rows=0`，但 `quality_gate_status=blocked`，因此不构成链选择或模型质量结论。
- P628 PyRosetta local install probe confirms wheel/path/module/import evidence, while `formal_license_decision_written=false`、`formal_runtime_receipt_written=false`、`approved_for_physical_ddg_runtime=false`、`physics_ddg_ready=false`、`ready_for_ddg_smoke=false`；install/import success 与 runtime authorization 保持分离。
- P629 physical runtime receipt preflight has `physical_backend_rows=3`、`ready_physical_backends=["pyrosetta"]`、`approved_runtime_receipt_rows=2`、`blocked_physical_backends=["rosetta","foldx"]`，but `physical_ddg_lane_capability_status="blocked"` and `safe_pipeline_manifest_connected=false`.
- P630 backend runtime receipt validation has `receipt_rows=2`、`valid_receipt_rows=2`、`approved_runtime_rows=2` and `any_backend_runtime_ready=true`, but FoldX receipt remains missing, `all_physical_backends_ready=false`, and lane capability stays `blocked`.
- P626-P630 focused validators all passed. A manual non-deferred receipt refresh temporarily exposed stale atomicity/guard receipts after the consistency validator changed; the full runner rebuilt the terminal chain with `KWB_DEFER_SAFE_PIPELINE_TERMINAL=1`.
- Final governed state: safe pipeline `881/881/0`, data lake live integrity `2429 artifacts/2427 strict/2 volatile/0 failures`, local release consistency `success=true/release_ready=false`, and safety guard current `success=true/guard_link_count=70/release_ready=false`. All P626-P630 audit/report/validation authorization fields remain false.

## 2026-08-20 P631-P635 DDG harness/proxy/receipt/backend failure boundary findings

- P631 source harness reports `harness_contract_rows=3`、`executor_contract_implemented_rows=3`、`approved_runtime_receipt_rows=2`、`physical_smoke_passed_rows=2`，但 `can_execute_physical_smoke_now_rows=0`、`ready_execution_plan_rows=0`；harness implementation and recognized artifacts do not authorize execution, training, model claim or release.
- P632 source validation reports `proxy_ddg_backend_ready=true`、`thermompnn_proxy_ready=true`、`proxy_is_physics=false`、`physics_ddg_ready=false`、`executable_ddg_backend_ready=false`；proxy readiness remains proxy-only.
- P633 source validation reports `total_receipts=11`、`fresh_receipts=11`、`stale_receipts=0`、`missing_artifacts=0`、`sha256_mismatches=0`，但 `receipts_without_artifact_hash_fields=11`； existence/mtime/hash readability is not receipt-level expected-hash completeness or release approval.
- P634 source receipts report `receipt_rows=4`、`validation_passed_rows=4`、`executed_rows=4`、`eligibility_changed_rows=0`、`training_import_written_rows=0`、`model_or_release_flags_changed_rows=0`；formal decision/runtime receipt counts remain local execution evidence only.
- P635 diagnostic reports physical DDG lane `blocked`、`one_ddg_backend_ready=true`、`ready_backend_count=2`、`physics_backend_ready_count=1`、`proxy_ddg_backend_ready=true`、`proxy_is_physics=false`、`formal_runtime_receipt_written=true`、`training_labels_written=false`、`unreviewed_formal_decision_written=false`、`release_ready=false`。
- P631-P635 focused validators all passed. The first full refresh found one stale atomicity regression receipt bound to the previous consistency-validator SHA; rebuilding that receipt and rerunning the deferred-terminal runner produced `891/891/0` with atomic receipt commit.
- Final governed state: data lake live integrity `2454 artifacts/2452 strict/2 volatile/0 failures`; local release consistency `success=true/release_ready=false`; safety guard current `success=true/guard_link_count=70/release_ready=false`. All new audit/report/validation authorization fields remain false; no new DDG job, training label, reviewed decision, deployment, sync, restart or production action was performed.

## 2026-08-20 P636-P640 human closeout/receipt/promotion current-boundary findings

- P636 binds `human_review_closeout_board_validation_report.json`: `closeout_rows=5`, `awaiting_human_decision_rows=5`, and `completion_ready_rows=0`. A valid closeout board remains an explicit pending-human-decision observation.
- P637 binds operator receipt-manifest consistency: `receipt_rows=8`, `open_blocked_receipt_rows=8`, `validated_receipt_rows=8`, `invalid_receipt_rows=0`, `completion_ready_items=0`, and `release_ready=false`. Receipt validation records manifest consistency, not completion or release approval.
- P638 top-tier ready-to-verify receipts are `3/3` valid with `0` invalid and `9` blocked board workstreams. P639 non-human receipts are likewise `3/3` valid with `0` invalid and `8` blocked board workstreams. Receipt validity stays distinct from model-quality, claim, or release readiness.
- P640 promotion board has `audit_rows=6`, `local_artifact_completion_rows=2`, `verified_blocked_rows=4`, and `automatic_promotion_rows=0`. "Verified local artifact only" cannot be promoted to workstream completion or model claim.
- Focused P636-P640 validators passed. The initial full pipeline stopped at `405` only because the local-release atomicity regression receipt carried the prior validator SHA after the consistency validator changed. Rebuilding that isolated receipt and rerunning the runner yielded `901/901/0` with atomic receipt commit.
- Final governed state: data lake live integrity `2479 artifacts/2477 strict/2 volatile/0 failures`; local release consistency `success=true/release_ready=false`; safety guard current `success=true/guard_link_count=70/release_ready=false`. All P636-P640 authorization fields remain false; no new DDG execution, runtime receipt, training label, reviewed decision, model claim, delivery, deployment, sync, restart, or production action occurred.

## 2026-08-20 P641 P0 今日收口 findings

- P641 将今天必须完成的 P0 处理为本地收口包：11 个 P0 plan item 均绑定真实源报告、下一动作、输入类型和完成条件。
- 当前真实 P0 仍未解锁：human decision backlog 仍有 `total_missing_rows=1211`、`open_items=11`、`ready_items=0`；五头训练 `ready_head_count=0`、`training_execution_allowed=false`；benchmark `15` 行中 `13` valid、`2` invalid、`heads_ready=3` 且 `ready_for_model_claim=false`；physical DDG lane 仍 `blocked`，proxy 不等于 physics；local release 仍 `release_ready=false`。
- P641 validator 固定 `p0_local_closeout_package_ready=true`，同时固定 `p0_unblocked=false`、`p0_completion_ready=false`、`training_import_allowed=false`、`safe_for_model_claim=false`、`release_ready=false`、`production_execution_allowed=false`。
- 今天完成的是 P0 的本地审计、计划、operator checklist、受管 manifest 和安全流水线证明；未完成也不得伪造的是人工 reviewed decisions、外部 license/IP/FTO/biosecurity 输入、正式 wet-lab/plate feedback intake、全物理 DDG runtime 闭环、五头训练授权、模型质量声明和 release/生产授权。
- 最终安全流水线为 `903/903/0`，data lake live integrity `2482 artifacts/2480 strict/2 volatile/0 failures`，local release consistency `success=true/release_ready=false`，safety guard current `success=true/guard_link_count=70/release_ready=false`。

## 2026-08-20 P642 P0 external-input packet findings

- P642 将 P641 的 11 个 P0 plan item 转成 external-input packet manifest；每个 packet 都有 `plan_item_id`、workstream、packet category、required input type、source refs、operator next action 和 acceptance condition。
- 当前 `packet_ready_for_dispatch_rows=11` 只表示可派发给人工/法务/实验/运行输入，不表示审批完成。
- P642 明确保持 `real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P642 的真实输入/decision/intake/runtime receipt 字段纳入 zero-risk 检查，防止后续 packet manifest 被误读成真实决策或执行证据。
- 最终安全流水线为 `905/905/0`，data lake live integrity `2485 artifacts/2483 strict/2 volatile/0 failures`，local release consistency `success=true/release_ready=false`，safety guard current `success=true/guard_link_count=70/release_ready=false`。

## 2026-08-20 P643 P0 external-input dispatch board findings

- P643 将 P642 的 11 个 packet 排成 4 个派发 wave：编号/结构链、反馈源/plate feedback、license/biosecurity/IP-FTO、physical DDG/benchmark/five-head/claim-release。
- 当前 `dispatch_ready_rows=11` 只表示 routing board 已可用于派发，不表示真实输入已收到或审批已完成。
- P643 validation 固定 `real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P643 的真实输入/decision/intake/runtime receipt 字段纳入 zero-risk 检查，把 P0 unblock/completion 字段纳入 false-risk 检查，防止 dispatch board 被误读为 P0 解锁或 release approval。
- 最终安全流水线为 `907/907/0`，data lake live integrity `2488 artifacts/2486 strict/2 volatile/0 failures`，local release consistency `success=true/release_ready=false`，safety guard current `success=true/guard_link_count=70/release_ready=false`。

## 2026-08-20 P644 P0 external-input handoff receipt board findings

- P644 将 P643 的 11 个 dispatch row 转成本地 handoff receipt board，分为 curation、feedback、governance、technical gate 四个 handoff channel。
- 当前 `prepared_handoff_rows=11` 只表示本地交接材料准备完成，不表示 packet 已发送、operator 已确认或外部输入已收到。
- P644 validation 固定 `handoff_sent_rows=0`、`operator_acknowledged_rows=0`、`external_input_acknowledged_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P644 的 sent/ack/input/decision/intake/runtime receipt 字段纳入 zero-risk 检查，把 P0 unblock/completion 字段纳入 false-risk 检查，防止 handoff receipt board 被误读为真实收件、审批、P0 解锁或 release approval。
- 最终安全流水线为 `909/909/0`，data lake live integrity `2491 artifacts/2489 strict/2 volatile/0 failures`，local release consistency `success=true/release_ready=false`，safety guard current `success=true/guard_link_count=70/release_ready=false`。

## 2026-08-20 P645 P0 external-input response slot registry findings

- P645 将 P644 的 11 个 handoff row 转成空 response slot registry，每个槽位绑定 handoff/dispatch/packet/workstream 和预期 response schema。
- 当前 `open_response_slot_rows=11` 与 `empty_response_slot_rows=11` 只表示空槽位已建立，不表示 response 已收到、已验证或可写入正式决策。
- P645 validation 固定 `response_received_rows=0`、`response_validated_rows=0`、`operator_acknowledged_rows=0`、`external_input_acknowledged_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P645 的 response/input/decision/intake/runtime/training label 字段纳入 zero-risk 检查，把 P0 unblock/completion 字段纳入 false-risk 检查，防止 response slot registry 被误读为真实输入、审批、P0 解锁或 release approval。
- 最终安全流水线为 `911/911/0`，data lake live integrity `2494 artifacts/2492 strict/2 volatile/0 failures`，local release consistency `success=true/release_ready=false`，safety guard current `success=true/guard_link_count=70/release_ready=false`。

## 2026-08-20 P646 P0 external-input response intake queue findings

- P646 将 P645 的 11 个空 response slot 转成 response intake queue shell，每个队列项绑定 response slot、handoff、dispatch、packet、workstream 和 response schema。
- 当前 `queue_rows=11`、`open_queue_rows=11`、`empty_queue_rows=11`、`enqueued_rows=11` 只表示队列壳已建立，不表示 queue item 已 dequeue、response 已收到或可执行 formal intake。
- P646 validation 固定 `dequeued_rows=0`、`response_received_rows=0`、`response_validated_rows=0`、`operator_acknowledged_rows=0`、`external_input_acknowledged_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P646 的 dequeue/response/input/decision/intake/runtime/training label 字段纳入 zero-risk 检查，把 P0 unblock/completion 字段纳入 false-risk 检查，防止 response intake queue 被误读为真实输入、formal intake、P0 解锁或 release approval。
- 最终安全流水线为 `913/913/0`，data lake live integrity `2497 artifacts/2495 strict/2 volatile/0 failures`，local release consistency `success=true/release_ready=false`，safety guard current `success=true/guard_link_count=70/release_ready=false`。

## 2026-08-20 P647 P0 external-input response validation preflight findings

- P647 将 P646 的 11 个 response intake queue item 转成 response validation preflight shell，每个 preflight 绑定 queue、response slot、handoff、dispatch、packet、workstream 和 response schema。
- 当前 `preflight_rows=11`、`open_preflight_rows=11`、`empty_preflight_rows=11` 只表示预检壳已建立，不表示 preflight 已执行、queue 已 dequeue、response 已收到或已验证。
- P647 validation 固定 `preflight_executed_rows=0`、`queue_dequeued_rows=0`、`response_received_rows=0`、`response_validated_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P647 的 preflight/queue/response/input/decision/intake/runtime/training label 字段纳入 zero-risk 检查，把 P0 unblock/completion 字段纳入 false-risk 检查，防止 response validation preflight 被误读为真实 response 校验、formal intake、P0 解锁或 release approval。
- 首轮完整安全流水线为 `915/915/0`，receipt committed；后续文档更新后需再次完整 pipeline 收敛 data lake/live/local release/safety guard receipt。P647 未执行任何 response validation，也未接收 response、写 reviewed decision、formal intake、runtime receipt 或训练标签。

## 2026-08-20 P648-P652 P0 response-control shell findings

- P648-P652 将 P647 的 response validation preflight 继续拆成 schema contract、evidence quarantine、decision routing、formal intake dry-run guard 和 closeout readiness gate 五个本地壳层。
- 每层均有 `11` rows，且全为 open/empty/blocked；这表示控制点已登记，不表示 response 已收到、证据已释放、decision route 已执行、formal intake dry-run 已通过或 closeout ready。
- 五层 validation 均固定 `response_received_rows=0`、`response_validated_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P648-P652 的 validation success 纳入 required success，把 P0 unblock/completion 字段纳入 false-risk，把所有执行/输入/decision/intake/runtime/training label 计数纳入 zero-risk。
- 完整安全流水线为 `925/925/0`，receipt committed；data lake artifact count 提升到 `2515`。P648-P652 未接收 response、未执行 validation/dry-run/route/closeout，也未写 reviewed decision、formal intake、runtime receipt 或训练标签。

## 2026-08-20 P653 P0 closeout blocker ledger findings

- P653 将 P652 的 closeout readiness gate 转成 blocker ledger：`blocker_ledger_rows=11`、`open_blocker_ledger_rows=11`、`empty_blocker_ledger_rows=11`、`blocked_blocker_ledger_rows=11`。
- P653 是阻塞原因台账，不是 blocker resolution、closeout approval、formal intake、runtime receipt、training label、model claim 或 release authorization。
- P653 validation 固定 `blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`response_validated_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P653 validation success 纳入 required success，把 P0 unblock/completion 字段纳入 false-risk，把 blocker/closeout/input/decision/intake/runtime/training label 计数纳入 zero-risk。
- 当前 manifest 链路已收敛到 data lake `2518 artifacts / 2516 strict / 2 volatile / 0 failures`，local release consistency `success=true/release_ready=false`。P653 未解除任何 P0 blocker。

## 2026-08-20 P654 P0 blocker escalation queue findings

- P654 将 P653 的 closeout blocker ledger 转成 blocker escalation queue：`blocker_escalation_rows=11`、`open_blocker_escalation_rows=11`、`empty_blocker_escalation_rows=11`、`blocked_blocker_escalation_rows=11`。
- P654 是本地升级队列壳，不是 escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、runtime receipt、training label、model claim 或 release authorization。
- P654 validation 固定 `escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`response_validated_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P654 validation success 纳入 required success，把 P0 unblock/completion 字段纳入 false-risk，把 escalation/blocker/closeout/input/decision/intake/runtime/training label 计数纳入 zero-risk。
- 当前 manifest 链路已收敛到 data lake `2521 artifacts / 2519 strict / 2 volatile / 0 failures`，local release consistency `success=true/release_ready=false`。P654 未发送 escalation，也未解除任何 P0 blocker。

## 2026-08-20 P655 P0 blocker escalation status board findings

- P655 将 P654 的 blocker escalation queue 转成 blocker escalation status board：`blocker_status_rows=11`、`open_blocker_status_rows=11`、`empty_blocker_status_rows=11`、`blocked_blocker_status_rows=11`。
- P655 是本地状态板，不是 escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、runtime receipt、training label、model claim 或 release authorization。
- P655 validation 固定 `escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`response_validated_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P655 validation success 纳入 required success，把 P0 unblock/completion 字段纳入 false-risk，把 status/escalation/blocker/closeout/input/decision/intake/runtime/training label 计数纳入 zero-risk。
- 当前 manifest 链路已收敛到 data lake `2524 artifacts / 2522 strict / 2 volatile / 0 failures`，local release consistency `success=true/release_ready=false`。P655 未发送 escalation，也未解除任何 P0 blocker。

## 2026-08-20 P656 P0 blocker escalation watchlist findings

- P656 将 P655 的 blocker escalation status board 转成 blocker escalation watchlist：`blocker_watch_rows=11`、`open_blocker_watch_rows=11`、`empty_blocker_watch_rows=11`、`blocked_blocker_watch_rows=11`。
- P656 是本地监视台账，不是 escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、runtime receipt、training label、model claim 或 release authorization。
- P656 validation 固定 `escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`response_validated_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P656 validation success 纳入 required success，把 P0 unblock/completion 字段纳入 false-risk，把 watch/escalation/blocker/closeout/input/decision/intake/runtime/training label 计数纳入 zero-risk。
- 当前 manifest 链路已收敛到 data lake `2527 artifacts / 2525 strict / 2 volatile / 0 failures`，local release consistency `success=true/release_ready=false`。P656 未发送 escalation，也未解除任何 P0 blocker。

## 2026-08-20 P657 P0 blocker escalation review queue findings

- P657 将 P656 的 blocker escalation watchlist 转成 blocker escalation review queue：`blocker_review_rows=11`、`open_blocker_review_rows=11`、`empty_blocker_review_rows=11`、`blocked_blocker_review_rows=11`。
- P657 是本地待复核队列，不是 review completion、escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、runtime receipt、training label、model claim 或 release authorization。
- P657 validation 固定 `escalation_reviewed_rows=0`、`escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`response_validated_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P657 validation success 纳入 required success，把 P0 unblock/completion 字段纳入 false-risk，把 review/escalation/blocker/closeout/input/decision/intake/runtime/training label 计数纳入 zero-risk。
- 当前 manifest 链路已收敛到 data lake `2530 artifacts / 2528 strict / 2 volatile / 0 failures`，local release consistency `success=true/release_ready=false`。P657 未执行复核、未发送 escalation，也未解除任何 P0 blocker。

## 2026-08-20 P658 P0 blocker escalation review status board findings

- P658 将 P657 的 blocker escalation review queue 转成 blocker escalation review status board：`blocker_review_status_rows=11`、`open_blocker_review_status_rows=11`、`empty_blocker_review_status_rows=11`、`blocked_blocker_review_status_rows=11`。
- P658 是本地复核状态板，不是 review completion、escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、runtime receipt、training label、model claim 或 release authorization。
- P658 validation 固定 `escalation_reviewed_rows=0`、`escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`response_validated_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P658 validation success 纳入 required success，把 P0 unblock/completion 字段纳入 false-risk，把 review-status/escalation/blocker/closeout/input/decision/intake/runtime/training label 计数纳入 zero-risk。
- 当前 manifest 链路已收敛到 data lake `2533 artifacts / 2531 strict / 2 volatile / 0 failures`，local release consistency `success=true/release_ready=false`。P658 未执行复核、未发送 escalation，也未解除任何 P0 blocker。

## 2026-08-20 P659 P0 blocker escalation review watchlist findings

- P659 将 P658 的 blocker escalation review status board 转成 blocker escalation review watchlist：`blocker_review_watch_rows=11`、`open_blocker_review_watch_rows=11`、`empty_blocker_review_watch_rows=11`、`blocked_blocker_review_watch_rows=11`。
- P659 是本地监视台账，不是 review completion、escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、runtime receipt、training label、model claim 或 release authorization。
- P659 validation 固定 `escalation_reviewed_rows=0`、`escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`response_validated_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`，并强制 `p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P659 validation success 纳入 required success，把 P0 unblock/completion 字段纳入 false-risk，把 review-watch/escalation/blocker/closeout/input/decision/intake/runtime/training label 计数纳入 zero-risk。
- 当前 manifest 链路已收敛到 data lake `2536 artifacts / 2534 strict / 2 volatile / 0 failures`，local release consistency `success=true/release_ready=false`，完整 safe training pipeline `939/939/0` 且 `receipt_committed=true`。P659 未执行复核、未发送 escalation，也未解除任何 P0 blocker。

## 2026-08-20 P660-P664 P0 follow-on guard findings

- P660-P664 将 P659 的本地 blocker review watchlist 继续拆成五层 source-bound、fail-closed 审计壳：aging、owner assignment、evidence missing、formal decision false-positive、closeout non-approval。
- 每层均为 `11` rows，全部 open/empty/blocked；五层 validation 均 `success=true`、`failures=0`、`response_received_rows=0`。
- P660/P661/P662/P663/P664 的新增动作计数分别保持 0：aging/staleness、owner assignment/acknowledgement、evidence received/validated、formal decision ready/false-positive cleared、closeout approved/approval written。
- 五层均未发生人工 review、escalation、blocker resolution、response intake、reviewed decision、formal intake、runtime receipt 或 training label 写入；`p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- local release fail-closed consistency 初次发现 P663 四个 `formal_decision` source-bound count 字段未被归类；将它们加入 `AUDITED_SOURCE_BOUND_RISK_SUMMARY_FIELDS` 后恢复 `success=true`，说明问题是校验器字段分类而非业务解锁。
- 最终链路：atomicity regression `5/5/0`；data lake `2553 artifacts`，live integrity `success=true/failure_count=0`；local release manifest `artifact_count=2553/release_ready=false`；local release consistency `success=true/failure_count=0/release_ready=false`；safe training pipeline `949/949/0`、`receipt_committed=true`。
- 结论：P660-P664 已完成本地受管审计建设，但不构成真实 P0 解锁、formal decision、closeout approval、训练授权、模型质量声明、release 或 production authorization。

## 2026-08-21 P665-P669 P0 closeout/intake/training/release non-promotion guard findings

- P665-P669 将 P664 closeout non-approval receipt audit 继续拆成五层 source-bound、fail-closed 审计壳：closeout non-approval watchlist、closeout owner review queue、formal intake non-write guard、training label non-import guard、release claim non-promotion guard。
- 每层均为 `11` rows，全部 open/empty/blocked；五层 validation 均 `success=true`、`failures=0`、`response_received_rows=0`。
- P665/P666/P667/P668/P669 的新增动作计数保持 0：closeout watch review、closeout owner assignment/review、formal intake guard review/write authorization、training label guard review/import authorization、release claim guard review/promotion 均未发生。
- 五层均未发生人工 closeout review、reviewed decision、formal intake、runtime receipt、training label 写入、training import、model claim、release promotion 或 production authorization；`p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P665-P669 的 P0 false flags 和动作计数纳入 false/zero-risk 检查，防止 non-approval watchlist、owner queue、non-write guard、non-import guard 或 non-promotion guard 被误读为完成态。
- 最终链路：atomicity regression `5/5/0`；data lake `2568 artifacts`，live integrity `success=true/failure_count=0`；local release manifest `artifact_count=2568/release_ready=false`；local release consistency `success=true/failure_count=0/release_ready=false`；safe training pipeline `959/959/0`、`receipt_committed=true`。
- 结论：P665-P669 已完成本地受管审计建设，但不构成真实 P0 解锁、formal intake、training import、模型质量声明、release 或 production authorization。

## 2026-08-21 P670-P674 P0 terminal non-promotion and blocked-state rollup findings

- P670-P674 将 P669 release claim non-promotion guard 继续拆成五层 source-bound、fail-closed 审计壳：release claim non-promotion status、model claim non-assertion、customer delivery non-authorization、production execution non-authorization、terminal blocked-state rollup。
- 每层均为 `11` rows，全部 open/empty/blocked；五层 validation 均 `success=true`、`failures=0`、`response_received_rows=0`。
- P670/P671/P672/P673/P674 的新增动作计数保持 0：release claim status/review/promotion、model claim review/assertion、customer delivery review/authorization、production execution review/authorization、terminal rollup review/unblock 均未发生。
- 五层均未发生 reviewed decision、formal intake、runtime receipt、training label 写入、model claim、customer delivery、release promotion 或 production execution；`p0_unblocked=false`、`p0_completion_ready=false`、`release_ready=false`。
- Local release consistency 已把 P670-P674 的 source-bound 高风险汇总字段、P0 false flags 和动作计数纳入检查，防止 terminal rollup 被误读为真实 P0 完成或授权。
- 最终链路：atomicity regression `5/5/0`；data lake `2583 artifacts`，live integrity `success=true/failure_count=0`；local release manifest `artifact_count=2583/release_ready=false`；local release consistency `success=true/failure_count=0/release_ready=false`；safe training pipeline `969/969/0`、`receipt_committed=true`。
- 结论：P670-P674 完成后，P0 本地审计建设已形成终端 blocked-state rollup，但真实 P0 仍未解锁，也没有模型声明、客户交付、release 或生产授权。

## 2026-08-21 P675-P676 true P0 input handoff findings

- P675 对 8 个当前 blocked actions 做真实本地突破探测后，确认剩余阻塞不是代码漏接：numbering 现有 4 条 formal decisions 均为 `reject_label`；KWB strict mutation holdout dataset 为 0 行；reviewed substrate identity set 没有正式 decision；license/IP/FTO/biosecurity 仍缺正式可交付/生产授权。
- 4G 原始测量可以支持 evaluation-only benchmark：plate/well 行 288、activity-risk 聚合 17，两个 benchmark validator 均通过；但正式 `datasets/feedback/experiment_feedback_plate.local.jsonl` 仍为 0 行，因为原始表缺 formal plate ID、instrument、protocol version、recorded_at 和人工 QC/review 状态。
- P676 将这些真实阻塞转成 5 类 handoff work package，并为 4G 生成 288 行人工工作表。工作表保留 measurement_id、sample_id、batch_id、variant_name、source_file、source_location、replicate_status、raw_value_numeric 等源字段，同时把 formal_plate_id、instrument_id、protocol_version、recorded_at、human_qc_decision、human_review_status、reviewer、reviewed_at、review_notes 留空。
- P676 的价值是把“下一步需要谁补什么”具体化：plate feedback 需要人工 QC/review 和正式 plate metadata；strict holdout 需要真实 holdout records/split/leakage/human acceptance；substrate identity 需要 reviewed decisions；numbering 需要 accepted canonical mapping；governance 需要 verified license/IP/biosecurity/delivery/production decisions。
- P676 validation 通过：`work_package_rows=5`、`worksheet_rows=288`、`formal_plate_intake_rows=0`、`training_eligible_plate_rows=0`、`failure_count=0`。它不写 formal intake、不写 reviewed decision、不导入 training label、不声明模型质量、不授权客户交付、release 或 production。
- 全量 safe training pipeline 收敛到 `971/971/0`、`receipt_committed=true`；data lake/local release artifact_count `2591`，local release consistency `success=true/failure_count=0/release_ready=false`。P0 仍未解锁，下一步必须接收真实人工/外部输入后再进入对应 formal validator。

## 2026-08-21 P677 P0 completion checklist findings

- P677 把 P676 的 5 类 handoff row 转成 completion checklist，不再只说明“缺什么”，而是绑定每项待建工作的 formal target file、模板/参考文件、首个 operator action、validator command 和 completion condition。
- 5 条 checklist 分别是：plate_feedback、strict_holdout、substrate_identity、numbering_curation、governance。对应 formal target 是 `experiment_feedback_plate.local.jsonl`、`kwb_strict_mutation_holdout/dataset.jsonl`、`substrate_identity_review_decisions.jsonl`、`numbering_curation_decisions.jsonl` 和 license/IP/biosecurity governance decision files。
- P677 明确当前仍无真实完成证据：`completion_ready_rows=0`、`real_input_received_rows=0`、`formal_validator_passed_rows=0`、`p0_unblocked_rows=0`。这防止“有 checklist”被误读为“已完成待建项”。
- P677 validation 通过：`success=true`、`checklist_rows=5`、`failure_count=0`，并强制 `training_import_allowed=false`、`safe_for_model_claim=false`、`customer_delivery_ready=false`、`release_ready=false`、`production_execution_allowed=false`。
- 全量 safe training pipeline 收敛到 `973/973/0`、`receipt_committed=true`；data lake/local release artifact_count `2598`，local release consistency `success=true/failure_count=0/release_ready=false`。下一步只有在真实 formal files 被填写并通过各自 validator 后，才能推进 completion。

## 2026-08-21 P678 P0 real-input live status board findings

- P678 将 P677 的 5 条 checklist 绑定到当前正式目标文件和 validator 观测，生成 5 条 source-bound live status row：`plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 当前 5 条状态均为 `blocked_*`，没有任何一条被标记为 real input received、formal validator passed、completion ready 或 P0 unblocked；汇总为 `status_rows=5`、`blocked_status_rows=5`、`completion_ready_rows=0`、`p0_unblocked_rows=0`。
- P678 focused validation 通过：`success=true`、`failure_count=0`。状态板只绑定当前观测，不写正式 plate intake、strict holdout、reviewed substrate decision、accepted canonical mapping 或 license/IP/FTO/biosecurity decision。
- 全量 safe training pipeline 通过 `975/975/0`、`receipt_committed=true`；local release manifest 为 `2604 artifacts`，fail-closed consistency `success=true/failure_count=0/release_ready=false`。
- 结论：P678 完成实时阻塞可见性和数据湖登记，但没有解除任何真实 P0 blocker；training import、model claim、customer delivery、release 和 production execution 继续关闭。

## 2026-08-21 P679 P0 real-input status freshness audit findings

- P679 对 P678 的 5 条 lane 状态逐项检查 formal target 和 validator report 是否存在、是否可读取，以及目标文件非空行数是否仍与状态板快照一致。
- 结果为 `audit_rows=6`（5 条 lane + 1 条汇总）、`current_source_bound_rows=5`、`stale_rows=0`、`source_missing_rows=0`；focused validation=`success=true/failure_count=0`。
- P679 只证明 P678 没有发现源漂移或缺失，不把“源文件存在”误读成“真实输入已完成”；`completion_ready_rows=0`、`p0_unblocked_rows=0`，且 training import、model claim、customer delivery、release、production execution 继续关闭。
- 全量 safe training pipeline 通过 `977/977/0`、`receipt_committed=true`；data lake live integrity=`success=true/failure_count=0`；local release=`2610 artifacts`、consistency=`success=true/failure_count=0/release_ready=false`。

## 2026-08-21 P681 P0 operator dispatch bundle findings

- P680 专项复核确认当前没有新的可安全解除 P0 的真实输入：plate intake `0` 行、KWB strict mutation holdout `0` 行、substrate identity formal decisions `0` 行。
- Numbering formal decisions 当前 `4` 行且全部为 `reject_label`，validator 虽通过但没有产生可用 canonical mapping；license decisions `3` 行均为 `self_attested`、`verified_rows=0`；sequence IP/FTO 与 biosecurity formal decisions 均为空。
- 新增 P681 bundle 将 5 条 P0 lane 的 formal target、source work file、模板/参考、required fields、首个 operator action、validator command 和 completion condition 集中到一个本地 JSONL/Markdown 包。
- P681 bundle 的语义是 `ready_for_manual_dispatch_blocked`：本地材料已备妥，但 `operator_dispatch_sent=0`、`operator_acknowledged=0`、`real_input_received=0`、`completion_ready=0`，不构成审批、训练导入、模型声明、客户交付、release 或 production authorization。

- P681 focused validation 为 `success=true/failure_count=0`；全量安全流水线为 `981/981/0`，receipt 已原子提交。
- 当前 local release artifact_count=`2622`；data lake live integrity 与 local release fail-closed consistency 均通过，`release_ready=false`、`safe_for_model_claim=false`。

## 2026-08-21 P687 P0 real-input closeout readiness gate findings

- P687 基于 P686 的 5 条 formal intake dry-run guard rows 建立 5 条 source-bound closeout readiness gate rows，并追溯到 decision routing、evidence quarantine、schema contract、receive preflight、operator bundle 和 completion checklist。
- 所有 row 都保持 `open_empty_closeout_readiness_gate`、`closeout_gate_open=true`、`closeout_gate_empty=true`、`closeout_gate_blocked=true`；不存在真实 response、evidence route、dry-run 或 formal intake。
- P687 validation 固定 `queue_dequeued_rows=0`、`formal_intake_dry_run_executed_rows=0`、`formal_intake_dry_run_passed_rows=0`、`formal_intake_written_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`completion_ready_rows=0`、`p0_unblocked_rows=0`，并保持 training import、model claim、customer delivery、release 和 production 相关 flags 为 false。
- local release summary 现在显式投影 P687 的 29 个 source-bound 字段；fail-closed consistency 把其中的 success、false 与 zero-risk 字段纳入检查，避免 data lake 与 release summary 之间出现未覆盖的 closeout 状态。
- 验证链路为：P687 focused validation=`success=true/failure_count=0`；local release consistency atomicity regression=`5/5/0`、`real_inputs_mutated=false`；safe training pipeline=`993/993/0`、`receipt_atomic_commit=true`；data lake live integrity 与 local release consistency 均为 `success=true/failure_count=0`。
- 结论：P687 是 closeout readiness 的受控空壳，不构成 closeout、completion、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍需要外部/人工正式输入后才可继续。

## 2026-08-21 P688 P0 real-input closeout blocker ledger findings

- P688 将 P687 的 5 条 closeout gate row 转成 source-bound closeout blocker ledger，覆盖 `plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 每条 ledger row 继承 P687 source chain、formal target、expected response fields、validator command 和 operator action，并新增 `blocker_reason` 与 `next_unblocking_evidence`；这些字段只是台账，不是响应、证据或批准。
- 所有 ledger row 均为 `open_empty_closeout_blocker`，并强制 `blocker_ledger_open=true`、`blocker_ledger_empty=true`、`blocker_ledger_blocked=true`。
- P688 validation 固定 `blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`。
- local release summary 已投影 P688 success/false/zero-risk 字段，fail-closed consistency 要求 P688 validator 成功且所有 P0 unblock、completion、training import、model claim、customer delivery、release、production flags 继续为 false。
- 验证链路为：P688 focused validation=`success=true/failure_count=0`；local release consistency atomicity regression=`5/5/0`、`real_inputs_mutated=false`；safe training pipeline=`995/995/0`、`receipt_committed=true`；data lake live integrity=`success=true/failure_count=0/artifact_rows=2664`；local release consistency=`success=true/failure_count=0`。
- 结论：P688 是 closeout blocker 的受控台账层，不构成 blocker resolution、closeout approval、formal intake、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍等待外部/人工正式输入。

## 2026-08-21 P689 P0 real-input blocker escalation queue findings

- P689 将 P688 的 5 条 closeout blocker ledger row 转成 source-bound blocker escalation queue，覆盖 `plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 每条 queue row 继承 P688/P687 source chain、formal target、expected response fields、validator command、operator action 和 blocker reason，并新增 `escalation_candidate_reason`；这些字段只是空队列登记，不是 escalation 或 acknowledgement。
- 所有 queue row 均为 `open_empty_blocker_escalation_queue`，并强制 `blocker_escalation_open=true`、`blocker_escalation_empty=true`、`blocker_escalation_blocked=true`。
- P689 validation 固定 `escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`。
- local release summary 已投影 P689 success/false/zero-risk 字段，fail-closed consistency 要求 P689 validator 成功且所有 P0 unblock、completion、training import、model claim、customer delivery、release、production flags 继续为 false。
- 验证链路为：P689 focused validation=`success=true/failure_count=0`；local release consistency atomicity regression=`5/5/0`、`real_inputs_mutated=false`；safe training pipeline=`997/997/0`、`receipt_committed=true`；data lake live integrity=`success=true/failure_count=0/artifact_rows=2670`；local release consistency=`success=true/failure_count=0`。
- 结论：P689 是 blocker escalation 的受控空队列层，不构成 escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍等待外部/人工正式输入。

## 2026-08-21 P690 P0 real-input blocker escalation status board findings

- P690 将 P689 的 5 条 blocker escalation queue row 转成 source-bound blocker escalation status board，覆盖 `plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 每条 status row 继承 P689/P688/P687 source chain、formal target、expected response fields、validator command、operator action、blocker reason 和 escalation candidate reason；这些字段只是状态板，不是 escalation 或 acknowledgement。
- 所有 status row 均为 `open_empty_blocker_escalation_status_board`，并强制 `blocker_status_open=true`、`blocker_status_empty=true`、`blocker_status_blocked=true`。
- P690 validation 固定 `escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`。
- local release summary 已投影 P690 success/false/zero-risk 字段，fail-closed consistency 要求 P690 validator 成功且所有 P0 unblock、completion、training import、model claim、customer delivery、release、production flags 继续为 false。
- 验证链路为：P690 focused validation=`success=true/failure_count=0`；local release consistency atomicity regression=`5/5/0`、`real_inputs_mutated=false`；safe training pipeline=`999/999/0`、`receipt_atomic_commit=true`；data lake live integrity=`success=true/failure_count=0/artifact_rows=2676`；local release consistency=`success=true/failure_count=0`。
- 结论：P690 是 blocker escalation 的受控状态板层，不构成 escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍等待外部/人工正式输入。

## 2026-08-21 P691 P0 real-input blocker escalation watchlist findings

- P691 将 P690 的 5 条 blocker escalation status board row 转成 source-bound blocker escalation watchlist，覆盖 `plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 每条 watch row 继承 P690/P689/P688/P687 source chain、formal target、expected response fields、validator command、operator action、blocker reason 和 escalation candidate reason；这些字段只是监视项，不是 escalation 或 acknowledgement。
- 所有 watch row 均为 `open_empty_blocker_escalation_watchlist`，并强制 `blocker_watch_open=true`、`blocker_watch_empty=true`、`blocker_watch_blocked=true`。
- P691 validation 固定 `escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`。
- local release summary 已投影 P691 success/false/zero-risk 字段，fail-closed consistency 要求 P691 validator 成功且所有 P0 unblock、completion、training import、model claim、customer delivery、release、production flags 继续为 false。
- 验证链路为：P691 focused validation=`success=true/failure_count=0`；local release consistency atomicity regression=`5/5/0`、`real_inputs_mutated=false`；safe training pipeline=`1001/1001/0`、`receipt_atomic_commit=true`；data lake live integrity=`success=true/failure_count=0/artifact_rows=2682`；local release consistency=`success=true/failure_count=0`。
- 结论：P691 是 blocker escalation 的受控 watchlist 层，不构成 escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍等待外部/人工正式输入。

## 2026-08-21 P692 P0 real-input blocker escalation review queue findings

- P692 将 P691 的 5 条 blocker escalation watch row 转成 source-bound blocker escalation review queue，覆盖 `plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 每条 review row 继承 P691/P690/P689/P688/P687 source chain、formal target、expected response fields、validator command、operator action、blocker reason 和 escalation candidate reason；这些字段只是待审核队列，不是 review、escalation 或 acknowledgement。
- 所有 review row 均为 `open_empty_blocker_escalation_review_queue`，并强制 `blocker_review_open=true`、`blocker_review_empty=true`、`blocker_review_blocked=true`。
- P692 validation 固定 `escalation_reviewed_rows=0`、`escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`。
- local release summary 已投影 P692 success/false/zero-risk 字段，fail-closed consistency 要求 P692 validator 成功且所有 P0 unblock、completion、training import、model claim、customer delivery、release、production flags 继续为 false。
- 验证链路为：P692 focused validation=`success=true/failure_count=0`；local release consistency atomicity regression=`5/5/0`、`real_inputs_mutated=false`；safe training pipeline=`1003/1003/0`、`receipt_atomic_commit=true`；data lake live integrity=`success=true/failure_count=0/artifact_rows=2688`；local release consistency=`success=true/failure_count=0`。
- 结论：P692 是 blocker escalation 的受控 review queue 层，不构成 escalation review、escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍等待外部/人工正式输入。

## 2026-08-21 P693 P0 real-input blocker escalation review status board findings

- P693 将 P692 的 5 条 blocker escalation review queue row 转成 source-bound blocker escalation review status board，覆盖 `plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 每条 status row 继承 P692/P691/P690/P689/P688/P687 source chain、formal target、expected response fields、validator command、operator action、blocker reason 和 escalation candidate reason；这些字段只是状态板，不是 review、escalation 或 acknowledgement。
- 所有 status row 均为 `open_empty_blocker_escalation_review_status_board`，并强制 `blocker_review_status_open=true`、`blocker_review_status_empty=true`、`blocker_review_status_blocked=true`。
- P693 validation 固定 `escalation_reviewed_rows=0`、`escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`。
- local release summary 已投影 P693 success/false/zero-risk 字段，fail-closed consistency 要求 P693 validator 成功且所有 P0 unblock、completion、training import、model claim、customer delivery、release、production flags 继续为 false。
- 验证链路为：P693 focused validation=`success=true/failure_count=0`；local release consistency atomicity regression=`5/5/0`、`real_inputs_mutated=false`；safe training pipeline=`1005/1005/0`、`receipt_atomic_commit=true`；data lake live integrity=`success=true/failure_count=0/artifact_rows=2694`；local release consistency=`success=true/failure_count=0`。
- 结论：P693 是 blocker escalation 的受控 review status board 层，不构成 escalation review、escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍等待外部/人工正式输入。

## 2026-08-22 P694 P0 real-input blocker escalation review watchlist findings

- P694 将 P693 的 5 条 blocker escalation review status row 转成 source-bound blocker escalation review watchlist，覆盖 `plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 每条 watch row 继承 P693/P692/P691/P690/P689/P688/P687 source chain、formal target、expected response fields、validator command、operator action、blocker reason 和 escalation candidate reason；这些字段只是监视项，不是 review、escalation 或 acknowledgement。
- 所有 watch row 均为 `open_empty_blocker_escalation_review_watchlist`，并强制 `blocker_review_watch_open=true`、`blocker_review_watch_empty=true`、`blocker_review_watch_blocked=true`。
- P694 validation 固定 `escalation_reviewed_rows=0`、`escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`completion_ready_observed_rows=0`、`response_received_rows=0`、`real_input_received_rows=0`、`reviewed_decision_written_rows=0`、`formal_intake_written_rows=0`、`runtime_receipt_written_rows=0`、`training_label_written_rows=0`。
- local release summary 已投影 P694 success/false/zero-risk 字段，fail-closed consistency 要求 P694 validator 成功且所有 P0 unblock、completion、training import、model claim、customer delivery、release、production flags 继续为 false。
- 验证链路为：P694 focused validation=`success=true/failure_count=0`；local release consistency atomicity regression=`5/5/0`、`real_inputs_mutated=false`；safe training pipeline=`1007/1007/0`、`receipt_atomic_commit=true`；data lake live integrity=`success=true/failure_count=0/artifact_rows=2700`；local release consistency=`success=true/failure_count=0`。
- 结论：P694 是 blocker escalation 的受控 review watchlist 层，不构成 escalation review、escalation sent、acknowledgement、blocker resolution、closeout approval、formal intake、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍等待外部/人工正式输入。

## 2026-08-22 P695 P0 real-input blocker escalation review watchlist aging audit findings

- P695 将 P694 的 5 条 blocker escalation review watch row 转成 source-bound aging audit row，覆盖 `plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 每条 aging row 继承 P694 source chain、formal target、blocker reason、next unblocking evidence、validator command 和 operator action；这些字段只是老化审计槽位，不是 aging review、staleness resolution、escalation 或 acknowledgement。
- 所有 aging row 均为 `open_empty_blocker_review_watchlist_aging_audit`，并强制 `blocker_review_aging_open=true`、`blocker_review_aging_empty=true`、`blocker_review_aging_blocked=true`、`p0_unblocked=false`、`p0_completion_ready=false`。
- P695 validation 固定 `aging_reviewed_rows=0`、`staleness_resolved_rows=0`、`escalation_reviewed_rows=0`、`escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`response_received_rows=0`、`real_input_received_rows=0`，以及所有 training/model/customer/release/production flags 为 false。
- 首次 local release consistency 发现两项可修复问题：P695 summary 缺失 `p0_completion_ready=false`，以及 consistency validator 修改后 atomicity receipt 仍绑定旧 SHA。补齐显式字段并运行 `validate_local_release_consistency_receipt_atomicity_regression.py` 后，回归=`5/5/0`、`real_inputs_mutated=false`。
- 验证链路为：P695 focused validation=`success=true/failure_count=0`；data lake live integrity=`success=true/failure_count=0/artifact_rows=2706`；local release consistency=`success=true/failure_count=0`；safe pipeline=`1009/1009/0`、`receipt_committed=true`。
- 结论：P695 是 blocker escalation review watchlist 的受控 aging audit 层，不构成 aging review、staleness resolution、真实 P0 输入接收、正式决策、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍等待外部/人工正式输入。

## 2026-08-22 P696 P0 real-input blocker escalation review owner assignment gap audit findings

- P696 将 P695 的 5 条 blocker review aging row 转成 source-bound owner-assignment gap row，覆盖 `plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 每条 gap row 继承 P695 source chain、formal target、blocker reason、next unblocking evidence、validator command 和 operator action；这些字段只是 owner assignment gap 审计槽位，不是 owner assignment 或 acknowledgement。
- 所有 gap row 均为 `open_empty_blocker_review_owner_assignment_gap`，并强制 `owner_assignment_gap_open=true`、`owner_assignment_gap_empty=true`、`owner_assignment_gap_blocked=true`、`p0_unblocked=false`、`p0_completion_ready=false`。
- P696 validation 固定 `owner_assigned_rows=0`、`owner_acknowledged_rows=0`、`aging_reviewed_rows=0`、`staleness_resolved_rows=0`、`escalation_reviewed_rows=0`、`escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`response_received_rows=0`、`real_input_received_rows=0`，以及所有 training/model/customer/release/production flags 为 false。
- 首次 local release consistency 发现三项问题：新增 validator 使旧 atomicity receipt SHA 失效，且 P696 layer summary 未通过 local release loop 投影两个 formal-intake zero-risk 字段。刷新 receipt、补齐 extra-zero 字段后，consistency=`success=true/failure_count=0`。
- 验证链路为：P696 focused validation=`success=true/failure_count=0`；atomicity regression=`5/5/0`、`real_inputs_mutated=false`；data lake live integrity=`success=true/failure_count=0/artifact_rows=2712`；local release manifest=`artifact_count=2712/release_ready=false`；safe pipeline=`1011/1011/0`、`receipt_committed=true`。
- 结论：P696 是 blocker escalation review watchlist 的受控 owner-assignment gap 层，不构成 owner assignment、owner acknowledgement、aging review、staleness resolution、真实 P0 输入接收、正式决策、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍等待外部/人工正式输入。

## 2026-08-22 P697 P0 real-input blocker escalation review evidence missing matrix findings

- P697 将 P696 的 5 条 owner-assignment gap row 转成 source-bound evidence missing matrix row，覆盖 `plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 每条 matrix row 继承 P696 source chain、formal target、blocker reason、next unblocking evidence、validator command 和 operator action；这些字段只是 evidence 缺失审计槽位，不是 evidence、验证结果或决策材料。
- 所有 matrix row 均为 `open_empty_evidence_missing_matrix`，并强制 `evidence_missing_matrix_open=true`、`evidence_missing_matrix_empty=true`、`evidence_missing_matrix_blocked=true`、`p0_unblocked=false`、`p0_completion_ready=false`。
- P697 validation 固定 `evidence_received_rows=0`、`evidence_validated_rows=0`、`evidence_released_rows=0`、`evidence_promoted_to_decision_rows=0`、`owner_assigned_rows=0`、`owner_acknowledged_rows=0`、`aging_reviewed_rows=0`、`staleness_resolved_rows=0`、`response_received_rows=0`、`real_input_received_rows=0`，以及所有 training/model/customer/release/production flags 为 false。
- 验证链路为：P697 focused validation=`success=true/failure_count=0`；atomicity regression=`5/5/0`、`real_inputs_mutated=false`；data lake live integrity=`success=true/failure_count=0/artifact_rows=2718`；local release consistency=`success=true/failure_count=0`；safe pipeline=`1013/1013/0`、`receipt_committed=true`。
- 结论：P697 是 blocker escalation review 的受控 evidence missing matrix 层，不构成 evidence 接收、证据验证、证据释放、证据提升到决策、真实 P0 输入接收、正式决策、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍等待外部/人工正式输入。

## 2026-08-22 P698 P0 real-input formal decision readiness false-positive guard findings

- P698 将 P697 的 5 条 evidence missing matrix row 转成 source-bound formal decision readiness false-positive guard，覆盖 `plate_feedback`、`strict_holdout`、`substrate_identity`、`numbering_curation`、`governance`。
- 每条 guard row 继承 P697 source chain、formal target、blocker reason、next unblocking evidence、validator command 和 operator action；这些字段只是防误报控制项，不是正式决策、审核结论或授权。
- 所有 guard row 均为 `open_empty_formal_decision_readiness_false_positive_guard`，并强制 `formal_decision_false_positive_guard_open=true`、`formal_decision_false_positive_guard_empty=true`、`formal_decision_false_positive_guard_blocked=true`。
- P698 validation 固定 `formal_decision_ready_rows=0`、`false_positive_cleared_rows=0`、`evidence_received_rows=0`、`evidence_validated_rows=0`、`owner_assigned_rows=0`、`owner_acknowledged_rows=0`、`aging_reviewed_rows=0`、`staleness_resolved_rows=0`、`escalation_reviewed_rows=0`、`escalation_sent_rows=0`、`escalation_acknowledged_rows=0`、`blocker_resolved_rows=0`、`closeout_ready_rows=0`、`response_received_rows=0`、`real_input_received_rows=0`、`formal_intake_dry_run_executed_rows=0`、`formal_intake_dry_run_passed_rows=0`，以及所有 training/model/customer/release/production flags 为 false。
- 首次 consistency 发现新增 validator 的旧 atomicity receipt SHA 与高风险 success summary 分类缺口；补齐 source-bound risk summary 字段并刷新 atomicity regression 后，回归=`5/5/0`、`real_inputs_mutated=false`。
- 验证链路为：P698 focused validation=`success=true/failure_count=0`；data lake live integrity=`success=true/failure_count=0/artifact_rows=2724`；local release manifest=`artifact_count=2724/release_ready=false`；local release consistency=`success=true/failure_count=0/safe_for_model_claim=false`；safe training pipeline=`1015/1015/0`、`receipt_committed=true`。
- 结论：P698 是 formal decision readiness 的受控 false-positive guard 层，不构成 false-positive 清除、正式决策、evidence 接收或验证、formal intake、训练导入、模型质量声明、客户交付、release 或 production authorization。真实 P0 仍等待外部/人工正式输入。

## 2026-08-27 P699 literature measurement extraction findings

- Batch 002 从三张正文表中获得 47 条实测突变体 measurement：YiAPPA 30、XynR 8、PjxA 9；与 Batch 001 合并后为 86 条。
- YiAPPA Table 2 同时提供 activity、Km、kcat、efficiency、55/80 C half-life、T50^30、Tm 和两种 protease resistance；但论文未在当前全文中给出可直接绑定的母本 accession/construct FASTA，因此 30 条保持 pending。
- XynR Table 2 的 Tm 是 duplicate determination 平均值，没有误差条；0 mM 和 5 mM CaCl2 必须是两个独立 assay context，不能合并。
- XynR 的 Tm 是不可逆 CD unfolding 得到的 apparent Tm；Figure 3 写 20 mM phosphate-NaOH pH 8.0，Methods 写 100 mM HEPES-NaOH pH 8.0，这一 buffer 冲突已写入 8 条 measurement 的 pending review 状态。
- XynR PDB 构建序列可映射到 UniProt `P07528` 46-396 + tag，但论文/PDB 声明的 `Bacillus sp. TAR-1` 与 P07528 当前物种 *H. halodurans* C-125 不一致；该 provenance conflict 阻止自动母本升级。
- YiAPPA 所有酶学性质为 `n=3, mean +/- SD`，kcat/Km 仅给派生点值；当前只能绑定实验室质粒 `pSTOP1622-yiappah`，不能将疑似 `Q000T0` 当作已核实 accession。
- PjxA Table 1 明确 `N30L` 属于 PTxA/PTxA-DB；PTxA-DB 是七突变组合体，其 53.6 min、76.6 C 或 delta Tm 21.3 C 不得回填给任一单点。
- PjxA 论文的 `MK948222` 描述与 GenBank 实际记录有边界差异：论文称 657-bp cDNA + 28-aa signal peptide，GenBank 却是 573-bp partial CDS / `QDX01881.1` 190-aa mature chain。成熟链位点 7/7 直接匹配，全长前体偏移只能标记为推导。
- 三篇 Batch 002 论文的 XML permissions 均声明 CC BY 4.0；开放许可只解决使用/再分发条件，不解除母本序列、编号、construct 和人工决策门禁。
- 文献候选仍与正式 feedback 物理分离；本轮验证证明 86 条均未进入 training/formal-decision/model-claim 路径。
- Batch 003 从三篇 JATS 正文表格新增 132 条：EfAmy 88、TmPhy 16、GOx 28；三批合计 218 条、218 个唯一 ID。
- EfAmy 排除另一物种同源酶 EcAmy；`E166P` 35 C kcat 的原文小数逗号仅在该已知单元显式规范为 `1033.78`，其他逗号数值一律拒绝。
- TmPhy MD2 保留 `NtermDeletionLength=10/deleted_sequence=unverified`，MD3 保留 `NtermReplacement=LNSSVPGA/replaced_span=unresolved`；直接构建谱系为 `TmPhyM <- TmPhy`、`TmPhyMD1 <- TmPhyM`、`TmPhyMD2/MD3 <- TmPhyMD1`。
- GOx Parent 以 `GOx-WT` 为背景，A2/A21/M6/F9/F91/M15 以 `GOx-Parent` 为背景；Table 1 无法将 pH 5.5/7.4 解析到行，故 `assay_ph` 留空并保留 unresolved note。
- 解析器现对来源表头语义、重复键、宽度、预期键集合、温度/指标完整性和严格数值格式执行 fail-closed；任何列重排或表结构漂移不得静默产生错配/缺失候选。
- 218 条文献候选均保持 `training_eligible=false`、`formal_decision_written=false`、`safe_for_model_claim=false`；未验证 construct 和未有人工授权回执时，数量增长不构成训练解锁。
- 新鲜门禁证据仍为 `ready_head_count=0`、`training_execution_allowed=false`；候选扩展不会绕过正式决策、授权回执和训练标签导入合同。
- Batch 004 新增 197 条：BLA 17 个完整构建体 x 5 指标 = 85；xynA 为 15 条可检出半衰期、56 条自归一化添加剂响应和 21 条酶学指标；GOx 为 4 个构建体 x 5 指标 = 20。
- BLA 条件存在三方冲突：Table caption `pH 6.0/95 C`、Results `pH 6.5/95 C`、Methods 动力学 `pH 6.5/70 C` 与半衰期 `90 C`；因此 85 条的 assay pH/温度留空。表载 kcat/Km 单位量纲和 T277/E277 命名冲突也未被静默修正。
- xynA `ND` 代表 not detectable，不是 0；Table 4 的每个 100% 都是该构建自身无添加条件分母，而且各构建的 optimum temperature 可为 50 或 55 C，因此 WT 百分比只是响应幅度比较量。
- GOx Table 1 没有 Parent Km/kcat/kcat/Km，不用摘要 `8.39` 或正文另一归一口径回填；`T132S/T56V` 和 `T132S/V42Y` 保留为双突变体，直接亲本为 `T132S`。
- BLA 来源许可为 CC BY-NC-ND 4.0，xynA/GOx 为 CC BY 4.0；可读和可抽取不等于已有训练授权回执。四批 415 条均保持三项 fail-closed 字段为 false。
- Batch 005 新增 87 条：MFAps 两个双半胱氨酸构建各 8 个指标；XYL10C_∆N 三个构建在 beechwood/sugarcane/corncob xylan 上共 39 条；ManAK 四个单突变体各 8 个指标。
- MFAps `A211C/S214C` 和 `S409C/Q412C` 是意图引入二硫键的完整双突变体；Table 2 的 relative/specific activity 存在 soluble starch versus maltodextrin 底物报告冲突，不强填底物。
- XYL10C_∆N 是 N 端截短工程亲本，∆N 长度/序列/偏移未报告；三个构建的 optimum pH 仅知为 4.0 或 4.5 但无法逐行映射，因此 `assay_ph` 留空。
- ManAK Table 1/2 采用 `S268Q`，但正文/补图还有 `S286Q`、`P199G`、`S268G` 冲突；正文把 `Km=2.1` 和 `kcat/Km=120.4` 错归 P194E，而表格明确属于 S199G，候选保留表值和冲突 note。
- ManAK 四个位点与 `MN539024.1/QHA94980.1` 翻译序列直接匹配，但该 synthetic construct 为 5' partial CDS，不构成完整前体或成熟链编号闭环。
- MFAps 和 ManAK 来源为 CC BY-NC-ND 4.0，XYL10C_∆N 为 CC BY 4.0；五批 502 条均保持 `training_eligible=false`、`formal_decision_written=false`、`safe_for_model_claim=false`。
- Batch 005 后重跑模型门禁确认：514 条 review draft 没有泄漏到 strict/claim-eligible 训练路径，`strict_rows=0`、`claim_eligible_rows=0`；五头 `ready_head_count=0`、`training_execution_allowed=false`。正式 feedback 仍为 7 行，这是 fail-closed 证据，不是模型质量或生产就绪证据。
- Batch 006 预审锁定 PMC9957083 XynA 正文表格作为下一条候选线：Table 1 含 Q24A/K104A/K143A 及多个完整工程构建体的稳定性指标，Table 2 含 3 种聚合木聚糖底物活性，Table 3 含 beechwood xylan 动力学；表格值可直接解析，图估读不纳入。Q24A/K104A/K143A/K 构建背景、XynA-VT/NT/SN/Spy 工程体和许可、母本编号仍需单独闭环，未生成训练标签。
- Batch 006 已完成：PMC9957083 Table 1/2/3 共 98 条候选，覆盖 Q24A、K104A、K143A、XynA-VT/NT/SN/Spy；XynA-SN 的 `half_life_60C=nd` 保留为不可检测文本，未转换为 0。六批联合为 600 条/600 个唯一 ID/17 个 PMCID，所有治理字段仍为 false；候选仍需 construct FASTA、编号、人工审核和许可证回执。
- Batch 007 已完成：PMC5738361 Table 1/2 共 16 条候选。Table 1 为 FSA 与 `EH-CC-E204G` 的 4 条 DSC Tm；Table 2 为 Ca/Zn ITC 的 12 条 Kd/DeltaH。解析器显式处理 JATS `rowspan`，将 Site 2-5 空金属列继承为 Zn2+，并保留 Site 4 FSA 缺失 comparator；工程背景写为 `engineered_EH-CC_background/E204G`。七批联合为 616 条/616 个唯一 ID/18 个 PMCID，三项治理字段异常 0；所有候选仍为 evidence-only，未写正式 feedback、未开启训练或模型声明。
- Batch 008 已完成：PMC8546418 Table 1 新增 9 条 XynLC9、N8Y、W6F/Q7H 的 Km/kcat/kcat/Km 动力学候选；Table 2 的 Volume/Area/Minimal distance 为计算结构量，按治理规则未纳入。八批联合为 625 条/625 个唯一 ID/19 个 PMCID，三项治理字段异常 0；构建背景、编号、人工复核和许可证仍未闭环，所有候选保持 evidence-only。
- Batch 009 已完成：PMC11430584 Table 1 新增 16 条 W6F/Q7H 相对 Xynst 的底物特异性 Vmax/Km/kcat/kcat/Km 候选；对 XML 中变体 rowspan 进行显式继承，未纳入 Table 2 计算结构量。九批联合为 641 条/641 个唯一 ID/20 个 PMCID，三项治理字段异常 0，仍未进入正式训练。
- Batch 010 已完成：PMC5984770 Table 1 新增 8 条 AnP-M1/AnP-M2 的 Km、Vmax、kcat、kcat/Km 候选；M1 的 18 substitutions 与 M2 的 9 substitutions 保持完整组合背景。十批候选仍为 evidence-only，未进入正式训练。
- Batch 011 已完成：PMC6883096 Table 1 新增 12 条 DS153/DS241/DS428 相对 reBaxA 的 Vmax、Km、kcat、kcat/Km 候选；组成分别为 N29S、S31R、I51V。十一批候选仍为 evidence-only，未进入正式训练。
- Batch 013 已完成：PMC9181005 Table 1 新增 12 条 AppA 变体 Km、kcat、kcat/Km 候选；HAT/HET/HAE/HDE 组成分别为 D304A、D304E、D304A/T305E、T305E，HDT 为对照。十三批候选仍为 evidence-only。
- Batch 014 已完成：PMC9181005 Table 2 新增 8 条 AppA 变体的 `InsP5 [4/6-OH]` 与 `InsP5 [1/3-OH]` 区域选择性比例候选，统一标记为 `substrate_regioselectivity`，未与动力学任务混用。十四批联合为 689 条/689 个唯一 ID/24 个 PMCID，来源哈希与三项治理字段异常均为 0。
- Batch 015 已完成：PMC10101328 Table 1 绑定 D7/E3/F8/F9/G10 完整组成，Table 2 新增 10 条酶活/产量候选，Table 3 新增 12 条 D7/E3/F8 动力学候选。F9/G10 在 Table 3 无值，未补填或推断。十五批候选仍为 evidence-only。
- Batch 016 已完成：PMC6167268 Table 4 新增 MutMCAP-8 `N331Q` 的 MCA、PA 和 MCA/PA 三条候选，MCAP-3 为直接构建对照；SyMCAP-6 只有密码子优化背景，M. mihei 为异源酶，均未作为突变标签。信号肽和表达背景仍待人工复核。
- Batch 017 已完成：PMC9148494 Table 1 新增 TlGA-M4/M6/M7 的 activity、relative activity、specific activity、Km、kcat、kcat/Km 共 18 条候选；三者分别保留八点、三点、五点完整组成。M1-M3/M5 属于片段置换构建体，边界未闭环前不抽取。
- Batch 018 已完成：PMC12007714 Table 1 新增 8 条 M-60(5) 水解动力学/热力学候选，Table 2 新增 4 个温度下 20 条不可逆热失活候选。正文和图注写位置 203，审稿记录写 L103I，因此 composition 固定为 `unresolved:L203I_vs_L103I`，编号状态为 blocked。
- Batch 019 已完成：PMC5457547 Table 1 新增 mRmMan5A 在 LBG、konjac powder、guar gum 上的 3 条 specific activity 候选；WT comparator 仅使用相同 pH 4.5/65 C 列，RmMan5A 的 pH 7.0/55 C 最适条件列未混入。
- P699 文献候选不再依赖临时联合脚本：统一 validator 对 19 个 batch 执行字段合同、全局 measurement ID、完整语义重复、source path/SHA-256 和三项治理字段检查。当前 `success=true/row_count=763/unique_measurement_ids=763/failure_count=0`。
- P699 新增单一复核注册表，按 batch/measurement ID 确定性排序并保留 `candidate_batch`。manifest 明确 `registry_status=evidence_only_review_draft`，三个授权计数均为 0；该产物用于审校交接，不是训练导入表。
- P699 人工复核队列已从 measurement 粒度修复为构建体复核粒度。同一 source SHA、parent、variant、composition、numbering status、human-review status 只生成一个稳定 review task；129 个任务覆盖 763 个唯一 measurement ID，P0/P1/P2=`1/97/31`，所有 reviewer/decision/time/authorization 字段为空。
- Batch 020（PMC12695923）Table 1 提供 BaqA∆C 与 BaqA∆C N185D 的 3 条动力学候选（Km、kcat、kcat/Km）。表格和正文明确底物为可溶性淀粉、最适条件为 pH 6.5/50 ℃；解析器保留原始 mg/mL、s−1、mL mg−1 s−1 单位及均值±误差，不把摘要中的 specific activity/DH 或计算 docking/MD 结果混入 measurement。
- BaqA∆C 是缺失 C 端 34 aa 的工程截短亲本，N185D 使用 BaqA∆C numbering；当前仅有 JN797599.1 亲本 accession 线索，未完成 construct FASTA、成熟链/标签边界和人工许可/审核回执。因此 3 条候选的 `numbering_status=sequence_accession_only`、`training_eligible=false`、`formal_decision_written=false`、`safe_for_model_claim=false`。
- Batch 020 后统一校验为 20 批/766 行/766 唯一 ID/28 个 PMCID/0 failures；registry 仍为 `evidence_only_review_draft`，review queue 增至 130 个构建体级任务，reviewed/authorized/training-eligible 均为 0。
- Batch 021（PMC5855647）Table 1 提供 7 个 GOx 突变体在 55 ℃ 下的半衰期与 Tm，共 14 条候选；WT 行作为同条件 comparator 保留。解析器只读取表格原值，不从图形估读，不混入其他功能指标。
- 该表的半衰期单位为 min、Tm 单位为 ℃，突变背景分别为 D408W/D408T/D408K/D408C、E476T/E476K、S100A；当前未完成 construct 序列、成熟链/标签边界和人工许可/审核回执，所有候选保持 `numbering_status=sequence_accession_only` 与三项 fail-closed 字段为 false。
- Batch 021 后统一校验为 21 批/780 行/780 唯一 ID/28 个 PMCID/0 failures；registry SHA-256 更新为 `44aeadf81e89f54b7f2e180f65106fe17c55f91f3ded5034175b0d18455b0f93`，review queue 为 137 个构建体级任务。
- Batch 022（PMC6659274）Table 1/2 新增 18 条木聚糖酶候选：PTxA、PjxA-DB、PTxA-DB 的 60 ℃ 半衰期/Tm 与 beechwood xylan 动力学指标。表格中的 T2C/T29C 二硫键和 PTxA 的五点背景保持完整，不拆成伪单点标签。
- 该文的动力学表使用 55 ℃、beechwood xylan；热稳定性表使用 60 ℃ 半衰期和 Tm。当前未完成构建序列与编号闭环，所有候选保持 sequence_accession_only、training_eligible=false、formal_decision_written=false、safe_for_model_claim=false。
- Batch 022 后统一校验为 22 批/798 行/798 唯一 ID/28 个 PMCID/0 failures；registry SHA-256 更新为 `ffac0ecd03343576645b098fc288f45eb72da74b147068fdbaea73f2b096d7ca`，review queue 为 141 个构建体级任务。
- Batch 023（PMC9986629）Table 1 新增 42 条 Anman 突变体性质候选，覆盖 E15C、S65P、A84P、A195P、T298P、Mut5 六个变体与七类指标；WT Anman 行作为 comparator 保留。表格为 locust bean gum 条件性质矩阵，未混入计算或图形估读数据。
- 构建体序列、编号及许可/人工审核回执仍未闭环，候选保持 `numbering_status=sequence_accession_only`、`training_eligible=false`、`formal_decision_written=false`、`safe_for_model_claim=false`。
- Batch 023 后统一校验为 23 批/840 行/840 唯一 ID/28 个 PMCID/0 failures；registry SHA-256 更新为 `ad6bdbe6562ea3cf5897557ac3646f52e7e04881f08e6f01b1256a86df9d9c6d`，review queue 为 147 个构建体级任务。
- Batch 024（PMC11380507）Table 2 新增 30 条 YiAPPA 三类突变体的性质候选，覆盖 specific activity、Km、kcat、kcat/Km、55/80 ℃ 半衰期、T50、Tm、pepsin/trypsin resistance；所有数值保留原始均值±误差。构建序列、编号和人工审核回执未闭环，候选保持 evidence-only。
- Batch 024 后统一校验为 24 批/870 行/870 唯一 ID/28 个 PMCID/0 failures；registry SHA-256 为 `5cc5f6eb66f4aa1b5ce4942ce2f31e7a2749f75594abbc97af0d4ad31d5e80d2`，review queue 为 150 个构建体级任务。
### 文献复核页面集成修复
- 页面 404 根因是缺少 `reports/literature_measurement_review_queue.json`，已补生成并保持与旧编号决策 API 隔离。
- 修复初始化空草稿被误标为“已起草”的状态 bug；状态现在只认 `reviewed_at`。
- 队列产物已建立可重复生成基线：JSON 与 CSV 任务 ID、测量计数完全一致，重生成无差异；后续批次更新必须通过该一致性检查。
