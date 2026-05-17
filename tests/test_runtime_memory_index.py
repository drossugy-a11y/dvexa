"""Tests for RuntimeMemoryIndex.

Verifies fingerprint computation, trace indexing, query matching,
and index lifecycle (count, clear).
"""

from __future__ import annotations

import hashlib

import pytest

from runtime.event import Event
from runtime.intelligence.runtime_memory_index import RuntimeMemoryIndex
from runtime.intelligence.types import RuntimeMemoryTemplate, MemoryQueryResult


class TestRuntimeMemoryIndex:
    """RuntimeMemoryIndex 单元测试。"""

    # ── Fingerprint Tests ───────────────────────────────────────────────

    def test_compute_fingerprint_consistent(self):
        """同一事件序列产生一致的指纹。"""
        events = [
            Event(trace_id="t1", stage="load", event_type="info", payload={}),
            Event(trace_id="t1", stage="semantic", event_type="decision", payload={}),
        ]
        idx = RuntimeMemoryIndex()
        fp1 = idx._compute_fingerprint(events)
        fp2 = idx._compute_fingerprint(events)
        assert fp1 == fp2

    def test_different_events_produce_different_fingerprints(self):
        """不同事件序列产生不同指纹。"""
        idx = RuntimeMemoryIndex()
        events_a = [
            Event(trace_id="t1", stage="load", event_type="info", payload={}),
            Event(trace_id="t1", stage="govern", event_type="decision", payload={}),
        ]
        events_b = [
            Event(trace_id="t2", stage="load", event_type="error", payload={}),
            Event(trace_id="t2", stage="govern", event_type="decision", payload={}),
        ]
        assert idx._compute_fingerprint(events_a) != idx._compute_fingerprint(events_b)

    def test_fingerprint_uses_stage_and_type_only(self):
        """指纹只使用 stage + event_type，不用 payload 内容。"""
        idx = RuntimeMemoryIndex()
        events_a = [
            Event(trace_id="t1", stage="load", event_type="info", payload={"key": "a"}),
        ]
        events_b = [
            Event(trace_id="t2", stage="load", event_type="info", payload={"key": "b"}),
        ]
        assert idx._compute_fingerprint(events_a) == idx._compute_fingerprint(events_b)

    def test_fingerprint_is_sha256_length(self):
        """指纹是 SHA256 十六进制字符串（64 字符）。"""
        events = [
            Event(trace_id="t1", stage="load", event_type="info", payload={}),
        ]
        idx = RuntimeMemoryIndex()
        fp = idx._compute_fingerprint(events)
        assert len(fp) == 64
        # Verify it's valid hex
        int(fp, 16)

    # ── Index Tests ─────────────────────────────────────────────────────

    def test_index_trace_stores_template(self):
        """index_trace 创建并存储 RuntimeMemoryTemplate。"""
        store = _MockEventStore()
        idx = RuntimeMemoryIndex()
        template = idx.index_trace("t1", store)

        assert isinstance(template, RuntimeMemoryTemplate)
        assert template.trace_id == "t1"
        assert template.fingerprint
        assert idx.total_indexed == 1

    def test_index_trace_extracts_stage_sequence(self):
        """index_trace 从事件提取阶段序列。"""
        store = _MockEventStore()
        idx = RuntimeMemoryIndex()
        template = idx.index_trace("t1", store)

        assert template.stage_sequence == ("load", "semantic", "govern")

    def test_index_trace_computes_outcome(self):
        """index_trace 从最后一个事件的 event_type 推导 outcome。"""
        store = _MockEventStore()
        idx = RuntimeMemoryIndex()

        template_ok = idx.index_trace("t1", store)
        assert template_ok.outcome == "decision"

        template_err = idx.index_trace("t2", store)
        assert template_err.outcome == "error"

    def test_index_trace_extracts_strategy_and_mode(self):
        """index_trace 从事件 payload 提取 strategy 和 mode。"""
        store = _MockEventStore()
        idx = RuntimeMemoryIndex()
        template = idx.index_trace("t1", store)

        assert template.strategy == "default"
        assert template.mode == "auto"

    # ── Query Tests ─────────────────────────────────────────────────────

    def test_index_and_query_exact_match(self):
        """query() 返回精确匹配。"""
        store = _MockEventStore()
        idx = RuntimeMemoryIndex()
        idx.index_trace("t1", store)

        # Get the stored fingerprint
        fingerprint = next(iter(idx._templates))

        result = idx.query(fingerprint)
        assert isinstance(result, MemoryQueryResult)
        assert len(result.exact_matches) == 1
        assert result.exact_matches[0].trace_id == "t1"

    def test_query_no_match_returns_empty(self):
        """query() 对未知指纹返回空结果。"""
        idx = RuntimeMemoryIndex()
        result = idx.query("nonexistent_fingerprint")
        assert len(result.exact_matches) == 0
        assert len(result.partial_matches) == 0

    def test_query_partial_match(self):
        """query() 返回阶段序列 >= 50% 重叠的部分匹配。"""
        idx = RuntimeMemoryIndex()
        store = _MockEventStore()
        idx.index_trace("t1", store)  # stages: load, semantic, govern
        idx.index_trace("t3", store)  # stages: load, govern, schedule

        fingerprint = next(iter(idx._templates))
        result = idx.query(fingerprint)

        # t3 shares "load" and "govern" with t1's "load, semantic, govern"
        # 2 out of 3 stages overlap = 66.6% >= 50% => partial match
        assert len(result.partial_matches) >= 1

    # ── Index Lifecycle Tests ───────────────────────────────────────────

    def test_total_indexed_count(self):
        """total_indexed 反映已索引模板数。"""
        store = _MockEventStore()
        idx = RuntimeMemoryIndex()
        assert idx.total_indexed == 0

        idx.index_trace("t1", store)
        assert idx.total_indexed == 1

        idx.index_trace("t2", store)
        assert idx.total_indexed == 2

    def test_clear_resets_index(self):
        """clear() 清空所有索引。"""
        store = _MockEventStore()
        idx = RuntimeMemoryIndex()
        idx.index_trace("t1", store)
        idx.index_trace("t2", store)
        assert idx.total_indexed == 2

        idx.clear()
        assert idx.total_indexed == 0
        assert idx._templates == {}


# ── Mock Helpers ────────────────────────────────────────────────────────


class _MockEventStore:
    """模拟 EventStore，返回预定义事件序列。"""

    def read_by_trace(self, trace_id: str) -> list[Event]:
        data: dict[str, list[Event]] = {
            "t1": [
                Event(
                    trace_id="t1", stage="load", event_type="info",
                    payload={"strategy": "default"},
                    runtime_mode="task",
                ),
                Event(
                    trace_id="t1", stage="semantic", event_type="decision",
                    payload={},
                    runtime_mode="task",
                ),
                Event(
                    trace_id="t1", stage="govern", event_type="decision",
                    payload={"mode": "auto"},
                    runtime_mode="task",
                ),
            ],
            "t2": [
                Event(trace_id="t2", stage="load", event_type="info", payload={}),
                Event(trace_id="t2", stage="validate", event_type="error", payload={}),
            ],
            "t3": [
                Event(trace_id="t3", stage="load", event_type="info", payload={}),
                Event(trace_id="t3", stage="govern", event_type="decision", payload={}),
                Event(trace_id="t3", stage="schedule", event_type="info", payload={}),
            ],
        }
        return list(data.get(trace_id, []))
