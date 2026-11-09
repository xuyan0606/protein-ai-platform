# 486 aa 热稳定性主聊天链修复与验收

状态：已发布并完成验收，生产源码`095449f78be899910a14b32e1234c58987456814`，2026-11-03 16:32:29（北京时间）完成归档；`accepted_with_recorded_exceptions`。后端全量1856项通过（173.01秒），真实486 aa隔离重放、公网确认执行及浏览器报告刷新通过。

根因与原真实执行见 [诊断记录](platform-486-thermal-routing-diagnosis-20261103.md)。本轮覆盖目标语义、实验条件、工具编排、参数桥接、后台调度及报告显示，不靠放松科学门控解决。

独立复测更新（17:04）：发现聊天附件摘要等待和OSS凭据回退问题，结论`passed_with_findings`，详见[发布后独立实测](platform-thermal-independent-test-20261103.md)。以下发布验收保留其原时间与范围。

## 最终行为

- 剩余/残余酶活、残余/剩余活性、residual/remaining activity在热处理语境下属于热稳定性终点。真正独立的增活目标仍保留，多目标无主次时继续澄清。FASTA和附件元数据不成为目标；测定pH数值不自动升级为pH改造。
- 原案保留95℃、5min、当前30%、目标≥60%；不会把60%填成未加热酶活保持下限。秒/小时归一化、温度/时长冲突、测活温度与热处理温度分开处理。底物、方法、pH、缓冲液及辅因子缺少时保持缺少，不编造。
- 三档热稳定性工程计划均接入thermostability_candidate_workflow。同源检索先于身份模块；不执行原案例无关的启发式kcat、通用优先打分和饱和扫描。已有结构复用，MSA默认本地，无合格MSA不强制共进化。
- 同一序列、上传对象、链、模型、内容哈希及参考结构绑定到身份/目标/总工具；传递已验证作者编号映射。普通PDB的独立增活请求也进入身份收集，明确位点请求仍保留身份/目标科学门控。
- 总工具先本地做输入/身份门控。需要补充或科学阻断时，当轮生成具体报告；符合条件的长计算继续后台执行。
- 二硫键/盐桥保留一个正式注册入口，兼容protein_pdb及旧阈值接口与几何结果，旧模块保留直接调用API。不同导入顺序不再覆盖上传对象合同，His接触与盐桥分开，仍为几何证据。

## 验证

先写回归并观察目标混淆、数值丢失、旧流程、注册覆盖等预期失败，再实施修复。定向353项通过；最后后端全量1853项通过（114.67秒）。新增46项与普通/理论PDB身份矩阵共覆盖64个新场景。旧热稳定性规划测试改为验证新总工具，未删除身份/编号/目标门控断言。另扫描所有工具静态注册名称，未发现其他重复正式注册。

真实输入仅在服务器私有验证区复制；原序列不写入Git文档。原会话1030、消息4208/4209/4211与旧报告4159已记录哈希，后续验收复核；不重写历史报告，不取消原BLAST。

## 发布接续

用户已授权测试通过后上线，本次发布已完成源码冻结、备份隔离恢复、容器切换、真实登录上传/签名确认执行/报告刷新和清理。快照20261103和旧容器保留；current陈旧，不从它重建；生产库未迁移、未恢复。

真实隔离重放再发现：附件的状态字段与“禁止联网”组合误触发external_connectivity_check。已增加三条回归，净化状态检测并使权限/限制服从工程任务；九场景真实486 aa重放与真实本地工具执行、两种注册导入顺序通过。原文件哈希327eacf9cab8703f13bd7dc72e052278a509ba4fe6ce594245565425db7f2454；缺口报告保留95℃/5min/30%/≥60%，没有把实验条件全部列为缺失。

## 发布与验收事实

- 冻结发布包783文件逐项校验，SHA-256 `f22a7053cab46ecd3b9ff152e8b8b6b9935a23bb25267a65060cb251de60f7a9`；相对上一生产版本修改9个应用文件，不涉及数据库模型/迁移或前端源码。最终后端全量1856 passed/173.01秒，联网路由定向231 passed/14.42秒；上文1853项为补充修复前的历史结果。
- 新数据库备份122396655 bytes，SHA-256 `c2526481b50a09d86b873986820693f32fdb99eae1ab735d84437e013109869f`；归档目录检查和断网临时PostgreSQL恢复通过，51张表、迁移号`20260917_0004`一致。
- 16:14:03（北京时间）开始替换五个应用容器，原镜像、环境、启动命令、资源配置和持久挂载保留。最终八容器healthy、重启0，四个后端服务各259个源码文件哈希与发布源一致，11个前端静态文件HTTP哈希一致，模型HTTP服务健康。
- 两个临时账号使用原486 aa结构副本完成真实注册/登录、上传解析、文件哈希与跨用户403检查。会话Bearer、cookie、refresh和完整AI摘要API通过。
- 真实签名策略为`structure_search_foldseek → residue_mapping_sifts → disulfide_saltbridge_scan → predict_properties → blast_search → enzyme_identity_profile → enzyme_objective_module_plan → build_site_structure_function_features → thermostability_candidate_workflow`。结构、编号、二硫键/盐桥、性质、身份和特征工具完成，BLAST真实提交；目标模块和热稳定性总工具按科学条件返回blocked，无failed工具。
- 生成3426 bytes持久化报告，保留95℃、5 min、当前30%、目标≥60%。没有执行无关kcat、通用优先打分或饱和扫描。最终合同`BLOCKED`：身份和完整测定条件尚未确认，不能据此给出有效突变或宣称酶活收益。
- fast/standard联网、deep禁止联网/禁BLAST四种公网策略通过；受限制计划不含BLAST，跨用户检查点404、旧签名409且未改变原签名。本项是策略和确认权限验收；断网工具执行另由隔离重放覆盖。
- 真实浏览器表单登录、刚生成报告显示、刷新保留、390×844宽度检查通过；浏览器错误和HTTP错误均0，文档宽度390。浏览器验收对象为实际API执行产生的报告，未将其扩大为本轮浏览器上传表单验收。
- 两临时账号禁用、五会话及一上传删除、一测试BLAST取消。独立数据库/存储读回确认清理完成，旧Bearer均403；原消息4159/4208/4209/4211与原结构哈希、原任务RID `EJM32AS6016`保留。原BLAST仍为degraded，未恢复或重新提交原序列。服务器和本机临时登录凭据已删除。

## 证据与回退

应用目录：`/opt/protein-ai-platform/releases/20261103-thermal-095449f78/protein-ai-platform`。服务器生产记录及本地`docs/baselines/current-production.json`同步实际容器ID、挂载、源码与验收回执。

本地脱敏证据为`output/thermal-release-095449f78/`，浏览器快照为`output/playwright/thermal-routing-486/`；服务端验收为`/opt/protein-ai-platform/candidates/thermal-095449f78-acceptance/`，准备记录为`/opt/protein-ai-platform/candidates/thermal-095449f78-private/`，备份及恢复凭据为`/opt/protein-ai-platform/backups/thermal-095449f78-precutover/`。

需要回退时使用以下入口，默认仅回退应用并保留最新用户数据；本轮未执行生产回退演练：

```sh
python3.11 /opt/protein-ai-platform/releases/20261103-thermal-095449f78/protein-ai-platform/scripts/prepare_thermostability_release.py \
  --rollback-runtime /opt/protein-ai-platform/candidates/thermal-095449f78-private
```

保留20261103快照及各历史回退容器。可信TLS和registry RepoDigest仍为既有例外，未将本次功能验收扩大为这些门禁已通过。
