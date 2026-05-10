"""Governance Types — HARD/SOFT 治理分类

HARD Governance:  100% deterministic，不依赖 LLM 推理
SOFT Governance:  允许 LLM-assisted evaluation
"""

from __future__ import annotations

from enum import Enum


class GovernanceType(str, Enum):
    HARD = "hard"      # 确定性规则，可 replay，可审计
    SOFT = "soft"      # LLM-assisted，建议性质


class GovCheckpoint:
    """治理检查点描述。"""

    def __init__(self, name: str, gov_type: GovernanceType,
                 description: str, deterministic: bool = True):
        self.name = name
        self.gov_type = gov_type
        self.description = description
        self.deterministic = deterministic

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.gov_type.value,
            "deterministic": self.deterministic,
            "description": self.description,
        }


# ── 预定义检查点 ──────────────────────────────────────────────────────

CHECKPOINTS: dict[str, GovCheckpoint] = {
    "tool_policy": GovCheckpoint(
        name="ToolPolicy",
        gov_type=GovernanceType.HARD,
        description="二进制允许/禁止工具调用。确定性规则。",
    ),
    "ats_validation": GovCheckpoint(
        name="ATS",
        gov_type=GovernanceType.HARD,
        description="7 阶段行为验证。确定性测试流水线。",
    ),
    "skill_score": GovCheckpoint(
        name="SkillScore",
        gov_type=GovernanceType.HARD,
        description="Skill 评分门控：score < threshold → reroute/downgrade。",
    ),
    "lifecycle": GovCheckpoint(
        name="Lifecycle",
        gov_type=GovernanceType.HARD,
        description="生命周期检查：experimental/active/deprecated/retired。",
    ),
    "strategy_override": GovCheckpoint(
        name="StrategyOverride",
        gov_type=GovernanceType.SOFT,
        description="策略覆盖建议。基于历史统计可调整。",
    ),
    "complexity_budget": GovCheckpoint(
        name="ComplexityBudget",
        gov_type=GovernanceType.HARD,
        description="前置结构约束：步骤数、嵌套深度。确定性。",
    ),
    "cost_model": GovCheckpoint(
        name="CostModel",
        gov_type=GovernanceType.HARD,
        description="经济约束：token 预算、成本上限。可计算。",
    ),
    "optimization_gate": GovCheckpoint(
        name="OptimizationGate",
        gov_type=GovernanceType.HARD,
        description="MetaControlPlane 闸门：health/drift 检查。确定性。",
    ),
}
