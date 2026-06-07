"""Skill Lifecycle — 能力生命周期管理（v1.87 Resilience）

生命周期路径：
  experimental → active → stable → degraded → quarantined → recovered → active

关键变更：
  - 移除自动 REMOVED（仅人工清理）
  - 新增 minimum_samples 保护（小样本禁止降级）
  - 新增 consecutive_failures 准入门槛
  - 新增 recovery 恢复路径
"""

from __future__ import annotations
from enum import Enum
from governance.analysis_score import AnalysisScore, MINIMUM_SAMPLES, CONSECUTIVE_FAILURE_THRESHOLD, RECOVERY_SUCCESS_THRESHOLD


class SkillStatus(Enum):
    EXPERIMENTAL = "experimental"
    ACTIVE = "active"
    STABLE = "stable"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"
    RECOVERED = "recovered"
    REMOVED = "removed"

    def __str__(self):
        return self.value


# 升降级阈值
PROMOTE_TO_ACTIVE_RATE = 0.85
PROMOTE_TO_STABLE_RATE = 0.95
PROMOTE_TO_STABLE_USAGE = 50
DEMOTE_TO_DEGRADED_RATE = 0.3      # error_rate >= 0.3
DEMOTE_TO_QUARANTINED_RATE = 0.5   # error_rate >= 0.5

# 恢复阈值
RECOVERY_CONFIRM_USAGE = 5  # 恢复验证期至少调用次数


def evaluate_lifecycle(current_status: SkillStatus, score: AnalysisScore) -> SkillStatus:
    """根据运行时指标评估 skill 应处的生命周期阶段。

    v1.87 规则：
      - REMOVED 仅人工触发，governance 不可自动设置
      - usage < MINIMUM_SAMPLES 时禁止降级（只允许升级）
      - QUARANTINED 需要连续失败次数达到阈值
    """
    if current_status == SkillStatus.REMOVED:
        return SkillStatus.REMOVED

    # ─── 降级检查（需满足 minimum_samples + 连续失败准入门槛）───────

    if score.usage >= MINIMUM_SAMPLES:
        # QUARANTINED: 高错误率 + 连续失败
        if (score.error_rate >= DEMOTE_TO_QUARANTINED_RATE
                and score.consecutive_failures >= CONSECUTIVE_FAILURE_THRESHOLD):
            if current_status in (SkillStatus.ACTIVE, SkillStatus.STABLE, SkillStatus.DEGRADED):
                return SkillStatus.QUARANTINED

        # DEGRADED: 错误率偏高
        if score.error_rate >= DEMOTE_TO_DEGRADED_RATE:
            if current_status in (SkillStatus.ACTIVE, SkillStatus.STABLE):
                return SkillStatus.DEGRADED

    # 小样本时：仅记录 warning 但不降级（由 calling code 处理）

    # ─── 升级检查 ────────────────────────────────────────────────────

    if current_status == SkillStatus.EXPERIMENTAL:
        if score.bayesian_success_rate >= PROMOTE_TO_ACTIVE_RATE:
            return SkillStatus.ACTIVE
        return SkillStatus.EXPERIMENTAL

    if current_status == SkillStatus.ACTIVE:
        if (score.bayesian_success_rate >= PROMOTE_TO_STABLE_RATE
                and score.usage >= PROMOTE_TO_STABLE_USAGE):
            return SkillStatus.STABLE
        return SkillStatus.ACTIVE

    if current_status == SkillStatus.DEGRADED:
        if score.error_rate < DEMOTE_TO_DEGRADED_RATE and score.bayesian_success_rate > PROMOTE_TO_ACTIVE_RATE:
            return SkillStatus.ACTIVE  # 从 degraded 恢复
        return SkillStatus.DEGRADED

    if current_status == SkillStatus.QUARANTINED:
        # QUARANTINED 不自动升级，由 evaluate_recovery 处理
        return SkillStatus.QUARANTINED

    if current_status == SkillStatus.RECOVERED:
        if score.usage >= RECOVERY_CONFIRM_USAGE and score.error_rate < DEMOTE_TO_DEGRADED_RATE:
            return SkillStatus.ACTIVE
        return SkillStatus.RECOVERED

    return current_status


def evaluate_recovery(score: AnalysisScore) -> str:
    """评估 quarantined skill 是否可以恢复。

    Returns:
        "recovered": 符合恢复条件
        "pending": 尚在验证期
        "failed": 恢复尝试失败
    """
    if score.consecutive_failures > 0:
        return "failed"

    # 连续成功次数达到阈值 → 可恢复
    # 从最近一次成功往前推：如果连续成功次数 = usage - 失败次数
    # 简化：consecutive_failures == 0 且 usage > 0 且最近一次成功
    if score.consecutive_failures == 0 and score.usage >= RECOVERY_SUCCESS_THRESHOLD:
        return "recovered"

    return "pending"


def validate_transition(from_status: SkillStatus, to_status: SkillStatus) -> bool:
    """验证生命周期转换是否合法。

    v1.87 允许路径:
      EXPERIMENTAL → ACTIVE
      ACTIVE → STABLE
      STABLE → DEGRADED
      DEGRADED → QUARANTINED
      QUARANTINED → RECOVERED
      RECOVERED → ACTIVE
      DEGRADED → ACTIVE（恢复）
      任何状态 → REMOVED（仅人工）
    """
    # REMOVED 只能人工设，但允许从任何状态进入
    if to_status == SkillStatus.REMOVED:
        return True

    # 允许的向前路径
    forward = {
        SkillStatus.EXPERIMENTAL: {SkillStatus.ACTIVE},
        SkillStatus.ACTIVE: {SkillStatus.STABLE, SkillStatus.DEGRADED},
        SkillStatus.STABLE: {SkillStatus.DEGRADED},
        SkillStatus.DEGRADED: {SkillStatus.QUARANTINED, SkillStatus.ACTIVE},
        SkillStatus.QUARANTINED: {SkillStatus.RECOVERED},
        SkillStatus.RECOVERED: {SkillStatus.ACTIVE, SkillStatus.DEGRADED},
    }
    allowed = forward.get(from_status, set())
    return to_status in allowed
