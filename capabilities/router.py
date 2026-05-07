"""Capability Router — 能力路由器

定位：executor 和 skill 之间的过滤层。
  选择 skill，不做判断，只做匹配。

与 Executor._select_tool 的关系：
  - _select_tool 是 Executor 内部的 keyword 匹配
  - CapabilityRouter 是独立的、可扩展的能力路由层
  - 两者互补：Router 提供更全面的能力发现，不改变 Executor 的控制逻辑

约束：
  ✗ 不允许"推理选工具"
  ✗ 不允许"动态策略选择"
  ✔ 只允许 keyword → skill mapping
"""

from __future__ import annotations
import time

from tools.base_tool import Tool
from capabilities.skill import SkillRegistry, SkillDef
from governance.skill_governor import SkillGovernor


class CapabilityRouter(Tool):
    """能力路由器 — 实现 Tool 接口，作为 executor 和 skill 之间的路由层。

    所有工具调用通过 Router 路由到具体 skill。
    Executor 通过 tool_registry 使用 Router，不感知路由过程。

    当 governor 存在时，自动使用 governance 评分选择最优 skill。
    """

    def __init__(self, registry: SkillRegistry | None = None, governor: SkillGovernor | None = None):
        self._registry = registry or SkillRegistry()
        self._governor = governor
        # 缓存由 registry 构建的 tool 映射，兼容 Executor 的 tool_registry
        self._tool_cache: dict[str, Tool] = {}

    def register_skill(self, name: str, handler, keywords: list[str] | None = None, description: str = ""):
        """注册技能到 Router，同时注册到 governor（如存在）。"""
        self._registry.register(name, handler, keywords, description)
        if self._governor:
            self._governor.register(name, handler, keywords, description)
        self._tool_cache.pop(name, None)  # 清除缓存，下次重建

    def match(self, action: str) -> str | None:
        """匹配 action 到技能名。"""
        return self._registry.match(action)

    def best_skill(self, action: str) -> SkillDef | None:
        """使用 governance 评分选择最优 skill。"""
        if self._governor:
            return self._governor.best_skill_for(action)
        # 无 governor 时退化为简单匹配
        name = self._registry.match(action)
        return self._registry.get(name) if name else None

    def call(self, input_data) -> dict:
        """实现 Tool.call(input) → dict 接口。

        当作为单一 tool 注册时使用。
        从 input_data 中解析技能名和输入，路由到对应 skill。
        """
        if isinstance(input_data, str):
            return {"content": f"[Router] 需指定技能名和输入，格式: {{\"skill\":\"...\",\"input\":\"...\"}}"}

        skill_name = input_data.get("skill", "")
        skill_input = input_data.get("input", "")

        skill = self._registry.get(skill_name)
        if not skill:
            return {"content": f"[Router] 技能不可用: {skill_name}"}

        return skill.handler.call(skill_input)

    def build_tool_registry(self) -> dict[str, Tool]:
        """构建兼容 Executor._call_tool 的 tool_registry。

        每个注册的技能生成一个 Tool 接口包装器。
        当 governor 存在时，包装器自动记录调用指标。
        """
        registry = {}
        for name, skill in self._registry.all_skills().items():
            if name not in self._tool_cache:
                if self._governor:
                    wrapper = _GovernedRouterSkill(skill, self._governor)
                else:
                    wrapper = _RouterSkill(skill)
                self._tool_cache[name] = wrapper
            registry[name] = self._tool_cache[name]

            # 同时注册 executor 兼容别名
            executor_name = _to_executor_name(name)
            if executor_name != name:
                registry[executor_name] = registry[name]

        return registry

    @property
    def skill_count(self) -> int:
        return self._registry.count

    @property
    def governor(self) -> SkillGovernor | None:
        return self._governor


class _RouterSkill(Tool):
    """RouterSkill — Tool 接口包装器。

    将 CapabilityRouter 中的 skill 包装为 Tool.call(input) → dict 接口。
    Executor 直接调用此包装器，不感知底层路由。
    """

    def __init__(self, skill_def):
        self._skill = skill_def

    def call(self, input_data) -> dict:
        return self._skill.handler.call(input_data)

    @property
    def name(self) -> str:
        return self._skill.name


class _GovernedRouterSkill(Tool):
    """受 governance 追踪的 Tool 接口包装器。

    自动记录每次调用的 success/failure + latency。
    """

    def __init__(self, skill_def, governor: SkillGovernor):
        self._skill = skill_def
        self._governor = governor

    def call(self, input_data) -> dict:
        start = time.time()
        try:
            result = self._skill.handler.call(input_data)
            latency = time.time() - start
            is_error = isinstance(result, dict) and any(
                kw in str(result.get("content", "")).lower()
                for kw in ["错误", "失败", "error", "不可用"]
            )
            self._governor.record_call(self._skill.name, success=not is_error, latency=latency)
            return result
        except Exception as e:
            latency = time.time() - start
            self._governor.record_call(self._skill.name, success=False, latency=latency, error=str(e))
            return {"content": f"[Governance Router] {self._skill.name} 调用异常: {str(e)}"}

    @property
    def name(self) -> str:
        return self._skill.name


def _to_executor_name(skill_name: str) -> str:
    """将技能名转换为 Executor 兼容的工具名。"""
    mapping = {
        "code": "code_executor",
        "http": "http_request",
        "llm": "llm",
    }
    return mapping.get(skill_name, skill_name)
