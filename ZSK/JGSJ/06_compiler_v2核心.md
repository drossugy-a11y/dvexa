# DVX Compiler v2.0 — 编译系统核心实现

> **所属层次**: 编译层（Compiler Layer）— 纯只读，不参与运行时
> **前序**: v2.0 架构转型规范（ZT11）
> **状态**: ✅ COMPLETE — 8 文件 + 113 测试
> **日期**: 2026-05-07

---

## 一、架构定位

**Compiler v2.0 是 DVX 系统的"预编译大脑"——在编译阶段完成所有分析和规划，Kernel 降级为纯执行器。**

```
                         DVX v2.0 Full Architecture
                         ==========================

  ┌─────────────────────────────────────────────────────┐
  │                   COMPILE TIME                       │
  │                                                     │
  │  EventStore ──┐                                     │
  │  OpenClaw ────┼──→ DVXCompiler ──→ DXB              │
  │  Governance ──┘    (8 stages)       (执行蓝图)       │
  │                                                     │
  └──────────────────────┬──────────────────────────────┘
                         │ DXB (确定性，可重放)
                         ▼
  ┌─────────────────────────────────────────────────────┐
  │                   RUNTIME                            │
  │                                                     │
  │  Kernel ──→ DXB.steps[] ──→ Execute ──→ Result       │
  │  (纯执行器，按步骤执行，不做决策)                      │
  │                                                     │
  └─────────────────────────────────────────────────────┘
```

### 核心转型

| 维度 | v1.91 | v2.0 |
|------|-------|------|
| 决策者 | Runtime Engine | DVX Compiler |
| 执行表示 | Event 流 | DXB 执行蓝图 |
| Kernel 角色 | 决策 + 调度 + 执行 | 纯执行器（无决策） |
| Governance | Runtime 决策 | Compiler Plugin |
| EventStore | 控制流参与者 | 纯历史记录层 |

---

## 二、模块结构

```
compiler_v2/
├── __init__.py              # 模块导出（含 try/except 降级）
├── capability_ir.py         # IR + DXB 核心数据结构
│   ├── CapabilitySignal     # 能力信号（frozen）
│   ├── CapabilityNode       # 能力节点（frozen）
│   ├── CapabilityIR         # 中间表示
│   ├── CapabilityStep       # 执行步骤（frozen）
│   └── DXB                  # 执行蓝图（含拓扑排序）
├── policy_injector.py       # 治理约束注入
│   └── PolicyInjector       # SGL/ATS/Scheduler → constraints
├── openclaw_adapter.py      # 外部能力源适配
│   └── OpenClawMemoryAdapter # #003 Memory System 能力提取
├── dxb_builder.py           # IR → DXB 编译器
│   └── DXBBuilder           # 步骤构建 + 约束合并 + 信号标注
├── dvx_compiler.py          # 主编排器
│   ├── DVXCompiler          # 8 阶段流水线
│   ├── CompilationResult    # 编译结果
│   └── CompilationDiagnostic # 诊断信息
├── optimizer.py             # 结构优化器
│   ├── DXBOptimizer         # 4 个优化 Pass
│   └── OptimizationReport   # 优化报告
└── validator.py             # 安全验证器
    ├── DXBValidator         # 3 层验证（结构/治理/策略）
    └── ValidationReport     # 验证报告
```

---

## 三、8 阶段流水线详解

### Stage 1: ingest_eventstore
- 从 EventStore 加载事件列表
- 按 `trace_id` 过滤
- 无事件时产生 warning，返回空结果

### Stage 2: extract_capabilities
- 遍历事件，按 `stage` 提取信号：
  - `load` → context_load（上下文加载）
  - `semantic` → semantic_intent / threat_detected（意图/威胁）
  - `validate` → validation_phases（验证阶段）
  - `schedule` → scheduled_action（调度动作）
- 整合 OpenClaw #003 Memory 信号
- 提取的信号类型决定后续 node_type 映射

### Stage 3: merge_capability_space
- 去重规则：相同 `(signal_type, trace_id)` 保留最高 confidence
- 不同 trace_id 的信号保留

### Stage 4: build_capability_ir
- 从合并后的信号构建 CapabilityIR
- intent 从 semantic_intent 信号提取
- risk_signals 从 threat_detected 信号提取
- 每个 signal 映射为 CapabilityNode
- node_type 映射：semantic_intent→SKILL, threat_detected→GOVERNANCE_CHECK, memory_capability→MEMORY

### Stage 5: build_dxb
- DXBBuilder 将 CapabilityIR 编译为 DXB
- 步骤排序：GOVERNANCE_CHECK → SKILL → TOOL
- 注入 PolicyInjector 约束
- 标注 OpenClaw 外部信号

### Stage 6: optimize_dxb
- DXBOptimizer 安全优化（4 Pass）:
  1. 去重相同步骤
  2. 移除孤立节点
  3. 去重约束列表
  4. 折叠线性链（同类型 A→B）

### Stage 7: validate_dxb
- DXBValidator 安全验证（3 层）:
  - **结构层**（阻断）：环检测、依赖完整性、孤儿路径
  - **治理层**（阻断）：决策泄漏检测、policy 字段完整性
  - **策略层**（警告）：覆盖完整性、风险阈值

### Stage 8: emit_final_dxb
- 组装 CompilationResult
- 包含 DXB + IR + 诊断 + 优化报告 + 验证报告

---

## 四、外部集成

### PolicyInjector — Governance 约束注入

从 SGL/ATS/Scheduler 事件提取约束，在编译时注入 DXB：

```
SGL Events    ──→ {intent_constraint, risk_threshold, threat_type, governance_impact}
ATS Events    ──→ {passed, phases, risk_score, failure_reason}
Scheduler     ──→ {final_state, action, quarantine_reason}
```

**关键**: 所有输出包含 `"runtime_decision": False`。

### OpenClawMemoryAdapter — #003 能力源

从 OpenClaw Memory System 提取能力信号：

- 8 种已知能力模式（关键词匹配）
- 5 个静态信号（无输入时返回）
- confidence 按匹配比例计算

---

## 五、测试覆盖

**113 tests, 12 类**:

| 测试类 | 测试数 |
|--------|--------|
| TestPolicyInjector | 16 |
| TestOpenClawAdapter | 13 |
| TestDXBBuilder | 10 |
| TestOptimizer | 10 |
| TestValidator | 13 |
| TestDVXCompilerPipeline | 15 |
| TestDeterminism | 3 |
| TestCapabilityIR | 8 |
| TestDXB | 8 |
| TestCompilerV2Package | 2 |
| TestEdgeCases | 15 |

全量回归: 724 passed, 1 skipped（零破坏）。

---

## 六、待完成

根据 ZT11 规范，以下模块尚未实现：

| 模块 | 说明 |
|------|------|
| Kernel v2 失智化 | `core/kernel.py` 移除决策逻辑 |
| Runtime Engine 改造 | `runtime/engine.py` 改为 DXB 执行器 |
| Runtime Models 简化 | `runtime/models.py` 删除冗余字段 |
| Governance Plugin 接口 | SGL/ATS/Scheduler 改为 Compiler Plugin |

---

*DVX Compiler v2.0 编译系统核心架构文档。*
