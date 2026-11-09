# 热稳定性真实多轮对话修复已上线（2026-11-05）

2026-11-05 16:36:07北京时间接受源码`0d743f03db7dad48b3b1ddeaf9a57b15bee210f9`，状态`accepted_with_open_storage_issue`。修复明确10个具体替换误用默认12、位点逻辑/工具来源追问泛化、对应平台工具后做一下误路由为纯聊天；支持自然数量改8并保持结构与目标。解释依据当前任务最新保存回执，新任务/新上传/未完成或失败回执不复用旧候选，旧10/12差异明确承认。

最终1936项全量通过（239.15秒），相关208项通过；815冻结文件、生产镜像隔离479结构/60真实DDGun评分/10初步位点通过。真实Chrome连续10轮26项通过，三次确认实际返回10/10/8，逻辑与来源两轮约1.3秒解释且零新工具，95℃/5min/30%→80%和pH4.5–4.8补充/刷新/390宽保留，阅读刷新零执行。三轮共一个BLAST，状态查询0.147秒返回waiting，不代表NCBI已完成；跨用户与真实旧签名拒绝、12字段服务端原结构绑定通过。

八服务healthy/restart0，四后端各262源码和11静态/HTTP哈希与原配置通过，51表断网备份恢复通过，生产库未恢复/迁移。两临时账号禁用、两会话/一上传清理，一个测试BLAST停止平台轮询；数据库审计独立复核，旧Bearer403和本地上传目录空通过。原1069/1070消息、479/486结构、原任务/RID及20261103快照保持。清理复用helper曾即时打印创建0任务，最终持久化记录已按审计更正为1，不能引用中间输出为最终数量。

前端源码/静态不变，聊天上方六模板保留，lint/build沿用此前验收。ESM缺torch/esm、OSS既有凭据问题及本地回退、陈旧current和TLS/registry例外未由本轮解决。初步位点仍为研究假设，不保证95℃残余酶活或实验增益。正式指针与仅应用回退入口见`docs/baselines/current-production.json`和`docs/continuations/platform-thermal-dialogue-20261105.md`；证据`output/thermal-dialogue-0d743f03d/`，原始失败/红绿日志保留在`output/thermal-dialogue-other-20261105/`。以下生产记录按历史理解。

## 验收证据

完整报告：`output/thermal-dialogue-0d743f03d/TEST-REPORT.md`。逐轮真实浏览器JSON/文本、22个服务端回执和冻结manifest均保留。原始99abb复测失败及本地红绿日志：`output/thermal-dialogue-other-20261105/`。

本次未更换候选算法或评分定义；只修复数量、执行路由及保存回执解释。旧回执数量10/12不一致可解释但不改写。新结构或新任务、最新未完成或失败执行不回用旧科学结果。

## 仅应用回退入口

`python3.11 /opt/protein-ai-platform/releases/20261105-thermal-dialogue-0d743f03d/protein-ai-platform/scripts/prepare_thermostability_release.py --rollback-runtime /opt/protein-ai-platform/candidates/thermal-dialogue-0d743f03d-private`

保留最新用户数据库，不恢复生产库，不覆盖20261103快照，不使用陈旧current重建。本次没有实际执行生产回退演练。
