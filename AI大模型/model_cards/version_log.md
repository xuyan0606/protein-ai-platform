# KWB-EnzymeDesigner 版本记录

## 0.1.0-rule-mvp

状态：本地研发完成。

内容：

- 规则 MVP。
- 本地 HTTP 服务。
- 6-case benchmark。
- 特征抽取。
- baseline ranker 训练/评估脚本。

验证：

- Python 编译通过。
- JSON 合法性校验通过。
- 本地服务 smoke 通过。
- 本地 benchmark 6/6 passed。

限制：

- 不是神经网络模型。
- benchmark 为本地研发 fixture。
- 尚未接入真实 KWB Lipase DB 特征抽取。
- 尚未接入平台工具注册。

## 0.2.0-baseline-ranker

状态：本地 baseline 完成。

目标：

- 建立可版本化线性 baseline。
- 生成训练表。
- 生成 baseline 模型文件。
- 形成后续神经网络/GBDT/排序模型对照基线。

下一步：

- 接入真实私有数据特征。
- 补模型训练数据质量报告。
- 补 family-level split 策略。

验证：

- `extract_features.py` 生成样例特征 2 行。
- `build_training_table.py` 生成本地训练表 12 行。
- `train_baseline_ranker.py` 生成 `prototype/baseline_ranker_model.json`。
- `evaluate_baseline_ranker.py` 生成 `reports/baseline_ranker_eval.json`，accuracy = 0.833。
- `smoke_local_service.py` 通过。

## 0.3.0-data-readiness

状态：本地只读数据接入启动。

内容：

- 本地数据发现。
- 数据质量评分。
- Lipase DB 只读特征抽取。
- 实验反馈抽取器草案。
- 工具审计抽取器草案。
- baseline 校准建议。
- family-level split 报告。

验证：

- `deploy_data/lipase/lipase.db` 只读检查 ready。
- 数据质量总分 84，ready_for_training=true。
- Lipase 特征抽取 24 行。
- 本地 app DB 暂缺 `experiment_feedback_records` 和 `tool_task_audits` 表，抽取器按 missing_table 输出。

限制：

- 暂未抽取线上 RDS 中的真实反馈/审计记录。
- 暂未把 lipase 特征并入监督训练标签。
- 仍未接入主平台工具注册。

## 0.4.0-supervised-pipeline

状态：本地监督训练流水线完成，模型质量未达可宣称门槛。

内容：

- enzyme mutation labels 转监督训练表。
- protein-group train/validation/test split。
- 无依赖监督 baseline 训练和评估。
- data lake manifest 和 training readiness 升级。

验证：

- `build_supervised_mutation_table.py` 生成 500 行监督训练表，覆盖 145 个 UniProt group。
- 标签分布：go 161、watch 181、no_go 158。
- `make_supervised_mutation_split.py` 生成 train/validation/test = 373/60/67，无 group leakage。
- `train_supervised_mutation_baseline.py` 生成 `prototype/supervised_mutation_baseline_model.json`。
- 非泄漏 baseline 当前选择 `majority_class`，validation/test accuracy = 0.317/0.239。
- `training_readiness_report.py` 输出 `ready_for_supervised_training_pipeline=true`、`ready_for_supervised_small_model_claim=false`。

限制：

- 当前特征还没有结构位点、口袋距离、保守性、家族 embedding。
- 当前监督标签来自本地/公开稳定性记录，尚未接入真实 KWB 湿实验反馈。
- baseline 只能证明训练流水线可运行，不能作为生产突变预测模型。

## 0.5.0-feature-enrichment-start

状态：本地结构/功能代理特征增强完成，模型质量仍未达可宣称门槛。

内容：

- 从本地 enzyme DB 合并 PDB、AlphaFold、PFAM、EC、kinetic、reviewed、function annotation 等上下文特征。
- 生成增强监督训练表。
- 训练增强 baseline 并与 0.4.0 对比。
- 扩展运行事件 schema，生成前端高级运行面板 demo trace。
- 补国际先进路线对标文档。
- 补本地平台 adapter stub，明确与 GPT-5.6 不冲突。

验证：

- `enrich_supervised_mutation_features.py` 生成 500 行增强训练表。
- 145 个 UniProt group 全部匹配 DB 上下文。
- 500 行有 PDB 证据，498 行有 AlphaFold 证据。
- 增强 baseline 当前仍选择 `majority_class`，validation/test accuracy = 0.317/0.239。
- `generate_runtime_trace_demo.py` 生成 8 条运行事件。

限制：

- 当前结构特征仍是记录级代理，不是突变位点级三维环境。
- 尚未计算口袋距离、催化残基距离、SASA、二级结构、MSA 保守性。
- 尚未接入真实 KWB 湿实验反馈闭环。

## 0.6.0-data-integrity-gate

状态：本地数据完整性门控完成，监督模型质量声明继续阻断。

内容：

- mutation label 编号完整性审计。
- verified label 子集导出。
- 编号修复建议报告。
- 位点级序列窗口特征生成。
- verified/site-level sanity baseline。

验证：

- 500 条增强监督 labels 中，25 条通过当前序列编号校验。
- 475 条存在 `wild_type_mismatch_current_sequence`。
- 编号修复建议无单一主导 offset：+1 只有 26 条，-2/-3 各 23 条，109 条在 ±20 内找不到 WT。
- domain architecture 1942 条区间均无效。
- DB 中 113836 条 PDB 路径在本地没有对应文件。
- site-level sequence feature table 生成 25 行、23 个 group。

限制：

- verified 样本太少，训练结果只能作为管线 sanity check。
- 需要 UniProt 版本/isoform/文献编号回源映射后，才能扩大强监督训练集。

## 0.7.0-curation-readiness

状态：本地证据分层和结构缓存审计完成。

内容：

- audited/verified/weak evidence 三层数据输出。
- numbering curation queue。
- weak evidence retrieval index。
- structure cache readiness audit。
- training readiness 增加结构缓存阻断项。

验证：

- weak evidence：475 行。
- numbering curation queue：475 行，P0 213、P1 249、P2 13。
- weak evidence index：475 行、145 个 UniProt group。
- structure cache audit：PDB sample existing = 0，AlphaFold sample existing = 0。

限制：

- 坐标级结构特征需要先补本地 PDB/mmCIF/AlphaFold 文件缓存。
- weak evidence 只能作为检索上下文，不能进入强监督训练。

## 0.8.0-curation-application-scaffold

状态：本地回源应用脚手架和结构缓存 manifest 完成。

内容：

- 编号回源决策 schema。
- 回源决策模板和空决策文件。
- apply curation 脚本。
- structure cache manifest schema。
- local-only structure cache config example。
- expected structure cache manifest。

验证：

- 当前 `numbering_curation_decisions.jsonl` 为空，应用后强监督标签仍为 25 条，不会误提升 weak evidence。
- `structure_cache_expected_manifest.json` 生成 500 个 entries，present 0、missing 500。

限制：

- 需要真实人工/程序回源决策后，`repaired` 表才会增长。
- 需要本地结构文件缓存后，坐标级特征才会解锁。

## 0.9.0-curation-operations

状态：本地编号回源运营工作包完成。

内容：

- P0 curation batch 生成。
- curation decision validation。
- apply curation 增加 canonical WT 序列校验和 confidence 门控。
- curation dashboard 汇总。

验证：

- P0 可回源记录：213。

## 2.3.0-feature-cache-adapters

状态：本地顶级模型特征缓存 scaffold 完成，模型质量声明仍阻断。

内容：

- 新增 advanced feature cache manifest schema。
- 新增 fail-closed advanced feature adapter scaffold。
- 新增 GitHub/Google 调研 watchlist 到本地 adapter requirement。
- 特征家族扩展到 sequence PLM、MSA/conservation、structure graph、ddG stability、structure/affinity complex、kinetics/function、candidate generation、benchmark score cache、wet-lab feedback calibration。
- release manifest 已记录 advanced feature family/adapter/blocked/ready 统计。

验证：

- `build_advanced_feature_cache_plan.py`：9 个 feature family、36 个 adapter requirement、34 个 blocked adapter。
- `run_safe_training_pipeline.py`：107/107、0 failed。
- `run_local_benchmark.py`：6/6 passed。
- `check_safe_training_entrypoint.py`：25 rows、0 failures、safe_for_model_claim false。
- `build_data_lake_manifest.py`：481 artifacts。
- `build_local_release_manifest.py`：release_ready false。

限制：

- 不是训练好的顶级模型。
- 未执行外部 PLM、MSA、Boltz-2、ThermoMPNN、Rosetta/PyRosetta/FoldX、CatPred、LigandMPNN 或 ProteinGym。
- reviewed numbering、MSA/cache、真实实验反馈、ddG backend 和生产同步授权仍未解锁。

## 2.4.0-top-tier-all-started

状态：顶级模型全部本地启动完成，全部仍 fail-closed。

内容：

- 新增 top-tier model execution board。
- 新增 12 条 P0/P1/P2/cross workstream。
- 新增 12 条 start packet。
- 新增 execution board validator。
- 接入 safe pipeline、data lake manifest 和 local release manifest。

验证：

- `build_top_tier_model_execution_board.py`：12 started、12 blocked、0 ready_to_verify。
- `validate_top_tier_model_execution_board.py`：success true、failed_checks 0。
- `run_safe_training_pipeline.py`：109/109、0 failed。
- `run_local_benchmark.py`：6/6 passed。
- `check_safe_training_entrypoint.py`：25 rows、safe_for_model_claim false。
- `build_data_lake_manifest.py`：489 artifacts。
- `build_local_release_manifest.py`：release_ready false。

限制：

- 本版本只表示全部 workstream 已开始。
- 未执行外部模型，未生成高级特征，未训练新权重。
- 不解除 model-quality、customer-delivery、ordering、license、ddG 或 production gate。

## 2.5.0-reviewed-structure-graph

状态：P0 reviewed structure graph 本地特征完成，模型质量声明仍阻断。

内容：

- 新增 reviewed structure graph builder。
- 新增 reviewed structure graph validator。
- 基于 12 条 reviewed chain mapping 生成 residue-neighborhood graph cache。
- 每个 graph artifact 记录 input structure sha256、graph sha256、selected chain、numbering basis、node/edge count。
- top-tier execution board 由 12 blocked 更新为 11 blocked、1 ready_to_verify。

验证：

- `build_reviewed_structure_graph_features.py`：graph_rows 12、failure_rows 0。
- `validate_reviewed_structure_graph_features.py`：valid_rows 12、invalid_rows 0、ready_for_coordinate_feature_use true。
- `run_safe_training_pipeline.py`：111/111、0 failed。
- `run_local_benchmark.py`：6/6 passed。
- `check_safe_training_entrypoint.py`：25 rows、safe_for_model_claim false。
- `build_data_lake_manifest.py`：505 artifacts。
- `build_local_release_manifest.py`：release_ready false。

限制：

- 结构图不是突变标签编号回源。
- 结构图不是 MSA、ddG、kinetics、benchmark 或湿实验反馈。
- 不能用于客户交付或顶级模型质量声明。

## 2.6.0-msa-trusted-cache-intake

状态：P0 MSA trusted cache intake 完成，MSA 真实特征仍阻断。

内容：

- 新增 trusted MSA/cache intake schema。
- 新增 local intake 和 full target template。
- 新增 apply 脚本，将真实本地 MSA/conservation 文件和 checksum 合并进 `msa_conservation_manifest.json`。
- 接入 safe pipeline、data lake manifest 和 local release manifest。

验证：

- `apply_msa_trusted_cache_intake.py`：accepted_rows 0、missing_target_rows 158、ready_to_validate_cache false。
- `validate_msa_conservation_cache.py`：ready false、valid_rows 0、invalid_rows 158。
- `build_msa_runtime_readiness.py`：runtime_ready false。
- `run_safe_training_pipeline.py`：112/112、0 failed。
- `run_local_benchmark.py`：6/6 passed。
- `check_safe_training_entrypoint.py`：25 rows、safe_for_model_claim false。
- `build_data_lake_manifest.py`：511 artifacts。
- `build_local_release_manifest.py`：release_ready false。

限制：

- 未运行 MMseqs2。
- 未创建或伪造 MSA/conservation。
- 仍需真实 homolog database/cache 或本地 runtime 才能解锁 MSA 特征。

## 2.7.0-benchmark-score-cache-intake

状态：P0 benchmark score cache intake 完成，benchmark scorecard 仍阻断。

内容：

- 新增 benchmark score cache intake schema。
- 新增 benchmark score cache local intake 和 template。
- 新增 apply + validate 脚本。
- 接入 safe pipeline、data lake manifest、local release manifest 和 top-tier execution board。

验证：

- `apply_benchmark_score_cache_intake.py`：accepted_rows 0、missing_rows 14。
- `validate_benchmark_score_cache.py`：ready_for_model_claim false、valid_rows 0、invalid_rows 14、heads_ready 0。
- `run_safe_training_pipeline.py`：114/114、0 failed。
- `run_local_benchmark.py`：6/6 passed。
- `check_safe_training_entrypoint.py`：25 rows、safe_for_model_claim false。
- `build_data_lake_manifest.py`：519 artifacts。
- `build_local_release_manifest.py`：release_ready false。

限制：

- 未下载外部 benchmark。
- 未创建或伪造 scorecard。
- Benchmark 只能作为评价证据，不能替代 KWB 湿实验标签。

## 2.8.0-proteingym-local-source

状态：ProteinGym local source index 完成，KWB benchmark scorecard 仍阻断。

内容：

- ProteinGym official repo/source package 已缓存到 `cache/external/ProteinGym`。
- 新增 source file index，每个文件记录 size、suffix、sha256 和相对路径。
- 新增 local source manifest/report。
- 接入 safe pipeline、data lake manifest 和 local release manifest。

验证：

- `build_proteingym_local_source_manifest.py`：source_present true、file_count 567、benchmark_file_count 69。
- `run_safe_training_pipeline.py`：115/115、0 failed。
- `run_local_benchmark.py`：6/6 passed。
- `check_safe_training_entrypoint.py`：25 rows、safe_for_model_claim false。
- `build_data_lake_manifest.py`：532 artifacts。
- `build_local_release_manifest.py`：release_ready false。

限制：

- ProteinGym source evidence 不是 KWB scorecard。
- `ready_as_kwb_scorecard=false`。
- `benchmark_score_cache_validation_ready_for_model_claim=false`。
- 未生成 MSA、ddG、kinetics、benchmark score 或 KWB 湿实验反馈。

## 2.9.0-mmseqs2-local-runtime

状态：MMseqs2 local binary runtime 完成，MSA search 仍阻断。

内容：

- 下载并缓存官方 macOS universal MMseqs2 package。
- 新增 MMseqs2 local runtime manifest/report。
- MSA runtime readiness 支持项目内 binary path。
- foreign tool readiness 支持项目内 required executable path。
- 接入 safe pipeline、data lake manifest 和 local release manifest。

验证：

- `build_mmseqs2_local_runtime_manifest.py`：binary_present true、probe ok true、version `17b688d21dda57fc5f5b7286ecba7ec003d4717f`。
- `build_msa_runtime_readiness.py`：runtime_ready false、homolog database not configured。
- `build_msa_execution_plan.py`：158 jobs、0 ready、158 blocked。
- `build_foreign_tool_readiness.py`：MMseqs2 install/runtime present, data_ready false, ready_for_local_evaluation 0。
- `run_safe_training_pipeline.py`：116/116、0 failed。
- `run_local_benchmark.py`：6/6 passed。
- `check_safe_training_entrypoint.py`：25 rows、safe_for_model_claim false。
- `build_data_lake_manifest.py`：540 artifacts。
- `build_local_release_manifest.py`：release_ready false。

限制：

- 未下载 homolog database。
- 未执行 MMseqs2 search。
- 未生成 MSA/conservation features。
- `msa_runtime_ready=false`、`safe_for_model_claim=false`。

## 2.10.0-mmseqs-swissprot-db

状态：MMseqs2 Swiss-Prot homolog database 完成。

内容：

- 使用 MMseqs2 `databases` 构建 UniProtKB/Swiss-Prot 本地 homolog DB。
- 新增 homolog database manifest/report。
- 配置 MSA runtime database_path、database_name、database_version 和 checksum_manifest。

验证：

- database prefix：`cache/mmseqs_databases/uniprot_sprot`。
- database version：UniProtKB/Swiss-Prot Release 2026_02 of 10-Jun-2026。
- lookup rows：575503。
- smoke hits：69597。
- `msa_runtime_ready=true`。
- `msa_runtime_selected_runtime=local_binary`。

限制：

- 数据库 ready 不等于 per-target MSA cache ready；必须继续生成并验证 per-target cache。

## 2.11.0-msa-swissprot-cache

状态：MSA/conservation cache 完成。

内容：

- 对 158 个 MSA targets 执行本地 MMseqs2 Swiss-Prot search。
- 生成 `cache/msa/mmseqs_swissprot_hits.m8`。
- 生成 158 个 per-target alignment FASTA。
- 生成 158 个 conservation JSON。
- trusted cache intake 和 validator 接入。

验证：

- raw_hit_rows：22410。
- targets_with_hits：158/158。
- accepted_rows：158。
- missing_target_rows：0。
- MSA cache validation：ready true、valid_rows 158、invalid_rows 0。
- safe pipeline：118/118、0 failed。
- benchmark：6/6 passed。
- safe entrypoint：25 rows、safe_for_model_claim false。
- data lake：874 artifacts。
- release manifest：release_ready false。

限制：

- MSA/conservation 是 computational feature，不是湿实验标签。
- 不替代 reviewed numbering、Rosetta/FoldX ddG、benchmark scorecard 或 KWB 实验反馈。
- `safe_for_model_claim=false` 仍保持。
- 已生成 5 个 P0 batch，覆盖 125 条。
- 当前决策文件为空，valid/invalid 均为 0。
- apply 后强监督标签仍为 25，未误提升 weak evidence。

限制：

- 需要真实回源决策后，repaired 强监督集才会增长。
- batch 工作包只组织人工/程序回源，不自动修改标签。

## 1.0.0-safe-training-entrypoint

状态：本地安全训练入口完成。

内容：

- 从 repaired 全量表导出 strict supervised table。
- 训练入口只保留 `usable_as_supervised_label=true`、`numbering_verified_by_sequence=true`、无 integrity flags 的记录。
- readiness 增加 strict supervised rows。

验证：

- repaired input rows：500。
- strict supervised rows：25。
- excluded rows：475。
- excluded reason：`not_usable_as_supervised_label`。
- strict 标签分布：go 8、watch 9、no_go 8。

限制：

- 当前 strong supervised rows 仍远低于 100 条门槛。
- strict baseline 只能作为入口 sanity check，不能作为模型质量依据。

## 1.1.0-safe-pipeline-runner

状态：本地安全训练流水线 runner 完成。

内容：

- strict training entrypoint checker。
- deterministic safe training pipeline runner。
- manifest/readiness 按固定顺序串行生成。

验证：

- `check_safe_training_entrypoint.py`：25 rows，0 failures，`safe_for_training_pipeline=true`，`safe_for_model_claim=false`。
- `run_safe_training_pipeline.py`：16 steps run，0 failed。

限制：

- runner 只保证本地治理流水线顺序和入口安全，不解决样本不足或结构缓存缺失。

## 1.2.0-curation-template-status

状态：本地回源模板和批次状态跟踪完成。

内容：

- P0 batch decision templates。
- batch status report。
- dashboard 增加 decision coverage。
- safe pipeline runner 扩展为 18 steps。

验证：

- decision templates：5 files、125 rows。
- batch status：5 batches、125 rows、0 decided rows、coverage 0.0。
- safe pipeline：18 steps run、0 failed。

限制：

- template 文件不作为真实决策输入。
- 真实覆盖率只由 `numbering_curation_decisions.jsonl` 决定。

## 1.3.0-master-readiness-board

状态：本地待建清单总控看板完成。

内容：

- master readiness board。
- 七条工作流状态、阻断原因和下一步命令。
- safe pipeline runner 扩展为 19 steps。

验证：

- `reports/master_readiness_board.json` 已生成。
- overall status：`blocked_for_model_claim`。
- ready streams：0/7。
- safe pipeline：19 steps run、0 failed。

限制：

- 看板只汇总状态，不自动补数据、下载结构或修改平台代码。

## 1.4.0-workstream-scaffolds

状态：本地待建工作流脚手架完成。

内容：

- domain interval repair schema and queue。
- MSA/conservation manifest and target scaffold。
- experiment feedback schema and local template。
- master readiness board 接入 domain/MSA/feedback 状态。

验证：

- domain repair queue：1000 queued，invalid domain rows 1942。
- MSA targets：158，present 0，missing 158。
- experiment feedback local rows：0，reviewed numbered rows 0。
- safe pipeline：22 steps run、0 failed。

限制：

- 不包含真实 domain 区间修复。
- 不包含真实 MSA 或保守性特征。
- 不包含真实 KWB 实验反馈数据。

## 1.5.0-domain-curation-operations

状态：本地域区间审校运营链路完成。

内容：

- domain repair queue 批次化。
- domain decision template、validation、apply、status。
- curation dashboard、manifest 和 safe pipeline 接入。

验证：

- domain queue：1000 rows。
- domain batches：5，覆盖 250 rows。
- decision rows：0，coverage 0.0。
- usable position-feature rows：0。
- safe pipeline：27 steps run、0 failed。

限制：

- 模板不是人工决策，不能进入 apply。
- 真实 domain 区间仍需人工或可信程序回源。

## 1.6.0-structure-workflow-gate

状态：本地结构工作流门控回归完成。

内容：

- 上传结构优先级门控。
- 编号未确认阻断结构依赖分析。
- 仅序列等待 ESMFold 后再输出结构结论。
- session/conversation/turn 级 task_ref 隔离。
- master readiness 标记为 `local_gate_passed`，不代表生产接入完成。

验证：

- safe pipeline：28 steps run、0 failed。
- structure workflow assertions：5/5 passed。
- benchmark：6/6 passed。
- JSON：69 files；JSONL：47 files、6459 rows，全部解析通过。

限制：

- 尚未修改生产后端、前端或服务器。
- 真实结构服务和平台 ToolRegistry 仍需后续授权接入。

## 1.7.0-local-tool-adapter

状态：本地 KWB 工具适配器完成。

内容：

- gate 与规则 MVP 的本地组合适配器。
- blocked/pending/completed 结果状态。
- session/conversation/turn 上下文、task_id 和事件输出。
- 纳入 safe pipeline、manifest 和 readiness。

验证：

- 上传结构不触发 ESMFold：通过。
- 编号未确认不调用 KWB：通过。
- 仅序列在预测完成前返回 pending：通过。
- 当前 ESMFold 结构完成后调用 KWB：通过。

限制：

- 适配器只调用本地规则 MVP。
- 尚未修改生产 ToolRegistry、AgentOrchestrator 或前端。

## 1.8.0-blocker-execution-wave

状态：六项模型质量阻塞完成本地执行准备。

内容：

- 475 条编号回源 retrieval packets。
- 1942 条 domain interval 全量审校批次。
- 500 条结构获取清单和本地缓存目录。
- 158 条 MSA FASTA 输入。
- 实验反馈 intake 校验。
- 五头模型 scaffold 和 fail-closed readiness。

验证：

- safe pipeline：34 steps run、0 failed。
- benchmark：6/6 passed。
- data lake：189 artifacts、0 missing。
- JSON/JSONL：77 个 JSON、126 个 JSONL、11760 行 JSONL 解析通过。

限制：

- 未执行真实 UniProt/文献映射。
- 未下载或伪造结构文件。
- 未生成伪造 MSA、保守性或实验反馈。
- 五头模型仍不能进行质量声明。

## 1.9.0-local-deployment

状态：门控版 KWB-EnzymeDesigner 已部署到本机。

验证：

- `http://127.0.0.1:8766/health` 返回 `ok`。
- 上传结构请求返回 `completed`。
- 仅序列请求返回 `pending_structure`。
- HTTP smoke 通过。

限制：

- 仅本机 local-only 服务。
- 未修改线上后端、前端或服务器。
- 当前仍是规则 MVP 和门控适配器，不是已完成质量声明的五头模型。

## 2.0.0-analysis-constraint-policy

状态：酶改造分析约束规则包完成。

内容：

- 固定“性质预测先行、数据库证据分层融合、编号/结构门控后再排序突变位点”的分析顺序。
- 固定工具调用展示字段和执行前确认要求。
- 明确 Rosetta/PyRosetta/FoldX ΔΔG 当前未作为可执行工具集成。
- 固定 ΔΔG 阈值和人工核实区间。
- 固定 6-10 个单点突变优先的湿实验验证流程。

验证：

- safe pipeline：104 steps run、0 failed。
- benchmark：6/6 passed。
- safe training entrypoint：25 rows、0 failures、safe_for_model_claim false。
- data lake：463 artifacts、0 missing。

限制：

- 未执行 Rosetta ddG、GROMACS、对接或湿实验。
- 未创建 reviewed decisions、训练标签或 customer delivery approval。
- 不改变 release_ready=false 和 model quality claim blocked 状态。

## 2.1.0-model-quality-unlock

状态：模型质量解锁条件整理完成。

内容：

- reviewed numbering、MSA/conservation、真实实验反馈、ddG backend、生产同步授权拆成独立 blocker。
- 每条 blocker 都绑定 required artifacts、validator reports 和 forbidden shortcuts。
- 明确当前仍不能做模型质量声明。

验证：

- safe pipeline：105 steps run、0 failed。
- benchmark：6/6 passed。
- safe entrypoint：25 rows、0 failures、safe_for_model_claim false。
- data lake：467 artifacts、0 missing。
- release manifest：`release_ready=false`。

限制：

- 不等于解锁模型质量。
- 不等于 Rosetta/FoldX 已集成。
- 不等于生产同步已授权。

## 2.2.0-advanced-scaffold

状态：顶级模型高级代码底座完成。

内容：

- 新增高级特征合同和预测合同。
- 新增 `kwb_enzyme_designer_advanced_model.py` 原型。
- 固定 PLM、MSA、structure GNN、ddG、wet-lab feedback、多头、Pareto、uncertainty 架构槽位。
- 新增高级模型架构报告和 demo 输出。

验证：

- safe pipeline：106 steps run、0 failed。
- benchmark：6/6 passed。
- safe entrypoint：25 rows、0 failures、safe_for_model_claim false。
- data lake：474 artifacts、0 missing。
- release manifest：`release_ready=false`。

限制：

- scaffold-only，不是训练好的神经网络。
- 未调用 ESM/SaProt/ThermoMPNN/Rosetta/FoldX。
- 不改变模型质量声明 blocked 状态。

## 2.12.0-benchmark-ddg-gates

状态：benchmark score cache 局部解锁，ddG backend gate 接线完成。

内容：

- 新增 `KWB strict mutation holdout` 本地 benchmark 四件套并写入 intake。
- 新增 Rosetta/PyRosetta/FoldX foreign registry 条目。
- 新增 ddG backend config、result schema、readiness、execution plan 和 fail-closed adapter。
- pipeline、data lake、release manifest、model-quality unlock 和 top-tier board 已接线。

验证：

- safe pipeline：123 steps run、0 failed。
- local benchmark：6/6 passed。
- safe entrypoint：25 rows、safe_for_model_claim false。
- benchmark score cache：valid_rows 1、invalid_rows 13、ready_for_model_claim false。
- ddG backend：adapter_integrated true、ready_backend_count 0、executable_ddg_backend_ready false。
- data lake：887 artifacts。
- release manifest：`release_ready=false`。

限制：

- benchmark primary holdout 只有 1 行，不能支撑模型质量声明。
- Rosetta/PyRosetta/FoldX 未下载、未安装、未执行。
- 未生成真实 ddG、未增加 reviewed numbering、未导入 training-eligible 湿实验反馈。

## 2.13.0-numbering-feedback-audits

状态：reviewed numbering 自动解锁审计和实验反馈可训练性审计完成。

内容：

- 新增 FireProtDB numbering evidence builder 和综合 auto-unlock audit。
- 新增 experiment feedback trainability audit，只读审计最高优先级历史反馈源。
- safe pipeline、data lake manifest、local release manifest 已接线。
- Matvenus 历史 VenusREM result.csv 链接已识别，但远端 OSS SSL 连接失败，未缓存 CSV。

验证：

- safe pipeline：125 steps run、0 failed。
- safe entrypoint：25 rows、safe_for_model_claim false。
- numbering auto-unlock：candidate_rows 8、ready_for_decision_draft_rows 0、safe_to_auto_promote false。
- FireProtDB evidence：exact_match_rows 0、failed_query_rows 2。
- feedback trainability：audited_rows 4、training_eligible_rows 0。
- data lake：901 artifacts。
- release manifest：`release_ready=false`。

限制：

- 未写入 reviewed numbering decisions。
- 未写入 wet-lab feedback intake。
- 未提升 strict supervised rows。
- 未生成 ddG 或外部 benchmark scorecard。

## 2.14.0-strict-msa-feature-path

状态：MSA conservation 已接入 strict verified 训练特征路径。

内容：

- 新增 `build_strict_msa_site_features.py`。
- 生成 strict MSA site feature table，25/25 strict rows 覆盖，missing_rows 0。
- 新增 repaired supervised MSA baseline artifact。
- MQ-U002 `msa_conservation` 从 blocked 调整为 ready_to_verify。
- safe pipeline、data lake manifest、release manifest 已接线。

验证：

- safe pipeline：127 steps run、0 failed。
- strict MSA features：feature_rows 25、missing_rows 0、cache_validation_ready true。
- MSA baseline：rows 25、features 88、validation_accuracy 0.0、test_accuracy 1.0。
- model quality unlock：blocked_requirements 4、ready_to_verify_requirements 1、model_quality_ready false。
- data lake：905 artifacts。
- release manifest：`release_ready=false`。

限制：

- test split 只有 1 行，baseline 结果没有统计力。
- 不增加 strict supervised rows。
- 不解锁 reviewed numbering、wet-lab feedback、ddG backend 或 benchmark claim。
- `safe_for_model_claim=false` 保持。

## 2.15.0-conservative-structure-chain-evidence

状态：结构链证据部分解锁，模型质量声明继续阻断。

内容：

- 新增 `build_structure_chain_evidence_audit.py`，用本地 PDB DBREF/SEQADV/REMARK 465 解释候选链与 UniProt 的差异。
- 追加 reviewed structure chain decisions：`1A2N` 和 `11YV`。
- 结构链 mapping decisions 从 12 增至 14，curated coordinate mappings 从 12 增至 14。
- reviewed structure graph cache 从 12 增至 14，全部通过校验。
- safe pipeline、data lake manifest、local release manifest 已接线。

验证：

- structure evidence audit：84 rows、strict_auto_promotable_rows 4。
- structure decision validation：decision_rows 14、valid_rows 14、invalid_rows 0。
- structure graph validation：valid_rows 14、invalid_rows 0、ready_for_coordinate_feature_use true。
- safe pipeline：128 steps run、0 failed。
- local benchmark：6/6 passed。
- safe entrypoint：25 rows、safe_for_model_claim false。
- data lake：909 artifacts。
- release manifest：`release_ready=false`。

限制：

- 结构链目标仍为 14/25，尚未解锁 P43-A002。
- 不增加 reviewed numbering rows，strict supervised rows 仍为 25/100。
- 不导入 wet-lab feedback，不生成 ddG backend artifact。
- 不改变 `model_quality_ready=false`、`safe_for_model_claim=false` 或 `release_ready=false`。

## 2.16.0-dbref-structure-chain-target

状态：结构链 reviewed coordinate target 达标，模型质量声明继续阻断。

内容：

- 新增 `build_structure_chain_dbref_evidence_audit.py`。
- 对 fragment/multi-chain 结构使用 PDB DBREF UniProt 区间证据做保守审计。
- 追加 11 条 reviewed structure chain decisions，使 reviewed/usable chain mappings 达到 25。
- reviewed structure graph cache 增至 25，全部通过校验。
- safe pipeline、data lake manifest、local release manifest 已接线。

验证：

- DBREF evidence audit：500 rows、strict_auto_promotable_rows 20；本轮追加 11 后剩余 9。
- structure decision validation：decision_rows 25、valid_rows 25、invalid_rows 0。
- structure graph validation：valid_rows 25、invalid_rows 0、ready_for_coordinate_feature_use true。
- next unlock blocker matrix：blocked_actions 10、completion_ready_actions 2，structure_chain_mapping blocker 已消失。
- safe pipeline：129 steps run、0 failed。
- local benchmark：6/6 passed。
- safe entrypoint：25 rows、safe_for_model_claim false。
- data lake：922 artifacts。
- release manifest：`release_ready=false`。

限制：

- DBREF fragment 结构只覆盖 DBREF UniProt 区间；未覆盖 canonical 区间不能用于坐标结论。
- 不增加 reviewed numbering rows，strict supervised rows 仍为 25/100。
- 不导入 wet-lab feedback，不生成 Rosetta/PyRosetta/FoldX ddG artifact。
- 不改变 `model_quality_ready=false`、`safe_for_model_claim=false` 或 `release_ready=false`。

## 2.17.0-domain-multi-occurrence-sidecar

状态：domain repeated Pfam occurrence 已用 sidecar 解锁 feature-use blocker。

内容：

- 新增 `scripts/build_domain_multi_occurrence_features.py`。
- 生成 `datasets/curation/domain_multi_occurrence_features.jsonl`，保留 155 条 repeated Pfam 的全部 occurrence。
- `build_domain_interpro_review_packets.py` 现在区分 raw unresolved 与 feature-use unresolved。
- 过期 domain unresolved packets 会在重建时清理，避免 manifest 收录旧批次。
- safe pipeline、data lake manifest、master board 和 local release manifest 已接线。

验证：

- multi-occurrence features：candidate rows 155、feature_rows 155、invalid_rows 0、ready_for_feature_use true。
- domain review packets：raw_unresolved_rows 157、sidecar_resolved_rows 155、unresolved_rows 2。
- domain decisions：1785 valid、0 invalid；single-interval curated rows 保持 1785。
- safe pipeline：130 steps run、0 failed。
- local benchmark：6/6 passed。
- safe entrypoint：25 rows、safe_for_model_claim false。
- next unlock：completion_ready_actions 3、blocked_actions 9。
- data lake：920 artifacts、0 missing。
- release manifest：`release_ready=false`。

限制：

- sidecar 不等于人工 occurrence selection，也不写入 single-interval reviewed decision。
- 剩余 2 条 no_exact_pfam_interval 仍需人工或新增证据。
- 不增加 reviewed numbering rows，strict supervised rows 仍为 25/100。
- 不导入 wet-lab feedback，不生成 Rosetta/PyRosetta/FoldX ddG artifact。
- 不改变 `model_quality_ready=false`、`safe_for_model_claim=false` 或 `release_ready=false`。

## 2.18.0-label-provenance-hard-gate

状态：最硬标签门槛已从“编号修复”上移为“真实来源 provenance + reviewed numbering”。

内容：

- 新增 `scripts/audit_label_provenance.py`。
- 新增 claim-eligible strict table 和 synthetic/unreceipted evidence table。
- safe entrypoint、training readiness、claim readiness、model-quality unlock、master board、manifest/release 已纳入 label provenance gate。
- 当前工程 strict rows 仍可用于本地 smoke，但不能支撑模型质量声明。

验证：

- label provenance：strict_rows 25、claim_eligible_rows 0、synthetic_or_unreceipted_rows 25。
- provenance flags：`synthetic_generate_sample_data_pmids_310xxxxx=25`、`no_raw_source_checksum_or_reviewed_source_receipt=25`。
- safe pipeline：131 steps run、0 failed。
- safe entrypoint：safe_for_training_pipeline true、safe_for_model_claim false。
- model quality unlock：blocked_requirements 4、model_quality_ready false。
- claim matrix：model_quality_claim 缺少 claim-eligible real supervised rows >=100 和 no synthetic/unreceipted strict labels。
- data lake：923 artifacts、0 missing。
- release manifest：`release_ready=false`。

限制：

- 不删除样例数据，不修改 SQLite。
- 不把 synthetic ProThermDB stability rows 当真实训练标签。
- 不写 reviewed numbering decisions，不增加 strict supervised rows。
- 真正解锁需要真实 ProTherm/FireProt/KWB wet-lab source artifact、checksum/receipt、编号校验和 >=100 claim-eligible rows。
- 不改变 `model_quality_ready=false`、`safe_for_model_claim=false` 或 `release_ready=false`。

## 2.19.0-venus15b-feedback-intake

状态：Venus-15B 真实历史反馈已接入 feedback intake。

内容：

- 新增 `scripts/import_venus15b_feedback.py`。
- 读取用户确认的真实实验来源 `/Venus-15B淀粉酶项目`。
- 校验 15B 序列中 E331Q 编号：position 331 residue E，numbering_verified true。
- 写入 `datasets/feedback/experiment_feedback.local.jsonl` 1 条 KWB historical activity observation。
- 记录 sequence/background/structure sha256。
- safe pipeline、data lake manifest、local release manifest 已接线。

验证：

- feedback intake：input_rows 1、valid_rows 1、training_eligible_rows 1、invalid_rows 0。
- Venus import：feedback_rows_after 1、numbering_verified true。
- safe pipeline：132 steps run、0 failed。
- next unlock：completion_ready_actions 4、blocked_actions 8。
- data lake：924 artifacts、0 missing。
- release manifest：`release_ready=false`。

限制：

- E331Q 记录是 pH4.5/pH6.0 活性比值的定性历史观察。
- 源目录未提供 numeric ratio、replicate、QC、instrument 或 raw plate signal。
- plate feedback 仍为 0，P43-A006 仍 blocked。
- 不增加 claim-eligible supervised stability rows，不解决 synthetic ProTherm label gate。
- 不改变 `model_quality_ready=false`、`safe_for_model_claim=false` 或 `release_ready=false`。

## 2.20.0-venus15b-experiment-asset-gate

状态：Venus-15B 真实实验来源已增加资产级证据审计和训练用途分层。

内容：

- 新增 `scripts/audit_venus15b_experiment_assets.py`。
- `import_venus15b_feedback.py` 的 E331Q row 增加 `data_granularity=qualitative_historical_observation`、`quantitative_assay_available=false`、`plate_level_available=false`。
- `validate_experiment_feedback_intake.py` 新增 qualitative/numeric training eligibility 分层。
- safe pipeline、data lake manifest、local release manifest、model quality unlock report 已接线。

验证：

- Venus-15B asset audit：source_files_scanned 18、candidate_mutation_rows 4、numbering_verified_mutation_rows 4。
- 真实反馈颗粒度：qualitative_feedback_rows 1、numeric_training_eligible_rows 0、plate_training_eligible_rows 0、tabular_assay_file_count 0。
- feedback intake：input_rows 1、valid_rows 1、training_eligible_rows 1、qualitative_training_eligible_rows 1、numeric_training_eligible_rows 0。
- safe pipeline：133 steps run、0 failed。
- next unlock validation：completion_ready_actions 4、blocked_actions 8。
- data lake：926 artifacts、0 missing。
- release manifest：`release_ready=false`。

限制：

- 把 Venus-15B 目录作为真实实验来源，但只把已观察字段放入对应训练门控。
- E331Q 仍是定性历史观察，不是数值活性标签，也不是 plate/well 原始实验数据。
- S265D、D405N、M204H 目前只做编号 verified 和设计候选记录，不写为实验反馈。
- 不伪造 activity ratio、replicate、QC、instrument、raw_signal 或 normalized_activity。
- 不增加 claim-eligible supervised stability rows，不解决 ddG backend/license/governance blockers。
- 不改变 `model_quality_ready=false`、`safe_for_model_claim=false` 或 `release_ready=false`。

## 2.21.0-venus15b-source-path-correction

状态：Venus-15B 真实实验来源路径已纠偏。

内容：

- 用户最新确认真实实验数据目录为 `AI大模型/Venus-15B淀粉酶项目`。
- `scripts/import_venus15b_feedback.py` 和 `scripts/audit_venus15b_experiment_assets.py` 默认读取该目录。
- 当前源文件为 3 个：`15B-AAP-noCa.pdb`、`淀粉酶15B序列.txt`、`淀粉酶背景.txt`。

验证：

- Venus-15B asset audit：source_files_scanned 3、qualitative_feedback_rows 1、numeric_training_eligible_rows 0、plate_training_eligible_rows 0。
- Venus import：feedback_rows_after 1、numbering_verified true。
- feedback intake：input_rows 1、valid_rows 1、training_eligible_rows 1。

限制：

- 旧父目录资产数量不再作为本轮 Venus-15B 真实实验资产计数。
- E331Q 仍是定性历史观察，不是数值 assay label 或 plate-level row。
- 不伪造 activity ratio、replicate、QC、raw_signal 或 normalized_activity。

## 2.22.0-thermompnn-source-gate

状态：ThermoMPNN 源码、许可和默认权重已缓存；运行依赖仍未解锁。

内容：

- 官方仓库缓存到 `cache/external/ThermoMPNN`。
- 新增 `scripts/build_thermompnn_local_source_manifest.py` 输出 source/license/model-weight/runtime readiness。
- `config/foreign_tool_registry.local.example.json` 和 `config/ddg_backend.local.example.json` 已注册 ThermoMPNN proxy backend。

验证：

- ThermoMPNN source report：source_license_model_ready true、runtime_dependency_ready false、ready_for_local_inference false。
- 缺失模块：`torch`、`pandas`、`numpy`、`tqdm`、`omegaconf`、`Bio`、`pytorch_lightning`、`torchmetrics`、`wandb`、`joblib`。
- pip 安装基础依赖失败：PyPI timeout/SSL EOF，未获取 numpy 版本列表。
- ddG readiness：ready_backend_count 0、executable_ddg_backend_ready false、proxy_ddg_backend_ready false、one_ddg_backend_ready false。

限制：

- ThermoMPNN 只能作为 future predicted ddG proxy，不是 Rosetta/PyRosetta/FoldX physics ddG。
- 未生成 mutation-level ΔΔG artifact。
- 不改变 `model_quality_ready=false`、`safe_for_model_claim=false` 或 `release_ready=false`。

## 2.23.0-thermompnn-venus15b-proxy-ddg-smoke

状态：Venus-15B ThermoMPNN proxy ddG smoke artifact 已生成。

内容：

- 新增 `scripts/run_thermompnn_venus15b_smoke.py`。
- ThermoMPNN smoke 使用 `.venv-thermompnn/bin/python`，并在运行时覆盖官方 `local.yaml` 中作者机器路径。
- 输出 `parameters.json`、`input_structure.sha256`、`mutation_list.json`、`ddg_table.json`、`runtime.log` 和 `reports/thermompnn_venus15b_smoke_report.json`。
- `build_ddg_backend_readiness.py` 现在要求 ThermoMPNN smoke artifact ready 后才放行 proxy backend。

验证：

- ThermoMPNN source/runtime：source_license_model_ready true、runtime_dependency_ready true、ready_for_local_inference true。
- Venus-15B smoke：status completed、mutation_rows 4、ready_as_proxy_ddg_artifact true。
- proxy ΔΔG：S265D +1.220178、D405N -0.545105、E331Q +0.144482、M204H +0.631782 kcal/mol。
- ddG readiness：ready_backend_count 1、proxy_ddg_backend_ready true、one_ddg_backend_ready true、executable_ddg_backend_ready false。
- safe pipeline：135 steps run、0 failed。
- data lake：935 artifacts。
- release manifest：artifact_count 935、release_ready false。

限制：

- ThermoMPNN 是 predicted ddG proxy，不是 Rosetta/PyRosetta/FoldX physics ddG。
- 这些 ΔΔG 不是湿实验稳定性标签，不能作为模型质量声明。
- `model_quality_ready=false`、`safe_for_model_claim=false`、`release_ready=false` 保持。

## 2.24.0-ddg-model-quality-gate-reconciliation

状态：ddG proxy backend 已反映到模型质量解锁报告。

内容：

- `build_model_quality_unlock_requirements.py` 现在在 `one_ddg_backend_ready=true` 时把 MQ-U003 标为 ready_to_verify。
- `run_safe_training_pipeline.py` 末尾补跑 claim/model-quality/data-lake/release，避免报告读取上一轮 pipeline 状态。

验证：

- ddG readiness：ready_backend_count 1、proxy_ddg_backend_ready true、one_ddg_backend_ready true、executable_ddg_backend_ready false。
- model quality unlock：blocked_requirements 3、ready_to_verify_requirements 2、model_quality_ready false。
- claim matrix：claims_allowed 2、claims_blocked 9。
- safe pipeline：139 steps run、0 failed。
- local release：artifact_count 935、release_ready false。

限制：

- MQ-U003 ready_to_verify 表示 ThermoMPNN proxy baseline 可审计。
- Rosetta/PyRosetta/FoldX 仍未授权/未安装/未产出 physics ddG。
- `model_quality_ready=false`、`safe_for_model_claim=false`、`release_ready=false` 保持。

## 2.25.0-external-stability-label-source-audit

状态：外部稳定性真实标签候选源已审计，但未导入训练。

内容：

- 新增 `scripts/audit_external_stability_label_sources.py`。
- 审计 ThermoMPNN 随仓库 `data_all/**/*.csv` 的 FireProt、Megascale、S669、SSYM、Myoglobin/P53 等稳定性数据。
- 生成 `reports/external_stability_label_source_audit_report.json` 和 `datasets/curation/external_stability_label_source_candidates.jsonl`。

验证：

- source_file_count 11。
- total_rows 280089。
- total_usable_numeric_rows 280089。
- ready_import_candidate_files 10。
- claim_eligible_rows_now 0。
- safe pipeline：140 steps run、0 failed。
- data lake：937 artifacts。
- local release：artifact_count 937、release_ready false。

限制：

- 审计只证明存在外部真实稳定性候选源。
- 未完成 KWB schema mapping、ddG 方向归一、license scope 选择、leakage review 或 reviewed import receipt。
- 不增加 claim-eligible supervised rows。
- `model_quality_ready=false`、`safe_for_model_claim=false`、`release_ready=false` 保持。

## 2.26.0-fireprot-curated-import-candidates

状态：FireProt curated 稳定性标签候选已形成受控导入包。

内容：

- 新增 `scripts/build_fireprot_curated_stability_import_candidates.py`。
- 生成 `datasets/curation/fireprot_curated_stability_import_candidates.jsonl`。
- 生成 `reports/fireprot_curated_stability_import_candidate_receipt.json`。
- 生成 `reports/fireprot_curated_stability_import_leakage_report.json`。

验证：

- candidate_rows 5067。
- claim_eligible_rows_now 0。
- strict_supervised_overlap_rows 0。
- kwb_strict_holdout_overlap_rows 0。
- safe pipeline：141 steps run、0 failed。
- data lake：940 artifacts。
- local release：artifact_count 940、release_ready false。

限制：

- 候选行还不是 KWB supervised training rows。
- 未完成 ddG 方向归一、KWB schema mapping、license scope 选择或 reviewed import approval。
- 不增加 claim-eligible supervised rows。
- `model_quality_ready=false`、`safe_for_model_claim=false`、`release_ready=false` 保持。

## 2.27.0-fireprot-ddg-direction-normalization

状态：FireProt curated 候选已完成 ddG 方向归一候选层处理。

内容：

- 新增 `scripts/build_fireprot_ddg_direction_normalization.py`。
- 生成 `datasets/curation/fireprot_curated_stability_direction_normalized_candidates.jsonl`。
- 生成 `reports/fireprot_curated_stability_direction_normalization_report.json`。

验证：

- candidate_rows 5067。
- direction_normalized_rows 5067。
- claim_eligible_rows_now 0。
- dTm sanity：62 行方向一致、11 行冲突、3 行 zero、4991 行无 dTm reference。
- safe pipeline：142 steps run、0 failed。
- data lake：942 artifacts。
- local release：artifact_count 942、release_ready false。

限制：

- direction normalization 不等于 reviewed import approval。
- 仍缺 license scope、reviewed import receipt、KWB supervised schema mapping 和 approved leakage policy。
- 不增加 claim-eligible supervised rows。
- `model_quality_ready=false`、`safe_for_model_claim=false`、`release_ready=false` 保持。

## 2.28.0-fireprot-kwb-schema-mapping-candidates

状态：FireProt curated 候选已映射为 KWB supervised schema draft。

内容：

- 新增 `scripts/build_fireprot_kwb_schema_mapping_candidates.py`。
- 生成 `datasets/curation/fireprot_curated_kwb_schema_mapping_candidates.jsonl`。
- 生成 `reports/fireprot_curated_kwb_schema_mapping_report.json`。

验证：

- input_rows 5067。
- mapped_candidate_rows 5067。
- manual_review_required_rows 5048。
- claim_eligible_rows_now 0。
- ready_for_training_import_rows 0。
- safe pipeline：143 steps run、0 failed。
- data lake：944 artifacts。
- local release：artifact_count 944、release_ready false。

限制：

- schema mapping 是候选层，不是 reviewed import approval。
- 仍缺 license scope、reviewed import receipt、approved leakage policy 和 KWB numbering review。
- 不增加 claim-eligible supervised rows。
- `model_quality_ready=false`、`safe_for_model_claim=false`、`release_ready=false` 保持。

## 2.29.0-fireprot-import-leakage-review

状态：FireProt 导入候选已生成 split proposal 和 leakage review。

内容：

- 新增 `scripts/build_fireprot_import_leakage_review.py`。
- 生成 `datasets/curation/fireprot_curated_import_split_proposal.jsonl`。
- 生成 `reports/fireprot_curated_import_leakage_review_report.json`。

验证：

- candidate_rows 5067。
- group_count 75。
- group_split_leakage_count 0。
- strict_supervised_overlap_rows 0。
- kwb_strict_holdout_overlap_rows 0。
- automated_leakage_checks_passed true。
- duplicate_mutation_key_count 2133。
- safe pipeline：144 steps run、0 failed。
- data lake：946 artifacts。
- local release：artifact_count 946、release_ready false。

限制：

- 自动 leakage check 通过不等于 approved leakage policy。
- duplicate mutation keys 需要 dedup/aggregation policy。
- 仍缺 license scope、reviewed import receipt 和 KWB numbering review。
- 不增加 claim-eligible supervised rows。
- `model_quality_ready=false`、`safe_for_model_claim=false`、`release_ready=false` 保持。
