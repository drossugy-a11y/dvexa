"""Tests for Meta Control Plane v3."""
import pytest
from governance.meta_control_plane import (
    MetaControlPlane,
    SystemHealthMonitor,
    EvolutionPermissionEngine,
    OptimizationGate,
    EvolutionClamp,
    SnapshotManager,
)


# ═══════════════════════════════════════════════════════════════════════════
# Test: SystemHealthMonitor
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthMonitor:
    def test_perfect_health(self):
        monitor = SystemHealthMonitor()
        state = {
            "strategy_effectiveness": {
                "BALANCED": {"success_rate": 1.0, "variance": 0.0},
            },
            "fallback_rate": 0.0,
            "cost_stability": 1.0,
        }
        result = monitor.assess(state)
        assert result["status"] == "STABLE"
        assert result["health_score"] >= 0.9

    def test_degraded_health(self):
        monitor = SystemHealthMonitor()
        state = {
            "strategy_effectiveness": {
                "BALANCED": {"success_rate": 0.5, "variance": 0.2},
            },
            "fallback_rate": 0.25,
            "cost_stability": 0.6,
        }
        result = monitor.assess(state)
        assert result["status"] == "DEGRADED"
        assert 0.4 <= result["health_score"] <= 0.8

    def test_unstable_health(self):
        monitor = SystemHealthMonitor()
        state = {
            "strategy_effectiveness": {
                "BALANCED": {"success_rate": 0.2, "variance": 0.3},
            },
            "fallback_rate": 0.5,
            "cost_stability": 0.3,
        }
        result = monitor.assess(state)
        assert result["status"] == "UNSTABLE"
        assert result["health_score"] < 0.6

    def test_empty_strategy_state(self):
        monitor = SystemHealthMonitor()
        state = {
            "strategy_effectiveness": {},
            "fallback_rate": 0.1,
            "cost_stability": 1.0,
        }
        result = monitor.assess(state)
        assert result["health_score"] > 0.6

    def test_signals_on_low_success(self):
        monitor = SystemHealthMonitor()
        state = {
            "strategy_effectiveness": {
                "BALANCED": {"success_rate": 0.3, "variance": 0.0},
            },
            "fallback_rate": 0.3,
            "cost_stability": 0.8,
        }
        result = monitor.assess(state)
        assert "low_success_rate" in result["signals"]
        assert "high_fallback" in result["signals"]


# ═══════════════════════════════════════════════════════════════════════════
# Test: EvolutionPermissionEngine
# ═══════════════════════════════════════════════════════════════════════════

class TestPermissionEngine:
    def test_full_mode_when_stable(self):
        engine = EvolutionPermissionEngine()
        health = {"health_score": 0.95, "status": "STABLE"}
        state = {
            "strategy_effectiveness": {},
            "drift": {"drift_detected": False, "severity": "none"},
            "rollback_rate": 0.0,
        }
        result = engine.evaluate(health, state)
        assert result["mode"] == "FULL"
        assert result["allowed"] is True

    def test_frozen_on_high_drift(self):
        engine = EvolutionPermissionEngine()
        health = {"health_score": 0.70, "status": "DEGRADED"}
        state = {
            "strategy_effectiveness": {},
            "drift": {"drift_detected": True, "severity": "high"},
            "rollback_rate": 0.0,
        }
        result = engine.evaluate(health, state)
        assert result["mode"] == "FROZEN"
        assert result["allowed"] is False

    def test_frozen_on_high_rollback(self):
        engine = EvolutionPermissionEngine()
        health = {"health_score": 0.80, "status": "STABLE"}
        state = {
            "strategy_effectiveness": {},
            "drift": {"drift_detected": False, "severity": "none"},
            "rollback_rate": 0.30,
        }
        result = engine.evaluate(health, state)
        assert result["mode"] == "FROZEN"
        assert result["allowed"] is False

    def test_limited_on_degraded_health(self):
        engine = EvolutionPermissionEngine()
        health = {"health_score": 0.55, "status": "DEGRADED"}
        state = {
            "strategy_effectiveness": {},
            "drift": {"drift_detected": False, "severity": "none"},
            "rollback_rate": 0.0,
        }
        result = engine.evaluate(health, state)
        assert result["mode"] == "LIMITED"
        assert result["allowed"] is True

    def test_limited_on_success_drop(self):
        engine = EvolutionPermissionEngine()
        health = {"health_score": 0.85, "status": "STABLE"}
        state = {
            "strategy_effectiveness": {
                "BALANCED": {"success_rate": 0.68, "_previous_rate": 0.80},
            },
            "drift": {"drift_detected": False, "severity": "none"},
            "rollback_rate": 0.0,
        }
        result = engine.evaluate(health, state)
        assert result["mode"] == "LIMITED"

    def test_frozen_on_large_success_drop(self):
        engine = EvolutionPermissionEngine()
        health = {"health_score": 0.85, "status": "STABLE"}
        state = {
            "strategy_effectiveness": {
                "BALANCED": {"success_rate": 0.3, "_previous_rate": 0.9},
            },
            "drift": {"drift_detected": False, "severity": "none"},
            "rollback_rate": 0.0,
        }
        result = engine.evaluate(health, state)
        assert result["mode"] == "FROZEN"


# ═══════════════════════════════════════════════════════════════════════════
# Test: OptimizationGate
# ═══════════════════════════════════════════════════════════════════════════

class TestOptimizationGate:
    def test_gate_open_when_healthy(self):
        gate = OptimizationGate()
        health = {"health_score": 0.90}
        permission = {"mode": "FULL"}
        result = gate.check(health, permission, drift_detected=False)
        assert result["can_optimize"] is True
        assert result["cooldown_tasks"] == 0

    def test_gate_blocked_on_low_health(self):
        gate = OptimizationGate()
        health = {"health_score": 0.45}
        permission = {"mode": "FULL"}
        result = gate.check(health, permission, drift_detected=False)
        assert result["can_optimize"] is False
        assert result["cooldown_tasks"] > 0

    def test_gate_blocked_on_drift(self):
        gate = OptimizationGate()
        health = {"health_score": 0.85}
        permission = {"mode": "FULL"}
        result = gate.check(health, permission, drift_detected=True)
        assert result["can_optimize"] is False

    def test_gate_blocked_when_frozen(self):
        gate = OptimizationGate()
        health = {"health_score": 0.80}
        permission = {"mode": "FROZEN"}
        result = gate.check(health, permission, drift_detected=False)
        assert result["can_optimize"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Test: EvolutionClamp
# ═══════════════════════════════════════════════════════════════════════════

class TestEvolutionClamp:
    def test_no_clamp_on_small_changes(self):
        clamp = EvolutionClamp()
        adjustments = {
            "tool_cost_multipliers": {"llm": 1.05},
            "strategy_biases": {"BALANCED": 0.05},
        }
        result = clamp.clamp(adjustments)
        assert result["clamped"] is False
        assert result["adjusted_changes"]["tool_cost_multipliers"]["llm"] == 1.05
        assert result["adjusted_changes"]["strategy_biases"]["BALANCED"] == 0.05

    def test_clamp_cost_model_change(self):
        clamp = EvolutionClamp()
        adjustments = {
            "tool_cost_multipliers": {"llm": 1.50},
        }
        prev = {"tool_cost_multipliers": {"llm": 1.0}}
        result = clamp.clamp(adjustments, prev)
        assert result["clamped"] is True
        assert len(result["violations"]) > 0
        assert result["adjusted_changes"]["tool_cost_multipliers"]["llm"] <= 1.20

    def test_clamp_strategy_bias_change(self):
        clamp = EvolutionClamp()
        adjustments = {
            "strategy_biases": {"BALANCED": 0.30},
        }
        prev = {"strategy_biases": {"BALANCED": 0.0}}
        result = clamp.clamp(adjustments, prev)
        assert result["clamped"] is True
        assert result["adjusted_changes"]["strategy_biases"]["BALANCED"] <= 0.10

    def test_clamp_tool_weight_change(self):
        clamp = EvolutionClamp()
        adjustments = {
            "tool_weight_updates": {"llm": 0.50},
        }
        prev = {"tool_weight_updates": {"llm": 0.0}}
        result = clamp.clamp(adjustments, prev)
        assert result["clamped"] is True
        assert len(result["violations"]) > 0

    def test_clamp_skill_score_change(self):
        clamp = EvolutionClamp()
        adjustments = {
            "skill_score_updates": {"llm": 0.25},
        }
        prev = {"skill_score_updates": {"llm": 0.0}}
        result = clamp.clamp(adjustments, prev)
        assert result["clamped"] is True
        assert result["adjusted_changes"]["skill_score_updates"]["llm"] <= 0.10

    def test_no_previous_adjustments(self):
        clamp = EvolutionClamp()
        adjustments = {"tool_cost_multipliers": {"llm": 1.10}}
        result = clamp.clamp(adjustments)
        assert result["clamped"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Test: SnapshotManager
# ═══════════════════════════════════════════════════════════════════════════

class TestSnapshotManager:
    def test_create_snapshot(self):
        sm = SnapshotManager()
        state = {"stable": True, "cost_stability": 1.0}
        sid = sm.create_snapshot(state, "test")
        assert sid.startswith("meta_snap_")
        assert sm.get_snapshot_count() == 1

    def test_get_last_stable_snapshot(self):
        sm = SnapshotManager()
        sm.create_snapshot({"stable": True}, "stable_1")
        sm.create_snapshot({"stable": False}, "unstable")
        snap = sm.get_last_stable_snapshot()
        assert snap is not None
        assert snap["reason"] == "stable_1"

    def test_rollback_to_snapshot(self):
        sm = SnapshotManager()
        sid = sm.create_snapshot({"a": 1}, "one")
        sm.create_snapshot({"a": 2}, "two")
        restored = sm.rollback_to(sid)
        assert restored is not None
        assert restored["system_state"]["a"] == 1

    def test_rollback_nonexistent(self):
        sm = SnapshotManager()
        assert sm.rollback_to("nonexistent") is None

    def test_max_snapshots_limit(self):
        sm = SnapshotManager()
        for i in range(15):
            sm.create_snapshot({"i": i}, f"snap_{i}")
        assert sm.get_snapshot_count() <= 10

    def test_no_stable_snapshot_fallback_to_last(self):
        sm = SnapshotManager()
        sm.create_snapshot({"stable": False}, "unstable_only")
        snap = sm.get_last_stable_snapshot()
        assert snap is not None
        assert snap["reason"] == "unstable_only"


# ═══════════════════════════════════════════════════════════════════════════
# Test: MetaControlPlane (integrated process)
# ═══════════════════════════════════════════════════════════════════════════

class TestMetaControlPlane:
    def test_process_allows_when_stable(self):
        mcp = MetaControlPlane()
        state = {
            "strategy_effectiveness": {
                "BALANCED": {"success_rate": 0.95, "variance": 0.02},
            },
            "fallback_rate": 0.05,
            "cost_stability": 0.95,
            "rollback_rate": 0.0,
            "drift": {"drift_detected": False, "severity": "none"},
        }
        result = mcp.process(state, {"adjustments": {}})
        assert result["meta_decision"]["allowed"] is True
        assert result["meta_decision"]["mode"] in ("FULL", "LIMITED")

    def test_process_blocks_on_drift(self):
        mcp = MetaControlPlane()
        state = {
            "strategy_effectiveness": {
                "BALANCED": {"success_rate": 0.70, "variance": 0.10},
            },
            "fallback_rate": 0.10,
            "cost_stability": 0.80,
            "rollback_rate": 0.0,
            "drift": {"drift_detected": True, "severity": "high"},
        }
        result = mcp.process(state, {"adjustments": {}})
        assert result["meta_decision"]["allowed"] is False
        assert result["meta_decision"]["mode"] == "FROZEN"

    def test_process_blocks_on_high_rollback(self):
        mcp = MetaControlPlane()
        state = {
            "strategy_effectiveness": {},
            "fallback_rate": 0.10,
            "cost_stability": 0.80,
            "rollback_rate": 0.30,
            "drift": {"drift_detected": False, "severity": "none"},
        }
        result = mcp.process(state, {"adjustments": {}})
        assert result["meta_decision"]["allowed"] is False
        assert result["meta_decision"]["mode"] == "FROZEN"

    def test_process_clamps_large_changes(self):
        mcp = MetaControlPlane()
        state = {
            "strategy_effectiveness": {
                "BALANCED": {"success_rate": 0.95, "variance": 0.02},
            },
            "fallback_rate": 0.05,
            "cost_stability": 1.0,
            "rollback_rate": 0.0,
            "drift": {"drift_detected": False, "severity": "none"},
        }
        opt = {
            "adjustments": {
                "tool_cost_multipliers": {"llm": 1.50},
                "strategy_biases": {},
            },
        }
        result = mcp.process(state, opt)
        assert result["meta_decision"]["allowed"] is True
        # 大变化被钳制
        clamped_cost = result["clamped_changes"].get("tool_cost_multipliers", {})
        if clamped_cost.get("llm") is not None:
            assert clamped_cost["llm"] <= 1.20

    def test_output_format_is_strict(self):
        mcp = MetaControlPlane()
        state = {
            "strategy_effectiveness": {
                "BALANCED": {"success_rate": 0.90, "variance": 0.01},
            },
            "fallback_rate": 0.02,
            "cost_stability": 0.95,
            "rollback_rate": 0.0,
            "drift": {"drift_detected": False, "severity": "none"},
        }
        result = mcp.process(state, {"adjustments": {}})
        assert "meta_decision" in result
        assert "allowed" in result["meta_decision"]
        assert "mode" in result["meta_decision"]
        assert "health_score" in result["meta_decision"]
        assert "drift_status" in result["meta_decision"]
        assert "cooldown" in result["meta_decision"]
        assert "clamped_changes" in result
        assert "snapshot_action" in result
        assert "reason" in result

    def test_snapshot_created_when_frozen(self):
        mcp = MetaControlPlane()
        state = {
            "strategy_effectiveness": {},
            "fallback_rate": 0.0,
            "cost_stability": 0.90,
            "rollback_rate": 0.25,
            "drift": {"drift_detected": False, "severity": "none"},
        }
        result = mcp.process(state, {"adjustments": {}})
        assert result["meta_decision"]["allowed"] is False
        assert result["snapshot_action"] == "ROLLBACK"

    def test_query_apis(self):
        mcp = MetaControlPlane()
        assert isinstance(mcp.get_health_monitor(), SystemHealthMonitor)
        assert isinstance(mcp.get_permission_engine(), EvolutionPermissionEngine)
        assert isinstance(mcp.get_gate(), OptimizationGate)
        assert isinstance(mcp.get_clamp(), EvolutionClamp)
        assert isinstance(mcp.get_snapshot_manager(), SnapshotManager)
        assert mcp.get_process_count() == 0
        assert mcp.get_last_adjustments() == {}
