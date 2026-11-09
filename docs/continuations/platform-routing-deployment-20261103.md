# 20261103 附件摘要路由修复发布

已发布并完成本次修复验收，状态 `accepted_with_recorded_exceptions`；服务器和本地生产记录均已同步。验收时间2026-11-03 14:50:23（北京时间）。

用户明确要求“测试没问题上线”。本轮发布源码 `9deb6b63dc33de5caeea4e3030f2d101aa20010f`，应用目录 `/opt/protein-ai-platform/releases/20261103-routing-9deb6b63d/protein-ai-platform`。前置缺陷和红绿测试见 [独立实测记录](platform-summary-independent-test-20261103.md)。

## 修复与发布前验证

治理意图识别先剥离附件元数据，再扫描用户正文，避免结构摘要中的“模型质量”将比活力任务误判为平台治理查询。与上一生产源码 `7feb1ca25` 相比，应用仅修改 `backend/app/core/agent_graph.py` 一行；前端、数据库模型、迁移、科学算法和执行门控不变。

- 后端全量：`1792 passed in 232.73s`，包含此前221项定向回归；`git diff --check`通过。
- 按冻结提交逐文件生成发布包，774文件逐项核验；既有未跟踪的 `frontend/public/vendor/3Dmol.js` 与上一发布包哈希相同，前端dist直接复制实际上一发布目录。
- 包 SHA-256：`b43b6a1457d7625941835f51e05f083b8ba86b4b1f40f9f3c7f9e55968baa185`。
- 在现有生产后端镜像、`--network none` 的隔离容器中编译新源码，三档深度×三种限制共九种路由场景通过；直接询问平台模型质量仍触发治理检查。
- 三个worker在线，切换前 active/reserved/scheduled均为0。
- 新备份122249472 bytes，SHA-256 `c5c6567e3c9a1da053d7f28e44b5ebef913be8a99217025d8d4ba44404eb5a9c`；只在断网临时PostgreSQL中恢复验证，51表、迁移号 `20260917_0004`，未恢复或迁移生产库。

## 上线后的真实验收

五个应用容器逐个替换，八容器healthy、重启0；四个后端服务各258个运行文件哈希一致，11个前端静态文件HTTP哈希一致。原启动命令、环境、镜像、资源限制、持久卷均保留，模型HTTP服务健康。切换开始时间为2026-11-03 14:36:02（北京时间）。

用两个独立临时账号、原336 aa结构副本进行公网验收：

1. 切换前注册、登录、PDB真实上传解析和下载哈希、跨用户文件隔离、原报告哈希与原BLAST检查点记录通过；切换后原Bearer、cookie、refresh、新登录、旧上传访问和所有者隔离通过。
2. 摘要API完整返回中文正文并保留GMQE=0.99。实际供应方摘要本身包含“模型质量”，本轮没有为触发该词而替换真实摘要。
3. 将完整 `analysis` JSON作为附件提交“提高蛋白的比活力”，生成正确的六步签名策略并确认执行：`structure_search_foldseek → residue_mapping_sifts → predict_properties → blast_search → enzyme_identity_profile → build_site_structure_function_features`。没有混入 `external_research_evidence`。
4. 输入解析、链内编号映射、性质与结构特征工具完成；BLAST提交异步任务并返回所有者受保护的查询入口。没有执行无前置身份/底物证据的kcat、位点扫描或候选排序。
5. 实际生成“比活力改造：身份检索阶段进展”报告，指出链A为336 aa、无需重复上传FASTA、同源检索仍在等待和需要补充的测定条件。报告2038 bytes，最终合同状态 `BLOCKED`，这是身份/测定证据缺失的门控，不是路由或工具执行故障。未将当前报告标为READY。
6. 真实浏览器表单登录、刚生成的阶段报告呈现、刷新保留、390像素宽显示通过；浏览器/HTTP错误均0，文档宽390与视口一致。本轮浏览器验证对象为执行后的报告，PDB摘要页面沿用此前独立浏览器证据，未冒称本轮重新测试该页面上传。

三档策略/限制矩阵全部通过：fast/standard联网和deep本地/禁BLAST均保留结构与编号步骤，受限制计划不含BLAST；跨用户检查点404、旧签名409且确认状态未被改变。此处的限制矩阵测试对象是策略与签名，没有扩大为重测所有工具的离线执行。

两个临时账号禁用，旧Bearer实测403；五会话、一个上传删除，一个测试BLAST取消并保留审计。清理后另行读取数据库和对象存储，确认账号均禁用、会话和文件不存在、任务检查点canceled、原结构哈希一致。原报告正文哈希、原RID保留；本机及服务器本轮临时登录凭据已删除。最终八容器健康与ID匹配已验收生产记录。

## 保留与回退

原报告消息4159/会话1010、原任务 `d62da89b-4b41-4c18-86ba-48ca446f36a9` 和RID `EJM32AS6016`不被本轮验收替换。原任务检查点仍为等待超时的degraded；本轮未恢复原查询或重复提交原序列，也未取得原RID完成结果。科学身份、突变收益、湿实验效力仍是独立问题。

新应用回退入口：

```sh
python3.11 /opt/protein-ai-platform/releases/20261103-routing-9deb6b63d/protein-ai-platform/scripts/prepare_thermostability_release.py \
  --rollback-runtime /opt/protein-ai-platform/candidates/routing-9deb6b63d-private
```

默认只回退应用，保留最新数据库与上传。原20261103快照、上一生产容器和更早的回退容器均保留；current仍陈旧，不从其重建。未执行生产回退演练。可信TLS和registry RepoDigest既有例外继续保留。

## 证据位置

- 服务端私有发布准备：`/opt/protein-ai-platform/candidates/routing-9deb6b63d-private/`。
- 新备份及隔离恢复回执：`/opt/protein-ai-platform/backups/routing-9deb6b63d-precutover/`。
- 服务端验收：`/opt/protein-ai-platform/candidates/routing-9deb6b63d-acceptance/`。
- 本地脱敏回执：`output/routing-release-9deb6b63d/`；浏览器快照：`output/playwright/routing-9deb6b63d/`；后端全量日志：`output/routing-release-backend-20261103.log`。
