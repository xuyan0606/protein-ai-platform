# 20261103 当前版本保留点

用户明确要求保留当前版本，以便后续开发出现问题时回退。已保存独立的实际运行快照、本地候选和主工作区应用源码；保留点名称为 `20261103`，没有发布新代码、修改应用 VERSION 或切换生产服务。

| 保留对象 | 入口 |
| --- | --- |
| 服务器实际运行版本 | `/opt/protein-ai-platform/snapshots/20261103/CHECKPOINT.json` |
| 服务器回退说明 | `/opt/protein-ai-platform/snapshots/20261103/RESTORE.md` |
| 本机总入口 | `/Users/keweibo/output/platform-version-20261103/回退说明_20261103.md` |
| 本地候选 Git 标签 | `snapshot/platform-20261103-local` → `7015ffda4023619eaf6a2c82565dc0dfb5a76c9e` |
| 机器可读保留记录 | [platform-retained-version-20261103.json](platform-retained-version-20261103.json) |

服务器实际后端仍运行 `20261030-identity-evidence-tier-b728d4ca`。原生产总记录及 current 与实际运行不一致的事实保留，详见 [远端核验记录](../continuations/platform-release-preflight-20261103.md)。本次冻结运行状态，不把尚未发布的本地候选冒称生产版本，也没有把陈旧指针改写成新的生产验收事实。

## 已保留与核验

- 八个运行服务的原镜像、配置、挂载与网络信息；另外为 backend/worker/md-worker/frontend/ligand-worker 生成不暂停容器的镜像快照，保留实际可写层。合计 11 个不同镜像 ID，归档 `private/images-20261103.tar.gz` 为 1128307609 字节，SHA-256 `e6b019b6a5932b2b2cb74c7cd8a519a5090000f0beff184e49764ebb16594250`。
- 在无网络的临时容器中核对快照内容：backend、worker、md-worker 各 234 个文件、ligand-worker 230 个文件，以及 frontend 28 个实际静态文件全部匹配。临时容器已自行清理，没有替换生产容器。
- 各相关 release 源码和配置，以及 shared nginx/TLS/OIDC 配置。私有容器创建请求固定快照镜像 ID，不依赖可变镜像标签或旧回滚脚本。
- 新 PostgreSQL custom-format 备份 129156288 字节，SHA-256 `ec18a34e957439511e3faeda46a05996470c76ded2d27ddbc2f870f6040d31b8`，已校验并运行 `pg_restore --list`；未执行临时库恢复演练。
- 本地候选独立源码包 708 个文件与 Git 归档逐项哈希一致，增量 Git bundle 已验证；主工作区应用源码另存 597 个文件，保留未提交改动而不整体提交。
- 服务器只读校验通过：18 个工件、8 份恢复配置；快照前后八个运行容器 ID、镜像、重启次数不变，全部 healthy。

镜像完整归档保留在服务器；本机另存源码、配置、数据库及核验记录。镜像/配置/数据库快照包含私有信息，保留在受限目录，不能上传 Git 或公开分享。

## 后续开发和回退

后续修改先保留此版本；新增版本使用独立目录和标签。恢复源码优先创建新 worktree，避免抹掉后续工作。生产应用回退按本机/服务器回退说明核验任务、数据库兼容性、配置变化和挂载路径，再恢复固定镜像及运行配置；校验健康与关键业务后重新记录一致的生产事实。

默认只回退应用，保留回退时点的数据库、上传文件和其他用户数据。数据库恢复须独立确定范围，不能自动用 20261103 备份覆盖后来数据。本保留点不是 OSS、上传卷和向量库的完整灾难恢复备份，也不等于已经演练生产切换。
