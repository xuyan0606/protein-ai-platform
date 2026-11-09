## 20261103 摘要修复已发布（最新事实）

用户已授权发布，实际源码为`7feb1ca253fea76dc196928a5983229c0bb0497d`。八容器healthy、重启0；发布后真实摘要API完整返回并保留GMQE=0.99，11个前端静态文件哈希通过。新备份经隔离恢复验证51表、迁移号20260917_0004；生产库未迁移或恢复。原报告与BLAST保留。临时验收账号、会话及上传清理。浏览器页面/刷新未验收，不能称全部通过。

回退：`python3.11 /opt/protein-ai-platform/releases/20261103-summary-7feb1ca25/protein-ai-platform/scripts/prepare_thermostability_release.py --rollback-runtime /opt/protein-ai-platform/candidates/summary-7feb1ca25-private`。保留最新数据、20261103快照及旧容器；current仍陈旧。以下历史记录按其当时状态理解。

# 20261103 摘要修复候选与联网身份证据补充

本轮接续用户“自己测试一下／继续”，允许联网。生产仍为 `2b46baee8f0926b04e547e2e2063355ef8620097`，本轮未切换应用、恢复数据库、迁移或改写原报告。摘要修复是已验证的候选，不能记作线上问题已关闭。

## 摘要故障与修复

用原336 aa结构在生产依赖环境中只读解析，再直接运行生产摘要函数及内存加载的候选函数。原结构SHA-256与原报告内容哈希均验证保持不变。

- 生产函数真实复现 `finish_reason=length`、`summary_status=truncated_not_used`：600个completion token全部为reasoning token，正文字符数0。不是单纯中文正文过长。
- 请求的Claude上游通道本轮返回503／model_not_found，现有网关回退至实际响应模型 `deepseek/deepseek-flash`；上述600 token被备用模型推理消耗。本轮没有修改网关策略。
- 候选将预算从600提高到1600，要求4项、总计不超过240个汉字；截断时用相同结构事实重新生成一次更短的完整摘要，不拼接或发布截断片段。持续截断或重试异常仍保留截断状态。
- 同一真实输入的候选连续3次生成完整摘要，171／209／177字符；均为`finish_reason=stop`、保留GMQE=0.99并说明模型估计的证据边界。消耗分别为700／621／1566 completion token，其中推理589／487／1452。
- 公共`summary_model`是原有产品选择项标签；本轮实际上游身份以验收回执的`response_model`为准，不能把选择标签当作Claude实际成功服务的证据。

修复前新增的两项截断恢复测试均失败，修复后通过。摘要、PDB接口、身份收集、理论模型、BLAST恢复与审计定向测试74项通过；后端全量 **1783 passed in 200.94s**。`git diff --check`通过。

本轮没有发布候选，因此未把此次函数实算写成“公网新版本摘要页面／刷新验收通过”；上轮公网主流程和浏览器结果仍以独立复测记录为准。

## 新的序列同源与功能证据

2026-11-03约12:51北京时间，原BLAST RID `EJM32AS6016`直接向NCBI查询仍为HTTP200／WAITING，持久化任务也为waiting／ncbi_waiting。未重复提交、伪造结果或把等待改成阴性。

另以原336 aa序列查询RCSB sequence服务（identity cutoff 0.5、E-value cutoff 1e-5，实验结构），返回2QHA_1、3CBW_1、2WHK_1。服务返回的标准化score只作排序，不能当作序列一致性。再下载官方聚合体序列和UniProt序列，使用Biopython PairwiseAligner比对：match=2、mismatch=-1、gap open=-10、gap extend=-0.5、terminal gap=0。

| 来源 | 实际逐位比对 | 查询覆盖度 | 注释 |
| --- | --- | --- | --- |
| [RCSB 2QHA entity 1](https://www.rcsb.org/structure/2QHA) | 330/336，98.214% | 100% | Beta-1,4-mannanase，EC 3.2.1.78；参考342 aa包含末端6个His |
| [UniProt Q5PSP8](https://www.uniprot.org/uniprotkb/Q5PSP8/entry) | 330/336，98.214% | 100% | Bacillus subtilis；GH26；本条功能与位点包含自动规则推断，不能全部称为实验注释 |
| [UniProt O05512](https://www.uniprot.org/uniprotkb/O05512/entry) | 328/336，97.619% | 100% | Bacillus subtilis 168，gmuG/ydhT；GH26；功能有文献实验依据，催化位点仍为同源转移 |

查询序列与Q5PSP8的27–362区间对应，6处差异位于查询编号16、18、81、89、91、134；同一位置与2QHA的1–336区间对应。差异是相对参考序列的比较，不证明参考序列就是用户的WT，也不构成新设计的有益突变。

两个UniProt条目的催化Glu193／Glu292均映射至查询序列 **E167／E266** 且残基一致，可作为需优先保护、后续核验的催化位点线索。它们没有变成用户酶的直接实验结论。

2QHA为1.45 Å的X射线实验结构，其原论文为Yan等（2008），[DOI:10.1016/j.jmb.2008.03.068](https://doi.org/10.1016/j.jmb.2008.03.068)，PMID18455734。1.45 Å属于参考结构，不能赋给用户的SWISS-MODEL模型。

这些证据强烈支持用户序列属于GH26内切β-1,4-甘露聚糖酶相关蛋白；实际底物、比活力测定条件、用户来源和WT归属仍需核对。不能直接称为“已证明有效突变”或“比活力提升”。精确序列MD5查询在EBI蛋白API及UniParc均无记录，这与高相似度同源存在并不矛盾。

## 接续与证据

候选只改变`backend/app/api/pdb.py`及摘要回归测试；数据库模型／迁移、前端和科学门控未改。原报告4159、原会话1010和原BLAST保持，未创建测试用户、上传副本或新BLAST任务。新同源证据本轮仅记录为补充，没有伪装为原NCBI任务结果或写入原报告。

本地可复核证据在被忽略目录 `output/summary-fix-20261103/`：`verification.json`、`live-summary.jsonl`、`identity-receipt.json`、`backend-full-tests.log`。失败验收脚本先遇到LiteLLM Usage不可JSON序列化，再遇到容器内误用宿主机目录；均修正后重跑，未修改应用来绕过验收。

若发布此候选，仍须基于实际容器和最新生产记录准备新版本、保留20261103快照及现有回退容器、执行当时的新备份与隔离恢复核验，再完成公网摘要和页面复测。不得从陈旧current重建；不恢复生产数据库。
