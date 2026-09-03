# 蛋白研发平台能力审计：外部示例提示词

## 目的

用户提供的 21 条示例提示词覆盖靶点发现、抗体工程、酶工程、生成式设计、结构预测和多类对接。它们不能只被理解为“更多工具入口”，而是六类不同的数据合同、运行时和结果验证链路。

本审计只回答两件事：

1. 每条提示词实际需要哪些输入、数据和计算工件。
2. 当前平台的真实状态是可运行、条件可运行、代理/MVP，还是缺失。

状态定义：

| 状态 | 含义 |
|---|---|
| `真实可运行（受环境门控）` | 已有真实命令/服务调用、输出工件和失败合同；缺依赖时必须 blocked。 |
| `部分可用` | 有数据检索或流程骨架，但不足以交付用户所要求的科学结论。 |
| `代理/MVP` | 只做启发式、模拟或占位输出，不能称作目标模型的真实推理。 |
| `缺失` | 没有对应的数据对象、工具链或评测。 |

## 六类产品线

### A. 人类靶点、膜蛋白与通路情报

对应提示：

- MUC16 纳米抗体健康膜蛋白脱靶筛选
- CXCL12 高亲和力受体查询
- TGF-beta 通路膜/胞外人类蛋白筛选

真正的交付物不应是“相似蛋白列表”，而应是带证据的候选表：

| 字段 | 最低证据 |
|---|---|
| 蛋白身份、亚细胞定位、跨膜拓扑 | UniProt reviewed feature / Human Protein Atlas |
| 健康组织表达 | HPA/GTEx，明确组织、细胞类型、数据版本 |
| 配体-受体关系 | UniProt/Reactome/OmniPath/CellPhoneDB 等可追溯关系源 |
| 通路与疾病角色 | Reactome/GO/文献，分别标注肿瘤、免疫抑制、纤维化的证据类型 |
| 脱靶相似性 | 序列、结构域、胞外可及表位、结构相似性，不能只用全长序列相似度 |
| 风险排序 | 正常组织表达、必需性、细胞表面可及性、同源表位风险的多目标排序 |

当前平台：

- `sequence_search`、UniProt 数据接入、结构搜索和注释基础设施可作为起点。
- 缺少人类膜蛋白专用对象、HPA/GTEx 表达层、受体-配体图谱、Reactome/OmniPath 通路边、健康组织安全性排序和“表位级”脱靶评估。
- 因此三类提示目前为 `部分可用`，不能交付药物发现级别的靶点/脱靶结论。

### B. 抗体与纳米抗体工程

对应提示：

- 小鼠 kappa 保守型抗体人源化
- MUC16 纳米抗体脱靶评估

最低工作流：

```text
VH/VL 序列
  -> IMGT 编号与链型校验
  -> V/J germline 匹配
  -> CDR/FR 边界与 canonical class
  -> 保守型人源化候选
  -> 结构/表位/关键 FR 风险检查
  -> developability: aggregation, liabilities, PTM, immunogenicity
  -> 表达、亲和力、热稳定性、非特异性结合验证
```

需要接入/实现：

- ANARCI 或等价 IMGT 编号器，且要能处理不完整序列并拒绝错误链型。
- 人类 germline 数据、SAbDab/OAS 等抗体背景库。
- CDR 保留策略、Vernier 区回突规则、框架突变可解释性。
- 抗原结构/表位条件下的亲和力保留评估；没有复合物或表位信息时只能给低置信序列人源化建议。

当前平台：`缺失`。Rosetta 本地文件不等于可交付的抗体人源化产品线。

### C. 酶工程与生物资源发现

对应提示：

- 人肠激酶 P98073 包涵体表达的增溶设计
- 溶菌酶 P00698 催化效率提升
- 热稳定性突变设计
- 宏基因组 PET 水解酶挖掘
- 极端嗜热菌耐高温淀粉酶筛选
- 漆酶未表征同源蛋白氧化活性筛选
- Kcat、溶解度、最适 pH 预测

当前平台已有的正向基础：

- 身份画像、催化/保护位点、编号门控、实验反馈、组合风险检查。
- 真实 Rosetta 和 GROMACS 接口具有 runtime/artifact 边界；没有运行时应 blocked。
- BRENDA/SABIO 类动力学数据接入方向、序列/结构搜索和注释接入。

必须保持的边界：

- `kcat_predict` 当前是类别统计和序列启发式，不能标记为真实模型推理或作为动力学定量结论。
- 没有独立的最适 pH 模型；pH 目标下的候选排序、标准蛋白 MD、以及催化残基 pKa 不是同一件事。
- `soluble_mpnn_design` 当前是代理规则，不能替代真实 SolubleMPNN/MembraneMPNN 推理。
- 活性提升必须区分纯酶比活/`kcat`/`kcat/Km`、稳定性维持和表达量提高；本平台已新增湿实验归因和第二轮规划器约束。

三个专项缺口：

| 任务 | 缺失的关键合同 |
|---|---|
| PET 宏基因组挖掘 | reads/contigs -> ORF -> 去冗余 -> HMM/家族 -> signal peptide -> 催化 motif -> 底物证据 -> 结构/活性排序 -> 序列簇多样性。 |
| 极端嗜热淀粉酶来源筛选 | taxonomy/极端环境来源、温度和 pH 的实验条件、结构域/家族、公开测定和文献证据，不能把预测温度当作最适温度。 |
| 漆酶高活性同源筛选 | 多序列家族构建、铜结合位点及信号肽/分泌背景、底物和氧化还原条件、同源已测活性标签、校准的相对排序模型。 |

### D. 生成式结构与序列设计

对应提示：

- RFdiffusion 设计 IL-17A 特异结合的新骨架
- AlphaFold 结构预测并评估置信度
- ProteinMPNN 重设计 1JMB 以提高热稳定性

真实生产流程：

```text
目标结构/表位/约束
  -> 真实 RFdiffusion 推理产生 backbone PDB 工件
  -> 真实 ProteinMPNN 产生 sequence set
  -> AlphaFold/ColabFold/Boltz 等复折叠验证
  -> 复合物界面与脱靶/自聚集/可表达性筛选
  -> 实验表达、SEC、DSF、结合和功能测定
```

当前状态：

| 工具 | 当前审计 |
|---|---|
| `alphafold2_folding` | `代理/MVP`：代码使用随机化的 pLDDT/pTM 和二级结构启发式；没有 AF2 MSA、权重或 PDB 工件。 |
| `rfdiffusion_design` | `代理/MVP`：几何采样骨架，文档已说明生产版本才连接真实 RFdiffusion。 |
| `proteinmpnn_design` | `代理/MVP`：二级结构/理化规则替代真正 ProteinMPNN 推理。 |
| `esmfold_folding` / `alphafold_folding` | 必须逐个核对真实 runtime、模型权重、MSA/模板策略和输出工件；不能因工具名称而假定是官方模型。 |

这三类入口需要 P0 整改：结果必须显示 `runtime_type`、`is_real_inference`、模型版本、权重/服务来源、输入哈希、输出 PDB/mmCIF、日志和失败原因。没有这些时应显示“流程预检/代理估算”，不应显示官方模型的置信度数值。

### E. 小分子、肽和蛋白互作结构建模

对应提示：

- AutoDock Vina：布洛芬到 COX-2 5IKR
- DiffDock：EGFR 与吉非替尼
- ADCP：多肽与 PD-L1
- 蛋白-蛋白：PD-1/PD-L1 5IUS
- PLIP：1ATP 中 ATP 与激酶相互作用

五种任务的科学合同不同：

| 类型 | 必需输入 | 最低输出 | 不能替代的验证 |
|---|---|---|---|
| Vina | 受体/配体的真实 3D、质子化、电荷、口袋盒子 | pose、Vina score、参数和 log | 重打分、共晶/活性、构象合理性 |
| DiffDock | 真正的蛋白坐标和配体 3D | pose ensemble、置信度、模型版本 | 不能把 proxy score 当 DiffDock 结果 |
| ADCP | 肽序列/初始构象、受体、柔性定义 | docking cluster、能量、构象 | 肽构象采样和实验亲和力 |
| PPI docking | 两个链、状态/结构、界面约束 | complex models、interface metrics | 生物学界面、实验数据 |
| PLIP | 已有复合物 PDB | 氢键、盐桥、疏水、pi 相互作用报告 | PLIP 是相互作用描述，不预测亲和力 |

当前状态：

- `ligand_preprocess` + Vina 是 `真实可运行（受环境门控）`：需要 3D 配体、PDBQT、口袋中心/尺寸和 Vina runtime；输出可带 docked pose 和日志。
- `diffdock_docking` 是 `代理/MVP`，源码已明确写明 simplified docking score。
- ADCP、PPI docking、PLIP 均为 `缺失`。
- 标准蛋白 MD 仅能给构象/稳定性相关轨迹指标；没有恒 pH、pKa 或 QM/MM 配置时，不能输出催化 pKa、反应能垒或“活性构象保留率”。

### F. 膜蛋白与复合物专用建模

膜蛋白搜索、MUC16 细胞表面脱靶、CXCL12 受体和 TGF-beta 受体通路都需要跨越“序列分析”和“人类转化医学”两层。平台应新增：

- 跨膜拓扑和胞外区可及性；
- 组织/细胞型表达、疾病和安全性数据；
- 蛋白复合物、糖基化和表位可及性；
- 结构相似性以胞外可及域/表位为中心，而不是全长相似度；
- 面向人类靶点的证据冲突处理和证据版本。

## 目标能力矩阵

| 示例能力 | 当前状态 | 近期正确产品形态 |
|---|---|---|
| 膜蛋白/脱靶筛选 | 部分可用 | Human Target Intelligence workflow |
| 配体-受体/通路 | 部分可用 | Knowledge Graph + evidence table |
| 抗体人源化 | 缺失 | Antibody engineering workflow |
| 酶稳定性/表达改造 | 部分可用 | Evidence-gated enzyme workflow |
| 宏基因组酶挖掘 | 缺失 | Metagenome enzyme discovery workflow |
| 来源/极端环境酶筛选 | 部分可用 | Metadata-first bioprospecting workflow |
| 同源酶活性排序 | 代理/MVP | Calibrated family-specific ranker |
| RFdiffusion/ProteinMPNN/AF2 | 代理/MVP | GPU runtime + artifacts + model cards |
| Vina 小分子对接 | 真实可运行（受环境门控） | Ligand workflow with artifacts |
| DiffDock/ADCP/PPI/PLIP | 代理或缺失 | Separate validated structural workflows |

## 建议的建设顺序

### P0：先清除“名称正确、结果不真实”的风险

1. 所有预测工具统一输出 `capability_status`：`real_runtime`、`external_service`、`proxy`、`blocked`。
2. 禁止代理工具使用 `is_real_inference=true` 或官方模型名称包装随机/启发式结果。
3. 结果页强制显示模型版本、数据版本、输入哈希、日志和工件链接；没有工件不展示结果为“已完成计算”。
4. 为每种对接类型建立独立输入门控，禁止“无 ligand 的 docking”或“2D SDF 直接 MD”。

### P1：人类靶点情报和抗体工程

1. Human protein profile：UniProt、HPA/GTEx、Reactome、疾病/药物安全性证据。
2. 受体-配体和通路关系图，支持证据来源和版本。
3. Antibody input normalizer：IMGT 编号、VH/VL 链校验、germline 匹配、CDR/FR 边界。
4. 纳米抗体脱靶：胞外表位可及性 + 健康表达 + 结构域/表位相似性。

### P2：酶发现与工程深化

1. 宏基因组候选发现链：ORF、HMM、家族、底物/机制、去冗余和多样性抽样。
2. 以实验条件为主键的酶性质数据表：底物、缓冲液、pH、温度、测定方法和来源。
3. 按家族和目标校准的相对排序器；没有足够训练/验证数据时只输出候选，不输出定量性质。
4. 继续用湿实验反馈、编号门控和组合风险检查约束后续轮次。

### P3：真实结构计算运行时

1. GPU 节点封装真实 AF/ColabFold、RFdiffusion、ProteinMPNN、DiffDock。
2. 分开部署 Vina、ADCP、PPI docking 和 PLIP；不要把它们塞进一个泛化 `docking` 工具。
3. 先建黑盒 benchmark 和工件验收，再开放在聊天中直接给出结构结论。

## 外部技术依据

- RFdiffusion：RosettaCommons 官方实现与论文。
- ProteinMPNN：Dauparas 等公开官方实现与论文。
- DiffDock：Corso 等公开官方实现与论文。
- AutoDock Vina：官方文档与可复现实行命令行工具。
- UniProt REST、Reactome Content Service、Human Protein Atlas：人类靶点资料应使用可版本化、可溯源的原始数据库服务。
- PLIP：PharmAI 的 Protein-Ligand Interaction Profiler；它分析既有复合物，而不是完成 docking 或亲和力预测。

这些来源支持“该能力需要什么数据与工件”的技术判断，不构成任一具体药物靶点、突变或活性提升的实验结论。
