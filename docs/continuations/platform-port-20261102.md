# 2026-11-02 平台生产基线移植接续

## 工作位置与版本

- 持久 worktree：`/Users/keweibo/output/platform-prod-base-20261102`。
- 候选分支：`platform/post-production-20261020`；起点为生产源码 `0421817d37b63a4fb69587a69ee926cec9f7d168`。
- 原 `/private/tmp/platform-prod-base-20261102` 已不存在；从 Git 保留的三阶段冲突索引恢复现场，使用 `git worktree repair` 关联持久目录。
- 原工作区仍在 `integrate-source-recovery-20261008`；本批不改写它的源码，也不提交其 AI 研究改动。
- 当前生产分支、运行镜像、发布目录和线上配置未切换。生产记录仍描述 2026-10-20 已验收发布，本次没有重新执行线上验收。

## 已采用的决定

用户此前确认：逐文件移植到生产分支；生产路由优先；补齐 11 个工具模块；Compose 只增加服务地址。

`enzyme_workflow_runtime.py` 完整保留生产版。`agent_graph.py` 的 `_message_starts_new_task`、`_build_context_for_message`、报告质量反馈识别和续问 payload 判断均与生产版 AST 一致；不引入 WIP 的复数附件判定与活动历史截断路由。报告质量复核仍保持生产处理顺序。生产附件元数据隔离、模型故障回复及结构工具白名单由生产回归守门。

## 本批实现

1. 补齐核心结果状态、执行上下文、工作流定义与模型工件接口；登记 11 个工具模块，保留生产按模块容错加载器。新增工具全部有能力边界与最低工件说明。研究推荐保持 `research_only`，不得作为已验证收益。
2. 使用生产的策略确认及执行链路，接入有 WT 校验的候选构建。没有适用候选时跳过构建，保持正式科学门控；不绕过生产编号依赖。
3. 将流式终态的任务合同与执行结果带入报告；保留 blocked/failed/submitted 与研究输出的证据边界。报告预览限定当前用户、项目与最新用户轮次，不复用旧轮次结果。
4. 修复移植残留：上下文中未定义的 `latest_sequence/current_object_names` 随生产函数恢复而移除；报告段落中的 `requests_activity` 改为调用现有目标识别函数。
5. 加入独立上传策略函数及四项测试；这是策略函数的保留，未将其冒称为新增页面上传流程。
6. 补充本地产物忽略规则，保留 `frontend/frontend/` 副本原位。补录生产基线文档；正确的既有文档提交为 `0d752310`。

## 验证

最终后端全量：**1181 passed in 155.09s**，无失败或跳过。命令：在 backend 下使用原工作区 backend/.venv/bin/python 运行 `-m pytest tests -q --tb=short -p no:cacheprovider --show-capture=no`，通过 OIDC_PRIVATE_KEY_PATH/OIDC_PUBLIC_KEY_PATH 指向上述测试密钥。

前端 `npm run lint` 与 `npm run build` 均通过；使用与生产锁文件相同的既有 node_modules。上传策略 `node --test frontend/tests/upload-policy.test.ts`：4/4 通过。

定向回归覆盖真实确认执行路径的模拟工具、候选 WT 校验、研究状态、报告发布权限/轮次、模型工件缺失/哈希/审批门控与能力审计。所有科学工具执行使用测试替身或受控缺失状态，未执行真实模型推断、MD 或外部发布。

首轮 1135 通过、56 失败，保留为失败记录：包含恢复 worktree 缺少真实测试资源，以及整份 WIP 测试依赖生产未具备接口的问题。恢复对应生产提交中的资源后，仅移植属于本批增量的测试；原生产测试完整保留。随着工具增加，两个固定工具数量断言改为必备工具集合及全量能力覆盖检查。

测试 OIDC 使用本地生成的临时密钥，位于被忽略的 `output/test-keys/`；不提交真实或临时密钥。

## 延后且保留的改动

- WIP 新路由、当前对象重分析、目标切换、历史序列继承及相应测试，需独立批次处理。
- 另一条分支中已存在但生产没有的历史能力、历史测试及验收脚本，不因文件名相同而整体覆盖生产版本。
- `docker/.env.research.example` 与 `scripts/run_delivery_acceptance.py` 的原 WIP 增量、2026-10-12 历史发布记录追加，保留在原工作区；其完整旧接口不属于本批生产路由移植。
- AI 研究源码、缓存清理、34 个本地删除的缓存文件、ESM 分支选择、历史重写和发布均未执行。

原工作区平台 WIP 补丁与逐文件 SHA-256 清单保存在 `output/recovery/`；该目录被忽略。新源码的入库清单见同目录 `commit-groups.json`。不要把这个候选分支称为线上新版本。
