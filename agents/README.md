# Agent contracts

这些 Agent 是工作流角色，不是数值判定器。当前 Python 实现在 `src/openfoam_cfd_agents/agents/`。

## Supervisor Agent

- 输入：有序 `StageTask`、审批策略、运行标识。
- 输出：`WorkflowManifest`。
- 约束：只接受阶段产生的 `StageResult`；失败立即截断；需要人工审批时返回 `approval_required`。

## Monitor Agent

- 输入：Foundation OpenFOAM 求解日志、显式阈值。
- 输出：`monitoring` 阶段结果与原始日志 artifact。
- 约束：解析程序生成指标；致命错误、进度不足、Courant 数、连续性误差或残差门失败时不得继续。

## Verification Agent

- 输入：三个系统加密网格的单元数与同一目标量。
- 输出：观测阶数、Richardson 外推、GCI、推荐级别与阶段状态。
- 约束：拒绝重复网格规模、零差值及不可计算序列；阈值由配置给出。

## Report Agent

- 输入：已持久化的 `WorkflowManifest`。
- 输出：Markdown 报告。
- 约束：仅展示证据，不重新决定状态，不把运行完成描述为结果可信。

## 后续 Agent

Physics、Case Builder、Mesh、HPC、Statistics、Postprocess 与独立 Reviewer 会在对应确定性工具和验收契约存在后接入。
