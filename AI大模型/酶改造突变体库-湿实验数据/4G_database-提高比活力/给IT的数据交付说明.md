# 给IT的数据交付说明

## 数据集

4G木聚糖酶突变体酶活数据（合并分析版），整合去异常值分析与试管复测分析。

**表达体系：毕赤酵母（Pichia pastoris）分泌表达，载体PICZa-4G。酶分泌至培养上清，测定时直接取上清稀释检测，无细胞破碎步骤。低酶活混杂因素为表达水平/上样量/样品制备差异。**

## 文件结构

- 数据文件: CSV(共7个)
- 说明文件: MD(2个)
- Excel汇总: 4G木聚糖酶突变体酶活_合并分析.xlsx(9个工作表)

## 关键字段说明

- `experiment_round`: Round1=96孔板, Round2A=小筛试管复测(图表1), Round2B=I153V克隆对比验证(图表2)
- `confidence_tier`: A=多轮复测覆盖, B=单轮结构化/图表估计
- `batch_id`: B1-B3=Round 1, B4=Round 2A, B5=Round 2B
- `control_sample_id`: 本批次对照样本ID
- `vs_control_pct_change`: 相对本批次对照的百分比变化

## 入库建议

1. 以04_原始测量事实表.csv作为事实表主表
2. 以05_样本与批次对应表.csv作为样本注册表
3. 以06_批次与对照映射表.csv作为批次-对照权威映射
4. 使用sample_id和measurement_id作为关联键
5. 对于confidence_tier=A的样本, 可优先用于模型训练

## 数据质量提示

1. Round 2A/2B数据为从图表截图估计的近似值, 建议后续补充原始Excel数据后将confidence_tier从B升级为A
2. I153V修正说明: 图表2证实I153V与对照无显著差异(相对酶活91%), 图表1中I153V高酶活值为假阳性
3. Round 1数据经过异常值清洗(去最小/最大/IQR), 清洗标记详见Excel的"OD清洗标记"工作表
4. 本数据为毕赤酵母分泌表达体系, 无细胞破碎步骤; confounding_flag中"表达水平"指不同克隆间分泌表达量差异, 非破碎效率差异
