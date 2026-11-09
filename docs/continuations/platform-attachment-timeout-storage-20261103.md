# 附件等待与对象存储问题修复（2026-11-03～04）

应用源码`f13e774cdd473fd2f4f1349b2436c0325312541e`已上线，2026-11-04 07:43北京时间完成验收，状态为`accepted_with_open_storage_issue`。聊天阻塞与摘要等待已修复，OSS云端恢复仍需有效凭据或RAM角色。

## 故障与根因

独立实测发现真实浏览器附件上传成功后110秒仍未发出聊天请求。ChatInput把结构解析和可选AI摘要串行绑定；默认摘要强制走Claude中继，返回503 model_not_found后仍逐次重试，单次120秒且多个供应方串行等待。未知摘要模型的回退只改了显示对象，没有改调用ID。

OSS原生签名GET和现有MinIO调用均为403 InvalidAccessKeyId。当前服务器、历史发布、本机部署配置的凭据指纹相同；服务器没有可用实例RAM角色或独立OSS配置。未输出、提交或更改密钥。有效凭据/角色是云端修复的外部前提，不能把本地回退当作OSS恢复。

## 应用改动

- 聊天使用include_summary=false，只传结构解析事实；解析请求15秒上限。失败展示错误并保留附件和任务，重试复用上传对象，附件准备期间展示进度。
- 结构页摘要整体25秒上限，含重试/短摘要重生成；超时取消供应方协程并返回状态，保留结构数据。前端请求35秒上限，明确展示摘要不可用状态。
- 默认结构摘要使用实测约3秒完成的direct DeepSeek路由，未知模型调用ID与回退对象一致；明确model_not_found/无可用模型通道跳过无效重试。
- 对象存储限定连接3秒/读取10秒、关闭客户端隐式重试；连接检查限定目标bucket权限。运行失败清除缓存以允许恢复，健康判断允许重新连接。删除同时清理本地旧回退副本，避免云端恢复后遗留本地对象。上传API显式返回实际storage后端。

## 发布前验证

- 新测试先在旧实现失败：摘要总超时、未知模型ID回退、聊天parse-only、恢复后本地副本清理、恢复检查五项；模型503无效重试单独复现失败。
- 定向71项通过；后端全量1862项通过（161.36秒）；前端lint/build通过。
- 前端浏览器合同测试通过：受控解析失败时未发聊天、文件/文字保留、重试不重复上传、parse-only请求、签名确认、结果呈现、报告导出。
- 生产配置下不含序列的独立摘要探针：DeepSeek约2.76秒、GPT-5.6 sol约3.86秒完整返回。

## 发布与线上验证

发布目录：`/opt/protein-ai-platform/releases/20261103-attachment-f13e774cd/protein-ai-platform`；发布包796文件校验通过。四个后端服务各259运行文件及11个前端静态文件核验通过。八个容器healthy、重启0；原配置、环境、镜像和数据卷保持。

2026-11-03 17:28:35北京时间启动应用切换；浏览器验收会话中断后，2026-11-04重新登录，从新会话完成全链路。中断期间的原测试策略已经持久化，没有被当作浏览器通过证据。

- 新账号真实486 aa PDB浏览器上传→结构解析→签名策略确认约22.7秒（含CLI操作），解析完成到发聊天约418毫秒，`include_summary=false`。策略刷新后仍待确认。
- 从刷新后的页面点击确认，实际执行结构搜索、残基映射、二硫键扫描、性质、身份与特征步骤，并提交异步BLAST。无failed工具。目标条件完整保持95℃/5min/30%/≥60%；3422字节报告持久化、刷新和390宽检查通过，浏览器/HTTP错误为空。
- 酶身份与测定证据缺失使目标模块及候选流程blocked，候选结果为`needs_input`、空候选并要求人工复核。这是科学证据门控，不是有效突变或热稳定性收益验证。
- 结构页真实摘要约7.8秒完整返回（direct DeepSeek）；受控超时页面明确提示且保留486残基解析数据，390宽通过。后台断网临时容器另证实总超时取消供应方协程。
- 四种策略、跨用户404/403、旧签名409、会话cookie/Bearer/刷新通过。
- 实际文件接口返回`storage=local`，授权下载字节一致、跨用户拒绝、删除后404。OSS原生仍`InvalidAccessKeyId`，没有执行成功的OSS云端往返，配置未改。已询问有效凭据文件路径或RAM角色。
- 两个临时账号禁用、六会话/五PDB副本/一个自动生成特征报告附件删除，一个测试BLAST取消；独立数据库/存储回读和旧Bearer403通过。本机/服务器临时登录资料与输入副本已删除，浏览器已关闭。
- 原消息内容哈希、原486 aa结构哈希和原BLAST RID `EJM32AS6016`保持。51表备份在断网临时库恢复通过，迁移号`20260917_0004`；生产库未恢复或迁移。

生产正式记录：`docs/baselines/current-production.json`，服务器`/opt/protein-ai-platform/production-version.json`。本地回执：`output/attachment-release-f13e774cd/`；浏览器DOM：`output/playwright/attachment-f13e774cd/`；服务器回执：`/opt/protein-ai-platform/candidates/attachment-f13e774cd-acceptance/`。

仅应用回退入口：`python3.11 /opt/protein-ai-platform/releases/20261103-attachment-f13e774cd/protein-ai-platform/scripts/prepare_thermostability_release.py --rollback-runtime /opt/protein-ai-platform/candidates/attachment-f13e774cd-private`。保留最新数据；未执行生产回退演练。服务器`current`仍陈旧，不能据此重建。可信TLS及registry RepoDigest既有例外保留。

保持20261103快照、旧容器和原报告/结构/RID；不恢复或迁移生产数据库。默认回退应用并保留最新数据。
