"""OpenClaw Memory Adapter — #003 能力源适配器

仅作为静态能力信号提供者，不执行运行时逻辑。
从 OpenClaw Memory System 的输出格式中提取能力信号。
"""

from __future__ import annotations

from compiler_v2.capability_ir import CapabilitySignal


class OpenClawMemoryAdapter:
    """OpenClaw Memory System 的能力适配器。

    职责：
      - 解析 memory chunks 输出
      - 提取 MMR 检索结果中的能力引用
      - 提取 hybrid search 结果中的模式
      - 仅产出 CapabilitySignal，不做运行时操作
    """

    # 已知能力关键词映射（从 OpenClaw memory 系统提取）
    MEMORY_CAPABILITY_PATTERNS: dict[str, list[str]] = {
        "hybrid_search": ["hybrid", "vector", "keyword", "fts5", "sqlite"],
        "mmr_ranking": ["mmr", "maximal marginal relevance", "diversity", "relevance"],
        "chunking": ["chunk", "token", "overlap", "split"],
        "embeddings": ["embedding", "vector", "dimension"],
        "temporal_decay": ["temporal", "decay", "recency", "time"],
        "semantic_search": ["semantic", "keyword extraction", "query expansion"],
        "memory_index": ["index", "fts5", "full-text", "inverted"],
        "batch_operations": ["batch", "bulk", "parallel"],
    }

    def extract_capabilities(self, memory_outputs: list[dict] | None = None) -> list[CapabilitySignal]:
        """从 memory 输出中提取能力信号。

        Args:
            memory_outputs: 可选，memory 系统的输出结果列表。
                           如果为 None，返回空信号列表。

        Returns:
            CapabilitySignal 列表
        """
        if not memory_outputs:
            return self._static_signals()

        signals: list[CapabilitySignal] = []
        for i, output in enumerate(memory_outputs):
            try:
                signals.extend(self._parse_output(output))
            except Exception:
                continue  # 单个元素解析失败不影响整体
        return signals

    def _static_signals(self) -> list[CapabilitySignal]:
        """返回 OpenClaw Memory 系统的静态能力信号。

        这些是基于 OpenClaw memory/ 模块架构分析确定的已知能力。
        """
        return [
            CapabilitySignal(
                source="openclaw",
                signal_type="memory_capability",
                payload={
                    "capability": "hybrid_search",
                    "description": "SQLite FTS5 + 向量混合搜索",
                    "weight": 0.7,
                },
                confidence=0.95,
            ),
            CapabilitySignal(
                source="openclaw",
                signal_type="memory_capability",
                payload={
                    "capability": "mmr_ranking",
                    "description": "最大边际相关性重排序",
                    "weight": 0.5,
                },
                confidence=0.90,
            ),
            CapabilitySignal(
                source="openclaw",
                signal_type="memory_capability",
                payload={
                    "capability": "chunking",
                    "description": "Token 分块 + 重叠",
                    "weight": 0.4,
                },
                confidence=0.85,
            ),
            CapabilitySignal(
                source="openclaw",
                signal_type="memory_capability",
                payload={
                    "capability": "semantic_search",
                    "description": "关键词提取 + 时间衰减 + 查询扩展",
                    "weight": 0.6,
                },
                confidence=0.85,
            ),
            CapabilitySignal(
                source="openclaw",
                signal_type="memory_capability",
                payload={
                    "capability": "embeddings",
                    "description": "远程嵌入提供者 + 批量操作",
                    "weight": 0.3,
                },
                confidence=0.80,
            ),
        ]

    def _parse_output(self, output: Any) -> list[CapabilitySignal]:
        """解析单个 memory 输出为能力信号。

        防御性解析: 非 dict 输入安全返回空列表。
        """
        signals: list[CapabilitySignal] = []
        if not isinstance(output, dict):
            return signals
        text = str(output.get("text", "")) + " " + str(output.get("snippet", ""))
        source = output.get("source", "memory")
        path = output.get("path", "")

        for cap_name, keywords in self.MEMORY_CAPABILITY_PATTERNS.items():
            score = sum(1.0 for kw in keywords if kw.lower() in text.lower())
            if score > 0:
                confidence = min(score / len(keywords), 1.0)
                signals.append(CapabilitySignal(
                    source="openclaw",
                    signal_type="memory_capability",
                    payload={
                        "capability": cap_name,
                        "source_path": path,
                        "source_type": source,
                        "match_score": score,
                    },
                    confidence=round(confidence, 2),
                ))
        return signals
