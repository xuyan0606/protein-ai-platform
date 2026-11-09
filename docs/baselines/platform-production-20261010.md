# 酶蛋白平台生产基线（2026-10-10）

> 此文件为历史快照。2026-10-20 已验收生产事实见 [当前机器可读版本](current-production.json) 和 [2026-10-20 基线](platform-production-20261020.md)，不要使用下述旧“最新状态”选择发布版本。

## 最新生产状态（2026-10-13 蛋白任务边界深度修复后）

`current` 指向 `/opt/protein-ai-platform/releases/20261013-3f65c976-task-context-deep`。backend/worker 镜像为 `protein-ai-backend:release-task-context-deep-3f65c976-20261013`（`sha256:bfe83e26800f7aae4acaf58528014165c8f80b2a6c0a63703c156977c40776cc`）；frontend 镜像和页面布局未变。382 项后端测试通过，候选生产镜像内 388 aa 同任务、新任务、保持约束重放通过，运行容器与公网健康检查通过。详见[任务边界深度修复发布记录](../releases/platform-20261013-task-context-deep.md)。以下为历史快照。

## 最新生产状态（2026-10-13 蛋白任务上下文承接修复后）

`current` 指向 `/opt/protein-ai-platform/releases/20261013-525475a8-task-context`。backend/worker 镜像为 `protein-ai-backend:release-task-context-525475a8-20261013`（`sha256:9b4a2d4c86cf203ed07c78ce81e569080a92bbc2c73babd04fb587a19a3ca197`）；frontend 镜像未变。370 项后端测试通过，候选生产镜像内 388 aa 同任务补输入与不同任务边界重放通过，运行容器和公网健康检查通过。详见[任务上下文承接发布记录](../releases/platform-20261013-task-context.md)。以下为历史快照。

## 最新生产状态（2026-10-13 388 aa 报告证据修复后）

`current` 指向 `/opt/protein-ai-platform/releases/20261013-a68c4fb3-388-report`。backend/worker 镜像为 `protein-ai-backend:release-388-report-a68c4fb3-20261013`（`sha256:7964f91c3aeb5d625eb4c202476c83b3fdfa3b27f8031d6c2c0e1adafbdc54e6`）；frontend 仍为下述剪贴板修复镜像。后端 362 项测试和运行容器内 388 aa 报告断言通过；见[388 aa 报告证据修复发布记录](../releases/platform-20261013-388-report.md)。以下为历史快照。

## 最新生产状态（2026-10-13 PDB 序列复制修复后）

`current` 指向 `/opt/protein-ai-platform/releases/20261013-e617bb5c-clipboard`。frontend 镜像为 `protein-ai-frontend:release-clipboard-e617bb5c-20261013`（`sha256:614e8fcf24a99721f07cf28b8994085ec694397ed7a002aa9903b207dd40df8f`）；backend/worker 仍使用下述性质分析范围修复镜像。公网 Playwright 已复测 PDB 序列复制成功和失败提示，详情见[剪贴板修复发布记录](../releases/platform-20261013-clipboard.md)。以下为历史快照。

## 最新生产状态（2026-10-13 性质分析范围修复后）

`current` 指向 `/opt/protein-ai-platform/releases/20261013-262bd9fb-property-scope`。backend/worker 镜像为 `protein-ai-backend:release-property-scope-262bd9fb-20261013`（`sha256:f7f3aac97984a4d84b01e1103e890fc17f76c4bf4d98524141fac7494dcd208c`）；frontend 镜像未变。353 项后端测试通过，真实 3WP6 公网 pH 单目标、三目标、原双目标性质及工程请求完成复测。外部 RCSB 注释有一次未返回，重试后通过；详情见[性质分析范围修复发布记录](../releases/platform-20261013-property-scope.md)。以下为历史快照。

## 最新生产状态（2026-10-13 证据门控深度审计后）

`current` 指向 `/opt/protein-ai-platform/releases/20261013-36c3ff48-evidence-gates`。backend/worker 镜像为 `protein-ai-backend:release-evidence-gates-36c3ff48-20261013`（`sha256:648676c8c25c33e3dd121d461fca6480c984359f68b4e576a268c8f4d32fa4a4`）；frontend 未更新。332 项后端测试通过，真实 3WP6 公网性质/工程请求和同名错序列反例均通过；详见[证据门控深度审计发布记录](../releases/platform-20261013-evidence-gates.md)。以下为历史快照。

## 最新生产状态（2026-10-13 3WP6 性质分析修复后）

`current` 指向 `/opt/protein-ai-platform/releases/20261013-142b9267-3wp6-property`。backend/worker 运行镜像 `protein-ai-backend:release-3wp6-property-fix-142b9267-20261013`（`sha256:3ba070fa40c1c7e1c771dec091e7ae27cc987517548f55f592d4c6292bc6e28b`）；frontend 镜像未变。324 项后端测试通过，真实公网 3WP6 性质分析和工程请求均完成验收；详情、科学结论边界和回滚点见[3WP6 性质分析发布记录](../releases/platform-20261013-3wp6-property.md)。以下各节为历史快照。

## 最新生产状态（2026-10-13 旧聊天模型清理后）

backend、worker 由 release `/opt/protein-ai-platform/releases/20261013-bff7d932-remove-retired-models` 管理；frontend 使用 `/opt/protein-ai-platform/releases/20261013-d4129de3-homepage-inline` 的首页横向品牌标题版本。模型接口只公布 GPT-6-sol、Claude-fable-5、DeepSeek-v4ro；GPT-5.4、GPT-5.5、GPT-5.6、GPT-5.6 sol 已从生产默认值、注册表和模型选择器移除。Claude 仍因上游通道权限未通过而标记不可用。backend、worker、frontend、Outline、ChromaDB 均 healthy，重启计数为 0；`/chat/agent`、`/platform/home`、`/kb` 均返回 HTTP 200。首页品牌行验收和前端回滚镜像见[首页品牌行发布记录](../releases/platform-20261013-homepage-inline.md)；模型回滚与验收见[旧聊天模型清理发布记录](../releases/platform-20261013-retired-models.md)。

## 最新生产状态（2026-10-12 报告与 ESMFold 超时信息修复后）

当前 release 为 `/opt/protein-ai-platform/releases/20261012-73a8f3b9-timeout-detail`；backend/worker 镜像 ID 为 `sha256:5224f005f4e1d9c65aaa508b2f5a78ff955b3464928e7d6642c9fa42b17e0d31`，均 healthy、重启 0 次。源码提交、真实报告复测、外部 ESMFold 超时限制与回滚点见[发布验收记录](../releases/platform-20261012-report-esmfold-timeout.md)。以下版本状态为历史快照。

## 最新生产状态（2026-10-12 3WP6 报告修复后）

当前 release 为 `/opt/protein-ai-platform/releases/20261012-5558e46f-3wp6`，backend/worker 镜像 ID 为 `sha256:ae6cd5f8f490f1d4cadc535400a37db68da572480068e41a507e1d648eaa4e2f`。源码和构建提交、真实 3WP6 公网前后两轮验收及回滚版本见 [3WP6 修复记录](../releases/platform-20261012-3wp6-repair.md)。以下双目标状态保留为上一生产版本的历史快照。

## 最新生产状态（2026-10-12 双目标修复后）

当前 release 为 `/opt/protein-ai-platform/releases/20261012-c11aedbf-multiobjective`，平台源码修复提交为 `4849919d`、`1b3895c2`、`c11aedbf`。backend/worker 镜像 ID 为 `sha256:f0d8871127ca04de6d0e5885acf9cb33f5434461f17ed8dde383e20e99f7fa2b`；前端未参与本次发布。精确 194 aa 双目标请求在切换后生成 6264 字报告，9/9 步有终态；上传 PDB 样本生成 8616 字报告，13/13 步有终态。详见 [双目标修复与线上验收](../releases/platform-20261012-dual-objective.md)。

以下内容保留为当日发布前的原始审计快照，不代表上述 release 的当前状态。

## 定义

本文件记录已经运行并验收的生产状态。它不是从本地 Git HEAD 可重建的源码发布声明。平台范围为后端、前端、编排、平台适配器和部署验收；模型训练与权重另见 [AI 模型研究基线](ai-model-research-20261010.md)。

## 发布前运行版本

| 项目 | 已核实状态 |
| --- | --- |
| ECS 当前 release | `/opt/protein-ai-platform/releases/20260928T075353Z-frontend-logo-centered/protein-ai-platform` |
| 本地核对时 Git HEAD | `8bd9b343d4c3fdf5004d274306934ec890f7fa64`，分支 `integrate-source-recovery-20261008` |
| 后端和 worker 镜像 | `protein-ai-backend:release-3a88c6e0-20260928`，镜像 ID `sha256:f8115afb0ebbb5936a325fe0808a0a8adf748221da820c3b70cde2ced03b9705` |
| 前端镜像 | `protein-ai-frontend:release-logo-centered-20260928`，镜像 ID `sha256:4938b3915816c289263170c5e89af4b21bccf361ed8ab41a75d82d879673d504` |
| 生产 Compose | `docker/docker-compose.aliyun-app.yml`，本地与线上 SHA-256 均为 `2bef908e1cda8d424424467f7fb84109fa553540568967bc3deba5893f87455a` |
| 主机运行依赖 | P2Rank、CAVER systemd 服务均为 `active`；服务源码和接线见 `docs/production_runtime_recovery_20261010.md` |

## 验收与边界

- 8 个容器健康，生产验收脚本 `PASS`，登记工具数 54；P2Rank 和 CAVER 能力接口为 `available`，主机服务为 `ready`。
- 真实浏览器登录后，Agent 工作区和 Outline Wiki 可打开；PDB 上传分析和 3D 结构显示成功。重复验收曾有一次 PDB 分析等待超过 45 秒，随后重试成功，耗时问题尚未定位。
- InterProScan 缺联系邮箱；ThermoMPNN、Rosetta、生产级 Km/Tm 仍未配置或验证通过；P2Rank/CAVER 商业许可门控仍阻断。能力详情以实时 `/api/capabilities` 为准。

## 源码一致性缺口

- 本地当前工作树的 226 个已跟踪 `backend/app` 文件与运行中的后端容器哈希一致，但其中仍有未提交修改。因此 Git HEAD 本身不能完整重建该后端状态。
- 本地 `frontend/src` 与线上 release 目录对比：5 个文件相同、36 个不同、27 个只在本地；本地 `frontend/dist` 与运行中的前端静态包也不同。线上页面来自预构建镜像，不能把 release 目录中的前端源码或本地构建结果直接当作该镜像的完整来源。
- 线上 release 没有 Git 元数据；原始 `release_manifest.json` 已不是当前运行快照。上述差异解除前，状态为“运行验收通过、源码可重建性未通过”。

## 下一次平台发布的最小条件

1. 将实际运行的后端和前端源码归入可追溯提交，分别核对构建输入、镜像 ID 和源文件哈希；不得以当前 HEAD 或旧 manifest 冒充完整基线。
2. 从干净的平台发布范围生成候选包，记录提交、镜像 ID、Compose 哈希和回滚位置；模型研究缓存、权重及未审查脚本不得混入。
3. 在保留现有 release 和持久数据的前提下，完成 Compose 校验、生产验收、登录态 Agent/Wiki/PDB 操作检查，再切换版本并记录结果。
