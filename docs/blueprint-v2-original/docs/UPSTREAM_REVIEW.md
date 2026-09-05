# V2 阅读说明

本文件保留前版 2026-09-04 调研记录，不能视为每项均已重新认证。2026-09-05 的新增及重新核验来源见 [SOURCES_V2.md](SOURCES_V2.md)。优先实施现有核心的可靠性和数据契约，不因新增 CAE 项目而扩大首发范围。

---

# 上游项目核验与集成决策

日期：2026-09-04。方法：官方文档、GitHub README 和指定 skill 文件审阅。未进行部署、性能测量、完整源代码审计或端到端测试。没有以 star 数代替版本兼容性与证据质量。

## 1. 优先采用或参考

| 项目 | 核验到的能力 | 约束与决定 |
| --- | --- | --- |
| [Foam-Agent](https://github.com/csml-rpi/Foam-Agent) [S07] | 多 Agent 规划/写案/执行/修复，教程检索，已有 `/foam` skill 与 MCP | 默认主要验证 Foundation v10。保留现有适配器，作为可选生成/诊断后端；v14 要单独验证 |
| [AI-CFD-Scientist](https://github.com/csml-rpi/AI-CFD-Scientist) [S08] | 科研流水线、阶段审计、强制网格检查、跨算例分析、独立 skill/结构化产物 | 参考契约与阶段设计；不照搬其阈值，不再引入第二个主控。此次未确认源码复用许可证 |
| [HPC-Skills](https://github.com/SciMate-AI/HPC-Skills) [S09] | 可移植的 HPC 技能库，包含 OpenFOAM/MPI/Gmsh/ParaView/编排 | 适合按需加载；需审校、固定版本、与本机能力核对 |
| [OpenFOAM_expert_SKILL](https://github.com/Zyzhan417/OpenFOAM_expert_SKILL) [S13] | 本地源码、继承链、边界与物理模型分析，MCP 接口 | 适合作为只读源码专家；来源必须与目标软件分支、版本匹配 |
| [milsonson/openfoam-mcp](https://github.com/milsonson/openfoam-mcp) [S11] | 23 个工具；模板、预检、串并行、状态与残差；路径边界 | 已有适配器可继续用。容器 OF11、snappyHexMesh 接口预留、异步 worker 尚属路线图；并行可自动降级串行 |
| [openfoam-claude-suite](https://github.com/swtbkim/openfoam-claude-suite) [S12] | of-setup/of-sim/of-post/of-doctor | 面向 OpenCFD v2412。借鉴分工，不能当作 Foundation v14 的受测模板 |
| [viznoir](https://github.com/kimimgo/viznoir) [S14] | 无界面 VTK 可视化 MCP，含 OpenFOAM 数据路径 | 可选渲染后端；不是 ParaView GUI，也不代替独立数据验证 |

Foam-Agent、HPC-Skills、OpenFOAM_expert_SKILL、viznoir 的所查页面显示 MIT 标记。**这不是依赖组合的法律审计，也不涵盖依赖、数据或 OpenFOAM 本身。** 正式集成需要重新读取选定提交的 LICENSE 和第三方声明。

### 重要的审校发现

HPC-Skills 的 `hpc-openfoam/SKILL.md` 同时包含旧式执行程序和现代模块化用法，且有与 OpenFOAM 无关的 VASP 提示。因此不应把技能库原样作为模型/版本/科学阈值的权威；应筛选、分版本并加测试。[S10]

milsonson 的自动串行回退是可用性行为，不是性能实验的成功。性能比较必须保留实际执行模式；正式任务是否允许回退由预算与审批决定。[S11]

AI-CFD-Scientist 已有网格验证与审计设计。因此不能再断言“所有开源 Agent 都没有网格检查”。但这些文档也不能证明其已满足本项目的全部模型、版本、HPC 与统计验收要求。[S08]

## 2. 备选与未选为默认项

| 项目 | 核验结论 | 处理 |
| --- | --- | --- |
| [LLNL/paraview_mcp](https://github.com/llnl/paraview_mcp) | README 提示新版本中的客户端/服务器同步与稳定性问题 | 仅实验性 GUI 交互候选；默认后处理使用批脚本 |
| [webworn/openfoam-mcp-server](https://github.com/webworn/openfoam-mcp-server) | 文档说明 OpenFOAM 能力部分实现，含教育/指导性质与待完成模块 | 不选为生产执行核心 |
| [svd-ai-lab/sim-cli](https://github.com/svd-ai-lab/sim-cli) | 通用 CAE CLI/插件方向，所查阶段为早期版本 | 参考未来多求解器插件边界 |
| [svd-ai-lab/sim-plugin-openfoam](https://github.com/svd-ai-lab/sim-plugin-openfoam) | OpenFOAM 插件与 skill | 待单独兼容性测试；不在首版叠加第二套工具栈 |
| [Terry-cyx/MetaOpenFOAM](https://github.com/Terry-cyx/MetaOpenFOAM) | README 标记 deprecated，并指向 sim-cli | 不作为新项目的维护基座 |

## 3. VibeFlow 的准确定位

[官方介绍](https://docs.vibeflow.ai/introduction)描述的是工作流/Web 应用平台，而非已验证的 CFD/HPC 执行环境。[S03]

[连接外部 MCP 的节点](https://docs.vibeflow.ai/nodes/mcp-node)给 Agent 提供远程工具，需配置 endpoint/auth，并使用 `agent.tools -> mcp.input` 连接。[S04]

[VibeFlow 自己的 MCP](https://docs.vibeflow.ai/features/mcp)用于它自己的项目创建/管理，不是 OpenFOAM 工具服务。[S06]

[GitHub 集成](https://docs.vibeflow.ai/features/github-integration)是付费功能，导入检查 React/Vite/TypeScript；新建仓库默认私有。建议独立的可选 UI 项目，通过受控 API 连接 CFD 核心。[S05]

不要把“VibeFlow 可接 MCP”写成“VibeFlow 已能可靠托管长时间 MPI 任务”，也不要宣称其部署模式已满足独立开源自托管要求。

## 4. 实际接入前必须补全的记录

每个选择的上游应记录：完整仓库名、不可变 commit SHA、许可证文件及依赖声明、工具 schema、支持版本、运行依赖、最小权限、已知限制、实际测试证据和回滚方法。

此次未捕获全部上游不可变提交，因此不提供伪造的 lock 文件。接入时使用真实提交生成锁定清单，不以 `main` 作为可复现版本。

## 5. 一手来源索引

编号 S01–S20 的完整链接见 [系统设计末尾](SYSTEM_DESIGN.zh-CN.md#15-主要一手来源)。本文件中每个候选项目也直接链接到其维护者仓库。上游事实以文档审阅为限；“建议用法”属于本系统的设计判断。
