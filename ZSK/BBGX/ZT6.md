# ZT6 — DVexa v1.86 Insight Agent（系统洞察层）

> **日期**：2026-05-07
> **版本**：v1.86
> **前置**：ZT5.md (v1.8 能力治理)
> **测试**：133 个，全部通过（旧 114 + 新增 19）

---

## 一、v1.86 本质

让系统第一次能解释自己的行为。纯观察层，不参与任何执行或决策。

---

## 二、变更内容

### 新增文件

| 文件 | 职责 |
|------|------|
| `insight/agent.py` | InsightAgent 入口，编排 analyzer→drift→report 链路 |
| `insight/analyzer.py` | SystemAnalyzer：分析 skill 频率、趋势、错误聚类 |
| `insight/drift.py` | DriftDetector：基线比对检测 usage/latency/error 偏移 |
| `insight/report.py` | ReportGenerator：生成 JSON + text 报告 |
| `insight/__init__.py` | 模块声明 |
| `tests/test_insight.py` | 19 个洞察层测试 |
| `ZSK/behavior_v1.86.md` | 系统行为快照 |
| `ZSK/SPEC.md` | 知识库规范 |

### 冻结层验证

| 文件 | 行数 | 变更 |
|------|------|------|
| `core/kernel.py` | 75 | 未修改 |
| `core/executor.py` | 75 | 未修改 |
| `core/guard.py` | 101 | 未修改 |
| `agents/base_agent.py` | 110 | 未修改 |
| `capabilities/router.py` | — | 未修改 |
| `governance/`（全部） | — | 未修改 |

---

## 三、核心流程

```
SkillGovernor ─┐
               ├─→ SystemAnalyzer.analyze()
MemoryStore  ──┘         │
                         ▼
                  DriftDetector.detect(analysis)
                         │
                         ▼
                  ReportGenerator.generate(analysis, drift)
                         │
                         ▼
              {summary, health_status, key_insights, recommendations}
```

---

## 四、架构红线

Insight Agent 严格遵循：
- 不调用 tool
- 不参与 kernel/executor 决策
- 不修改 governance 评分
- 不嵌入执行链路
- 不修改任何现有文件
