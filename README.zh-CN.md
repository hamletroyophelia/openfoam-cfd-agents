# OpenFOAM CFD Agents

[English](README.md) · [0.2.0 实现与边界](docs/RELIABILITY_V2.md) · [原始 V2 蓝图](docs/blueprint-v2-original/README.md)

面向 **Foundation OpenFOAM v14** 的确定性 CFD 工作流核心。Agent 可以提出建议，
阶段是否通过由数值规则决定。当前提供可靠性工具和适配器，完整无人值守建模、
常驻作业 worker、调度器及科学分析流水线仍在规划中。

本版结合服务器小球与圆柱算例，修复 NaN/Inf 误放行、v14 时间格式漏读和 MPI
通信错误漏报，增加检查点候选检查、物理核冲突检测、持久进度观察和 SQLite 作业账本。

## 安装

Linux 使用 Python 3.11 或更新版本；服务器自带 Python 3.10 时需要单独环境。

```bash
git clone https://github.com/hamletroyophelia/openfoam-cfd-agents.git
cd openfoam-cfd-agents
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
source /opt/openfoam14/etc/bashrc
cfd-workflow probe-runtime --solver-module incompressibleVoF
```

Windows PowerShell 7 可运行日志分析、CPU 清单检查、作业账本和报告；
`live-monitor` 的进程身份检查需要 Linux `/proc`。Windows 安装命令见英文 README。

## 使用

```bash
# 全日志数值检查；VOF 容限须来自自己的算例，不是通用物理标准。
cfd-workflow monitor /path/to/log.solver --max-courant 0.9 \
  --max-interface-courant 0.55 --alpha-tolerance 0.000002

# 在全部分区中选择可用候选；真实续算必须列出全部必要历史字段。
cfd-workflow checkpoint /path/to/case --processes 4 --fields U,p

# 核查拓扑，识别逻辑核对应的同一个物理核心。
lscpu -p=CPU,CORE,SOCKET,NODE > topology.csv
cfd-workflow audit-cpus topology.csv --cpus 0-3 --reserved 4-7

# 每次调用做一次只读观察。重复调用时保留同一 job-id 和 state。
cfd-workflow live-monitor /path/to/log.solver --pid 1234 --job-id case-attempt-1 \
  --state /path/to/monitor/state.json --stall-seconds 300

# 仅生成续算计划：不改字典，不重分区，不启动求解器。
cfd-workflow plan-run /path/to/case --processes 4 --restart-time 1.0 \
  --fields U,p --shared-memory-mpi --output restart-plan.json
```

状态不通过时退出码为 `2`。首次实时观察建立基线，也返回 `2`；后续必须实测到
已完成时间步推进才可能通过。保留故障状态的监控文件不能跨新作业复用。
2 MiB 尾部采样不覆盖采样区间之外的历史错误，全日志检查和运行日志分段仍有必要。

`--shared-memory-mpi` 仅适用于单机 Open MPI 4.x，经验证才使用；不适用于多机，
不修改全局 MPI 配置，也不自动设置 CPU/NUMA 绑定。CPU 检查输出同样不等于资源预留。
检查点通过只说明字段封装和时间元数据符合条件，仍须确认进程停止、网格/物理一致、
字段数据可读并执行适当的恢复试验。`U,p` 只是简单算例示例，VOF 和时间格式可能
需要更多历史字段。

字段名包含逗号时，使用 JSON 数组保留完整名称，例如
`--fields '["U","CrankNicolson:ddt0(rho,U)"]'`。这仍只是语法示例，
真实清单必须包含该算例的全部必要字段。

## 交付状态

新实现和负向测试以 [可靠性说明](docs/RELIABILITY_V2.md) 为准；蓝图中的 24 项
验收规范没有全部转化为端到端能力。作业账本及证据依赖目前是 Python 库接口，
未接入常驻 worker 或认证网关。服务器验证为隔离的只读检查，没有重启生产算例。

Apache-2.0，见 [LICENSE](LICENSE)。不随仓库发布服务器密钥、原始大体场或专属主机配置。
