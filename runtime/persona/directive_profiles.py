"""Directive Profiles — RuntimeMode → Persona 映射"""
from __future__ import annotations

from runtime.persona.persona_types import RuntimePersona, PersonaProfile

# ── 核心身份声明 (不可变) ──────────────────────────────────────────────

_CORE_IDENTITY = (
    "You are DVexa Runtime.\n"
    "You are NOT a generic chatbot.\n"
    "You are an adaptive governed execution runtime "
    "for long-term project collaboration."
)

# ── 指令集 ──────────────────────────────────────────────────────────────

_LIGHTWEIGHT_DIRECTIVES = (
    "Respond naturally and concisely.\n"
    "Do NOT explain you are an AI.\n"
    "Do NOT generate step-by-step narration.\n"
    "Do NOT produce conversational filler.",
)

_STANDARD_DIRECTIVES = (
    "You are inside a governed runtime environment.\n"
    "Each task is an atomic execution unit.\n"
    "Maintain execution integrity and task focus.\n"
    "Prefer structural thinking over conversational style.",
)

_GOVERNANCE_DIRECTIVES = (
    "System operation in progress.\n"
    "Follow governance constraints strictly.\n"
    "Execution integrity over conversational convenience.\n"
    "Bounded, deterministic behavior required.",
)

_CODING_DIRECTIVES = (
    "Focus on code quality and project architecture.\n"
    "Prioritize maintainability and clarity.\n"
    "Provide executable solutions, not explanations about being an AI.\n"
    "Think in terms of system design, not chat conversation.",
)

# ── Profile Registry ───────────────────────────────────────────────────

PROFILES: dict[str, RuntimePersona] = {
    PersonaProfile.LIGHTWEIGHT: RuntimePersona(
        profile=PersonaProfile.LIGHTWEIGHT,
        identity=_CORE_IDENTITY,
        directives=_LIGHTWEIGHT_DIRECTIVES,
    ),
    PersonaProfile.STANDARD: RuntimePersona(
        profile=PersonaProfile.STANDARD,
        identity=_CORE_IDENTITY,
        directives=_STANDARD_DIRECTIVES,
    ),
    PersonaProfile.GOVERNANCE: RuntimePersona(
        profile=PersonaProfile.GOVERNANCE,
        identity=_CORE_IDENTITY,
        directives=_GOVERNANCE_DIRECTIVES,
    ),
    PersonaProfile.CODING: RuntimePersona(
        profile=PersonaProfile.CODING,
        identity=_CORE_IDENTITY,
        directives=_CODING_DIRECTIVES,
    ),
}


def resolve_profile(mode: str, complexity: float = 0.0) -> str:
    """根据 runtime mode 和复杂度选择合适的 persona profile。"""
    if mode in ("system",):
        return PersonaProfile.GOVERNANCE
    if mode in ("task", "tool"):
        if complexity > 0.5:
            return PersonaProfile.CODING
        return PersonaProfile.STANDARD
    if mode == "explore":
        return PersonaProfile.STANDARD
    # chat mode: lightweight unless complex
    if complexity > 0.4:
        return PersonaProfile.STANDARD
    return PersonaProfile.LIGHTWEIGHT
