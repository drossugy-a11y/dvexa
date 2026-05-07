# ZT7 — DVexa v1.87 Resilience Governance（鲁棒性治理层）

> **日期**：2026-05-07
> **版本**：v1.87
> **前置**：ZT6.md (v1.86 Insight Agent)
> **测试**：169 个，全部通过（旧 151 + 新增 18）

---

## 一、v1.87 本质

修复 v1.86 的核心缺陷：**一次失败不应导致评分崩溃或 skill 直接 REMOVED**。引入贝叶斯平滑评分、minimum_samples 小样本保护、完整降级→隔离→恢复生命周期。

---

## 二、变更内容

### 新增文件

无新增文件 — 全部为现有文件修改。

### 变更文件

| 文件 | 变更 | 原因 |
|------|------|------|
| `governance/skill_score.py` | 重写评分系统 | 贝叶斯平滑 `bayesian_success_rate = (successes + 8) / (usage + 10)`，新增 `consecutive_failures`、`recovery_attempts` 追踪 |
| `governance/lifecycle.py` | 重写生命周期 | 移除自动 REMOVED，新增 DEGRADED/QUARANTINED/RECOVERED 路径，minimum_samples 保护，consecutive_failures 准入门槛 |
| `governance/skill_governor.py` | 路由权重 + 恢复机制 | `STATUS_WEIGHTS` 路由权重表、`try_recovery()` 恢复方法、生态稳定性/隔离数/流失率指标 |
| `insight/analyzer.py` | 新增生态指标 | `ecosystem_stability_score`、`capability_churn_rate`、`quarantine_count`、`recovery_success_rate` 输出 |
| `insight/report.py` | 更新健康评估 | 隔离数 >1 或稳定性 <0.5 触发 unstable |

### 冻结层验证

| 文件 | 行数 | 状态 |
|------|------|------|
| `core/kernel.py` | 75 | 未修改 |
| `core/executor.py` | 75 | 未修改 |
| `core/guard.py` | 101 | 未修改 |
| `agents/base_agent.py` | 110 | 未修改 |
| `capabilities/router.py` | — | 未修改 |
| `capabilities/skill.py` | — | 未修改 |
| `insight/agent.py` | — | 未修改 |
| `insight/drift.py` | — | 未修改 |

---

## 三、核心流程

### 生命周期

```
experimental ──→ active ──→ stable ──→ degraded ──→ quarantined ──→ recovered ──→ active
                    ↑                                                      │
                    └──────────────────── 恢复路径 ──────────────────────────┘
                    ↑
    degraded ───────┘ (错误率恢复后直接回 active)

REMOVED → 仅人工触发，governance 永不自动设置
```

### 恢复判断

```
evaluate_recovery(score):
  consecutive_failures > 0  ──→ "failed"
  consecutive_failures == 0 && usage >= 3 ──→ "recovered"
  其他 ──→ "pending"
```

### 路由权重

| 状态 | 权重 |
|------|------|
| ACTIVE / STABLE / RECOVERED | 1.0 |
| EXPERIMENTAL | 0.9 |
| DEGRADED | 0.5 |
| QUARANTINED | 0.0 |
| REMOVED | 0.0 |

---

## 四、架构红线

- Governance 层仍为纯状态管理，不嵌入执行链路
- Insight Agent 继续纯观察，不受 governance 变更影响
- 冻结层（kernel / executor / guard / base_agent / router）均未修改
- REMOVED 仅人工触发，governance 无自动移除路径
- 小样本（< MINIMUM_SAMPLES=10）保护优先于降级逻辑
