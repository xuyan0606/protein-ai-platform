## 当前源码与 Git 基线（20261109 修复）

- 当前实际运行源码为 `197bf67c137b4059c88455f81b7e4956e1ef1e8d`，release 为 `20261107-chat-timeout-197bf67c1`。以下旧生产记录按历史理解。
- 从 `release/production-20261107` 建立后续修复分支，发布标签 `production/20261107-197bf67c1` 固定后禁止移动。该分支是干净平台源码归档，提交号与原运行提交不同；两者的关系见 `docs/baselines/current-production.json` 的 `git_source_management`。
- 修改前读取 `docs/baselines/platform-source-management-20261109.md`，运行 `python3 scripts/verify_production_source.py --check-refs --require-clean`。源码不匹配或工作区不干净时先核查，不能用旧主目录测试替代线上版本验收。
- 服务器事实入口为 `/opt/protein-ai-platform/production-version.json`；旧 `current` 指针保留兼容历史配置，禁止据其目录推定当前源码或重建服务。核对实际容器挂载和文件哈希。
- 原始历史保留在私有归档引用和增量恢复包；不得将其中的数据库备份、模型缓存、虚拟环境、密钥、用户输入整体推送到远端。
- 本次只修复源码版本管理；未重新部署应用，未宣称外部身份查询或 NCBI BLAST 超时已解决。

## 20261106 补充条件接续修复已上线（有明确遗留问题）

应用源码9f916ca4abe58fd50589f43c9683cfa336fde3b0，正式状态accepted_with_open_storage_and_tool_issues。补充条件仅更新原任务/失效旧策略，实际继续统一按原热目标规划；否定新任务不清上下文；缺位点和编号追问引用真实回执。最终1961项、25项接续、本地Chrome12项与线上Chrome21项通过；线上首回合和后7轮分次接续，实算479结构/60 DDGun/10候选，回执保留90℃/10min/40%→85%/pH4.5。不能把候选评分当作实测收益。8服务healthy/restart0；818文件、4后端各262源码、11静态HTTP及原配置通过，51表断网备份恢复，生产库未迁移/恢复。原1069/1070/1083消息、原结构和BLAST保持，2账号停用、3临时会话/1上传清理，未新建BLAST。ESM/ColabFold配置、跨会话身份档案、上游模型误拒/背景污染、快速切换会话发送竞态及OSS均未修。失败脚本日志保留；详见`docs/continuations/platform-assay-continuation-20261106.md`和`output/assay-continuation-20261106/TEST-REPORT.md`。以下本地候选与0d生产均为历史记录。

## 20261106 补充条件接续修复候选（尚未上线）

当前生产仍为0d743f03d。本地修复纯条件回答误规划、否定新任务误清上下文、旧签名未失效、最终继续被pH条件覆盖目标；路由和规划共用目标来源。原26项验收错误接受“补条件生成新策略”，并未跑完下一次继续。新25项接续/完整流式策略回归、本地Chrome12项和全量1961项（120.80秒）通过。首轮本地1960通过后仍被真实Chrome抓到pH错目标，红测试与原失败日志保留。未切换生产、未改原数据，不宣称底层ESM/ColabFold恢复、身份跨会话存档或全部需求完成。详见`docs/continuations/platform-assay-continuation-20261106.md`和逐工具清单`platform-tool-verification-20261106.md`；证据`output/assay-continuation-20261106/`。

## 20261105 多轮对话数量与实际工具依据修复已上线（最新生产事实）

2026-11-05 16:36:07北京时间接受源码`0d743f03db7dad48b3b1ddeaf9a57b15bee210f9`，状态`accepted_with_open_storage_issue`。修复明确10个具体替换误用默认12、位点逻辑/工具来源追问泛化、对应平台工具后做一下误路由为纯聊天；支持自然数量改8并保持结构与目标。解释依据当前任务最新保存回执，新任务/新上传/未完成或失败回执不复用旧候选，旧10/12差异明确承认。

最终1936项全量通过（239.15秒），相关208项通过；815冻结文件、生产镜像隔离479结构/60真实DDGun评分/10初步位点通过。真实Chrome连续10轮26项通过，三次确认实际返回10/10/8，逻辑与来源两轮约1.3秒解释且零新工具，95℃/5min/30%→80%和pH4.5–4.8补充/刷新/390宽保留，阅读刷新零执行。三轮共一个BLAST，状态查询0.147秒返回waiting，不代表NCBI已完成；跨用户与真实旧签名拒绝、12字段服务端原结构绑定通过。

八服务healthy/restart0，四后端各262源码和11静态/HTTP哈希与原配置通过，51表断网备份恢复通过，生产库未恢复/迁移。两临时账号禁用、两会话/一上传清理，一个测试BLAST停止平台轮询；数据库审计独立复核，旧Bearer403和本地上传目录空通过。原1069/1070消息、479/486结构、原任务/RID及20261103快照保持。清理复用helper曾即时打印创建0任务，最终持久化记录已按审计更正为1，不能引用中间输出为最终数量。

前端源码/静态不变，聊天上方六模板保留，lint/build沿用此前验收。ESM缺torch/esm、OSS既有凭据问题及本地回退、陈旧current和TLS/registry例外未由本轮解决。初步位点仍为研究假设，不保证95℃残余酶活或实验增益。正式指针与仅应用回退入口见`docs/baselines/current-production.json`和`docs/continuations/platform-thermal-dialogue-20261105.md`；证据`output/thermal-dialogue-0d743f03d/`，原始失败/红绿日志保留在`output/thermal-dialogue-other-20261105/`。以下生产记录按历史理解。

## 20261105 热稳定性工具候选与真实续问修复已上线（最新生产事实）

北京时间2026-11-05 14:54:43接受应用源码`99abb9c5997c86e28350f9a3a1cad41f08a20a69`，状态`accepted_with_open_storage_issue`。真实会话1070的4UZU是479坐标残基、作者4–482，勿混用此前486 aa。修复测定字段/持久化JSON误变表达目标、5min误认PDB、pH范围丢失、续问目标/数量丢失、input_only坐标未下传、探索不生成/不评分、证据JSON截断及无来源LLM替换。全结构保守堆积探针是研究假设，实际DDGun独立评分，ESM生产缺torch/esm明确blocked；正式候选/实验集合保持为空，不保证95℃残余活性或有效突变。

最终1912项通过（167.10s），811冻结文件、生产镜像隔离479行/60评分/10初步位点、公网8工具/8103字节持久化报告/42状态更新通过；原样95℃/5min/30%→80%和pH4.5–4.8补充、12个服务端结构绑定字段、继续要工具位点通过。原会话4460/4468只读重放保留时间边界/上传/目标/10数量、不新提BLAST。真实Chrome十一项（模板/刷新/390宽/零执行POST）通过。八服务healthy/restart0，四后端各261文件与11静态/HTTP哈希和配置通过，51表断网备份恢复通过，生产库未恢复/迁移。

首轮3f74候选因主规划器仍误认可溶性淀粉未接受，实际回退2e后新增主规划器/完整策略红绿回归，再发布最终99abb。首轮哈希/恢复及原会话重放脚本的时序/字段错误已保留并修正，不能写成应用成功或删除失败证据。两轮共四临时账号/四会话/两上传清理且独立复核/旧Bearer403通过；原消息/479与486结构/BLAST RID/20261103快照保持。前端静态未改，lint/build沿用此前验收；OSS既有凭据问题、陈旧current及既有TLS/registry例外保留。正式记录见`docs/baselines/current-production.json`，实施和仅应用回退入口见`docs/continuations/platform-thermal-sites-20261105.md`，证据`output/thermal-sites-99abb9c59/`。以下均按历史记录理解。

## 20261104 未知条件继续热稳定性探索已上线（最新生产事实）

北京时间2026-11-04 17:15:15接受源码 `2e2879ee59e4f51985466c4145e2eba2eee265f3`，状态 `accepted_with_open_storage_issue`。用户明确授权放宽聊天探索门控：只有序列/PDB且身份、实验条件未知时继续探索分析；WT/来源/映射及已知催化/金属/二硫键保护保留，科学API默认strict，不虚构条件或放行正式候选集合。新增35秒有界RCSB→UniProt/InterPro身份参考路线，独立于BLAST；当前486 aa找到4条相似参考但序列不同，未转移位点或宣称身份确认。条件逐轮合并/更正，酶活测定方法和未加热保持比例不再误当第二目标。

后端1887项通过；真实未知条件签名执行8工具/2553字节报告及后续95℃/5min/30%/≥60%+完整条件策略通过；真实Chrome九项（刷新/模板/390宽/零执行POST）通过。展示脱敏路径引起一次错误比较标记，补充独立会话直接核验服务端12个字段均绑定原上传后修正记录，错误回执保留。首轮fb827211d未接受，清理并实际回退61d后发布最终2e；累计6临时账号/6会话/3上传清理，独立复核/旧Bearer403通过，未新建BLAST。

八服务healthy/restart0，806冻结文件、四后端各260文件、11静态文件哈希与配置核验通过；51表备份隔离恢复，生产库未恢复/迁移，原消息/结构/新旧RID和20261103快照保留。前端静态不变，沿用此前已接受lint/build合同。current仍陈旧，OSS既有凭据问题未解决。详情与回退61d入口见 `docs/continuations/platform-thermal-exploration-20261104.md`、`docs/baselines/current-production.json`，证据 `output/thermal-exploration-2e2879ee5/`。下方生产记录均按历史理解。


## 20261104 长会话任务记忆与后台查询恢复已上线（最新生产事实）

北京时间 2026-11-04 14:34:12 验收应用源码 `61d86d19b15bd0f0457ed52f7f94dc716bf134c2`，状态 `accepted_with_open_storage_issue`。同会话18轮后由数据库恢复项目、序列和95℃/5min/30%/≥60%，真实API续问与签名策略、真实浏览器9项（刷新/再次刷新/390宽）通过；1875项后端、前端lint/build、后台查询4项、PDB原回归10项及模板19项通过。查询15秒超时后可重查/恢复原RID，不重复提交；原NCBI `EN3F8R22016`只读仍WAITING，科学门控保留。八容器healthy/restart0，803包文件、四后端各259源码和11静态文件校验通过。新备份隔离恢复51表，生产库未恢复/迁移；两测试账号禁用、两会话删除、独立复核与旧Bearer403通过，原消息/结构/RID及20261103快照保持。六个上方模板保持。中间8ef候选未接受，补充真实FASTA识别后最终验收；首轮模型偶发拒答另存，重复请求与浏览器实际回复通过，不保证上游模型绝对稳定。当前实际版本、证据及回退（先回8ef，再可回原已接受版本）见 `docs/continuations/platform-chat-memory-task-status-20261104.md` 与 `docs/baselines/current-production.json`。current仍陈旧、OSS既有凭据问题未解决。以下均按历史记录理解。

## 20261104 聊天上方提问模板已上线（最新前端事实）

前端源码 `c03b63b753eba3f514d561cee6c6399f37d5e585`，2026-11-04 08:56:52 北京时间验收。用户明确只放在聊天窗口上方：六模板点击填入、草稿替换确认、附件保留、展开收起及执行/待确认锁定。19 项新浏览器合同、10 项原聊天回归、16 项线上实际登录/刷新/390 宽检查及 lint/build 通过；11 静态文件 HTTP/容器哈希一致。只替换前端，另外七容器不变，八容器 healthy/restart0。后端仍 `f13e774cd`，数据库未迁移/恢复；原消息/结构/RID与20261103快照保留。一个临时账号清理且旧Bearer403；没有创建会话/上传/BLAST。OSS既有凭据阻塞仍未解决。正式记录使用独立 `frontend_source_commit`，详见 `docs/continuations/platform-chat-templates-20261104.md`；仅前端回退入口在该文档，勿误用旧五服务回退来撤销模板。

## 20261104 附件等待修复已上线，OSS仍待有效凭据（最新事实）

应用源码`f13e774cdd473fd2f4f1349b2436c0325312541e`，2026-11-04 07:43北京时间验收，`accepted_with_open_storage_issue`。后端1862项、前端lint/build和失败重试浏览器合同通过。真实486 aa UI上传约23秒进入签名策略，刷新后确认执行、实际工具、3422字节报告、再次刷新及390宽通过；保留95℃/5min/30%/≥60%，无failed工具，科学身份/测定证据不足仍needs_input/blocked且空候选。真实完整摘要约8秒；受控超时保留解析数据。八容器healthy重启0，796包文件、四服务各259源码及11静态文件校验通过；51表备份隔离恢复通过，生产库未恢复/迁移。两测试账号、六会话、五PDB副本、一个自动报告附件及一测试BLAST清理复核，原哈希/RID和20261103快照保持。

OSS原生签名仍403 InvalidAccessKeyId，现有部署/历史凭据一致，未找到可用RAM角色；实际storage=local，读写删与权限已验证，**不能称OSS恢复**。已请求有效凭据文件路径或RAM角色，勿要求聊天粘贴密钥。生产正式指针已更新，current仍陈旧；回退保留最新数据。详见`docs/continuations/platform-attachment-timeout-storage-20261103.md`与`docs/baselines/current-production.json`。以下095449f78等记录按历史理解。

## 20261103 热稳定性发布后独立实测（最新测试结论）

17:04北京时间完成新账号/结构副本实测，生产仍`095449f78`，结论`passed_with_findings`。公网API签名策略、实际工具、保留95℃/5min/30%/≥60%的报告、四种策略与权限通过；真实浏览器报告显示/刷新/390宽通过。但聊天真实附件提交110秒未进入策略确认，上传成功却尚未发聊天请求：摘要模型连续503 model_not_found，页面无进度或错误反馈。另发现OSS InvalidAccessKeyId，文件读写依赖本地回退，不能说OSS正常。本轮没有改动应用/配置或重新部署。两个临时账号、五会话、两个上传及一测试BLAST清理，独立复核/旧Bearer403通过，原报告/结构/RID与20261103快照保留，八容器healthy重启0。详细证据与边界见`docs/continuations/platform-thermal-independent-test-20261103.md`；以下发布记录按其当时状态理解。

## 20261103 486 aa 热稳定性主聊天修复已上线（最新生产事实）

生产源码`095449f78be899910a14b32e1234c58987456814`，2026-11-03 16:32:29北京时间完成验收，状态`accepted_with_recorded_exceptions`。后端1856项、生产镜像断网九场景真实486 aa重放及两种注册顺序通过；公网副本实际上传→签名策略→确认工具执行→报告→浏览器刷新/390宽通过。报告保留95℃/5min/30%/≥60%，没有无关kcat或旧饱和扫描；最终BLOCKED为身份及测定证据缺失，未宣称有效突变。八容器healthy重启0，四个后端服务各259文件与11个前端静态文件校验通过。两个临时账号禁用、五会话/一上传删除、一测试BLAST取消，独立复核及旧Bearer403通过；原报告/结构哈希与原RID保留。生产库未迁移/恢复，51表备份隔离恢复成功；20261103快照和旧容器保留。current仍陈旧，TLS/registry既有例外保留，生产回退演练未执行。实施、证据及回退入口见`docs/continuations/platform-thermal-routing-fix-20261103.md`，实际生产记录见`docs/baselines/current-production.json`。以下记录按其当时状态理解。

## 20261103 附件摘要路由修复已上线（最新生产事实）

用户要求测试通过后上线，已发布9deb6b63dc33de5caeea4e3030f2d101aa20010f，14:50完成验收。后端全量1792项、生产镜像隔离九场景通过；实际含“模型质量”的供应方摘要附件生成正确六步策略，确认执行得到身份检索阶段报告，浏览器展示/刷新/390宽通过。三档策略、限制、跨用户及旧签名检查通过。八容器healthy重启0；两账号/五会话/一上传/一测试BLAST清理且复核，原报告/结构哈希与原RID保留。新备份隔离恢复51表通过，生产库未恢复/迁移；旧容器和20261103快照保留，current仍陈旧。状态accepted_with_recorded_exceptions，TLS/registry既有例外不变，科学身份与收益仍未确认。生产记录见`docs/baselines/current-production.json`，验收与回退见`docs/continuations/platform-routing-deployment-20261103.md`。以下记录按其当时状态理解。

## 20261103 摘要发布后独立实测（最新结论）

真实浏览器表单登录、PDB上传完整摘要（GMQE=0.99）、390宽显示、策略刷新保留通过；结构页刷新回到上传页，重新上传成功。发现新问题：附件摘要“模型质量”误触发治理路由，四个线上计划遗漏结构步骤，实际确认执行为BLOCKED且无预期身份阶段报告；本轮为passed_with_findings。已本地修复并复跑221项通过，提交9deb6b63d，未部署，生产仍7feb1ca25。两个账号禁用、五会话及三个上传删除、一个测试BLAST取消；原报告哈希/RID保留。八容器healthy重启0，原NCBI HTTP200/WAITING，平台检查点为等待超时degraded。详见`docs/continuations/platform-summary-independent-test-20261103.md`。

## 20261103 摘要修复已发布（最新事实）

用户已授权发布，实际源码为`7feb1ca253fea76dc196928a5983229c0bb0497d`。八容器healthy、重启0；发布后真实摘要API完整返回并保留GMQE=0.99，11个前端静态文件哈希通过。新备份经隔离恢复验证51表、迁移号20260917_0004；生产库未迁移或恢复。原报告与BLAST保留。临时验收账号、会话及上传清理。浏览器页面/刷新未验收，不能称全部通过。

回退：`python3.11 /opt/protein-ai-platform/releases/20261103-summary-7feb1ca25/protein-ai-platform/scripts/prepare_thermostability_release.py --rollback-runtime /opt/protein-ai-platform/candidates/summary-7feb1ca25-private`。保留最新数据、20261103快照及旧容器；current仍陈旧。以下历史记录按其当时状态理解。

# AGENTS.md — 酶蛋白 AI 平台项目记忆

## 20261103 比活力报告修复已上线（最新生产事实）

- 当前生产源码`2b46baee8f0926b04e547e2e2063355ef8620097`，八容器healthy、重启0；见`docs/continuations/platform-activity-report-deployment-20261103.md`和`docs/baselines/current-production.json`。下述7c46ab6c3发布记录为上一版本。
- 真实PDB副本完成上传→签名策略→确认执行→实际工具→阶段报告及浏览器呈现验收；没有放松身份/候选门控，目标酶身份与有效突变仍未确认。
- 原报告哈希与原BLAST RID保留；临时测试账号/会话/文件/任务已清理。生产数据库未恢复/迁移；20261103快照、首次发布及本次切换前旧容器都保留。
- 本次回退入口为新版本下`prepare_thermostability_release.py --rollback-runtime /opt/protein-ai-platform/candidates/activity-2b46baee8-private`，仅回退应用并保留最新数据。服务器current仍陈旧，不用它重建。

## 20261103 热稳定性应用发布（上一生产版本）

- 此前实际应用源码为 `7c46ab6c3a4e7d90603bd5e45424096c98b09228`，状态 `accepted_with_recorded_exceptions`。先读 `docs/continuations/platform-thermostability-deployment-20261103.md` 与 `docs/baselines/current-production.json`；下述较早生产指针仅作历史。
- 后续平台修改以此次已发布源码为基线；服务器 `production-version.json` 已同步实际验收记录，但 `current` 仍陈旧，不从它复制配置或重建容器。
- DDGun完整同源数据库、ColabFold本地MSA单模型CPU和EVcouplings已通过公开输入真实HTTP验证；发布后DDGun异步API/Celery链路通过。不要扩大为目标酶有效性、湿实验、GPU或长MD已通过。
- 五个原应用容器及 `snapshots/20261103` 均保留，回退入口见上述发布记录；默认只回退应用，保留最新数据。可信TLS与registry RepoDigest仍是明确例外，生产回退演练未执行。

## 20261103 保留版本（后续修改前必读）

- 用户要求把当前状态保留为 `20261103`，后续问题可回退；不得覆盖快照目录或移动既有快照标签。
- 本机恢复入口：`/Users/keweibo/output/platform-version-20261103/回退说明_20261103.md`。服务器实际运行快照：`/opt/protein-ai-platform/snapshots/20261103/`，以 `CHECKPOINT.json` 与 `RESTORE.md` 为准。
- 本地未发布候选标签 `snapshot/platform-20261103-local` 指向 `7015ffda4`，与线上运行版本不同。完整镜像归档在服务器，本机另存源码、配置和数据库副本。
- 已核实实际后端为 `20261030-identity-evidence-tier-b728d4ca`；旧总版本记录及 current 陈旧。后续先读 `docs/baselines/platform-retained-version-20261103.md`，下述旧生产指针仅作历史，不得直接覆盖较新线上改动。
- 默认只回退应用并保留最新用户数据；数据库恢复独立评估。未执行生产回退演练。

后续 agent 进入本项目时，先读取：

- `task_plan.md`
- `findings.md`
- `progress.md`
- `docs/project-experience-memory.md`

## 必守边界

- 不使用 Codex `view_image` 工具；本机模型不支持图像输入。需要图片元数据时用 `sips`、`file`、`mdls`、`ls -lh`。
- Codex 只使用 `4200-4299` 端口范围；本项目默认前端入口是 `http://localhost:4200`。
- 不要声称真实 GPU/GROMACS 长 MD、真实突变体 topology、真实 Vina docking、真实 ligand topology 已完成，除非实际在具备工具链的服务器上跑过并有日志/测试结果。
- 阿里云 GPU 服务器尚未提供；GPU/长 MD/live gate 任务必须继续等待用户提供服务器后再执行。
- 本机当前缺少 `gmx/gmx_mpi`、`obabel`、`vina`、`acpype`、`antechamber`，只能做代码层、smoke、受控 blocked 合同和本地单测。
- `Structure2D_COMPOUND_CID_5478883.sdf` 是 2D SDF，不可直接对接或进入 GROMACS。
- 运行后端主回归和 `scripts/run_release_acceptance.py` 时串行执行，避免 SQLite 测试库冲突。
- `docker compose config` 会展开 `.env` 明文；优先使用 `config --quiet`，不要把密钥输出到终端或日志。
- 工作区可能很脏；不要回滚或删除用户/其他 agent 的改动。

## 当前长期方向

- 真实数据层继续按 `PDB -> AlphaFold -> Foldseek DB` 顺序补齐。
- 配体/底物链路按 `2D SDF -> 3D -> PDBQT -> Vina -> ACPYPE/Antechamber topology -> GROMACS` 顺序推进。
- MD 长任务、topology live gate、真实 batch ranking 等待阿里云 GPU/GROMACS 节点。

## 平台与模型版本边界

- 平台后续改动从已发布源码 `7c46ab6c3` 建立分支，当前生产记录见 `docs/baselines/current-production.json`。`release/production-20261020`（`0421817d`）、`platform-production-20261020.md` 及基线文档提交 `0d752310` 为历史，不覆盖最新运行事实。
- `backend/`、`frontend/`、`docker/` 的平台改动与 `AI大模型/` 的研究改动分别提交；缓存、环境、权重、运行数据不得整体暂存。
- 未验收的本地候选分支和测试结果不表示已经发布；只有实际切换并验收后更新当前生产源码指针。
