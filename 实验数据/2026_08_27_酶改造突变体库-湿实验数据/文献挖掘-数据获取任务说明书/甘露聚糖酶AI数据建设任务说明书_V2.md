# 甘露聚糖酶AI数据建设任务说明书

## 1. 任务目标

现安排开展甘露聚糖酶改造文献数据建设。目标不是泛搜甘露聚糖酶资料，而是围绕**突变体—性质变化**关系，建立可直接用于AI建模的结构化数据集。

第一阶段以**稳定性**和**活性**为主，后续再扩展至 pH 特性、底物相关特性和产物相关特性。

## 2. 范围定义

### 2.1 纳入范围
优先纳入以下研究：
- 定点突变
- 饱和突变
- 组合突变
- 定向进化
- 结构指导改造
- 系统突变扫描
- 补充材料中含完整突变数据的论文

### 2.2 排除范围
以下情况不纳入第一阶段：
- 仅描述野生型性质，无突变信息
- 只有定性结论，无定量数据
- 无法定位“具体突变体—具体性质数值”对应关系
- 实验条件缺失严重，无法判断数据可比性

### 2.3 第一阶段优先标签
- **稳定性**：Tm、T50、半衰期、残余活性
- **活性**：比活、相对活性、酶活单位、kcat、Km、kcat/Km
- **pH 特性**：最适 pH、pH 稳定区间、不同 pH 条件下残余活性
- **底物相关特性**：底物谱、特异性、催化效率变化
- **产物相关特性**：甘露寡糖组成、产物分布、产物特异性变化

## 3. 文献检索要求

### 3.1 检索网站
按以下顺序使用：

1. **PubMed**  
   主检索入口。用于查题名、摘要、关键词、PMID、DOI。  
   `https://pubmed.ncbi.nlm.nih.gov/`

2. **PubMed Central（PMC）**  
   免费全文入口。若文献在 PMC 可获取，优先从这里下载全文和补充材料。  
   `https://pmc.ncbi.nlm.nih.gov/`

3. **DOI 落地页**  
   通过 DOI 跳转论文正式页面，查找 PDF、HTML 正文和补充材料。  
   `https://doi.org/`

4. **SCI-hub**
  用于下载正式PDF
网址：https://www.sci-hub.ren/
用法：将DOI号或PMID号填写至搜索框中，搜索，出来结果后进行保存下载


5. **出版社官网页面**  
   用于下载补充材料、图表附件，并核对方法学细节。  
   常见来源：Elsevier、Springer、Wiley、Nature、ACS 等。

6. **Google Scholar（辅助）**  
   仅用于辅助定位公开版本、作者主页或机构仓储版本，不作为主检索库。



### 3.2 检索关键词
按“酶名称 + 改造动作 + 性质标签”组合检索。

建议首轮关键词：
- `("mannanase" OR "beta-mannanase" OR "β-mannanase" OR "endo-beta-mannanase" OR "endo-1,4-beta-mannanase") AND (mutation OR mutagenesis OR engineering OR "directed evolution" OR "site-directed mutagenesis")`
- `("mannanase" OR "beta-mannanase") AND (stability OR thermostability OR Tm OR T50)`
- `("mannanase" OR "beta-mannanase") AND (activity OR "specific activity" OR kcat OR Km)`
- `("mannanase" OR "beta-mannanase") AND (substrate specificity OR substrate scope OR selectivity)`
- `("mannanase" OR "beta-mannanase") AND (product profile OR manno-oligosaccharide OR hydrolysis products)`

### 3.3 检索步骤
1. 在 PubMed 输入关键词检索。
2. 根据题名和摘要初筛。
3. 记录 PMID、DOI、期刊、年份、链接。
4. 如页面存在 PMC 免费全文入口，转入 PMC。
5. 如无 PMC 免费全文，通过 DOI 跳转出版社正式页面。
6. 在正式页面查找 PDF、HTML 正文、Supplementary information / Supporting information。
7. 将结果登记到文献索引表。

### 3.4 初筛标准
文献一般满足以下至少 2 项即可纳入候选：
- 研究对象为甘露聚糖酶或 β-甘露聚糖酶相关改造
- 有具体突变体名称
- 有定量性质数据
- 有与 WT 对照的数据
- 有表格或补充材料可定位数据来源

## 4. 文献下载与归档要求

### 4.1 下载优先级
按以下顺序获取：
1. PMC 免费全文
2. SCI-Hub填写DOI或PMID号下载
3. 出版社官网开放获取全文
4. 如暂时无法获取全文，保留摘要页、DOI 和正式页面链接，标记待补

### 4.2 每篇文献至少保留
- PDF 文件（如有）
- HTML 正式页面链接
- 补充材料
- 勘误或更新页（如有）

### 4.3 下载步骤
1. 从 PubMed 进入文献详情页。
2. 先看是否有 PMC Full Text / Free PMC article。
3. 若有，进入 PMC，下载 PDF，并检查页面右侧或文末是否有 supplementary files。
4. 若没有 PMC 免费全文，复制 DOI，访问下面网址，进行如下操作：
网址：https://www.sci-hub.ren/
用法：将DOI号或PMID号填写至搜索框中，搜索，出来结果后进行保存下载

5. 将下载结果登记到文献索引表，记录下载来源和本地文件名。

### 4.4 文件命名规则
统一命名：
- `年份_文献名_酶类型.pdf`
- `年份_文献名_酶类型_supp1.xlsx`
- `年份_文献名_酶类型_supp2.pdf`

如 DOI 不便写入文件名，可使用：
- `年份_第一作者_关键词_pmidxxxxxxx.pdf`

### 4.5 目录结构
统一按以下目录归档：
- `literature/raw_pdf/`：PDF
- `literature/supplement/`：补充材料
- `literature/index/`：文献索引表
- `literature/screening/`：初筛结果表
- `literature/extraction/`：抽取结果表

### 4.6 下载不到全文时的处理
- 记录 PubMed 链接
- 记录 DOI 链接
- 记录出版社落地页
- 标记 `access_type = unavailable`
- 保留摘要和元数据，进入待补清单

## 5. 数据抽取要求

### 5.1 抽取对象
以“**每个突变体—每个性质—每组实验条件**”为最小记录单位。

### 5.2 必抽字段

#### 文献表 `papers`
- paper_id
- title
- journal
- year
- doi
- PMID
- source_url
- fulltext_url
- supplemental_url
- access_type
- local_file_name
- inclusion_status
- notes

#### 酶表 `enzymes`
- enzyme_id
- enzyme_name_reported
- normalized_enzyme_name
- enzyme_family
- organism
- accession_id
- wild_type_sequence
- sequence_length

#### 突变体表 `variants`
- variant_id
- enzyme_id
- paper_id
- variant_name_reported
- normalized_variant_name
- mutation_type
- mutation_count
- mutation_sites
- single_or_multi_mutant
- background_variant

#### 表型数据表 `measurements`
- measurement_id
- variant_id
- paper_id
- property_category
- property_name
- substrate
- raw_value
- raw_unit
- normalized_value
- normalized_unit
- relative_to_wt
- direction_of_change
- assay_method
- temperature_c
- pH
- buffer_system
- host_system
- expression_system
- source_location
- extraction_method
- confidence_grade
- qc_flag
- comments

### 5.3 标准化要求
- 单突变统一写法：如 `D32N`
- 多突变统一写法：如 `D32N/S145A`
- 保留原始值和原始单位，同时填写标准化字段
- 图中估读数据必须标记
- 单突变和多突变必须分开标记
- 阴性结果、无改善结果、性能下降结果必须保留
- 不同底物体系数据需分开记录，不得合并
- 产物分布数据需注明检测方法

## 6. 数据质量与质控要求

### 6.1 质量分级
- **A级**：表格或补充材料可直接定位，数据和条件完整
- **B级**：正文或图注可提取，主要信息完整，部分条件缺失
- **C级**：图中估读或推断得到，仅作低优先级补充

### 6.2 质控检查项
- 同一突变体命名是否一致
- 同一数据是否来自不同底物或不同条件
- 同一突变体是否基于不同背景序列
- 是否误把 WT 数据录成突变体数据
- 是否遗漏阴性或无改善突变
- 是否混淆活性、稳定性、pH 特性、底物特性和产物特性标签
- 下载来源是否可追溯
- 补充材料是否与主文一一对应
- 底物名称是否标准化

## 7. 交付物

第一阶段提交以下内容：
1. 候选文献清单
2. 纳入 / 排除结果表
3. 已下载文献索引表
4. 结构化突变体数据表
5. 字段字典与标准化规则文档
6. 质控问题清单

## 8. 验收标准

满足以下条件视为第一阶段合格：
- 已完成 50–100 篇高相关文献筛选
- 文献索引表信息完整，可追溯到 PMID / DOI / 正式页面
- 已建立四张核心数据表并能关联
- 数据记录中保留实验条件，不混填不同条件数据
- 已区分 A / B / C 级数据
- 已保留阴性、无改善和性能下降数据
- 已形成待人工复核清单

## 9. 执行分工

### IT侧
负责：
- 文献检索
- 文献下载与归档
- 数据抽取与入库
- 表结构维护
- 质控标记

### 研发侧
负责：
- 最终确认纳入范围
- 复核重点文献与关键数据
- 处理冲突记录和低可信记录
- 确认后续建模优先标签

## 10. 执行要求

本任务先追求**质量可用**，再追求**规模扩张**。第一阶段先跑通检索、下载、抽取、标准化、质控全流程，再扩展数据量。