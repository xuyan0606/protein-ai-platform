# GPT 中转恢复（2026-10-21 北京时间）

已按用户明确要求复用本机 Codex 当前配置的 API key，恢复 GPT-6-sol；DeepSeek/deepseek-flash 保留为备用。凭据只注入服务器新 release 的私有环境文件，未写入源码、Git 或日志。

本次只变更模型配置，源码仍为 `0421817d37b63a4fb69587a69ee926cec9f7d168`，前后端镜像沿用上一已验收版本，前端布局保持一致。

- Release：`20261020T232642Z-0421817d-gpt-recovery`。
- 源码 tree：`743f5f01e8317cb1e001e5f7a969c84029d29340`。
- 后端 / worker / md-worker：`sha256:d8fe0b6398d3565151946a77169b3f4391bf8ccc4b43bc6e226c1e371a1f2b77`。
- 前端（源码 0cc380a4）：`sha256:bf4fa2cb7f94bac3b43419033007d75bffb33dd5f2c03c3c7d869cdb09ea1941`。
- key 来源：用户授权的当前 Codex 客户端 provider 配置；只记录来源，不记录凭据。
- 原失效 key 和上一个 release 配置完整保留，必要时可用当前 release 的 `rollback-previous.py --execute-approved-rollback` 回退。

平台旧默认 GPT-5.5 原生模型未列入服务目录，本次将其置空避免错误选择，当前默认 GPT-6-sol 已通过真实请求验证。页面保留用户显式选择；既有会话如果仍选择 DeepSeek，可从模型菜单选择 GPT-6-sol。

真实接口探测与服务器隔离网关调用均收到 `gpt-6-sol` 响应，2+3 精确回答为 5。科学工具的 blocked/degraded/background 状态保持原样，不把报告生成等同所有科学任务完成。

本次沿用既有 HTTP 环境授权例外；正式 registry RepoDigest 与受信任 HTTPS 尚未补齐。既有 1107 项后端 / 114 项服务器回归对应相同源码上一 release，本次不冒充重新运行这些测试。

线上 12 项真实浏览器检查通过，控制台/页面错误与 HTTP 5xx 为零；212 个后端源码文件、11 个前端资源哈希核对一致，8 个容器 healthy、零重启。临时账号 389/390 已停用，两个测试会话和上传已删除，测试 BLAST 已取消。

Git 配置发布标签：`production/20261020T232642Z-0421817d-gpt-config`。首轮浏览器脚本错误要求默认选择必须写入 localStorage，保留该失败记录；修正断言后完整重跑通过，未修改产品代码。

---

下列为先前发布历史，旧“GPT 中转禁用”描述已被本次恢复替代。

# 2026-10-20 先前发布历史

当前生产源码为 `0421817d37b63a4fb69587a69ee926cec9f7d168`，release `20261020T091507Z-0421817d-model-recovery`。后端模型服务已恢复；前端继续使用 0cc380a4 已验收构建，源码祖先关系明确，11 个静态文件哈希一致。

机器可读事实见 [current-production.json](current-production.json)，对应服务器 `/opt/protein-ai-platform/production-version.json` 与 `current/DEPLOYMENT-RECORD.json`。生产分支 `release/production-20261020` 已快进至 0421817d，标签为 `production/20261020T091507Z-0421817d`；文档分支提交不代表运行代码。

| 对象 | 当前值 |
| --- | --- |
| source tree | `743f5f01e8317cb1e001e5f7a969c84029d29340` |
| current | `/opt/protein-ai-platform/releases/20261020T091507Z-0421817d-model-recovery/protein-ai-platform` |
| backend / worker / md-worker | `sha256:d8fe0b6398d3565151946a77169b3f4391bf8ccc4b43bc6e226c1e371a1f2b77` |
| frontend（源码 0cc380a4） | `sha256:bf4fa2cb7f94bac3b43419033007d75bffb33dd5f2c03c3c7d869cdb09ea1941` |
| 当前模型 | DeepSeek 直连，原生模型 `deepseek-flash`，页面名称 DeepSeek |
| 上一 release / 回滚目标 | `20261020T083442Z-0cc380a4-hotfix`，保留镜像、配置和数据 |

## 模型恢复根因与范围

中转密钥真实请求返回 401；平台现有配置内有有效 DeepSeek 密钥，之前没有注入线上。只向新 release 的服务器私有配置注入这一个已验证密钥和模型参数；不把密钥纳入 Git、源码包或验收日志。原 GPT 中转被禁用，未将 DeepSeek 冒称为 GPT。旧 v4ro 原生模型置空，并让可用性策略拒绝空模型。

仅更新 backend、worker、md-worker；部署前检查 worker 空闲，运行配置只允许八个模型变量改变。没有数据迁移，其他五个容器未重建。沿用已批准的既有 HTTP 环境；正式 registry / HTTPS 门禁仍未满足。

## 本次验收

- 本地后端全量 **1107** 项通过；服务器 Python 3.12 隔离回归 **114** 项通过，并完成真实 1TCA 几何检查。
- 候选容器经过平台 LiteLLM 网关真实调用 `deepseek-flash`，2+3 回复为 `5`。
- 线上 **12** 项浏览器检查通过：真实登录、首页/侧栏/移动端布局、自动选择 DeepSeek、真实聊天、1TCA 上传/预分析、深度策略确认/执行、报告显示和 HTML 导出。控制台、页面错误和 HTTP 5xx 均为零。
- 212 个运行后端源码文件与当前 release 内容完全一致；11 个前端静态文件哈希保持一致；八个容器 healthy、零重启。
- 测试账号 388 的两个会话及上传已删除；等待中的测试 BLAST 已取消；账号已停用。用户原 admin 数据未改动。
- 会话恢复/令牌刷新/用户切换/过期清理由同一前端镜像的上一 release 验收提供，明确标注证据来源为 0cc380a4，未冒充本次重跑。

## 仍需保留的科学边界

报告可生成和导出不等于所有科学工具完成。该轮 Foldseek 仍未配置而降级、位点特征结果为 blocked、BLAST 为后台提交状态；已逐项保留原始状态，不能声称全部科学分析完成。几何工具不能证明催化、结合能、突变收益；未执行 MD/docking。

当前 release 的 `rollback-previous.py` 恢复上一个 release 的三个后端服务、配置、current 和生产记录；只准备且语法检查通过，未执行回滚。源码有独立增量 Git bundle，旧 release / 镜像及历史标签保留。本地 Git 尚未推送远端，主工作区其他未审查改动未上线。

以下保留较早发布历史；其中“模型 401 未解决”仅描述 08:34 UTC 时状态，已由本次模型恢复替代。

---

# 08:34 UTC 发布历史（0cc380a4）

该次生产版本为 `0cc380a435b13c9a0599937525127c28ce13365d`，release `20261020T083442Z-0cc380a4-hotfix`，已完成线上验收。它是明确批准的现有 HTTP 环境临时修复发布，尚未满足正式注册表摘要与受信任 HTTPS 门禁。

机器可读事实见 [current-production.json](current-production.json)。服务器事实入口为 `/opt/protein-ai-platform/production-version.json` 和 `/opt/protein-ai-platform/current/DEPLOYMENT-RECORD.json`。本地其他分支 HEAD、旧发布文档和可变镜像标签不能替代这三个入口。

## 已核实版本

| 对象 | 值 |
| --- | --- |
| 源码提交 | `0cc380a435b13c9a0599937525127c28ce13365d` |
| 源码 tree | `63ab438b7a5f859ce23f01bb5f981d4174de1e4e` |
| Git 生产分支 | `release/production-20261020`，只指向本次已运行的源码提交 |
| Git 发布标签 | `production/20261020T083442Z-0cc380a4` |
| current | `/opt/protein-ai-platform/releases/20261020T083442Z-0cc380a4-hotfix/protein-ai-platform` |
| 前端镜像 | `sha256:bf4fa2cb7f94bac3b43419033007d75bffb33dd5f2c03c3c7d869cdb09ea1941` |
| 后端 / worker / md-worker 镜像 | `sha256:4608795ca61dac439d041661b621caa20462f1f2744f4d453f2f38db7e8fb2bd` |
| 前端 JS / CSS | `index-ClBLIViq.js` / `index-Dotzi4zd.css` |
| JS SHA-256 | `a18111ee48d3c091c1ebde71644df4459170ef4de023820ddeb38ad6fc923938` |
| CSS SHA-256 | `2d887522ce1fdf90094a3a6b277ae85085e0bd3bc97a472e53cbe8df2b9d3a68` |
| Compose 镜像锁 | 当前 release 根目录 `COMPOSE-IMAGES.lock.yml`，固定八个运行服务的真实 image ID |
| 旧 release | `20261020T014104Z-ba3e56c7`，完整保留 |

本次只重建 frontend、backend、worker、md-worker 四个容器；没有数据库迁移、持久卷清理、模型配置变更或其他服务重启。新旧 Compose 展开后的环境与关键运行设置在内存中比较一致，未输出凭据。

## 修复与验收

恢复首页与侧栏的小 Logo、标题同行、移除 Workspace，并恢复 `/platform/home` 入口。回退根因为跨分支整合漏入历史界面修复，不能归因于浏览器缓存；也不能断言它首次发生于本次发布前一天。

对 PDB 附件剥离元数据后再识别用户目标，避免 `alpha` 误触发 pH、`engineered: YES` 误触发改造意图；将三个基础几何证据工具纳入相应策略白名单，保留未知工具和科学证据门控。包含此前模型永久认证错误降级、BLAST 状态审计同步及报告章节去重修复。

- 发布前后端全量 1104 项通过；服务器 Python 3.12 隔离环境 91 项通过。
- 最终前端按锁文件独立 npm ci 后构建；该构建 9 项布局/路由检查及模拟 API 的 7 项报告流程检查通过。
- 发布后真实登录、桌面首页与侧栏、移动端、真实 1TCA 上传与预分析、深度策略确认与执行、报告显示、HTML 导出共 10 项通过，PDB 浏览器控制台/页面错误与 HTTP 5xx 均为零。
- 会话恢复、真实令牌刷新、用户切换隔离和过期会话清理通过。换页时有一条策略记忆控制台错误；同一请求记录为 `net::ERR_ABORTED`，归类为导航取消，保留原始证据，没有将所有 fetch 失败一概忽略。
- 公网 HTTP smoke 通过；11 个生产静态文件哈希与锁文件构建逐一一致。八个运行容器全部 healthy，重启次数为零。
- QA 用户 383–387 的测试会话和上传已清理；两个仍等待的测试 BLAST 任务取消，五个临时账号停用。原 admin 上传和会话未改动。

验收脚本首轮提前等待尚未触发的上传；第二轮仍按工程报告标题匹配，纯分析实际生成“蛋白性质分析报告”。两处均修正后重跑，最终完整流程通过；保留失败日志，不作为生产代码故障或成功证据。

## 已知限制

模型上游仍返回 401 Invalid token，未恢复模型回答；需要用户提供有效配置文件路径或安全密钥引用。当前报告来自真实工具输出的降级整合。一次 1TCA 执行完成 7 项、受阻 3 项、后台等待 1 项；不能把所有工具或后台 BLAST 写成已完成。几何证据不能证明结合能、催化机制、突变增益或实验酶活，未执行 MD 或 docking。

注册表 RepoDigest 和受信任 HTTPS 仍缺失。本次固定 image ID 记录不是伪造的正式 RELEASE-MANIFEST，不得将临时例外泛化为以后发布许可。所有镜像和旧标签保留；后续操作必须读取当前锁文件，不能直接用 `:aliyun` 默认值重启回旧版。

## 回滚与后续发布

当前 release 内 `rollback-previous.py` 已通过语法检查，需明确 `--execute-approved-rollback` 才执行；恢复旧四个服务镜像并核验健康后，再恢复 current 指针和生产版本记录。本轮未执行生产回滚演练。

旧镜像归档位于 `/opt/protein-ai-platform/candidates/0cc380a4-frontend-20261020/rollback/images.tar.gz`，SHA-256 `626c96f18fce142cf0ed8bfa66926b9ace3c7e0dd7de83d1cb8fc8d533a0802b`。原配置仍保留于原 release，仅记录路径与哈希，不在仓库保存凭据。

后续平台修复从此生产源码分支建立独立分支，合并前逐项核对历史功能；模型研究与主工作区未提交改动继续保留，不能整体覆盖上线。每次发布必须同时更新机器可读当前版本与带日期基线，并在切换后核对实际镜像、静态资源、真实登录首页/侧栏及 PDB 报告流程。

本次发布源码和版本标签保存在本地 Git，共三个修复提交另有已验证的增量 Git bundle（依赖 ba3e56c7）及服务器源码包备份；尚未推送远端，也未合并主工作区的其他未审查差异。
