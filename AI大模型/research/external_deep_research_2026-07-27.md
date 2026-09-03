# 外部全面深入调研：KWB-EnzymeDesigner

日期：2026-07-27

范围：仅基于公开论文、官方仓库、官方文档和公开数据库页面；不下载、不安装、不部署。

## 结论

KWB 不该再找“一个更大的模型”来兜底。更合适的路线是：

1. `MSA / conservation`
2. `sequence prior`
3. `structure / affinity`
4. `mutation effect / stability`
5. `enzyme function / kinetics / variant databases`
6. `wet-lab feedback`

主控仍应是 GPT-5.6，专业能力由可审计工具链承接。

## 1) MSA / Conservation

### 首选：MMseqs2

- 官方仓库给出本地二进制、Docker、brew、conda 等安装路径。
- 许可为 MIT，商业研发使用边界最清晰。
- 对当前 KWB 的价值最高，因为它直接对应 `MSA 0/158` 阻塞。

### 次选 / 对照：ColabFold、HH-suite、HMMER

- ColabFold 的工作流明确以 MMseqs2 构造 MSA，并支持 jackhmmer。
- HH-suite / HHblits 更适合远缘同源和 profile-profile 检测。
- HMMER / jackhmmer 适合作为 profile HMM 对照路线。

### 取舍

- 第一落地点应是 `MMseqs2 + 本地数据库或可信 cache`。
- HH-suite / HMMER 只作为二线增强，不应抢第一解阻点。

## 2) Structure / Affinity

### 首选：Boltz-2

- 官方仓库为 MIT license。
- 公开描述覆盖 complex structure 和 binding affinity prediction。
- 对酶底物 fit、口袋和复合物证据最直接。

### 许可/算力门控：Chai-1

- Hugging Face model card 标注 Apache-2.0。
- 官方安装页要求 Linux + CUDA + bfloat16，推荐 A100/H100。
- 可做结构/复合物候选对照，但不应默认进入生产主链路。

### 只做对标：AlphaFold 3

- 代码仓库是 Apache-2.0，但模型参数受额外 Terms of Use 约束。
- 官方明确 server 版为 non-commercial。
- 适合作为 benchmark，不适合作为 KWB 商业默认后端。

### 开放结构后端：OpenFold / ESM

- OpenFold 代码开源，但 pretrained parameters 仍有单独条款。
- ESM 代码与生态是开放的，适合作为 sequence prior / structure prior。
- 这类工具更适合做先验和对照，不适合掩盖真实结构与配体证据缺口。

## 3) Mutation Effect / Stability

### 主 benchmark：ProteinGym

- ProteinGym 是突变效应评测的核心 benchmark 之一。
- 适合评估 mutation ranking、zero-shot / supervised 泛化和稳定性排序。
- 不应把 benchmark 数据直接当训练标签回灌。

### 稳定性 baseline：ThermoMPNN

- 适合作为 ddG proxy baseline。
- 输出只能当证据、特征或过滤信号，不可直接当实验标签。

### 功能一致性：CLEAN / SaProt

- CLEAN 更偏 EC / function prediction，适合作为功能偏移检查。
- 它有研究用途许可约束，适合研究位，不适合直接默认生产化。
- SaProt 属于结构感知序列建模路线，适合在有结构输入时补充先验。

### 取舍

- KWB 应把突变排序、稳定性、功能一致性拆开，不要压成一个分数。
- `ProteinGym + ThermoMPNN + CLEAN` 比单纯再堆一个生成模型更有工程价值。

## 4) Enzyme Function / Kinetics / Variant Databases

### UniProt

- 适合作为序列、注释和版本回源主干。
- 官方帮助页强调高质量、自由可访问的蛋白序列和功能信息。

### BRENDA

- 适合作为酶功能主集合之一。
- 在线版页面给出 CC BY 4.0 信息。

### SABIO-RK

- 适合作为 curated kinetics 数据库。
- 强项是 rate equations、parameters 和 conditions。
- 我没有在本轮证据里看到足够明确的可再分发许可说明，后续应单独核对。

### MaveDB

- 最值得借鉴的是它的数据组织方式：variant mapping、score sets、结构化元数据。
- 软件为 AGPLv3，数据默认 CC0。
- 对 KWB 来说，它是 feedback loop schema 的最佳对照对象。

### FireProtDB / ProThermDB

- FireProtDB 2.0 是更现代的 curated stability 参考。
- ProThermDB 更像历史稳定性基准，适合对照，不适合无脑混训。
- 两者都需要按来源、实验条件、编号与测量方式再清洗一次。

## 5) Closed-loop / Product Pattern

### Cradle

- 强调实验驱动、多目标优化和数据闭环。
- 更像“平台 + 工作流 + 实验反馈”系统，而不是单一模型。

### Arzeda

- 体现的是设计、实验和制造一体化。
- 说明酶设计最终还是要落到可执行的实验与工艺链路。

### Profluent

- 强调基础模型与实验/工程闭环结合。
- 对 KWB 的启发是：模型输出必须绑定审计、版本和实验来源。

### 取舍

- KWB 要学的是闭环结构，不是品牌故事。
- 必须建设 plate-level feedback、权限、审计、API 和版本追踪。

## 6) GitHub / Google 证据矩阵补强

本轮补查重点放在官方 GitHub、官方数据库文档和可验证的产品/数据库页面。结论不改变主线，但把各项的工程门槛进一步压实：

| 类别 | 工具/数据源 | 官方证据 | 许可/门槛 | KWB 结论 |
|---|---|---|---|---|
| MSA | MMseqs2 | 官方 README 标注 MIT，支持 source/static binary/Homebrew/conda/Docker；支持 `easy-search`、database workflow、UniProtKB/Swiss-Prot 等库；README 还说明 ARM64 可用，GPU 搜索需要 CUDA GPU。 | MIT；真实解阻仍需要 executable + homolog DB/cache。 | 仍是第一优先级。当前本机缺 `mmseqs` 和同源库，不能只改配置。 |
| MSA/structure | ColabFold | 官方 README 明确 `colabfold_search` 依赖 MMseqs2；大规模本地 DB 约 940GB，batch 搜索约 128GB RAM，server/fast single query 可到 768GB-1TB RAM。 | MIT；数据库和 RAM 是主要成本。 | 可作为 MSA/AF2-style 对照，但 KWB 第一解阻仍应先做 MMseqs2/cache。 |
| MSA/profile | HH-suite | 官方 README：GPL-3.0，profile HMM pairwise alignment，支持 conda/Docker/static binaries，数据库包括 Uniclust30/BFD/Pfam/SCOP/PDB70/dbCAN。 | GPL-3.0；商业集成要谨慎。 | 适合二线远缘同源/annotation 对照，不应默认进商业闭源主链。 |
| MSA/profile | HMMER | 官方 GitHub：BSD，使用 profile HMMs 搜索同源序列，被 InterPro 等 domain 数据库/注释流程使用。 | BSD；仍需安装 executable 和数据库。 | 适合 domain/profile 对照和审计，不解决当前最快的 MSA 0/158 阻塞。 |
| Structure/affinity | Boltz-2 | 官方 README：Boltz-2 joint modeling complex structures and binding affinities；code+weights MIT；CPU 可跑但明显慢，GPU 推荐；affinity 输出区分 binder probability 与 `log10(IC50)` 风格值。 | MIT，商业友好；需要 Python/GPU/MSA server 或本地 MSA。 | 结构/亲和力第一候选；输出必须标为 predicted affinity，不可当实验测量。 |
| Structure | Chai-1 | 官方 README：Apache-2.0，code+weights 可学术和商业使用；要求 Linux、Python >=3.10、CUDA+bfloat16 GPU，推荐 A100/H100/L40S，A10/A30 只适合小 complex。 | Apache-2.0；硬件门槛高。 | 可作为 Boltz-2 对照；KWB 本机 Apple Silicon 不适合作为直接运行目标。 |
| Structure benchmark | AlphaFold 3 | 官方 repo：source code Apache-2.0，但 model parameters 有独立 Terms；server 明示 non-commercial；运行区分 CPU data pipeline 和 GPU inference。 | 参数/输出条款必须单独合规；生产默认不可用。 | 只做 benchmark 或隔离评估，不进入商业默认后端。 |
| Sequence/structure prior | ESM / ESMC / ESMFold2 | 官方 Biohub repo：ESMC/ESMFold2 可通过 Biohub Platform 或 Hugging Face 跑；ESMFold2 可选 MSA，单序列模式更快；ESM Atlas 覆盖海量预测结构。 | 需逐模型核对 Hugging Face 权重许可和 API 条款。 | 做 sequence/structure prior 和 benchmark，不替代真实结构、MSA、湿实验。 |
| Mutation effect benchmark | ProteinGym | 官方 repo：DMS substitutions 约 2.7M missense variants、217 DMS assays；clinical proteins 2525；MIT license；含 MSA、AF2 structures、zero-shot/supervised score files。 | MIT；数据体量 GB 级；benchmark 不等于训练标签。 | 应作为 mutation ranking 固定评测基准，避免只看自家小样本 accuracy。 |
| Stability | ThermoMPNN | 官方 repo：GNN 预测 protein point mutants 的 thermodynamic stability change；提供 model weights 和 dataset splits；依赖 FireProt/Megascale/S669/ProtDDG benchmark 等数据。 | MIT；输入需要结构/序列准备。 | 做稳定性外部 baseline，输出作为 predicted ddG proxy，不回灌为实验标签。 |
| Function | CLEAN | 官方 repo：contrastive learning 做 EC/function prediction；仓库包含研究用途 license PDF。 | 研究用途许可，生产默认需隔离。 | 做 EC/function consistency 检查，不作为商业默认生产能力。 |
| Protein API | UniProt / EBI Proteins API | EBI Proteins REST API 可取 UniProt mapped sequence features、variation、proteomics、taxonomy、coordinates；请求限速 200 req/s/user。 | API/使用条款需遵守；适合版本化回源。 | 编号、isoform、feature 和 variation 回源主干。 |
| Structure API | RCSB PDB Data API | 官方 Data API 支持 GraphQL、REST 和 JSON Schema，查询 structures、entities、assemblies、branched entities 等。 | PDB 数据本身通常商业友好，但仍需记录版本和来源。 | 结构链映射和 mmCIF/PDB fallback 的官方回源入口。 |
| Enzyme data | BRENDA | 官方介绍页：酶功能数据主集合，online version free under CC BY 4.0；数据由生物/化学专家从文献抽取并人工核查。 | CC BY 4.0 online；下载/API/再分发仍需遵守 terms。 | 酶功能/动力学主干，但必须保留文献、条件、单位和 release。 |
| Variant feedback schema | MaveDB | GitHub 旧仓库已归档并拆分为 `mavedb-api` / `mavedb-ui`；旧仓库 AGPL-3.0。MaveDB 模式本身仍值得借鉴。 | 软件 AGPL-3.0；数据/score set 许可需逐条核对。 | 借鉴 schema/score set/variant mapping，不直接搬软件进闭源系统。 |

关键工程判断：

- `MMseqs2` 是最短路径，但不是“装上二进制就完成”：必须同时配置真实 homolog database 或可信 cache，并把 database release 写进 manifest。
- `Boltz-2` 的许可和能力最适合先评估；`Chai-1` 许可友好但硬件路径不适合当前 Mac 本机；`AlphaFold 3` 参数/Server 条款决定它只能在隔离 benchmark 位。
- `ProteinGym`、`ThermoMPNN`、`CLEAN` 应分别承担 benchmark、stability proxy、function consistency 三个角色，不应混成一个神秘总分。
- `BRENDA`、`SABIO-RK`、`UniProt`、`RCSB`、`MaveDB` 的共同要求是版本、许可、单位、条件、编号和来源必须结构化；否则导入越多，训练污染越大。

## 7) 第三轮补强：设计后端、kinetics API、闭环产品

### Ligand-aware design

- `LigandMPNN` 官方 GitHub/PyPI 均指向 MIT license，核心价值是带 ligand / DNA / RNA / metal / context atoms 的 sequence design 和 side-chain packing。
- 它适合 KWB 的“底物/口袋约束下候选生成”，但前提是结构链映射、配体识别、底物坐标和 active-site residue set 已经审校。
- 它不适合直接给 Go/No-Go；合理输出是候选序列、多样性、固定残基约束、side-chain clash/packing 风险和 ligand-context 依赖说明。

### Rosetta / PyRosetta

- Rosetta 能覆盖能量函数、结构设计、docking、remodeling 等成熟 workflow，但官方许可明确不是 OSI open source；商业用途需要 University of Washington CoMotion 商业许可。
- 对 KWB 来说，Rosetta 只能放在“license-reviewed optional backend”位置；没有商业许可前，不能作为默认商业推理链路，也不能隐藏在自动工具后端里。
- 如果未来采购商业许可，它更适合承担高精度二次过滤、界面/底物 docking、局部重设计，而不是替代快速筛选模型。

### SABIO-RK kinetics API

- 官方文档确认 SABIO-RK 提供 RESTful Web Services，可查 kinetic law entry、entry IDs、reaction IDs，并输出 SBML/XML/TSV 等格式。
- 官方手册还特别提醒一部分 SMILES/InChI/InChIKey 存在错误，compound mapping 不能不经校验直接入库。
- KWB 接入 SABIO-RK 时应先做 read-only enrichment：`UniProtID`、`ECNumber`、`Parameter`、`temperature`、`pH`、organism/tissue、PubMed/source，而不是直接把 kcat/Km 混成通用活性标签。

### MaveDB feedback schema

- MaveDB REST API 可公开读取 score sets、scores、mapped variants、experiments；public data 读取不需要 API key，写入/private data 需要 API key。
- MaveDB accession 体系按 experiment set / experiment / score set / variant 层级组织，score set 使用 `urn:mavedb:` 风格标识。
- 发布后 score set 不可随意改目标、scores、counts；错误修复走 deprecation/replace 机制。这个机制非常适合作为 KWB 实验反馈版本治理参考。
- KWB 的 `experiment_feedback.local.jsonl` 应靠近 MaveDB 思路：一个 plate / assay / round 对应一个 score set，变体编号、测量条件、replicate、失败样本和数据版本都必须可追踪。

### 产品/平台模式

- Cradle 公开页面强调上传 wet-lab data、custom schemas、provenance tracking、API access、multi-property optimization、plate design 和 automated finetuning。KWB 应优先补这些能力，而不是先追求“更大生成模型”。
- Arzeda 强调 design-build-test-learn、LIMS、strain/process/formulation 与 protein design 的跨团队闭环。这对 KWB 的启发是：酶设计输出必须带应用条件、表达/稳定性/工艺约束。
- Profluent 强调 foundation model + in-house wet lab + multi-attribute optimization；Basecamp 强调 proprietary evolutionary dataset / biodiversity partnerships。二者说明数据来源和闭环验证是核心资产，不能靠公开模型名称复制。

第三轮结论：

- 候选生成：`LigandMPNN` 可进入候选生成路线，但必须等结构链映射和 ligand/context 证据成熟。
- 高精度物理设计：`Rosetta/PyRosetta` 需商业许可后再评估。
- kinetics enrichment：`SABIO-RK` 可以先做只读 API enrich，但 compound identifiers 和实验条件必须校验。
- feedback loop：`MaveDB` 的 score set / URN / publish-deprecate 模式应直接影响 KWB 反馈 schema 设计。
- 产品化能力：优先补 custom schema、provenance、plate-level feedback、round-level model update、权限和 API，而不是把未安装模型显示为已可用。

## 8) 第四轮补强：mutation-effect、结构检索、kinetics prediction

### Mutation-effect classical stack

- `EVE` 官方仓库为 MIT，核心是每个 protein family 用 MSA 训练 Bayesian VAE，再输出 single amino-acid mutation 的 evolutionary index / pathogenicity-like score。它对 KWB 的直接提醒是：无 MSA 时不要伪造 conservation 或 evolutionary effect。
- `EVmutation` 使用 plmc 估计 sequence family 的 undirected graphical model，再用 coevolution/covariation 估计突变效应。它同样依赖高质量 alignment，适合作为审计/benchmark 参考。
- `GEMME` 论文显示它是 global epistatic model，基于 natural sequence evolutionary history 预测 mutational effects；但论文许可为 CC BY-NC，商业复用需要谨慎。
- `VESPA` PyPI 标注 AGPLv3+，适合作公开/研究参考；如果集成到闭源商业平台，需要严格隔离或做替代实现评估。

KWB 结论：

- 这些方法强化了同一个事实：mutation-effect 路线首先缺的是真实 MSA/cache 和可追踪编号，不是又一个 adapter 名称。
- `EVE/EVmutation/GEMME/VESPA` 更适合进入 benchmark/evidence matrix，不宜在当前缺 MSA、缺编号 reviewed labels 时直接接入生产链。

### Structure search / alignment

- `Foldseek` 官方 GitHub 是 GPL-3.0，适合大规模结构相似性搜索、cluster search、3Di+AA alignment，并能用 TMalign 作为 alignment type。
- `TM-align`/TM-score 适合 pairwise structure comparison 和模型质量/同源结构评估；部分发行包/封装 license 不一致，若集成应优先用清晰许可的独立实现或外部命令隔离。
- `US-align` 提供 proteins、nucleic acids 和 macromolecular complexes 的通用结构比对，适合后续复合物/多链结构审校评估。

KWB 结论：

- `Foldseek` 可用于结构候选检索、同源结构补齐和结构聚类，但 GPL-3.0 决定它不应直接链接进闭源商业核心。
- 结构特征生产前应先形成 `structure_chain_mappings_curated.jsonl`，再用 TM-score/Foldseek 类指标做 structure-neighbor evidence，不要反过来用结构相似性绕过链映射审校。

### Enzyme kinetics prediction

- `CatPred` 官方 GitHub/论文面向 kcat、Km、Ki 预测，输入包括 enzyme sequence/structure 和 substrate SMILES，并输出 uncertainty quantified kinetic parameters；它的训练数据来自 BRENDA 和 SABIO-RK，且明确处理 out-of-distribution evaluation。
- `CatPred` GitHub README 还给出 API/批量预测形态，但输入需要 `SMILES`、`sequence`、`pdbpath`，并提示同一 sequence 的 `pdbpath` cache 复用边界；这和 KWB 的结构版本/chain mapping governance 高度相关。
- `GotEnzymes2` 扩展到 kcat、Km、kcat/Km、optimal temperature、melting temperature 等大规模预测资源，适合作为 coverage/reference，但预测数据库不能当实验真值。

KWB 结论：

- `CatPred` 可以作为 enzyme kinetics external baseline，但必须把输出列命名为 predicted_kcat / predicted_Km / predicted_Ki，并携带 substrate SMILES、structure version、model version 和 uncertainty。
- `GotEnzymes/GotEnzymes2` 适合作广覆盖 annotation/reference，不适合作监督训练标签来源。
- KWB 真正要补的是 wet-lab feedback 的 measured activity / condition / batch / replicate，而不是用公开 prediction database 填实验反馈空表。

### Sequence / backbone generation

- `ProteinMPNN` 官方 GitHub 是 MIT，适合固定 backbone 下的 sequence design、fixed residues、multi-chain、homooligomer 等场景；输出可包含 score/probabilities。
- `RFdiffusion` 论文和官方仓库显示其适合 motif scaffolding、binder design、backbone generation；license 为 BSD，商业友好度较高，但它生成 backbone 后仍需 ProteinMPNN/LigandMPNN、structure prediction/filtering 和实验验证。
- `Evo` 等 biological foundation model 更偏序列/基因组生成与先验，当前对 KWB 酶改造的直接落地点不如 MSA、结构链映射、kinetics/feedback 明确。

KWB 结论：

- 第一阶段不接 de novo backbone generation。先把 mutation ranking、stability、substrate/assay feedback 做稳。
- 只有在结构链映射、底物约束和实验反馈闭环稳定后，才把 `ProteinMPNN / LigandMPNN / RFdiffusion` 放入候选生成队列。

## 9) 第五轮补强：active learning、实验数据标准、版本治理

### Adaptive experimentation / active learning

- `BoTorch` 官方 GitHub/PyPI 均为 MIT，是 PyTorch 上的 Bayesian optimization 库，支持 probabilistic models、acquisition functions、multi-task GP、GPU/auto-diff 等底层能力。
- `Ax` 官方 GitHub 为 MIT，是 adaptive experimentation platform，面向管理、部署和自动化实验；支持 Bayesian optimization、bandit optimization、多目标、约束、噪声观测、并行 trial、early stopping，并由 BoTorch 提供 BO 能力。
- 对 KWB 来说，`Ax` 比直接裸用 BoTorch 更贴近实验运营：它有 experiment/trial/raw_data 的概念，可以映射到 plate / assay round / measured metric。

KWB 结论：

- 第一版闭环不应做完全自动的 autonomous evolution。更稳妥的是 `human-approved active learning`：模型提出候选、系统生成 plate plan、人工确认、实验回填、再更新候选。
- BO 的目标函数必须拆开：activity、stability、expression、substrate fit、assay success 和 uncertainty；不能只优化一个合成分数。
- 每个 BO trial 必须绑定 `model_version`、`training_data_version`、`candidate_generation_version`、`assay_protocol_version` 和 `plate_id`。

### Laboratory data / automation standards

- `SiLA 2` 面向 lab automation 的开放连接标准，官方文档强调 instrument/software interoperability、standardized communication protocols；GitLab work 为 MIT。
- `AnIML` 是 ASTM XML analytical data 标准，核心 schema + technique schema + technique definition documents，适合仪器分析数据交换。
- `Allotrope` 提供 ADF/ADM/AFO/ASM：ADF 用于实验数据 acquisition/exchange/storage/access，AFO 提供 ontology，ASM 是 JSON-based laboratory data representation，并可用 JSON Schema 校验。
- `Autoprotocol` 是 open standard，用精确、无歧义的数据表示实验 protocol；它强调 protocol encoded as data，不包含自然语言里的“mix gently / overnight”模糊描述。

KWB 结论：

- KWB 不需要一开始完整实现这些标准，但 feedback schema 应吸收它们的共同点：instrument、method、sample/container、protocol step、parameter、unit、operator、timestamp、raw data pointer、derived result、audit trail。
- 对酶平台最先需要的是 plate-level JSON schema，而不是通用 LIMS 大工程：`plate_id`、`well_id`、`variant_id`、`sample_batch`、`substrate_smiles`、`temperature`、`pH`、`replicate`、`raw_signal`、`normalized_activity`、`QC_flag`。

### ELN / LIMS integration pattern

- Benchling Developer Platform 提供 REST APIs、Events、Python SDK、App Framework，可读写 structured data，并覆盖 assay results、inventory、entities 等场景；API/Developer Platform 需要企业租户和权限。
- Benchling 文档里的 assay flow 明确包括创建 assay run、上传 raw data、写 assay results、关联 ELN entry，再通过 warehouse 查询结果。这与 KWB 的反馈闭环高度一致。
- Aquarium/Pydent 走 planning、executing、analyzing scientific experiments 的 LIMS/API 思路，适合作为开源概念参考，但 KWB 当前不应先迁移 LIMS。

KWB 结论：

- KWB 本地系统先定义 adapter contract：`import_assay_run`、`import_assay_results`、`link_raw_data`、`validate_feedback_rows`、`freeze_score_set`。
- 真接 Benchling 或其它 ELN/LIMS 前，先在本地 `experiment_feedback.local.jsonl` 中跑通同样的数据形状和校验门控。

### Versioning, quality and metadata governance

- `MLflow Model Registry` 提供 model versions、aliases/tags、annotations 和 lineage；如果自托管 registry，官方文档要求 database-backed backend store 才能通过 UI/API 使用 registry。
- `DVC` 是 Apache-2.0 的 data/model versioning 工具，用 Git-like 方式管理数据和模型，对 KWB 的 cache/report/data artifact 版本化有直接参考价值。
- `Great Expectations / GX Core` 是 Apache-2.0 的 data quality framework，适合把反馈行、domain rows、MSA cache manifest、chain mapping decision 做 expectation-style 校验。
- `DataHub` 是 Apache-2.0 的 metadata platform / data catalog，支持 lineage、governance、observability、OpenAPI/GraphQL/SDK 和 AI-ready metadata；对 KWB 来说可作为长期数据目录参考。

KWB 结论：

- 短期不需要部署 MLflow/DVC/DataHub/GX，但 KWB 应立刻采用它们背后的字段：artifact URI、checksum、producer script、input versions、schema version、validation report、lineage edge、model alias、deprecation reason。
- `master_readiness_board.json` 应继续保持 fail-closed；未来模型卡和 local registry 应引用 exact dataset/report hash，而不是“最新数据”这类不可复现引用。

第五轮结论：

- active learning 可做，但必须先是 human-approved，不是自动实验闭环。
- 反馈 schema 必须 plate-level、well-level、protocol-versioned，并保留失败和 QC fail 样本。
- ELN/LIMS 对接先做 adapter contract 和本地 JSONL 验证，再考虑 Benchling/其它系统。
- 模型和数据版本治理是生产验收必需项；没有 lineage/hash/validation report 的模型不能进入 KWB 平台默认推荐。

## 10) 第六轮补强：运行环境、数据许可、合规登记

### Local Mac vs CUDA Linux

- 当前 KWB 本地机器是 Apple Silicon / macOS 路线。PyTorch 的 MPS backend 可以让部分 PyTorch 张量计算跑到 Apple GPU，但它不是 CUDA 替代品。
- `Chai-1`、很多结构/扩散/蛋白设计模型和 GPU container workflow 仍以 Linux + NVIDIA CUDA 为默认目标。需要 bfloat16/CUDA 的工具不能假设能在 Mac MPS 上等价运行。
- NVIDIA Container Toolkit 的正式路线是 Linux host + NVIDIA driver + container runtime；macOS Docker Desktop 里的 Linux VM 不能直接变成 CUDA host。

KWB 结论：

- Mac 本机优先承担：数据治理、JSONL/report pipeline、结构解析、轻量 CPU adapter、HTTP/local dashboard、review packet。
- CUDA Linux 机器才承担：Boltz-2/Chai-1/RFdiffusion/大模型 inference、GPU MMseqs2、批量结构/亲和力评估。
- 所有外部工具 readiness 需要区分 `mac_local_ready`、`linux_cpu_ready`、`linux_cuda_ready`、`license_ready`、`data_ready`，不能只用一个 ready boolean。

### Database and cache sizing

- ColabFold 本地数据库和 search server 的公开说明显示，本地 MSA/structure pipeline 的主要瓶颈经常是数据库体量和 RAM，而不是 Python wrapper。
- MMseqs2 即使安装成功，也必须有 UniRef/Swiss-Prot/MMseqs DB 或可信 MSA cache；否则会跑出形式上成功、实际上无效的空同源搜索。
- ProteinGym、MaveDB、BRENDA/SABIO-RK、RCSB/mmCIF、AlphaFold/ESM Atlas 这类来源都需要 release/version、query date、checksum 和 license note。

KWB 结论：

- `msa_runtime.local.example.json` 需要继续区分 executable、database_path、database_release、cache_manifest、validation_report。
- 对 cache 不只检查“文件存在”，还要检查 target count、sequence ID、database release、alignment depth、conservation rows、checksum 和 failure reasons。

### Data license and attribution

- UniProt 和 BRENDA 等数据库虽然可公开访问，但 license、API 限速、再分发和 attribution 条款不同，不能混成一个“free data”桶。
- RCSB/wwPDB 数据通常适合公开使用，但结构文件、派生特征、链映射和版本仍应记录 PDB ID、format、download date、assembly/model、chain、checksum。
- MaveDB、ProteinGym、FireProtDB/ProThermDB 这类 benchmark/variant 数据适合评测或 schema 参考；训练使用要逐条区分数据许可、实验条件、编号和是否允许商业衍生训练。

KWB 结论：

- 应新增 `external_data_source_registry`：`source_name`、`url`、`license`、`commercial_use_status`、`redistribution_status`、`attribution_required`、`version`、`retrieved_at`、`allowed_uses`、`forbidden_uses`。
- 当前所有 predicted/benchmark/reference 数据默认只能作 evidence、benchmark、feature 或 review aid；只有真实 KWB wet-lab/historical experiment 且编号/条件合规后才能进入 supervised label。

### Tool license registry

- 当前候选栈已经出现 MIT、Apache-2.0、BSD、GPL-3.0、AGPL、research-only、non-commercial、commercial-license-required 等多种状态。
- 工程上必须把 tool readiness 拆成 install readiness、runtime readiness、license readiness、data readiness 和 model weight readiness。

KWB 结论：

- `foreign_tool_registry.local.example.json` 应升级成正式 registry：每个工具必须有 `license_type`、`license_evidence_url`、`weight_terms_url`、`commercial_status`、`runtime_requirements`、`data_requirements`、`adapter_status`。
- 运行面板只能显示四类状态：ready、not installed、license review required、restricted。不能把缺 license 或缺 CUDA 的工具显示成 running。

### Deployment path

- 短期：local-only pipeline 继续产出 review packet、validator、manifest、board。
- 中期：如果有 CUDA Linux 机器，先跑 isolated evaluation，不接生产，不覆盖本地 source DB。
- 长期：生产接入必须走 P31：远端备份、最小文件集同步、构建前检查、灰度重启、公网 smoke。当前未授权，不执行。

第六轮结论：

- 当前最现实的工程动作不是“安装一堆模型”，而是把 runtime/license/data registry 补严。
- Mac 本机继续做治理和轻量验证；GPU 模型评估需要单独 Linux CUDA 环境。
- MSA/cache readiness 必须继续 fail-closed，数据库 release 和 cache validator 是硬门槛。

## 11) 第七轮补强：AI 治理、生物安全、平台验收

### AI risk management / governance

- `NIST AI RMF 1.0` 的核心是 `Govern / Map / Measure / Manage`，强调 AI 风险管理贯穿系统生命周期，不是一次性验收。
- `NIST Generative AI Profile` 和 NIST AIRC 提供 TEVV（testing, evaluation, verification, validation）方向的资源，适合转化为 KWB 的本地验收 checklist。
- `ISO/IEC 42001:2023` 是 AI management system 标准，核心要求是建立、实施、维护和持续改进 AI 管理体系，强调风险、透明度、责任和持续学习。
- `OECD AI Principles` 强调 human oversight、transparency、robustness/security/safety、accountability 和 traceability。

KWB 结论：

- `KWB-EnzymeDesigner` 必须有模型卡、数据卡、工具卡和 readiness board 四件套；只给一个 API endpoint 不足以进入平台默认推荐。
- 每次模型输出都应可追溯：input sequence/structure/hash、tool version、model version、database/cache release、license status、validation report、decision gate。
- GPT 主控调用 KWB 工具时必须遵守 tool boundary：未安装、license blocked、cache invalid、编号未审校、结构链未审校、反馈缺失时，只能返回 blocked/pending/evidence-needed。

### Biosecurity / dual-use governance

- WHO `Global guidance framework for the responsible use of the life sciences` 强调 biosafety、laboratory biosecurity 和 dual-use research oversight 是共同责任。
- NIH Guidelines 覆盖 recombinant or synthetic nucleic acid molecules；机构需要 IBC、职责分工和合规流程。即便 KWB 当前只做酶蛋白本地模型，也要为后续 DNA synthesis / expression 实验留出审查钩子。
- International Gene Synthesis Consortium（IGSC）的 harmonized screening protocol 提醒：任何走向 DNA synthesis / gene order 的序列都需要 screening 和 customer/order 审查。
- OECD synthetic biology 页面也强调合成生物学的 biosecurity、biosafety、伦理和公平访问风险。

KWB 结论：

- KWB 不能直接输出“可下单表达”的序列包而无审查；候选序列进入 synthesis/order 前必须过 biosecurity screening、organism/toxin/pathogen risk、intended use 和 human approval。
- 平台 UI 应区分：`design_candidate`、`experiment_candidate`、`approved_for_ordering`。默认只到 design_candidate。
- 对任何 pathogen/toxin/virulence/gene-drive/host-range/immune-evasion 相关请求，应进入 restricted or manual review，不由模型自动优化。
- 即使是工业酶，也要记录 expression host、vector、selection marker、containment level、operator approval 和 biosafety note。

### LLM / agent tool safety

- AI agent 不能根据网页或模型输出自动执行安装、下载权重、Docker pull、订单提交、服务器部署或实验提交。
- 所有外部网页、GitHub README、论文、数据库记录都应视为 untrusted input，只能作为 evidence，经本地 schema/validator 后才能进入 pipeline。
- 工具调用应有 allowlist、local-only flag、license gate、network/download gate 和 destructive-action gate。

KWB 结论：

- 现有 safe pipeline 的 fail-closed 思路正确，应扩展到：`biosecurity_gate`、`license_gate`、`runtime_gate`、`data_lineage_gate`、`human_approval_gate`。
- `run_safe_training_pipeline.py` 后续可新增不联网的 governance report builder：读取 registry、reports 和 decisions，生成平台验收前的 `governance_readiness_report.json`。

### Platform acceptance checklist

生产接入前最低条件：

- 数据：strict supervised rows、domain intervals、MSA/conservation、structure chain mappings、feedback rows 都有 version/hash/validator。
- 模型：每个 head 有训练数据版本、评测 split、benchmark、calibration、failure mode 和禁止用途。
- 工具：每个外部工具有 install/runtime/license/data/model-weight readiness。
- 安全：biosecurity gate、license gate、human approval gate、audit log 都通过。
- 平台：GPT 主控只消费结构化 result envelope，不能把 blocked 状态改写成可用建议。

第七轮结论：

- KWB 的真正验收线不是“能生成建议”，而是建议是否可审计、可复现、可解释、可被人工审批和可被安全拒绝。
- 下一步工程上最值得新增的是 `governance_readiness_report.json` 和 `external_data_source_registry.json`，而不是继续增加未安装模型名字。

## 12) 第八轮补强：SBOM、provenance、数据卡/模型卡、发布包

### Software supply chain / SBOM

- `SPDX` 是 Linux Foundation 下的 open standard，可机器化表达 package metadata、license、copyright、security references 和 SBOM。
- `CycloneDX` 是 OWASP 生态下的 SBOM 标准，覆盖 software、hardware、services、vulnerabilities 和 operational risk。
- `SLSA` 强调 build provenance、source integrity、dependency pinning 和 tamper resistance；`Sigstore/cosign` 提供 artifact signing、container signing 和 keyless signing 路线。

KWB 结论：

- P30 本地发布包应包含 `software_bill_of_materials`，至少覆盖 scripts、prototype/platform_integration、contracts、config、model_cards、reports 和外部工具 registry。
- 每个模型/报告/数据 artifact 应记录 producer script、input artifact hashes、environment note、license note 和 validation status。
- 即使当前不部署，local release package 也应支持“谁生成、用什么数据、通过了哪些 gate、哪些外部工具 blocked”。

### Provenance / research object metadata

- `W3C PROV` 是 provenance data model，可表达 entity、activity、agent 和 wasGeneratedBy / used / wasAssociatedWith 等关系。
- `RO-Crate` 是 research object metadata packaging 规范，使用 JSON-LD 描述 dataset、software、workflow、provenance 和 contextual metadata。
- `FAIR Principles` 强调 Findable、Accessible、Interoperable、Reusable；KWB 当前最欠缺的是 Interoperable/Reusable 所需的 schema、license、lineage 和 version。
- `Croissant` 是 ML dataset metadata format，用 JSON-LD/schema.org 表达 ML dataset 的 resources、record sets、fields、license 和 extraction transform。

KWB 结论：

- 不需要立刻引入完整 RO-Crate 工具链，但 `data_lake_manifest.json` 可以向 RO-Crate/W3C PROV 思路扩展：artifact as entity、script as activity、curator/tool as agent、input/output edges。
- `external_data_source_registry.json` 和 `governance_readiness_report.json` 应能回答：这个结论来自哪个 source、哪个版本、哪个 validator、哪个 human decision。

### Model cards / data cards

- Model Cards 和 Datasheets for Datasets 的共同点是：用途、训练数据、评估、限制、伦理/安全风险和维护方式必须显式化。
- Hugging Face dataset cards / model cards 和 Croissant 都提供了更工程化的元数据组织参考。

KWB 结论：

- KWB 的五头模型卡不能只写 accuracy；必须按 head 分别写 data eligibility、label source、benchmark、calibration、out-of-domain behavior、prohibited uses。
- 数据卡应覆盖：mutation labels、numbering curation decisions、domain intervals、MSA/cache、structure chain mappings、feedback score sets、external benchmark data。
- 每张卡都应指向 exact reports 和 checksums，而不是模糊的“最新版本”。

### Local release package

P30 本地验收时建议形成一个 `local_release_manifest.json`，包含：

- `release_id`、`created_at`、`local_only`、`git_or_filesystem_state`。
- `artifact_manifest`：datasets/reports/contracts/models/config/model_cards 的 path、sha256、schema、producer。
- `readiness_summary`：master readiness、training readiness、governance readiness、biosecurity readiness。
- `sbom_summary`：Python scripts、third-party tool registry、external model registry、licenses。
- `blocked_capabilities`：MSA、feedback、license、CUDA、biosecurity 等未满足项。
- `allowed_claims` / `forbidden_claims`：能说什么、不能说什么。

第八轮结论：

- KWB 的本地验收交付物应是“可审计发布包”，不是一个临时运行目录。
- `data_lake_manifest.json`、`master_readiness_board.json`、`safe_training_pipeline_run.json` 已经具备雏形；下一步应新增 SBOM/provenance/release manifest，而不是继续扩展散落报告。

## 13) 第九轮补强：benchmark / evaluation suite

### Sequence and fitness benchmarks

- `FLIP2` 扩展原 FLIP benchmark，覆盖 enzymes、protein-protein interactions、light-sensitive proteins，并提供 position/mutation/fitness/wild-type 等现实工程 split；公开页面说明数据带 provenance，数据为 CC-BY 4.0 或 MIT。
- `TAPE` 是早期 protein transfer learning benchmark，适合检查 sequence representation 的基础能力，但它不是专门面向 KWB 酶改造闭环。
- `PEER` 是 protein sequence understanding 多任务 benchmark，覆盖 function、localization、structure、PPI、protein-ligand interaction 等，source code Apache-2.0；适合作多任务序列先验评估。

KWB 结论：

- `mutation_rank_head` 应优先用 ProteinGym + FLIP/FLIP2 风格 split 评估，特别是 unseen mutation、unseen position、unseen wild-type、fitness extrapolation。
- 不要只报告 random split；P30 至少要有 protein/family/time 或 wild-type holdout split。

### 3D structure benchmarks

- `ATOM3D` 是 3D biomolecular ML benchmark，包含 mutation stability prediction、ligand binding affinity、protein interface prediction、protein structure ranking 等任务。
- `CASP` 是两年一度的 structure prediction blind assessment；CASP15 仍强调 deep MSA、hard targets、complex/ligand categories 和 confidence estimates。
- `CAMEO` 是连续自动结构预测评测，按 PDB weekly release 做 blind/automated assessment，并提供 coverage、local accuracy、completeness、ligand binding site accuracy 等多维 score。

KWB 结论：

- `structure_feature_head` 或结构依赖结论不能只看“是否有 PDB/AF 文件”；至少要报告 chain mapping coverage、missing residues、local confidence、structure-neighbor evidence 和 ligand/site QA。
- 对 Boltz-2/Chai-1/AF3 benchmark，KWB 应借鉴 CAMEO/CASP 的多指标输出：global fold、local accuracy、interface/ligand site、confidence calibration，而不是一个“结构成功”布尔值。

### Protein-ligand / affinity benchmarks

- `PDBbind/CASF` 是 protein-ligand scoring function 的经典 benchmark；CASF-2016 使用 285 high-quality protein-ligand complexes，并按 scoring/ranking/docking/screening power 评估。
- `D3R Grand Challenge` 提供 blind pose prediction 和 affinity/ranking challenge，强调真实 protein-ligand co-crystal 和 measured affinity 数据。
- `PoseBusters` 可对生成或 docked ligand pose 做几何/化学 plausibility checks，适合作 predicted ligand pose 的 sanity gate。

KWB 结论：

- `substrate_fit_head` 不应只输出 affinity 数值。最低输出应拆成：pose plausibility、pocket/contact evidence、ranking confidence、predicted affinity/IC50 proxy、known substrate similarity 和 assay applicability。
- CatPred/Boltz-2/Chai-1 的 predicted affinity 只能以 CASF/D3R/PDBbind 类 benchmark 做外部校准，不得替代 KWB wet-lab measured activity。

### KWB evaluation matrix

| KWB head / capability | Primary benchmark | Secondary benchmark | 必须报告 |
|---|---|---|---|
| mutation_rank_head | ProteinGym, FLIP/FLIP2 | PEER sequence tasks | protein/family/time split, top-k enrichment, calibration, OOD failure |
| stability_head | ThermoMPNN eval, ATOM3D MSP, FireProt/ProTherm references | ProteinGym stability-like assays | predicted ddG proxy vs measured labels, uncertainty, structure availability |
| activity_risk_head | KWB wet-lab feedback, BRENDA/SABIO-RK curated kinetics | CatPred/GotEnzymes as predicted reference | assay condition, substrate, unit, batch, QC flag |
| substrate_fit_head | CASF/PDBbind/D3R style benchmark | PoseBusters, CAMEO ligand-site metrics | pose plausibility, pocket evidence, affinity calibration, ligand identity |
| assay_success_head | KWB plate-level feedback | Autoprotocol/Benchling-like assay run QA | failure class, missingness, replicate consistency, QC fail rate |

第九轮结论：

- KWB 的 benchmark 不能只有 `run_local_benchmark.py 6/6`。P30 需要五头分层 benchmark matrix。
- ProteinGym/FLIP/PEER/ATOM3D/CASP/CAMEO/CASF/D3R/PoseBusters 分别覆盖不同层，不能互相替代。
- 所有外部 benchmark 都只能说明模型能力边界；最终 go/no-go 仍必须依赖 KWB verified numbering、真实结构/链映射、MSA/cache 和 wet-lab feedback。

## 14) 第十轮补强：合成核酸筛查、订单前门控、序列安全

### Policy baseline

- HHS/ASPR 在 `October 13, 2023` 发布 synthetic nucleic acid screening guidance，强调 baseline standards、order/recipient screening 和 record keeping。
- White House OSTP 在 `April 29, 2024` 发布 Framework for Nucleic Acid Synthesis Screening；框架要求 federally funded research 在采购 synthetic nucleic acids / benchtop synthesis equipment 时使用遵循框架的 providers/manufacturers。
- NIH IRP 页面明确 NIH researchers effective date 为 `April 26, 2025`，并要求 provider screening、customer legitimacy screening、potentially illegitimate order reporting、screening records retained 3 years、screening records cybersecurity。
- CHS Gene Synthesis Screening Information Hub 汇总了 April 2024 Framework、October 2023 HHS Guidance、August 2024 screening tools list、April 2025 sample attestation form 等资源。

KWB 结论：

- 即使 KWB 当前 local-only，只输出 protein design candidates，也应提前在平台设计中放入 `synthesis_readiness` 和 `order_screening_status`。
- 任何 DNA/RNA sequence、codon optimized gene、plasmid map、viral vector、expression construct、order-ready FASTA/GenBank 导出都必须进入 synthesis screening / customer-use review。

### SecureDNA / screening API pattern

- SecureDNA 提供免费、隐私保护的 DNA synthesis screening；文档说明 API 通过 `/v1/screen` 接收 FASTA，返回 `synthesis_permission`，可为 `granted` 或 `denied`。
- SecureDNA 文档强调 privacy-preserving screening：local encryption / cryptographic blinding / no inbound connections，并支持 region 参数如 `us`、`eu`、`prc`、`all`。
- SecureDNA API 文档明确建议 fail-closed：必须检查 `synthesis_permission`；如果有 errors，synthesis must not proceed。

KWB 结论：

- KWB 不需要在当前阶段接 SecureDNA，但应把它的 response shape 作为本地 `biosecurity_screening_result` schema 参考。
- 订单前状态建议为：`not_requested`、`screening_required`、`screening_pending`、`screening_denied`、`screening_granted`、`manual_exemption_required`、`approved_for_ordering`。
- 任何 screening error、missing provider attestation、missing customer legitimacy、missing intended-use record 都必须 fail-closed。

### Customer / use / record review

- Nucleic acid screening 不只是 sequence screening；政策和行业资料同时强调 customer screening、intended use、provider/manufacturer attestation、record keeping 和 cybersecurity。
- KWB 不是合成服务商，但如果平台后续连接供应商、LIMS、ELN 或采购流程，就会进入 customer/use/order evidence 责任链。

KWB 结论：

- `experiment_candidate` 到 `approved_for_ordering` 之间至少需要四个字段：`screening_provider`、`screening_reference`、`customer_or_project_approval`、`intended_use_statement`。
- 审计记录最少保留：candidate sequence hash、translated protein sequence hash、codon optimization method、screening result、screening timestamp、reviewer、approval decision、provider/order reference。
- sequence safety gate 不应把完整危险命中序列回显给普通用户；UI 应显示 risk category / restricted / manual review，不暴露敏感命中细节。

### KWB output policy

- KWB 默认输出：mutation recommendation、protein sequence candidate、evidence and uncertainty。
- KWB 不默认输出：order-ready DNA sequence、codon-optimized gene、plasmid-ready insert、synthesis provider payload。
- 若用户明确进入实验设计，系统仍应先输出 `experiment_candidate`，再等待 biosecurity/manual approval。

第十轮结论：

- `biosecurity_gate` 应拆成 protein-level restricted-topic gate、nucleic-acid screening gate、customer/use approval gate 和 ordering gate。
- 当前本地下一步可新增不联网的 `biosecurity_readiness_report.json`：只检查 schema、state machine、blocked defaults 和是否禁止 order-ready output。
- 平台层必须保持 fail-closed：screening unavailable / error / missing review 不等于 approved。

## 15) 第十一轮补强：IP/FTO、序列专利、商业交付审查

### Patent sequence listings

- WIPO Sequence Suite 是申请人生成 WIPO Standard ST.26 compliant amino acid / nucleotide sequence listings 的官方工具；WIPO Sequence Validator 用于专利局验证 sequence listings。
- WIPO 页面明确 ST.26 已生效；WIPO Sequence 当前支持 Windows、Linux、macOS。
- USPTO sequence listing basics 明确：filing date / international filing date on or after `July 1, 2022` 的申请必须使用 ST.26 XML sequence listing；ST.25 适用于更早 filing date。
- USPTO 还强调 ST.26 XML 包含 general information 和 sequence listing 信息，且 XML 文件需要 UTF-8、符合 ST.26 DTD；大文件还有 Patent Center 上传限制。
- PATENTSCOPE 支持检索 published nucleotide/amino acid sequence listings，并提供 PCT published sequence listings bulk download。

KWB 结论：

- KWB 候选蛋白序列如果进入 patent disclosure / invention record / customer deliverable，应保存 `protein_sequence_hash`、`variant_set_id`、`parent_sequence`、`mutation_set`、`generation_method` 和 `known_prior_art_hits`。
- KWB 不应自动生成专利 sequence listing 或法律结论；最多生成 invention-disclosure-ready evidence packet，交给 IP counsel 或专利代理人审查。

### Patent search / FTO APIs

- EPO Open Patent Services（OPS）是 RESTful XML interface，可访问 EPO bibliographic、worldwide legal status、full-text、image databases，数据来源与 Espacenet/European Patent Register 一致；需要注册和 OAuth。
- Google Patents、WIPO PATENTSCOPE、USPTO、EPO OPS、PatentsView/Lens 等可组成 prior-art / FTO evidence sources，但各自 license/API/coverage 不同。
- Sequence-level patent FTO 不能只靠 keyword；需要 sequence similarity search、claim scope review、jurisdiction、legal status、expiration、assignee 和 family mapping。

KWB 结论：

- 后续应新增 `ip_prior_art_registry` 或 `sequence_ip_review_packet`，至少包含：query sequence hash、database/source、query date、hit accession/publication、identity/coverage、claim relevance、legal status、jurisdiction、reviewer、decision。
- `approved_for_customer_delivery` 和 `approved_for_ordering` 不能只依赖生物安全；还需要 IP/FTO review status。

### Commercialization / customer output

- 商业交付风险不只来自模型能力，还来自 IP chain-of-title、第三方数据许可、open-source license contamination、patent claim overlap 和客户用途。
- 对公开 benchmark / predicted database / research-only model 生成的候选，需要记录 whether derived from restricted source、whether trained-on external benchmark、whether output is merely ranked existing sequence or newly generated candidate。

KWB 结论：

- KWB 输出状态机应扩展：`internal_design_candidate`、`ip_review_required`、`biosecurity_review_required`、`experiment_candidate`、`customer_delivery_candidate`、`approved_for_customer_delivery`、`approved_for_ordering`。
- 任何 customer-facing sequence package 必须有：data license clearance、tool license clearance、IP/FTO review note、biosecurity review note、human approval、allowed claims。

### Local IP governance

- 对工业酶平台，很多价值在 mutation combination、screening data、process condition、expression/assay workflow，而不只是单个 sequence。
- 因此 KWB 的 evidence packet 应同时记录 negative results、failed variants、assay conditions 和 selection criteria；这些是 trade secret / know-how 的重要部分。

第十一轮结论：

- `external_data_source_registry` 还不够，需新增 `ip_review_status` 和 `customer_delivery_gate`。
- KWB 可以自动化 prior-art evidence gathering 和 sequence comparison worklist，但不能自动给 freedom-to-operate 法律结论。
- P30/P31 之前，任何客户交付包都要同时通过 license、biosecurity、IP/FTO、model/data provenance 四道门。

## 16) 第十二轮补强：工程化待建清单

前面十一轮外部调研已经足够支持下一步本地工程建设。继续调研的边际收益低于把证据转成可执行 artifacts。建议把调研输出转为以下本地待建清单：

### Registry / manifest

1. `config/external_data_source_registry.local.example.json`
   - 字段：source_name、source_type、url、license、commercial_use_status、redistribution_status、attribution_required、version、retrieved_at、allowed_uses、forbidden_uses。
   - 目的：阻止 BRENDA/SABIO-RK/MaveDB/ProteinGym/FireProt/ProTherm/PDB/UniProt 这类来源被混成一个训练源。

2. `config/foreign_tool_registry.local.example.json` 升级
   - 新增字段：license_type、license_evidence_url、weight_terms_url、commercial_status、runtime_requirements、data_requirements、mac_local_ready、linux_cpu_ready、linux_cuda_ready、license_ready、data_ready、model_weight_ready。
   - 目的：把安装、许可、CUDA、数据和权重门槛分开，不再用单个 ready boolean。

3. `reports/provenance_graph_report.json`
   - 从 `data_lake_manifest.json`、safe pipeline 和主要 reports 构造 entity/activity/agent/input-output edges。
   - 目的：向 W3C PROV/RO-Crate 风格靠拢，支撑 P30 发布包。

### Governance / safety reports

4. `reports/governance_readiness_report.json`
   - 汇总模型卡、数据卡、工具卡、readiness board、license、runtime、data lineage、TEVV、allowed/forbidden claims。
   - 目的：P30 不能只看 training readiness。

5. `reports/biosecurity_readiness_report.json`
   - 检查是否存在 order-ready DNA/RNA/construct 输出；检查状态机是否 fail-closed：not_requested、screening_required、screening_pending、screening_denied、screening_granted、manual_exemption_required、approved_for_ordering。
   - 目的：本阶段不联网、不调用 screening API，只验证门控形状。

6. `reports/customer_delivery_readiness_report.json`
   - 检查客户交付所需 license、biosecurity、IP/FTO、model/data provenance、human approval、allowed claims 是否齐全。
   - 目的：明确当前只能内部研发，不能客户交付。

### IP / FTO work packets

7. `datasets/curation/sequence_ip_review_packets/*.jsonl`
   - 字段：sequence_hash、parent_sequence_hash、mutation_set、source_model/tool、prior_art_source、hit_id、identity、coverage、jurisdiction、legal_status、claim_relevance、review_decision。
   - 目的：自动生成 prior-art evidence worklist，但不输出法律结论。

### Benchmark / model evaluation

8. `reports/benchmark_matrix_report.json`
   - 按五个 head 映射 ProteinGym/FLIP/PEER、ThermoMPNN/ATOM3D、PDBbind/CASF/D3R/PoseBusters、KWB plate feedback。
   - 目的：替代单一 smoke benchmark，支撑模型卡。

9. `model_cards/KWB-EnzymeDesigner-heads.template.md`
   - mutation_rank/stability/activity_risk/substrate_fit/assay_success 五头分别写：训练资格、数据来源、benchmark、calibration、failure modes、prohibited uses。

### Feedback / active learning

10. `contracts/experiment_feedback_plate.schema.json`
    - 字段：plate_id、well_id、variant_id、sample_batch、substrate_smiles、temperature、pH、replicate、raw_signal、normalized_activity、QC_flag、instrument、protocol_version、operator、raw_data_uri。
    - 目的：把 feedback 从“单行结果”升级成 plate/well-level score set。

11. `contracts/active_learning_trial.schema.json`
    - 字段：candidate_id、model_version、training_data_version、objective_vector、uncertainty、plate_plan_id、human_approval_status、budget_note。
    - 目的：支持 human-approved active learning，不自动提交实验。

### Release package

12. `reports/local_release_manifest.json`
    - 字段：release_id、created_at、local_only、artifact_manifest、readiness_summary、sbom_summary、blocked_capabilities、allowed_claims、forbidden_claims。
    - 目的：P30 的实际交付物，而不是散落目录。

工程优先级：

1. 先做 registry 和 governance report，因为它们不依赖外部安装，也能立刻增强 fail-closed 能力。
2. 再做 biosecurity/customer delivery/IP packet，因为它们能防止平台误把内部候选当客户交付。
3. 再做 benchmark matrix 和 feedback plate schema，为 P28-P30 铺路。
4. 最后再考虑外部工具 adapter；没有 registry/readiness 前，不应继续增加模型名称。

第十二轮结论：

- 深度调研阶段可以收束到工程化待建清单。
- 下一步建议回到本地代码：新增 registry/report builder/schema，并纳入 safe pipeline。
- 仍然不需要下载、安装、部署或服务器同步。

## 17) KWB 差距矩阵

| 层 | 当前状态 | 主要缺口 | 推荐动作 |
|---|---|---|---|
| MSA / conservation | 158 jobs blocked | 无执行器、无可信 cache、无 homolog DB | 先解 MMseqs2 / cache |
| Structure / affinity | 有结构缓存，但链映射未审校完 | 底物 fit、口袋、复合物证据不足 | 先 Boltz-2，AF3 只做对标 |
| Mutation effect | 只有少量 strict labels | 缺 MSA、ddG / DMS /功能一致性基线 | ProteinGym + ThermoMPNN，EVE/EVmutation/GEMME 仅作对照 |
| Structure search | 有本地结构文件 | 缺结构邻居、TM-score/Foldseek 类审计 | 链映射 curated 后再做 Foldseek/TM-align evidence |
| Function / kinetics | 主干存在，但未统一版本追溯 | 条件、编号、许可边界不统一 | UniProt + BRENDA + SABIO-RK 清洗，CatPred 只作预测 baseline |
| Feedback loop | 还在 scaffold 阶段 | 没有 plate/well/assay-level score set | 按 MaveDB + Autoprotocol/Allotrope 思路建 schema |
| Active learning | 未启动 | 无 human-approved trial / plate loop | 先用 Ax/BoTorch 思路设计 candidate-to-plate contract |
| License / ops | 许可边界不统一 | 商业可用与研究用途混在一起 | 建 tool/license registry |
| Version governance | reports/artifacts 已有但 registry 不完整 | 缺统一 lineage/hash/model alias | 建 local artifact/model registry schema |
| Runtime ops | Mac 本机可做治理，CUDA 工具不可直接等价运行 | 缺 linux_cuda_ready / data_ready / weight_terms_ready 拆分 | 扩展 foreign tool registry 和 readiness board |
| AI/biosecurity governance | 还没有统一治理验收报告 | 缺 biosecurity、human approval、agent safety gates | 新增 governance readiness 和 biosecurity gate |
| Release governance | artifacts 分散在 datasets/reports/model_cards | 缺 SBOM/provenance/release manifest | 新增 local_release_manifest 和 provenance edges |
| Benchmark governance | 只有局部 smoke/fixture benchmark | 缺五头分层外部 benchmark matrix | 新增 benchmark_matrix_report 和 head-level scorecards |
| Synthesis/order governance | 当前无 order-ready 输出门控 | 缺 synthesis screening state machine 和 customer/use approval | 新增 biosecurity_readiness_report 和 order output policy |
| IP/customer delivery governance | 当前无 FTO/IP review 状态 | 缺 sequence patent/prior-art/customer delivery gate | 新增 sequence_ip_review_packet 和 customer_delivery_gate |
| Engineering translation | 调研文档已很完整 | 待建清单未全部落成脚本/schema/report | 先做 registry/governance/biosecurity/release manifest builder |

## 18) 推荐落地顺序

### 第一优先级：MSA 解阻

- 先装或接入 MMseqs2。
- 若无法安装，先提供可信 MSA cache。
- 目标是把 `0/158` 变成可追踪的 conservation features。

### 第二优先级：Boltz-2 结构/亲和力评估

- 先做本地 adapter 和 benchmark。
- 输出只写 predicted structure / predicted affinity，不和实验结构混用。

### 第三优先级：ThermoMPNN + CLEAN

- ThermoMPNN 负责稳定性 baseline。
- CLEAN 负责 EC / function consistency。
- 这一步的目标是把“突变排序”和“功能风险”拆开。

### 第四优先级：Ligand-aware 设计

- 只有在结构链映射稳定后再接 LigandMPNN / 结构条件设计。
- 这一步更适合做候选生成，不适合直接给最终决策。

### 第五优先级：反馈闭环

- 把实验结果变成结构化 score set。
- 保留失败样本、条件、批次和编号回溯。
- 这是 KWB 真正的护城河，不是模型名。

## 19) 不建议直接生产化的项

- AlphaFold 3：只做对标。
- 许可不清晰或研究用途限制明显的权重：先隔离。
- Rosetta/PyRosetta：未取得商业许可前不能作为商业默认后端。
- Foldseek / VESPA / HH-suite 这类 GPL/AGPL 工具：闭源商业集成需隔离或另做合规方案。
- CatPred/GotEnzymes 等 predicted kinetics：只能作预测证据，不得当湿实验标签。
- Ax/BoTorch：不能在没有人工审批、实验预算和 QC 门控时自动提交下一轮实验。
- 任何只在 Linux CUDA 上可用的模型：不能在 Mac 本机 readiness 中显示为 ready。
- 任何缺 database release、license note、checksum 的外部数据：不能进入训练或默认推荐链路。
- 任何候选序列进入 DNA synthesis / order / expression 前：必须经过 biosecurity 和 human approval gate。
- 任何 pathogen/toxin/virulence/gene-drive/host-range/immune-evasion 相关请求：不能由模型自动优化。
- 任何缺 SBOM/provenance/release manifest 的本地包：不能作为可交付发布包。
- 任何只在随机 split 或 fixture benchmark 上表现好的模型：不能进入生产默认推荐。
- 任何未经过 synthesis screening 和 customer/use approval 的 DNA/RNA/construct/order payload：不能导出给采购或合成供应商。
- 任何未经过 IP/FTO review 的 customer-facing sequence package：不能作为客户交付物。
- 任何没有编号、条件、实验来源的反馈：不能回灌训练。
- 任何把结构代理当作实验真值的流程：不能直接上线。

## Sources

- MMseqs2: https://github.com/soedinglab/MMseqs2
- ColabFold: https://github.com/sokrypton/ColabFold
- HH-suite: https://github.com/soedinglab/hh-suite
- HMMER: https://github.com/EddyRivasLab/hmmer
- Boltz-2: https://github.com/jwohlwend/boltz
- Chai-1: https://huggingface.co/chaidiscovery/chai-1
- Chai-1 GitHub: https://github.com/chaidiscovery/chai-lab
- AlphaFold 3: https://github.com/google-deepmind/alphafold3
- OpenFold: https://github.com/aqlaboratory/openfold
- ESM / Biohub: https://github.com/Biohub/esm
- ProteinGym: https://proteingym.org/
- ProteinGym GitHub: https://github.com/OATML-Markslab/ProteinGym
- FLIP2: https://openreview.net/forum?id=p2dMLEwL8tF
- FLIP2 GitHub: https://github.com/kirjner/flip
- TAPE: https://github.com/songlab-cal/tape
- PEER: https://github.com/DeepGraphLearning/PEER_Benchmark
- ATOM3D: https://www.atom3d.ai/
- ATOM3D GitHub: https://github.com/drorlab/atom3d
- CASP: https://predictioncenter.org/
- CAMEO: https://www.cameo3d.org/
- PDBbind: http://www.pdbbind.org.cn/
- CASF-2016: https://pubs.acs.org/doi/10.1021/acs.jcim.8b00545
- D3R Grand Challenge: https://drugdesigndata.org/about/grand-challenge
- PoseBusters: https://github.com/maabuu/posebusters
- EVE: https://github.com/OATML/EVE
- EVmutation: https://marks.hms.harvard.edu/evmutation/downloads.html
- GEMME: https://pmc.ncbi.nlm.nih.gov/articles/PMC6805226/
- VESPA: https://pypi.org/project/vespa-effect/
- ThermoMPNN: https://github.com/Kuhlman-Lab/ThermoMPNN
- CLEAN: https://github.com/tttianhao/CLEAN
- SaProt: https://github.com/westlake-repl/SaProt
- LigandMPNN: https://github.com/dauparas/LigandMPNN
- ProteinMPNN: https://github.com/dauparas/ProteinMPNN
- RFdiffusion: https://github.com/RosettaCommons/RFdiffusion
- Foldseek: https://github.com/steineggerlab/foldseek
- TM-align paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC1084323/
- US-align paper: https://www.nature.com/articles/s41592-022-01585-1
- Rosetta license: https://docs.rosettacommons.org/docs/latest/LICENSE
- Rosetta licensing FAQ: https://rosettacommons.org/licensing-faq/
- EBI Proteins API: https://www.ebi.ac.uk/proteins/api/doc/
- RCSB Data API: https://data.rcsb.org/
- UniProt: https://www.uniprot.org/help/about
- BRENDA: https://www.brenda-enzymes.org/introduction.php
- SABIO-RK: https://www.sabio.h-its.org/
- SABIO-RK RESTful Web Services: https://sabiork.h-its.org/layouts/content/docuRESTfulWeb/manual.gsp
- MaveDB: https://www.mavedb.org/about
- MaveDB GitHub archive: https://github.com/VariantEffect/MaveDB
- MaveDB API Quickstart: https://www.mavedb.org/docs/mavedb/programmatic-access/api-quickstart.html
- FireProtDB 2.0: https://pmc.ncbi.nlm.nih.gov/articles/PMC12807726/
- ProThermDB: https://pmc.ncbi.nlm.nih.gov/articles/PMC7778892/
- CatPred: https://github.com/maranasgroup/CatPred
- CatPred paper: https://www.nature.com/articles/s41467-025-57215-9
- GotEnzymes2: https://academic.oup.com/nar/article/54/D1/D583/8307361
- BoTorch: https://github.com/meta-pytorch/botorch
- BoTorch docs: https://botorch.org/docs/overview
- Ax adaptive experimentation: https://github.com/facebook/Ax
- Ax / Meta engineering: https://engineering.fb.com/2025/11/18/open-source/efficient-optimization-ax-open-platform-adaptive-experimentation/
- PyTorch MPS backend: https://docs.pytorch.org/docs/stable/notes/mps.html
- NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/
- Docker Desktop Mac: https://docs.docker.com/desktop/setup/install/mac-install/
- NIST AI RMF: https://www.nist.gov/itl/ai-risk-management-framework
- NIST Generative AI Profile: https://airc.nist.gov/airmf-resources/airmf/
- ISO/IEC 42001 overview: https://www.iso.org/standard/81230.html
- OECD AI Principles: https://oecd.ai/en/ai-principles
- SPDX: https://spdx.dev/
- SPDX specification: https://spdx.github.io/spdx-spec/v3.0.1/
- CycloneDX: https://cyclonedx.org/
- SLSA: https://slsa.dev/
- Sigstore cosign: https://docs.sigstore.dev/cosign/signing/signing_with_containers/
- W3C PROV: https://www.w3.org/TR/prov-dm/
- RO-Crate: https://www.researchobject.org/ro-crate/
- FAIR Principles: https://www.go-fair.org/fair-principles/
- Croissant: https://docs.mlcommons.org/croissant/docs/croissant-spec.html
- Model Cards: https://arxiv.org/abs/1810.03993
- Datasheets for Datasets: https://arxiv.org/abs/1803.09010
- Hugging Face model cards: https://huggingface.co/docs/hub/en/model-cards
- WHO responsible life sciences guidance: https://www.who.int/publications/i/item/9789240056107
- NIH Guidelines: https://osp.od.nih.gov/policies/biosafety-and-biosecurity-policy/
- IGSC Harmonized Screening Protocol: https://genesynthesisconsortium.org/harmonized-screening-protocol/
- OECD synthetic biology: https://www.oecd.org/en/topics/sub-issues/synthetic-biology.html
- HHS 2023 synthesis screening guidance: https://aspr.hhs.gov/legal/synna/Pages/default.aspx
- OSTP 2024 Nucleic Acid Synthesis Screening Framework: https://bidenwhitehouse.archives.gov/ostp/news-updates/2024/04/29/framework-for-nucleic-acid-synthesis-screening/
- CHS Gene Synthesis Screening Information Hub: https://www.centerforhealthsecurity.org/our-work/research-projects/gene-synthesis-screening-information-hub
- NIH IRP synthetic nucleic acid screening implementation: https://irbo.nih.gov/confluence/pages/viewpage.action?pageId=250740743
- SecureDNA Screening API: https://securedna.org/docs/screening-api/
- SecureDNA FAQ: https://securedna.org/faqs/
- WIPO Sequence: https://www.wipo.int/en/web/wipo-sequence/
- WIPO PATENTSCOPE sequence listings: https://www.wipo.int/patentscope/en/programs/sequences/
- USPTO sequence listing basics: https://www.uspto.gov/patents/apply/applying-online/about-efs-web/checker/patent-applications-specifications
- EPO Open Patent Services: https://www.epo.org/en/searching-for-patents/data/web-services/ops
- Google Patents Public Datasets: https://console.cloud.google.com/marketplace/product/google_patents_public_datasets/google-patents-public-data
- UniProt license: https://www.uniprot.org/help/license
- RCSB PDB policies: https://www.rcsb.org/pages/policies
- wwPDB data download terms: https://www.wwpdb.org/downloads
- SiLA 2: https://sila2.gitlab.io/sila_base/
- AnIML: https://new.animl.org/
- Allotrope technical reports: https://docs.allotrope.org/
- Allotrope Simple Model: https://www.allotrope.org/introduction-to-allotrope-simple-model
- Autoprotocol: https://autoprotocol.org/
- Benchling API: https://docs.benchling.com/docs/getting-started-1
- Benchling Developer Platform: https://help.benchling.com/hc/en-us/articles/9714802977805-Access-Benchling-s-Developer-Platform-and-Documentation-Base
- MLflow Model Registry: https://mlflow.org/docs/latest/ml/model-registry/workflow
- DVC: https://github.com/treeverse/dvc
- Great Expectations GX Core: https://greatexpectations.io/
- DataHub: https://github.com/datahub-project/datahub
- Cradle: https://cradle.bio/
- Cradle platform: https://www.cradle.bio/platform
- Arzeda: https://arzeda.com/
- Arzeda technology: https://www.arzeda.com/technology
- Profluent: https://www.profluent.bio/
- Profluent platform: https://www.profluent.bio/platform
- Basecamp Research: https://basecamp-research.com/
