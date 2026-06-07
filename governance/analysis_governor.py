"""Analysis Governor — 分析质量管控

核心职责：
  1. 分析工具质量评分（贝叶斯平滑）
  2. 分析工具生命周期管理
  3. 分析工具选择（带降级权重）
  4. 恢复机制
"""

from __future__ import annotations
import time

from governance.analysis_score import AnalysisScore, MINIMUM_SAMPLES
from governance.lifecycle import SkillStatus, evaluate_lifecycle, evaluate_recovery
from governance.tool_policy import ToolPolicy, is_tool_allowed, resolve_policy, expand_tool_list

STATUS_WEIGHTS = {
    SkillStatus.STABLE: 1.0,
    SkillStatus.ACTIVE: 1.0,
    SkillStatus.RECOVERED: 1.0,
    SkillStatus.EXPERIMENTAL: 0.9,
    SkillStatus.DEGRADED: 0.5,
    SkillStatus.QUARANTINED: 0.0,
    SkillStatus.REMOVED: 0.0,
}


class AnalysisGovernor:
    """分析质量管控中心。"""

    def __init__(self):
        self._scores: dict[str, AnalysisScore] = {}
        self._statuses: dict[str, SkillStatus] = {}
        self._policies: dict[str, ToolPolicy | None] = {}
        self._global_policy: ToolPolicy | None = None
        self._recovery_verifications: dict[str, int] = {}

    def register(self, name: str):
        self._scores[name] = AnalysisScore()
        self._statuses[name] = SkillStatus.EXPERIMENTAL
        self._policies[name] = None

    def set_policy(self, name: str, policy: ToolPolicy):
        self._policies[name] = policy

    def set_global_policy(self, policy: ToolPolicy):
        self._global_policy = policy

    def get_policy(self, name: str) -> ToolPolicy:
        return resolve_policy(
            skill_specific=self._policies.get(name),
            global_policy=self._global_policy,
        )

    def check_skill_allowed(self, name: str) -> bool:
        policy = self.get_policy(name)
        expanded = expand_tool_list(policy.allow)
        if "all" in policy.allow:
            return True
        if not expanded:
            return is_tool_allowed(ToolPolicy(allow=[], deny=policy.deny), name)
        return is_tool_allowed(policy, name)

    def record_call(self, name: str, success: bool = True, latency: float = 0.0, error: str = ""):
        score = self._scores.get(name)
        if not score:
            return
        if success:
            score.record_success(latency)
        else:
            score.record_failure(latency, error)
        current = self._statuses.get(name, SkillStatus.EXPERIMENTAL)
        new_status = evaluate_lifecycle(current, score)
        if score.usage < MINIMUM_SAMPLES and new_status in (SkillStatus.DEGRADED, SkillStatus.QUARANTINED):
            new_status = current
        if new_status != current:
            self._statuses[name] = new_status

    def try_recovery(self, name: str) -> bool:
        if self._statuses.get(name) != SkillStatus.QUARANTINED:
            return False
        score = self._scores.get(name)
        if not score:
            return False
        result = evaluate_recovery(score)
        if result == "recovered":
            self._statuses[name] = SkillStatus.RECOVERED
            score.recovery_attempts += 1
            return True
        if result == "failed":
            score.recovery_attempts += 1
        return False

    def get_score(self, name: str) -> AnalysisScore | None:
        return self._scores.get(name)

    def get_status(self, name: str) -> SkillStatus:
        return self._statuses.get(name, SkillStatus.EXPERIMENTAL)

    def get_routing_weight(self, name: str) -> float:
        status = self._statuses.get(name, SkillStatus.EXPERIMENTAL)
        return STATUS_WEIGHTS.get(status, 0.0)

    def list_all(self) -> list[dict]:
        result = []
        for name in self._scores:
            score = self._scores[name]
            status = self._statuses.get(name, SkillStatus.EXPERIMENTAL)
            result.append({
                "name": name,
                "status": status.value,
                "combined_score": score.combined_score,
                "usage": score.usage,
                "consecutive_failures": score.consecutive_failures,
                "routing_weight": self.get_routing_weight(name),
            })
        return result

    def quarantine_count(self) -> int:
        return sum(1 for s in self._statuses.values() if s == SkillStatus.QUARANTINED)

    def ecosystem_stability_score(self) -> float:
        total = len(self._scores)
        if total == 0:
            return 1.0
        active = sum(1 for s in self._statuses.values()
                     if s in (SkillStatus.ACTIVE, SkillStatus.STABLE, SkillStatus.RECOVERED))
        quarantined = self.quarantine_count()
        return round((active / total) * (1.0 - quarantined / total), 3)

    def wrap_handler(self, name: str, handler) -> '_GovernedHandler':
        return _GovernedHandler(name, handler, self)


class _GovernedHandler:
    def __init__(self, name: str, handler, governor: AnalysisGovernor):
        self._name = name
        self._handler = handler
        self._governor = governor

    def call(self, input_data) -> dict:
        start = time.time()
        try:
            result = self._handler.call(input_data)
            latency = time.time() - start
            is_error = isinstance(result, dict) and "error" in result
            self._governor.record_call(self._name, success=not is_error, latency=latency)
            return result
        except Exception as e:
            latency = time.time() - start
            self._governor.record_call(self._name, success=False, latency=latency, error=str(e))
            return {"error": f"{self._name} 调用异常: {str(e)}"}
