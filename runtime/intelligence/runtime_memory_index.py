"""Runtime Memory Index — 执行轨迹指纹索引

将执行轨迹转换为可查询的记忆模板。
纯观察模块：只读 EventStore，不修改 runtime 状态。
"""

from __future__ import annotations

import hashlib

from runtime.intelligence.types import RuntimeMemoryTemplate, MemoryQueryResult


class RuntimeMemoryIndex:
    """运行时记忆索引 — 按指纹索引执行轨迹。

    指纹基于事件序列的 stage + event_type 计算（不含 payload 内容）。
    支持精确匹配和部分匹配（阶段序列 >= 50% 重叠）查询。
    """

    def __init__(self):
        self._templates: dict[str, list[RuntimeMemoryTemplate]] = {}

    # ── Index ───────────────────────────────────────────────────────────

    def index_trace(self, trace_id: str, event_store) -> RuntimeMemoryTemplate:
        """索引一次执行轨迹到记忆。

        从 EventStore 读取事件序列，计算 SHA256 指纹，
        创建 RuntimeMemoryTemplate 并存入索引。
        """
        events = event_store.read_by_trace(trace_id)
        fingerprint = self._compute_fingerprint(events)

        outcome = events[-1].event_type if events else "unknown"

        duration_ms = 0.0
        if len(events) >= 2:
            duration_ms = (events[-1].timestamp - events[0].timestamp) * 1000

        # Extract strategy and mode from events
        strategy = ""
        mode = ""
        for e in events:
            if not strategy and e.payload.get("strategy"):
                strategy = e.payload["strategy"]
            if not mode and e.payload.get("mode"):
                mode = e.payload["mode"]
        # Fallback: use runtime_mode when no payload mode was found
        if not mode and events:
            mode = events[0].runtime_mode

        stage_sequence = tuple(e.stage for e in events)

        template = RuntimeMemoryTemplate(
            fingerprint=fingerprint,
            trace_id=trace_id,
            outcome=outcome,
            duration_ms=duration_ms,
            strategy=strategy,
            mode=mode,
            stage_sequence=stage_sequence,
        )

        self._templates.setdefault(fingerprint, []).append(template)
        return template

    # ── Query ───────────────────────────────────────────────────────────

    def query(self, fingerprint: str) -> MemoryQueryResult:
        """按指纹查询相似执行。

        exact_matches：同一指纹的记忆模板。
        partial_matches：阶段序列 >= 50% 重叠的其他记忆模板。
        """
        exact = list(self._templates.get(fingerprint, []))

        partial: list[RuntimeMemoryTemplate] = []
        if exact:
            base_sequence = exact[0].stage_sequence
            for fp, templates in self._templates.items():
                if fp == fingerprint:
                    continue
                for t in templates:
                    if self._partial_match(base_sequence, t.stage_sequence):
                        partial.append(t)

        total = sum(len(v) for v in self._templates.values())
        return MemoryQueryResult(
            exact_matches=exact,
            partial_matches=partial,
            total_indexed=total,
        )

    # ── Fingerprint ─────────────────────────────────────────────────────

    def _compute_fingerprint(self, events) -> str:
        """从事件序列计算 SHA256 指纹。

        指纹 = hash(stage1 + type1 + stage2 + type2 + ... + outcome)
        只使用 stage + event_type，不使用 payload 内容。

        outcome = 最后一个事件的 event_type。
        """
        parts = [e.stage + e.event_type for e in events]
        outcome = events[-1].event_type if events else ""
        full_string = "".join(parts) + outcome
        return hashlib.sha256(full_string.encode()).hexdigest()

    @staticmethod
    def _partial_match(seq_a: tuple[str, ...], seq_b: tuple[str, ...]) -> bool:
        """检查两个阶段序列是否 >= 50% 重叠。"""
        if not seq_a or not seq_b:
            return False
        shorter = set(seq_a) if len(seq_a) <= len(seq_b) else set(seq_b)
        longer = set(seq_b) if len(seq_a) <= len(seq_b) else set(seq_a)
        overlap = len(shorter & longer)
        return overlap / len(shorter) >= 0.5

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def total_indexed(self) -> int:
        """已索引的记忆模板总数。"""
        return sum(len(v) for v in self._templates.values())

    def clear(self) -> None:
        """清空所有索引。"""
        self._templates.clear()
