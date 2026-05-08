"""OpenClaw Report Writer — 吞并分析报告生成

将 OpenClawAnalyzer 的输出写入两份：
  1. ZSK/TBRZ/TB{N}.json — 机器日志（通过 AssimilationLogger）
  2. TBRZ/reports/YYYY-MM-DD_项目名_report.md — 人类可读报告

红线：
  - 纯文件 IO
  - 不涉及任何系统控制层
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path

from external.assimilation_log import AssimilationLogEntry, AssimilationLogger


class OpenClawReportWriter:
    """吞并分析报告写入器。"""

    def __init__(self, logger: AssimilationLogger, report_dir: str | Path | None = None):
        self._logger = logger
        report_dir = report_dir or Path(__file__).resolve().parent.parent / "TBRZ" / "reports"
        self._report_dir = Path(report_dir)
        self._report_dir.mkdir(parents=True, exist_ok=True)

    def write(self, analysis: dict, repo_url: str) -> dict:
        """写入分析报告和日志，返回文件路径。"""
        owner_repo = analysis.get("meta", {}).get("full_name", "unknown")

        # 1. 写入 AssimilationLog
        tb_file = self._write_assimilation_log(analysis, owner_repo)

        # 2. 写入 Markdown 报告
        report_path = self._write_markdown_report(analysis, owner_repo, repo_url)

        return {
            "tb_log_file": tb_file,
            "report_file": report_path.name,
            "report_path": str(report_path),
            "status": "ok",
        }

    def _write_assimilation_log(self, analysis: dict, owner_repo: str) -> str:
        """写入 TB 序号日志。"""
        candidates = []
        for c in analysis.get("candidate_skills", []):
            candidates.append({
                "candidate_skill": c["name"],
                "source_module": c["source_module"],
                "confidence": c.get("relevance", 0.5),
                "complexity": c.get("complexity", "medium"),
                "risk": "low",
                "estimated_value": c.get("description", ""),
            })

        rejected = []
        for s in analysis.get("merge_suggestions", []):
            if s.get("action") == "reject":
                rejected.append({
                    "candidate_skill": s["module"].split("/")[-1].replace(".py", ""),
                    "source_module": s["module"],
                    "reason": s.get("rationale", "人工决策"),
                })

        arch = analysis.get("architecture", {})
        summary = analysis.get("project_summary", {})

        entry = AssimilationLogEntry(
            source_project=owner_repo,
            analysis_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            decision="pending",
            observed_architecture={
                "modules": arch.get("top_level_dirs", []),
                "agents": [],
                "tools": [],
                "memory": [],
                "workflow": [],
            },
            candidate_capabilities=candidates,
            rejected_capabilities=rejected,
            future_notes=f"星级: {summary.get('stars', 0)} | 语言: {summary.get('language', '')} | 分析自动生成",
        )

        return self._logger.save_log(entry)

    def _write_markdown_report(self, analysis: dict, owner_repo: str, repo_url: str) -> Path:
        """生成人类可读的 Markdown 报告。"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_name = owner_repo.replace("/", "_")
        filename = f"{date_str}_{safe_name}_report.md"
        filepath = self._report_dir / filename

        lines = [
            f"# {owner_repo} — 吞并分析报告",
            "",
            f"> **分析时间**: {analysis.get('meta', {}).get('analyzed_at', '')}",
            f"> **仓库地址**: {repo_url}",
            "",
            "---",
            "",
            "## 1. 项目摘要",
            "",
        ]

        summary = analysis.get("project_summary", {})
        lines.extend([
            f"- **名称**: {summary.get('name', '')}",
            f"- **描述**: {summary.get('description', '')}",
            f"- **主要语言**: {summary.get('language', '')}",
            f"- **星级**: {summary.get('stars', 0)}",
            f"- **许可证**: {summary.get('license', '未标注')}",
            f"- **磁盘占用**: {summary.get('disk_usage_kb', 0)} KB",
            "",
            "---",
            "",
            "## 2. 架构分析",
            "",
        ])

        arch = analysis.get("architecture", {})
        lines.extend([
            f"- **文件数**: {arch.get('file_count', 0)}",
            f"- **目录数**: {arch.get('dir_count', 0)}",
            f"- **Python 文件**: {arch.get('python_files', 0)}",
            f"- **顶层目录**: {', '.join(arch.get('top_level_dirs', []))}",
            "",
            "### 扩展名分布",
            "",
        ])
        for ext, count in arch.get("extension_breakdown", {}).items():
            lines.append(f"- `.{ext}`: {count} 个文件")
        lines.append("")

        if arch.get("dependencies"):
            lines.append("### 依赖文件")
            lines.append("")
            for dep in arch["dependencies"]:
                lines.append(f"- `{dep['path']}`")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## 3. 候选吞并能力",
            "",
        ])

        for c in analysis.get("candidate_skills", []):
            lines.extend([
                f"### {c['name']}",
                f"- **来源**: `{c['source_module']}`",
                f"- **类型**: {c.get('type_hint', '未分类')}",
                f"- **复杂度**: {c.get('complexity', 'medium')}",
                f"- **相关度**: {c.get('relevance', 0)}",
                f"- **描述**: {c.get('description', '')}",
                "",
            ])

        if not analysis.get("candidate_skills"):
            lines.append("_未发现可直接吞并的能力_")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## 4. 风险分析",
            "",
        ])

        for r in analysis.get("risk_analysis", []):
            level_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(r.get("level", ""), "⚪")
            lines.append(f"- {level_icon} **{r.get('category', '')}**: {r.get('detail', '')}")
        lines.append("")

        lines.extend([
            "---",
            "",
            "## 5. 冻结层影响评估",
            "",
        ])
        lines.append("无直接影响 — 所有能力均为增长层候选")
        lines.append("")

        lines.extend([
            "---",
            "",
            "## 6. 吞并建议",
            "",
        ])

        for s in analysis.get("merge_suggestions", []):
            action_icon = {
                "assimilate_as_skill": "✅", "extract_pattern": "📐",
                "reference_only": "📖", "reject": "❌",
            }.get(s.get("action", ""), "⚪")
            lines.append(f"### {action_icon} `{s['module']}`")
            lines.append(f"- **动作**: {s.get('action', '')}")
            lines.append(f"- **优先级**: {s.get('priority', 5)}")
            lines.append(f"- **理由**: {s.get('rationale', '')}")
            lines.append(f"- **重构方式**: {s.get('refactor_type', '')}")
            lines.append(f"- **工作量**: {s.get('estimated_effort', 'medium')}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## 7. 推荐策略",
            "",
        ])

        strategy = analysis.get("recommended_strategy", {})
        lines.append(f"- **总体策略**: {strategy.get('overall_approach', '')}")
        lines.append(f"- **快速吞并** ({len(strategy.get('quick_wins', []))} 个):")
        for m in strategy.get("quick_wins", []):
            lines.append(f"  - ✅ `{m}`")
        lines.append(f"- **需人工审查** ({len(strategy.get('needs_human_review', []))} 个):")
        for m in strategy.get("needs_human_review", []):
            lines.append(f"  - 🔍 `{m}`")
        lines.append(f"- **建议拒绝** ({len(strategy.get('should_reject', []))} 个):")
        for m in strategy.get("should_reject", []):
            lines.append(f"  - ❌ `{m}`")
        lines.append("")

        lines.extend([
            "---",
            "",
            "## 8. 人工审批清单",
            "",
            "请在以下能力中选择操作：",
            "",
        ])

        for i, c in enumerate(analysis.get("candidate_skills", []), 1):
            lines.extend([
                f"- [ ] `{c['name']}` (来自 `{c['source_module']}`)",
                f"  - 选项: 1)吞并 2)重构后吞并 3)拒绝 4)延后",
                "",
            ])

        filepath.write_text("\n".join(lines), encoding="utf-8")
        return filepath
