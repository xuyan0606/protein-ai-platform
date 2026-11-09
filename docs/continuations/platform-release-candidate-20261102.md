# 2026-11-02 平台本地发布候选

> 后续结果：20261103 已整合并发布真实模型与应用，详见[发布验收记录](platform-thermostability-deployment-20261103.md)。下文为当时的历史检查/交付状态，其中“未部署”“尚未执行”不代表当前状态。

> 2026-11-03 远端核验更新：发现实际运行版本与本地基线、服务器版本记录及 current 不一致；候选遗漏线上改动，当前为 **no-go**。先按 [远端核验接续记录](platform-release-preflight-20261103.md) 完成生产改动整合，再重新准备正式发布。

## 候选范围

- 分支：`platform/routing-improvements-20261102`。
- 源码候选：`1e5e8d304dfc1b6fdf85472ba946ea6cddfef20d`。本文件之后的纯文档提交不改变已验证源码。
- 生产基线：`release/production-20261020`，源码 `0421817d37b63a4fb69587a69ee926cec9f7d168`。生产记录仍以 `docs/baselines/current-production.json` 为准，本次没有改变生产指针。
- 移植与复核提交保留在 `platform/post-production-20261020`（`26af45d4a`）；路由批次 `a039dc6ab` 和摘要修复 `1e5e8d304` 位于其上，不将已完成的独立路由批次再次按旧冲突决定撤回。

候选包含工具能力与研究证据边界、候选 WT 归属校验、模型准入、报告终态、活动对象隔离、续问与重分析确认。最新修复保留普通分析及未选主目标的多目标请求摘要，避免报告总结或补充序列时丢失原请求。平台变更与 AI 模型研究源码分别处理。

## 验证证据

| 检查 | 结果 | 范围与限制 |
| --- | --- | --- |
| 后端全量 | 1211 passed，0 failed、0 skipped | 前一轮已对当前源码完成，187.61 秒；本次仅复核提交差异，未重复运行 |
| 扩大定向回归 | 291 passed | 报告事实在模型故障时保留、序列补充、目标选择、对象隔离、确认执行与报告合同 |
| 前端 lint | 通过 | 本轮重新运行 `npm run lint` |
| 前端生产 build | 通过 | 本轮重新运行 `npm run build`；使用既有 node_modules，未重新安装依赖 |
| 上传策略 | 4 passed | 本轮运行 `node --test frontend/tests/upload-policy.test.ts` |
| 源码打包预览 | 通过 | `package_deploy_bundle.py --dry-run --exclude frontend/frontend`：706 个文件，17082236 字节；未生成部署压缩包 |
| 发布总控 | 仅计划 | `run_release_acceptance.py --plan-only --json`：11 项，3 项人工门、2 项跳过；不等同于验收执行通过 |
| 本地回滚资产检查 | blocked | 本地缺 `dist/packages` 发布包和 `backups` 数据库备份；不据此推断线上资产缺失 |

校验摘要与前端构建产物 SHA-256：本地被忽略目录 `output/release-candidate-20261102/verification-summary.json`。总控计划、打包预览和回滚检查原始输出在同目录。后端完整结果及失败修复过程见 [路由接续记录](platform-routing-20261102.md)。

## 发布执行顺序

1. 只读核验服务器 `production-version.json`、`current/DEPLOYMENT-RECORD.json`、实际镜像与当前链接，确认仍与生产基线一致；若已漂移，先重新确定发布差异。
2. 从已提交候选源码准备独立源码包，排除 `frontend/frontend` 副本、配置密钥、运行数据、依赖与模型权重；校验包内文件与源码哈希。当前仅完成打包预览。
3. 为发布准备正式版本清单，绑定源码、前端产物、报告 schema、适用模型工件及回滚镜像。现有 installer 默认要求 `RELEASE-MANIFEST.json`；本轮尚未验证正式清单，不启用 legacy 绕过。
4. 使用既有受控运行配置，在独立候选环境构建镜像并执行实际发布验收。检查登录、上传、报告总结、目标切换、更换结构、确认执行与下载；所有科学结果继续区分 completed、blocked、failed、submitted 和 research_only。
5. 发布前核验正式 HTTPS/配置门、备份校验与可用回滚资产；记录维护窗口和操作目标。当前计划未执行这些门，不把计划状态升级为可上线。
6. 候选验收与回滚准备完成后再进行生产切换；保留旧 release、镜像、配置和生产事实记录，在切换后重新验证健康、关键页面及版本一致性。

## 回滚准备

- 参考回退对象为生产记录中的当前 release：`20261020T232642Z-0421817d-gpt-recovery`；上线前须重新核验它仍是实际运行版本，不能把该记录当作新鲜线上检查。
- 保留原 current 目标、各服务不可变镜像 ID、配置来源与哈希。候选源码相对生产基线未修改 `backend/alembic` 或 `backend/app/models`，仍应在发布前核验远端数据库版本。
- 回退优先恢复上次已验收的应用镜像与 current/生产记录，并检查健康和关键流程。本轮不执行数据库恢复；如未来涉及迁移，另行评估数据库回退兼容性与恢复范围。
- `rollback_plan.py` 是通用演练计划，其中停服和数据库恢复步骤不作为本次应用回退的自动执行指令。异地恢复、外部存储恢复等人工门按实际目标单独核验。

当前结论：本地代码与前端检查通过，候选可进入部署环境验证；尚未完成正式发布验收、远端资产核验或生产切换。
