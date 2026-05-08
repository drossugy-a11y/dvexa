#!/usr/bin/env python3
"""OpenClaw 吞并流水线手动运行脚本

用法：
  python3 scripts/test_openclaw_pipeline.py [仓库URL]

默认分析: https://github.com/drossugy-a11y/OpenClaw
"""

import sys
import json
from pathlib import Path

# 确保项目根在 path 上
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.github_cli_tool import GitHubCLITool
from external.openclaw_analyzer import OpenClawAnalyzer
from external.openclaw_report_writer import OpenClawReportWriter
from external.assimilation_log import AssimilationLogger


def main():
    repo_url = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/drossugy-a11y/OpenClaw"

    print(f"╔══════════════════════════════════════════════╗")
    print(f"║  DVexa v1.89 — 吞并流水线                    ║")
    print(f"╚══════════════════════════════════════════════╝")
    print()
    print(f"分析仓库: {repo_url}")
    print()

    # ─── Step 1: Browse ─────────────────────────────────
    print("▶ Step 1/3: 浏览仓库...")
    gh = GitHubCLITool()
    analyzer = OpenClawAnalyzer(gh)

    # ─── Step 2: Analyze ────────────────────────────────
    print("▶ Step 2/3: 分析架构...")
    result = analyzer.analyze(repo_url)

    if "error" in result:
        print(f"❌ 分析失败: {result['error']}")
        sys.exit(1)

    summary = result.get("project_summary", {})
    print(f"  ├─ 项目: {summary.get('name', '?')}")
    print(f"  ├─ 描述: {summary.get('description', '?')[:60]}")
    print(f"  ├─ 语言: {summary.get('language', '?')}")
    print(f"  ├─ 星级: {summary.get('stars', 0)}")
    print(f"  ├─ 许可证: {summary.get('license', '?')}")
    print(f"  └─ 候选技能: {len(result.get('candidate_skills', []))} 个")
    print()

    # ─── Step 3: Report ─────────────────────────────────
    print("▶ Step 3/3: 生成报告...")
    logger = AssimilationLogger()
    writer = OpenClawReportWriter(logger)
    report = writer.write(result, repo_url)

    print(f"  ├─ 日志: {report['tb_log_file']}")
    print(f"  └─ 报告: {report['report_path']}")
    print()
    print("✅ 流水线完成！")
    print()

    # ─── 展示候选技能 ────────────────────────────────────
    print("══════════════════════════════════════════════")
    print("候选吞并能力:")
    print()
    for i, s in enumerate(result.get("candidate_skills", []), 1):
        print(f"  [{i}] {s['name']}")
        print(f"     来源: {s['source_module']}")
        print(f"     类型: {s.get('type_hint', '?')}")
        print(f"     复杂度: {s.get('complexity', '?')}")
        print(f"     相关度: {s.get('relevance', 0)}")
        print()

    strategy = result.get("recommended_strategy", {})
    print("══════════════════════════════════════════════")
    print("推荐策略:")
    print(f"  {strategy.get('overall_approach', '?')}")
    print()
    print(f"  快速吞并 ({len(strategy.get('quick_wins', []))} 个):")
    for m in strategy.get("quick_wins", []):
        print(f"    ✅ {m}")
    print()
    print(f"  需人工审查 ({len(strategy.get('needs_human_review', []))} 个):")
    for m in strategy.get("needs_human_review", []):
        print(f"    🔍 {m}")
    print()
    print(f"  建议拒绝 ({len(strategy.get('should_reject', []))} 个):")
    for m in strategy.get("should_reject", []):
        print(f"    ❌ {m}")
    print()
    print("══════════════════════════════════════════════")
    print("下一步: 人工审批以上候选能力，然后执行吞并。")
    print(f"完整报告: {report['report_path']}")


if __name__ == "__main__":
    main()
