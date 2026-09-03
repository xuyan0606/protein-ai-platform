# 科学报告格式与 Claim 级证据门控设计

## 背景

外部平台的 MUC16 纳米抗体脱靶报告展示了一个值得借鉴的产品形态：先生成研究计划、再确认大纲、分章节撰写、最后输出完整报告和置信度附录。这个形式适合复杂生物研发任务，因为用户能看到“从问题到报告”的形成过程。

但该报告也暴露了关键缺陷：正文里大量平台定义、版本号、权重、阈值、风险分层被写成确定事实，而验证附录中对应 claim 却是 `MISSING`、`WEAK` 或 `CONFLICTING`。这说明报告生成和证据门控没有闭环，正文仍然可能把“作者设计/合理推断”包装成“平台已使用/文献已证明”。

本平台应学习其报告组织方式，但必须改造为 fail-closed 的证据报告。

## 可借鉴点

### 1. 先给研究计划，再进入报告

好的形式：

```text
用户问题
  -> 研究计划
  -> 用户确认
  -> 数据源检索 / 计算任务
  -> 章节大纲
  -> 用户确认
  -> 分章节撰写
  -> claim 验证
  -> 最终报告
```

这适合复杂任务，尤其是膜蛋白脱靶、抗体人源化、酶改造、生成式设计等跨数据源问题。

### 2. 章节化输出

MUC16 报告的 8 章结构有产品价值：

1. 执行摘要；
2. 定义与入选规则；
3. 数据源与版本；
4. 可及性/结构准备；
5. 算法与特征；
6. 排序公式；
7. 实验验证与平台对标；
8. 局限性与实施建议。

对本平台而言，不同任务可以套同一骨架，但章节名要按任务定制。

### 3. 置信度附录

报告末尾逐条列出 claim 的验证状态，是很好的机制：

- `SUPPORTED`
- `WEAK`
- `MISSING`
- `CONFLICTING`

这比只给参考文献列表更有用，因为它能指出正文中哪些句子只是推断。

### 4. 目录 + 表格 + 公式 + 决策树

复杂生物研发报告应尽量结构化：

- 输入定义表；
- 数据源版本表；
- 算法参数表；
- 风险公式；
- Go/No-Go 表；
- 下一轮实验优先级；
- 局限性与不可下结论范围。

这能明显提升用户可读性和可审计性。

## 必须避免的问题

### 1. 不能让 MISSING claim 留在正文里当事实

外部报告中大量句子被附录标为 `MISSING`，例如：

- “平台使用 9 个核心数据库”；
- “默认权重为 0.30/0.25/0.20/0.15/0.10”；
- “高风险阈值为 0.60”；
- “年度更新差异 <5% 才通过”；
- “IND 申报快照服务永久归档”。

这些如果没有平台代码、配置、数据库快照或文档支持，只能写成：

```text
建议平台采用...
本报告建议的默认初始权重为...
该阈值为待校准工程假设...
```

不能写成：

```text
平台采用...
平台锁定...
平台最终公式为...
```

### 2. 文献事实和平台实现必须分开

报告里常见的混淆：

```text
文献证明工具 A 可用于 X
  -> 平台已使用 A
  -> 平台结果因此可信
```

正确写法：

```text
文献支持 A 是可选算法。
本平台当前状态：未接入 / proxy / real runtime / external service。
若未来接入，最小工件应包括...
```

### 3. 版本号不能凭搜索结果或 LLM 记忆写死

数据源版本必须来自：

- 本平台实际 `data_manifest`；
- 下载脚本日志；
- 数据库 dump metadata；
- 官方 release 页面；
- 任务审计里的 runtime artifact。

否则只能写“建议锁定版本”，不能写“平台锁定版本”。

### 4. 风险公式不能装成已验证模型

没有实验标签校准的权重公式，只能定位为：

- rule-based prioritization；
- expert-weighted score；
- uncalibrated risk ranking；
- hypothesis generator。

不能解释为：

- 脱靶概率；
- 临床毒性概率；
- 监管级安全结论。

## 本平台推荐报告协议

### 报告顶部固定三行

```text
Capability status: real_runtime / external_service / proxy / evidence_synthesis / blocked
Evidence readiness: ready / partial / blocked
Conclusion level: verified fact / evidence-backed inference / design hypothesis / missing evidence
```

### 正文章节

#### 1. Executive Summary

只允许出现三类结论：

- 已由证据支持的结论；
- 明确标注的推断；
- 明确阻断项。

如果核心 claim 有 `MISSING/CONFLICTING`，摘要必须写“当前不能得出结论”。

#### 2. Input Normalization

列出：

- 用户输入；
- 序列/结构/靶点/抗体链/配体格式；
- 编号体系；
- 缺失输入；
- 不做哪些假设。

#### 3. Foundation Profile

不同任务的基础画像不同：

- 酶工程：家族、EC、结构域、催化/结合/金属/二硫键、编号映射；
- 膜蛋白脱靶：人类蛋白身份、定位、拓扑、胞外区、表达、结构；
- 抗体人源化：VH/VL、链型、编号、CDR/FR、germline；
- 结构设计：靶点结构、链、表位、约束、可用结构状态。

#### 4. Evidence Ledger

每条关键结论都要有：

- claim id；
- source；
- source version；
- artifact id/path；
- evidence level；
- coordinate system；
- status。

#### 5. Method And Runtime

区分：

- 数据检索；
- 规则估算；
- 模型推理；
- 外部服务；
- 真实命令行运行。

真实运行必须有：

- model/tool version；
- command/config；
- input hash；
- output files；
- stdout/stderr；
- runtime environment。

#### 6. Scoring / Ranking

必须写：

- 变量定义；
- 归一化方式；
- 权重来源；
- 是否校准；
- 是否做敏感性分析；
- 不可解释成什么。

#### 7. Results

结果表不能只给分数，应包含：

- why this candidate；
- evidence strength；
- risk driver；
- missing evidence；
- next validation。

#### 8. Experimental Plan

必须按 Go / Watch / No-Go 或 P0/P1/P2 输出：

- 最小验证实验；
- 对照；
- 读数；
- 成功判据；
- 失败后如何迭代。

#### 9. Limitations

不写泛泛局限，要写会改变结论的局限：

- 缺编号映射；
- 缺蛋白表达；
- 结构低置信；
- 表位未知；
- 公式未校准；
- 工具为 proxy。

#### 10. Claim Audit Appendix

最终附录必须列出所有关键 claim：

| claim_id | claim | status | source | action |
|---|---|---|---|---|
| C001 | 平台使用 HPA v25.1 | MISSING | none | 改成建议项或补 manifest |
| C002 | TM-score >0.5 表示相同 fold | SUPPORTED | TM-align paper | 可保留 |
| C003 | 风险阈值 0.60 | DESIGN_HYPOTHESIS | internal rule | 需实验校准 |

## Claim 状态如何影响正文

| Claim 状态 | 正文处理 |
|---|---|
| `SUPPORTED` | 可作为事实写入 |
| `WEAK` | 可写入，但必须带“不确定/弱证据/需验证” |
| `MISSING` | 不能写成事实，只能写成建议或待补证据 |
| `CONFLICTING` | 必须从摘要和结论移除，列为冲突项 |
| `DESIGN_HYPOTHESIS` | 可保留在方法设计中，但必须标为未校准 |
| `RUNTIME_UNVERIFIED` | 不能称“真实运行”，只能称“计划/接口/proxy” |

## 针对 MUC16 类报告的本平台输出应这样改

### 错误风格

```text
平台使用 UniProt 2025_02、HPA v25.1、GTEx v8、AlphaFold DB v4。
最终风险公式权重为 0.30/0.25/0.20/0.15/0.10。
高风险阈值为 0.60。
```

### 正确风格

```text
本次若要形成可复现的 MUC16 纳米抗体脱靶报告，建议最低锁定以下数据层：
UniProt reviewed human proteome、HPA normal tissue/subcellular localization、GTEx normal tissue RNA、AlphaFold/PDB structures。

当前平台尚未读取项目级数据 manifest，因此不能声明具体版本已锁定。

风险排序可先采用未校准 expert-weighted score：
R = w_expression * E + w_accessibility * A + w_epitope * P + w_structure * S + w_tissue * T

默认权重只能作为初始设计假设，必须在实验回测后校准；报告中不得解释为脱靶概率。
```

## 对酶工程报告的迁移

酶工程也应该采用同样格式：

```text
Foundation Profile
  -> 家族/EC/结构域/催化位点/编号映射/保护位点
Objective Module
  -> 热稳定性 or 比活 or 特异性 or pH
Candidate Table
  -> 只有 Foundation ready 才出现
Claim Audit
  -> 每个突变机制、位点距离、ddG、pKa、文献证据逐条核验
```

示例：

```text
“D105N 会降低最适 pH”如果没有实验证据或 pKa 计算工件，应标为 DESIGN_HYPOTHESIS。
“D105N 比活下降 40-50%、最适 pH 未降低”来自用户湿实验，应标为 USER_EXPERIMENT_L1。
第二轮组合推荐必须优先尊重 USER_EXPERIMENT_L1，而不是继续重复模型初始排序。
```

## 产品落地优先级

### P0

- 报告生成器新增 claim ledger；
- `MISSING/CONFLICTING` claim 不允许进入摘要和最终结论；
- proxy 工具结果在报告顶部显示；
- 数据源版本来自 manifest，不允许 LLM 写死。

### P1

- 每个工具返回 `claim_evidence` 数组；
- 前端支持展开 claim audit；
- 用户可以把 claim 标记为“实验已验证/用户已否定/待验证”。

### P2

- 自动生成可复现实验/计算包；
- 支持报告版本 diff；
- 支持监管/客户审计导出。

