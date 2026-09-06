# OpenFOAM CFD Agents

[English](README.md) · [0.4.1 论文式科学可视化](examples/cylinder-t300/README.md) · [原始 V2 蓝图](docs/blueprint-v2-original/README.md)

面向 **Foundation OpenFOAM v14** 的确定性 CFD 工作流核心。Agent 可以提出建议，
阶段是否通过由数值规则决定。当前提供可靠性工具、适配器及 Linux systemd 常驻
作业 worker；完整无人值守建模、资源调度和科学分析流水线仍在规划中。

本版把 SQLite 作业账本接入真实执行后端，支持持久提交、worker 重启后核对、
按进程身份取消及日志保存；结合圆柱恢复修正 FPE 启动提示误报和 MPI 主机槽位。
0.2.0 的检查点、物理核检查、持久进度和有限数值规则继续保留。

0.4.0 增加只读算例后处理：严格核对全部分区和完整时间步，用 ParaView `pvbatch`
输出固定色标的速度、涡量和真实三维 Q* 图，并用独立 Python 环境分析原始 Cd 历史。
[圆柱 t=300 样板](examples/cylinder-t300/README.md)包含 3200×1800 图、原始提取数据、
ParaView 状态、静态图集、manifest 和逐图 QA；可复用流程位于
`.agents/skills/cfd-visualization/SKILL.md`。

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

使用 `cfd-workflow jobs submit/status/cancel/worker` 管理受信本地作业，具体安装、
常驻服务、验证和限制见 [worker 说明](docs/WORKER_V3.md)。蓝图的 24 项验收尚未全部
覆盖，认证网关和自动科学验收仍未实现。服务器圆柱已按授权单独恢复；小球保留原进程。
两个生产求解器继续使用原有 tmux 托管，新 worker 的生命周期验证使用隔离测试进程。

Apache-2.0，见 [LICENSE](LICENSE)。不随仓库发布服务器密钥、原始大体场或专属主机配置。
