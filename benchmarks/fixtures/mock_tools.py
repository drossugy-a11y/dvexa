"""Mock tool stubs for deterministic benchmark testing."""

from __future__ import annotations


class MockCodeExecutor:
    """Deterministic code executor stub for benchmark tests.

    Raises RuntimeError when code input contains the word "fail".
    """

    def __init__(self) -> None:
        self.call_count: int = 0

    def call(self, code: str) -> dict:
        """Execute mock code or raise on failure trigger."""
        self.call_count += 1
        if "fail" in code:
            raise RuntimeError("mock failure")
        return {"content": "mock execution result", "status": "ok"}


class MockHttpTool:
    """Deterministic HTTP tool stub for benchmark tests."""

    def __init__(self) -> None:
        self.call_count: int = 0

    def get(self, url: str) -> dict:
        self.call_count += 1
        return {"status": 200, "body": f"mock response from {url}"}
