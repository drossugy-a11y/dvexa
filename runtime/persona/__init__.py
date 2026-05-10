"""Runtime Persona Kernel — 系统级身份注入层"""

from runtime.persona.runtime_persona import RuntimePersonaKernel
from runtime.persona.persona_types import RuntimePersona, PersonaProfile
from runtime.persona.directive_profiles import resolve_profile, PROFILES

__all__ = [
    "RuntimePersonaKernel",
    "RuntimePersona",
    "PersonaProfile",
    "resolve_profile",
    "PROFILES",
]
