# V2 源码审查：非有限数值验收

检查日期：2026-09-05。仓库：`hamletroyophelia/openfoam-cfd-agents`。

读取的 `domain.py` blob 为 `fffca99ea7dd09cad98357ae3590d58381d75d7e`。读取的 README blob 为 `cd810969f69e6546f94616194c85324ed4eb65ec`。blob 标识具体文件版本，不是整个仓库的 commit SHA。

## 发现

`_evaluate_rule` 对 observed 做 int/float 类型检查并排除 bool，但比较前没有有限数检查；threshold 也没有对应的有限数前置约束。以下特定组合可能给出 passed：

| 输入 | 运算结果 | 应采取的策略 |
| --- | --- | --- |
| observed 为 NaN，规则 `!= 0` | True | 拒绝非有限指标 |
| observed 为 +Inf，规则 `>= 0` | True | 拒绝非有限指标 |
| observed 为 -Inf，规则 `<= 1` | True | 拒绝非有限指标 |
| threshold 为 NaN，规则 `!=` | True | 配置校验拒绝非有限阈值 |

不是所有 NaN 比较都会通过；这里描述的是存在误放行的输入组合，不是声称真实已有 CFD 算例遭到误判。

## 修复要求

对 observed 与 threshold 使用一致的有限数策略；保持布尔值不被当数值证据。缺失、非有限数、定义/单位不匹配、过期证据均不得产生 passed。保留原始证据，在 JSON 中用 null 和明确 validity/reason 表示异常。禁止依赖特殊浮点数比较为业务语义兜底。

针对所有六种比较符加入回归用例；正常有限数行为保持兼容。新增 schema 字段使用显式迁移，不回写历史 manifest。更换规则只能产生新判定，不能篡改过去判定。

## 本次验证边界

已完成：读取源码与 README、独立 Python 浮点比较复现、记录文件 blob。

未完成：克隆完整仓库、安装项目依赖、执行其测试、提交补丁或运行求解器。`validation/finite_comparison_probe.json` 仅为浮点行为复现，不是仓库测试通过证明。

来源：[domain.py](https://github.com/hamletroyophelia/openfoam-cfd-agents/blob/main/src/openfoam_cfd_agents/domain.py)。
