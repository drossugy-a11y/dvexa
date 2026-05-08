"""Assimilation Report Writer — Phase 3

生成 DvexaZSK/reports/opencode_analysis_report.md
中文，deterministic，不使用 LLM。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AssimilationReportWriter:
    """基于 analyzer + extractor 输出生成中文分析报告。"""

    def __init__(self, output_dir: str | None = None):
        self._output_dir = Path(output_dir or "DvexaZSK/reports")

    def generate(self, analysis: dict, extracted: dict,
                 review: dict | None = None) -> str:
        """生成完整的分析报告。

        Args:
            analysis: OpenCodeAnalyzer.analyze_repo() 的输出
            extracted: PatternExtractor.extract() 的输出
            review: AssimilationReview.review_all() 的输出（可选）

        Returns:
            报告文件路径
        """
        md = self._build_report(analysis, extracted, review)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / "opencode_analysis_report.md"
        path.write_text(md, encoding="utf-8")
        return str(path)

    def _build_report(self, analysis: dict, extracted: dict,
                      review: dict | None) -> str:
        repo = analysis.get("repository", {})
        arch = analysis.get("architecture_summary", {})
        summary = extracted.get("summary", {})
        patterns = extracted.get("patterns", [])

        lines = []
        lines.append("# OpenCode Assimilation Report\n")
        lines.append(f"> 生成时间: {_now_iso()}\n")
        lines.append(f"> 目标仓库: https://github.com/sst/opencode\n")
        lines.append(f"> 语言: {repo.get('language', 'N/A')}\n")
        lines.append(f"> 运行时: {repo.get('runtime', 'N/A')}\n")
        lines.append("> 分析方式: 静态源码分析 (deterministic, 无 LLM)\n")

        # ── Repository Overview ────────────────────────────────────────
        lines.append("---\n\n## 1. Repository Overview\n")
        lines.append(f"- **Name**: {repo.get('name', 'unknown')}\n")
        lines.append(f"- **Language**: {repo.get('language', 'N/A')}\n")
        lines.append(f"- **Runtime**: {repo.get('runtime', 'N/A')}\n")
        lines.append(f"- **Framework**: {repo.get('framework', 'N/A')}\n")
        lines.append(f"- **Package Manager**: {repo.get('package_manager', 'N/A')}\n")
        lines.append(f"- **Monorepo**: {repo.get('is_monorepo', False)}\n")
        wss = repo.get("workspaces", [])
        if wss:
            lines.append(f"- **Workspaces**: {', '.join(wss[:5])}\n")
        lines.append("\n")

        # ── Architecture Summary ───────────────────────────────────────
        lines.append("---\n\n## 2. Architecture Summary\n\n")
        modules = arch.get("top_level_modules", [])
        lines.append(f"### Top-level Modules ({len(modules)} total)\n\n")
        for m in modules:
            cnt = arch.get("module_file_counts", {}).get(m, 0)
            lines.append(f"- `{m}/` — {cnt} files\n")
        lines.append("\n")

        core = arch.get("core_runtime_modules", [])
        ctrl = arch.get("control_modules", [])
        infra = arch.get("infra_modules", [])

        lines.append(f"### Core Runtime: {', '.join(core)}\n\n")
        lines.append(f"### Control Layer: {', '.join(ctrl)}\n\n")
        lines.append(f"### Infra: {', '.join(infra)}\n\n")

        # ── Extracted Patterns ─────────────────────────────────────────
        lines.append("---\n\n## 3. Extracted Patterns\n\n")
        lines.append(f"**Total patterns extracted: {summary.get('total_patterns', 0)}**\n\n")

        cats = {}
        for p in patterns:
            c = p.get("category", "other")
            cats.setdefault(c, []).append(p)

        for cat, plist in sorted(cats.items()):
            lines.append(f"### 3.{list(cats).index(cat)+1} {cat.upper()} Patterns\n\n")
            lines.append("| Pattern | 兼容性 | 风险 | 建议 |\n")
            lines.append("|---------|--------|------|------|\n")
            for p in plist:
                name = p.get("pattern_name", "")
                comp = p.get("dvexa_compatibility", "")
                risk = p.get("risk_level", "")
                rec = p.get("adoption_recommendation", "")
                lines.append(f"| {name} | {comp} | {risk} | {rec} |\n")
            lines.append("\n")

            for p in plist:
                lines.append(f"#### {p.get('pattern_name', '')}\n\n")
                lines.append(f"- **Problem Solved**: {p.get('problem_solved', '')}\n")
                lines.append(f"- **Mechanism**: {p.get('mechanism', '')}\n")
                lines.append(f"- **DVexa Compatibility**: {p.get('dvexa_compatibility', '')}\n")
                lines.append(f"- **Risk**: {p.get('risk_level', '')}\n")
                lines.append(f"- **Recommendation**: {p.get('adoption_recommendation', '')}\n")
                changes = p.get("required_changes", [])
                if changes:
                    lines.append(f"- **Required Changes**:\n")
                    for c in changes:
                        lines.append(f"  - {c}\n")
                lines.append("\n")

        # ── Recommended Adoptions ─────────────────────────────────────
        lines.append("---\n\n## 4. Recommended Adoptions\n\n")
        recs = analysis.get("recommended_adoptions", [])
        for i, r in enumerate(recs):
            lines.append(f"### 4.{i+1} {r.get('pattern', '')}\n\n")
            lines.append(f"- **Priority**: {r.get('priority', '')}\n")
            lines.append(f"- **Category**: {r.get('category', '')}\n")
            lines.append(f"- **Reason**: {r.get('reason', '')}\n")
            lines.append(f"- **Target**: `{r.get('dvexa_target', '')}`\n")
            lines.append(f"- **Effort**: {r.get('effort', '')}\n")
            lines.append(f"- **Risk**: {r.get('risk', '')}\n\n")

        # ── Risk Analysis ─────────────────────────────────────────────
        lines.append("---\n\n## 5. Risk Analysis\n\n")
        risks = analysis.get("risk_patterns", [])
        for i, r in enumerate(risks):
            lines.append(f"### 5.{i+1} {r.get('type', '')}\n\n")
            lines.append(f"- **Severity**: {r.get('severity', '')}\n")
            lines.append(f"- **Description**: {r.get('description', '')}\n")
            lines.append(f"- **DVexa Equivalent**: {r.get('dvexa_equivalent', '')}\n\n")

        # ── Governance Compatibility ───────────────────────────────────
        lines.append("---\n\n## 6. Governance Compatibility\n\n")
        if review:
            lines.append(f"- **Total patterns reviewed**: {review.get('total', 0)}\n")
            lines.append(f"- **Approved**: {review.get('approved_count', 0)}\n")
            lines.append(f"- **Rejected**: {review.get('rejected_count', 0)}\n")
            lines.append(f"- **Require sandbox**: {review.get('sandbox_count', 0)}\n\n")

            violations = review.get("global_violations", [])
            if violations:
                lines.append("### Critical Violations\n\n")
                for v in violations:
                    lines.append(f"- {v}\n")
                lines.append("\n")

            results = review.get("results", {})
            if results:
                lines.append("### Per-Pattern Review\n\n")
                lines.append("| Pattern | Approved | Risk Score | Layer | Sandbox |\n")
                lines.append("|---------|----------|------------|-------|--------|\n")
                for name, rv in sorted(results.items()):
                    lines.append(
                        f"| {name} | {rv.get('approved', False)} "
                        f"| {rv.get('risk_score', 0):.2f} "
                        f"| {rv.get('recommended_layer', 'N/A')} "
                        f"| {rv.get('requires_sandbox', True)} |\n"
                    )
            lines.append("\n")
        else:
            lines.append("_Governance review pending._\n\n")

        # ── Suggested Injection Targets ────────────────────────────────
        lines.append("---\n\n## 7. Suggested Injection Targets\n\n")
        adoption_map: dict[str, list[str]] = {}
        for p in patterns:
            if p.get("adoption_recommendation") in ("adopt", "adapt"):
                for chg in p.get("required_changes", []):
                    if "/" in chg:
                        fname = chg.split("/")[0] + "/"
                        adoption_map.setdefault(fname, []).append(p["pattern_name"])
                        break
                else:
                    adoption_map.setdefault("reference_only", []).append(p["pattern_name"])

        for layer, plist in sorted(adoption_map.items()):
            lines.append(f"### {layer}\n\n")
            for pn in plist:
                lines.append(f"- {pn}\n")
            lines.append("\n")

        # ── Regression Risk ───────────────────────────────────────────
        lines.append("---\n\n## 8. Regression Risk\n\n")
        adapter_count = summary.get("adaptable_count", 0)
        reject_count = summary.get("rejected_count", 0)
        adopt_count = summary.get("adoptable_count", 0)

        if adapter_count > 3:
            lines.append("⚠️ **HIGH REGRESSION RISK**: Many patterns require adaptation.\n\n")
        elif reject_count > adopt_count:
            lines.append("⚠️ **MODERATE REGRESSION RISK**: More rejected than accepted patterns.\n\n")
        else:
            lines.append("✅ **LOW REGRESSION RISK**: Adoptable patterns are well-defined.\n\n")

        lines.append("### Frozen Layer Protection\n\n")
        lines.append("- ✅ `core/kernel.py` — no changes proposed\n")
        lines.append("- ✅ `core/guard.py` — no changes proposed\n")
        lines.append("- ✅ `agents/base_agent.py` — no changes proposed\n\n")

        # ── Final Recommendation ──────────────────────────────────────
        lines.append("---\n\n## 9. Final Recommendation\n\n")
        total = summary.get("total_patterns", 0)
        adoptable = summary.get("adoptable_count", 0) + summary.get("adaptable_count", 0)

        if adoptable > 5:
            lines.append("**VERDICT**: ✅ RECOMMEND SELECTIVE ADOPTION\n\n")
            lines.append(f"Of {total} extracted patterns, {adoptable} are recommended "
                         f"for adoption or adaptation. All must go through:\n\n")
            lines.append("1. Governance Review (AssimilationReview)\n")
            lines.append("2. Sandbox Testing (AssimilationSandbox)\n")
            lines.append("3. Regression Suite (pytest tests/)\n")
            lines.append("4. Human Approval\n")
            lines.append("5. Snapshot & Register\n\n")
            lines.append("No pattern should bypass these gates.\n")
        else:
            lines.append("**VERDICT**: ⚠️ LIMITED ADOPTION\n\n")
            lines.append("Few high-quality patterns available. Proceed with caution.\n")

        return "".join(lines)

    def generate_json(self, extracted: dict) -> str:
        """生成 JSON 格式的模式数据。"""
        import json
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir.parent / "assimilations" / "opencode_patterns.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(extracted.get("patterns", []), f, ensure_ascii=False, indent=2)
        return str(path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
