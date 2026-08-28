# Architecture

## Boundary

`openfoam_cfd_agents.domain` 是稳定核心。所有执行平台、LLM、调度器和可视化工具都在边界之外，只能通过适配器产生证据，再由核心规则计算状态。

## Flow

1. Supervisor 调用一个阶段任务。
2. Agent 或 Adapter 生成原始 artifact 与规范化 metrics。
3. `MetricRule` 对 metrics 执行确定性比较。
4. `evaluate_stage` 从所有检查结果派生 `passed` 或 `failed`。
5. Supervisor 仅在 `passed` 且审批策略允许时进入下一阶段。
6. Report 读取 Manifest，原样呈现状态和证据。

## OpenFOAM v14 profile

- 平台：Foundation OpenFOAM。
- 版本：14。
- 单区域应用：`foamRun`。
- 串行：`foamRun -case <path>`。
- 并行：`decomposePar` → `mpirun -np N foamRun -parallel` → `reconstructPar`。
- 所有命令使用参数数组执行，不拼接 shell 字符串。
- 预检同时验证案例结构、环境变量、版本和必要可执行文件。

`fieldMinMax` 等 function object 不进入默认模板。任何 function object 都必须先在目标 v14 安装的可用类型、源码或实际案例中验证。

## Upstream integration

### Foam-Agent

后续通过规划端口接入其 Architect/Input Writer/Reviewer 能力。生成内容必须经过 v14 适配、案例预检和独立阶段门禁，不能直接继承其 Foundation v10 成功结论。

### openfoam-mcp

`OpenFoamMcpAdapter` 当前映射以下工具：

| Workflow operation | MCP tool |
| --- | --- |
| preflight | `openfoam_preflight_check` |
| validate case | `openfoam_validate_case` |
| serial run | `openfoam_run_solver` |
| parallel run | `openfoam_run_parallel` |
| status | `openfoam_get_run_status` |

Adapter 接受注入的异步 `call_tool(name, arguments)`，因此不绑定特定 MCP Client SDK。调用方负责连接、认证、超时和重试策略。

## Trust model

阶段状态的可信度按以下顺序递增：

```text
process exited
< numerical run healthy
< discretization verified
< statistics converged
< physical validation passed
```

较低层级的通过不能替代较高层级的检查。
