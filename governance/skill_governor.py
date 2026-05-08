"""Skill Governor — 能力治理中心（v1.87 Resilience）

核心职责：
  1. skill 质量评分（贝叶斯平滑）
  2. skill 生命周期管理（minimum_samples 保护）
  3. skill 冲突检测
  4. 最优 skill 选择（带降级权重）
  5. 恢复机制
"""

from __future__ import annotations
import time

from capabilities.skill import SkillRegistry, SkillDef
from governance.skill_score import SkillScore, MINIMUM_SAMPLES
from governance.lifecycle import SkillStatus, evaluate_lifecycle, evaluate_recovery
from governance.conflict_detector import ConflictDetector, SkillConflict
from governance.tool_policy import ToolPolicy, is_tool_allowed, resolve_policy, default_policy, expand_tool_list

# Routing 权重（用于 best_skill_for）
STATUS_WEIGHTS = {
    SkillStatus.STABLE: 1.0,
    SkillStatus.ACTIVE: 1.0,
    SkillStatus.RECOVERED: 1.0,
    SkillStatus.EXPERIMENTAL: 0.9,
    SkillStatus.DEGRADED: 0.5,
    SkillStatus.QUARANTINED: 0.0,
    SkillStatus.REMOVED: 0.0,
}


class SkillGovernor:
    """能力治理中心 — 管理所有 skill 的健康度和生命周期。"""

    def __init__(self, registry: SkillRegistry | None = None):
        self._registry = registry or SkillRegistry()
        self._scores: dict[str, SkillScore] = {}
        self._statuses: dict[str, SkillStatus] = {}
        self._conflict_detector = ConflictDetector()
        self._policies: dict[str, ToolPolicy | None] = {}
        self._global_policy: ToolPolicy | None = None
        # 恢复验证计数器
        self._recovery_verifications: dict[str, int] = {}

    # ─── 注册 ────────────────────────────────────────────────────────────

    def register(self, name: str, handler, keywords: list[str] | None = None, description: str = ""):
        """注册 skill 并初始化治理记录。"""
        self._registry.register(name, handler, keywords, description)
        self._scores[name] = SkillScore()
        self._statuses[name] = SkillStatus.EXPERIMENTAL
        self._policies[name] = None  # 使用全局策略

    # ─── 工具策略 ────────────────────────────────────────────────────────

    def set_policy(self, name: str, policy: ToolPolicy):
        """设置 skill 级策略（最高优先级）。"""
        self._policies[name] = policy

    def set_global_policy(self, policy: ToolPolicy):
        """设置全局策略（中间优先级）。"""
        self._global_policy = policy

    def get_policy(self, name: str) -> ToolPolicy:
        """获取 skill 的最终生效策略（三层优先级解析后）。"""
        return resolve_policy(
            skill_specific=self._policies.get(name),
            global_policy=self._global_policy,
        )

    def check_skill_allowed(self, name: str) -> bool:
        """检查 skill 当前是否被策略允许。"""
        policy = self.get_policy(name)
        expanded = expand_tool_list(policy.allow)

        if "all" in policy.allow:
            return True

        if not expanded:
            # 空 allow = 允许绝对全部（包括未知），但 deny 仍生效
            return is_tool_allowed(ToolPolicy(allow=[], deny=policy.deny), name)

        return is_tool_allowed(policy, name)

    # ─── 调用追踪 ────────────────────────────────────────────────────────

    def record_call(self, name: str, success: bool = True, latency: float = 0.0, error: str = ""):
        """记录一次 skill 调用并自动更新生命周期。"""
        score = self._scores.get(name)
        if not score:
            return

        if success:
            score.record_success(latency)
        else:
            score.record_failure(latency, error)

        # 自动生命周期评估（minimum_samples 保护内置）
        current = self._statuses.get(name, SkillStatus.EXPERIMENTAL)
        new_status = evaluate_lifecycle(current, score)

        # 小样本 warning：仅记录，不降级
        if score.usage < MINIMUM_SAMPLES and new_status in (
            SkillStatus.DEGRADED, SkillStatus.QUARANTINED
        ):
            # 仅降低权重，不改状态
            new_status = current

        if new_status != current:
            self._statuses[name] = new_status

    # ─── 恢复机制 ────────────────────────────────────────────────────────

    def try_recovery(self, name: str) -> bool:
        """尝试恢复 quarantined skill。

        如果当前为 QUARANTINED 且符合恢复条件 → RECOVERED。
        返回是否恢复成功。
        """
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

    # ─── 查询 ────────────────────────────────────────────────────────────

    def get_score(self, name: str) -> SkillScore | None:
        return self._scores.get(name)

    def get_status(self, name: str) -> SkillStatus:
        return self._statuses.get(name, SkillStatus.EXPERIMENTAL)

    def get_skill(self, name: str) -> SkillDef | None:
        return self._registry.get(name)

    def get_routing_weight(self, name: str) -> float:
        """获取 skill 的 routing 权重（带生命周期折扣）。"""
        status = self._statuses.get(name, SkillStatus.EXPERIMENTAL)
        return STATUS_WEIGHTS.get(status, 0.0)

    # ─── 最优 skill 选择 ─────────────────────────────────────────────────

    def best_skill_for(self, action: str) -> SkillDef | None:
        """根据 action 匹配并返回最优 skill。

        选择逻辑：
          1. match_all 获取候选集
          2. 过滤 REMOVED
          3. QUARANTINED 默认不参与（weight=0）
          4. 按 评分 × 权重 排序 → 返回最优
        """
        candidates = self._registry.match_all(action)
        if not candidates:
            return None

        def effective_score(name: str) -> float:
            score = self._scores.get(name, SkillScore())
            weight = self.get_routing_weight(name)
            return score.combined_score * weight

        # 过滤完全不可用的
        available = [
            name for name in candidates
            if self._statuses.get(name, SkillStatus.EXPERIMENTAL) not in (SkillStatus.REMOVED,)
        ]
        if not available:
            return None

        best = max(available, key=effective_score)
        # 如果 best 的 effective_score 为 0（eg. QUARANTINED），返回 None
        if effective_score(best) <= 0:
            return None
        return self._registry.get(best)

    def list_by_status(self, status: SkillStatus) -> list[dict]:
        """按生命周期状态列出 skill。"""
        result = []
        for name, s in self._statuses.items():
            if s == status:
                skill = self._registry.get(name)
                score = self._scores.get(name)
                result.append({
                    "name": name,
                    "status": s.value,
                    "score": score.combined_score if score else 1.0,
                    "usage": score.usage if score else 0,
                    "keywords": skill.keywords if skill else [],
                    "description": skill.description if skill else "",
                })
        return result

    def list_all(self) -> list[dict]:
        """列出所有 skill 的治理状态。"""
        result = []
        for name in self._registry.all_skills():
            skill = self._registry.get(name)
            score = self._scores.get(name)
            status = self._statuses.get(name, SkillStatus.EXPERIMENTAL)
            result.append({
                "name": name,
                "status": status.value,
                "combined_score": score.combined_score if score else 1.0,
                "bayesian_success_rate": score.bayesian_success_rate if score else 1.0,
                "success_rate": score.success_rate if score else 1.0,
                "error_rate": score.error_rate if score else 0.0,
                "usage": score.usage if score else 0,
                "latency": round(score.latency, 3) if score else 0.0,
                "consecutive_failures": score.consecutive_failures if score else 0,
                "recovery_attempts": score.recovery_attempts if score else 0,
                "keywords": skill.keywords if skill else [],
                "routing_weight": self.get_routing_weight(name),
            })
        return result

    # ─── 治理指标 ────────────────────────────────────────────────────────

    def quarantine_count(self) -> int:
        """当前 QUARANTINED 的 skill 数量。"""
        return sum(1 for s in self._statuses.values() if s == SkillStatus.QUARANTINED)

    def recovery_success_rate(self) -> float:
        """恢复成功率（有恢复记录的 skill 中成功恢复的比例）。"""
        total = 0
        success = 0
        for name, status in self._statuses.items():
            score = self._scores.get(name)
            if score and score.recovery_attempts > 0:
                total += 1
                if status == SkillStatus.RECOVERED:
                    success += 1
        return success / total if total > 0 else 1.0

    def ecosystem_stability_score(self) -> float:
        """生态系统稳定性评分（0.0~1.0）。

        基于：活跃 skill 比例 × (1 - quarantined 比例) × (1 - churn proportion)
        """
        all_skills = self._registry.count
        if all_skills == 0:
            return 1.0

        active = sum(1 for s in self._statuses.values()
                     if s in (SkillStatus.ACTIVE, SkillStatus.STABLE, SkillStatus.RECOVERED))
        quarantined = sum(1 for s in self._statuses.values() if s == SkillStatus.QUARANTINED)
        churned = sum(1 for s in self._statuses.values() if s == SkillStatus.REMOVED)

        return round(
            (active / all_skills)
            * (1.0 - quarantined / all_skills)
            * (1.0 - churned / all_skills),
            3,
        )

    def capability_churn_rate(self) -> float:
        """能力流失率 — REMOVED / total。"""
        all_skills = self._registry.count
        if all_skills == 0:
            return 0.0
        removed = sum(1 for s in self._statuses.values() if s == SkillStatus.REMOVED)
        return round(removed / all_skills, 3)

    # ─── 冲突检测 ────────────────────────────────────────────────────────

    def detect_conflicts(self) -> list[SkillConflict]:
        """检测所有 skill 之间的功能冲突。"""
        return self._conflict_detector.detect_all(self._registry.all_skills())

    # ─── 包装器 ──────────────────────────────────────────────────────────

    def wrap_handler(self, name: str, handler) -> '_GovernedHandler':
        """将 handler 包装为受 governance 追踪的版本。"""
        return _GovernedHandler(name, handler, self)


class _GovernedHandler:
    """受治理追踪的 handler 包装器。"""

    def __init__(self, name: str, handler, governor: SkillGovernor):
        self._name = name
        self._handler = handler
        self._governor = governor

    def call(self, input_data) -> dict:
        start = time.time()
        try:
            result = self._handler.call(input_data)
            latency = time.time() - start
            is_error = isinstance(result, dict) and any(
                kw in str(result.get("content", "")).lower()
                for kw in ["错误", "失败", "error", "不可用"]
            )
            self._governor.record_call(self._name, success=not is_error, latency=latency)
            return result
        except Exception as e:
            latency = time.time() - start
            self._governor.record_call(self._name, success=False, latency=latency, error=str(e))
            return {"content": f"[治理追踪] {self._name} 调用异常: {str(e)}"}
