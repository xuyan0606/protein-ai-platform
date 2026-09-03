# P0 今日收口操作清单

日期：2026-08-20

结论：本地 P0 收口包已建立；P0 解锁、训练、模型声明、客户交付、release 和生产执行仍关闭。

执行顺序：
1. 先完成 P0-01/P0-02 编号与结构链人工审核。
2. 再完成 P0-03/P0-04 反馈来源审核、QC 和正式 intake 前置。
3. 并行处理 P0-05/P0-07 的 license、IP/FTO 和 P0-06 biosecurity 决策。
4. 只有真实输入回填并通过 validator 后，才重新评估 P0-08/P0-10/P0-11。
5. P0-09 物理 ddG 继续保持 fail-closed；proxy 不得当作 physics。

禁止事项：
- 不把 candidate、draft、receipt、ready-to-verify 或 validation success 当作 approval。
- 不手写 reviewed decision、训练标签、正式 feedback intake 或 release/production 授权。
- 不在缺少真实输入时运行新的 Rosetta/FoldX/PyRosetta 任务。

计划行数：11；当前全部 blocked；P0 解锁：false。
