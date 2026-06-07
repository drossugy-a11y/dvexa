"""Analysis Score — 分析评分模型

贝叶斯平滑 + 连续失败追踪。
"""

from __future__ import annotations
from dataclasses import dataclass
import time

PRIOR_SUCCESS = 8
PRIOR_TOTAL = 10
PRIOR_FAILURE = PRIOR_TOTAL - PRIOR_SUCCESS
MINIMUM_SAMPLES = 10
CONSECUTIVE_FAILURE_THRESHOLD = 3
RECOVERY_SUCCESS_THRESHOLD = 3


@dataclass
class AnalysisScore:
    """分析工具评分。"""
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
        successes = int(round(self.success_rate * self.usage)) if self.usage > 0 else 0
        return (successes + PRIOR_SUCCESS) / (self.usage + PRIOR_TOTAL)

    @property
    def combined_score(self) -> float:
        latency_score = max(0.0, 1.0 - self.latency / 10.0) if self.latency > 0 else 1.0
        return (
            0.5 * self.bayesian_success_rate
            + 0.2 * self.stability
            + 0.2 * (1.0 - self.error_rate)
            + 0.1 * latency_score
        )

    def record_success(self, latency: float = 0.0):
        prev = self.success_rate * self.usage
        self.usage += 1
        self.success_rate = (prev + 1.0) / self.usage
        self.error_rate = (self.error_rate * (self.usage - 1)) / self.usage
        self.latency = (self.latency * (self.usage - 1) + latency) / self.usage
        self.stability = min(1.0, self.stability + 0.01)
        self.consecutive_failures = 0
        self.last_success_at = time.time()

    def record_failure(self, latency: float = 0.0, error: str = ""):
        prev_success = self.success_rate * self.usage
        self.usage += 1
        self.success_rate = prev_success / self.usage
        self.error_rate = (self.error_rate * (self.usage - 1) + 1.0) / self.usage
        self.latency = (self.latency * (self.usage - 1) + latency) / self.usage
        self.stability = max(0.0, self.stability - 0.05)
        self.last_error = error[:200] if error else None
        self.consecutive_failures += 1
