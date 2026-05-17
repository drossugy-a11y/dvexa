"""Strategy Evolution Engine — 基于规则的演化建议生成器

执行分析报告 + 故障模式 → 演化建议。
全部 deterministic（无 LLM），每类规则独立触发。
"""

from __future__ import annotations

import hashlib
from typing import Any

from governance.evolution.types import EvolutionSuggestion
from runtime.intelligence.types import ExecutionAnalysisReport, FailurePattern


class StrategyEvolutionEngine:
    """策略演化引擎 — 基于确定性规则从执行数据生成演化建议。

    规则清单（按优先级排序）:
      1. 策略倾斜: strategy_distribution 某策略 > 80%
      2. 治理阻塞: failure_patterns 含 governance_block
      3. 重试风暴: retry_rate > 0.5
      4. 治理率高: governance_block_rate > 0.3
      5. 错误多样: error_types 类型数 > 3
    """

    # ── 规则阈值 ────────────────────────────────────────────────────────
    _STRATEGY_DOMINANCE_THRESHOLD = 0.80
    _RETRY_RATE_THRESHOLD = 0.50
    _GOVERNANCE_BLOCK_RATE_THRESHOLD = 0.30
    _ERROR_TYPE_COUNT_THRESHOLD = 3

    # ── 建议 target ─────────────────────────────────────────────────────
    _TARGET_STRATEGY = "strategy"
    _TARGET_THRESHOLD = "threshold"
    _TARGET_CAPABILITY = "capability"
    _TARGET_ROUTE = "route"

    def suggest(
        self,
        report: ExecutionAnalysisReport,
        failure_patterns: list[FailurePattern],
    ) -> list[EvolutionSuggestion]:
        """根据执行报告与故障模式生成演化建议。

        Args:
            report: 执行分析报告（不可变聚合数据）
            failure_patterns: 故障模式列表

        Returns:
            演化建议列表（空列表表示无需演化）
        """
        suggestions: list[EvolutionSuggestion] = []

        # Rule 1: 策略倾斜 — 某策略占比 > 80%
        if rule := self._rule_strategy_dominance(report):
            suggestions.append(rule)

        # Rule 2: 治理阻塞 — 存在 governance_block 故障
        if rule := self._rule_governance_block(report, failure_patterns):
            suggestions.append(rule)

        # Rule 3: 重试风暴 — retry_rate > 0.5
        if rule := self._rule_retry_storm(report):
            suggestions.append(rule)

        # Rule 4: 治理率高 — governance_block_rate > 0.3
        if rule := self._rule_high_governance_rate(report):
            suggestions.append(rule)

        # Rule 5: 错误多样 — error_types 类型数 > 3
        if rule := self._rule_error_diversity(report):
            suggestions.append(rule)

        return suggestions

    # ═══════════════════════════════════════════════════════════════════
    # 各规则实现
    # ═══════════════════════════════════════════════════════════════════

    def _rule_strategy_dominance(
        self, report: ExecutionAnalysisReport,
    ) -> EvolutionSuggestion | None:
        """Rule 1: 策略倾斜检测。

        如果 strategy_distribution 中某一个策略的使用占比超过 80%，
        建议 rebalance —— 说明策略空间未被充分利用。
        """
        total = sum(report.strategy_distribution.values())
        if total <= 0:
            return None

        for strategy, count in report.strategy_distribution.items():
            ratio = count / total
            if ratio > self._STRATEGY_DOMINANCE_THRESHOLD:
                confidence = min(ratio, 1.0)
                return EvolutionSuggestion(
                    target=self._TARGET_STRATEGY,
                    proposed_change=(
                        f"Rebalance strategies: '{strategy}' dominates "
                        f"at {ratio:.0%} usage. Consider increasing "
                        f"allocation to other strategies."
                    ),
                    confidence=round(confidence, 4),
                    evidence=(),
                    description=(
                        f"Strategy dominance detected: {strategy} = "
                        f"{ratio:.0%} (threshold > 80%)"
                    ),
                )
        return None

    def _rule_governance_block(
        self, report: ExecutionAnalysisReport,
        failure_patterns: list[FailurePattern],
    ) -> EvolutionSuggestion | None:
        """Rule 2: 治理阻塞检测。

        如果存在 pattern_type == 'governance_block' 的故障模式，
        建议调整相关阈值。
        """
        block_patterns = [
            fp for fp in failure_patterns
            if fp.pattern_type == "governance_block"
        ]
        if not block_patterns:
            return None

        # 收集所有相关 trace_id 作为证据
        evidence: set[str] = set()
        max_severity = 0.0
        for fp in block_patterns:
            evidence.update(fp.trace_ids)
            max_severity = max(max_severity, fp.severity)

        return EvolutionSuggestion(
            target=self._TARGET_THRESHOLD,
            proposed_change=(
                f"Review governance thresholds: {len(block_patterns)} "
                f"governance block pattern(s) detected. Consider "
                f"relaxing overly restrictive policies or increasing "
                f"timeout limits."
            ),
            confidence=round(min(max_severity + 0.2, 1.0), 4),
            evidence=tuple(sorted(evidence)),
            description=(
                f"Governance block: {len(block_patterns)} pattern(s) "
                f"with max severity {max_severity:.2f}"
            ),
        )

    def _rule_retry_storm(
        self, report: ExecutionAnalysisReport,
    ) -> EvolutionSuggestion | None:
        """Rule 3: 重试风暴检测。

        retry_rate > 0.5 说明工具/操作频繁超时或失败，
        建议增加 tool timeout。
        """
        if report.retry_rate <= self._RETRY_RATE_THRESHOLD:
            return None

        # 重试率越高，置信度越高（线性映射 0.5→0.5, 1.0→1.0）
        confidence = min(report.retry_rate, 1.0)

        return EvolutionSuggestion(
            target=self._TARGET_THRESHOLD,
            proposed_change=(
                f"Increase tool timeout values: retry rate is "
                f"{report.retry_rate:.0%} (threshold > 50%). Higher "
                f"timeouts or more generous retry budgets may reduce "
                f"retry pressure."
            ),
            confidence=round(confidence, 4),
            evidence=(),
            description=(
                f"Retry storm: rate = {report.retry_rate:.0%} "
                f"(threshold > 50%)"
            ),
        )

    def _rule_high_governance_rate(
        self, report: ExecutionAnalysisReport,
    ) -> EvolutionSuggestion | None:
        """Rule 4: 治理阻塞率高检测。

        governance_block_rate > 0.3 说明治理层过于严格，
        建议放松治理策略或阈值。
        """
        if report.governance_block_rate <= self._GOVERNANCE_BLOCK_RATE_THRESHOLD:
            return None

        confidence = min(report.governance_block_rate, 1.0)

        return EvolutionSuggestion(
            target=self._TARGET_THRESHOLD,
            proposed_change=(
                f"Relax governance policies: block rate is "
                f"{report.governance_block_rate:.0%} (threshold > 30%). "
                f"Consider adjusting policy thresholds or adding allow-"
                f"list entries for legitimate operations."
            ),
            confidence=round(confidence, 4),
            evidence=(),
            description=(
                f"High governance block rate: "
                f"{report.governance_block_rate:.0%} (threshold > 30%)"
            ),
        )

    def _rule_error_diversity(
        self, report: ExecutionAnalysisReport,
    ) -> EvolutionSuggestion | None:
        """Rule 5: 错误类型多样化检测。

        error_types 超过 3 种不同类型说明系统面临超出
        当前能力边界的任务，建议限制 capability 范围。
        """
        error_count = len(report.error_types)
        if error_count <= self._ERROR_TYPE_COUNT_THRESHOLD:
            return None

        # 置信度基于错误类型数量（类型越多置信度越高）
        confidence = min(error_count / 10.0, 1.0)

        return EvolutionSuggestion(
            target=self._TARGET_CAPABILITY,
            proposed_change=(
                f"Restrict capability scope: {error_count} distinct "
                f"error types detected (threshold > 3). The system may "
                f"be facing tasks beyond its current capability "
                f"boundaries. Consider narrowing the supported task "
                f"range or adding specialized handlers."
            ),
            confidence=round(confidence, 4),
            evidence=(),
            description=(
                f"Error diversity: {error_count} error types "
                f"(threshold > 3)"
            ),
        )
