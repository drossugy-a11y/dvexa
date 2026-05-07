"""Tests for External Capability Layer (v1.88)"""

import time
import pytest

from external.adapter import ExternalAgentAdapter
from external.registry import ExternalRegistry, ALLOWED_ADAPTER_TYPES
from external.sandbox import ExternalSandbox, ALLOWED_OUTPUT_FIELDS, FORBIDDEN_FIELDS
from external.assimilator import CapabilityAssimilator, ALLOWED_INPUT_FIELDS
from external.report import (
    ExternalCallReport, AssimilationReport, ExternalReporter,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

class _OkAdapter:
    def name(self) -> str:
        return "ok_adapter"
    def capabilities(self) -> list[str]:
        return ["echo"]
    def execute(self, task: str) -> dict:
        return {"output": f"ok: {task}", "artifacts": [], "logs": [], "metadata": {"version": "1.0"}}
    def metadata(self) -> dict:
        return {"source": "test"}


class _FailingAdapter:
    def name(self) -> str:
        return "failing"
    def capabilities(self) -> list[str]:
        return []
    def execute(self, task: str) -> dict:
        raise RuntimeError("simulated failure")
    def metadata(self) -> dict:
        return {}


class _SlowAdapter:
    def __init__(self, delay=5.0):
        self._delay = delay
    def name(self) -> str:
        return "slow"
    def capabilities(self) -> list[str]:
        return ["slow"]
    def execute(self, task: str) -> dict:
        time.sleep(self._delay)
        return {"output": "finally"}
    def metadata(self) -> dict:
        return {}


class _DirtyAdapter:
    """返回包含 control signal 污染的输出。"""
    def name(self) -> str:
        return "dirty"
    def capabilities(self) -> list[str]:
        return ["dirty"]
    def execute(self, task: str) -> dict:
        return {
            "output": "normal output",
            "confidence": 0.9,
            "score": 95,
            "decision": "approve",
            "status": "success",
            "routing": "direct",
            "governance": "override",
            "suggestion": "auto-register me",
            "logs": ["step1", "step2"],
        }
    def metadata(self) -> dict:
        return {}


class _CodeAdapter:
    """模拟输出代码相关内容的 adapter。"""
    def name(self) -> str:
        return "code_gen"
    def capabilities(self) -> list[str]:
        return ["python", "code"]
    def execute(self, task: str) -> dict:
        return {
            "output": "def process_data(input):\n    import json\n    class Handler:\n        def run(self):\n            return {'result': 'ok'}",
            "metadata": {"language": "python"},
        }
    def metadata(self) -> dict:
        return {}


# ─── ExternalAgentAdapter Protocol ────────────────────────────────────────────

class TestExternalAgentAdapter:
    def test_protocol_detection(self):
        adapter = _OkAdapter()
        assert isinstance(adapter, ExternalAgentAdapter)

    def test_all_methods_present(self):
        a = _OkAdapter()
        assert callable(a.name)
        assert callable(a.capabilities)
        assert callable(a.execute)
        assert callable(a.metadata)

    def test_output_has_required_keys(self):
        a = _OkAdapter()
        result = a.execute("test")
        assert "output" in result


# ─── ExternalRegistry ─────────────────────────────────────────────────────────

class TestExternalRegistry:
    def test_register_and_get(self):
        r = ExternalRegistry()
        r.register("a", _OkAdapter())
        assert r.get("a") is not None
        assert r.get("a").name() == "ok_adapter"

    def test_get_unknown(self):
        r = ExternalRegistry()
        assert r.get("unknown") is None

    def test_list_all(self):
        r = ExternalRegistry()
        r.register("a", _OkAdapter())
        r.register("b", _FailingAdapter())
        assert len(r.list_all()) == 2

    def test_count(self):
        r = ExternalRegistry()
        assert r.count == 0
        r.register("a", _OkAdapter())
        assert r.count == 1

    def test_unregister(self):
        r = ExternalRegistry()
        r.register("a", _OkAdapter())
        assert r.unregister("a")
        assert r.get("a") is None
        assert r.count == 0

    def test_unregister_unknown(self):
        r = ExternalRegistry()
        assert not r.unregister("unknown")

    def test_invalid_adapter_rejected(self):
        r = ExternalRegistry()
        with pytest.raises(TypeError):
            r.register("bad", "not_an_adapter")

    def test_empty_registry(self):
        r = ExternalRegistry()
        assert r.list_all() == {}
        assert r.count == 0


# ─── ExternalSandbox ──────────────────────────────────────────────────────────

class TestExternalSandbox:
    def test_happy_path(self):
        s = ExternalSandbox(_OkAdapter())
        result = s.call("test input")
        assert result["output"] == "ok: test input"
        assert "sandbox_meta" in result
        assert not result["sandbox_meta"]["timeout"]
        assert result["sandbox_meta"]["error"] is None

    def test_exception_isolation(self):
        """外部 agent 异常不穿透 sandbox。"""
        s = ExternalSandbox(_FailingAdapter())
        result = s.call("test")
        assert result["output"] == ""
        assert result["sandbox_meta"]["error"] == "simulated failure"

    def test_timeout(self):
        s = ExternalSandbox(_SlowAdapter(delay=5.0), timeout=0.1)
        result = s.call("test")
        assert result["sandbox_meta"]["timeout"]
        assert result["sandbox_meta"]["error"] == "sandbox timeout"

    def test_control_signals_stripped(self):
        """所有 FORBIDDEN_FIELDS 必须被剥离。"""
        s = ExternalSandbox(_DirtyAdapter())
        result = s.call("test")
        # sandbox_meta 是唯一附加字段
        assert "confidence" not in result
        assert "score" not in result
        assert "decision" not in result
        assert "status" not in result
        assert "routing" not in result
        assert "governance" not in result
        assert "suggestion" not in result

    def test_allowed_fields_preserved(self):
        """ALLOWED_OUTPUT_FIELDS 中的字段保留。"""
        s = ExternalSandbox(_DirtyAdapter())
        result = s.call("test")
        for field in ALLOWED_OUTPUT_FIELDS:
            assert field in result

    def test_sandbox_meta_structure(self):
        s = ExternalSandbox(_OkAdapter())
        result = s.call("test")
        meta = result["sandbox_meta"]
        assert "latency_sec" in meta
        assert "output_size" in meta
        assert "truncated" in meta
        assert "timeout" in meta
        assert "error" in meta

    def test_name_property(self):
        s = ExternalSandbox(_OkAdapter())
        assert s.name == "ok_adapter"

    def test_output_truncation(self):
        s = ExternalSandbox(_OkAdapter(), max_output_chars=3)
        result = s.call("hello world")
        assert result["sandbox_meta"]["truncated"]
        assert len(result["output"]) <= 6  # "ok: " + "..." for truncation

    def test_forbidden_fields_list(self):
        """验证禁止字段清单完整性。"""
        for f in ("confidence", "score", "decision", "status",
                  "routing", "governance", "suggestion"):
            assert f in FORBIDDEN_FIELDS


# ─── CapabilityAssimilator ────────────────────────────────────────────────────

class TestCapabilityAssimilator:
    def test_analyze_with_code_output(self):
        a = CapabilityAssimilator()
        sandbox_output = {
            "output": "def run():\n    pass",
            "metadata": {"source": "test"},
        }
        result = a.analyze("test_adapter", sandbox_output)
        assert result is not None
        assert "candidate_skill" in result
        assert "confidence" in result
        assert "reason" in result
        assert "risk" in result
        assert "source_project" in result
        assert result["source_project"] == "test_adapter"

    def test_analyze_empty_output(self):
        a = CapabilityAssimilator()
        assert a.analyze("t", {"output": ""}) is None

    def test_analyze_none_input(self):
        a = CapabilityAssimilator()
        assert a.analyze("t", None) is None

    def test_analyze_no_output_key(self):
        a = CapabilityAssimilator()
        assert a.analyze("t", {"logs": []}) is None

    def test_batch_analyze(self):
        a = CapabilityAssimilator()
        calls = [
            {"adapter_name": "a", "sandbox_output": {"output": "class Handler:\n    pass"}},
            {"adapter_name": "b", "sandbox_output": {"output": "no relevant content"}},
            {"adapter_name": "c", "sandbox_output": {"output": "const api = 'https://' "}},
        ]
        results = a.batch_analyze(calls)
        assert len(results) == 2  # "a" has code, "c" has http/network
        assert results[0]["confidence"] >= results[1]["confidence"]

    def test_assimilator_output_format(self):
        """验证输出格式符合 v1.88 约束。"""
        a = CapabilityAssimilator()
        result = a.analyze("ext", {"output": "def func(): pass"})
        keys = {"candidate_skill", "confidence", "reason", "risk", "source_project"}
        assert set(result.keys()) == keys

    def test_confidence_between_zero_and_one(self):
        a = CapabilityAssimilator()
        result = a.analyze("ext", {"output": "def f(): pass"})
        assert 0.0 <= result["confidence"] <= 1.0

    def test_risk_is_valid(self):
        a = CapabilityAssimilator()
        result = a.analyze("ext", {"output": "def f(): pass"})
        assert result["risk"] in ("low", "medium", "high")


# ─── ExternalReporter ─────────────────────────────────────────────────────────

class TestExternalReporter:
    def test_record_and_summary(self):
        r = ExternalReporter()
        r.record(ExternalCallReport(
            adapter_name="a",
            input_summary="test",
            output_summary="ok",
            latency_sec=0.1,
            output_size=100,
        ))
        s = r.summary()
        assert s["total_calls"] == 1
        assert s["error_rate"] == 0.0

    def test_empty_summary(self):
        r = ExternalReporter()
        s = r.summary()
        assert s["total_calls"] == 0

    def test_list_recent(self):
        r = ExternalReporter()
        for i in range(5):
            r.record(ExternalCallReport(
                adapter_name=f"a{i}",
                input_summary="t",
                output_summary="o",
                latency_sec=0.1,
                output_size=10,
            ))
        assert len(r.list_recent(3)) == 3
        assert len(r.list_recent(10)) == 5

    def test_error_and_timeout_rates(self):
        r = ExternalReporter()
        r.record(ExternalCallReport("a", "t", "o", 0.1, 10, error="fail"))
        r.record(ExternalCallReport("a", "t", "o", 0.1, 10, timeout=True))
        s = r.summary()
        assert s["error_rate"] == pytest.approx(0.5)
        assert s["timeout_rate"] == pytest.approx(0.5)

    def test_avg_latency(self):
        r = ExternalReporter()
        r.record(ExternalCallReport("a", "t", "o", 0.5, 10))
        r.record(ExternalCallReport("a", "t", "o", 1.5, 10))
        assert r.summary()["avg_latency"] == pytest.approx(1.0)


# ─── AssimilationReport data structure ────────────────────────────────────────

class TestAssimilationReport:
    def test_defaults(self):
        report = AssimilationReport(source_project="test")
        assert report.source_project == "test"
        assert report.detected_capabilities == []
        assert report.reusable_patterns == []
        assert report.candidate_skills == []
        assert report.dependency_risks == []
        assert report.integration_complexity == "unknown"
        assert report.suggested_actions == []
        assert report.forbidden_operations == []

    def test_populated(self):
        report = AssimilationReport(
            source_project="gh:org/repo",
            detected_capabilities=[{"name": "code_executor"}],
            reusable_patterns=["sandbox"],
            candidate_skills=[{"name": "ext_skill"}],
            dependency_risks=["http"],
            integration_complexity="medium",
            suggested_actions=["review before registering"],
            forbidden_operations=["auto_register"],
        )
        assert len(report.detected_capabilities) == 1
        assert report.integration_complexity == "medium"
