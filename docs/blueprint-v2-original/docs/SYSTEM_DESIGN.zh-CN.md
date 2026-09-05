# OpenFOAM CFD Agents：通用 CFD 全生命周期系统设计 V2

V2 增量核验日期：2026-09-05。目标仓库：`hamletroyophelia/openfoam-cfd-agents`。此前方案与未重新检查的上游资料保留 2026-09-04 的核验日期。

**来源边界：**用户提供的微信《【CAE 数值仿真的 MCP 调研报告】生态现状、研发价值与短板分析》未能读取，未找到可核验转载。本版不是该报告的摘要，也不将任何观点归因于作者；新增内容来自现有方案、目标仓库源码审查及可访问的一手资料。详见《V2 来源与核验范围》。

**V2 重点：**保留一套确定性主控，将通用原则落实为可测试的接口兼容、物理语义、持久作业、数据契约、证据失效和安全规则，不增加一批互相重叠的 Agent。

**文档状态：待实施设计。** 文中“应当”“建议”“拟新增”的内容不是已经实现的功能。本次未修改远端仓库、未安装这些集成、未执行 OpenFOAM/HPC/ParaView 端到端验收。上游能力以所查文档为依据，来源见文末和《上游项目核验》。

## 1. 项目定位与现有基础

目标不是“让几个聊天 Agent 轮流写算例”，而是建立可恢复、可复现、可审计的工程流水线：自然语言和结构化需求都能进入；物理决策有依据；数值指标由程序计算；长计算脱离聊天生命周期；结果有证据和适用范围。

现有仓库文档列出了确定性 Supervisor、日志 Monitor、三网格 Verification、Markdown Report、Foundation v14 本地执行适配器，以及 Foam-Agent/openfoam-mcp 的接口映射。生产级建模、网格、HPC、统计、后处理、实时停止和调度器等仍待补齐。[S01][S02]

**保留已有核心和包名，不另起一套同名框架。** 通用性通过能力接口实现，不以“支持所有求解器”的 README 宣称实现。首个受测配置继续是 Foundation v14；其他版本和软件只有通过相应集成测试才能标记为支持。

## 2. 一套主控，五类职责

| 层 | 职责 | 禁止承担的职责 |
| --- | --- | --- |
| Skill | 提供方法、规则、检查步骤和版本化参考资料 | 仅凭文字宣布误差或统计收敛 |
| Agent | 解释需求、提出方案、诊断问题、提出修改 | 绕过审批、直接更改验收状态 |
| MCP/API | 暴露有类型、有权限的工具接口 | 把任意远程 shell 当默认工具 |
| Core | 管理状态、任务、证据、验收规则和预算 | 相信外部 Agent 的 success 就是科学正确 |
| Worker | 实际执行网格、求解、统计、后处理任务 | 因浏览器或 LLM 请求断开而丢失作业 |

CLI、MCP 客户端和 VibeFlow 是入口，不是三个不同的计算主控。Foam-Agent、AI-CFD-Scientist 等只在明确的阶段边界提供能力；禁止套娃式地同时启动多个全流程 Supervisor。

## 3. 集成架构

```text
CLI / MCP-compatible client / optional VibeFlow console
                              |
                  Authenticated CFD gateway
                REST for deterministic operations
                MCP for agent-discovered tools
                              |
            Existing deterministic workflow core
         approvals / rules / manifests / resource budgets
                              |
          Durable job store + event/artifact registry
                              |
        Versioned adapters + bounded execution workers
        |              |              |              |
    OpenFOAM       mesh tools      schedulers      postprocess
    local/MPI     native/Gmsh      local/SLURM     ParaView batch
        |                                             |
        +--------------- evidence --------------------+
                  CSV / plots / states / reports
```

**建议技术组合：**沿用 Python 核心，增加类型化配置与 JSON Schema、HTTP/MCP 网关、持久化任务表和 worker。单机优先 SQLite 加本地文件存储；出现多节点并发需求再评估 PostgreSQL 和对象存储。不要在首版同时引入多个队列框架、多个 Agent 框架和多个数据库。

网关可以异步，但昂贵计算必须由 worker 托管。提交操作迅速返回 `job_id`；通过状态、指标、事件和产物接口继续获取结果。worker 启动时应将数据库记录与真实进程/调度器作业核对，避免重复启动或误报作业结束。

### VibeFlow 的位置

VibeFlow 官方文档说明其生成 TypeScript 工作流，使用 Convex，并能连接远程 MCP；其 MCP Node 是挂在 Agent 的 tools 上的工具提供器，不是主流程的普通执行节点。[S03][S04]

因此建议只用它做需求表单、审批、任务看板、对比结果和通知。关键提交/取消/审批优先走确定性 HTTP 调用；对话式解释再接 MCP。其 `agent.tools -> mcp.input` 连接应指向经过认证、实际可达的 CFD 网关，而不是服务器上的本地 stdio 服务。

VibeFlow 自身提供的 MCP 用于创建和管理 VibeFlow 项目，不能与它的“连接外部 MCP”节点混为一谈。[S06]

GitHub 同步目前是付费功能；导入检查 React/Vite/TypeScript 兼容性。[S05] 推荐独立的可选控制台仓库，或经过验证的前端子项目发布边界，不直接把整个 Python 科学核心交给自动同步覆盖。未配置 VibeFlow 时 CLI/MCP 应完整工作。

### 3.1 工具控制层与科学数据层分离

MCP 提供工具与结果的交互规范，不替代求解器、数据仓库或工程验收。当前工具规范允许结构化结果、输出 schema 和资源链接；本项目仍需定义自己的 CFD 语义及授权规则。[S22]

控制层只传 spec、批准的修订、job_id、有限指标摘要和 artifact_id。完整网格、体场和长日志留在计算侧，后处理在数据附近执行。向 Agent 返回摘要与证据索引，向浏览器返回预览，向研究人员提供有权限的原始数据访问。

不要把 `result_mesh.json` 一类轻量浏览器格式提升为完整科学存档：预览可能删减体单元、精度、变量或时间点。原生场文件仍为权威输入；预览必须标注简化/抽样规则。ParaView 的远程模式也采取服务端处理与渲染、尽量少传数据的方式。[S26]

### 3.2 能力注册与准入，不等同于 tools/list

每个 adapter 按具体操作记录：provider、上游提交、schema 指纹、支持的协议与 SDK、求解器发行分支/版本/模块、操作系统、MPI、权限、副作用及返回状态语义。把以下证据分开：

| 证据 | 能证明什么 | 不能证明什么 |
| --- | --- | --- |
| 上游声明 | README/工具列表宣称存在某能力 | 目标环境能运行 |
| 契约测试 | 参数、结果、错误、取消语义符合约定 | 算例数值正确 |
| 运行测试 | 特定环境确实完成指定工作 | 所有模型或网格均可靠 |
| 科学基准测试 | 指定条件与目标量达到预设要求 | 对未测试物理范围普遍有效 |

这四类不是可以相互替代的单个评分。准入结果由本地证据和策略计算；外部服务不能自己填一个 `verified: true` 获得生产权限。环境或上游 schema 改变后重新评估。

本地/OpenFOAM CLI 或原生 API 优先；受审查 MCP 是适配入口，不再叠加一层全流程主控。Fluent 的未来适配可基于官方 PyFluent，而不必先依赖第三方 GUI 控制器；具体版本依赖必须单独测试。[S28] 几何或专有软件确需交互式操作时使用隔离 session，导出完整输入后再进入 batch 工作流。交互式修复不得直接修改正在求解的目录。

### 3.3 独立作业协议，兼容不同 MCP 版本

2025-11-25 的 Tasks 是实验功能；官方 SEP-2663 描述了向 Tasks 扩展的调整，Python SDK 的旧实验 Tasks 接口也标记弃用。不得把任一 SDK 的实验类固定为主控领域模型。[S23][S24]

核心始终使用本项目的 `JobSpec/JobRecord`。基础路径为快速提交并返回业务 job_id；经能力核验的 MCP Tasks 仅映射这个业务任务，不另建一个求解进程。MCP task 过期、客户端断开或协议会话结束，不应删除业务作业或科学证据。

协议请求处理成功、工具业务执行成功、求解进程成功、科学判据通过分别记录。尤其是“提交工具完成”只证明提交成功，不能让界面显示求解完成。取消请求已接收也不等于底层 MPI 进程已经停止。

## 4. 上游能力取舍

| 组件 | 推荐用法 | 集成边界 |
| --- | --- | --- |
| Foam-Agent | 可选规划、输入生成、诊断修复后端 | 现有 MCP adapter；生成内容经目标版本转换、预检和审批 |
| AI-CFD-Scientist | 参考科研阶段契约、网格门槛、跨算例审计 | 研究型 profile；不再增加第二个主控 |
| HPC-Skills | 按需加载 OpenFOAM、MPI、Gmsh、ParaView 和调度知识 | 审校后固定版本；参考资料不是执行证据 |
| OpenFOAM_expert_SKILL | 查询与运行版本相同的本地源码、边界条件和模型类 | 默认只读，记录源码版本及位置 |
| milsonson/openfoam-mcp | 可选工具后端，复用现有适配器 | 禁止把其降级/完成状态直接升级为科学验收 |
| openfoam-claude-suite | 参考 setup/sim/post/doctor 的分工和修复流程 | 其 v2412 配置不能原样用于 Foundation v14 |
| ParaView batch | 默认可复现后处理后端 | 固定版本、受控脚本、相同数据生成相同产物定义 |
| viznoir | 可选 VTK 可视化 MCP 后端 | 与科学统计/验收分离，不作为 ParaView 状态文件的替代 |

Foam-Agent 自带 skill 和 MCP，但主要验证路径仍为 Foundation v10；milsonson 项目的容器与模板也不是已验证的 Foundation v14 运行层。[S07][S11] 每个外部后端都必须声明版本和能力，不允许“改一个版本字符串就算兼容”。

## 5. 逻辑 Agent 与标准产物

这些是逻辑责任，可由少量 Agent 按需承担，不要求同时启动十几个 LLM 进程。监控、统计、计时和阈值比较始终是普通程序。

| 角色 | 主要职责 | 标准产物 |
| --- | --- | --- |
| Supervisor | 计划依赖、预算、审批、状态推进、重试上限 | `WorkflowManifest`、事件记录 |
| Physics & Numerics | 方程、物性、无量纲数、湍流/多相模型、算法、离散格式、边界/初始条件 | `PhysicsSpec`、`NumericsSpec`、依据与假设 |
| Geometry & Mesh | 几何单位、计算域、patch、多区域、边界层、加密族、网格质量 | `MeshFamilySpec`、质量指标、网格哈希 |
| Case Builder | 版本匹配的字典/字段/脚本生成与预检 | 不可变算例修订、配置差异 |
| Verification | 空间、时间、计算域敏感性；适用时 GCI | `VerificationResult`、比较 CSV |
| HPC & Selection | 核数/SMT/NUMA/分解方法试验，性能与误差约束选择 | `BenchmarkResult`、推荐配置及证据 |
| Runner / Monitor / Doctor | 作业控制、健康指标、异常分级、受控恢复 | 作业 ID、日志、告警、修复提案 |
| Statistics | 统计窗口、均值/RMS、相关性、置信区间、频谱 | `StatisticsResult`、分析元数据 |
| Postprocess | 采样、云图、截面、适用的涡结构、动画、CSV | 脚本、状态、图像、数据清单 |
| Report | 汇总已有证据、局限与失败原因 | Markdown/HTML 报告、产物索引 |
| Independent Reviewer | 审核物理假设、证据完整性和结论措辞 | 审查意见；不能自行修改验收数据 |

### 5.1 物理语义契约与几何身份

自然语言需求首先落为可审查的 `CaseSpec`，再生成求解器字典。每个物性/边界量需保存数值、单位、维度、来源、适用条件及转换过程。物理量还要说明参考坐标系、符号约定、空间位置和时间含义；名称相同不代表定义相同。

把几何单位、几何哈希、patch 的物理角色与网格实体映射显式记录为 `GeometryBinding`。重网格、拓扑变化或导入新 CAD 后必须重建映射并检查面积、方向、连通性和覆盖范围。不能仅凭旧面编号给新网格施加边界条件，也不能用截图确认替代实体检查。

通用层保存物理含义，版本化 adapter 负责具体字段和字典编译。无法无损表达的模型、边界条件或耦合返回 unsupported，不静默降级为近似模型。模型选择输出候选与适用范围；关键缺失信息进入审批，不使用未经披露的 `turbulence_model: auto` 补全。

Physics & Numerics 必须处理单位、参考量、可压缩性、热/多相耦合、壁面处理、压力参考以及场间一致性。模型选择不能只看一个 Re，也不能把 `laminar` 自动解释为经过分辨率验证的 DNS。没有必要时不自动扫遍所有湍流模型。

## 6. 完整工作流

```text
定义目标量、误差预算、物理范围与计算预算
  -> 探测环境 / 版本 / 源码 / 可用工具
  -> 物理模型、算法、边界条件和初始条件审查
  -> 创建网格族与版本化算例
  -> 网格质量检查 + 小规模运行预检
  -> 性能预试验与粗筛
  -> 空间 / 时间 / 计算域验证及统计误差评估
  -> 合格候选的性能对比与联合复核
  -> 审批正式运行
  -> 持续监控 + 统计收敛检查 + 有预算上限的续算
  -> 解析解/制造解用于数值验证；适用实验数据用于物理验证
  -> 可复现后处理
  -> 报告 / 审查 / 归档
```

性能实验与部分验证可在依赖和资源允许时并行，但不能相互抢占到导致计时失真。任一失败阶段仍需生成诊断报告。没有适用实验或可追溯实测证据时，标记“未建立物理验证”，不要阻止保存已完成的数值研究，也不要把它包装成已验证的预测。

## 7. 精度与时间效率的选择方法

### 7.1 先定义目标量和容限

案例需要明确关心的量，例如阻力、压降、质量流率、换热系数、自由液面高度或载荷 RMS。每个量应说明定义、单位、归一化参数、时间窗口、容差来源及绝对/相对判据。接近零的量必须有绝对误差尺度，不能仅比较相对百分比。

不存在适用于所有算例的“网格误差小于 2% 就通过”。容限应来自研究或工程需求；系统拒绝未经说明的统一默认科学门槛。

### 7.2 固定步数测试只衡量性能

预热后运行固定步数，可以比较每步耗时与资源消耗，但不能证明网格或时间步的精度。比较并行配置时，保持网格、数值设置、起始场、输出频率与任务负载一致，重复实验并记录计时离散程度。

记录 wall time、seconds/step、实际推进物理时间、资源时成本、I/O，以及定义清楚的内存指标。SMT 测试应分别定义预约 CPU 槽时与实际占用的物理核时，不把逻辑线程数直接标作物理核数。区分单 rank 峰值、各 rank 峰值之和与真实节点峰值，不能把启动器 RSS 当作整个作业的内存。

以可运行的 `p_ref` 核配置为基准：

```text
speedup(p) = T(p_ref) / T(p)
efficiency(p) = speedup(p) * p_ref / p
```

不要求大型算例一定能单核运行。瞬态计算还要比较推进单位物理时间的成本；稳态计算应比较达到相同收敛判据的总成本。

SMT、绑核、NUMA、MPI 版本、分区方法和硬件拓扑都应写入记录。**性能实验禁止并行失败后回退串行并继续当成原配置成功结果。** 上游存在自动回退行为，因此适配层需要显式识别和拒绝这种无效样本。[S11]

### 7.3 网格、时间步和计算域验证

优先构造至少三层有明确加密关系的网格；保持物理模型、几何定义、边界条件和可比较的数值设置一致。NASA 的网格收敛资料支持以三网格估计阶数并检查渐近行为，同时强调趋向数值极限不等于物理模型正确。[S17]

只有满足适用条件时才计算和解释 Richardson/GCI。非单调、采样噪声主导、非渐近、不同几何或不可比较加密时返回 `inconclusive` 或采用明确的替代分析，不能用数值技巧强行获得 passed。

LES/DNS 的网格变化可能同时改变已解析尺度与亚格子贡献，需要分辨率指标、统计采样不确定度和目标量的联合证据；不能对所有 LES 机械套用稳态式 GCI。相关样本和采样误差会影响统计量及离散误差估计。[S18]

时间步验证比较相同物理区间或可比的收敛统计窗口，而非相同步数。自适应步长需保存真实 `deltaT` 历史，并比较受控的上限/控制参数。CFL 限制主要是稳定性控制，不能替代时间精度验证。计算域敏感性应按边界对关注量的影响评估。

建议先粗筛，再对候选网格与时间步作嵌套研究，最后联合复核，避免无差别运行网格×时间步×核数的全组合。选择中等网格时，必须有该网格自己的误差证据，不能拿细网格 GCI 代替。

### 7.4 推荐配置的证据链

```text
排除环境/网格/数值健康失败配置
  -> 排除未满足目标量误差或统计要求的配置
  -> 在合格配置中比较 wall time 与 core-hours
  -> 给出 Pareto 候选及受预算约束的推荐项
  -> 对最终网格 + 时间步 + 核数配置再验证
```

推荐用语应是“在当前模型、验证证据和容限下满足要求”，不是“保证真实物理精度”。耗时最小和计算费用最小可能不是同一配置。

## 8. 运行监控、恢复和统计

### 数值健康监控

按求解器能力采集残差、Courant 数、连续性/守恒误差、场极值、力/热通量以及相分数等。区分字段缺失、暂未输出和真正越界；时间长、残差低或进程退出码为零，都不能单独表示科学收敛。

规则分为提示、需要人工检查、触发安全停止三类。停止优先使用适配器验证过的正常结束/检查点路径；超过限定等待后再终止进程组。停止和重新启动都必须记录，且不能越权终止其他算例。

### 受控修复

Doctor 只提交修改差异、原因、预期影响和应失效的证据。路径、环境或启动参数修复与物理/数值修改分开审批。任何改变网格、模型、离散格式或时间策略的修复都创建新修订，重新运行相关验证，不能继承旧结论。

运行中的同一算例只允许一个写入者；实验候选使用独立目录和不可变父检查点。最大重试次数、core-hours、墙钟时间、磁盘量和并发数都受预算控制。

### 8.1 从原则落为可恢复作业的事务规则

提交时在本地持久存储中原子记录授权主体、项目、幂等键、请求摘要、资源预约和 launch intent。同键同摘要返回同一 job_id；同键不同摘要拒绝。采用“幂等业务效果 + 执行核对”，不承诺一般分布式环境下天然 exactly-once。

worker 认领使用租约；受管服务/进程或调度器作业须可按稳定身份重新发现。新 worker 接管前核对旧执行者是否仍活跃：租约到期不能单独证明旧 MPI 已结束。进程标识至少关联启动时间与主机启动身份，避免 PID 复用误杀。

必须测试“已经启动求解器，但还没写回运行 ID 时 worker 崩溃”的窗口。单机可使用可重识别的受管服务身份，集群用受测调度器关联策略；无法消除歧义时进入 `unknown/reconciling` 并阻止重复启动，不盲目重试。

检查点只有在目标 profile 要求的字段、分区、时间与网格一致性检查完成后才可用于续算。最近的数字时间目录可能写到一半，不能直接等同于可恢复检查点。记录原始重启分支；分析不得把重复/冲突时刻算成新样本。

取消先写 `cancel_requested`，再请求所属执行单元安全结束，确认退出后写 `cancelled`。超时升级终止须有权限和审计；部分产物单独保留。数据库只记录事实，不通过改变状态假装进程已停止。

### 统计有效性

稳态场和统计稳态分开处理。瞬态流程需记录初始化舍弃区间、采样规则、窗口长度、缺失/重复时刻和相关性处理。均值与积分使用正确的时间权重；不规则采样频谱必须先采用明确的方法或经检验的重采样，不能直接按等间隔 FFT。

支持分块均值、块间相关性诊断、有效样本/块数和置信区间。PSD、主频和 Strouhal 需报告窗口、采样率、分辨率及参考尺度。只有探索性证据时必须这样标记，不自动称为可发表频谱。预算耗尽而证据不足时应结束为 `inconclusive`，而非无限续算。[S18]

## 9. 后处理交付标准

正式后处理采用版本匹配的 ParaView `pvpython`/`pvbatch` 脚本。官方文档提供数据、截图、动画及状态保存接口；具体格式与运行能力应在目标环境测试。[S19][S20]

| 输出 | 必需的可追溯信息 |
| --- | --- |
| CSV | 目标量定义、列单位、参考尺度、时刻、采样位置、来源数据哈希 |
| 云图/截面/流线 | 变量及 cell/point 关联、单位、时间、相机、色标范围、采样/滤波流程 |
| Q、lambda2 等 | 方法和定义、量纲/归一化、阈值、速度梯度来源、适用域 |
| 动画 | 帧列表、物理时间、相机、色标、帧率；Linux 优先帧序列加可选编码器 |
| ParaView 状态 | `.pvsm` 或可重放 `.py`，软件版本、输入清单和路径映射 |
| 报告 | 每个图表对应的数据/脚本/参数、验收状态和局限 |

必须区分压力与运动学压力、`p` 与 `p_rgh`，检查密度、参考面积与力系数定义。不同算例比较图使用统一且明确的范围，禁止自动色标掩盖数量级差异。截图漂亮不是物理正确性的证据。

viznoir 可以作为交互式 VTK 渲染后端。[S14] LLNL ParaView MCP 当前 README 提示客户端/服务器同步及稳定性问题，因此不设为默认生产后处理路径。[S15]

### 9.1 后处理可重放，而非像素级绝对一致

正式输出由固定输入、软件版本与 recipe 生成；数值数组用明确容差比较。跨驱动、渲染器或平台不承诺 PNG 字节完全一致。色标、相机等视觉参数变化只更新视觉产物；更换采样区域、插值方法或统计窗口则影响相关数值结论。

原始 artifact 与派生 artifact 分开。每项派生产物保存 parents、输入哈希、recipe 哈希、方法版本、单位、坐标/时间、误差或精度信息。MCP 返回的 resource link 也必须经项目权限校验，不因为知道 artifact_id 就允许读取。[S22][S25]

## 10. 数据契约与状态

建议在现有模型上进行向后兼容扩展，而不是直接替换 `domain.py`。

| 契约 | 核心字段 |
| --- | --- |
| `CaseSpec` | schema_version、单位、几何/物性、物理模型、BC/IC、目标量与预算 |
| `RuntimeProfile` | 软件分支/版本/构建、模块、MPI、可用工具、环境指纹 |
| `StudySpec` | 网格/时间步/域研究策略、候选配置、适用性与验收规则 |
| `JobSpec` | 已批准修订、执行类型、资源限制、幂等键、输入产物 |
| `JobRecord` | job_id、进程/调度器 ID、生命周期、心跳、事件、退出信息 |
| `StageResult` | 阶段、规则版本、逐项 checks、metrics、证据与 verdict |
| `ArtifactRecord` | 标识、类型、校验和、单位/时刻/坐标信息、生成脚本/版本 |
| `WorkflowManifest` | 输入、配置、所有尝试、修复、审批、引用和结果索引 |

作业生命周期与科学结论必须分开：

```text
job_state: queued | launching | running | reconciling | unknown | cancel_requested | succeeded | failed | cancelled
verdict:   passed | failed | inconclusive | not_applicable
```

现有 `StageStatus` 同时包含 pending/running/passed/failed/blocked/approval_required，尚未分离完整的作业生命周期与科学结论，也没有 inconclusive 枚举。[S21] 新状态要通过 schema 迁移与回归测试加入；不得直接修改旧 manifest 的历史事实。只有适用且必需的检查得到 passed 才满足阶段门槛；`not_applicable` 必须由明确的适用性规则产生并保留理由，不能用作人工跳过失败的按钮。

审批决定是否执行，不改变证据真假。例外运行可以记录为批准的探索实验，但不得把 failed 改为 passed。没有参考数据时物理验证单独显示未建立，不与求解作业成功混淆。

### 10.1 先修复非有限数验收缺口

本次读取的 `domain.py` 中，`_evaluate_rule` 排除了缺失、非数值和布尔型 observed，但在比较前没有排除 NaN/Inf。源文件 blob 为 `fffca99ea7dd09cad98357ae3590d58381d75d7e`。[S21]

因此 `NaN != 0`、`+Inf >= 0` 或 `-Inf <= 1` 可满足比较，得到通过。这是特定输入与操作符组合下的风险，并非所有包含 NaN 的规则都会通过。本次只做源码审查及独立算术复现，未运行仓库完整测试，未修改代码。

拟修复规则：observed 和 threshold 均需有效有限数；缺失、非有限数、单位不匹配及过期证据不可作为 passed 的依据。增加 `data_validity` 与诊断 reason。原始日志保留原样；对外 JSON 用 null 加状态编码异常，不输出非标准 NaN/Infinity。求解发散与采样尚不足分别分类，不一律当作同一种错误。

### 10.2 证据依赖图与结论失效

新增 `EvidenceGraph` 连接 spec、几何、网格、输入修订、运行、时间序列、统计、验证、图表、报告与审批。每条边标注它依赖哪些参数，避免“文件还在就继续用旧结论”。

| 改动 | 必须重新评估或生成 | 通常可保留 |
| --- | --- | --- |
| 方程、物性、BC/IC、模型或几何 | 相关建案、运行、数值/物理证据及报告 | 不受影响的源码知识索引 |
| 网格、算法、时间策略 | 相关运行与验证，必要时统计 | 上游已批准的物理需求 |
| 统计窗口或采样/过滤方法 | 统计、依赖均值/RMS的网格比较、频谱及报告 | 原始场与时间序列 |
| MPI/绑核/分解 | 对应性能数据；结果等价性与科学证据复用审查 | 不依赖执行布局的几何定义 |
| 色标、相机、版式 | 对应图片/报告 | 未变更的数据、统计与数值判据 |
| 容限或验收规则 | 生成新版本判定并重新审批 | 旧证据与旧判定作为历史 |

审批绑定输入修订、规则版本、资源预算与操作范围。Agent 不能在审批后换一份配置继续沿用批准；不受影响的证据可按规则复用，但复用理由必须可审计。

### 10.3 更严格地区分 verification 与 validation

解析解、制造解与已知数学性质主要为数值验证服务；与其他求解器一致属于交叉检查，不能单独证明真实物理正确。物理验证需要与适用实验/实测比较，并记录工况、测量与模型不确定度和验证范围。[S27]

统计收敛、离散误差、模型适用性分别报告。误差项没有独立性证据时，不自动用均方根相加给出“总误差”。

## 11. 拟新增的工具接口

**以下名称属于建议契约，并非现有可调用工具。** 实施前须完成发现、schema、权限和契约测试。

| 拟议接口 | 行为 |
| --- | --- |
| `cfd_inspect_environment` | 读取 worker 能力、软件版本和环境指纹 |
| `cfd_validate_spec` | 检查需求完整性、单位、规则和兼容性 |
| `cfd_prepare_case` | 提交已批准的建案任务，返回 job_id |
| `cfd_submit_job` | 提交受预算限制的求解/网格/分析任务 |
| `cfd_get_job_status` | 返回生命周期、最新事件与证据状态 |
| `cfd_get_metrics` | 按时间范围读取确定性采集的指标 |
| `cfd_cancel_job` | 仅停止授权任务并记录原因 |
| `cfd_run_verification` | 提交比较分析或验证实验任务 |
| `cfd_postprocess` | 提交版本化可视化/采样配方 |
| `cfd_build_report` | 汇总已有结果，不重写验收状态 |
| `cfd_list_artifacts` | 返回受权限保护的产物索引 |

长任务采用 job 模式，不在一个 MCP 请求里持续运行数小时。写操作包含 `case_revision`、幂等键及审批/预算检查。对外使用受管资源 ID，而不是任意 shell 和不受限绝对路径。

现有外部适配器分别使用 Foam-Agent 的 `request` 参数封装和 milsonson 的 `params` 封装。它们的连接管理、认证与超时仍需调用方实现，不能把“已有映射类”写成“所有服务器已连通”。[S02]

## 12. Skill 库与上下文管理

建议的逻辑技能包：`cfd-orchestrator`、`cfd-physics-numerics`、`cfd-case-builder`、`cfd-meshing`、`cfd-verification`、`cfd-hpc`、`cfd-monitor-doctor`、`cfd-statistics`、`cfd-postprocess`、`cfd-report-review`。

每个 Skill 只在相关阶段加载。通用方法与特定求解器资料分开；资料按分支、版本、源码提交和主题索引。长日志在程序侧聚合，只把异常片段和指标给 LLM；全日志作为证据保存。共享的不是不断增长的聊天记录，而是结构化 spec、阶段结果与产物索引。

上游 skills 的内容需要审校和版本测试，不可作为控制方程、字典语法或科学验收的最终权威。[S09][S10] 优先级建议：目标安装源码/版本文档 > 已验证模板 > 审校技能参考 > 未验证外部笔记。所有自动发现的知识更新走 review/PR，不允许运行中的 Agent 修改自己的验收规则。

本方案包仅附原创建议版 orchestrator Skill；其余技能为待实施目录规划，不伪装成已安装技能集合。

## 13. 安全、资源和发布

外部 README、论文、skill 和日志都按不可信输入处理。只通过受限工具使用其中信息，不允许文档指令改变授权范围。网关需认证和访问控制；worker 尽量处于私有网络；浏览器与 LLM 不接触 SSH 私钥或服务令牌。

算例目录做路径和符号链接边界检查。命令使用参数数组而不是字符串拼接。`Allrun`、动态编译、`#codeStream` 和 coded 条件按代码执行审查；不可因为它是 CFD 字典就绕过执行安全规则。

保护原算例和检查点；并发必须满足 CPU、内存、磁盘及 I/O 配额。失联时先核对进程/调度器，再决定重试。重放请求不能重复启动昂贵计算。

GitHub 发布应保留已有许可证和第三方归属，逐依赖核验许可证、提交与分发方式；未确认授权的代码不复制。新核心不能替上游或 OpenFOAM 重新授权。大体场和敏感几何不进入 Git 历史，示例数据要有来源与使用权限。

### 13.1 安全分级与供应链准入

建议将操作按 read、prepare、run、modify_model、publish/delete 分级。只读查询与已批准预算内的确定性步骤可自动运行；新增代码执行、物理模型修改、超预算运行和破坏性操作需与风险匹配的明确授权。权限由认证后的策略层决定，不能由 LLM 文字或工具的 readOnlyHint 自我声明决定。MCP 官方规范将未受信服务器的工具 annotations 视为不可信信息。[S22]

远程网关校验令牌的受众与最小权限范围；不要把客户端给 MCP 的 token 原样转发给下游服务。严格限制可访问的远端地址与重定向、防止 SSRF，并对日志/报告做密钥和个人路径脱敏。[S25]

上游升级需固定提交、审查依赖和权限差异、重跑契约测试及小型真实案例。未知 plugin/skill 先进入只读或隔离试验区。截图驱动交互与通用 Python 执行不列为默认生产权限。

## 14. 实施顺序与发布门槛

| 阶段 | 实施内容 | 验收重点 |
| --- | --- | --- |
| P0 | 非有限数漏洞回归、状态/契约迁移、物理语义、能力准入 | NaN/Inf不能误过；不破坏现有 CLI 和历史结果 |
| P1 | 事务化 job store、启动核对、检查点、取消、证据图 | 小算例真实闭环；不确定状态不重复启动；变更使相关结论失效 |
| P2 | 网格/时间步/域研究、HPC 选择、统计证据 | 不可判定场景、并行回退、噪声和样本相关性测试 |
| P3 | ParaView 配方、CSV、统一报告、独立审查 | 数据—脚本—图表可追溯且可重放 |
| P4 | SLURM 等调度器及可选 VibeFlow 控制台 | CLI 独立可用、远程授权与作业状态一致 |

新增独立的 `tests/contracts`、`tests/fault_injection` 和 `tests/scientific` 证据类别，分别测试接口、断线/故障恢复、数值判据。真实 OpenFOAM 测试跑在隔离的受信 worker 上，不让未审查的外部 PR 直接使用生产自托管 runner。

发布指标不只看“算例运行成功率”，还包括错误放行、不可判定识别、断线恢复、数据溯源完整性、费用/资源预算及人工介入次数。具体容限由测试集和用例说明，不编造行业统一成功率。

先使用小型层流通道/方腔测试执行与守恒，再使用非定常绕流测试统计，最后增加 VOF 等复杂 profile。示例必须明确是解析/实验比较、真实求解输出，还是仅供解析器测试的合成 fixture。

README 的功能矩阵分为“已实现且受测”“实验性”“计划中”。必须附实际环境、命令、输入哈希、结果和失败信息才能宣称通过端到端测试。**文档完备不等于软件已完工。**

## 15. 主要一手来源

S01–S20 为前版来源；未再次打开的条目保留 2026-09-04 核验日期。V2 重新读取目标仓库 README、S16/S17 及以下新增资料；具体核验范围见《V2 来源与核验范围》。实际集成时仍需固定提交并验证。

- [S01] [目标仓库 README](https://github.com/hamletroyophelia/openfoam-cfd-agents/blob/main/README.md)
- [S02] [目标仓库架构](https://github.com/hamletroyophelia/openfoam-cfd-agents/blob/main/docs/ARCHITECTURE.md)
- [S03] [VibeFlow introduction](https://docs.vibeflow.ai/introduction)
- [S04] [VibeFlow MCP Node](https://docs.vibeflow.ai/nodes/mcp-node)
- [S05] [VibeFlow GitHub integration](https://docs.vibeflow.ai/features/github-integration)
- [S06] [VibeFlow MCP service](https://docs.vibeflow.ai/features/mcp)
- [S07] [Foam-Agent](https://github.com/csml-rpi/Foam-Agent)
- [S08] [AI-CFD-Scientist](https://github.com/csml-rpi/AI-CFD-Scientist)
- [S09] [HPC-Skills](https://github.com/SciMate-AI/HPC-Skills)
- [S10] [HPC-Skills / hpc-openfoam](https://github.com/SciMate-AI/HPC-Skills/blob/main/skills/hpc-openfoam/SKILL.md)
- [S11] [milsonson/openfoam-mcp](https://github.com/milsonson/openfoam-mcp)
- [S12] [openfoam-claude-suite](https://github.com/swtbkim/openfoam-claude-suite)
- [S13] [OpenFOAM_expert_SKILL](https://github.com/Zyzhan417/OpenFOAM_expert_SKILL)
- [S14] [viznoir](https://github.com/kimimgo/viznoir)
- [S15] [LLNL ParaView MCP](https://github.com/llnl/paraview_mcp)
- [S16] [Foundation v14 solver modules](https://doc.cfd.direct/openfoam/user-guide-v14/solvers-modules)
- [S17] [NASA: Examining Spatial (Grid) Convergence](https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html)
- [S18] [Oliver et al.: Estimating Uncertainties in Statistics Computed from DNS](https://arxiv.org/abs/1311.0828)
- [S19] [ParaView: Batch Python Scripting](https://docs.paraview.org/en/latest/Tutorials/SelfDirectedTutorial/batchPythonScripting.html)
- [S20] [ParaView: Saving Results](https://docs.paraview.org/en/latest/UsersGuide/savingResults.html)

### V2 新增来源

- [S21] [目标仓库 domain.py](https://github.com/hamletroyophelia/openfoam-cfd-agents/blob/main/src/openfoam_cfd_agents/domain.py)，通过已连接 GitHub 读取；blob `fffca99ea7dd09cad98357ae3590d58381d75d7e`。
- [S22] [MCP 2026-07-28 Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)。
- [S23] [MCP SEP-2663 Tasks Extension](https://modelcontextprotocol.io/seps/2663-tasks-extension)，作为版本迁移背景；实施以所选协议版本的规范为准。
- [S24] [MCP Python SDK 旧 Tasks 接口](https://py.sdk.modelcontextprotocol.io/v1/experimental/tasks-server/)。
- [S25] [MCP 2026-07-28 Security Best Practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices)。
- [S26] [ParaView Remote and parallel visualization](https://docs.paraview.org/en/latest/ReferenceManual/parallelDataVisualization.html)。
- [S27] [NASA Overview of CFD Verification & Validation](https://www.grc.nasa.gov/www/wind/valid/tutorial/overview.html)。
- [S28] [官方 PyFluent 文档](https://fluent.docs.pyansys.com/version/stable/)。
- [S29] [CAE-Agent-Hub README](https://github.com/Cai-aa/CAE-Agent-Hub)，仅作为跨 CAE 适配与轻量 viewer 的可选参考；未安装或认证其功能。

微信报告链接仅作为待对照资料，未被当作论据：[用户提供的报告](https://mp.weixin.qq.com/s/B-Hn3eEcaUty5Gf5enUVow)。
