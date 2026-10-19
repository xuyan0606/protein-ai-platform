# 版本管理审计记录

日期：2026-10-17
工作树：`feature/4track-upgrade-20260627`
状态：代码门禁已接入，线上发布待正式 manifest

## 已核对项目

- 生产模型配置：`gpt-6-sol`
- 报告 schema：`1.1`
- 湿实验计划 schema：`wet_lab_plan_v1`
- 前端构建 hash：由 `RELEASE-MANIFEST.json` 的 `alignment.frontend_bundle_sha256` 绑定
- 后端、前端、worker、MD worker、ligand worker：要求 `@sha256` 固定镜像
- 回滚：要求上一版 release ID 与 manifest SHA-256
- 工作树：当前包含既有改动，不能生成可直接上线的 clean release manifest

## 证据

- 版本一致性测试：`9 passed`，覆盖 Git revision、报告 schema、前端 bundle、模型选择、运行时镜像 digest 和 rollback 漂移
- release acceptance 对齐门测试：`3 passed`
- 发布、部署和湿实验定向测试：`22 passed`
- 核心报告/结构/证据回归：Python 3.12 报告/策略 `213 passed`；结构工具 `36 passed`
- 证据、manifest、报告质量和用户场景回归：`41 passed`
- 前端构建：通过
- `check_upgrade_readiness.py --json`：无 manifest 时将 `release.provenance` 和 `release.alignment` 标记为 `manual_required`

## 未完成项

1. 在干净 release 工作树生成正式 `RELEASE-MANIFEST.json`。
2. 填入真实镜像 digest 和上一版本 rollback manifest。
3. 在 Python 3.12 项目环境运行完整后端回归。
4. 线上执行 7DVJ 上传、报告生成、下载/发布、健康检查和回滚演练。

补充：Python 3.12 定向报告/结构/BLAST 服务回归已执行；BLAST 仍有 2 个 API 级用例需要挂载 OIDC signing key，不能用临时密钥替代生产配置。

## Chroma 数据卷切换风险更新（2026-10-17）

- `deploy-aliyun.sh app up` 现要求先停止并归档现有 Chroma `/chroma/chroma` mount，写出 SHA-256 与 JSON receipt；归档失败会中止升级。
- 脚本级归档/校验回归 `2 passed`，部署顺序回归已加入 `test_release_deployment_scripts.py`。
- 该 receipt 只证明归档完整性，不证明 `chromadb/chroma:0.6.3` 能读取线上旧版本数据。仍需隔离环境真实 restore drill 和 collection 查询后，才可解除数据兼容性人工门。
- 当前 upgrade readiness 为 `blocked`，工作树 dirty 文件数 461、正式 release manifest 和本地部署环境配置缺失；没有生成发布 manifest 或修改线上容器。

在这些证据完成前，不切换线上 `current`。
