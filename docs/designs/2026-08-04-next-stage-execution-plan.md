# 下一阶段执行计划：可信计算与跨域蛋白研发能力

## 目标

在扩展膜蛋白、抗体、靶点情报和生成式设计前，先完成工具真实性、输入证据、可下载工件、成本确认和实验闭环的统一合同。

本计划的首要产物不是更多“模型名称”，而是用户能够复核的结果：

```text
任务定义
  -> 输入/编号/化学状态预检
  -> 成本和运行时说明
  -> 用户确认
  -> 真实模型或明确 proxy/blocked
  -> 参数、日志、工件、证据版本
  -> 结果解释与实验验证边界
```

## 阶段 20：计算真实性与成本门控

**时间：2026-08-04 至 2026-08-11**

### 要做什么

1. 给每个工具加统一 `capability_status`：
   - `real_runtime`
   - `external_service`
   - `proxy`
   - `blocked`
2. 统一输出：
   - `model_name`、`model_version`、git commit；
   - checkpoint/容器 digest/输入 SHA256；
   - CPU/GPU、CUDA、运行时版本；
   - 参数文件、stdout/stderr、产物清单和 SHA256；
   - `scientific_boundary`、失败原因和恢复路径。
3. 清理误导性标记：
   - 代理或启发式工具不得写 `is_real_inference=true`；
   - 代理工具不得伪造 AF/RFdiffusion/ProteinMPNN/DiffDock 的置信度或数值；
   - 不可用时返回 `blocked`，不返回模拟成功结果。
4. 为长任务补“报价 -> 确认 -> 执行”三段式合同：
   - 按结构准备、模型推理、重复数、轨迹/后处理、存储拆分报价；
   - 任务 ID 记录提交报价、最终计费、差异原因；
   - 支持取消状态和计费审计，不承诺尚未实现的退款。

### 验收

- 对 AlphaFold、RFdiffusion、ProteinMPNN、DiffDock、Vina、MD 各有一条 `proxy/blocked/real_runtime` 回归。
- 任何完成状态都至少包含可下载工件或明确的外部服务 job/reference；没有工件不能称“完成计算”。
- 聊天报告能看见运行时状态而不是只看工具名称。

## 阶段 21：真实结构设计与结构预测运行时

**时间：2026-08-11 至 2026-08-25**

### 优先顺序

1. **ProteinMPNN**
   - 使用官方模型权重和 `protein_mpnn_run.py`。
   - 支持固定链、固定残基、设计链、采样温度、seed。
   - 输出 FASTA、score/probability、参数和版本信息。
2. **RFdiffusion**
   - 使用官方 `scripts/run_inference.py`、固定容器与权重。
   - binder 任务必须要求 target PDB、链、表位或明确的无表位模式。
   - 输出 `.pdb`、`.trb`、轨迹和完整 Hydra config。
3. **AlphaFold**
   - 先选择合规路线：自建 AlphaFold/ColabFold 或受控外部服务。
   - 单体和复合物输出必须包含结构文件、置信度 JSON/PAE、ranking、运行计时和输入上下文。
   - AlphaFold3 与 AlphaFold2/ESMFold 不得混称；每个任务明确运行的实际系统。

### 验收案例

- 输入 1JMB：ProteinMPNN 产生锁定位点和可追溯输出。
- 输入一个已批准的 target PDB：RFdiffusion 产生 2 个 pilot backbone 与 `.trb`。
- 输入单链/复合物：AlphaFold 输出 PDB/mmCIF、PAE、pLDDT/ipTM（适用时）和排名文件。

## 阶段 22：小分子、肽与相互作用工作流拆分

**时间：2026-08-18 至 2026-09-01，可与阶段 21 部分并行**

### 要做什么

1. 保留 Vina 为独立、受环境门控的真实 workflow：
   - 2D -> 3D -> 质子化/电荷 -> PDBQT -> pocket box -> poses -> log；
   - 输出 pose、参数、seed、score 和日志；
   - docking score 标为排序/构象评分，不等同实验亲和力。
2. 部署真实 DiffDock：
   - 与 Vina 分开建模、版本管理和结果解释；
   - 输出 pose ensemble 与 confidence；
   - 禁止写“预测 Kd/结合能”。
3. 新增 PLIP：
   - 只接收已有复合物 PDB/mmCIF；
   - 输出可下载相互作用报告；
   - 不用于替代 docking 或 affinity 预测。
4. ADCP 与 PPI docking 作为独立后续项目：
   - 不复用 DiffDock；
   - 为 peptide/PPI 分别设计输入限制、约束、评分和 benchmark。

### 验收案例

- 5IKR + 布洛芬：Vina 完整工件、参数、pose 输出。
- EGFR + 吉非替尼：DiffDock pose/confidence 输出，报告不出现 Kd。
- 1ATP：PLIP 相互作用报告，与 docking 报告分开显示。

## 阶段 23：人类靶点与膜蛋白情报层

**时间：2026-08-25 至 2026-09-08**

### 数据合同

1. `HumanProteinProfile`
   - UniProt accession、canonical/isoform、亚细胞定位、TM/胞外区、功能和注释证据。
2. `ExpressionSafetyProfile`
   - HPA/GTEx 正常组织、免疫细胞、肿瘤表达；
   - 数据版本、组织/细胞类型和表达单位；
   - 不把 RNA 与蛋白表达混成同一分数。
3. `PathwayRelation`
   - Reactome 通路、方向、参与角色、证据和版本。
4. `OffTargetRisk`
   - 目标/候选配对；
   - 胞外可及域、结构域/表位相似度、健康组织表达和风险解释；
   - 不以全长序列相似度单独下结论。

### 首批验收任务

- CXCL12 受体表：身份、定位、受体-配体关系、通路、表达和疾病证据逐条可追溯。
- TGF-beta 膜/胞外关联蛋白：筛选条件可重放、来源版本可追溯。
- MUC16 纳米抗体脱靶：输出“候选风险队列”，明确是表位/结构筛查候选而不是实验脱靶结论。

## 阶段 24：抗体人源化与可开发性

**时间：2026-09-01 至 2026-09-15**

### 要做什么

1. 接入 ANARCI/IMGT：
   - VH/VL 识别、kappa/lambda 校验；
   - IMGT/Kabat/Chothia 编号；
   - 不完整或链型不确定时阻断。
2. 接入人类 germline 库：
   - V/J 匹配、框架替换、CDR 保留；
   - 回突位点标注为结构/家族假设或已知证据。
3. 建立保守型人源化输出合同：
   - 原序列、编号映射、germline 命中；
   - proposed variants、每个框架改动的理由和风险；
   - developability 检查、表达/结合/稳定性实验计划。

### 验收

- 小鼠 kappa VH/VL 示例必须返回编号和链型证据。
- 无抗原表位/结构时不得承诺亲和力保持。
- 用户可导出完整残基映射表。

## 阶段 25：酶发现和可校准性质预测

**时间：2026-09-08 至 2026-09-29**

### 要做什么

1. 宏基因组 PET 水解酶发现 MVP：
   - 输入 reads/contigs；
   - ORF calling、去冗余、HMM/家族、催化 motif、信号肽、结构/保守位点、序列簇多样性；
   - 输出候选序列、证据、风险和实验优先级。
2. 极端环境酶筛选：
   - taxonomy、来源环境、培养/测定条件、温度/pH、底物和文献来源独立存储。
3. 相对活性排序：
   - 对 PETase、漆酶、淀粉酶等按家族建立训练/验证集；
   - 无家族内校准数据时只输出候选优先级，不输出定量 kcat、最适 pH 或倍数提升。
4. 延续已完成的湿干闭环：
   - 将纯酶动力学、稳定性和表达/分泌分离；
   - 第二轮仅生成受证据约束的二点组合，三点以上依赖前序组合实验。

## 外部平台继续取证的问题

请用户按顺序向 MatwingsVenus 询问并保留完整工具卡片/文件列表：

1. **RFdiffusion 零成本运行时预检**
   - 要 checkpoint hash、镜像 digest、GPU/CUDA、完整命令模板、预期 `.pdb/.trb/trajectory` 文件。
2. **最小 RFdiffusion pilot 的逐项报价**
   - 2 个 backbone、每个 2 条 ProteinMPNN 序列、复折叠；先报价再确认。
3. **AlphaFold3 实际任务的工件**
   - 要求 mmCIF、confidence JSON、PAE、ranking、MSA/模板/日志与任务状态。
4. **DiffDock 的科学边界**
   - 明确是否输出姿势置信度而非 affinity；要求 pose 文件、模型版本和输入配体 3D 来源。
5. **人类靶点/抗体专项的数据来源**
   - MUC16 脱靶、CXCL12 受体、TGF-beta 通路、人源化，逐条索要数据库版本、算法和可导出的证据表。
6. **长任务成本审计**
   - 要求提交前报价、最终扣费明细、取消后的计费状态和输出文件留存时间。

## 决策门

| 门 | 条件 | 未通过时 |
|---|---|---|
| 真实性门 | 模型/运行时/版本/工件可追溯 | 降为 proxy 或 blocked |
| 输入门 | 结构、编号、配体 3D、表位/底物信息完整 | 请求补充，禁止提交 |
| 成本门 | 逐项报价和确认记录存在 | 不提交长任务 |
| 解释门 | 结果不越过工具科学边界 | 降级为构象/排序假设 |
| 实验门 | 测试条件、重复、对照、蛋白归一化完整 | 不提升为工程结论 |

## 参考依据

- AlphaFold 3 官方输出说明：结构 mmCIF、置信度 JSON、ranking、PAE/pLDDT/ipTM 等。
- RFdiffusion 官方说明：`run_inference.py`、checkpoint、`.pdb`、`.trb` 和 trajectory 工件。
- ProteinMPNN 官方说明：`protein_mpnn_run.py`、权重、锁定链/位点、seed、FASTA/score 输出。
- DiffDock 官方说明：输出 pose/confidence，不是 binding affinity 预测。
- AutoDock Vina 官方文档：pose、energies、seed、box 与 docking 参数。
- Reactome、UniProt/EBI Proteins API、Human Protein Atlas：人类靶点、通路和表达层应可版本化、可程序化检索。
