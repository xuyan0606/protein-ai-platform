# 20261103 热稳定性真实模型与应用发布

应用已发布并完成功能验收，状态为 `accepted_with_recorded_exceptions`。源码提交为 `7c46ab6c3a4e7d90603bd5e45424096c98b09228`，版本目录为 `/opt/protein-ai-platform/releases/20261103-thermostability-7c46ab6c3/protein-ai-platform`。机器记录见 [当前生产记录](../baselines/current-production.json)。后续文档提交不改变上述已发布源码。

## 应用与数据

- backend、worker、md-worker、frontend、ligand-worker 已逐个替换，八个线上容器均 healthy，重启数 0。nginx、Chroma、Outline 保留原容器；nginx 仅检查配置并 reload，刷新上游地址。
- 使用 20261103 冻结镜像，保留实际运行依赖、环境、启动方式、卷和网络，新增只读源码挂载及三项模型服务的 URL、令牌和 CPU 超时配置。四个后端服务各 257 个源码/资源/迁移文件逐项 SHA-256 与发布包一致；11 个前端运行文件通过 HTTP 逐项核对。
- 包内 280 个文件已核验，源码包 SHA-256 为 `875b2b53e7a080ee2134a50e34c5b52b9ca7a52bf3c38d8963b2b7f67e48604d`。32 个模型、迁移和数据库入口文件与原运行版本一致；网络隔离的临时容器编译 223 个 Python 文件，并实际导入、注册四个新增工具。
- 切换前，三个 worker 的 active/reserved/scheduled 均为 0，default/celery/md_cpu/ligand_cpu 队列均为空。
- 切换前新备份在 `/opt/protein-ai-platform/backups/thermostability-7c46ab6c3-precutover/`：122177636 字节，SHA-256 `7e97924a9f7363ac7267fe9272ef904c4ebacabbceb2045e3ca1b91deb5b2f71`。已在 `--network none` 的临时 PostgreSQL 恢复并核对 51 张表、迁移号 `20260917_0004`，随后清理临时数据库。生产库未恢复、未升级迁移、未 stamp；切换后只读复核仍为相同表数及迁移号。

服务器 `production-version.json` 已更新为本次实际验收结果，旧记录另存于私有发布准备目录。`current` 仍是历史陈旧链接，未改动；不能据其复制配置或推断运行源码。原 Compose 标签保留，因此实际运行事实应联合检查容器 ID、只读挂载、源码哈希和本次记录。

## 三项真实服务

模型服务以 `protein-models` 用户监听 Docker 网关 `172.18.0.1:4270`，要求 Bearer 鉴权，不直接监听公网。未经鉴权返回 401，现有后端容器经鉴权可访问。单个科学任务、CPU 200%、内存 12GB；任务工作目录和缓存独立可写，源码目录只读。忙碌时明确返回 429。

| 工具 | 固定来源与实际验证 | 边界 |
| --- | --- | --- |
| DDGun | 官方 `bcf112c616bcd4eb9b18f193ec08cc704eb761b5`；完整 `uniprot20_2016_02`；真实 HHblits/HSSP 序列计算与 DSSP/3D 计算均通过 | 原始 unfolding ΔΔG，正值表示增稳；不是 Tm 或实验命中率 |
| ColabFold | 官方源码 `84c27d9cc500489fd9b97545d2325b9d00f251d5`，实际导入的 19 个源码文件哈希一致；官方 AF2 参数 | 公开短序列、本地 MSA、CPU 单模型、1 recycle；未验证长序列或 GPU 性能 |
| EVcouplings | 官方 `14c83457c6cfca8156aabe0615067447a2169791`、PLMC `18c9e55e3bd2f14f4968be19a807b401996c929a`；实际导入 59 个源码文件哈希一致；3616 条公开 MSA 真实拟合，独立重算 Neff 约 1568、覆盖度约 0.962 | 共进化统计证据，不是突变 ΔΔG、Tm 或活性 |

三套源码均另与官方固定提交的Git对象逐文件核对，既无内容不匹配，也无多余Python源码。ColabFold安装目录曾混入两个不同版本的文件及六个未使用的RGI文件，已恢复/隔离并重新实算，最终回执与当前源码绑定。

三项均已通过“原后端容器 → 私有 HTTP 服务 → 官方算法 → 平台严格适配器”验证；`runs/readiness/` 的回执只在实算和严格校验成功后生成。完整 DDGun 压缩数据库 11902954502 字节，归档 SHA-256 为 `0cf2241e518bb06769e63dc611494a222af4062e27f938bc7d60c2ee0f8cbb66`。安装测试用自序列数据库未用于生产。

本次还完成了发布后“用户登录 API → DDGun 异步提交 → Celery → 真实 HTTP 服务 → 严格适配器 → 所属用户轮询结果”的完整链路；跨用户读取任务被拒绝。主候选流程另实测了缺目标/身份材料时返回 needs_input/blocked、无候选，开启预测器不能绕过门控。

## 业务验收与清理

旧 Bearer、Cookie、刷新令牌及重新登录均通过；原上传文件下载哈希、原会话及原后台任务可用。第二用户无法读取其文件、会话、项目报告和任务。

切换前复现的旧报告 HTTP 500 为 AsyncSession 懒加载 `MissingGreenlet`；候选已有 eager loading 修复，同一份切换前创建的会话现可生成报告。报告验收使用明确标记的工程夹具，不包含虚构科学结果，也未调用 LLM 生成新科学结论。

Playwright 实际打开公网登录页，并用旧验收会话 Cookie 打开 `/platform/home`；页面正常呈现，检查时控制台错误、警告均为 0。本项不声称完成浏览器登录表单或所有前端交互的全面回归。

4 个临时验收账号已禁用，2 份上传、2 个会话、2 个项目及其 2 个临时 Wiki 集合已清理；任务审计保留。真实用户数据未修改。

本地后端完整日志为 1765 passed；本次新运行器、HTTP 服务和发布保护测试为 30 passed。完整证据保存在本工作树忽略目录 `output/thermostability-validation-20261103/`；服务器私有切换/回执目录分别为 `candidates/thermostability-7c46ab6c3-private/` 和 `candidates/thermostability-7c46ab6c3-acceptance/`。私有会话、创建请求及令牌不进入 Git。

## 明确保留的例外与回退

沿用原 HTTP/IP 自签 HTTPS 入口；可信域名证书门尚未通过。冻结镜像只有真实本地 image ID，尚无 registry RepoDigest；本次独立记录来源和哈希，没有伪造正式 `RELEASE-MANIFEST.json` 或宣称通用发布总控所有门通过。

20261103 快照与五个停止的原应用容器均保留。需要应用回退时运行：

```sh
python3.11 /opt/protein-ai-platform/releases/20261103-thermostability-7c46ab6c3/protein-ai-platform/scripts/prepare_thermostability_release.py \
  --rollback-runtime /opt/protein-ai-platform/candidates/thermostability-7c46ab6c3-private
```

该命令保留最新数据库与全部持久卷。回退后须重新验证容器健康、业务并更新生产事实记录。本次未执行生产回退演练，也未完成企业目标酶效果验证、湿实验、真实 GPU 或长 MD。
