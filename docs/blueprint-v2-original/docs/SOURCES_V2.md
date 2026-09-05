# V2 来源与核验范围

核验日期：2026-09-05。以一手文档与实际读取的源文件为依据。下表的设计决定是本方案提出的，不意味着来源作者做出了同样的产品建议。

| 来源 | 本次确认的事实/范围 | 对设计的影响 |
| --- | --- | --- |
| [用户提供的微信报告](https://mp.weixin.qq.com/s/B-Hn3eEcaUty5Gf5enUVow) | 未读取；直接打开失败，题名/地址搜索未找到可核验转载；未获取正文 | 不引用报告内容，不虚构作者论点；待正文后才能逐条对照 |
| [仓库 README](https://github.com/hamletroyophelia/openfoam-cfd-agents/blob/main/README.md) | 通过 GitHub connector 读取；仍标记 Phase 1 MVP，许多生产模块待实现 | 保留核心，按实际功能而非目标清单安排开发 |
| [仓库 domain.py](https://github.com/hamletroyophelia/openfoam-cfd-agents/blob/main/src/openfoam_cfd_agents/domain.py) | 读取到的比较函数未过滤非有限浮点数；状态尚未完整分层 | 优先修复判定输入、补负向测试，再做功能扩展 |
| [MCP Tools 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) | 存在 schema、结构化结果、资源链接；未受信工具 annotations 不可被直接信任 | 定义 CFD 业务契约，工具提示不能代替权限策略 |
| [MCP SEP-2663](https://modelcontextprotocol.io/seps/2663-tasks-extension) 与 [旧 SDK Tasks 文档](https://py.sdk.modelcontextprotocol.io/v1/experimental/tasks-server/) | Tasks 从早期实验接口向扩展演进；旧 SDK 实验接口标记弃用 | 核心 job 模型独立，协议和 SDK 兼容层可替换 |
| [MCP Security Best Practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices) | 描述令牌透传、SSRF、权限与本地服务风险 | 令牌受众校验、最小权限、受限网络、脱敏 |
| [Foundation v14 solver modules](https://doc.cfd.direct/openfoam/user-guide-v14/solvers-modules) | 模块化求解器及 foamRun 路径；不同模块有明确物理范围 | 能力矩阵细分到发行分支、模块与操作，不能泛称兼容 OpenFOAM |
| [ParaView remote visualization](https://docs.paraview.org/en/latest/ReferenceManual/parallelDataVisualization.html) | 服务端处理/渲染以减少客户端数据传输 | 完整体场留计算侧，客户端拿摘要与预览 |
| [NASA V&V overview](https://www.grc.nasa.gov/www/wind/valid/tutorial/overview.html) 与 [grid convergence](https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html) | verification 与 validation 的作用不同，网格研究有适用前提 | 解析对照不等同于物理验证；独立展示证据类别 |
| [PyFluent 官方文档](https://fluent.docs.pyansys.com/version/stable/) | 提供设置、执行、监控、结果提取的 Python 接口；版本兼容有边界 | 未来 Fluent adapter 原生 API 优先，仍需真实环境测试 |
| [CAE-Agent-Hub](https://github.com/Cai-aa/CAE-Agent-Hub) | README 展示多个 CAE MCP、skills 与轻量 viewer | 可借鉴适配与预览分层，不扩大首发为全 CAE 平台 |

原方案中其他项目的能力说明继承自 2026-09-04 的调研，未因此自动成为 2026-09-05 的重新认证结果。本包没有统计 GitHub star 排名，也未用 star、README 的 Active 或工具数量作为科学可信度指标。

没有运行新增 MCP、OpenFOAM、MPI、ParaView 或商业求解器集成；没有验证所有新接口。新增配置为设计示例，不保证当前仓库 CLI 可直接读取。
