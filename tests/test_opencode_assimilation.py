"""Tests for OpenCode Assimilation Pipeline (Phases 1-9)."""
import os
import sys
import json
import pytest

from external.opencode_analyzer import OpenCodeAnalyzer
from external.pattern_extractor import PatternExtractor
from external.opencode_report_writer import AssimilationReportWriter
from governance.assimilation_review import AssimilationReview
from external.assimilation_sandbox import AssimilationSandbox
from external.pattern_registry import PatternRegistry


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

OPN_PATH = os.path.join(
    os.path.dirname(__file__), "..", "DvexaZSK", "external_sources", "opencode"
)


def create_test_pattern(name="test_pattern",
                        category="execution",
                        recommendation="adopt",
                        changes=None,
                        mechanism="Test mechanism",
                        recommended_layer="capabilities"):
    return {
        "pattern_name": name,
        "category": category,
        "source": "test/source.ts",
        "problem_solved": "Test problem description",
        "mechanism": mechanism,
        "dvexa_compatibility": "adaptable",
        "risk_level": "low",
        "adoption_recommendation": recommendation,
        "required_changes": changes or ["Add test to capabilities/"],
        "recommended_layer": recommended_layer,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Test: Repository Analysis
# ═══════════════════════════════════════════════════════════════════════════

class TestRepoAnalysis:
    def test_analyze_nonexistent_path(self):
        analyzer = OpenCodeAnalyzer()
        result = analyzer.analyze_repo("/nonexistent/path")
        assert "error" in result

    def test_analyze_opencode_repo(self):
        if not os.path.isdir(OPN_PATH):
            pytest.skip(f"OpenCode repo not cloned at {OPN_PATH}")
        analyzer = OpenCodeAnalyzer()
        result = analyzer.analyze_repo(OPN_PATH)
        assert "error" not in result
        assert "repository" in result
        assert "planner_patterns" in result
        assert "execution_patterns" in result

    def test_analysis_structure_is_complete(self):
        if not os.path.isdir(OPN_PATH):
            pytest.skip(f"OpenCode repo not cloned at {OPN_PATH}")
        analyzer = OpenCodeAnalyzer()
        result = analyzer.analyze_repo(OPN_PATH)
        required_keys = [
            "repository", "planner_patterns", "execution_patterns",
            "context_patterns", "memory_patterns", "tool_patterns",
            "runtime_patterns", "risk_patterns", "recommended_adoptions",
            "architecture_summary",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_deterministic_output(self):
        if not os.path.isdir(OPN_PATH):
            pytest.skip(f"OpenCode repo not cloned at {OPN_PATH}")
        analyzer1 = OpenCodeAnalyzer()
        analyzer2 = OpenCodeAnalyzer()
        r1 = analyzer1.analyze_repo(OPN_PATH)
        r2 = analyzer2.analyze_repo(OPN_PATH)
        assert r1["planner_patterns"] == r2["planner_patterns"]
        assert r1["execution_patterns"] == r2["execution_patterns"]
        assert r1["risk_patterns"] == r2["risk_patterns"]
        assert r1["recommended_adoptions"] == r2["recommended_adoptions"]


# ═══════════════════════════════════════════════════════════════════════════
# Test: Pattern Extraction
# ═══════════════════════════════════════════════════════════════════════════

class TestPatternExtraction:
    def test_extract_from_analysis(self):
        if not os.path.isdir(OPN_PATH):
            pytest.skip(f"OpenCode repo not cloned at {OPN_PATH}")
        analyzer = OpenCodeAnalyzer()
        analysis = analyzer.analyze_repo(OPN_PATH)

        extractor = PatternExtractor()
        result = extractor.extract(analysis)

        assert "patterns" in result
        assert "count" in result
        assert result["count"] > 0
        assert result["count"] == len(result["patterns"])

    def test_pattern_format(self):
        extractor = PatternExtractor()
        # Minimal analysis mock
        analysis = {
            "execution_patterns": [{
                "source": "test.ts",
                "pattern": "test-retry-pattern",
                "description": "Test retry mechanism",
                "mechanism": "Retry with backoff",
            }],
            "planner_patterns": [],
            "context_patterns": [],
            "memory_patterns": [],
            "tool_patterns": [],
            "runtime_patterns": [],
            "risk_patterns": [],
            "recommended_adoptions": [],
        }
        result = extractor.extract(analysis)
        for p in result["patterns"]:
            assert "pattern_name" in p
            assert "category" in p
            assert "dvexa_compatibility" in p
            assert "risk_level" in p
            assert "adoption_recommendation" in p
            assert "required_changes" in p

    def test_summary_stats(self):
        extractor = PatternExtractor()
        analysis = {
            "execution_patterns": [
                {"source": "a", "pattern": "p1", "description": "desc",
                 "mechanism": "autonomous agent spawning"},
                {"source": "b", "pattern": "p2", "description": "retry",
                 "mechanism": "simple backoff"},
            ],
            "planner_patterns": [],
            "context_patterns": [],
            "memory_patterns": [],
            "tool_patterns": [],
            "runtime_patterns": [],
            "risk_patterns": [
                {"type": "multi-agent", "severity": "high",
                 "description": "desc",
                 "dvexa_equivalent": "N/A"},
            ],
            "recommended_adoptions": [],
        }
        result = extractor.extract(analysis)
        summary = result["summary"]
        assert summary["total_patterns"] == 3
        assert "by_recommendation" in summary
        assert "execution" in summary["by_category"]


# ═══════════════════════════════════════════════════════════════════════════
# Test: Assimilation Review
# ═══════════════════════════════════════════════════════════════════════════

class TestGovernanceReview:
    def test_review_rejects_incompatible_pattern(self):
        review = AssimilationReview()
        pattern = create_test_pattern(
            name="multi-agent-spawn",
            mechanism="agent spawns sub-agent autonomously",
            recommendation="reject",
        )
        result = review.review(pattern)
        assert result["approved"] is False
        assert result["risk_score"] > 0.9

    def test_review_approves_safe_pattern(self):
        review = AssimilationReview()
        pattern = create_test_pattern(
            name="simple-retry",
            mechanism="Retry with backoff",
            recommendation="adopt",
            changes=["Add retry to capabilities/retry.py"],
        )
        result = review.review(pattern)
        assert result["approved"] is True

    def test_review_blocks_kernel_modification(self):
        review = AssimilationReview()
        pattern = create_test_pattern(
            name="dangerous",
            mechanism="override control",
            recommendation="adopt",
            changes=["Modify core/kernel.py loop"],
        )
        result = review.review(pattern)
        assert result["approved"] is False

    def test_review_batch(self):
        review = AssimilationReview()
        patterns = [
            create_test_pattern("p1", recommendation="adopt"),
            create_test_pattern("p2", recommendation="reject"),
            create_test_pattern("p3", recommendation="adapt"),
        ]
        result = review.review_all(patterns)
        assert result["total"] == 3
        assert "approved_count" in result
        assert "results" in result

    def test_global_violations_detected(self):
        review = AssimilationReview()
        patterns = [
            create_test_pattern("bad", changes=["Modify core/kernel.py"]),
        ]
        result = review.review_all(patterns)
        assert len(result["global_violations"]) > 0

    def test_all_seven_checks_run(self):
        review = AssimilationReview()
        pattern = create_test_pattern(
            "test", mechanism="recursive agent can spawn sub-tasks via shell exec",
            changes=["Edit core/executor.py to add write-back capability",
                     "Add replay to memory store",
                     "Add new tool to registry",
                     "Add event bus"],
        )
        result = review.review(pattern)
        assert "violations" in result
        assert "risk_score" in result
        assert isinstance(result["risk_score"], float)
        assert 0 <= result["risk_score"] <= 1


# ═══════════════════════════════════════════════════════════════════════════
# Test: Assimilation Sandbox
# ═══════════════════════════════════════════════════════════════════════════

class TestAssimilationSandbox:
    def test_inject_pattern_returns_snapshot(self):
        sandbox = AssimilationSandbox()
        pattern = create_test_pattern("test")
        result = sandbox.inject_pattern(pattern)
        assert "injection_id" in result
        assert "snapshot_id" in result
        assert result["status"] == "injected"

    def test_regression_suite_passes_for_safe_patterns(self):
        sandbox = AssimilationSandbox()
        sandbox.inject_pattern(create_test_pattern(
            "safe", changes=["Add to capabilities/test.py"]
        ))
        result = sandbox.run_regression_suite()
        assert result["passed"] is True
        assert result["failed_count"] == 0

    def test_regression_blocks_frozen_violation(self):
        sandbox = AssimilationSandbox()
        sandbox.inject_pattern(create_test_pattern(
            "dangerous", changes=["Modify core/kernel.py"]
        ))
        result = sandbox.run_regression_suite()
        assert any(
            not d["passed"] and "frozen" in d["check"]
            for d in result["details"]
        )

    def test_rollback_single_injection(self):
        sandbox = AssimilationSandbox()
        sandbox.inject_pattern(create_test_pattern("a"))
        inj2 = sandbox.inject_pattern(create_test_pattern("b"))
        result = sandbox.rollback(inj2["injection_id"])
        assert result["rolled_back"] is True
        # "b" rolled back, "a" still active
        assert "b" not in sandbox.get_active_injections()
        assert "a" in sandbox.get_active_injections()

    def test_rollback_all(self):
        sandbox = AssimilationSandbox()
        sandbox.inject_pattern(create_test_pattern("a"))
        sandbox.inject_pattern(create_test_pattern("b"))
        result = sandbox.rollback()
        assert result["rolled_back"] is True
        assert result["count"] == 2

    def test_commit(self):
        sandbox = AssimilationSandbox()
        inj = sandbox.inject_pattern(create_test_pattern("commit_test"))
        result = sandbox.commit(inj["injection_id"])
        assert result["committed"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Test: Pattern Registry
# ═══════════════════════════════════════════════════════════════════════════

class TestPatternRegistry:
    def test_register_pattern(self):
        registry = PatternRegistry()
        pattern = create_test_pattern("reg-test")
        pid = registry.register(pattern)
        assert "execution/reg-test" == pid

    def test_search_by_category(self):
        registry = PatternRegistry()
        registry.register(create_test_pattern("p1", category="execution"))
        registry.register(create_test_pattern("p2", category="tool"))
        results = registry.search(category="tool")
        assert len(results) == 1
        assert results[0]["pattern_name"] == "p2"

    def test_get_adopted_patterns(self):
        registry = PatternRegistry()
        registry.register(create_test_pattern("p1"))
        registry.register(create_test_pattern("p2"))
        registry.adopt("execution/p1")
        adopted = registry.get_adopted_patterns()
        assert len(adopted) == 1
        assert adopted[0]["pattern_name"] == "p1"

    def test_advance_tbrz_stage(self):
        registry = PatternRegistry()
        pid = registry.register(create_test_pattern("stage-test"))
        assert registry.advance_stage(pid, "sandboxed")
        assert registry.get_pattern(pid)["tbrz_stage"] == 3

    def test_export_json(self):
        registry = PatternRegistry()
        registry.register(create_test_pattern("json-test"))
        j = registry.export_json()
        data = json.loads(j)
        assert "patterns" in data
        assert "summary" in data

    def test_register_batch(self):
        registry = PatternRegistry()
        patterns = [
            create_test_pattern("b1"), create_test_pattern("b2"),
            create_test_pattern("b3"),
        ]
        ids = registry.register_batch(patterns)
        assert len(ids) == 3
        assert registry.get_count() == 3


# ═══════════════════════════════════════════════════════════════════════════
# Test: Report Generation
# ═══════════════════════════════════════════════════════════════════════════

class TestReportGeneration:
    def test_generate_report(self, tmp_path):
        writer = AssimilationReportWriter(output_dir=str(tmp_path / "reports"))
        analysis = {
            "repository": {"name": "test", "language": "TS"},
            "architecture_summary": {
                "top_level_modules": ["a", "b"],
                "module_file_counts": {},
                "core_runtime_modules": [],
                "control_modules": [],
                "infra_modules": [],
            },
            "risk_patterns": [],
            "recommended_adoptions": [],
        }
        extracted = {
            "patterns": [create_test_pattern("test-pat", mechanism="test")],
            "count": 1,
            "summary": {
                "total_patterns": 1,
                "by_category": {"execution": 1},
                "by_risk": {"low": 1},
                "by_recommendation": {"adopt": 1},
                "adoptable_count": 1,
                "adaptable_count": 0,
                "rejected_count": 0,
            },
        }
        path = writer.generate(analysis, extracted)
        assert os.path.exists(path)
        content = open(path).read()
        assert "# OpenCode Assimilation Report" in content
        assert "test-pat" in content

    def test_generate_json(self, tmp_path):
        writer = AssimilationReportWriter(output_dir=str(tmp_path / "reports"))
        extracted = {
            "patterns": [create_test_pattern("json-pat")],
            "count": 1,
            "summary": {},
        }
        path = writer.generate_json(extracted)
        assert os.path.exists(path)
        data = json.load(open(path))
        assert len(data) == 1
        assert data[0]["pattern_name"] == "json-pat"


# ═══════════════════════════════════════════════════════════════════════════
# Test: End-to-End Pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestE2EPipeline:
    def test_full_pipeline(self, tmp_path):
        """端到端测试：分析 → 提取 → 审查 → 沙箱 → 注册。"""
        # 模拟分析
        analyzer = OpenCodeAnalyzer()
        if not os.path.isdir(OPN_PATH):
            pytest.skip(f"OpenCode repo not cloned at {OPN_PATH}")
        analysis = analyzer.analyze_repo(OPN_PATH)

        # 提取
        extractor = PatternExtractor()
        extracted = extractor.extract(analysis)
        assert extracted["count"] > 0

        # 审查
        review = AssimilationReview()
        review_result = review.review_all(extracted["patterns"])
        assert review_result["total"] == extracted["count"]

        # 只处理 approved 的 pattern
        sandbox = AssimilationSandbox()
        registry = PatternRegistry()

        injected = 0
        for p in extracted["patterns"]:
            rv = review.get_review(p["pattern_name"])
            if rv and rv["approved"]:
                sandbox.inject_pattern(p)
                registry.register(p, review=rv)
                injected += 1

        # 回归
        reg_result = sandbox.run_regression_suite()
        assert "passed" in reg_result

        # 输出验证
        writer = AssimilationReportWriter(
            output_dir=str(tmp_path / "reports"),
        )
        report_path = writer.generate(analysis, extracted, review_result)
        assert os.path.exists(report_path)

        json_path = writer.generate_json(extracted)
        assert os.path.exists(json_path)

    def test_no_kernel_modification(self):
        """验证 pipeline 不修改 kernel。"""
        if not os.path.isdir(OPN_PATH):
            pytest.skip(f"OpenCode repo not cloned at {OPN_PATH}")
        analyzer = OpenCodeAnalyzer()
        analysis = analyzer.analyze_repo(OPN_PATH)

        extractor = PatternExtractor()
        extracted = extractor.extract(analysis)

        review = AssimilationReview()
        review_result = review.review_all(extracted["patterns"])

        # 任何 pattern 都不能修改 kernel
        for name, rv in review_result["results"].items():
            if rv["approved"]:
                for v in rv.get("violations", []):
                    assert "CRITICAL" not in v, \
                        f"Approved pattern {name} has critical violation: {v}"

    def test_pipeline_is_deterministic(self):
        """Pipeline 必须全部 deterministic 输出。"""
        if not os.path.isdir(OPN_PATH):
            pytest.skip(f"OpenCode repo not cloned at {OPN_PATH}")

        # Run 1
        a1 = OpenCodeAnalyzer()
        e1 = PatternExtractor()
        r1 = AssimilationReview()
        analysis1 = a1.analyze_repo(OPN_PATH)
        extracted1 = e1.extract(analysis1)
        review1 = r1.review_all(extracted1["patterns"])

        # Run 2
        a2 = OpenCodeAnalyzer()
        e2 = PatternExtractor()
        r2 = AssimilationReview()
        analysis2 = a2.analyze_repo(OPN_PATH)
        extracted2 = e2.extract(analysis2)
        review2 = r2.review_all(extracted2["patterns"])

        # 检查一致性
        assert extracted1["count"] == extracted2["count"]
        assert review1["total"] == review2["total"]
        for i, (p1, p2) in enumerate(
            zip(extracted1["patterns"], extracted2["patterns"])
        ):
            assert p1["pattern_name"] == p2["pattern_name"], \
                f"Pattern {i} differs between runs"
