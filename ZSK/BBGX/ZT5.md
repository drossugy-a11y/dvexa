# ZT5 — DVexa v1.8 能力治理系统

> **日期**：2026-05-07
> **版本**：v1.8
> **前置**：ZT4.md (v1.7 能力隔离架构)
> **测试**：114 个，全部通过（旧 59 + 新增 55）

---

## 一、变更内容

v1.7 解决了能力无限增长，v1.8 解决能力增长的质量控制。

### 新增 `governance/` 目录（5 文件）

| 文件 | 职责 |
|------|------|
| `skill_score.py` | SkillScore dataclass + combined_score 公式 |
| `lifecycle.py` | SkillStatus 枚举 + evaluate_lifecycle 自动升降级 |
| `conflict_detector.py` | ConflictDetector + SkillConflict（Jaccard ≥ 0.85） |
| `skill_governor.py` | 治理中心：注册/评分/选择/升降级/冲突检测 |
| `__init__.py` | 模块声明 |

### 变更文件（3 个）

- `capabilities/skill.py` — `_keyword_map` 升级为 `dict[str, list[str]]`，新增 `match_all()`
- `capabilities/router.py` — 集成 SkillGovernor，新增 `_GovernedRouterSkill`
- `main.py` — 注入 SkillGovernor

---

## 二、治理流程

```
action → match_all() → governor.best_skill_for() 
  → combined_score 排序 → 过滤 deprecated/removed → 返回最优 SkillDef
```

评分权重：success_rate 50% + stability 20% + error_rate 20% + latency 10%

---

## 三、冻结层（零改动）

kernel.py / guard.py / executor.py / base_agent.py — 未修改。
