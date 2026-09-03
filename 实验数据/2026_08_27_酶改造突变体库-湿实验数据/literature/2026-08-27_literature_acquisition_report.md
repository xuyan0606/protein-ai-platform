# 酶突变湿实验文献数据首轮采集报告

日期：2026-08-27

## 结果

- 从 Europe PMC 官方 API 保存 6 类检索元数据。
- 保存 34 份 PMC 开放全文 XML。
- 建立 27 个全文证据候选，其中 23 个已定位到正文数据表。
- 建立 13 个全文/补充材料获取 backlog。
- 从 NCBI 保存 8 份母本参考/CDS 翻译 FASTA，并建立 7 条编号预检记录。
- 当前 `training_eligible_rows=0`；所有候选均需母本序列、编号、construct、许可和人工复核闭环。

候选分布：

| 酶类 | 全文证据候选 |
|---|---:|
| 淀粉酶/葡糖淀粉酶 | 8 |
| 木聚糖酶 | 7 |
| 甘露聚糖酶 | 3 |
| 植酸酶 | 4 |
| 葡萄糖氧化酶 | 4 |
| 酸性蛋白酶 | 1 |

机器清单：

- `screening/oa_fulltext_table_candidates.jsonl`
- `screening/fulltext_acquisition_backlog.jsonl`
- `index/raw_europepmc/*.json`
- `raw_fulltext_xml/<family>/*.xml`
- `sequences/reference/*.fasta`
- `screening/sequence_numbering_precheck.jsonl`

## Measurement 抽取进度

- Batch 001：`extraction/measurement_candidates_batch001.csv`，39 条，覆盖 4 篇论文的淀粉酶、甘露聚糖酶和葡萄糖氧化酶湿实验表格。
- Batch 002：`extraction/measurement_candidates_batch002.csv`，47 条，覆盖 YiAPPA 30 条、XynR 8 条、PjxA 组合构建体 9 条。
- Batch 003：`extraction/measurement_candidates_batch003.csv`，132 条，覆盖 EfAmy 88 条、TmPhy 16 条、GOx 28 条；由 `build_measurement_batch003.py` 从 JATS XML 表格可重现生成。
- Batch 004：`extraction/measurement_candidates_batch004.csv`，197 条，覆盖 BLA 85 条、xynA 92 条、A. niger GOx 20 条；由 `build_measurement_batch004.py` 从 JATS XML 表格可重现生成。
- Batch 005：`extraction/measurement_candidates_batch005.csv`，87 条，覆盖 MFAps 16 条、XYL10C_∆N 39 条、ManAK 32 条；由 `build_measurement_batch005.py` 从 JATS XML 表格可重现生成。
- Batch 006：`extraction/measurement_candidates_batch006.csv`，98 条，覆盖 XynA 的 Q24A、K104A、K143A 与四个完整工程构建体；`nd` 保留为不可检测原值。
- Batch 007：`extraction/measurement_candidates_batch007.csv`，16 条，覆盖 FSA/EH-CC-E204G 的 DSC Tm 与 Ca/Zn ITC Kd/DeltaH；Table 2 `rowspan` 金属上下文由构建器显式继承。
- Batch 008：`extraction/measurement_candidates_batch008.csv`，9 条，覆盖 PMC8546418 Table 1 的 XynLC9/N8Y/W6F-Q7H 动力学；Table 2 计算结构量排除。
- Batch 009：`extraction/measurement_candidates_batch009.csv`，16 条，覆盖 PMC11430584 Table 1 的 W6F/Q7H 相对 Xynst 的四底物动力学；Table 2 计算结构量排除。
- Batch 010：`extraction/measurement_candidates_batch010.csv`，8 条，覆盖 PMC5984770 Table 1 的 AnP-M1/AnP-M2 植酸酶动力学。
- Batch 011：`extraction/measurement_candidates_batch011.csv`，12 条，覆盖 PMC6883096 Table 1 的 DS153/DS241/DS428 木聚糖酶动力学。
- Batch 013：`extraction/measurement_candidates_batch013.csv`，12 条，覆盖 PMC9181005 Table 1 的 AppA HDT motif 变体动力学。
- Batch 014：`extraction/measurement_candidates_batch014.csv`，8 条，覆盖 PMC9181005 Table 2 的 AppA InsP5 区域选择性比例。
- Batch 015：`extraction/measurement_candidates_batch015.csv`，22 条，覆盖 PMC10101328 Table 2/3 的植酸酶活力、产量和动力学。
- Batch 016：`extraction/measurement_candidates_batch016.csv`，3 条，覆盖 PMC6167268 Table 4 的 MutMCAP-8 N331Q 酸性蛋白酶指标。
- Batch 017：`extraction/measurement_candidates_batch017.csv`，18 条，覆盖 PMC9148494 Table 1 的 TlGA-M4/M6/M7 表达和动力学指标。
- Batch 018：`extraction/measurement_candidates_batch018.csv`，28 条，覆盖 PMC12007714 Table 1/2 的 M-60(5) 动力学与热失活指标；编号冲突保持阻断。
- Batch 019：`extraction/measurement_candidates_batch019.csv`，3 条，覆盖 PMC5457547 Table 1 的 mRmMan5A 同条件底物比活。
- 十九批合计 763 条、763 个唯一 measurement ID，覆盖 28 个 PMCID；来源文件均存在且 SHA-256 一致。
- Batch 002 保留 PjxA 半衰期原始单位：PTxA 为秒，PjxA-DB/PTxA-DB 为分钟；未静默换算 WT `30 s`。
- Batch 003 保留完整组合构建体；TmPhy 直接构建谱系为 `TmPhyM <- TmPhy`、`TmPhyMD1 <- TmPhyM`、`TmPhyMD2/MD3 <- TmPhyMD1`，GOx Parent 与 WT 背景分开。
- Batch 004 不将 xynA Table 3 的 `ND` 写为 0；Table 4 仅作为“各构建自身无添加对照归一化”的条件响应候选，不解释为绝对突变活性。
- Batch 005 保留 MFAps 双半胱氨酸构建、XYL10C_∆N N 端截短工程亲本和 ManAK partial CDS/文内命名冲突，不将任何组合体拆成伪单点标签。
- 所有 502 条均为 `training_eligible=false`、`formal_decision_written=false`、`safe_for_model_claim=false`。
- 三篇 Batch 002 来源均在正文声明 CC BY 4.0，但仍需保留署名、许可证链接和修改说明，不因开放许可跳过 construct 与人工复核。
- Batch 004 中 xynA 和 GOx 来源为 CC BY 4.0；BLA 来源为 CC BY-NC-ND 4.0，其许可条件需独立回执，不得因 PMC 可读自动进入训练。
- Batch 005 中 XYL10C_∆N 来源为 CC BY 4.0；MFAps 和 ManAK 为 CC BY-NC-ND 4.0，两者均保持许可范围审查待决。

## 高价值真实表格

1. TlGa15B 葡糖淀粉酶，pH 4.5 条件高度相关。Table 1 给出 WT、GA1、GA2 的比活、Km、Vmax 和 kcat/Km；GA2 存在 Q108E/Q108A 正文冲突，因此保持阻断。[DOI](https://doi.org/10.1186/s13068-021-02052-3) / [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8520190/)
2. BaqA-deltaC N185D。Table 1 给出 WT/突变的 Km、kcat 和 kcat/Km；正文 pH 扫描覆盖 4.0-4.5，但精确低 pH 数值位于曲线，不能由“>70%”替代。[DOI](https://doi.org/10.1038/s41598-025-27398-8) / [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12695923/)
3. Bacillus licheniformis alpha-amylase。Table 1 包含 14 个单突变体和 3 个双突变体的 Km、kcat、半衰期和 Tm；表题、Results 和 Methods 的 pH/温度不一致，已保持条件冲突。[DOI](https://doi.org/10.1016/j.csbj.2024.02.005) / [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10883975/)
4. PjxA 木聚糖酶。Table 1 记录组合突变、60 C 半衰期和 Tm，PTxA-DB 的半衰期为 53.6 min、Tm 为 76.6 C；组合体不得拆成伪单点效应。[DOI](https://doi.org/10.1186/s12896-019-0541-7) / [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6659274/)
5. XynR T315H/N/Q/S。Table 2/3 含有/无 CaCl2 的 Tm 以及 65 C 热失活动力学；同时保留性能下降变体。[DOI](https://doi.org/10.1038/s41598-024-57819-z) / [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10987496/)
6. Anman beta-mannanase。Table 1 同时包含 E15C、S65P、A84P、A195P、T298P 单点和 Mut5 组合体的比活、残余活性、Km、kcat、半衰期和 Tm。[DOI](https://doi.org/10.3389/fmicb.2023.1119232) / [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9986629/)
7. YiAPPA 植酸酶。Table 2 给出 K189R、K216R 和双突变的比活、动力学、55/80 C 半衰期、T50、Tm 和蛋白酶耐受率；Table 4 含食品原料降植酸数据。[DOI](https://doi.org/10.4014/jmb.2403.03031) / [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11380507/)
8. Penicillium glucose oxidase。Table 1 同时含正向和负向突变；例如 D408C 的半衰期/Tm 低于 WT，适合保留为真实阴性证据。[DOI](https://doi.org/10.3390/ijms19020425) / [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5855647/)
9. GOx 微流控库。Table 1 给出 WT、Parent 和六个多突变体的 Km、kcat、kcat/Km 和比活；Parent 是工程背景，不能当作 WT。[DOI](https://doi.org/10.3390/molecules25102418) / [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7287683/)
10. MCAP N331Q 酸性蛋白酶。Table 4 含 milk-clotting activity、proteolytic activity 和比值；不同信号肽/密码子背景必须先完成背景对齐。[DOI](https://doi.org/10.1186/s13568-018-0691-3) / [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6167268/)

## 明确阻断

- PMID 40249742 在 L203I/L103I 之间存在编号冲突。
- TlGa15B GA2 在 Q108E/Q108A 之间存在正文冲突。
- PcMan113 正文存在 N246Y/N236Y 冲突。
- PjxA 摘要/结论将“`delta Tm = 21.3 C`”误写为起始 Tm；正确表格证据为 WT `55.3 +/- 0.4 C`、PTxA-DB `76.6 +/- 0.6 C`、`delta Tm = 21.3 +/- 1.0 C`。
- XynR Table 2 为不可逆 CD unfolding 的 apparent Tm，只给 duplicate 平均值而无离散度；Figure 3 与 Methods 对 buffer 分别写为 `20 mM phosphate-NaOH` 和 `100 mM HEPES-NaOH`，必须保留条件冲突。
- 组合突变、截短、删除、片段替换和工程背景不得拆成未实测单点标签。
- 图中估读数据只能进入低置信候选，不能伪装成表格测量值。
- PMC 可读不自动等于允许任意再分发；每篇仍需记录具体许可证和署名要求。
- 任何 MD、对接、B-factor、计算 delta-delta-G 或预测值均不作为湿实验监督标签。

## 母本与编号预检

- PcMan113 `GIO63020.1`：F110、N246 均直接匹配参考序列。
- PjxA `MK948222` CDS 翻译：7 个报告位点全部直接匹配。
- PjxA 复核表明 `MK948222.1` 实为 573-bp mature partial CDS，对应蛋白 `QDX01881.1` 190 aa；它不含论文所述 28-aa 信号肽。因此 7/7 直接匹配只对成熟链编号成立，全长前体偏移仍是推导值。
- BaqA `JN797599.1` CDS 翻译：N185 直接匹配；仍需绑定 C 端截短背景。
- MCAP `JQ906105` CDS 翻译：N331 直接匹配；仍需区分信号肽和表达背景。
- Anman `XP_001390707.1`：5 个位点在参考序列 `+38` 偏移后全部匹配，符合成熟链编号候选，但边界仍需人工确认。
- TmPhy `WP_277039767.1`：7 个位点在 `+22` 偏移后全部匹配，符合信号肽切除编号候选。
- Xynst `WP_101863413.1`：W6/Q7 在 `+28` 偏移后匹配，但论文实际克隆仅报告与参考序列高于 95% identity，不能据此确认 construct。
- YiAPPA 当前论文只声明实验室保存的 `pSTOP1622-yiappah`；未给出完整序列、信号肽、成熟链边界或 accession。引用的 2006 年论文可继续回溯，但疑似 UniProt `Q000T0` 不得在未直接绑定前升级为已验证母本。
- XynR 主文报告 `Bacillus sp. TAR-1`，PDB 8Y1M/8XY0 的构建序列却映射到 UniProt `P07528` / *H. halodurans* C-125；物种与序列来源冲突未解决前不能直接升级母本。

## 下一步门槛

1. 从 accession、补充序列和 construct 描述恢复每篇论文的实际母本序列。
2. 对突变位点执行野生型残基逐位校验，并区分全长、成熟链、信号肽和 tag 编号。
3. 将每个“突变体-指标-实验条件”拆成独立 measurement 行，保留原始值、单位、误差、重复数和表格位置。
4. 完成人工复核和许可证回执后，才允许生成正式训练导入提案。

本报告只证明文献证据已获取并初筛，不证明突变有效性，不构成模型质量或发布结论。
