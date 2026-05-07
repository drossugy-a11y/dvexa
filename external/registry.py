"""External Registry — 外部能力注册表（v1.88）

只允许白名单 adapter 注册。
禁止：eval() / exec() / dynamic import string。

所有外部 adapter 必须显式注册。
"""

from __future__ import annotations

from external.adapter import ExternalAgentAdapter


# 白名单 Adapter 类型（运行时检查）
ALLOWED_ADAPTER_TYPES = (ExternalAgentAdapter,)


class ExternalRegistry:
    """外部能力注册表。

    安全约束：
      - 只接受 ExternalAgentAdapter Protocol 实现
      - 禁止 eval/exec/dynamic import
      - adapter 必须显式注册
    """

    def __init__(self):
        self._adapters: dict[str, ExternalAgentAdapter] = {}

    def register(self, name: str, adapter: ExternalAgentAdapter, metadata: dict | None = None):
        """注册外部 adapter。

        Args:
            name: 唯一标识名
            adapter: 实现 ExternalAgentAdapter Protocol 的实例
            metadata: 可选的元信息

        Raises:
            TypeError: adapter 未实现 ExternalAgentAdapter Protocol
        """
        if not isinstance(adapter, ALLOWED_ADAPTER_TYPES):
            if not hasattr(adapter, "name") or not callable(getattr(adapter, "execute", None)):
                raise TypeError(
                    f"adapter '{name}' 未实现 ExternalAgentAdapter Protocol"
                )
        self._adapters[name] = adapter

    def get(self, name: str) -> ExternalAgentAdapter | None:
        """按名称获取 adapter。"""
        return self._adapters.get(name)

    def list_all(self) -> dict[str, ExternalAgentAdapter]:
        """返回所有注册的 adapter。"""
        return dict(self._adapters)

    @property
    def count(self) -> int:
        return len(self._adapters)

    def unregister(self, name: str) -> bool:
        """移除已注册的 adapter。"""
        if name in self._adapters:
            del self._adapters[name]
            return True
        return False
