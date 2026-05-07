"""外部能力接入层 — External Capability Layer（v1.88）

外部 agent 永远只是"能力来源"，不是"控制来源"。

约束：
  - 禁止外部 agent 进入 kernel 控制流
  - 禁止外部 agent 参与 routing 决策
  - 禁止外部 agent 修改 governance
  - 禁止外部 agent 修改 memory
  - 禁止外部 agent 直接调用 planner/executor
"""

from __future__ import annotations
