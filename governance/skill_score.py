"""Skill Score — 能力评分模型（v1.87 Resilience）

贝叶斯平滑 + 连续失败追踪 + 恢复机制。
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time

# 贝叶斯先验（小样本保护）
PRIOR_SUCCESS = 8
PRIOR_TOTAL = 10
PRIOR_FAILURE = PRIOR_TOTAL - PRIOR_SUCCESS

# 最小样本阈值（低于此值禁止降级）
MINIMUM_SAMPLES = 10

# 连续失败阈值（触发 quarantined）
CONSECUTIVE_FAILURE_THRESHOLD = 3

# 恢复成功阈值（连续成功 N 次即可恢复）
RECOVERY_SUCCESS_THRESHOLD = 3


@dataclass
class SkillScore:
    """技能评分 — 运行时可观测指标（v1.87）。

    success_rate:      原始成功率 0.0~1.0
    latency:           平均延迟（秒）
    stability:         稳定性 0.0~1.0
    usage:             调用次数
    error_rate:        原始错误率 0.0~1.0
    last_error:        最后一次错误信息
    consecutive_failures: 连续失败次数
    last_success_at:   上次成功时间戳
    recovery_attempts: 恢复尝试次数
    """
    success_rate: float = 1.0
    latency: float = 0.0
    stability: float = 1.0
    usage: int = 0
    error_rate: float = 0.0
    last_error: str | None = None
    consecutive_failures: int = 0
    last_success_at: float = 0.0
    recovery_attempts: int = 0

    @property
    def bayesian_success_rate(self) -> float:
        """贝叶斯平滑成功率 — 小样本不剧烈波动。"""
        successes = int(round(self.success_rate * self.usage)) if self.usage > 0 else 0
        return (successes + PRIOR_SUCCESS) / (self.usage + PRIOR_TOTAL)

    @property
    def bayesian_error_rate(self) -> float:
        """贝叶斯平滑错误率。"""
        failures = int(round(self.error_rate * self.usage)) if self.usage > 0 else 0
        return (failures + PRIOR_FAILURE) / (self.usage + PRIOR_TOTAL)

    @property
    def combined_score(self) -> float:
        """综合评分（0.0~1.0）— 使用贝叶斯平滑版本。

        权重：
          bayesian_success_rate: 50%
          stability: 20%
          (1 - bayesian_error_rate): 20%
          latency: 10%
        """
        latency_score = max(0.0, 1.0 - self.latency / 10.0) if self.latency > 0 else 1.0
        return (
            0.5 * self.bayesian_success_rate
            + 0.2 * self.stability
            + 0.2 * (1.0 - self.bayesian_error_rate)
            + 0.1 * latency_score
        )

    def record_success(self, latency: float = 0.0):
        """记录一次成功调用。"""
        prev = self.success_rate * self.usage
        self.usage += 1
        self.success_rate = (prev + 1.0) / self.usage
        self.error_rate = (self.error_rate * (self.usage - 1)) / self.usage
        self.latency = (self.latency * (self.usage - 1) + latency) / self.usage
        self.stability = min(1.0, self.stability + 0.01)
        self.consecutive_failures = 0
        self.last_success_at = time.time()

    def record_failure(self, latency: float = 0.0, error: str = ""):
        """记录一次失败调用。"""
        prev_success = self.success_rate * self.usage
        self.usage += 1
        self.success_rate = prev_success / self.usage
        self.error_rate = (self.error_rate * (self.usage - 1) + 1.0) / self.usage
        self.latency = (self.latency * (self.usage - 1) + latency) / self.usage
        self.stability = max(0.0, self.stability - 0.05)
        self.last_error = error[:200] if error else None
        self.consecutive_failures += 1
