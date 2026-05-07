"""Tests for Insight Agent (v1.86)"""

from governance.skill_governor import SkillGovernor
from governance.skill_score import SkillScore
from governance.lifecycle import SkillStatus
from memory.memory_store import MemoryStore
from insight.analyzer import SystemAnalyzer
from insight.drift import DriftDetector
from insight.report import ReportGenerator
from insight.agent import InsightAgent
import os, json


# ─── Helpers ──────────────────────────────────────────────────────────────────

class _Handler:
    def call(self, x): return {"content": x}


# ─── SystemAnalyzer ───────────────────────────────────────────────────────────

class TestSystemAnalyzer:
    def test_analyze_empty_governor(self):
        a = SystemAnalyzer()
        result = a.analyze()
        assert result["hot_skills"] == []
        assert result["declining_skills"] == []
        assert result["error_clusters"] == []
        assert result["execution_count"] == 0

    def test_analyze_with_healthy_skills(self):
        g = SkillGovernor()
        g.register("llm", _Handler(), ["llm", "ai"])
        g.register("code", _Handler(), ["code"])
        for _ in range(10):
            g.record_call("llm", success=True, latency=0.1)
            g.record_call("code", success=True, latency=0.2)

        a = SystemAnalyzer(governor=g)
        result = a.analyze()
        assert len(result["hot_skills"]) == 2
        assert len(result["declining_skills"]) == 0

    def test_analyze_with_declining_skill(self):
        g = SkillGovernor()
        g.register("good", _Handler(), ["good"])
        g.register("bad", _Handler(), ["bad"])
        for _ in range(10):
            g.record_call("bad", success=False, latency=1.0, error="fail")

        a = SystemAnalyzer(governor=g)
        result = a.analyze()
        assert len(result["declining_skills"]) >= 1
        assert result["declining_skills"][0]["name"] == "bad"

    def test_analyze_with_memory(self):
        g = SkillGovernor()
        g.register("s", _Handler(), ["s"])
        m = MemoryStore()
        m.tasks.append({"task_id": "t1", "status": "completed"})
        m.tasks.append({"task_id": "t2", "status": "failed"})

        a = SystemAnalyzer(governor=g, memory=m)
        result = a.analyze()
        assert result["execution_count"] == 2

    def test_find_hot_skills_limited_to_five(self):
        g = SkillGovernor()
        for i in range(10):
            g.register(f"s{i}", _Handler(), [f"k{i}"])
            for _ in range(3):
                g.record_call(f"s{i}", success=True)

        a = SystemAnalyzer(governor=g)
        hot = a._find_hot_skills(g.list_all())
        assert len(hot) <= 5

    def test_cluster_errors_by_status(self):
        g = SkillGovernor()
        g.register("a", _Handler(), ["a"])
        g.register("b", _Handler(), ["b"])
        g._statuses["b"] = SkillStatus.DEGRADED

        a = SystemAnalyzer(governor=g)
        clusters = a._cluster_errors(g.list_all())
        statuses = {c["status"] for c in clusters}
        assert "experimental" in statuses

    def test_ecosystem_stability_in_report(self):
        g = SkillGovernor()
        g.register("a", _Handler(), ["a"])
        g.register("b", _Handler(), ["b"])
        a = SystemAnalyzer(governor=g)
        result = a.analyze()
        assert "ecosystem_stability_score" in result
        assert "capability_churn_rate" in result
        assert "quarantine_count" in result
        assert "recovery_success_rate" in result

    def test_quarantine_count_reflected(self):
        g = SkillGovernor()
        g.register("a", _Handler(), ["a"])
        g.register("b", _Handler(), ["b"])
        g._statuses["a"] = SkillStatus.QUARANTINED
        a = SystemAnalyzer(governor=g)
        result = a.analyze()
        assert result["quarantine_count"] == 1


# ─── DriftDetector ───────────────────────────────────────────────────────────

class TestDriftDetector:
    def setup_method(self):
        self._snapshot = "/tmp/test_insight_baseline.json"
        if os.path.exists(self._snapshot):
            os.remove(self._snapshot)

    def _make_data(self, skills=None, conflicts=None, exec_count=0):
        return {
            "skill_summary": skills or [],
            "conflicts": conflicts or [],
            "execution_count": exec_count,
        }

    def test_first_call_establishes_baseline(self):
        d = DriftDetector(snapshot_path=self._snapshot)
        data = self._make_data(skills=[{"name": "llm", "usage": 5, "error_rate": 0.0, "latency": 0.1}])
        result = d.detect(data)
        assert result["drift_detected"] is False
        assert os.path.exists(self._snapshot)

    def test_no_change_no_drift(self):
        d = DriftDetector(snapshot_path=self._snapshot)
        data = self._make_data(skills=[{"name": "s", "usage": 5, "error_rate": 0.0, "latency": 0.1}])
        d.detect(data)

        result = d.detect(data)
        assert result["drift_detected"] is False
        assert result["drift_score"] == 0.0

    def test_error_rate_increase_detected(self):
        d = DriftDetector(snapshot_path=self._snapshot)
        d.detect(self._make_data(
            skills=[{"name": "s", "usage": 10, "error_rate": 0.0, "latency": 0.1}]
        ))
        result = d.detect(self._make_data(
            skills=[{"name": "s", "usage": 10, "error_rate": 0.3, "latency": 0.1}]
        ))
        assert result["drift_score"] > 0.0
        assert "error_rate" in result["affected_components"][0]

    def test_new_conflict_detected(self):
        d = DriftDetector(snapshot_path=self._snapshot)
        d.detect(self._make_data(conflicts=[]))
        result = d.detect(self._make_data(
            conflicts=[{"skill_a": "a", "skill_b": "b", "similarity": 0.9}]
        ))
        assert result["drift_score"] >= 0.25

    def test_cleanup(self):
        if os.path.exists(self._snapshot):
            os.remove(self._snapshot)


# ─── ReportGenerator ─────────────────────────────────────────────────────────

class TestReportGenerator:
    def test_generate_healthy(self):
        r = ReportGenerator()
        report = r.generate(
            analysis={"hot_skills": [], "declining_skills": [], "conflicts": [],
                      "skill_summary": [], "execution_count": 0},
            drift={"drift_detected": False, "drift_score": 0.0, "affected_components": []},
        )
        assert report["health_status"] == "healthy"
        assert "key_insights" in report
        assert "recommendations" in report

    def test_generate_unstable_with_drift(self):
        r = ReportGenerator()
        report = r.generate(
            analysis={"hot_skills": [], "declining_skills": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
                      "conflicts": [{"skill_a": "x", "skill_b": "y", "similarity": 0.9},
                                    {"skill_a": "p", "skill_b": "q", "similarity": 0.9},
                                    {"skill_a": "m", "skill_b": "n", "similarity": 0.9}],
                      "skill_summary": [], "execution_count": 5},
            drift={"drift_detected": True, "drift_score": 0.5, "affected_components": ["latency shift"]},
        )
        assert report["health_status"] == "unstable"

    def test_generate_degraded(self):
        r = ReportGenerator()
        report = r.generate(
            analysis={"hot_skills": [], "declining_skills": [{"name": "a"}],
                      "conflicts": [], "skill_summary": [], "execution_count": 0},
            drift={"drift_detected": False, "drift_score": 0.0, "affected_components": []},
        )
        assert report["health_status"] == "degraded"

    def test_to_text_output(self):
        r = ReportGenerator()
        report = r.generate(
            analysis={"hot_skills": [{"name": "llm", "combined_score": 0.95}],
                      "declining_skills": [], "conflicts": [],
                      "skill_summary": [], "execution_count": 3},
            drift={"drift_detected": False, "drift_score": 0.0, "affected_components": []},
        )
        text = r.to_text(report)
        assert "系统洞察报告" in text
        assert "healthy" in text
        assert "llm" in text


# ─── InsightAgent Integration ────────────────────────────────────────────────

class TestInsightAgent:
    def test_generate_report_with_real_data(self):
        g = SkillGovernor()
        g.register("llm", _Handler(), ["llm", "ai"], "通用 AI 问答")
        g.register("code", _Handler(), ["code", "python"], "代码执行")
        g.register("http", _Handler(), ["http", "api"], "HTTP 请求")
        for _ in range(20):
            g.record_call("llm", success=True, latency=0.1)
            g.record_call("code", success=True, latency=0.3)
        g.record_call("http", success=False, latency=2.0, error="timeout")

        m = MemoryStore()
        for i in range(5):
            m.save(type("obj", (object,), {
                "id": f"t{i}", "input": "test", "status": type("s", (object,), {"value": "completed"})(),
                "plan_goal": "", "plan": [], "steps": [], "result": "ok", "retry_count": 0, "error": None
            })())

        agent = InsightAgent(governor=g, memory=m)
        report = agent.generate_report()

        assert report["health_status"] in ("healthy", "degraded")
        assert "key_insights" in report
        assert "recommendations" in report
        assert "summary" in report
        assert report["analysis"]["execution_count"] > 0
        assert len(report["analysis"]["skill_summary"]) == 3

    def test_report_to_text(self):
        g = SkillGovernor()
        g.register("s", _Handler(), ["s"])
        agent = InsightAgent(governor=g, memory=MemoryStore())
        report = agent.generate_report()
        text = agent.report_to_text(report)
        assert isinstance(text, str)
        assert len(text) > 20

    def test_quick_health(self):
        agent = InsightAgent()
        assert agent.quick_health() in ("healthy", "degraded", "unstable")

    def test_empty_agent_no_error(self):
        agent = InsightAgent()
        report = agent.generate_report()
        assert report["health_status"] == "healthy"
