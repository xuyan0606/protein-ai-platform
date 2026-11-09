# 20261106 补充条件后继续原项目修复

状态：已发布源码 `9f916ca4abe58fd50589f43c9683cfa336fde3b0`；接受时间 2026-11-06T05:14:22.657818+00:00 UTC；`accepted_with_open_storage_and_tool_issues`。替换前版0d743f03d；原数据保持。

## 已复现的问题与原因

此前26项浏览器验收把“补充条件后生成新策略”当作成功，未完成补充后再次继续的全路径。因此旧验收结论不能证明不会重新分析或忘记目标。

- 完整条件被当作目标变更；裸温度/缓冲液又可能被当作普通聊天。
- “不要再开一个新的对话分析”匹配了“新的对话”，清空原任务上下文。
- UI修改策略模式将原任务和补充数据拼接后送去重新规划。
- 条件更新后旧待确认签名仍可执行旧参数。
- 首次本地全量1960项通过后，真实Chrome又发现：最终继续请求生成了pH优化策略。运行时路由保留耐热目标，规划器却反向取最后一条pH条件作为目标，两处选择逻辑不一致。

## 本轮修改

纯条件回答持久化到原会话并确定性确认，不调用模型、规划、身份检索或工具；旧待确认策略失效。实际请求继续计算时再生成待确认策略，保留上传、目标、数量、链范围、工具限制及逐轮更正的条件。路由和规划共用同一个目标来源选择器，条件数据不重新决定优化目标。百分数只沿用用户已明确的评价指标，不从裸百分数猜指标。

探索报告只展示已知条件，不再重复展示一整张未知字段表。位点缺失和编号异议优先解释本任务最新回执，明确ColabFold、DDGun、ESM各自实际状态，不生成假评分或自动重启流程。身份门控、工具算法、模型权重和生产配置未改。

## 验证证据

本地证据目录：`output/assay-continuation-20261106/`。

- 初始补充条件回归：12失败、4通过（原有日志保留）。
- 最终策略边界新增红测试：`resumed-plan-red.log`，明确复现热目标变成pH策略。
- 25项接续回归通过：`resumed-plan-green.log`。实际流式策略检查最新条件、原结构绑定、10数量、链A、禁BLAST及无未确认执行。
- 真实Chrome在4207端口、独立SQLite与存储目录完成5次输入、12项检查：修改策略回答条件、3次更正、否定新任务、刷新、再次请求工具、再次刷新、390宽。完整结果 `browser-local-direct.log`；原实际失败 `browser-local-wrong-ph-goal.log`；截图 `output/playwright/assay-continuation-local-20261106.png`。
- 本地浏览器只验收输入/路由/签名策略/持久化，不代表实际突变计算完成；结构为20残基CA测试夹具。
- 最终全量1961项通过（120.80秒），见 `backend-full-final.log`。首次1960项通过仍漏掉下游错目标，不能用测试总数替代真实路径。

## 线上只读发现

只读查询1083/1070/1069，会话原文、原结构和原BLAST未修改。

- 1083消息4550：97.79秒，外层completed、业务partial；筛查60、DDGun60/60、请求12/返回12；ESM blocked。不能称这次工具一直卡住。
- 1083消息4558：序列路径ColabFold blocked，原因 `COLABFOLD_LOCAL_MSA_PATH is required for local MSA; public search is disabled.`；DDGun/ESM未运行，`no_eligible_hypotheses`。4559追问未给位点，4560泛化为用户条件不全，未解释实际工具阻断。
- 1070消息4468：完整95℃/5min/30%→80%及测定条件补充后，4469错误说任务输入不足。

## 未解决项

没有接通ESM或补齐ColabFold本地MSA，没有新增跨会话身份存档，也没有把全部身份流程压为两步。本轮不能宣称全部底层工具恢复、目标效果验证或全部原始需求完成。逐工具状态与通过标准见 `platform-tool-verification-20261106.md`。

## 发布后实际验收

线上Chrome21项通过，首个补充回合与后续7轮分次接续；最终确认实算479结构位置、60/60 DDGun、10个候选，实际回执含90℃/10分钟/40%→85%/pH4.5。两轮回执追问无重跑。原1069/1070/1083消息、结构和原任务哈希保持，2账号停用、3临时会话和1上传清理，未新建BLAST。8服务healthy/restart0，4后端各262源码、11静态HTTP哈希/配置通过，51表备份断网恢复；生产库未迁移或恢复。正式记录同步`docs/baselines/current-production.json`，完整证据`output/assay-continuation-20261106/TEST-REPORT.md`。

隔离字符串转义、浏览器发送/加载/ID类型/确认脚本失败、清理内部括号及过早finalize均未算成功。浏览器加载竞态曾误发到额外空白测试会话，已清理；前端竞态本轮未修。上游错误拒答仍出现在策略背景，未修模型全路径，不应称全部业务完成。

仅应用回退：`python3.11 /opt/protein-ai-platform/releases/20261106-assay-continuation-9f916ca4a/protein-ai-platform/scripts/prepare_thermostability_release.py --rollback-runtime /opt/protein-ai-platform/candidates/assay-continuation-9f916ca4a-private`。原容器和20261103快照保留，不恢复生产库。
