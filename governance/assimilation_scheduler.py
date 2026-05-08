"""Assimilation Scheduler v1.0 — 吞并节奏控制层

控制规则：
  - 每次只能吞 1 个模块
  - 必须 ATS 通过
  - 必须写 DevLog
  - risk_score >= 0.6 → QUARANTINE
  - risk_score >= 0.7 → REJECT
  - 必须人工确认才能进入下一轮

状态机:
READY → ANALYZING → TESTING → APPROVED → LOGGED → NEXT → READY
                            ↓            ↓
                        QUARANTINE    REJECTED

红线：
  - 不修改任何系统状态（除了调度器自身）
  - 不调用 SkillRegistry/SkillGovernor
  - 不触发真实执行
"""

from __future__ import annotations

import enum
import os
import json
from datetime import datetime
from typing import Any


class AssimilationState(enum.Enum):
    READY = "ready"
    ANALYZING = "analyzing"
    TESTING = "testing"
    APPROVED = "approved"
    LOGGED = "logged"
    NEXT = "next"
    QUARANTINE = "quarantine"
    REJECTED = "rejected"


# Valid transitions: {from_state: [to_state1, to_state2, ...]}
_VALID_TRANSITIONS = {
    AssimilationState.READY: [AssimilationState.ANALYZING],
    AssimilationState.ANALYZING: [AssimilationState.TESTING, AssimilationState.READY],  # cancel
    AssimilationState.TESTING: [
        AssimilationState.APPROVED,
        AssimilationState.QUARANTINE,
        AssimilationState.REJECTED,
        AssimilationState.READY,
    ],
    AssimilationState.APPROVED: [AssimilationState.LOGGED, AssimilationState.READY],
    AssimilationState.LOGGED: [AssimilationState.NEXT, AssimilationState.READY],
    AssimilationState.NEXT: [AssimilationState.READY, AssimilationState.ANALYZING],
    AssimilationState.QUARANTINE: [AssimilationState.READY],  # quarantine can restart
    AssimilationState.REJECTED: [AssimilationState.READY],    # rejected can restart
}

RISK_QUARANTINE_THRESHOLD = 0.6
RISK_REJECT_THRESHOLD = 0.7


class AssimilationScheduler:
    """吞并调度器 — 控制外部能力吞并的节奏。

    Usage:
        scheduler = AssimilationScheduler()
        scheduler.begin("loader", risk_score=0.3)
        scheduler.complete_analysis(capabilities=["config_loader"])
        scheduler.complete_testing(passed=True)
        scheduler.log()
        scheduler.confirm_human()
        scheduler.next_round()
    """

    DEVLOG_DIR = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "DvexaZSK", "devlog"
    )

    def __init__(self) -> None:
        self._state = AssimilationState.READY
        self._current_module: str | None = None
        self._history: list[dict[str, Any]] = []
        self._round_count = 0
        self._risk_score = 0.0
        self._capabilities: list[str] = []
        self._test_passed = False
        os.makedirs(self.DEVLOG_DIR, exist_ok=True)

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def state(self) -> AssimilationState:
        return self._state

    @property
    def current_module(self) -> str | None:
        return self._current_module

    @property
    def is_busy(self) -> bool:
        return self._state not in (AssimilationState.READY, AssimilationState.NEXT)

    @property
    def round_count(self) -> int:
        return self._round_count

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _transition(self, to_state: AssimilationState) -> None:
        if to_state not in _VALID_TRANSITIONS.get(self._state, []):
            raise InvalidTransitionError(
                f"Cannot transition from {self._state.value} to {to_state.value}"
            )
        self._state = to_state

    def _assert_state(self, expected: AssimilationState) -> None:
        if self._state != expected:
            raise InvalidTransitionError(
                f"Expected state '{expected.value}', but current state is "
                f"'{self._state.value}'"
            )

    def _record_history(self, result: str, reason: str) -> None:
        self._history.append({
            "module": self._current_module,
            "risk_score": self._risk_score,
            "result": result,
            "reason": reason,
            "capabilities": list(self._capabilities),
            "timestamp": datetime.now().isoformat(),
        })

    def _write_devlog(self, event: str, reason: str) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.DEVLOG_DIR, f"{today}_assimilation_scheduler.md")

        entry = (
            f"\n## Assimilation Event: {event}\n"
            f"- **Timestamp**: {datetime.now().isoformat()}\n"
            f"- **Module**: {self._current_module}\n"
            f"- **Risk Score**: {self._risk_score}\n"
            f"- **Result**: {event}\n"
            f"- **Reason**: {reason}\n"
            f"- **Capabilities**: "
            f"{', '.join(self._capabilities) if self._capabilities else 'none'}\n"
        )

        if not os.path.exists(log_file):
            header = (
                f"# Assimilation Scheduler Log — {today}\n"
                f"\n"
                f"Automated log from AssimilationScheduler.\n"
                f"Records all assimilation events "
                f"(approved/rejected/quarantine/cancelled).\n"
            )
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(header)

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)

    # ── Public API ───────────────────────────────────────────────────────────

    def process_event(self, event: "Event") -> list["Event"]:
        """Event Transformer: input Event → list[output Events]。

        执行完整状态机：begin → complete_analysis → complete_testing
        → [log → confirm → next (if approved)]。

        不写 _history / DevLog（由 EventStore 投影层处理）。
        """
        from runtime.event import Event as RuntimeEvent
        payload = event.payload
        target = payload.get("target", "")
        risk_score_val = payload.get("risk_score", 0.0)
        capabilities = payload.get("capabilities", [])
        ats_passed = payload.get("passed", False)

        events: list[RuntimeEvent] = []

        # begin
        begin_r = self.begin(target, risk_score=risk_score_val)
        events.append(RuntimeEvent(
            trace_id=event.trace_id, stage="schedule", event_type="info",
            payload=dict(begin_r),
        ))

        # complete_analysis
        analysis_r = self.complete_analysis(capabilities)
        events.append(RuntimeEvent(
            trace_id=event.trace_id, stage="schedule", event_type="info",
            payload=dict(analysis_r),
        ))

        # complete_testing
        test_r = self.complete_testing(passed=ats_passed)
        final_state = test_r["state"]
        events.append(RuntimeEvent(
            trace_id=event.trace_id, stage="schedule", event_type="decision",
            payload={**test_r, "final_state": final_state},
        ))

        # If approved: log → confirm → next
        if final_state == "approved":
            log_r = self.log()
            events.append(RuntimeEvent(
                trace_id=event.trace_id, stage="schedule", event_type="info",
                payload=dict(log_r),
            ))
            confirm_r = self.confirm_human()
            events.append(RuntimeEvent(
                trace_id=event.trace_id, stage="schedule", event_type="info",
                payload=dict(confirm_r),
            ))
            next_r = self.next_round()
            events.append(RuntimeEvent(
                trace_id=event.trace_id, stage="schedule", event_type="info",
                payload=dict(next_r),
            ))

        return events

    def begin(self, module_name: str, risk_score: float = 0.0) -> dict:
        """开始吞并流程：READY/NEXT → ANALYZING"""
        if self.is_busy:
            raise SchedulerBusyError(
                f"Scheduler is busy with module '{self._current_module}' "
                f"in state '{self._state.value}'. Cancel first or wait."
            )
        if not module_name or not module_name.strip():
            raise ValueError("module_name must not be empty")

        risk_score = max(0.0, min(risk_score, 1.0))
        self._current_module = module_name.strip()
        self._risk_score = risk_score
        self._capabilities = []
        self._test_passed = False
        self._transition(AssimilationState.ANALYZING)

        return {
            "status": "started",
            "module": self._current_module,
            "state": self._state.value,
            "risk_score": self._risk_score,
        }

    def complete_analysis(
        self, capabilities: list[str] | None = None
    ) -> dict:
        """完成分析：ANALYZING → TESTING"""
        self._assert_state(AssimilationState.ANALYZING)
        self._capabilities = capabilities or []
        self._transition(AssimilationState.TESTING)
        return {
            "status": "analysis_complete",
            "module": self._current_module,
            "state": self._state.value,
            "capabilities": self._capabilities,
        }

    def complete_testing(self, passed: bool = True) -> dict:
        """完成测试：TESTING → APPROVED / QUARANTINE / REJECTED

        决策规则:
          - passed=False → REJECTED
          - risk >= 0.7 → REJECTED
          - risk >= 0.6 → QUARANTINE
          - otherwise  → APPROVED
        """
        self._assert_state(AssimilationState.TESTING)
        self._test_passed = passed

        if not passed:
            result_state = AssimilationState.REJECTED
            reason = "测试未通过"
        elif self._risk_score >= RISK_REJECT_THRESHOLD:
            result_state = AssimilationState.REJECTED
            reason = (
                f"风险评分 {self._risk_score} >= {RISK_REJECT_THRESHOLD}"
            )
        elif self._risk_score >= RISK_QUARANTINE_THRESHOLD:
            result_state = AssimilationState.QUARANTINE
            reason = (
                f"风险评分 {self._risk_score} >= {RISK_QUARANTINE_THRESHOLD}"
            )
        else:
            result_state = AssimilationState.APPROVED
            reason = (
                f"测试通过，风险 {self._risk_score} < {RISK_QUARANTINE_THRESHOLD}"
            )

        self._transition(result_state)
        result = {
            "status": "testing_complete",
            "module": self._current_module,
            "state": self._state.value,
            "test_passed": passed,
            "risk_score": self._risk_score,
            "reason": reason,
        }

        # 如果被拒绝或隔离，自动写 DevLog 并记录历史
        if result_state in (
            AssimilationState.REJECTED,
            AssimilationState.QUARANTINE,
        ):
            self._write_devlog(result_state.value, reason)
            self._record_history(result_state.value, reason)

        return result

    def log(self) -> dict:
        """记录 DevLog：APPROVED → LOGGED"""
        self._assert_state(AssimilationState.APPROVED)
        reason = f"吞并已记录: {self._current_module}"
        self._write_devlog("approved", reason)
        self._transition(AssimilationState.LOGGED)
        return {
            "status": "logged",
            "module": self._current_module,
            "state": self._state.value,
        }

    def confirm_human(self) -> dict:
        """人工确认：LOGGED → NEXT"""
        self._assert_state(AssimilationState.LOGGED)
        self._transition(AssimilationState.NEXT)
        return {
            "status": "confirmed",
            "module": self._current_module,
            "state": self._state.value,
            "message": "人工确认完成，准备下一轮",
        }

    def next_round(self) -> dict:
        """进入下一轮：NEXT → READY"""
        self._assert_state(AssimilationState.NEXT)
        reason = f"吞并完成: {self._current_module}"
        self._record_history("completed", reason)
        entry = dict(self._history[-1]) if self._history else {}
        self._current_module = None
        self._risk_score = 0.0
        self._capabilities = []
        self._test_passed = False
        self._round_count += 1
        self._transition(AssimilationState.READY)
        return {
            "status": "ready_for_next",
            "round": self._round_count,
            "state": self._state.value,
            "last_completed": entry.get("module"),
        }

    def cancel(self) -> dict:
        """取消当前操作：任意状态 → READY"""
        if self._state == AssimilationState.READY:
            return {"status": "already_ready", "state": self._state.value}

        module = self._current_module
        reason = f"操作已取消: {module} (state={self._state.value})"
        self._record_history("cancelled", reason)
        self._current_module = None
        self._risk_score = 0.0
        self._capabilities = []
        self._test_passed = False
        self._transition(AssimilationState.READY)
        return {
            "status": "cancelled",
            "module": module,
            "state": self._state.value,
        }

    def status(self) -> dict:
        """当前状态报告。"""
        return {
            "state": self._state.value,
            "module": self._current_module,
            "risk_score": self._risk_score,
            "is_busy": self.is_busy,
            "round": self._round_count,
            "test_passed": self._test_passed,
            "capabilities": self._capabilities,
            "last_history": self._history[-1] if self._history else None,
        }

    def history(self) -> list[dict]:
        """吞并历史记录（返回副本）。"""
        return list(self._history)


# ── Exceptions ────────────────────────────────────────────────────────────────

class SchedulerError(Exception):
    """基类异常"""
    pass


class InvalidTransitionError(SchedulerError):
    """非法状态转换"""
    pass


class SchedulerBusyError(SchedulerError):
    """调度器忙（正在处理其他模块）"""
    pass
