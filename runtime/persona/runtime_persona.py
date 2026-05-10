"""Runtime Persona Kernel v2 — 系统级身份注入内核

职责：
- 在 LLM 调用边界强制注入 runtime identity
- 单任务生命周期内身份稳定
- 不被用户输入、历史对话、stream 输出覆盖
- thread-safe
"""

from __future__ import annotations

import threading
from typing import Any

from runtime.persona.persona_types import RuntimePersona, PersonaProfile
from runtime.persona.directive_profiles import PROFILES, resolve_profile


class RuntimePersonaKernel:
    """运行时身份内核 — task-scoped persona 管理。

    用法:
        kernel = RuntimePersonaKernel()
        kernel.set_for_task(directive)   # 任务开始时设置
        prompt = kernel.get_system_prompt()  # 注入到 LLM call
        kernel.reset()                     # 任务结束后重置
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._active_profile: str = PersonaProfile.LIGHTWEIGHT
        self._persona: RuntimePersona = PROFILES[PersonaProfile.LIGHTWEIGHT]

    def set_for_task(self, directive: Any) -> None:
        """根据 directive 设置当前任务的 persona。

        在 task 生命周期内 immutable — 不会被后续输入改变。
        """
        mode = getattr(directive, 'mode', 'chat') if directive else 'chat'
        with self._lock:
            profile = resolve_profile(mode, 0.0)
            self._active_profile = profile
            self._persona = PROFILES.get(profile, PROFILES[PersonaProfile.LIGHTWEIGHT])

    def get_system_prompt(self) -> str:
        """获取当前 persona 的完整 system prompt。

        这是注入到 LLM 调用的最终身份声明。
        """
        return self._persona.to_system_prompt()

    @property
    def active_profile(self) -> str:
        return self._active_profile

    def reset(self) -> None:
        """任务结束后重置为 lightweight，准备下一任务。"""
        with self._lock:
            self._active_profile = PersonaProfile.LIGHTWEIGHT
            self._persona = PROFILES[PersonaProfile.LIGHTWEIGHT]

    def is_lightweight(self) -> bool:
        return self._active_profile == PersonaProfile.LIGHTWEIGHT
