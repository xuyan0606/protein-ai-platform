# 平台源码版本管理修复（20261109）

当前运行 release 是 `20261107-chat-timeout-197bf67c1`，原始应用提交为
`197bf67c137b4059c88455f81b7e4956e1ef1e8d`。本次修复仅补齐 Git 保护、
远端源码归档和版本入口，不重新部署应用，不修复外部检索超时。

## 正式源码入口

- Git 远端：`git@github.com:xuyan0606/protein-ai-platform.git`。
- 生产源码分支：`release/production-20261107`。
- 固定发布标签：`production/20261107-197bf67c1`；创建后禁止移动。
- 原始平台源码快照提交：`e9e9ba0d90241eca345faec9b732068906b79cc6`。
- 运行事实：`docs/baselines/current-production.json`。
- 逐文件来源和排除清单：`production-source-manifest-20261107.json`。

原运行提交曾混入模型缓存、虚拟环境、大文件、数据库备份和私有环境备份，
其完整历史不适合推送到源码远端。本仓库建立了新的干净 Git 历史，保留原始
提交号与逐文件 SHA-256 对应关系。分支和发布标签指向含管理修复的提交，
不是原运行提交本身；不得声称两个 Git 提交号相同。

导出范围为平台应用、前后端测试、部署模板和相关说明，共 728 个原始文件；
管理修复增加了校验脚本、测试和基线记录。原始源码中的 AGENTS.md、.gitignore
和当前生产记录作为明确的元数据更新例外，其旧内容在源码快照提交中保留。
AI 研究数据和权重、运行包、数据库、私有环境、用户输入 PDB 和测试截图不在
此源码归档范围内。独立模型服务的外部权重和运行配置仍按原流程管理。

## 修改与校验

```sh
git clone --branch release/production-20261107 \
  git@github.com:xuyan0606/protein-ai-platform.git protein-ai-source
cd protein-ai-source
python3 scripts/verify_production_source.py --check-refs --require-clean
git switch -c fix/<本次问题>
```

校验会拒绝错误的生产提交记录、缺失文件、源码哈希不匹配、私有文件被跟踪、
生产分支与标签不一致，以及要求干净时的未提交内容。开发完成后原始哈希检查
因应用修改而失败是正常现象；应审查差异、运行相关测试，并在实际发布及验收
后建立下一份运行清单。不能为了通过检查而直接重写旧清单或移动历史标签。

## 服务器版本入口

服务器以 `/opt/protein-ai-platform/production-version.json`、实际容器镜像、
挂载目录及源码哈希为事实依据。旧 `current` 指针仍与运行版本不符，保留给
历史配置使用；禁止从它复制源码、默认重建容器或执行旧回退脚本。
本次新增的 Git 归档记录不赋予旧 `current` 当前版本的含义。

修复前只读核对八个运行容器均 healthy、重启次数为零。四个后端服务的每个
264 个 app/alembic 文件均一致，且与原运行提交及干净源码归档一致。这是源码
一致性核验，不是重新运行历史应用验收或科学工具验收。

## 原始历史与恢复

原仓库新增私有保护引用：

- 分支：`archive/production-20261107-original`。
- 标签：`archive/production-20261107-197bf67c1`。
- 增量包：`production-20261107-original.incremental.bundle`。

增量包依赖 `7015ffda4023619eaf6a2c82565dc0dfb5a76c9e` 原始快照提交，
不是可以独立克隆的完整历史。使用原仓库或具备该前置提交的恢复库验证后导入；
原有 20261103 快照和标签保持不动。GitHub 的干净源码归档可独立克隆恢复平台
源码，不依赖这个私有增量包，但不包含原始历史中的模型、数据库或私有配置。

应用运行、数据库、用户上传和模型服务不因本次管理修复而切换或恢复。
