"""Governance Stabilizer v1 — 治理收敛层

防止 governance system 结构发散。只做压缩/合并/约束，
不新增治理规则，不改变决策语义。

红线:
  - 不调用 LLM
  - 不新增 governance rule
  - 只能压缩 / 合并 / 约束
  - 不改变决策语义
  - 输出复杂度 ≤ 输入复杂度
"""

from __future__ import annotations

from typing import Any

# ─── 已知工具名（标准化用）─────────────────────────────────────────────────

_KNOWN_TOOLS = frozenset({
    "llm", "code_executor", "http_request", "github", "security",
})

_ACTION_PRIORITY = {"block": 0, "downgrade": 1, "reroute": 2, "allow": 3}

_MAX_PLAN_STEPS = 8


# ═══════════════════════════════════════════════════════════════════════════
# GovernanceStabilizer
# ═══════════════════════════════════════════════════════════════════════════


class GovernanceStabilizer:
    """收敛层：防止 governance system 结构发散。

    在 GovernanceKernel.process() 输出端插入，确保:
      - plan 结构不膨胀（step 上限 / 去重 / 标准化）
      - decision 不冗余（合并 / 最高优先级保留）
      - feedback 不越界（仅允许统计更新）
    """

    def __init__(
        self,
        kernel: Any = None,
        feedback_engine: Any = None,
        skill_governor: Any = None,
    ):
        self._kernel = kernel
        self._feedback_engine = feedback_engine
        self._governor = skill_governor

    # ═══════════════════════════════════════════════════════════════════
    # Public API — Plan Stabilization
    # ═══════════════════════════════════════════════════════════════════

    def stabilize_plan(self, plan: dict, context: dict | None = None) -> dict:
        """Plan 结构收敛。

        操作:
          1. Step 数量上限（保留前 8 个）
          2. 合并连续重复 action（相同 tool + action）
          3. 去除低信息密度 step（空 action / 空 tool）
          4. 强制 tool 名标准化到已知集

        Args:
            plan: 输入 plan dict
            context: 可选上下文（当前未使用，保留参数）

        Returns:
            收敛后的 plan（复杂度 ≤ 输入）
        """
        if not plan or "steps" not in plan:
            return plan

        steps = plan["steps"]
        if not isinstance(steps, list):
            return plan

        # Rule 1: 去除低信息密度 step
        cleaned = [
            s for s in steps
            if isinstance(s, dict)
            and (s.get("action") or "").strip()
        ]

        # Rule 2: 合并连续重复 action
        merged: list[dict] = []
        for s in cleaned:
            if merged and _is_duplicate_step(merged[-1], s):
                continue
            merged.append(s)

        # Rule 3: Step 数量上限
        capped = merged[:_MAX_PLAN_STEPS]

        # Rule 4: 标准化 tool 名
        for s in capped:
            tool = s.get("tool", "")
            if tool and tool not in _KNOWN_TOOLS:
                s["tool"] = "llm"
            # 确保 type 字段合法
            if s.get("type") not in ("tool", "reasoning"):
                s["type"] = "tool"

        return {**plan, "steps": capped}

    # ═══════════════════════════════════════════════════════════════════
    # Public API — Decision Stabilization
    # ═══════════════════════════════════════════════════════════════════

    def stabilize_decisions(self, decisions: list[dict]) -> list[dict]:
        """Decision 输出收敛。

        操作:
          - 按 step_id 去重，保留最高优先级 action
          - 合并同类策略判断的 reason
          - 按 step_id 稳定排序

        Args:
            decisions: 原始 decisions 列表

        Returns:
            收敛后的 decisions（长度 ≤ 输入）
        """
        if not decisions:
            return []

        # 按 step_id 分组
        groups: dict[int, list[dict]] = {}
        for d in decisions:
            sid = d.get("step_id", 0)
            groups.setdefault(sid, []).append(d)

        result: list[dict] = []
        for sid in sorted(groups):
            entries = groups[sid]

            # 取最高优先级（最小 priority 值）
            best = min(
                entries,
                key=lambda e: _ACTION_PRIORITY.get(e.get("action", "allow"), 3),
            )

            # 合并 reasons
            reasons = list(dict.fromkeys(
                e.get("reason", "") for e in entries if e.get("reason")
            ))
            merged_reason = " | ".join(reasons) if len(reasons) > 1 else (reasons[0] if reasons else "")

            result.append({
                "step_id": sid,
                "action": best["action"],
                "reason": merged_reason,
            })

        return result

    # ═══════════════════════════════════════════════════════════════════
    # Public API — Feedback Stabilization
    # ═══════════════════════════════════════════════════════════════════

    def stabilize_feedback(self, feedback_event: dict) -> dict:
        """Feedback 事件结构收敛。

        只允许三件事:
          - skill_score: score 更新值
          - tool_preference: preference 更新值
          - strategy_stats: 计数器增量

        禁止: 任何结构性修改（新增 rule / 修改决策链 / 变更配置）

        Args:
            feedback_event: FeedbackEngine 输出事件

        Returns:
            过滤后仅含允许字段的 event
        """
        if not isinstance(feedback_event, dict):
            return {}

        allowed_keys = {"skill_score", "tool_preference", "strategy_stats"}
        return {
            k: v for k, v in feedback_event.items()
            if k in allowed_keys
        }


# ═══════════════════════════════════════════════════════════════════════════
# Internal Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _is_duplicate_step(a: dict, b: dict) -> bool:
    """判断两个连续步骤是否为重复（相同 tool + action）。"""
    return (
        a.get("tool") == b.get("tool")
        and (a.get("action") or "").strip()
        == (b.get("action") or "").strip()
    )
