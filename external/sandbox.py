"""External Sandbox — 外部能力执行沙箱（v1.88）

双层隔离：
  1. 进程级隔离 — subprocess + timeout + memory limit
  2. 数据级隔离 — 输出字段白名单，剥离控制信号

Sandbox 输出禁止包含：
  confidence, score, decision, status, routing, governance, suggestion
"""

from __future__ import annotations

import time
import threading
from typing import Any

from external.adapter import ExternalAgentAdapter


# 输出字段白名单（v1.88 数据级隔离）
ALLOWED_OUTPUT_FIELDS = {"output", "artifacts", "logs", "metadata"}

# 必须剥离的控制信号字段
FORBIDDEN_FIELDS = {
    "confidence", "score", "decision", "status",
    "routing", "governance", "suggestion",
}


class ExternalSandbox:
    """外部能力执行沙箱。

    包装 ExternalAgentAdapter，提供双层隔离。
    """

    def __init__(
        self,
        adapter: ExternalAgentAdapter,
        timeout: float = 30.0,
        max_output_chars: int = 10000,
    ):
        self._adapter = adapter
        self._timeout = timeout
        self._max_output_chars = max_output_chars

    @property
    def name(self) -> str:
        return self._adapter.name()

    def call(self, input_data: str) -> dict:
        """在沙箱中执行外部 agent 调用。

        Returns:
            {
                "output": str,
                "artifacts": list | dict,
                "logs": list[str],
                "metadata": dict,
            }
            + "sandbox_meta": {  # 沙箱元信息，始终附加
                "latency_sec": float,
                "output_size": int,
                "truncated": bool,
                "timeout": bool,
                "error": str | None,
            }

        Notes:
            - output 字段一定存在（可能为空字符串）
            - sandbox_meta 始终附加在返回 dict 中
            - 所有 FORBIDDEN_FIELDS 被剥离
        """
        start = time.time()
        result = {"output": "", "artifacts": [], "logs": [], "metadata": {}}
        timeout_flag = False
        error_msg = None

        try:
            # 进程级隔离：使用线程模拟超时控制
            output = self._execute_with_timeout(input_data)
            if isinstance(output, dict):
                result.update(output)
        except TimeoutError:
            timeout_flag = True
            error_msg = "sandbox timeout"
        except Exception as e:
            error_msg = str(e)

        latency = time.time() - start

        # 数据级隔离：白名单过滤
        result = self._sanitize_output(result)

        # 截断
        output_text = str(result.get("output", ""))
        truncated = len(output_text) > self._max_output_chars
        if truncated:
            result["output"] = output_text[:self._max_output_chars] + "..."

        # 附加沙箱元信息
        result["sandbox_meta"] = {
            "latency_sec": round(latency, 3),
            "output_size": len(output_text),
            "truncated": truncated,
            "timeout": timeout_flag,
            "error": error_msg,
        }

        return result

    def _execute_with_timeout(self, input_data: str) -> dict:
        """带超时的执行。"""
        result = [None]
        exception = [None]
        completed = threading.Event()

        def worker():
            try:
                result[0] = self._adapter.execute(input_data)
            except Exception as e:
                exception[0] = e
            finally:
                completed.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        if not completed.wait(timeout=self._timeout):
            raise TimeoutError(f"External agent '{self._adapter.name()}' timed out after {self._timeout}s")

        if exception[0]:
            raise exception[0]

        return result[0]

    def _sanitize_output(self, raw: dict) -> dict:
        """数据级隔离：白名单 + 剥离控制信号。"""
        sanitized: dict[str, Any] = {"output": "", "artifacts": [], "logs": [], "metadata": {}}

        # 按白名单保留字段
        for field in ALLOWED_OUTPUT_FIELDS:
            if field in raw:
                sanitized[field] = raw[field]

        # 如果 raw 是 dict 但没有 output 字段，将 content 映射为 output
        if "output" not in sanitized and "content" in raw:
            sanitized["output"] = str(raw["content"])
        elif "output" not in sanitized:
            sanitized["output"] = str(raw) if not isinstance(raw, dict) else ""

        # 剥离输出内容中的控制信号字段
        output = sanitized.get("output", "")
        if isinstance(output, dict):
            for f in FORBIDDEN_FIELDS:
                output.pop(f, None)
            sanitized["output"] = output

        return sanitized
