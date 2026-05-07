# COMPILER_V2 v1.0 — DVX Capability Compiler v2.0

> **版本**: 1.0
> **日期**: 2026-05-07
> **状态**: ✅ COMPLETE
> **前置**: V2_TRANSITION_v2.0（ZT11 架构规范）
> **类型**: 纯编译时分析系统（Compile-time Only）

---

## 一、设计定位

**DVX Capability Compiler v2.0 是 EventStore → DXB（执行蓝图）的纯编译管道。**

将系统从"运行时决策引擎"转型为"编译器驱动执行 OS"——Compiler 在编译阶段完成所有分析和规划，Kernel 降级为纯执行器。

```
                    DVX v2.0 Compiler Architecture
                    ==============================

 EventStore ────┐
 OpenClaw #003 ─┼──→ DVXCompiler ──→ DXB ──→ Kernel (纯执行器)
 (memory) ──────┘       │
                         │  8-Stage Pipeline
                         ├─ 1. ingest_eventstore
                         ├─ 2. extract_capabilities
                         ├─ 3. merge_capability_space
                         ├─ 4. build_capability_ir
                         ├─ 5. build_dxb
                         ├─ 6. optimize_dxb
                         ├─ 7. validate_dxb
                         └─ 8. emit_final_dxb
```

### 核心原则

- **Compiler = 纯转换器**：不做运行时决策，不产生副作用
- **DXB = 唯一输出**：可执行蓝图，Kernel 按键执行
- **EventStore = 唯一事实源**：编译器从 EventStore 读取，不修改
- **确定性**：相同输入 → 相同 DXB（可重放）
- **Governance 前置**：SGL/ATS/Scheduler 在编译时注入约束，不在运行时决策

---

## 二、模块架构

```
compiler_v2/
├── __init__.py              # 模块导出
├── capability_ir.py         # IR + DXB 数据结构（~210 行）
├── policy_injector.py       # SGL/ATS/Scheduler 约束注入器（~150 行）
├── openclaw_adapter.py      # OpenClaw #003 Memory 能力适配器（~130 行）
├── dxb_builder.py           # CapabilityIR → DXB 构建器（~180 行）
├── dvx_compiler.py          # 8 阶段主流水线编排器（~480 行）
├── optimizer.py             # DXB 结构优化器（~280 行）
└── validator.py             # DXB 安全验证器（~250 行）
```

### 数据流

```
Event[] ──→ CapabilityIR ──→ DXB ──→ Optimized DXB ──→ Validated DXB
              │                │
              │                ├── steps[]（CapabilityStep 列表）
              │                ├── dag（依赖图）
              │                └── constraints（治理约束）
              │
              ├── capabilities[]（CapabilityNode 列表）
              ├── risk_signals（风险信号）
              └── governance_constraints（治理约束）
```

---

## 三、核心数据结构

### CapabilitySignal（能力信号）

```python
@dataclass(frozen=True)
class CapabilitySignal:
    source: str           # "eventstore" | "openclaw"
    signal_type: str      # "semantic_intent" | "threat_detected" | ...
    payload: dict         # 信号内容
    confidence: float     # 置信度 [0, 1]
    trace_id: str         # 溯源追踪
```

### CapabilityNode（能力节点）

```python
@dataclass(frozen=True)
class CapabilityNode:
    id: str               # 唯一标识
    node_type: str        # SKILL | TOOL | GOVERNANCE_CHECK | RUNTIME_ACTION | MEMORY
    name: str             # 能力名称
    metadata: dict        # 附加元数据
```

### CapabilityIR（能力中间表示）

```python
@dataclass
class CapabilityIR:
    intent: str                        # 提取的用户意图
    target: str                        # 目标
    capabilities: list[CapabilityNode] # 能力节点列表
    risk_signals: dict[str, float]     # 风险信号
    governance_constraints: dict       # 治理约束
    extracted_patterns: list[str]      # 提取的模式
    trace_id: str                      # 追踪 ID
```

### CapabilityStep（执行步骤）

```python
@dataclass(frozen=True)
class CapabilityStep:
    id: str                    # 步骤 ID
    step_type: str             # SKILL | TOOL | GOVERNANCE_CHECK
    capability_ref: str        # 能力引用
    inputs: dict               # 输入参数
    dependencies: list[str]    # 依赖步骤 ID 列表
    risk: float                # 风险评分
    preconditions: list[str]   # 前置条件
    postconditions: list[str]  # 后置条件
    expected_output: dict      # 期望输出
```

### DXB（执行蓝图）

```python
@dataclass
class DXB:
    id: str                           # 蓝图 ID
    steps: list[CapabilityStep]       # 执行步骤列表
    dag: dict[str, list[str]]         # 依赖图
    constraints: dict                 # 编译时约束
    origin_trace_id: str              # 溯源追踪
    compiled_at: float                # 编译时间戳

    # 方法: ordered_steps(), to_dict(), get_step(), risk_score, step_count
```

### CompilationResult（编译结果）

```python
@dataclass
class CompilationResult:
    dxb: DXB | None                          # 最终执行蓝图
    ir: CapabilityIR | None                  # 中间表示
    diagnostics: list[CompilationDiagnostic] # 编译诊断
    optimization_report: OptimizationReport  # 优化报告
    validation_report: ValidationReport      # 验证报告
    compiled_at: float                       # 编译时间戳
```

---

## 四、核心模块

### 4.1 PolicyInjector（策略注入器）

将 Governance events（SGL/ATS/Scheduler）输出转换为编译时约束，注入 DXB。

| 方法 | 输入 | 输出 |
|------|------|------|
| `inject_sgl_constraints()` | semantic events | {intent_constraint, risk_threshold, threat_type} |
| `inject_ats_constraints()` | validate events | {passed, phases, risk_score} |
| `inject_scheduler_constraints()` | schedule events | {final_state, action, quarantine_reason} |
| `inject_all()` | all events | 合并后的完整约束 |

**关键约束**: 所有输出包含 `"runtime_decision": False`，确保 Kernel 不做决策。

### 4.2 OpenClawMemoryAdapter（外部能力适配器）

仅作为静态能力信号提供者，不执行运行时逻辑。

- `extract_capabilities(memory_outputs)` — 从 OpenClaw Memory System 输出提取能力信号
- 无输入时返回 5 个静态信号（hybrid_search, mmr_ranking, chunking, semantic_search, embeddings）
- 关键词匹配 8 种能力模式

### 4.3 DXBBuilder（DXB 构建器）

将 CapabilityIR 编译为 DXB 执行蓝图。

**排序规则**:
- GOVERNANCE_CHECK 前置
- SKILL 中间（依赖 governance steps）
- TOOL 末尾（依赖 skill steps）

**集成点**:
- PolicyInjector → constraints
- OpenClawMemoryAdapter → 步骤 annotation

### 4.4 DXBOptimizer（结构优化器）

仅做安全的、结构级的优化。

| 优化 Pass | 操作 |
|-----------|------|
| deduplicate_steps | 合并相同 capability_ref + inputs 的步骤 |
| remove_unreachable | 移除无依赖关系的孤立步骤 |
| deduplicate_constraints | 递归去重约束字典中的列表值 |
| collapse_linear_chains | 折叠 A→B 同类型线性依赖链 |

**禁止操作**: 修改风险评分、修改治理约束、语义重新解释。

### 4.5 DXBValidator（安全验证器）

编译时安全门，验证 DXB 正确性。

**结构检查（阻断性）**:
- DAG 环检测（DFS）
- 依赖完整性（所有引用存在）
- 孤儿执行路径检测
- 步骤数量合理性

**治理检查（阻断性）**:
- constraints 格式良好
- 无运行时决策泄漏（FORBIDDEN_RUNTIME_KEYWORDS）
- policy 字段完整性（compiled_at, runtime_decision）

**策略检查（警告性）**:
- Governance 覆盖完整性
- 风险阈值合理性

---

## 五、8 阶段编译流水线

| 阶段 | 方法 | 职责 |
|------|------|------|
| 1. Ingest | `_stage_ingest` | 加载 EventStore 事件，按 trace_id 过滤 |
| 2. Extract | `_stage_extract` | 从事件提取 CapabilitySignal，整合 OpenClaw 信号 |
| 3. Merge | `_stage_merge` | 去重信号（相同 type+trace_id 保留最高 confidence） |
| 4. Build IR | `_stage_build_ir` | 构建 CapabilityIR（intent, nodes, risk_signals） |
| 5. Build DXB | `_stage_build_dxb` | 通过 DXBBuilder 构建执行蓝图 |
| 6. Optimize | `_stage_optimize` | 结构优化（去重、去孤、折叠） |
| 7. Validate | `_stage_validate` | 安全验证（环检测、决策泄漏、依赖完整性） |
| 8. Emit | `_stage_emit` | 发射 CompilationResult |

---

## 六、测试覆盖

**113 tests、12 个测试类**:

| 测试类 | 测试数 | 覆盖范围 |
|--------|--------|----------|
| TestPolicyInjector | 16 | SGL/ATS/Scheduler 约束提取、合并、边界 |
| TestOpenClawAdapter | 13 | 静态信号、输出解析、关键词匹配、置信度 |
| TestDXBBuilder | 10 | IR→DXB 构建、DAG 结构、约束注入、排序 |
| TestOptimizer | 10 | 去重、去孤、折叠、约束去重、安全保障 |
| TestValidator | 13 | 环检测、依赖完整性、决策泄漏、孤儿检测、风险标记 |
| TestDVXCompilerPipeline | 15 | 8 阶段端到端、trace_id 过滤、威胁检测、OpenClaw 集成 |
| TestDeterminism | 3 | 相同输入→相同输出、to_dict 一致性 |
| TestCapabilityIR | 8 | IR 数据结构、节点过滤、frozen 属性 |
| TestDXB | 8 | DXB 数据结构、DAG 构建、拓扑排序 |
| TestCompilerV2Package | 2 | 模块导出、类实例化 |
| TestEdgeCases | 15 | None 处理、空输入、畸形约束、异常路径 |

---

## 七、禁止行为

Compiler v2 中**严格禁止**:

- ❌ 任何运行时决策逻辑
- ❌ 修改 EventStore
- ❌ 修改现有 Runtime/Governance 代码
- ❌ DXB 中包含 `runtime_decision: true`
- ❌ Validator 修改 DXB（只读验证）
- ❌ Optimizer 修改风险评分或语义

---

## 八、与 v1.91 的兼容性

- **不修改** `core/kernel.py`、`runtime/engine.py`、`governance/` 任何文件
- **纯新增** compiler_v2/ 目录
- **不参与** 运行时控制流
- **EventStore 只读**：从 EventStore 读取，不写入
- **全量回归**: 724 passed, 1 skipped（零破坏）

---

*COMPILER_V2 v1.0 — DVX Capability Compiler v2.0 版本规范。*
