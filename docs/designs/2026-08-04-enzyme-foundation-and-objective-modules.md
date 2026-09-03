# 酶工程基础画像与目标模块设计

## 目标

本平台的酶改造链路必须先回答“这个酶到底是什么、关键功能位点在哪里、这些编号是否对应用户输入序列”，再回答“怎么改”。外部平台可作为反面/对标样本，但不能照搬其固定 skill 话术。

本设计把酶工程拆成两层：

```text
P0 Foundation Profile
  -> 身份、家族、EC、结构域、催化/结合/金属/二硫键/信号肽、编号映射、证据账本
P1 Objective Modules
  -> 热稳定性、比活/催化效率、底物特异性、pH 活性谱等目标专项决策树
```

P0 不通过时，P1 只能输出补证据计划，不能输出实验突变主表。

## 外部资料复核结论

### 1. 家族、结构域、位点不是同一种证据

InterPro 官方把 entry type 分为 family、domain、site、repeat、homologous superfamily。Family 可支持具体家族判断；domain 支持结构域边界；site 才更接近功能位点；homologous superfamily 只说明远缘结构/共同起源，不能直接等同具体酶家族或 EC。

平台规则：

- `family`：可进入身份候选。
- `domain`：进入结构域与模块边界，不单独定 EC。
- `site`：进入功能位点候选，但仍需编号映射。
- `homologous_superfamily`：只作为远缘背景，不允许确认具体 family。
- 短 motif：最多是 L5 线索，不能直接给 EC 或突变主表。

### 2. UniProt / M-CSA 的位点是记录坐标，不是用户序列坐标

UniProt feature table 中 Active site、Binding site、Site 等都是 position-specific annotations。M-CSA/CSA 记录催化残基和活性位点，CSA 历史上以 PDB residue numbering 为核心，并区分 literature / homologue evidence。

平台规则：

- 外部位点必须带 `source_coordinate_system`。
- 只有在 `input_sequence == curated_sequence` 或通过全局 alignment/SIFTS 得到一对一映射时，才能转成用户序列编号。
- 无法映射的 curated 位点进入 `protected_pending_numbering_confirmation`，并阻断突变推荐。
- 报告里必须同时显示“来源编号”和“用户输入编号”，不能只显示一个数字。

### 3. BLAST、HMMER、InterProScan 是互补证据层

UniProt BLAST 可优先搜 Swiss-Prot/Reviewed，因为 reviewed 记录更适合功能/家族注释迁移；弱同源、远缘家族、多结构域蛋白时，应追加 HMMER/InterProScan 这类 profile/signature 层证据。InterProScan 官方定位就是对新蛋白序列运行 member database signatures 的整合扫描。

平台规则：

- 第一轮默认：Swiss-Prot/Reviewed BLAST 或本地精确序列命中。
- BLAST 弱、结果冲突、或多结构域：追加 HMMER / InterProScan。
- 糖苷水解酶/碳水酶：额外接 CAZy / dbCAN 家族层。
- 有结构：Foldseek/SIFTS 是结构映射和远缘结构证据，不替代 EC/function 结论。

### 4. 性质数据必须保留实验条件

BRENDA 明确有 pH optimum、pH range、KM、kcat/KM 等字段，并要求把底物、突变体、测定条件写入 commentary。SABIO-RK 也强调 kinetics 是反应、酶、物种、参数和实验条件共同定义的数据。

平台规则：

- kcat、Km、kcat/Km、最适 pH、最适温度不能脱离底物、温度、pH、buffer、纯化/总活性、表达宿主。
- “总活性提升”不等于“比活/催化效率提升”。
- “pH4.5/pH6.0 活性比提高”不等于“最适 pH 已经移动到 4.5”。

## P0 Foundation Profile 合同

### 输入

- 必填其一：UniProt ID、FASTA、PDB/mmCIF。
- 可选：物种、EC、底物、已知催化位点、实验编号体系、表达体系、已有突变数据。

### 输出字段

| 字段 | 说明 | 门控 |
|---|---|---|
| `identity_status` | `identified / candidate / unresolved / conflict` | 只有 `identified` 可进入突变推荐 |
| `family_candidates` | family 级证据，含 accession、entry type、source、confidence | 不接受 superfamily 单独确认 |
| `ec_candidates` | EC、反应/功能、来源 | EC 必须说明是 curated、family-inferred 还是 predicted |
| `domains` | 结构域区段、family/domain/superfamily 类型 | 作为目标模块边界 |
| `key_residues` | catalytic、binding、metal、disulfide、PTM、flap/loop 等 | 可映射才进入保护坐标 |
| `protected_positions` | 用户序列编号下不可突变位点 | 缺映射则为空并阻断 |
| `pending_numbering` | 来源位点未映射列表 | 非空时阻断候选主表 |
| `cofactors` | 金属/小分子/辅酶 | 影响结构准备和不可触碰区 |
| `signal_peptide` | 分泌/前体/成熟蛋白边界 | 影响编号与表达策略 |
| `structure_status` | experimental / predicted / unavailable，含覆盖率、缺失残基 | 影响空间距离可信度 |
| `evidence_ledger` | 每个结论的来源、版本、artifact、坐标体系 | 报告必须展示 |

### 证据等级

| 等级 | 来源 | 可做什么 |
|---|---|---|
| L1 | curated record / reviewed UniProt / 文献机制 / M-CSA literature / 已验证本地库 | 可确认身份或功能位点，但仍需编号映射 |
| L2 | InterPro/Pfam/PROSITE family-site、M-CSA homologue、CAZy family | 可确认家族候选和保护位点候选 |
| L3 | BLAST/HMMER/Foldseek 高置信同源 | 可做候选身份，需要冲突检查 |
| L4 | 结构口袋/几何/对接/MD/模型预测 | 只能支持机制假设 |
| L5 | 短 motif、氨基酸理化启发式、LLM 推理 | 只能做线索，不能放行主表 |

## P1 目标模块

### A. 热稳定性

前提：

- Foundation Profile 通过；
- 活性/结合/金属/二硫键等保护区明确；
- 有结构或足够可信的同源结构更好。

决策树：

1. 先排除催化位点、底物通道、金属/辅因子配位、二硫键和高度保守核心。
2. 按机制生成候选池：
   - 表面盐桥/氢键网络；
   - flexible loop 的 Pro/Gly rigidification；
   - 疏水核心 cavity filling；
   - 新二硫键，必须检查 Cα/Cβ 距离、二面角和功能区距离；
   - consensus / thermophile homolog back-to-consensus。
3. 评分不只看 ddG：
   - Rosetta/FoldX/ddG；
   - 结构局部冲突；
   - 保守性；
   - 离活性中心距离；
   - 活性风险。
4. 实验输出：
   - 第一批以 8-20 个单点为主；
   - 组合只在单点验证后进入。

Go/No-Go：

- `Tm/Tagg/半衰期提升` 且 `比活保留` 才算热稳定性工程成功；
- 总活提高但表达量也提高时，归为表达/折叠收益，不归为热稳定性本体。

### B. 比活 / 催化效率

前提：

- 催化残基与底物结合口袋已定位；
- 用户目标指标明确：比活、kcat、Km、kcat/Km、还是总活。

决策树：

1. 保护催化一阶残基，不直接建议突变。
2. 候选区域按优先级：
   - 第一/第二壳层，但避开不可触碰残基；
   - 底物定位残基；
   - 过渡态稳定网络；
   - flap/loop 动力学；
   - 远端变构候选仅在有进化/结构连通/文献证据时进入探索池。
3. 需要分清机制：
   - `kcat` 提升：构象/化学步骤/过渡态；
   - `Km` 降低：结合增强，可能不提升周转；
   - `kcat/Km` 提升：更接近催化效率；
   - 总活提升：可能是表达/稳定性。
4. 输出不应只给 Top mutation：
   - 每个候选必须有“目标瓶颈假设”；
   - 必须标注是否需要底物对接、MD 或动力学实验验证。

Go/No-Go：

- 没有纯酶归一化数据时，不得声明“真实催化提升”。
- 只测一个底物时，不得声明“底物谱优化”。

### C. 底物特异性

前提：

- 至少有目标底物和非目标底物；
- 最好有底物/类似物复合物结构、对接位姿或已知 S1/S2/S1' 口袋定义。

决策树：

1. 从 Foundation Profile 读取结合口袋、结构域、CBM/辅助结构域。
2. 对比目标/非目标底物：
   - 尺寸、极性、电荷、糖环/芳香/脂肪链；
   - 入口通道与子位点。
3. 候选机制：
   - 口袋变大/变小；
   - 极性/疏水匹配；
   - 引入排斥非目标底物的位阻；
   - 调整 CBM 或远端入口，而不是直接破坏催化中心。
4. 必须做负筛：
   - 目标底物活性提高但非目标也提高，不算特异性提高；
   - 只用 docking score 不足以判定特异性。

Go/No-Go：

- 输出指标用选择性比值：`kcat/Km_target / kcat/Km_off-target`。
- 对多糖/复杂底物，要明确底物批次、聚合度、取代度。

### D. pH 活性谱 / 最适 pH

前提：

- 已知 pH-activity curve，而不是单点 pH 活性；
- 明确目标是移动 optimum、拓宽窗口、酸稳定性，还是 pH4.5/pH6.0 比值提高。

决策树：

1. 从机制上拆分：
   - 催化残基表观 pKa；
   - 底物结合 pH 依赖；
   - 蛋白整体酸/碱稳定性；
   - 表达/成熟/加工差异。
2. 候选区域：
   - 催化酸/碱附近可滴定残基；
   - 第二壳层静电网络；
   - 口袋水网络；
   - 表面电荷网络只作为稳定性/酸耐受候选，不直接当 optimum 位移候选。
3. 计算支持：
   - PROPKA/Poisson-Boltzmann/pKa 工具只能输出 pKa 假设；
   - 标准 MD 不能自动输出 pKa 或最适 pH；
   - 恒 pH MD/QM/MM 需要单独运行时和更强证据。
4. 实验必须：
   - 测完整 pH 曲线；
   - 同时测酸性孵育后残余活性；
   - 对比 pH optimum 和 pH stability。

Go/No-Go：

- 单点 pH 比值提高只标为 `pH-window ratio improved`，不能标为 `optimum shifted`。
- pH 改造候选应优先做单点梯度，再做少量二点组合。

## 组合突变与第二轮反馈

平台不应宣称“小样本训练专属上位性模型”。更准确的机制是：

```text
实验反馈
  -> 表型归因：催化 / 稳定性 / 表达 / 未解
  -> 单点证据池更新
  -> 结构距离与机制冲突检查
  -> 组合候选只作为下一轮实验设计
  -> 二点实测后再评估三点
```

最低数据量建议：

- <10 个单点：只能做规则约束重排。
- 10-30 个单点：可做轻量校准和探索/深耕配额调整。
- ≥30 个单点 + ≥5 个二点：才可以开始拟合该蛋白的组合倾向，但仍应显示不确定性。
- ≥50 个单点 + ≥20 个组合：才可把“三点以上组合预测”作为主路线候选。

如果出现“总活性升高但比活没升高”：

- 标记为表达/分泌/折叠/稳定性介导；
- 不进入 catalytic efficiency 有效单点池；
- 可作为骨架/表达优化位点与催化位点组合，但必须双目标标注。

## 当前代码层需要继续收紧

### P0-1：`protein_benchmark` 降级

现状：该工具内置 GH13/GH11/GH7/GH5/GH1 等知识库，容易在用户给 enzyme_type 或短线索时过早输出家族解释。

改法：

- 只消费 `enzyme_identity_profile.identity_status=identified` 的家族；
- 内置知识库只能在 family 已确认后补解释；
- 若 identity unresolved/conflict，则输出“无法 benchmark”，不输出工程推荐。

### P0-2：外部真实运行工件

需要实现：

- BLAST against Swiss-Prot/Reviewed：输入 FASTA、数据库、参数、job id、stdout/JSON/TSV、数据库日期。
- HMMER/InterProScan：signature 版本、member database、raw output、domain coordinates。
- SIFTS/全局 mapping：对每个 curated 位点生成 source->query mapping 表。
- Foldseek：结构命中、TM-score/alignment、结构覆盖率；不自动确认 EC。

### P0-3：报告主表顺序

报告必须固定为：

1. Foundation Profile；
2. Numbering Gate；
3. Missing Evidence / Blockers；
4. Objective Module Plan；
5. Candidate Table，仅在门控 ready 时出现；
6. Experimental Design；
7. Evidence Ledger。

## 下一批验收测试

- superfamily-only 不得 identified。
- 单一 `GXSXG/GYSIG` 不得给 lipase/esterase EC。
- 有 UniProt/M-CSA 位点但 mapping_required 时，不得进入 protected_positions。
- `mutation_priority_score` 直接调用、但无当前轮 identity profile 时必须 blocked。
- `protein_benchmark` 在 identity unresolved 时不得输出 known-family 推荐。
- pH 任务里只给 pH4.5/pH6.0 单点比值时，不得声明 optimum shift。
- 总活升高、比活不升高时，第二轮规划归为 expression/stability mediated。

## 参考来源

- InterPro entry types and relationships: https://interpro-documentation.readthedocs.io/en/latest/entries_info.html
- InterProScan overview: https://interpro-documentation.readthedocs.io/en/latest/interproscan.html
- UniProt BLAST help: https://www.uniprot.org/help/blast-submission
- UniProt sequence annotation/features: https://www.uniprot.org/help/sequence_annotation
- M-CSA about/documentation: https://www.ebi.ac.uk/thornton-srv/m-csa/about/
- PDBe SIFTS overview and quick access: https://www.ebi.ac.uk/pdbe/docs/sifts/overview.html
- BRENDA data fields: https://www.brenda-enzymes.org/datafields.php
- SABIO-RK: https://sabiork.h-its.org/
- CAZy GH classification: https://www.cazy.org/Glycoside-Hydrolases
- Thermostability review: https://pmc.ncbi.nlm.nih.gov/articles/PMC6481699/
- Rational enzyme engineering review: https://pmc.ncbi.nlm.nih.gov/articles/PMC3962183/
- Activity-enhancing mutation mechanisms: https://pmc.ncbi.nlm.nih.gov/articles/PMC7380680/
- Protein electrostatics and enzyme design: https://pmc.ncbi.nlm.nih.gov/articles/PMC10938506/
- Protein pKa calculations/re-design: https://pmc.ncbi.nlm.nih.gov/articles/PMC5380367/ and https://pmc.ncbi.nlm.nih.gov/articles/PMC2203286/
