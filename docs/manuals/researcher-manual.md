# 研发用户手册

适用版本：0.1.0

## 主要入口

- 首页：`/home`
- 智能体对话：`/chat/agent`
- PDB/结构分析：`/pdb`
- 数据浏览：`/data`
- 知识库：`/kb` 或 `/wiki`
- Benchmark 案例：`/benchmarks`

## PDB 结构分析

`/pdb` 页面支持：

- 上传 PDB
- 查看 3D 结构
- 结构位点映射
- Foldseek 结构搜索
- annotation bundle
- MD Validation

结构 overlay 中不同来源含义：

- curated：人工整理或真实注释来源
- inferred：平台推断结果
- signal：信号肽区域
- domain：InterPro/Pfam 等结构域区域

## MD Validation

MD Validation 是真实 GROMACS 流程，不是随机模拟。

当前页面支持选择协议模板：

- `smoke_short`：快速验证链路，不适合发表级结论
- `engineering_short`：工程筛选级别
- `production_review`：候选复核级别

MD 报告中的 `Interpretation & Review` 会给出：

- verdict
- confidence
- evidence level
- quality gates
- warnings
- recommended next steps

短轨迹结果只能作为筛选和诊断依据，不能直接作为最终稳定性结论。

## 文件下载

MD 任务完成后可下载全部 artifacts。下载权限绑定任务所有者，其他用户不能下载你的任务文件。

## 常见问题

如果 Wiki 打不开：

- 先刷新当前页面
- 确认已登录平台
- 不要直接访问旧的 `state-mismatch` URL

如果 MD 任务失败：

- 查看错误信息
- 确认 PDB 文件格式有效
- 确认后端运行环境有 GROMACS
- 联系管理员查看任务审计和 worker 状态
