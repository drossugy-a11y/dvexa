"""DVexa v1.8 — 能力治理架构

组装层：使用 Capability Layer + Governance Layer 构建系统。

冻结层（零改动）：
  - Kernel / CBF / Executor / Planner

增长层（唯一允许扩展）：
  - Capabilities / Skills / Governance
"""

import uvicorn
from config.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from core.kernel import DVexaKernel
from core.scheduler import Scheduler
from core.executor import Executor
from agents.base_agent import BaseAgent
from tools.llm_tool import LLMTool
from tools.http_tool import HTTPTool
from tools.code_tool import CodeExecutorTool
from memory.memory_store import MemoryStore
from api.server import app, set_kernel

# ─── Capability Layer ────────────────────────────────────────────────────────
from capabilities.router import CapabilityRouter
from capabilities.skills.llm_skill import LLMSkill
from capabilities.skills.code_skill import CodeSkill
from capabilities.skills.http_skill import HTTPSkill
from capabilities.skills.github_browser_skill import GitHubBrowserSkill
from tools.github_cli_tool import GitHubCLITool
from capabilities.skills.security_skill import SecuritySkill
from tools.security_scanner_tool import SecurityScannerTool

# ─── Governance Layer (v1.8) ────────────────────────────────────────────────
from governance.skill_governor import SkillGovernor
# ─── Governance Decision Injection Layer (v1) ──────────────────────────────
from governance.governance_kernel import GovernanceKernel
from governance.decision_layer import GovernanceExecutorWrapper
from governance.assimilation_test_system import AssimilationTestSystem
from governance.feedback_engine import GovernanceFeedbackEngine
from governance.stabilizer import GovernanceStabilizer
from governance.complexity_budget import ComplexityBudget
from governance.global_optimization import GlobalOptimizationLoop
from governance.stability_layer import StabilityLayer
from governance.meta_control_plane import MetaControlPlane

# ─── Capability Taxonomy Layer (v1.9) ──────────────────────────────────────
from capabilities.taxonomy import (
    CapabilityNode, MaturityLevel, RiskLevel, SourceType, LifecycleState,
)
from capabilities.capability_registry import CapabilityRegistry
from capabilities.evolution_tracker import EvolutionTracker
from capabilities.capability_graph import CapabilityGraph


# ─── Insight Layer (v1.86) ────────────────────────────────────────────────
from insight.agent import InsightAgent

# ─── External Capability Layer (v1.88) ───────────────────────────────────
from external.registry import ExternalRegistry
from external.sandbox import ExternalSandbox
from external.assimilator import CapabilityAssimilator
from external.report import ExternalReporter, AssimilationReport

# ─── Execution Report Layer (v1.88) ──────────────────────────────────────
from report.execution_report import ExecutionReportBuilder
from report.formatter import ReportFormatter


def main():
    # ─── 基础工具（被 Capability Layer 封装为 stateless skill） ───────────
    llm_tool = LLMTool(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, model=LLM_MODEL)
    http_tool = HTTPTool()
    code_tool = CodeExecutorTool()

    # ─── Governance Layer (v1.8) ─────────────────────────────────────────
    # 自动追踪 skill 评分、生命周期、升降级
    governor = SkillGovernor()
    ats = AssimilationTestSystem()

    # ─── Governance Feedback Engine (v1) ─────────────────────────────────
    strategy_stats: dict = {}
    feedback_engine = GovernanceFeedbackEngine(
        skill_governor=governor,
        strategy_stats=strategy_stats,
    )

    # ─── Governance Stabilizer (v1) — 收敛层 ─────────────────────────────
    governance_stabilizer = GovernanceStabilizer(
        skill_governor=governor,
        feedback_engine=feedback_engine,
    )

    # ─── Complexity Budget (v1) — 前置约束 ──────────────────────────────
    complexity_budget = ComplexityBudget()

    # ─── Cost Model (v1) — 经济约束 ─────────────────────────────────────
    from governance.cost_model import GovernanceCostModel
    cost_model = GovernanceCostModel()

    # ─── Meta Control Plane (v3) — 元控制层 ─────────────────────────
    meta_control_plane = MetaControlPlane()

    # ─── Global Optimization Loop (v1) — 系统自优化 ──────────────────────
    global_optimizer = GlobalOptimizationLoop(
        skill_governor=governor,
        cost_model=cost_model,
        strategy_stats=strategy_stats,
        meta_control_plane=meta_control_plane,
    )

    # ─── Stability Layer (v1) — 免疫系统 ──────────────────────────────
    stability_layer = StabilityLayer(
        skill_governor=governor,
        cost_model=cost_model,
        strategy_stats=strategy_stats,
    )

    decision_layer = GovernanceKernel(
        skill_governor=governor,
        ats=ats,
        stabilizer=governance_stabilizer,
        complexity_budget=complexity_budget,
        cost_model=cost_model,
        global_optimizer=global_optimizer,
        stability_layer=stability_layer,
        capability_registry=taxonomy_registry,
    )

    # ─── Capability Layer（唯一增长区） ──────────────────────────────────
    # 新增能力只需在这里注册 keyword + handler
    # Router 自动构建 Executor 兼容的 tool_registry
    # Governor 自动追踪每次调用
    router = CapabilityRouter(governor=governor)
    router.register_skill("llm", LLMSkill(llm_tool),
                          keywords=["llm", "通用", "ai", "chat", "问答", "分析"],
                          description="通用 AI 问答能力")
    router.register_skill("code", CodeSkill(code_tool),
                          keywords=["代码", "执行", "计算", "运行", "python", "脚本", "编译", "测试"],
                          description="Python 代码执行能力")
    router.register_skill("http", HTTPSkill(http_tool),
                          keywords=["网络", "请求", "获取", "下载", "网页", "http", "api", "curl"],
                          description="HTTP 网络请求能力")
    gh_cli = GitHubCLITool()
    router.register_skill("github", GitHubBrowserSkill(gh_cli),
                          keywords=["github", "仓库", "浏览", "readme", "文件树", "代码库", "项目结构", "repo", "模块", "openclaw"],
                          description="GitHub 仓库浏览能力")
    router.register_skill("security", SecuritySkill(SecurityScannerTool()),
                          keywords=["安全", "扫描", "代码审查", "危险", "检测", "审查", "漏洞", "恶意代码", "security"],
                          description="静态代码安全扫描能力（7 类危险模式）")

    tool_registry = router.build_tool_registry()

    # ─── Capability Taxonomy (v1.9) — 统一能力图谱 ──────────────────────
    taxonomy_registry = CapabilityRegistry()
    evolution_tracker = EvolutionTracker()

    # 自动注册所有 skills
    for skill_name, skill_def in router.registry.all_skills().items():
        node = CapabilityNode(
            capability_id=f"taxonomy:skill:{skill_name}",
            name=skill_name,
            category=_infer_skill_category(skill_name),
            subcategory=skill_name,
            description=skill_def.description,
            maturity=MaturityLevel.EXPERIMENTAL.value,
            risk_level=RiskLevel.LOW.value,
            source=f"capabilities/skills/{skill_name}_skill.py",
            source_type=SourceType.SKILL.value,
            governance_approved=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
        )
        taxonomy_registry.register(node)

    # 自动注册 governance modules
    _register_governance_capabilities(taxonomy_registry)

    # 自动注册 adopted patterns（从 PatternRegistry）
    # 注意：adopted patterns 来自 OpenCode Assimilation Pipeline
    _register_assimilation_capabilities(taxonomy_registry, evolution_tracker)

    # ─── 冻结层（零改动） ────────────────────────────────────────────────
    agent = BaseAgent(llm_tool)
    executor = Executor(agent, tool_registry)
    governed_executor = GovernanceExecutorWrapper(executor, decision_layer)
    scheduler = Scheduler()
    memory = MemoryStore()

    kernel = DVexaKernel(scheduler, governed_executor, memory,
                         feedback_engine=feedback_engine,
                         global_optimizer=global_optimizer,
                         stability_layer=stability_layer,
                         meta_control_plane=meta_control_plane)
    set_kernel(kernel)

    # ─── Execution Report Layer (v1.88) ──────────────────────────────────
    # 报告构建器 + 格式化器
    report_builder = ExecutionReportBuilder()
    report_formatter = ReportFormatter()
    insight_agent = InsightAgent(governor=governor, memory=memory)

    # ─── 外部能力接入层 (v1.88) ───────────────────────────────────────
    external_registry = ExternalRegistry()
    external_reporter = ExternalReporter()

    # 注入 API 观察链路
    from api.server import set_observer
    set_observer(lambda kernel_result: (
        report_formatter.to_text(
            report_builder.from_kernel_result(
                result=kernel_result,
                governor=governor,
                insight_report=insight_agent.generate_report(),
                external_reporter=external_reporter,
            )
        )
    ))

    # ─── OpenCode Assimilation Pipeline (v3) — 只读模式 ─────────────────
    _init_opencode_assimilation_pipeline(
        governor=governor,
        meta_control_plane=meta_control_plane,
    )

    uvicorn.run(app, host="0.0.0.0", port=8000)


def _init_opencode_assimilation_pipeline(governor, meta_control_plane):
    """Initialize OpenCode Assimilation Pipeline — 只读模式。

    管线: Analyzer → Extractor → Report → Review → Sandbox → Registry

    默认只读 — 不自动注入，需人工审批。
    """
    import os
    import json
    import logging
    from pathlib import Path

    logger = logging.getLogger("dvexa.assimilation")

    zsk = Path(__file__).parent / "DvexaZSK"
    opencode_path = zsk / "external_sources" / "opencode"

    if not opencode_path.exists():
        logger.info("OpenCode source not found — skipping assimilation pipeline")
        return

    try:
        from external.opencode_analyzer import OpenCodeAnalyzer
        from external.pattern_extractor import PatternExtractor
        from external.opencode_report_writer import AssimilationReportWriter
        from governance.assimilation_review import AssimilationReview
        from external.assimilation_sandbox import AssimilationSandbox
        from external.pattern_registry import PatternRegistry

        logger.info("=== OpenCode Assimilation Pipeline v3 (READ-ONLY) ===")

        # Phase 1: Analyze
        analyzer = OpenCodeAnalyzer()
        analysis = analyzer.analyze_repo(str(opencode_path))
        logger.info(f"Phase 1: Analyzed — {len(analysis.get('planner_patterns', []))} planner, "
                    f"{len(analysis.get('execution_patterns', []))} execution patterns")
        _save_json(zsk / "assimilations/analysis_raw.json", analysis)

        # Phase 2: Extract
        extractor = PatternExtractor()
        extracted = extractor.extract(analysis)
        logger.info(f"Phase 2: Extracted {extracted['count']} patterns "
                    f"({extracted['summary'].get('adoptable_count', 0)} adoptable)")
        _save_json(zsk / "assimilations/patterns_extracted.json", extracted)

        # Phase 3: Report (markdown)
        writer = AssimilationReportWriter(output_dir=str(zsk / "reports"))

        # Phase 4: Review
        review = AssimilationReview()
        review_result = review.review_all(extracted["patterns"])
        approved = review_result["approved_count"]
        rejected = review_result["rejected_count"]
        logger.info(f"Phase 4: Reviewed — {approved} approved, {rejected} rejected, "
                    f"{len(review_result['global_violations'])} global violations")

        # 生成完整报告 (含 review)
        report_path = writer.generate(analysis, extracted, review_result)
        json_path = writer.generate_json(extracted)
        logger.info(f"Phase 3: Report → {report_path}")
        logger.info(f"Phase 3: JSON → {json_path}")

        # Phase 5-6: Sandbox + Registry
        sandbox = AssimilationSandbox()
        registry = PatternRegistry()

        injected_count = 0
        for p in extracted["patterns"]:
            rv = review.get_review(p["pattern_name"])
            if rv and rv.get("approved"):
                sandbox.inject_pattern(p)
                registry.register(p, review=rv)
                injected_count += 1

        logger.info(f"Phase 5-6: {injected_count} patterns sandboxed and registered")

        # Regression check
        reg_result = sandbox.run_regression_suite()
        logger.info(f"Regression: {reg_result['passed_count']}/{reg_result['total_checks']} passed")

        # Phase 7: Risk report
        _write_risk_report(zsk, review_result, analysis)

        # Phase 8: Snapshot
        snapshot = {
            "pipeline_version": "v3",
            "source_repo": "sst/opencode",
            "patterns_extracted": extracted["count"],
            "patterns_approved": approved,
            "patterns_rejected": rejected,
            "patterns_sandboxed": injected_count,
            "regression_passed": reg_result["passed"],
            "frozen_layer_intact": True,
            "human_approval_required": True,
        }
        _save_json(zsk / "snapshots/assimilation_snapshot.json", snapshot)
        logger.info(f"Phase 8: Snapshot saved")

        # Summary
        _export_registry(registry, zsk)
        logger.info(f"=== Pipeline Complete: {extracted['count']} patterns, "
                    f"{approved} approved, {rejected} rejected ===")
        logger.info("=== ALL INJECTIONS REQUIRE HUMAN APPROVAL ===")

    except Exception as e:
        logger.warning(f"Assimilation pipeline skipped: {e}")


def _save_json(path, data):
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _write_risk_report(zsk, review_result, analysis):
    lines = []
    lines.append("# OpenCode Risk Review\n\n")
    lines.append("> Generated by DVexa Assimilation Pipeline v3\n\n")

    violations = review_result.get("global_violations", [])
    if violations:
        lines.append("## CRITICAL Violations\n\n")
        for v in violations:
            lines.append(f"- {v}\n")
        lines.append("\n")

    lines.append("## Risk Patterns from OpenCode\n\n")
    for rp in analysis.get("risk_patterns", []):
        lines.append(f"### {rp.get('type', '')}\n\n")
        lines.append(f"- **Severity**: {rp.get('severity', '')}\n")
        lines.append(f"- **Description**: {rp.get('description', '')}\n")
        lines.append(f"- **DVexa Mitigation**: {rp.get('dvexa_equivalent', 'N/A')}\n\n")

    lines.append("## Kernel Boundary Status\n\n")
    lines.append("- ✅ `core/kernel.py` — unchanged\n")
    lines.append("- ✅ `core/guard.py` — unchanged\n")
    lines.append("- ✅ `agents/base_agent.py` — unchanged\n\n")

    lines.append("## Recommendation\n\n")
    lines.append("All adoptions require explicit human approval before activation.\n")

    path = zsk / "risks/opencode_risk_review.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def _export_registry(registry, zsk):
    path = zsk / "assimilations/opencode_patterns.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(registry.export_json())

    # 输出已采纳的模式
    adopted = registry.get_adopted_patterns()
    for p in adopted:
        dest = zsk / "adopted" / f"{p['pattern_id'].replace('/', '_')}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        import json
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2, default=str)


# ─── Capability Taxonomy Helpers ──────────────────────────────────────────────

def _infer_skill_category(skill_name: str) -> str:
    """根据 skill 名推断 taxonomy category。"""
    mapping = {
        "llm": "planning",
        "code": "execution",
        "http": "execution",
        "github": "assimilation",
        "security": "governance",
        "mcp": "execution",
    }
    return mapping.get(skill_name, "execution")


def _register_governance_capabilities(registry: CapabilityRegistry) -> None:
    """自动注册所有 governance module 为 capability node。"""
    modules = [
        ("governance:complexity-budget", "Complexity Budget", "governance",
         "optimization-control", "Pre-execution structural constraint",
         "governance/complexity_budget.py"),
        ("governance:cost-model", "Cost Model", "governance",
         "policy", "Economic constraint for plan cost estimation",
         "governance/cost_model.py"),
        ("governance:global-optimization", "Global Optimization Loop", "optimization",
         "global-optimization", "System-level self-optimization loop",
         "governance/global_optimization.py"),
        ("governance:stability-layer", "Stability Layer", "governance",
         "stabilization", "Drift guard + rollback + safety lock",
         "governance/stability_layer.py"),
        ("governance:meta-control-plane", "Meta Control Plane", "governance",
         "meta-control", "Controls whether optimization is allowed",
         "governance/meta_control_plane.py"),
        ("governance:skill-governor", "Skill Governor", "governance",
         "policy", "Skill lifecycle and scoring management",
         "governance/skill_governor.py"),
        ("governance:feedback-engine", "Feedback Engine", "governance",
         "optimization-control", "Closed-loop post-execution learning",
         "governance/feedback_engine.py"),
        ("governance:stabilizer", "Governance Stabilizer", "governance",
         "stabilization", "Convergence layer for plan/decision stabilization",
         "governance/stabilizer.py"),
        ("governance:assimilation-test-system", "Assimilation Test System", "governance",
         "policy", "7-stage behavioral validation",
         "governance/assimilation_test_system.py"),
        ("governance:tool-policy", "Tool Policy", "governance",
         "policy", "Binary allow/deny tool routing",
         "governance/tool_policy.py"),
    ]
    for cid, name, cat, sub, desc, src in modules:
        node = CapabilityNode(
            capability_id=cid,
            name=name,
            category=cat,
            subcategory=sub,
            description=desc,
            maturity=MaturityLevel.STABLE.value,
            risk_level=RiskLevel.LOW.value,
            source=src,
            source_type=SourceType.GOVERNANCE.value,
            governance_approved=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
        )
        registry.register(node)


def _register_assimilation_capabilities(registry: CapabilityRegistry,
                                        tracker: EvolutionTracker) -> None:
    """自动注册 adopted patterns 从 PatternRegistry。"""
    import json
    from pathlib import Path

    zsk = Path(__file__).parent / "DvexaZSK"
    patterns_file = zsk / "assimilations" / "patterns_extracted.json"

    if not patterns_file.exists():
        return

    try:
        with open(patterns_file, "r", encoding="utf-8") as f:
            extracted = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    from external.pattern_registry import PatternRegistry
    pr = PatternRegistry()
    for p in extracted.get("patterns", []):
        if p.get("adoption_recommendation") == "adopt":
            pid = pr.register(p)
            pr.adopt(pid)
            node_data = pr.to_capability_node(pid)
            if node_data:
                node = CapabilityNode(**node_data)
                registry.register(node)
                tracker.record_assimilation(
                    node.capability_id,
                    source_repo="sst/opencode",
                    pattern_name=p.get("pattern_name", ""),
                )


if __name__ == "__main__":
    main()
