# 酶蛋白AI平台与AI大模型

> 研究时间：2026-09-03 | 所属领域：工业酶工程 / 蛋白基础模型 / 科研智能体 | 研究对象类型：产品 + 技术范式

## 一、一句话定义

科为博酶蛋白 AI 平台是一套「通用大语言模型做主控、专业蛋白工具做证据、物理模拟与湿实验反馈做校准」的工业酶改造操作系统；它不是 AlphaFold 或 ESM 的替代品，也还不是 Cradle 那种实验数据驱动的封闭 SaaS。它当前真正成立的能力，是把酶身份、编号门控、策略确认、工具降级和科学声明边界写成可执行合同。平台旁边的 `AI大模型/` 目录正在孵化自有多头模型 `KWB-EnzymeDesigner`，但到 2026 年 9 月仍被生产门禁锁死：五头全部 `blocked`，严格监督标签为 0 行，不能对外宣称已有可用预测模型。

把这句话拆开，研究对象其实是两件互相咬合的事。一件是产品：聊天、项目、Wiki、PDB 页、MD、配体预处理、权限和阿里云部署。另一件是模型层：通用 LLM（GPT-5.5/5.6、DeepSeek、预留的 Qwen）如何编排蛋白专用模型（ESM、AlphaFold 系、ProteinMPNN、VenusREM、Boltz），以及科为博要不要、以什么节奏训练自己的酶改造小模型。两条线如果混在一起讲，很容易把「平台能聊天」误写成「模型能预测酶活」。这份报告把它们并排放在同一张时间桌面上，再横向对比国内外竞品和基础模型。

## 二、纵向分析：从诞生到当下

### 2.1 蛋白计算的前史：物理直觉比数据更早

工业酶改造并不是 2020 年才开始用计算机的。1990 年代到 2010 年代，主流工具是力场、同源建模、序列比对和统计势能。Baker 实验室的 Rosetta 把蛋白质折叠写成可采样的能量景观；HMM/PSSM 和 BLAST 把「这条酶像谁」变成可检索的问题；FoldX 一类方法试图用经验势能估计点突变的 ΔΔG。这些工具今天看起来「不够 AI」，但它们留下了一个到现在都没有过时的约束：酶的功能发生在三维口袋、质子化状态、辅因子和底物构象上，而不发生在一段漂亮的自然语言里。

科为博平台后来把 GROMACS、Vina、ACPYPE 写进工具合同，不是为了追赶潮流，而是在补这条物理链路。平台经验记忆写得很硬：本机没有 `gmx`、`obabel`、`vina`、`acpype`、`antechamber` 时，只能做代码层和受控 `blocked`，不能声称真实长 MD 或真实对接已经完成。这条纪律看起来像运维洁癖，其实是在对抗蛋白计算领域最常见的自我欺骗——把接口存在当成计算发生。

早期机器学习并没有缺席。SVM、随机森林和后来的 CNN 都在二级结构、溶剂可及性和简单突变分类上工作过。它们的上限很清楚：标签少、家族偏、编号乱。ProteinGym 后来把这件事变成公开基准，把「突变效应预测」从实验室内部的 Spearman 相关，变成可以横向比较的 DMS 排行榜。科为博自己的监督 baseline 在 2026 年 8 月给出过一组不泄漏数字：validation/test accuracy 约 0.317/0.239。这个数字不好看，但它比「我们用了大模型」诚实。它说明酶改造小模型现在缺的不是 Transformer 名字，而是能对上 UniProt 编号、能对上结构位点、能对上同一套 assay 的标签。

### 2.2 结构预测先爆发：CASP14 把「看见」变成基础设施

2018 年 AlphaFold 1 在 CASP13 已经让人侧目，真正改写行业的是 2020 年 CASP14 上的 AlphaFold 2。DeepMind 用 Evoformer 把多序列比对和成对几何表示做成可端到端学习的系统，单体结构预测第一次在大量靶点上接近实验精度。随后 AlphaFold DB 把上亿条预测结构铺开，Foldseek 让结构检索变得像 BLAST 一样日常。工业酶实验室突然可以在没有晶体的情况下，先问「这个口袋长什么样」。科为博把这件事写进了真实数据层顺序：先 PDB，再 AlphaFold，再 Foldseek DB。PostgreSQL、Redis、MinIO 是底座，不能冒充结构数据。这个顺序看起来像运维清单，其实是在承认 AF2 之后的行业共识——没有结构资产的酶平台，只能做序列聊天。没有 Foldseek，28 万酶记录也只是一张大表；有了它，用户才可能问「还有谁长得像我的催化口袋」。平台已经为结构检索写下远端 API 和本地二进制双入口，缺配置时返回明确降级，而不是编造同源结构。

2021 年 Baker 实验室的 RoseTTAFold 证明这件事可以被复现和扩展。同一年前后，ProteinMPNN 把「给定骨架设计序列」做成可用工具，RFdiffusion 把「给定功能约束生成骨架」做成生成模型。结构预测和结构条件设计在两三年内完成了从论文到工作流的跳跃。NVIDIA BioNeMo 后来把 AlphaFold2、RFdiffusion、ProteinMPNN 收成 blueprint，公开承认这些模型各管一段：折叠置信度不是结合亲和力，设计可折叠不等于可表达、可纯化、有活性。

2024 年 5 月 8 日，AlphaFold 3 发表于 *Nature*。Abramson 等人把扩散模块直接预测原子坐标，把蛋白、核酸、小分子、离子和修饰残基放进同一个复合物模型。对酶平台，这是比 AF2 更关键的一步：底物不再只是一个名字，而可以是口袋里的化学实体。但 AF3 的服务器许可是非商业限制，工业用户立刻面对一个产品问题——精度在闭源那边，可部署在开源这边。

开源阵营的反应很快。2024 年 11 月 MIT 团队发布 Boltz-1，作为一个可商业使用的 AF3 风格共折叠模型。2025 年 6 月 Boltz-2 再进一步，把结构预测和蛋白–配体结合亲和力放进同一套模型，并宣称在部分 FEP+ 基准上接近自由能微扰，同时快三个数量级以上。Boltz 官方页面给出的公开数字是：FEP+（OpenFE）hold-out 靶点上平均 Pearson 约 0.62，CASP16 亲和力子集上超过当时提交方法。这些数字需要带着任务边界读：它们主要针对小分子–蛋白，不是工业酶的 kcat、热稳定性或最适 pH。Chai Discovery 的 Chai-1、百度 PaddleHelix 的 HelixFold3、OpenFold 基金会的 OpenFold3、以及后续 Protenix 等，把 2024–2026 的结构赛道从「一个模型」变成「许可证、速度、亲和力头、抗体界面、可自托管」的多维选择。

科为博平台在代码层注册了 `alphafold2_folding`、`esmfold_folding`。读实现会发现一个必须写进报告的事实：本地 `alphafold2_folding` 明确标记 `capability_status="proxy"`、`is_real_inference=False`，用氨基酸倾向和随机数生成 pLDDT 区间，并警告「未运行官方 AlphaFold2 权重/MSA/模板流水线」。这不是疏忽，是早期为了把工具名接进 agent 而留下的代理合同。平台后来用 `scientific_claim_gate` 和能力审计去约束它，但代理工具本身仍在。纵轴上的这个选择，会在横向对比里变成短板：竞品如果真的跑 VenusREM 或 HelixFold3，用户体感会立刻分出真假。

### 2.3 蛋白语言模型后爆发：进化统计被写成 Transformer

结构模型解决「它长什么样」。蛋白语言模型试图解决「进化允许什么」。Meta 的 ESM 系列把 UniRef 规模的序列统计压缩进掩码语言模型。ESM-1v 证明零样本突变效应有信号，ESM-2 把规模和结构接触预测绑在一起，ESMFold 用语言模型绕过深度 MSA，换速度、让步精度。2024–2025 年 EvolutionaryScale 发布 ESM3：序列、结构、功能三条离散 token 轨道的生成式掩码模型。公开材料写明最大模型约 980 亿参数，训练约 27.8 亿条蛋白、7710 亿 unique tokens；开源的是 14 亿参数的 small。ESM C（Cambrian）则把表征和生成拆开，ESMFold2 后来挂在 ESM C 6B 上。对酶改造，ESM 系最有用的不是「生成一条前所未见的酶」，而是给位点一个进化先验，并在没有 DMS 时提供零样本排序。

生成式序列模型走了另一条路。ProGen / ProGen2 做家族条件生成；EvoDiff 做扩散生成。2025 年 2 月 Arc Institute 与 NVIDIA 发布 Evo 2：在 DNA 单碱基分辨率上训练，上下文可达 100 万 token，最大 400 亿参数，训练数据公开材料写的是约 9.3 万亿碱基、超过 12.8 万个基因组。2026 年该工作进入 *Nature*。Evo 2 对工业酶的直接帮助有限——它更像基因组操作系统，而不是脂肪酶突变排序器——但它把「生物基础模型」的想象从蛋白序列拉到了整段遗传密码。NVIDIA 把它接进 BioNeMo，说明算力厂商要卖的是生物世界模型，而不只是折叠服务。

国内这条线上，BioMap 与清华的 xTrimoPGLM 把蛋白语言模型推到约 1000 亿参数、约 1 万亿 token。预印本 2023–2024 年公开，后续有 Nature Methods 路径的报道。它同时做理解和生成，并衍生抗体专用小模型。HelixFold3 则走结构复制路线：PaddleHelix 明确写「复现 AlphaFold3 能力」，GitHub 学术开源，Web 服务另有 HelixFold3.1/3.2 迭代。2025 年他们又把 HelixFold3 接到 HelixDesign-Antibody 的生产级抗体设计平台。国内大厂更擅长把模型做成云上工作台，而不是把湿实验反馈写成项目对象。

突变效应专用模型是酶工程更贴身的一层。SaProt 用结构感知词表；ProSST / ProtSSN 把局部结构和坐标图引进来；VenusREM 在 2025 年 ISMB/ECCB 发表于 *Bioinformatics*，用检索增强把序列、结构和进化信息融合进突变效应预测，GitHub 自称 2025 年 4 月在 ProteinGym substitution leaderboard 排名第一。Matwings 把 Venus 1.0（序列）→ Venus-ProSST（结构）→ VenusREM（进化检索）写成产品栈，并在 2026 年用四轮 AI–湿实验、222 个变体的公关稿证明闭环。对科为博，Venus 不是远方的论文，而是最近的产品镜子：会话里的分阶段确认、preflight、artifact 交接，已经被本平台调研文档逐条对照过。

### 2.4 通用大语言模型进来之后：主控权从「会折叠」变成「会编排」

GPT-4 之后，科研工具开始被包进对话。2024–2026 年，Claude、Gemini、Qwen、DeepSeek 都在抢「能调工具的长上下文推理模型」。生物这边出现两类用法。一类是实验室助手：查文献、写方案、解释 pLDDT、把 PDB 残基对到 UniProt。一类是伪专业模型：直接让 GPT 输出「N185D 提高 3 倍活力」。前者是平台该做的；后者是平台必须挡住的。

科为博的模型注册表把这件事写进了代码。`llm_registry.py` 里稳定模型 id 是 `gpt55`、`gpt56`、`gpt56-sol`、`deepseek-v4ro`，分别走 kuaPao 中继和 DeepSeek。默认主提供者是 kuaPao，回退 DeepSeek，`LLM_DISABLED_PROVIDERS` 默认关掉 dashscope。配置里仍预留 `qwen3.7-max` 和 MiniMax。`AI大模型/README.md` 的推荐接入方式写得很干脆：

```text
GPT-5.6 主控
  -> 调用 KWB-EnzymeDesigner
  -> 调用结构/注释/MD/配体工具
  -> 汇总证据分层报告
```

长期才考虑让 `KWB-EnzymeDesigner` 升级为主控。这个决策和 2024 年以来蛋白 AI 的真实分工一致：通用 LLM 擅长计划、追问、解释和遵守协议；蛋白模型擅长表示、折叠、设计和打分；物理引擎擅长能量和轨迹；湿实验才有资格升级 claim。Cradle 2026 年 3 月的 bioRxiv 预印本 `cradle-1` 把同一逻辑推到更极端：先用预训练 PLM，再在进化邻域做无监督微调，再用实验数据做监督，然后多模型工作流优化多性质。他们甚至写「结构数据在很大程度上可以被序列–功能对替代」。这句话对抗体亲和力优化可能成立，对工业酶的底物特异性和 pH 工程，我判断仍然危险——口袋几何和质子化不是序列–功能表能完全吸收的。

同一时期，科研 agent 开始从「会检索」走向「会遵守实验室 SOP」。本平台 8 月交付的三层架构，本质上是把 SOP 从文档变成路由表。用户说「把最适 pH 降到 4.5」，策略层只允许走向酸碱工程相关卡片，不允许直接跳进 de novo 生成；路由层给出唯一 workflow，不允许同一句话同时触发稳定性、活性和表达三条互斥深分析；执行层遇到 MSA 缺失、结构缺失、编号冲突时输出 BLOCKED，而不是让 GPT 补一段听起来像证据的话。通用模型在这里的角色被降格得刚刚好：它仍然决定怎么问人、怎么写报告，但它不再决定科学上「可以声称什么」。

这个降格有代价。用户会觉得系统「话少、爱拒绝、确认键太多」。MatVenus 的流畅来自把下一步塞进自然语言里；Cradle 的流畅来自把 round 做成向导。科为博的流畅目前主要来自 SSE 流式和策略确认按钮，科学上则故意不流畅。纵轴走到这里，产品已经选边：先做可审计的酶工程系统，再做让人爽的酶工程助手。两边最终要合并，但合并顺序反了，就会回到 6 月那种代理工具满天飞的状态。

### 2.5 科为博平台自己的生命史：七十多天从聊天壳到可部署操作系统

Git 记录里，仓库在 2026 年 6 月 22 日以 `Protein AI Platform v0.2` 初始化。同一天就有 MD 查看器、批量对比表、HTML 报告导出和项目工作区。它一开始就不是纯聊天机器人，而是「分析工作台 + 对话」的双入口。随后两周，四轨升级并行：ML Docker、ECS 加固、binder design、Outline Wiki。Agent 很快从单模型补成 DataAgent / LiteratureAgent / Coordinator。6 月 30 日已经接到 BRENDA/SABIO、SPECTER2/BioBERT、RFdiffusion 对称化和 i18n。速度极快，也因此留下了代理工具和能力名大于能力实的债务。

7 月之后，项目性格发生变化。用户把「AI 酶改造平台：人工分析流程」定为默认路径：先认识这条酶，再按目标选分析路径，最后整合证据。经验记忆把真实数据层顺序写成 `PDB -> AlphaFold -> Foldseek DB`，把配体顺序写成 `2D SDF -> 3D -> PDBQT -> Vina -> ACPYPE -> GROMACS`。占位 `gromacs_md` 被改成真实 GROMACS 管线接口：没有 `gmx` 时明确失败。脂肪酶文献库 `lipase.db` 被接入为证据源。酶身份画像 `enzyme_identity_profile` 出现，是因为同一条 388 aa SD-WT 案例里，短 motif 被误判成 EC、催化位点没门控、候选数量虚高。从那以后，平台开始用「先证明你是谁」对抗「直接给突变」。

8 月是治理月。MatVenus 会话复盘证明：竞品的核心不是每次重写完整流程，而是维护任务上下文、preflight、分阶段确认和 artifact 交接。本平台修了 `execute_confirmed`：确认执行必须携带 `confirmed_plan + strategy_signature`，校验通过后不再重新规划。同时补上 DBTL 只读 trace、实验反馈导入合同、claim gate、项目 ACL、组织权限、运维告警、备份恢复、发布验收。8 月 27 日的三层架构交付包把产品从「随便聊」锁成「策略层 / 路由层 / 执行控制层」：22 张策略卡决定改什么方向，路由层选出唯一 `workflow_id`，执行层用工具目录和 `scientific_claim_gate` 禁止把预测写成实验结论。

可以把这七十天再切成四个产品性格。6 月是收藏家：把世界上能叫出名字的蛋白模型都登记成工具，RFdiffusion、ProteinMPNN、Chroma、ProGen2、EvoDiff、DiffDock、ESM-2 并排出现。收藏让 agent 看起来能干，也让后来的能力审计变得漫长。7 月是酶工：人工分析流程、身份画像、脂肪酶库、结构位点和 PDB 页成为主舞台，目标从「什么模型都有」变成「先认识这条酶」。8 月是审计官：confirmed plan、DBTL trace、实验反馈合同、claim gate、三层架构、权限和发布验收。9 月初是上线员：ECS、RDS、OSS、公网入口、28 万酶记录。四个性格叠在同一套代码里，所以今天打开产品会同时感到：工具很多、说话很谨慎、后台很重、科学内核还在等电。

9 月 2 日，release `20260902T071756Z-bcf5b2d` 装到阿里云 ECS，公网 `http://120.27.108.138` 的 HTTP smoke 和 live smoke 通过。线上导入结构化酶蛋白库 `enzyme_records=280036`。health 一度报告 `tools_registered=59`，与此前 33 的实测基线存在漂移，文档要求继续对账，不把 59 写成已确认基线。GPU/GROMACS 节点、正式域名 HTTPS、真实 ligand topology live gate、维护窗口回滚演练，仍标为外部依赖。平台在七十天内完成了大多数蛋白 AI 创业公司一年才做完的产品外壳，同时用门禁把科学承诺按住。这是它的独特轨迹：先长出操作系统，再等待模型和算力来填内核。

上线本身也改写了模型问题的优先级。本地 Mac 缺 GROMACS 时，讨论的是合同写得对不对；ECS 上线后，讨论变成：公网用户如果问「帮我把这条酶的热稳定性提高」，系统会调用哪些 live 工具、哪些 proxy、哪些直接 blocked。`progress.md` 把剩余 backlog 收成 `external_required`：域名证书、GPU、ligand runtime、部分演练。也就是说，到 2026 年 9 月 3 日，平台已经不是「能不能做出产品」的问题，而是「产品外壳已经暴露在公网，科学内核还不能跟外壳过同样的生活」。这种时间差，比缺少某个开源模型更危险，因为它会诱惑组织用主控 LLM 去填内核的空。

### 2.6 KWB-EnzymeDesigner：模型目录比模型本身更早成熟

`AI大模型/` 是本地研发区，默认不同步服务器。对外名字统一叫 `KWB-EnzymeDesigner`，内部不是一个黑盒分数，而是五个头：突变排序、稳定性、活性风险、底物适配、实验成功率。路线图写明 V1 用自有数据做多头排序，V2 加结构几何，V3 加 MSA/家族，V4 做真实反馈闭环。GPT-5.6 继续主控。

到 2026 年 8 月 29 日的状态快照，流水线已经像一座建好但没通电的工厂。规则 MVP 和 6-case 本地 benchmark 通过；监督训练表、protein-group split、编号审计、weak evidence 降级、安全训练入口、生产 gate 校验脚本都在。文献 measurement registry 有 870 条唯一候选，全部 evidence-only。五头 `ready_head_count=0`，`training_execution_allowed=false`，`safe_for_model_claim=false`。`activity_risk` 头有 6 行标签，离 100 行门槛仍远；其余头是 0 行。500 条 mutation labels 里只有 25 条能与当前 UniProt 编号直接验证，475 条降为 weak evidence。无标签 MLM 预训练在 MSA 序列上跑过若干批次，validation loss 在 2.83–2.94 区间，报告明确禁止解释成下游准确率。

后端工具 `kwb_enzyme_designer` 把这些数字变成运行时行为：读生产 gate 报告，`production_ready` 不是 true 就返回 `blocked_pending_production_gate`，`inference_executed=False`，`candidates=[]`。它故意不回退到规则或 proxy。这是纵轴上最重要的一次「反向加速」：团队已经有能力做出看起来能打分的接口，但选择让接口失败。和 6 月底那些随机 pLDDT 的代理折叠工具相比，8 月底的自有模型入口活成了另一种动物。平台在两个月里学会了：工具名可以先存在，模型声明不能先存在。

训练侧还有一条容易被忽略的支线：无标签序列 MLM。`findings.md` 记录第一轮在 158 条 MSA 目标序列上跑通 masked amino-acid 训练，随后发现 checkpoint 文件名互相覆盖、重复序列造成 embedding 碰撞、去重后碰撞消失。全量唯一序列被切成 26 个可恢复批次，至少跑完前 15 批，validation loss 稳定在约 2.88 上下。这条支线证明两件事。第一件，本地有人认真对待「先有表征、再有监督」，而不是一上来微调五头。第二件，表征实验被正确地隔离为 pretraining-only artifact：它不能解锁监督训练，也不能写成突变准确率。对一个工业酶团队，这种隔离比多跑几个 epoch 更值钱。因为一旦把 MLM loss 下降讲成「模型已经懂脂肪酶」，后面的编号审计和 wet-lab QC 都会失去政治空间。

国际对标文档 `international_benchmark_2026.md` 把自有模型的位置写死了：蛋白语言模型给先验，结构模型给几何，结构条件生成给候选，实验反馈给校准，主控 LLM 给编排。KWB-EnzymeDesigner 只应成为其中的专业工具模型。我认同这个分工。不认同的是一种隐性期待——等五个头都到 100 条标签再一起发布。工业上更常见的是先发布一个窄头，比如热稳定，在单一家族、单一 assay 上做到可复现的排序增益。窄头不会让平台变成 EvolutionaryScale，但能让「自有模型」从目录走进一次真实的项目 round。前提仍是编号和 QC，不是换更大的 backbone。

## 三、横向分析：竞争图谱

当前截面是场景 C，竞品充分。不能把所有「做蛋白 AI」的公司放进同一张桌子。按科为博的定位——工业酶、对话式研发、证据门控、将来的干湿闭环——分层如下。

### 3.1 Direct：直接争夺同一类用户注意力

**Matwings / MatVenus。** 上海的对话式蛋白工程平台，也是本项目调研最多的镜子。它把自然语言任务拆成技能和专家服务，强调设计即验证。Venus 模型栈从序列走到结构再走到检索增强突变预测。公开技术叙事很完整：Venus 1.0 做序列中心建模，Venus 2.0 / ProSST 引入三维结构，Venus 3.0 / VenusREM 再加进化检索，旁边还有 Venus-FSFP、Venus-Maxwell、Venus-Mine、Venus-RXN、Venus-Fold 等任务模型。2026 年公关披露与合作方一起完成四轮闭环、222 个变体，并成立 Biowings 做内部管线；同一时期还有 GenSci148 进入国内临床试验相关报道，用来证明闭环不只存在于酶工程演示。

用户选它的理由通常是：会说话、有湿实验和专家托底、突变模型在 ProteinGym 上有公开成绩。本平台从真实会话里看到的机制更具体：`preflight_only=true` 先报价和确认，用户说「那你开始吧」只提交当前阶段，artifact 路径交给下一阶段，只有「重新执行任务」才全链路重跑。这套节奏把对话从聊天变成了可恢复的实验室班组会。

槽点同样具体。公开材料里的高成功率、倍数和「100%」表述不能当方法学。本平台复盘过的会话里出现过编号映射和工具参数错误。FAQ 自己也承认，更准确的结果需要 PDB、实验通量和湿实验数据。也就是说，MatVenus 对外卖的是闭环体验，对内真正起作用的仍是结构和实验。科为博学了它的阶段确认，拒绝了它的话术强度。两者若在同一客户处相遇，比的不是谁更像 ChatGPT，而是谁更少在编号上犯错、谁能把上一轮测过的单点送进下一轮组合检查。

**Cradle。** 阿姆斯特丹的蛋白工程 SaaS。产品页写科学家训练和运行蛋白 AI，把传统工作流缩短到 2–12 倍；阿姆斯特丹湿实验室持续验证平台内核，并强调客户数据训练出的模型保持私有。它的产品原语是蛋白质类型、是否已有实验数据、这一轮要做什么，然后引导数据准备、训练、生成、评估和选板。traceability 被写成可见关系：哪一版模型生成了哪些候选。

2026 年 3 月 `cradle-1` 预印本把 lead optimization 写成自动化框架，覆盖 VHH、scFv、IgG、肽、酶、CRISPR、疫苗，并给出相对理性设计 4–7 倍更快（以湿实验轮次计）的体外验证叙述。技术上它从预训练 PLM 出发，在进化邻域做无监督微调，再用 lab-in-the-loop 数据做监督，最后进多模型工作流。作者是 Cradle 员工，数字需要当公司研究读，不能直接当成第三方评测。即便如此，方向是清楚的：他们赌「能测的性质就能优化」，结构不是第一公民。

用户选它的理由是：上传实验数据，模型按项目变好，多性质一起优化，不必自建 ML，也不必把研发流程说成聊天。槽点来自同一设计：没有项目数据时，零样本能走多远，公开材料说得比较虚；对没有高通量 assay 的传统酶企，Cradle 可能过重。它几乎不靠聊天赢，靠 round、dataset、model version 和 plate。对工业酶客户，Cradle 是「数据闭环成熟度」的上限参照。科为博今天还没有资格在这一层正面开战，但 8 月已经把实验反馈、Go/Watch/No-Go、上位性检查和只读 DBTL trace 做成了预演。预演和自动微调之间，差的是对象模型和标签纪律，不是再做一个聊天模型。

**MoleculeMind / MoleculeOS。** 国内一站式蛋白设计，公开强调酶活、选择性、热稳定、表达和抗体/de novo 工作流，并提供对话 Agent 入口。公开材料喜欢讲多目标设计和湿实验验证过的例子，同时把部分数据保密。中文用户会在它和科为博之间感到直接替代：都是对话，都谈工业酶，都承诺把结构、设计和报告串起来。

差异要看证据层。MoleculeMind 更像生成式设计平台，把工作流包装成可调用的设计引擎；科为博更像带治理的研发操作系统，先问身份和编号，再允许候选进入排单。MoleculeMind 的公开案例如果带着 withheld data，客户无法判断那是个别成功还是可迁移方法。科为博的相反风险是：证据层太显眼，候选表太小心，第一次使用的人会觉得「系统很专业但没给我能测的突变」。这块心智争夺，短期不取决于谁的 foundation model 更大，而取决于谁先在一个真实工业酶项目上交出可复核的轮次记录。

### 3.2 Adjacent：能力重叠，客户不完全相同

**OpenProtein.AI** 把 assay dataset 和 job 做成一等对象，零样本、自定义训练、结构预测可组合。作业有 ID、状态、前置作业、进度和失败信息。它是数据/作业原语的教科书，不是酶交付公司。科为博的 Celery 长任务、artifact manifest 和 task audit 已经朝这个方向走，但还没有把「assay 数据集」提升到和「对话」同级的产品对象。谁先把实验表变成一等公民，谁就更接近 Cradle，而不是更接近又一个 ChatGPT 套壳。

**Arzeda** 做工业酶的设计到生产，物理建模加十余年结构化实验数据和法规、配方、制造约束。它卖的是酶产品，不是软件席位。对科为博的启发不是抄界面，而是策略卡里必须出现底物、assay、表达宿主和放大约束。没有这些，对话里的「提高活力」会在工厂门口作废。

**PaddleHelix / HelixDesign** 是云上结构与抗体工作台，HelixFold3 可学术使用，商业需另谈。2025 年 HelixDesign-Antibody 论文把 HelixFold3 接到可规模化的抗体候选生成和抗原相互作用评估，并强调 HPC 和高通量。腾讯 iDrug、深势玻尔、阿里云/百度云的结构预测门户属于算力工作台：提交任务、看结构、下载结果。它们会在「折叠和设计工具」上碰到科为博，但不会在「这条脂肪酶该不该改 N185、编号对不对、实验反馈能不能进下一轮」上碰到科为博。科为博若把自己活成又一个折叠门户，会直接撞上这些巨头的免费或低价入口。

**Absci、Profluent、Generate:Biomedicines** 是生成式生物医药，自研 foundation model 加内部湿实验，主战场是抗体和治疗蛋白。酶是他们的能力菜单，不是销售主轴。Generate 的 Chroma、Profluent 的 ProGen 系、Absci 的生成加高通量筛选，展示的是「模型公司养一座湿实验室」的上限。科为博没有必要模仿他们的分子类型，但必须承认：没有实验装置的生成模型，在工业酶上会很快变成文献综述机。

### 3.3 Aspirational：定标尺，不抢同一单

DeepMind AlphaFold Server 定结构精度标尺。EvolutionaryScale Forge 定蛋白生成式基础模型标尺。NVIDIA BioNeMo 定可编排模型微服务标尺。BioMap/xTrimo 定国内千亿蛋白语言模型标尺。这些玩家不靠给一家酶制剂公司做项目制改造吃饭，但他们决定了「什么叫现代蛋白 AI」的词汇表。科为博必须会说这些词，并且在报告里写清自己有没有真正跑起来。

### 3.4 模型横向：不要用一个排行榜打所有仗

| 模型 | 机构 | 公开时间 | 模态 | 开源/许可 | 对工业酶的真实用处 | 主要短板 |
|---|---|---|---|---|---|---|
| AlphaFold 3 | DeepMind / Isomorphic | 2024-05 | 复合物结构 | 服务器非商业限制 | 底物/辅因子口袋几何 | 工业自托管受限 |
| Boltz-2 | MIT Jameel / Recursion | 2025-06 | 结构 + 小分子亲和力 | MIT | 配体筛选、复合物姿态 | 不是 kcat/Tm 模型 |
| Chai-1 | Chai Discovery | 2024 | 多模态共折叠 | 权重/API 需核 | 复合物探索 | 工业许可需核 |
| HelixFold3 | 百度 PaddleHelix | 2024-08 起 | 复合物结构 | 学术开源 | 国内可落地的 AF3 替代候选 | 商业合作另议 |
| ESM-2 / ESMFold | Meta | 2022–2023 | 序列表征 / 快速折叠 | 开源 | 位点先验、快速结构 | 精度和复合物弱于 AF3 |
| ESM3 | EvolutionaryScale | 2024–2025 | 序列/结构/功能生成 | 1.4B 开源，大模型 API | 条件生成、多模态提示 | 98B 不可随便自托管 |
| ProteinMPNN / LigandMPNN | Baker lab 等 | 2022 / 后续 | 结构条件序列设计 | 开源 | 固定骨架改序列、配体环境 | 不保证活性和表达 |
| RFdiffusion | Baker lab / IPD | 2023 | 骨架生成 | 开源 | de novo、口袋脚手架 | 酶催化机制仍要后处理 |
| VenusREM | Matwings / 高校合作 | 2025 | 突变效应 | 研究代码公开 | 零样本突变排序 | 排行榜≠该酶该 assay |
| SaProt / ProSST | 学术团队 | 2023–2024 | 结构感知 PLM | 开源 | 突变与表征 | 依赖结构质量 |
| xTrimoPGLM | BioMap / 清华 | 2023–2025 | 理解 + 生成 | 100B INT4 等 | 通用蛋白表征 | 结构非原生训练信号 |
| Evo 2 | Arc / NVIDIA | 2025–2026 | DNA 基因组 | 开源权重 | 远期基因组设计 | 不直接做酶点突变 |
| ThermoMPNN | 学术 | 近年 | 热稳定 | 研究代码 | 稳定性头的公开基线 | 覆盖家族有限 |
| GPT-5.6 / DeepSeek / Qwen | 通用模型公司 | 持续迭代 | 文本+工具 | API | 主控、报告、协议遵守 | 无酶几何，易幻觉 |

ProteinGym 的价值是给「突变适应度」一个公共球场。VenusREM、ESM3、ProGen3、xTrimoPGLM 都陆续被加进 baselines。工业酶项目不能直接把 leaderboard 第一翻译成「这株脂肪酶改完能涨活力」。DMS 多数不是工业条件，标签是适应度或结合，不是反应器里的时空收率。Cradle 之所以强调上传你自己的实验，就是因为公开基准到产品性能中间还隔着一层项目数据。

### 3.5 科为博在这张图上的位置

它现在占住的是一块还不拥挤、但很容易被说成「什么都有一点」的格子：

- 对话式，像 MatVenus，但 claim 更紧。
- 有项目、Wiki、权限、审计、备份，像内部 SaaS，但不像 Cradle 那样每轮自动训练。
- 工具目录覆盖折叠、设计、对接、MD、注释，但相当一部分是 proxy 或缺 runtime 的 blocked。
- 有私有脂肪酶证据库和 28 万酶记录，可这不是 foundation model，是检索和门控的燃料。
- 有自有模型品牌和完整训练治理，可还没有可发布的权重。

用户如果要「给我五条突变、下周测」，今天更可能被 MatVenus 或 MoleculeMind 的流畅话术吸走，除非科为博用身份核验、编号门控和「我不知道」把专业用户留下来。用户如果要「把我们三轮 96 孔板的数据变成下一轮库」，今天会被 Cradle 吸走，除非科为博尽快把实验反馈从项目记忆升级成可学习的 assay 对象。用户如果只要「把序列折起来」，会被云厂商吸走。科为博不该在那一层死磕。

生态位可以写得更狠一点。卖算力的是云和 BioNeMo。卖基础模型的是 EvolutionaryScale、BioMap、DeepMind。卖 DBTL 软件的是 Cradle 和 OpenProtein。卖对话加湿实验服务的是 Matwings。卖工业酶分子本身的是 Arzeda 和传统酶企。科为博若做成，卖的是「酶企研发操作系统 + 将来的自有多头模型」，中间态只能靠诚实的工具状态和私有数据积累活下去。

## 四、横纵交汇洞察

### 4.1 历史如何塑造了今天的位置

6 月底的速度决定了平台现在「看起来像全能蛋白工作台」。Agent、Wiki、RFdiffusion、MD 查看器在第一周就出现，工具名先于真实 runtime 进注册表。这让横向对比时，目录很漂亮，实测会露馅。7–8 月的治理转向决定了平台「说起话来像监管者」。酶身份、编号门控、confirmed plan、claim gate、生产模型入口 fail-closed，都是在还债。今天的核心优势——用户难以从本平台得到一句无法追溯的科学谎言——直接来自那段还债史，尤其来自 SD-WT 误判和 MatVenus 复盘。今天的核心劣势——真实折叠/对接/长 MD/自有模型都还没通电——也来自同一段历史：先做操作系统，GPU 和标签后到。

自有模型目录比模型更早成熟，是另一件被历史锁死的事。团队看见了国际多模型系统，于是先写五个 head、schema、gate、model card。这避免了把 GPT 输出包装成 KWB 模型，但也让「AI 大模型」在对外叙事上容易超前。正确的对外句子只有一句：我们有模型研发体系和门禁，还没有可发布的酶改造模型。

### 4.2 把竞品也放到时间线上

AlphaFold 系走的是「先精度、后许可、再开源追赶」。ESM 系走的是「先进化统计、再多模态生成」。Venus 走的是「先突变模型、再对话和湿实验公司化」。Cradle 走的是「先实验对象和轮次、再 foundation + 自动微调」。科为博走的是「先对话操作系统和治理、再补物理 runtime 和标签」。四条路径会在 2026–2027 汇合到同一点：谁能把项目级湿实验变成下一轮模型的合法输入。谁先到达，谁就从工具目录竞争进入命中率竞争。

通用 LLM 的纵向也很清楚。2023 年它们是聊天窗口，2024 年是 Copilot，2025–2026 年是带工具的 agent。科为博把 GPT-5.6 放在主控位，是承认通用模型的规划能力已经够用，蛋白专业能力必须外置。这个判断与 BioNeMo blueprint、与本平台三层架构、与 `KWB-EnzymeDesigner` 不当主控的路线图一致。风险在于主控太强、工具太假时，报告仍然好看。claim gate 是目前唯一挡在这中间的硬装置。

### 4.3 优势与劣势的历史根源

优势一：fail-closed 文化。来自代理工具伤过自己、来自用户要求真实能力必须真实执行。它让平台在专业用户面前有可信度。

优势二：酶身份和编号作为前置条件。来自具体误判案例，不是抽象最佳实践。工业酶最脏的问题往往不是模型，而是「你说的 185 是哪一套编号」。

优势三：产品化底座。权限、审计、备份、OSS、发布包、阿里云分角色部署，来自要上线而不是停在 demo。Cradle 之外，不少学术模型平台在这里是空白。

优势四：私有脂肪酶证据和酶记录库。来自科为博自己的业务积累，这是通用基础模型买不到的。

劣势一：科学内核大量 proxy。来自 6 月为了让 agent 有工具可调。AF2 本地入口仍会生成随机置信度，只是被标记了。

劣势二：没有 GPU/GROMACS 真节点。来自基础设施时序，不是算法失败。物理链路合同写完了，电没接上。

劣势三：监督标签被编号现实击穿。来自公开/内部突变表与当前 UniProt 对不上。流水线 ready 而数据不 ready，是 2026 年蛋白 ML 的常见死因，科为博没有幸免。

劣势四：对话主控是通用模型。来自务实选择，但也意味着平台的「智能」会随 kuaPao/DeepSeek 波动，且任何未门控的自由生成都可能漏出过强结论。

当初的好决策里，有两个正在变成包袱。一是「先把所有著名模型登记成工具」——目录 completeness 变成了真实性负担。二是「自有模型要五头齐备才训练」——门槛保护了声明，也可能让单头小模型（比如只做热稳定排序）迟迟不能在内部以 `exploratory` 身份跑起来。我的判断是：对外声明继续五头合取；对内可以让单头在 `not for customer delivery` 标签下学习，但必须沿用现在的 model card 禁令。

### 4.4 三个剧本

**最可能。** 2026 年第四季度到 2027 年上半年，阿里云 GPU 节点到位，Boltz 或 HelixFold3、真实 ESM 推理、GROMACS 短程 MD 和配体 3D 链路逐个从 proxy/blocked 变成 live。KWB-EnzymeDesigner 仍不能五头齐发，但热稳定或突变排序中的一个头，在修复编号后的几十到上百条严格标签上给出低于公开 VenusREM、高于随机的内部分数。平台靠身份门控和策略确认稳住工业用户，命中率仍主要来自规则、结构和文献证据，而不是自有神经网络。通用 LLM 继续做主控。这个剧本不辉煌，但和当前门禁、数据现实、部署现实同向。

**最危险。** GPU 仍不到，销售或演示压力把 proxy 折叠和 LLM 叙述推到客户面前。竞品用 VenusREM 真推理和湿实验案例打脸。自有模型目录继续膨胀，870 条文献候选被口头升级成「训练集」。一旦发生一次编号错误导致的湿实验失败，fail-closed 文化会在组织内部破产。这个剧本的点火器不是技术，是把「工具已注册」说成「能力已上线」。

**最乐观。** 私有脂肪酶与项目湿实验在 2027 年攒出可学习的序列–功能对，Cradle 式 round 对象在平台落地。KWB-EnzymeDesigner 不必做到 ESM3 规模，只要在科为博关心的酶家族、底物和工艺条件下，校准后的排序稳定优于零样本公开模型。Boltz-2 类开源复合物模型处理底物姿态，GROMACS 做关键候选的物理复核，GPT 类模型只负责协议和解释。那时平台才从「诚实的操作系统」变成「可迭代的酶设计引擎」。乐观不等于幻想：缺的不是 transformer 论文，是同一套编号下、带 QC 和 replicate 的实验表。

### 4.5 交汇处的那句判断

蛋白 AI 这六年的主线，不是大模型吃掉生物化学，而是「看见结构、读懂进化、生成候选、用实验回写」四段能力被拆开，再被产品重新焊在一起。通用大语言模型是很好的焊枪，也是很好的造假工具。科为博平台目前焊枪已经握在手里，焊点（门控、身份、策略、审计）打得比多数国内对话产品更认真；被焊的钢板（真折叠、真对接、真 MD、真标签）还没到货。

所以，不该问「我们有没有 AI 大模型」。该问的是：主控 LLM 有没有被协议绑住；蛋白专用模型有没有 live 而不是 proxy；自有小模型有没有合法标签；湿实验有没有对象化。四问里，今天只有第一问勉强算是。其余三问，是下一阶段唯一值得投入的纵轴。

如果一定要用一句更刺的话收束：2026 年的酶蛋白 AI，已经不再缺会写突变的模型，缺的是敢把「这句突变建议从哪条证据来、编号对不对、能不能进湿实验」写成系统行为的产品。科为博在后一件事上走得比模型界大多数人更远，在前一件事上还站在起跑线。这个不对称不是缺陷叙事，是战略窗口——前提是窗口被用来接电和收标签，而不是用来把目录写得更长。接电指的是 GPU 上的真实折叠、对接和短程 MD；收标签指的是同一套编号下、带 QC 与重复实验的序列–功能表。两件事都比再登记一个开源模型名字更接近工业酶的命中率。目录可以继续长，但命中率只跟 live 推理和合法标签一起长。这一点要写进下一轮计划。

## 五、信息来源

平台与自有模型（本地，访问日期 2026-09-03）：

- `README.md`、`AGENTS.md`、`task_plan.md`、`findings.md`、`progress.md`、`docs/project-experience-memory.md`
- `docs/designs/2026-08-11-ai-protein-platform-strategy-state-research.md`
- `AI大模型/README.md`、`AI大模型/roadmap.md`、`AI大模型/research/international_benchmark_2026.md`、`AI大模型/model_cards/KWB-EnzymeDesigner-heads.status.md`
- `AI酶工程平台三层架构_交付包_v2_20260827/README.md`
- `backend/app/core/llm_registry.py`、`backend/app/core/config.py`、`backend/app/tools/kwb_enzyme_designer.py`、`backend/app/tools/alphafold2_folding.py`
- Git 日志：2026-06-22 初始化至 2026-09-02 上线记录

外部来源（访问日期 2026-09-03）：

- AlphaFold 3：https://www.nature.com/articles/s41586-024-07487-w
- ESM3：https://www.science.org/doi/10.1126/science.ads0018 ；https://github.com/evolutionaryscale/esm
- Boltz-2：https://doi.org/10.1101/2025.06.14.659707 ；https://boltz.bio/boltz2 ；https://jclinic.mit.edu/boltz-2-towards-accurate-and-efficient-binding-affinity-prediction/
- Evo 2：https://arcinstitute.org/news/evo2 ；https://www.nature.com/articles/s41586-026-10176-5 ；https://github.com/ArcInstitute/evo2/
- HelixFold3：https://arxiv.org/html/2408.16975v3 ；https://github.com/PaddlePaddle/PaddleHelix/tree/dev/apps/protein_folding/helixfold3
- xTrimoPGLM：https://arxiv.org/html/2401.06199 ；https://github.com/biomap-research/xTrimoPGLM
- VenusREM：https://doi.org/10.1093/bioinformatics/btaf189 ；https://github.com/ai4protein/VenusREM
- ProteinGym：https://github.com/OATML-Markslab/ProteinGym ；https://pmc.ncbi.nlm.nih.gov/articles/PMC10723403/
- Cradle：https://www.cradle.bio/platform ；https://www.biorxiv.org/content/10.64898/2026.03.06.710001v2
- Matwings 闭环公关：https://www.wfmz.com/news/pr_newswire/pr_newswire_health/matwings-demonstrates-closed-loop-protein-ai-through-four-ai-wet-lab-cycles-and-222-protein/article_8f3aa2ef-5728-5e2e-9f1c-07492c3b8ad4.html
- 结构模型综述与对比：https://intuitionlabs.ai/articles/biology-foundation-models-comparison ；https://purna.ai/blog/alphafold-vs-boltz-vs-esmfold/ ；https://scalingbiotech.substack.com/p/open-source-protein-models-openfold
- ProteinMPNN：https://pubmed.ncbi.nlm.nih.gov/36108050/
- ProGen / ProGen2：https://arxiv.org/abs/2004.03497 ；https://arxiv.org/abs/2206.13517

公开竞品的融资额、未在论文或官方页面出现的准确率数字，本报告标为不采用，不编造。Boltz-2 亲和力数字、Cradle 倍数、Matwings 变体数量均来自各自公开稿，解读时已注明任务边界。

## 方法论说明

本报告采用数字生命卡兹克提出的横纵分析法：纵轴还原蛋白 AI 与科为博平台从起源到 2026 年 9 月的因果历程，横轴在同一时间截面对比平台竞品与基础模型，交叉处给出可证伪的判断，而不是把前文缩写成结论。
