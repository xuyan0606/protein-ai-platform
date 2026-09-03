# 编号复核并发提交实现计划

> **面向 AI 代理的工作者：** 使用已有代码库模式逐任务实现并验证此计划。

**目标：** 允许多个复核人同时提交不同编号记录，并让安全管线进入单实例后台队列，不再阻塞复核工作台。

**架构：** 服务端用进程内队列和单 worker 串行执行安全管线，所有请求立即获得独立 `run_id`；决策文件使用进程锁、临时文件和原子替换，避免并发读写丢失。前端只锁定当前记录，安全管线提交后显示 queued/running 状态并立即允许切换和提交其他记录。

**技术栈：** Python `ThreadingHTTPServer`、`queue.Queue`、原子文件替换；原生 JavaScript、Fetch API。

---

### 任务 1：服务端并发决策写入与安全管线队列

**文件：**
- 修改：`AI大模型/scripts/serve_numbering_review_platform.py`

- [ ] 为决策写入增加 `DECISION_LOCK`，写入采用同目录临时文件后 `os.replace`，并补充服务端 `submission_id` 与 `submitted_at` 审计字段。
- [ ] 增加安全管线队列状态结构；`start_run_step("safe_pipeline")` 将任务放入单 worker 队列，worker 依次执行并更新 queued/running/succeeded/failed 状态。
- [ ] 保留普通步骤现有行为；安全管线任务不因已有任务运行而失败或覆盖状态。

### 任务 2：前端按记录解锁并展示队列状态

**文件：**
- 修改：`AI大模型/ui/numbering_review/app.js`

- [ ] 将 `workflowBusy` 改为 `busyByRecord`，保存、验证、应用和冲突处理只锁定当前 `record_id`。
- [ ] 安全管线提交后不等待完成，不把当前记录全局锁死；记录 `run_id`，后台轮询只更新状态提示。
- [ ] 切换记录或提交其他记录时按钮保持可用；同一记录重复点击仍被保护。

### 任务 3：并发回归测试

**文件：**
- 创建：`AI大模型/tests/test_numbering_review_concurrency.py`

- [ ] 测试两个线程保存不同 `record_id` 后 JSONL 同时保留两条记录。
- [ ] 测试同一 `record_id` 的写入是完整行，不产生半行或损坏 JSON。
- [ ] 测试两个安全管线请求均返回 queued/run_id，并按队列顺序执行而非立即失败。

### 任务 4：验证

- [ ] 运行 `python3 -m pytest AI大模型/tests/test_numbering_review_concurrency.py -q`。
- [ ] 运行 `python3 -m py_compile AI大模型/scripts/serve_numbering_review_platform.py`。
- [ ] 用本地服务发送两个并发 `save-numbering-decision` 请求，确认响应均为成功且文件行数正确。
