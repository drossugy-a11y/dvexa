"""Runtime Persona Types — DVexa 运行时身份类型"""
from __future__ import annotations
from dataclasses import dataclass


class PersonaProfile(str):
    """Persona 配置文件标识。"""
    LIGHTWEIGHT = "lightweight"   # 简单聊天
    STANDARD = "standard"         # 标准任务
    GOVERNANCE = "governance"     # 治理/系统操作
    CODING = "coding"             # 代码/工程任务


@dataclass(frozen=True)
class RuntimePersona:
    """运行时身份声明 — 不可变，task-scoped。"""
    profile: str
    identity: str
    directives: tuple[str, ...]

    def to_system_prompt(self) -> str:
        parts = [self.identity]
        parts.extend(self.directives)
        return "\n\n".join(parts)
