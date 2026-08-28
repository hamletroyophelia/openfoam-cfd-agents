# OpenFOAM CFD Agents

面向 OpenFOAM CFD 算例全生命周期的可复现、可审查多 Agent 工作流。当前优先支持 **Foundation OpenFOAM v14**，并通过端口/适配器为 SU2、Fluent、STAR-CCM+ 等平台保留扩展边界。

> 当前处于 Phase 1 MVP。项目已经建立确定性控制平面，但尚未实现完整的自然语言建模与全生命周期无人值守计算。

## 核心原则

- Agent 负责形成建议与解释，确定性程序负责数值计算和阶段判定。
- 每个阶段输出统一的 `StageResult` JSON，只有 `passed` 才能继续。
- “求解器正常退出”和“结果可信”是两个不同的验收门。
- OpenFOAM 版本假设显式写入配置；当前只接受 `foundation-14` 与 `foamRun`。
- 外部执行通过适配器隔离，不把 Foam-Agent 或 openfoam-mcp 的 v10/v11 假设泄漏到工作流核心。

## 已实现的 MVP

| 模块 | 当前能力 |
| --- | --- |
| Supervisor Agent | 顺序编排、失败即停、人工审批状态、异常转机器失败结果、Manifest 持久化 |
| Monitor Agent | 解析 `Time`、残差、Courant 数、连续性误差和致命错误；按阈值判定 |
| Verification Agent | 三网格 Richardson 外推、观测阶数、GCI 与推荐网格级别 |
| Report Agent | 从已判定的 Manifest 生成 Markdown，不重新解释或改写状态 |
| Local OpenFOAM Adapter | v14 环境/算例预检、`foamRun` 串并行命令计划、无 shell 执行、逐命令日志 |
| openfoam-mcp Adapter | 映射预检、算例验证、串并行运行和状态查询工具调用 |
| CLI | 配置验证、日志监控、网格验证、运行计划和报告渲染 |

尚未实现：Physics/Case Builder/Mesh/HPC/Statistics/Postprocess Agent 的生产逻辑、LLM Provider、自动停止运行中的求解器、SLURM/PBS、HTML/PDF 报告和完整 OpenFOAM v14 算例模板。

## 架构

```text
Supervisor Agent
├── deterministic stage gates
├── approval / recovery state
└── WorkflowManifest
    ├── LocalOpenFoamAdapter  ──> foamRun / MPI
    ├── OpenFoamMcpAdapter   ──> openfoam-mcp tools
    ├── MonitorAgent         ──> solver log metrics
    ├── VerificationAgent    ──> Richardson + GCI
    └── ReportAgent          ──> Markdown report
```

Foam-Agent 可在后续作为规划、输入文件生成与 Reviewer 推理来源；openfoam-mcp 作为执行工具层。本项目自己的 `StageResult` 与验收规则仍是唯一的流转依据。

## 快速开始

PowerShell 7：

```powershell
Set-Location -LiteralPath 'D:\Code\openfoam cfd agents'
py -3.12 -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python -m pytest
```

运行确定性工具：

```powershell
cfd-workflow validate-config .\config\default.yaml
cfd-workflow monitor .\examples\phase1\log.foamRun --output .\runs\demo\monitor.json
cfd-workflow verify-mesh .\examples\phase1\mesh-study.yaml --output .\runs\demo\mesh-verification.json
cfd-workflow plan-run 'D:\cases\case with spaces' --processes 16 --output .\runs\demo\run-plan.json
```

在实际执行 OpenFOAM 前，运行主机必须加载 Foundation v14 环境，并让 `WM_PROJECT_DIR`、`WM_PROJECT_VERSION=14`、`foamRun`、`blockMesh` 和 `checkMesh` 可见。Windows 可运行分析、验证和报告工具；本地求解通常在已配置 OpenFOAM 的 Linux、容器或 HPC 节点进行。

## 机器可读输出

```json
{
  "stage": "mesh_verification",
  "status": "passed",
  "metrics": {
    "fine_gci": 0.018,
    "observed_order": 1.92,
    "recommended_level": "fine"
  },
  "checks": [],
  "artifacts": ["mesh-study.yaml"],
  "message": "All acceptance checks passed."
}
```

状态由规则计算，不接受 Agent 自报 `passed`。

## 项目结构

```text
openfoam cfd agents/
├── agents/                       # Agent 责任与输入输出契约
├── config/                       # 通用工作流配置
├── docs/                         # 架构与集成说明
├── examples/phase1/              # 可直接用于 CLI 冒烟测试的数据
├── src/openfoam_cfd_agents/
│   ├── agents/                   # Supervisor/Monitor/Verification/Report
│   ├── adapters/openfoam/        # Local v14 与 openfoam-mcp 适配器
│   ├── cli.py
│   ├── config.py
│   └── domain.py                 # StageResult 和确定性门禁
├── tests/
├── LICENSE
└── pyproject.toml
```

## 上游基础

- [csml-rpi/Foam-Agent](https://github.com/csml-rpi/Foam-Agent)：多 Agent 编排、输入生成、纠错与可视化参考；其默认验证路径仍是 Foundation v10。
- [milsonson/openfoam-mcp](https://github.com/milsonson/openfoam-mcp)：23 个 OpenFOAM MCP 工具的执行层参考；其 Docker 路径当前基于 OpenFOAM 11。
- [Foundation OpenFOAM v14 User Guide](https://doc.cfd.direct/openfoam/user-guide-v14)：v14 行为的首要版本依据。

本仓库未复制上述项目源码；适配器只依赖公开工具契约。

## License

Apache License 2.0。参见 [LICENSE](LICENSE)。
