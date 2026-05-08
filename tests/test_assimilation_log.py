"""吞并日志系统测试（v1.89）"""

import json
import shutil
import tempfile
from pathlib import Path
import pytest

from external.assimilation_log import (
    AssimilationLogEntry, AssimilationLogger,
    CandidateCapability, RejectedCapability, ObservedArchitecture,
    LOG_DIR, VALID_DECISIONS,
)


# ─── 辅助函数 ──────────────────────────────────────────────────────────────────

def _make_entry(**kw) -> AssimilationLogEntry:
    entry = AssimilationLogEntry(
        source_project=kw.get("source_project", "test_project"),
        github_url=kw.get("github_url", "https://github.com/org/test"),
        analyzed_commit=kw.get("analyzed_commit", "abc123"),
        analysis_time=kw.get("analysis_time", "2026-05-07 12:00:00"),
        decision=kw.get("decision", "pending"),
        observed_architecture=kw.get("arch", ObservedArchitecture(
            modules=["core", "api"],
            agents=["base_agent"],
            tools=["http", "code"],
            memory=["store"],
            workflow=["plan", "execute"],
        )),
        candidate_capabilities=kw.get("candidates", [
            CandidateCapability("code_executor", "core/executor", 0.85, "low", "low", "代码执行"),
            CandidateCapability("llm_router", "core/router", 0.65, "medium", "medium", "LLM 路由"),
        ]),
        rejected_capabilities=kw.get("rejected", [
            RejectedCapability("auto_planner", "core/planner", "违反 frozen layer"),
        ]),
        future_notes=kw.get("future_notes", "可再分析"),
    )
    return entry


class _TempLogger:
    """使用临时目录的 logger，测试结束后自动清理。"""
    def __init__(self):
        self._tmpdir = tempfile.mkdtemp()
        self.logger = AssimilationLogger(log_dir=self._tmpdir)

    def cleanup(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)


# ─── AssimilationLogEntry ─────────────────────────────────────────────────────

class TestAssimilationLogEntry:
    def test_default_analysis_time(self):
        entry = AssimilationLogEntry(source_project="test")
        assert entry.analysis_time != ""
        assert entry.decision == "pending"

    def test_invalid_decision_defaults_to_pending(self):
        entry = AssimilationLogEntry(source_project="t", decision="invalid")
        assert entry.decision == "pending"

    def test_to_dict(self):
        entry = _make_entry()
        d = entry.to_dict()
        assert d["source_project"] == "test_project"
        assert d["decision"] == "pending"
        assert len(d["candidate_capabilities"]) == 2

    def test_from_dict(self):
        original = _make_entry()
        d = original.to_dict()
        restored = AssimilationLogEntry.from_dict(d)
        assert restored.source_project == original.source_project
        assert restored.decision == original.decision
        assert len(restored.candidate_capabilities) == 2
        assert restored.candidate_capabilities[0].candidate_skill == "code_executor"

    def test_from_dict_nested_objects(self):
        """验证嵌套的 dataclass 能正确反序列化。"""
        data = {
            "source_project": "test",
            "observed_architecture": {
                "modules": ["a"], "agents": [], "tools": [], "memory": [], "workflow": [],
            },
            "candidate_capabilities": [
                {"candidate_skill": "s", "source_module": "m", "confidence": 0.5,
                 "complexity": "low", "risk": "low", "estimated_value": ""},
            ],
            "rejected_capabilities": [],
            "decision": "approved",
            "future_notes": "",
            "analysis_time": "2026-05-07",
        }
        entry = AssimilationLogEntry.from_dict(data)
        assert entry.decision == "approved"
        assert len(entry.candidate_capabilities) == 1

    def test_valid_decisions(self):
        assert "approved" in VALID_DECISIONS
        assert "rejected" in VALID_DECISIONS
        assert "pending" in VALID_DECISIONS

    def test_candidate_capability_defaults(self):
        c = CandidateCapability(candidate_skill="s", source_module="m")
        assert c.complexity == "medium"
        assert c.risk == "low"
        assert c.confidence == 0.0


# ─── AssimilationLogger — 基本功能 ────────────────────────────────────────────

class TestAssimilationLoggerBasic:
    def test_save_and_load_json(self):
        t = _TempLogger()
        entry = _make_entry()
        fname = t.logger.save_log(entry)
        loaded = t.logger.load_log(fname)
        assert loaded is not None
        assert loaded.source_project == entry.source_project
        assert loaded.decision == entry.decision
        t.cleanup()

    def test_save_log_returns_filename(self):
        t = _TempLogger()
        entry = _make_entry()
        fname = t.logger.save_log(entry)
        assert fname.startswith("TB")
        assert fname.endswith(".json")
        t.cleanup()

    def test_list_all_empty(self):
        t = _TempLogger()
        assert t.logger.list_all() == []
        t.cleanup()

    def test_list_all_after_save(self):
        t = _TempLogger()
        t.logger.save_log(_make_entry(source_project="proj_a"))
        t.logger.save_log(_make_entry(source_project="proj_b"))
        all_logs = t.logger.list_all()
        assert len(all_logs) == 2
        t.cleanup()

    def test_load_nonexistent(self):
        t = _TempLogger()
        assert t.logger.load_log("TB999.json") is None
        t.cleanup()

    def test_load_corrupted_file(self):
        t = _TempLogger()
        bad_file = Path(t._tmpdir) / "TB1.json"
        bad_file.write_text("not json", encoding="utf-8")
        loaded = t.logger.load_log("TB1.json")
        assert loaded is None
        t.cleanup()

    def test_multiple_saves_sequential_numbering(self):
        """多次保存应生成 TB1, TB2, TB3..."""
        t = _TempLogger()
        f1 = t.logger.save_log(_make_entry(source_project="proj", decision="pending"))
        f2 = t.logger.save_log(_make_entry(source_project="proj", decision="approved"))
        f3 = t.logger.save_log(_make_entry(source_project="proj2"))
        assert f1 == "TB1.json"
        assert f2 == "TB2.json"
        assert f3 == "TB3.json"
        assert len(t.logger.list_all()) == 3
        t.cleanup()

    def test_log_dir_created(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "subdir"
            logger = AssimilationLogger(log_dir=sub)
            assert sub.exists()
            logger.save_log(_make_entry())
            assert len(logger.list_all()) == 1


# ─── AssimilationLogger — 文件名 ──────────────────────────────────────────────

class TestFilenameNumbering:
    def test_json_filename_is_tb_format(self):
        t = _TempLogger()
        entry = _make_entry()
        fname = t.logger.save_log(entry)
        assert fname == "TB1.json"
        t.cleanup()

    def test_md_filename_is_tb_format(self):
        t = _TempLogger()
        entry = _make_entry()
        path = t.logger.save_log_markdown(entry)
        assert Path(path).name == "TB1.md"
        t.cleanup()

    def test_json_and_md_shared_numbering(self):
        """JSON 和 MD 共享序号序列。"""
        t = _TempLogger()
        t.logger.save_log(_make_entry())           # TB1.json
        t.logger.save_log_markdown(_make_entry())  # TB2.md
        t.logger.save_log(_make_entry())           # TB3.json
        t.logger.save_log_markdown(_make_entry())  # TB4.md
        files = sorted(Path(t._tmpdir).glob("TB*"))
        names = [f.name for f in files]
        assert "TB1.json" in names
        assert "TB3.json" in names
        assert "TB2.md" in names
        assert "TB4.md" in names
        assert len(names) == 4
        t.cleanup()

    def test_no_path_traversal_in_filename(self):
        """TB 序号命名天然免疫路径穿越。"""
        t = _TempLogger()
        entry = _make_entry(source_project="../../etc/passwd")
        fname = t.logger.save_log(entry)
        assert ".." not in fname
        assert fname == "TB1.json"
        t.cleanup()

    def test_filename_not_affected_by_project_name(self):
        """项目名不进入文件名，由 TB 序号替代。"""
        t = _TempLogger()
        entry = _make_entry(source_project="any_project_name")
        fname = t.logger.save_log(entry)
        assert fname == "TB1.json"
        t.cleanup()


# ─── AssimilationLogger — 搜索 ────────────────────────────────────────────────

class TestSearch:
    def test_search_by_project(self):
        t = _TempLogger()
        t.logger.save_log(_make_entry(source_project="openclaw"))
        t.logger.save_log(_make_entry(source_project="some_other"))
        results = t.logger.search_logs("openclaw", field="project")
        assert len(results) == 1
        assert results[0].source_project == "openclaw"
        t.cleanup()

    def test_search_by_capability(self):
        t = _TempLogger()
        t.logger.save_log(_make_entry(source_project="p1"))
        t.logger.save_log(_make_entry(source_project="p2", candidates=[
            CandidateCapability("data_analyzer", "m", 0.9, "low", "low", "data"),
        ]))
        results = t.logger.search_logs("data_analyzer", field="capability")
        assert len(results) == 1
        assert results[0].source_project == "p2"
        t.cleanup()

    def test_search_by_risk(self):
        t = _TempLogger()
        t.logger.save_log(_make_entry(source_project="safe", candidates=[
            CandidateCapability("s1", "m", 0.5, "low", "low", ""),
        ]))
        t.logger.save_log(_make_entry(source_project="risky", candidates=[
            CandidateCapability("danger", "m", 0.8, "high", "high", "危险操作"),
        ]))
        results = t.logger.search_logs("high", field="risk")
        assert len(results) >= 1
        t.cleanup()

    def test_search_by_decision(self):
        t = _TempLogger()
        t.logger.save_log(_make_entry(decision="approved"))
        t.logger.save_log(_make_entry(decision="rejected"))
        results = t.logger.search_logs("approved", field="decision")
        assert len(results) == 1
        t.cleanup()

    def test_search_all_fields(self):
        t = _TempLogger()
        t.logger.save_log(_make_entry(source_project="unique_proj"))
        results = t.logger.search_logs("unique_proj")
        assert len(results) == 1
        t.cleanup()

    def test_search_no_match(self):
        t = _TempLogger()
        t.logger.save_log(_make_entry())
        results = t.logger.search_logs("nonexistent")
        assert results == []
        t.cleanup()

    def test_search_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            logger = AssimilationLogger(log_dir=d)
            assert logger.search_logs("anything") == []


# ─── AssimilationLogger — 汇总 ────────────────────────────────────────────────

class TestSummarize:
    def test_summarize_project_history(self):
        t = _TempLogger()
        t.logger.save_log(_make_entry(source_project="proj"))
        t.logger.save_log(_make_entry(source_project="proj", decision="approved"))
        summary = t.logger.summarize_project_history("proj")
        assert summary["analysis_count"] == 2
        assert summary["decision"] == "approved"
        assert len(summary["candidate_skills"]) == 4  # 2 entries × 2 candidates
        t.cleanup()

    def test_summarize_no_history(self):
        with tempfile.TemporaryDirectory() as d:
            logger = AssimilationLogger(log_dir=d)
            summary = logger.summarize_project_history("nonexistent")
            assert summary["analysis_count"] == 0

    def test_summarize_avg_confidence(self):
        t = _TempLogger()
        t.logger.save_log(_make_entry(source_project="p", candidates=[
            CandidateCapability("s1", "m", 0.8, "low", "low", ""),
        ]))
        t.logger.save_log(_make_entry(source_project="p", candidates=[
            CandidateCapability("s2", "m", 0.6, "low", "low", ""),
        ]))
        summary = t.logger.summarize_project_history("p")
        assert summary["avg_confidence"] == pytest.approx(0.7)
        t.cleanup()

    def test_summarize_rejected_skills(self):
        t = _TempLogger()
        t.logger.save_log(_make_entry(source_project="p", rejected=[
            RejectedCapability("bad", "m", "违反冻结层"),
        ]))
        summary = t.logger.summarize_project_history("p")
        assert "bad" in summary["rejected_skills"]
        t.cleanup()


# ─── Markdown 导出 ────────────────────────────────────────────────────────────

class TestMarkdownExport:
    def test_save_markdown_creates_file(self):
        t = _TempLogger()
        entry = _make_entry()
        path = t.logger.save_log_markdown(entry)
        assert Path(path).exists()
        t.cleanup()

    def test_markdown_contains_key_sections(self):
        t = _TempLogger()
        entry = _make_entry()
        path = t.logger.save_log_markdown(entry)
        content = Path(path).read_text(encoding="utf-8")
        assert "吞并分析报告" in content
        assert "来源信息" in content
        assert "观察到的架构" in content
        assert "候选吞并能力" in content
        assert "已拒绝的能力" in content
        assert "吞并决策" in content
        t.cleanup()

    def test_markdown_has_yaml_frontmatter(self):
        t = _TempLogger()
        entry = _make_entry()
        path = t.logger.save_log_markdown(entry)
        content = Path(path).read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "project: test_project" in content
        t.cleanup()

    def test_markdown_no_future_notes_skips_section(self):
        t = _TempLogger()
        entry = _make_entry(future_notes="")
        path = t.logger.save_log_markdown(entry)
        content = Path(path).read_text(encoding="utf-8")
        assert "后续备注" not in content
        t.cleanup()


# ─── 边缘场景 ─────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_entry_with_empty_candidates(self):
        entry = _make_entry(candidates=[])
        assert len(entry.candidate_capabilities) == 0

    def test_entry_with_empty_rejected(self):
        entry = _make_entry(rejected=[])
        assert len(entry.rejected_capabilities) == 0

    def test_logger_default_dir(self):
        """LOG_DIR 常量必须在 ZSK/TBRZ/。"""
        assert "ZSK" in str(LOG_DIR)
        assert "TBRZ" in str(LOG_DIR)

    def test_json_roundtrip_preserves_all_fields(self):
        t = _TempLogger()
        entry = _make_entry(future_notes="需人工审核")
        fname = t.logger.save_log(entry)
        loaded = t.logger.load_log(fname)
        assert loaded.future_notes == "需人工审核"
        assert loaded.observed_architecture.modules == ["core", "api"]
        t.cleanup()
