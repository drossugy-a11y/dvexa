# ZT8 — DVexa v1.88 External Capabilities & Execution Reports

> **日期**：2026-05-07
> **版本**：v1.88
> **前置**：ZT7.md (v1.87 Resilience Governance)
> **测试**：229 个，全部通过（旧 169 + 新增 60）

---

## 一、v1.88 本质

不是"自进化"，而是"外部能力观察 + 能力提取准备"。建立两个新增长层：External Capability Layer（安全接入外部系统）和 Execution Report Layer（让系统可观测/可审计/可回放）。

---

## 二、变更内容

### 新增文件

| 文件 | 职责 | 行数 |
|------|------|------|
| `external/__init__.py` | 外部层模块声明 + 架构约束 | ~10 |
| `external/adapter.py` | ExternalAgentAdapter Protocol（stateless, input→output） | ~30 |
| `external/registry.py` | 白名单外部 adapter 注册表（禁止 eval/exec/dynamic import） | ~45 |
| `external/sandbox.py` | ExternalSandbox 双层隔离（进程级超时 + 数据级白名单净化） | ~95 |
| `external/assimilator.py` | CapabilityAssimilator（只建议，不自动注册） | ~80 |
| `external/report.py` | ExternalCallReport + AssimilationReport + ExternalReporter | ~80 |
| `report/__init__.py` | 报告层模块声明 + 边界约束 | ~12 |
| `report/metrics.py` | MetricsCollector（从 post-execution 数据提取指标） | ~80 |
| `report/execution_report.py` | ExecutionReport 标准结构 + ExecutionReportBuilder | ~100 |
| `report/formatter.py` | ReportFormatter（text/JSON/summary 格式化） | ~85 |
| `tests/test_external.py` | 外部层测试（30 个） | ~290 |
| `tests/test_report.py` | 报告层测试（30 个） | ~270 |

### 变更文件

| 文件 | 变更 | 原因 |
|------|------|------|
| `main.py` | 新增外部层/报告层初始化和 API 观察链路（+25 行） | 组装层集成 |
| `api/server.py` | 新增 observer 回调机制（+5 行） | 不污染 kernel 控制流 |

### 冻结层验证

| 文件 | 行数 | 状态 |
|------|------|------|
| `core/kernel.py` | 75 | 零改动 |
| `core/executor.py` | 75 | 零改动 |
| `core/guard.py` | 101 | 零改动 |
| `agents/base_agent.py` | 110 | 零改动 |
| `capabilities/router.py` | — | 零改动 |
| `governance/`（全部） | — | 零改动 |
| `insight/`（全部） | — | 零改动 |

---

## 三、核心流程

### 外部能力接入

```
外部 Agent
    │
    ▼
ExternalAgentAdapter (Protocol)
    │ stateless, input→output
    ▼
ExternalSandbox.call()
    ├── 进程级隔离 (threading.Timer 超时)
    ├── 数据级隔离 (白名单过滤 + 剥离控制信号)
    └── 输出: {output, artifacts, logs, metadata, sandbox_meta}
         │
         ▼
CapabilityAssimilator.analyze()
    ├── 只输出: {candidate_skill, confidence, reason, risk, source_project}
    └── 永不调用 register_skill() / router / governor
         │
         ▼
    人工审批 → Compiler → Manual Register
```

### 执行报告

```
kernel.run_task() returns result
    │
    ▼
ExecutionReportBuilder.from_kernel_result()
    ├── MetricsCollector.collect()
    ├── InsightAgent.generate_report()
    ├── ExternalReporter.summary()
    │
    ▼
ReportFormatter.to_text() / to_json() / to_summary()
```

---

## 四、关键设计决策

1. **Adapter 用 Protocol 不用 ABC** — 遵循 `capabilities/skill.py` 的 `SkillHandler(Protocol)` 模式
2. **Sandbox 输出白名单** — 只保留 `{output, artifacts, logs, metadata}`，剥离 `{confidence, score, decision, status, routing, governance, suggestion}`
3. **Assimilator 不持机器人** — 不持有 router/governor 引用，确保无法自动注册
4. **Report 纯 post-hoc** — 不嵌入 kernel/executor 执行链路，不修改 governance
5. **Registry 白名单** — 禁止 eval/exec/dynamic import string

---

## 五、架构红线

```
观察权 ≠ 修改权
分析权 ≠ 注册权
建议权 ≠ 控制权

外部 agent = 能力来源，不是控制来源
Report     = 观察层，不是控制层
Kernel     = 唯一控制权，永远不改
```
