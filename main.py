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

# ─── Governance Layer (v1.8) ────────────────────────────────────────────────
from governance.skill_governor import SkillGovernor


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

    tool_registry = router.build_tool_registry()

    # ─── 冻结层（零改动） ────────────────────────────────────────────────
    agent = BaseAgent(llm_tool)
    executor = Executor(agent, tool_registry)
    scheduler = Scheduler()
    memory = MemoryStore()

    kernel = DVexaKernel(scheduler, executor, memory)
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

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
