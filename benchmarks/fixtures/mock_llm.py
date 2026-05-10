"""Mock LLM tools for deterministic benchmark testing."""

from __future__ import annotations


class MockLLMTool:
    """Deterministic LLM stub for benchmark tests.

    Returns pre-configured responses without any real LLM call.
    Tracks invocation count for verification.
    """

    def __init__(self, responses: dict[str, dict] | None = None):
        self.responses: dict[str, dict] = responses or {}
        self.call_count: int = 0

    def call(self, prompt: str, system_prompt: str | None = None) -> dict:
        """Return a deterministic mock response."""
        self.call_count += 1
        key = prompt.strip()
        if key in self.responses:
            return self.responses[key]
        return {"content": "mock response", "role": "assistant"}
