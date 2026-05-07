"""Control Boundary Filter（CBF）— DVexa v1.6 控制稳定性强化

职责：
  1. 统一清洗所有从 executor 返回给 kernel 的数据
  2. 剥离所有非控制信号（confidence/score/risk/validation/suggestion）
  3. 确保 kernel 只看"事实"，不看"评价"

CBF 定位：
  Kernel ← CBF ← Executor ← Tool
            ↑
  唯一的数据净化关口

v1.6 强化：
  - 明确为 CBF（Control Boundary Filter），不再只是 ControlGuard
  - 所有"智能信号"被彻底视为"数据噪声"并剥离
  - 决策输入白名单在 sanitize 中强制执行
"""

from enum import Enum


class ControlSignal(Enum):
    """Kernel 唯一允许接受的决策信号类型。

    所有决策只能基于这些信号。
    任何不在此列表中的信号，CBF 在 sanitize 阶段自动剥离。
    """
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    RETRY_EXCEEDED = "retry_exceeded"
    PLAN_READY = "plan_ready"
    EXECUTION_RESULT = "execution_result"


# CBF 清洗黑名单 — 这些字段即使存在，也会被 sanitize 强制移除
CBF_BLOCKLIST = {
    "confidence",
    "score",
    "risk",
    "validation",
    "suggestion",
    "status",
    "tool",
    "tool_metadata",
    "heuristic_suggestion",
    "validation_result",
}


class CBF:
    """Control Boundary Filter — 控制边界过滤器。

    统一清洗所有从 executor 返回给 kernel 的数据。
    只保留 kernel 决策真正需要的纯净字段。
    """

    # kernel 只允许接收这些字段
    ALLOWED_FIELDS = {"step_id", "output"}

    @classmethod
    def sanitize(cls, result: dict) -> dict:
        """清洗执行结果：只保留 kernel 允许的字段。

        从 executor 返回的数据经过 CBF 后：
          - 允许通过: step_id, output
          - 自动剥离: confidence, score, risk, validation, status,
                     tool, input, suggestion, 及其他所有非允许字段

        Args:
            result: executor.execute_step() 的原始返回

        Returns:
            仅含 step_id 和 output 的纯净字典
        """
        return {k: v for k, v in result.items() if k in cls.ALLOWED_FIELDS}

    @classmethod
    def assert_signal(cls, signal_type: str):
        """断言信号在控制白名单中。

        用于 kernel 决策点的防御性检查。
        如果未来有人试图将 blocked 信号接入控制流，这里会立即失败。
        """
        if signal_type not in ControlSignal._value2member_map_:
            raise ValueError(
                f"[CBF] 禁止信号 '{signal_type}' 试图进入控制流。"
                f" 允许的信号: {[s.value for s in ControlSignal]}"
            )

    @classmethod
    def verify(cls, result: dict) -> None:
        """验证结果是否已被清洗（测试用断言）。

        检查 result 中是否包含 blocked 字段。
        用于测试和审计，确保 sanitize 正确执行。
        """
        violations = CBF_BLOCKLIST & set(result.keys())
        if violations:
            raise AssertionError(
                f"[CBF] 检测到未清洗的禁止字段: {violations}"
            )
