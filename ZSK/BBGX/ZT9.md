# ZT9 — DVexa v1.89 Assimilation Log System（吞并日志系统）

> **日期**：2026-05-07
> **版本**：v1.89
> **前置**：ZT8.md (v1.88 External + Report)
> **测试**：268 个，全部通过（旧 229 + 新增 39）

---

## 一、v1.89 本质

DVexa 第一次拥有"进化记忆"。系统现在能回答：学过什么项目？从哪里学的？分析了哪些模块？建议吞并哪些能力？风险是什么？哪些被批准/拒绝/待定？

---

## 二、变更内容

### 新增文件

| 文件 | 职责 | 行数 |
|------|------|------|
| `external/assimilation_log.py` | AssimilationLogEntry + AssimilationLogger（save/load/search/summarize） | ~270 |
| `tests/test_assimilation_log.py` | 39 个测试 | ~320 |
| `ZSK/assimilation_logs/` | 日志存储目录（自动创建） | — |

### 修改文件

无 — 全部为新增。

### 冻结层验证

| 文件 | 状态 |
|------|------|
| `core/kernel.py` | 零改动 |
| `core/executor.py` | 零改动 |
| `core/guard.py` | 零改动 |
| `agents/base_agent.py` | 零改动 |
| `external/` 其他文件 | 零改动 |

---

## 三、Assimilation Log System 架构

```
外部项目分析完成
    │
    ▼
AssimilationLogger.save_log(entry)
    │
    ├── JSON: ZSK/assimilation_logs/YYYYMMDD_project.json
    └── MD:  ZSK/assimilation_logs/YYYYMMDD_project.md（可选）
         │
         ▼
AssimilationLogger 提供:
    ├── load_log(filename)     → 单条日志加载
    ├── search_logs(keyword)   → 按项目/能力/风险/决策搜索
    ├── summarize_project(name) → 项目历史汇总
    └── list_all()             → 所有日志清单
```

### 日志生命周期

```
分析外部项目 → 生成 AssimilationLogEntry → 持久化到文件系统
    │
    ├── 人工审核 → 修改 decision 为 approved/rejected
    ├── 能力注册 → 关联到实际 skill（未来）
    └── 后续分析 → 累加历史记录
```

---

## 四、搜索机制

| 字段 | 搜索范围 | 用途 |
|------|----------|------|
| `project` | 按项目名 | "DVexa 学过 openclaw 吗？" |
| `capability` | 按候选能力名 | "有 code_executor 相关的分析吗？" |
| `risk` | 按风险等级 | "哪些分析标记为 high risk？" |
| `decision` | 按决策状态 | "哪些分析被批准了？" |
| 全部字段 | 全文搜索 | 模糊匹配 |

---

## 五、知识沉淀机制

```
Analyst（外部分析）
    │ 输出 candidate_skills
    ▼
AssimilationLogger（v1.89）
    │ 持久化到文件系统
    │ 支持搜索/汇总
    ▼
Human Review
    │ 人工审批
    ▼
Skill Registry（手动）
    │ 正式注册
    ▼
Governance（持续追踪）
```

---

## 六、"系统进化历史"设计说明

1. **日志不是运行日志** — 记录的是"系统学过什么"，不是"系统做了什么"
2. **纯文件 IO** — 不依赖任何数据库，不进入控制流
3. **搜索能力** — 按项目/能力/风险/决策搜索
4. **防文件名冲突** — 同项目多次分析自动加序号
5. **路径穿越防护** — 文件名净化（只保留字母数字下划线连字符）

### 约束执行

```
❌ 不允许进入 kernel
❌ 不允许影响 router
❌ 不允许影响 governance
❌ 不允许自动触发注册
❌ 不允许自动修改系统
依赖白名单：dataclasses, pathlib, json, typing, external
禁止引用：kernel, executor, router, governor
```
