"""DVX Capability Compiler v2.0 — 能力编译系统

将 EventStore 中的事件流编译为 DXB (DVX Execution Blueprint)。
纯只读分析层，不修改任何现有系统模块。
"""

from compiler_v2.dvx_compiler import DVXCompiler
from compiler_v2.capability_ir import (
    CapabilityIR,
    CapabilityNode,
    CapabilitySignal,
    DXB,
    CapabilityStep,
)
from compiler_v2.dxb_builder import DXBBuilder
from compiler_v2.policy_injector import PolicyInjector
from compiler_v2.openclaw_adapter import OpenClawMemoryAdapter

try:
    from compiler_v2.optimizer import DXBOptimizer
except ImportError:
    DXBOptimizer = None  # type: ignore[assignment]

try:
    from compiler_v2.validator import DXBValidator
except ImportError:
    DXBValidator = None  # type: ignore[assignment]

__all__ = [
    "DVXCompiler",
    "CapabilityIR",
    "CapabilityNode",
    "CapabilitySignal",
    "DXB",
    "CapabilityStep",
    "DXBBuilder",
    "DXBOptimizer",
    "DXBValidator",
    "PolicyInjector",
    "OpenClawMemoryAdapter",
]
