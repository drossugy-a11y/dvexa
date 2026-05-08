"""DXB Optimizer v2.0 — 结构级 DXB 优化器

仅做结构优化，不修改语义，不做治理决策。
优化必须是安全的（不改变执行结果）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from compiler_v2.capability_ir import CapabilityStep, DXB


@dataclass
class OptimizationReport:
    """优化报告。"""
    original_step_count: int = 0
    optimized_step_count: int = 0
    removed_steps: list[str] = field(default_factory=list)
    merged_steps: list[dict[str, str]] = field(default_factory=list)
    optimizations_applied: list[str] = field(default_factory=list)


class DXBOptimizer:
    """DXB 结构优化器 — 仅做安全的、结构级的优化。

    允许的优化:
      - 合并冗余步骤（相同 capability_ref + 相同 inputs 的步骤）
      - 移除不可达节点（无入边且不在 DAG 中的步骤）
      - 去重约束（移除 constraints 中的重复项）
      - 安全重排序（在不违反依赖的前提下尽量并行化）

    禁止的优化:
      - 修改风险评分
      - 修改治理约束
      - 语义层面的重新解释
      - 添加/删除能力引用
    """

    def optimize(self, dxb: DXB) -> OptimizationReport:
        """对 DXB 执行结构优化（就地优化）。

        Args:
            dxb: 待优化的 DXB

        Returns:
            OptimizationReport 包含优化详情
        """
        report = OptimizationReport(original_step_count=dxb.step_count)

        # 1. Deduplicate steps
        self._deduplicate_steps(dxb, report)

        # 2. Remove unreachable nodes
        self._remove_unreachable(dxb, report)

        # 3. Deduplicate constraints
        self._deduplicate_constraints(dxb, report)

        # 4. Collapse linear chains
        self._collapse_linear_chains(dxb, report)

        report.optimized_step_count = dxb.step_count
        return report

    # ── Optimization Pass 1: Deduplicate steps ────────────────────

    def _deduplicate_steps(
        self, dxb: DXB, report: OptimizationReport
    ) -> None:
        """合并具有相同 capability_ref 和 inputs 的冗余步骤。

        保留第一个步骤，将后续重复步骤的依赖者重定向到第一个。
        """
        seen: dict[tuple[str, str], CapabilityStep] = {}
        new_steps: list[CapabilityStep] = []
        redirect: dict[str, str] = {}  # old_id → new_id

        for step in dxb.steps:
            # Build a signature from capability_ref + key inputs
            inputs_key = str(sorted(step.inputs.items())) if step.inputs else ""
            sig = (step.capability_ref, inputs_key)

            if sig in seen:
                # Redirect all references to the first occurrence
                redirect[step.id] = seen[sig].id
                report.removed_steps.append(step.id)
                report.merged_steps.append({
                    "removed": step.id,
                    "kept": seen[sig].id,
                    "capability_ref": step.capability_ref,
                })
            else:
                seen[sig] = step
                new_steps.append(step)

        if redirect:
            # Update dependencies in remaining steps
            final_steps: list[CapabilityStep] = []
            for step in new_steps:
                new_deps = [redirect.get(d, d) for d in step.dependencies]
                if step.id not in redirect:
                    final_steps.append(CapabilityStep(
                        id=step.id,
                        step_type=step.step_type,
                        capability_ref=step.capability_ref,
                        inputs=dict(step.inputs),
                        dependencies=new_deps,
                        risk=step.risk,
                        preconditions=list(step.preconditions),
                        postconditions=list(step.postconditions),
                        expected_output=dict(step.expected_output),
                    ))

            dxb.steps = final_steps
            # Rebuild DAG
            dxb._build_dag()
            report.optimizations_applied.append("deduplicate_steps")

    # ── Optimization Pass 2: Remove unreachable nodes ─────────────

    def _remove_unreachable(
        self, dxb: DXB, report: OptimizationReport
    ) -> None:
        """移除没有任何入边且不在任何依赖链中的步骤。

        保留:
        - 所有被其他步骤依赖的步骤
        - 所有作为 DAG 入口的步骤
        - GOVERNANCE-PRESENCE LOCK: 有 SKILL 但无 GOV 时不删除任何步骤
        - GOVERNANCE_CHECK 和 SKILL 步骤受保护，不允许被删除
        """
        if len(dxb.steps) == 0:
            return

        # GOVERNANCE-PRESENCE LOCK
        # 如果存在 SKILL 但没有 GOVERNANCE_CHECK，不执行任何删除
        # 治理缺失应由 validator 阻断，optimizer 不隐式"修复"它
        has_gov = any(s.step_type == "GOVERNANCE_CHECK" for s in dxb.steps)
        has_skill = any(s.step_type == "SKILL" for s in dxb.steps)
        if has_skill and not has_gov:
            report.optimizations_applied.append("gov_lock_preserved")
            return

        # 保护 GOV 和 SKILL 步骤不被删除
        protected_ids: set[str] = set()
        for step in dxb.steps:
            if step.step_type in ("GOVERNANCE_CHECK", "SKILL"):
                protected_ids.add(step.id)

        # Find all steps that are referenced as dependencies
        referenced: set[str] = set()
        for step in dxb.steps:
            for dep in step.dependencies:
                referenced.add(dep)

        # Steps that are not referenced by anyone AND have no dependencies
        # are truly isolated — EXCLUDING protected types
        isolated: set[str] = set()
        for step in dxb.steps:
            if step.id not in referenced and not step.dependencies:
                if step.id not in protected_ids:
                    isolated.add(step.id)

        if isolated:
            new_steps = [s for s in dxb.steps if s.id not in isolated]
            if new_steps:
                dxb.steps = new_steps
                dxb._build_dag()
                for sid in isolated:
                    report.removed_steps.append(sid)
                report.optimizations_applied.append("remove_unreachable")

    # ── Optimization Pass 3: Deduplicate constraints ──────────────

    def _deduplicate_constraints(
        self, dxb: DXB, report: OptimizationReport
    ) -> None:
        """移除 constraints 中的重复条目。"""
        before = len(dxb.constraints)
        # Recursively deduplicate list values in constraints
        self._dedup_lists_in_dict(dxb.constraints)
        after = len(dxb.constraints)
        if before != after:
            report.optimizations_applied.append("deduplicate_constraints")

    @staticmethod
    def _dedup_lists_in_dict(d: dict) -> None:
        """递归去重字典中的列表值。"""
        for key, value in d.items():
            if isinstance(value, list):
                seen = []
                unique = []
                for item in value:
                    if item not in seen:
                        seen.append(item)
                        unique.append(item)
                d[key] = unique
            elif isinstance(value, dict):
                DXBOptimizer._dedup_lists_in_dict(value)

    # ── Optimization Pass 4: Collapse linear chains ───────────────

    def _collapse_linear_chains(
        self, dxb: DXB, report: OptimizationReport
    ) -> None:
        """折叠线性依赖链。

        如果 A → B → C，且 B 没有其他依赖者，且 A 和 B 同类型，
        则合并 A+B 为一个步骤。
        """
        if len(dxb.steps) < 2:
            return

        # Build incoming edge count
        incoming: dict[str, int] = {}
        for step in dxb.steps:
            incoming.setdefault(step.id, 0)
            for dep in step.dependencies:
                incoming[dep] = incoming.get(dep, 0) + 1

        # Find linear chain candidates: steps with exactly 1 outgoing and 1 incoming
        step_map = {s.id: s for s in dxb.steps}
        merged: set[str] = set()

        for step in list(dxb.steps):
            if step.id in merged:
                continue
            # Find sole successor
            successors = [s for s in dxb.steps if step.id in s.dependencies]
            if len(successors) != 1:
                continue
            successor = successors[0]
            if successor.id in merged:
                continue
            # Check successor has only this one predecessor (depends only on current step)
            if len(successor.dependencies) != 1:
                continue
            # Same type?
            if step.step_type != successor.step_type:
                continue

            # Merge: successor absorbs step
            new_inputs = dict(step.inputs)
            new_inputs.update(successor.inputs)
            new_pre = list(dict.fromkeys(step.preconditions + successor.preconditions))
            new_post = list(dict.fromkeys(step.postconditions + successor.postconditions))
            # Merge dependencies: union minus self-reference
            new_deps = list(dict.fromkeys(
                step.dependencies + [d for d in successor.dependencies if d != step.id]
            ))

            merged.add(step.id)
            merged.add(successor.id)
            merged_id = f"{step.id}+{successor.id}"

            dxb.steps.append(CapabilityStep(
                id=merged_id,
                step_type=successor.step_type,
                capability_ref=f"{step.capability_ref}+{successor.capability_ref}",
                inputs=new_inputs,
                dependencies=new_deps,
                risk=max(step.risk, successor.risk),
                preconditions=new_pre,
                postconditions=new_post,
                expected_output=dict(successor.expected_output),
            ))

            # Update successors of successor
            for s in dxb.steps:
                if successor.id in s.dependencies:
                    new_deps_s = [merged_id if d == successor.id else d for d in s.dependencies]
                    idx = dxb.steps.index(s)
                    dxb.steps[idx] = CapabilityStep(
                        id=s.id,
                        step_type=s.step_type,
                        capability_ref=s.capability_ref,
                        inputs=dict(s.inputs),
                        dependencies=new_deps_s,
                        risk=s.risk,
                        preconditions=list(s.preconditions),
                        postconditions=list(s.postconditions),
                        expected_output=dict(s.expected_output),
                    )

            report.merged_steps.append({
                "result": merged_id,
                "absorbed": step.id,
                "into": successor.id,
            })

        if merged:
            dxb.steps = [s for s in dxb.steps if s.id not in merged]
            dxb._build_dag()
            report.optimizations_applied.append("collapse_linear_chains")
