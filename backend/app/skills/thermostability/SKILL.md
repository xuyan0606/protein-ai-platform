---
name: thermostability
description: >
  Engineering protein thermostability — improving Tm, half-life at elevated
  temperature, and thermal unfolding resistance. Covers disulfide engineering,
  hydrophobic core packing, helix stabilization, Gly→Pro substitutions,
  and salt bridge optimization.
  Triggers: "thermostability", "Tm", "melting temperature", "heat resistance",
  "thermal stability", "耐热", "热稳定", "temperature", "unfolding"
category: engineering
tags: [thermostability, Tm, disulfide, packing, unfolding]
triggers:
  - thermostability
  - Tm
  - thermal
  - heat
  - 耐热
  - 热稳定
  - temperature
  - unfolding
  - melting
---

# 热稳定性单突变筛选

使用 `thermostability_candidate_workflow`，产出待实验的候选假设。

1. 先确定 endpoint（tm / half_life / residual_activity）、method、pH、底物、缓冲液、辅因子及 min_activity_retention_pct。half_life / residual_activity 还需温度，residual_activity 还需热处理分钟数。最适温度不等于热稳定性。
2. 核验输入序列、样品/成熟肽起点、身份和功能注释；身份 query 的 sequence_sha256 必须对应此序列。KWB 模型生产门继续独立生效。
3. 优先复用适合的实验/已有预测结构。缺结构时才选择 ColabFold；默认本地 MSA，公共 MSA 须明确授权。PDB 作者编号、插入码、缺失片段和输入序列编号必须核验，不能按相同数字迁移文献突变。
4. 明确提供 mutations，或 candidate_positions（每个位置枚举19种替换），或 candidate_sources（kind/reference/sequence_sha256/mutations）。多来源取并集去重，未命中文献不阻断。跨蛋白候选先独立映射审查；此工具不自动迁移同源突变。
5. 催化位点、必需功能、金属配位和现有二硫键保守保护；配体和跨链接触进入人工审查。没有配体/生物学装配信息不代表不存在功能风险。
6. DDGun 是预测 unfolding ΔΔG，正值表示预测更稳定，不能换算 Tm/半衰期/活性。ESM WT-marginal 是进化偏好。各自保留原始值、方向和版本，不相加成未经验证的总分。
7. EVcouplings 在 MSA 质量满足时作为可选证据；强耦合位置不全部禁改。MD 是按需机制研究，不是全部候选的强制依赖，也不证明 Tm 增加。
8. 输出单点候选、来源、编号、风险、缺失证据及 WT 对照；人工审查后按实验预算选择。取得单点热稳定性、活性和表达反馈后再设计组合。规则风险筛查不能证明组合获益或排除上位性。

预测结构的 B-factor 列通常存 pLDDT，高值表示置信度，不能解释为高柔性。实验 B 因子同样不能直接跨结构比较。二硫键、盐桥、核心填充、Gly→Pro 等属于依赖具体局部环境的设计假设，不承诺固定 ΔTm 或低风险。

最终验收：在相同实验预算和目标工艺条件下，相比人工/简单共识筛选，是否得到更多热稳定性改善且活性保留的单突变体。API执行成功、算法真实运行和实验收益分别记录。
