"""Tests for OpenClaw Analyzer and Report Writer"""

import json
import tempfile
from pathlib import Path
import pytest

from external.openclaw_analyzer import OpenClawAnalyzer
from external.openclaw_report_writer import OpenClawReportWriter
from external.assimilation_log import AssimilationLogger


class _MockGHTool:
    """Mock GitHubCLITool for analyzer tests."""

    def call(self, input_data) -> dict:
        action = input_data.get("action", "")
        repo = input_data.get("repo", "")

        if action == "repo_info":
            return {
                "status": "ok",
                "data": {
                    "name": "openclaw",
                    "description": "A test claw game framework",
                    "language": "Python",
                    "stars": 100,
                    "license": "MIT",
                    "disk_usage_kb": 2048,
                },
            }
        if action == "readme":
            return {
                "status": "ok",
                "data": {"readme": "# OpenClaw\n\nA claw machine framework for testing."},
            }
        if action == "tree":
            return {
                "status": "ok",
                "data": {
                    "file_count": 20,
                    "dir_count": 5,
                    "files": [
                        {"path": "openclaw/core.py", "size": 800, "mode": "100644"},
                        {"path": "openclaw/tools/http_tool.py", "size": 300, "mode": "100644"},
                        {"path": "openclaw/skills/grab_skill.py", "size": 200, "mode": "100644"},
                        {"path": "openclaw/router.py", "size": 150, "mode": "100644"},
                        {"path": "openclaw/config.py", "size": 50, "mode": "100644"},
                        {"path": "openclaw/__init__.py", "size": 0, "mode": "100644"},
                        {"path": "tests/test_core.py", "size": 400, "mode": "100644"},
                        {"path": "requirements.txt", "size": 50, "mode": "100644"},
                    ],
                    "dirs": ["openclaw", "openclaw/tools", "openclaw/skills", "tests"],
                },
            }
        if action == "file":
            return {
                "status": "ok",
                "data": {"path": input_data.get("path", ""), "size": 100,
                         "content": "# 示例依赖\nrequests>=2.28\n", "encoding": "base64"},
            }
        if action == "languages":
            return {
                "status": "ok",
                "data": {"total_bytes": 10000,
                         "languages": [{"name": "Python", "bytes": 10000, "percent": 100.0}]},
            }
        return {"status": "error", "data": None, "error": f"Mock 不支持: {action}"}


# ─── OpenClawAnalyzer 测试 ─────────────────────────────────────────────────

class TestOpenClawAnalyzer:
    def setup_method(self):
        self.analyzer = OpenClawAnalyzer(_MockGHTool())

    def test_analyze_returns_all_required_sections(self):
        result = self.analyzer.analyze("https://github.com/owner/openclaw")
        assert "meta" in result
        assert "project_summary" in result
        assert "architecture" in result
        assert "useful_modules" in result
        assert "candidate_skills" in result
        assert "conflicts" in result
        assert "risk_analysis" in result
        assert "merge_suggestions" in result
        assert "recommended_strategy" in result

    def test_project_summary_has_key_fields(self):
        result = self.analyzer.analyze("https://github.com/owner/openclaw")
        s = result["project_summary"]
        assert s["name"] == "openclaw"
        assert s["language"] == "Python"
        assert s["stars"] == 100

    def test_architecture_analysis(self):
        result = self.analyzer.analyze("https://github.com/owner/openclaw")
        a = result["architecture"]
        assert a["file_count"] > 0
        assert "openclaw" in a["top_level_dirs"]
        assert a["python_files"] >= 6

    def test_useful_modules_found(self):
        result = self.analyzer.analyze("owner/openclaw")
        modules = result["useful_modules"]
        paths = [m["path"] for m in modules]
        assert "openclaw/tools/http_tool.py" in paths
        assert "openclaw/skills/grab_skill.py" in paths

    def test_useful_modules_have_scores(self):
        result = self.analyzer.analyze("owner/openclaw")
        for m in result["useful_modules"]:
            assert 0 <= m["relevance_score"] <= 1
            assert m["category"] in ("tool", "agent", "router", "skill", "pipeline", "api", "util", "other")

    def test_candidate_skills_extracted(self):
        result = self.analyzer.analyze("owner/openclaw")
        skills = result["candidate_skills"]
        assert len(skills) >= 1
        for s in skills:
            assert "name" in s
            assert "type_hint" in s
            assert "complexity" in s

    def test_conflicts_detected(self):
        result = self.analyzer.analyze("owner/openclaw")
        assert len(result["conflicts"]) >= 1

    def test_risk_analysis(self):
        result = self.analyzer.analyze("owner/openclaw")
        assert len(result["risk_analysis"]) >= 1

    def test_merge_suggestions(self):
        result = self.analyzer.analyze("owner/openclaw")
        assert len(result["merge_suggestions"]) >= 1
        for s in result["merge_suggestions"]:
            assert s["action"] in ("assimilate_as_skill", "extract_pattern", "reference_only", "reject")

    def test_recommended_strategy(self):
        result = self.analyzer.analyze("owner/openclaw")
        s = result["recommended_strategy"]
        assert "overall_approach" in s
        assert "quick_wins" in s
        assert "needs_human_review" in s

    def test_parse_repo_url_full(self):
        owner, repo = self.analyzer._parse_repo_url("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_repo_url_short(self):
        owner, repo = self.analyzer._parse_repo_url("owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_repo_url_invalid(self):
        owner, repo = self.analyzer._parse_repo_url("")
        assert repo == ""


# ─── OpenClawReportWriter 测试 ─────────────────────────────────────────────

class TestOpenClawReportWriter:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.report_dir = Path(self.tmpdir) / "reports"
        self.logger = AssimilationLogger(log_dir=str(Path(self.tmpdir) / "logs"))
        self.writer = OpenClawReportWriter(self.logger, report_dir=str(self.report_dir))

    def _sample_analysis(self) -> dict:
        return {
            "meta": {"full_name": "owner/openclaw", "analyzed_at": "2026-05-07T12:00:00"},
            "project_summary": {"name": "openclaw", "description": "Test", "language": "Python",
                                "stars": 100, "license": "MIT", "disk_usage_kb": 1024},
            "architecture": {"file_count": 10, "dir_count": 3, "python_files": 5,
                             "top_level_dirs": ["src", "tests"], "extension_breakdown": {".py": 5},
                             "dependencies": [{"path": "requirements.txt", "name": "requirements.txt",
                                               "content_preview": "requests>=2.28"}]},
            "useful_modules": [{"path": "src/tool.py", "name": "tool", "size": 200,
                                "category": "tool", "relevance_score": 0.85, "reason": "工具模块"}],
            "candidate_skills": [{"name": "tool", "source_module": "src/tool.py",
                                  "type_hint": "http", "keywords": ["tool"], "description": "工具模块",
                                  "complexity": "low", "estimated_lines": 200, "relevance": 0.85}],
            "conflicts": [{"module": "src/tool.py", "conflict_type": "duplicate_skill",
                           "severity": "medium", "description": "可能重叠", "dvx_equivalent": "参考"}],
            "risk_analysis": [{"category": "license", "level": "low", "detail": "MIT 许可证"}],
            "merge_suggestions": [{"module": "src/tool.py", "action": "assimilate_as_skill",
                                   "priority": 1, "rationale": "高价值", "refactor_type": "wrap_as_skill",
                                   "estimated_effort": "low"}],
            "recommended_strategy": {"overall_approach": "分优先级吞并", "quick_wins": ["src/tool.py"],
                                     "needs_human_review": [], "should_reject": [],
                                     "total_candidates": 1, "avg_relevance_score": 0.85},
        }

    def test_write_creates_report_file(self):
        analysis = self._sample_analysis()
        result = self.writer.write(analysis, "https://github.com/owner/openclaw")
        assert result["status"] == "ok"
        assert result["report_path"] is not None
        report_path = Path(result["report_path"])
        assert report_path.exists()
        assert report_path.suffix == ".md"

    def test_report_contains_required_sections(self):
        analysis = self._sample_analysis()
        result = self.writer.write(analysis, "https://github.com/owner/openclaw")
        content = Path(result["report_path"]).read_text(encoding="utf-8")
        assert "吞并分析报告" in content
        assert "项目摘要" in content
        assert "架构分析" in content
        assert "候选吞并能力" in content
        assert "风险分析" in content
        assert "吞并建议" in content
        assert "推荐策略" in content
        assert "人工审批清单" in content

    def test_write_creates_assimilation_log(self):
        analysis = self._sample_analysis()
        self.writer.write(analysis, "https://github.com/owner/openclaw")
        logs = self.logger.list_all()
        assert len(logs) == 1
        assert logs[0].endswith(".json")

    def test_empty_report_dir_is_created(self):
        d = Path(tempfile.mkdtemp()) / "new_reports"
        w = OpenClawReportWriter(self.logger, report_dir=str(d))
        assert d.exists()
