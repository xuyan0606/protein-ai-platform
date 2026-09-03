# 给IT的数据交付说明

## 数据集

酸性蛋白酶突变体酶活数据（标准化交付包），来源为上交大数据。

## 表达体系

- **酶名称：** 酸性蛋白酶
- **表达体系：** 毕赤酵母分泌表达
- **宿主菌：** 毕赤酵母 (Pichia pastoris)
- **样品来源：** 发酵上清液（分泌表达，无细胞破碎步骤）
- **测定方法：** 蛋白酶国标法（福林酚法）（GB/T 23527）
- **热稳定性条件：** 80°C, 3min
- **优化目标：** 提高热稳定性 + 提高比活力（单点突变难以双正，需多轮改造）

> 本数据集为毕赤酵母分泌表达体系，酶分泌至发酵上清后直接稀释测定，无细胞破碎步骤。

## 文件清单

| 文件 | 格式 | 编码 | 行数 |
|------|------|------|------|
| 00_先看这个_数据库使用说明.md | Markdown | UTF-8 | - |
| 01_突变体总体判断总表.csv | CSV | UTF-8-BOM | 34 |
| 02_单条测量记录判读表.csv | CSV | UTF-8-BOM | 67 |
| 03_相对对照派生分析表.csv | CSV | UTF-8-BOM | 67 |
| 04_原始测量事实表.csv | CSV | UTF-8-BOM | ~100 |
| 05_样本与批次对应表.csv | CSV | UTF-8-BOM | 34 |
| 06_批次与对照映射表.csv | CSV | UTF-8-BOM | 4 |
| generate_standard_package.py | Python | UTF-8 | - |

## 表结构

### 01_突变体总体判断总表
- 主键：sample_id
- 粒度：每个样本一行（突变体×批次×轮次）
- 新增字段：target_alignment（优化目标对齐）、multi_round_potential（多轮改造潜力）

### 02_单条测量记录判读表
- 主键：judgement_id
- 外键：measurement_id → 04.measurement_id
- confounding_flag值域：no / possible_expression_variation / possible_measurement_variation / unknown

### 03_相对对照派生分析表
- 主键：derived_id
- 外键：measurement_id → 04.measurement_id
- 计算字段：vs_control_ratio, vs_control_delta, vs_control_pct_change

### 04_原始测量事实表
- 主键：measurement_id
- 外键：sample_id → 05.sample_id
- metric_code值域：rel_activity_pct / specific_activity / therm_resid_80c / therm_resid_80c_2

### 05_样本与批次对应表
- 主键：sample_id
- 外键：batch_id → 06.batch_id

### 06_批次与对照映射表
- 主键：batch_id + experiment_round
- 每行记录一个批次×轮次的对照样本信息

## 数据质量提示

1. 所有CSV文件使用UTF-8-BOM编码，Excel可直接打开。
2. confidence_tier字段标注数据置信度：A=结构化复测数据，B=单轮/图片数据。
3. confounding_flag标注混杂因素类型。毕赤酵母分泌表达体系中，低酶活记录标注为possible_expression_variation（表达水平差异），非破碎效果。
4. target_alignment字段标注突变体与优化目标（稳定性+比活力双提升）的对齐情况。
5. 二轮突变体（batch_2）数据来自图片截图估计值，置信度B级。

## 生成脚本

`generate_standard_package.py`为完整生成脚本，包含所有原始数据和处理逻辑。修改输出路径后可重新运行生成全部文件。
