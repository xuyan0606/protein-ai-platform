# 酶蛋白 AI 平台专业化竞品调研与反超路线

日期：2026-08-18

## 结论

前一轮调研只够判断方向，不够支撑研发排期。补充调研后，结论更明确：平台要比 Venus 更专业，不能停在“报告格式更顺、措辞更谨慎”。真正要做的是把平台升级为酶工程决策系统，围绕酶身份、反应、催化机制、结构因果、多目标评分、实验设计和反馈学习建立可追溯数据结构。

Venus 的近期优势主要在三点：位点级解释更像人工专家、候选表更会排序、能对用户指定突变做复核。国外成熟平台和工具链的优势更深：Cradle/Arzeda 强在湿实验数据闭环和多目标设计，Schrodinger/Rosetta 强在物理建模，PROSS/FireProt/FuncLib/HotSpot Wizard/CAVER 强在蛋白或酶工程专项方法。我们要超过 Venus，应优先补齐“酶专属证据层 + 位点特征表 + 实验反馈闭环”，而不是继续堆通用 AI 文案。

## 调研范围与证据等级

| 类型 | 对标对象 | 主要价值 | 证据等级 |
|---|---|---|---|
| 直接竞品 | Venus / MatwingsVenus | 对话式蛋白工程、候选表、指定突变复核、实验反馈解释 | 本地真实会话和用户对比材料 |
| AI 蛋白工程平台 | Cradle, OpenProtein.AI | 项目/轮次/数据集/模型/候选闭环，多目标优化 | 官方资料 |
| 工业酶平台 | Arzeda | AI + 物理建模 + DBTL + 制造/应用条件约束 | 官方资料 |
| 物理建模平台 | Rosetta, Schrodinger | ddG、packing、docking、FEP/MD、企业级工作流 | 官方资料/论文生态 |
| 酶/蛋白专项工具 | PROSS2, FireProt, FuncLib, HotSpot Wizard, CAVER | 热稳定性、表达、功能库、热点、通道/隧道 | 论文/官方工具 |
| 酶知识库 | UniProt, Rhea, M-CSA, BRENDA, SABIO-RK | EC、反应、催化残基、动力学、pH/温度/底物条件 | 官方数据库 |

## 竞品能力矩阵

| 对象 | 领域焦点 | 专业能力 | 对我们的启发 | 必须反超点 |
|---|---|---|---|---|
| Venus | 对话式蛋白工程 | 候选位点表、功能残基预测、指定突变复核、实验反馈解释 | 学它的位点级解释和“预测 vs 实验反馈”复盘 | 增加酶身份、反应、催化机制、实验条件门控，避免只像报告专家 |
| Cradle | AI 蛋白工程 SaaS | 多目标优化、实验数据训练、自定义模型、板设计、同一 workspace 积累数据 | 项目轮次、实验数据、候选选择必须结构化 | 做酶专属 DBTL：底物、kcat/Km、Tm、pH 曲线、表达体系全部入库 |
| OpenProtein.AI | 蛋白数据/模型工作流 | assay dataset、job、zero-shot/custom model、异步任务 | 把数据集、模型和任务状态做成一等对象 | 不只预测性质，还要绑定酶学 assay 条件 |
| Arzeda | 工业酶/蛋白设计 | AI + 物理设计 + DBTL + 应用/制造条件 | 酶产品要考虑应用条件、表达、制程、配方 | 做“应用条件优先”的酶改造，不只在 pH 7 buffer 里排序 |
| AlphaFold/AlphaFold Server | 结构与复合物预测 | 蛋白结构、互作、复合物预测、结构置信度 | 结构是输入证据和空间约束，不是功能结论 | 报告必须显示 pLDDT/PAE/覆盖率/缺失残基与能否解释位点 |
| Rosetta | 物理建模与设计 | energy、packing、stability、interface、enzyme design | ddG/packing 适合成为候选评分的一层 | 把 Rosetta/FoldX 作为评分证据，不让 LLM 直接给突变理由 |
| Schrodinger | 企业级分子建模 | 物理建模、数据分析、协作、配体/蛋白工作流 | 大客户要可复现、可协作、可归档 | 做轻量版“建模证据账本”，每个结论能追到参数和 artifact |
| PROSS2 | 稳定性/表达优化 | 结构 + 同源序列约束，主动避开活性位点，输出多套不同激进程度设计 | 热稳定性模块要同时看保守性、结构能量、活性位点排除 | 增加酶活保持门控，不能只优化稳定性 |
| FireProt | 热稳定性自动设计 | 能量/进化/保守性组合，面向 thermostable protein design | 建立热稳定性候选池分桶 | 加入酶口袋/通道/活性风险，使增稳不是孤立目标 |
| FuncLib | 功能位点库设计 | 围绕活性位点组合突变，做 functional library | 比活/底物特异性要做位点组合库，而非单点 TopN | 输出低通量可验证的智能库：位点、氨基酸集合、组合规模 |
| HotSpot Wizard | 酶热点/智能库 | 酶工程热点，覆盖活性、稳定性、特异性、选择性 | 适合做“突变热点解释器” | 结合我们自己的实验反馈和客户 assay，形成项目专属热点 |
| CAVER/Caver Web | 通道/隧道分析 | 底物/产物通道、瓶颈半径、通道残基 | 酶活和底物谱常常由通道/入口控制 | 将 tunnel/pocket/channel 特征纳入每个位点评分 |
| BRENDA/SABIO-RK/Rhea/M-CSA | 酶学知识底座 | 反应、底物、kcat/Km、Km、pH、温度、催化残基、机制 | 报告必须先定义“这个酶催化什么、怎么催化、在什么条件下测” | 建立酶专属知识图谱，不让通用蛋白平台在酶学专业度上压过我们 |

## 当前平台差距

当前平台已经完成的基础能力：

- 有 `enzyme_identity_profile`、`enzyme_objective_module_plan`、`catalytic_site_lookup`、`residue_mapping_sifts`、`structure_search_foldseek`、`mutation_priority_score`、`mutation_scan`、`protssn_score`、`kcat_predict` 等工具入口。
- 有报告质量 contract，能阻断旧模板、错误顺序、过度候选输出和工具来源不透明。
- 有 PDB-only/HM gate，能防止把结构相似性、坐标顺序推断和启发式 kcat 写成确定酶工程结论。
- 有初步实验反馈/经验存储，但尚未升级为项目级模型校准和候选学习闭环。

仍缺的关键能力：

1. 缺“反应层”：Rhea/ChEBI substrate/product/reaction direction 尚未成为报告主干。
2. 缺“酶学条件层”：BRENDA/SABIO-RK 的 kcat、Km、specific activity、pH、温度、底物、突变体、物种和测定条件没有形成统一 baseline registry。
3. 缺“催化机制层”：M-CSA 式 catalytic role、mechanistic step、first shell/second shell 还没有变成位点保护和解释核心。
4. 缺“位点结构特征表”：relSASA、到催化簇距离、到配体/金属/二硫键距离、B-factor/RMSF、pLDDT/PAE、保守性、口袋/通道归属、ddG、packing clash 还没有统一输出。
5. 缺“酶目标评分器”：热稳定性、比活、kcat/Km、Km、底物谱、pH 活性、表达/可溶性仍未形成分目标评分 + 冲突解释。
6. 缺“指定突变复核器”：用户给 T32A/P338T 这类突变时，需要逐个输出预测、机制、风险、实验反馈解释和下一轮补偿位点。
7. 缺“实验轮次闭环”：WT baseline、变体、assay 条件、实验结果、预测偏差、下一轮设计没有形成强约束数据模型。

## 反超 Venus 的产品模块

### M1 酶身份与反应画像

输入：FASTA、PDB/mmCIF、UniProt ID、用户提供 EC/底物/物种。

输出：

- identity_status：identified / candidate / unresolved / conflict
- EC 与反应候选：EC、Rhea、底物、产物、方向、辅因子
- family/domain/site：InterPro/Pfam/PROSITE/dbCAN/CAZy
- sequence/structure coverage：链、缺失残基、编号体系、SIFTS 映射状态

验收：身份和编号未通过时，不输出可下单突变表。

### M2 催化机制与禁改位点

输出：

- catalytic residues：残基、角色、来源编号、用户编号、证据来源
- first shell / second shell / cofactor / metal / disulfide / glycosylation / signal peptide
- protected_positions 与 pending_numbering

验收：候选命中 catalytic/metal/disulfide/essential binding 位点时自动降级或阻断。

### M3 位点级结构-功能特征表

每个残基至少记录：

- structural：relSASA、二级结构、core/surface、B-factor 或 pLDDT、缺失/低置信区
- spatial：到催化簇、底物、金属、二硫键、结构域界面、通道瓶颈的距离
- evolutionary：conservation、MSA entropy、family-site annotation
- physics：ddG、packing、clash、hydrogen/salt bridge gain/loss
- dynamics：MD RMSF、loop/flap/gate 标记
- enzyme semantics：first shell、second shell、pocket entrance、substrate channel、remote network

验收：候选表必须由该特征表生成，不能由 LLM 直接编排。

### M4 多目标酶工程评分器

评分拆为独立分量：

- activity_score：口袋/二壳层/通道/机制相关性
- stability_score：ddG、packing、柔性、盐桥、疏水核心、二硫键可行性
- specificity_score：目标/非目标底物口袋匹配和选择性风险
- ph_profile_score：pKa、表面电荷、酸碱稳定性、pH 曲线证据
- expression_score：分泌信号、疏水暴露、聚集、降解热点
- risk_score：催化位点、保守位点、配体/金属/界面、编号不确定、实验条件缺失

输出必须同时给出 `score_components`、`blocking_reason` 和 `assay_required`。多目标任务不允许压成一个总分。

### M5 指定突变复核与反馈解释

用户给突变清单时，平台应输出：

- 原始预测：每个突变对 activity/stability/specificity/pH/expression 的预期
- 结构解释：残基环境、距离、通道/口袋/loop 归属
- 实验反馈解释：若预测与实验冲突，先承认偏差，再做机制重构
- 下一轮策略：保留收益、补偿损失、避开冲突位点、设计单点/双点验证梯度

这是 Venus 当前相对强的区域，必须优先补。

### M6 实验设计与 DBTL 项目记忆

核心对象：

- Project：酶、客户目标、应用条件、成功阈值
- WT Baseline：底物、pH、温度、buffer、表达宿主、纯化状态、活性/稳定性/表达基线
- Variant：突变组合、构建批次、表达、纯化、assay 结果
- Prediction：工具版本、参数、输入 artifact、候选分数
- Feedback：预测偏差、机制解释、下一轮约束

验收：没有 WT 同批 baseline，不得声明“提升”；只能写“相对历史数据或模型假设”。

### M7 专家报告与可视化

报告主线：

1. 酶身份与反应确认
2. 输入结构/序列证据
3. 编号映射
4. 催化机制与禁改位点
5. 位点结构-功能特征表
6. 多目标评分与冲突
7. 候选突变/指定突变复核
8. 实验批次设计
9. 反馈学习与下一轮 DBTL

可视化：

- 3D 结构高亮：候选位点、禁改位点、通道、口袋、低置信区
- 候选表：高置信/探索/阻断分层
- 反馈面板：预测 vs 实验，偏差归因和下一轮补偿策略

## 优先级

### P0：2 周内，追平 Venus 报告专业感

- 新增指定突变复核报告路径。
- 候选位点表增加 relSASA、到催化簇距离、保护区风险、目标分数、实验动作。
- 报告中加入“预测 vs 证据等级 vs 实验验证需求”列。
- 续问“这个突变怎么样/和 Venus 比哪里差”必须进入复核模式。

### P1：4-6 周，建立酶专属证据层

- Rhea/ChEBI 反应层适配器。
- BRENDA/SABIO-RK baseline registry。
- M-CSA catalytic mechanism mapper。
- 位点编号跨 UniProt/PDB/用户序列统一映射。

### P2：6-10 周，建立位点结构-功能评分

- relSASA、距离矩阵、pocket/channel、conservation、ddG、packing、MD RMSF 统一入 `residue_feature_table`。
- 多目标评分器拆出 activity/stability/specificity/pH/expression/risk。
- 报告不再按工具结果拼接，而按 residue_feature_table 生成候选解释。

### P3：10-16 周，形成项目 DBTL 闭环

- 实验数据上传、WT baseline、variant assay 数据模型。
- 预测偏差追踪和项目级校准。
- 智能库设计：单点、组合、探索/深耕配额、板布局。
- 形成客户项目复盘：每轮设计、实验结果、下一轮假设。

## 上线验收门槛

- 任一候选突变必须能回答：为什么选它、离催化中心多远、是否在通道/口袋/loop、是否保守、对每个目标有什么正负影响、需要什么实验验证。
- 任一“提升”结论必须绑定 WT baseline、assay 条件和统计口径。
- 任一结构解释必须绑定结构来源、覆盖率、编号映射和低置信区处理。
- 任一外部数据库结论必须标注来源、版本或抓取时间；不可把 fallback/启发式写成 live curated 证据。
- 指定突变复核必须能承认预测偏差，并把用户实验结果转化为下一轮设计约束。

## 参考来源

- Cradle platform: https://www.cradle.bio/platform
- Arzeda technology: https://www.arzeda.com/technology
- Schrodinger platform: https://www.schrodinger.com/platform/
- AlphaFold / AlphaFold Server: https://deepmind.google/science/alphafold/
- PROSS2 paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC7611707/
- FireProt 2.0 paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC10685400/
- M-CSA documentation/about: https://www.ebi.ac.uk/thornton-srv/m-csa/documentation/
- BRENDA: https://www.brenda-enzymes.org/
- SABIO-RK: https://sabiork.h-its.org/
- Rhea: https://www.rhea-db.org/
- Caver Web 2.0: https://academic.oup.com/nar/article/53/W1/W132/8126903
