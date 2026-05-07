# ZT4 — DVexa v1.7 能力增长隔离架构

> **日期**：2026-05-07
> **版本**：v1.7
> **主题**：能力增长隔离 — 把"变强"从控制系统中彻底剥离
> **测试**：59 个，全部通过

---

## 一、v1.7 的本质

v1.6 锁死了控制权，v1.7 解决下一个问题：**系统怎么变强，但永远不变复杂？**

答案：**Capability Isolation Layer（能力隔离层）**

```
v1.6 控制权锁定      →   系统不乱
v1.7 能力增长隔离     →   能力增长不破坏控制结构
```

---

## 二、架构变更

### 新增 Capability Layer

```
                        ┌──────────────────────┐
                        │   Kernel              │ ← 冻结
                        ├──────────────────────┤
                        │   CBF                 │ ← 冻结
                        ├──────────────────────┤
                        │   Planner             │ ← 冻结
                        ├──────────────────────┤
                        │   Executor            │ ← 冻结
                        ├──────────────────────┤
                        │   Capability Router   │ ← v1.7 新增
                        ├──────────────────────┤
                        │   Skills (能力集)      │ ← 唯一增长区
                        │   llm / code / http   │
                        │   + 未来无限扩展       │
                        └──────────────────────┘
```

### 冻结层（零改动）

| 模块 | 文件 | 状态 |
|------|------|------|
| Kernel | `core/kernel.py` | 未修改 |
| Executor | `core/executor.py` | 未修改 |
| CBF | `core/guard.py` | 未修改 |
| Planner | `agents/base_agent.py` | 未修改 |

### 增长层（新增）

| 模块 | 文件 | 职责 |
|------|------|------|
| Skill Registry | `capabilities/skill.py` | 技能注册与发现 |
| Capability Router | `capabilities/router.py` | 路由层，keyword→skill 匹配 |
| LLM Skill | `capabilities/skills/llm_skill.py` | LLM 能力封装 |
| Code Skill | `capabilities/skills/code_skill.py` | 代码执行封装 |
| HTTP Skill | `capabilities/skills/http_skill.py` | HTTP 请求封装 |
| MCP Skill | `capabilities/skills/mcp_skill.py` | MCP 能力封装（默认 disabled） |

---

## 三、Capability Layer 设计

### SkillDef — 技能定义

```python
SkillDef(name, handler, keywords, description)
```

每个 skill 必须满足：
- **stateless**：无状态，不存储上下文
- **input → output**：纯函数式 IO
- **no memory**：不记忆历史
- **no decision**：不做判断

### SkillRegistry — 技能注册中心

```
register(name, handler, keywords)  → 注册技能
match(action)                       → keyword 匹配技能名
get(name)                           → 获取技能
all_skills()                        → 列出所有技能
```

### CapabilityRouter — 能力路由器

```
Router 定位：executor 和 skill 之间的过滤层
  ✗ 不允许"推理选工具"
  ✗ 不允许"动态策略选择"
  ✔ 只允许 keyword → skill mapping

Router 实现 Tool 接口，兼容 Executor 的 tool_registry。
build_tool_registry() 自动生成 Executor 兼容的注册表。
```

---

## 四、执行链路（v1.7 最终版）

```
User
  │
  ▼
Kernel (唯一决策)
  │
  ├─ CBF (信号过滤)
  │
  ├─ Planner (结构化计划)
  │
  ├─ Executor (纯执行)
  │     └─ _select_tool → 返回 "code_executor"
  │     └─ _call_tool → tool_registry["code_executor"]
  │
  ├─ Capability Router (路由层)     ← 新增
  │     └─ match(action) → 选择 skill
  │     └─ 委托给具体的 skill handler
  │
  ├─ Skill (纯 IO)
  │     └─ llm_skill.call(input) → dict
  │     └─ code_skill.call(input) → dict
  │
  ├─ CBF 再次过滤
  │
  └─ Kernel (只接收结果)
```

---

## 五、冻结 vs 增长

| 维度 | 冻结层 | 增长层 |
|------|--------|--------|
| 模块 | Kernel, CBF, Planner, Executor | Capability Layer |
| 代码量 | 固定（不会增加） | 可无限增长 |
| 职责 | 控制、决策、执行 | 提供能力 |
| 修改频率 | 永不 | 按需注册 |
| 新增能力方式 | — | 一行 `register_skill()` |

### 如何在 Capability Layer 新增能力

```python
# main.py 中只需加一行：
router.register_skill(
    "新能力名",     # 技能标识
    NewSkillHandler(),  # 实现 Tool.call(input) → dict
    keywords=["关键词1", "关键词2"],  # 触发关键词
    description="描述"  # 可选
)
# Router 自动将其接入系统，Executor 不需要任何改动
```

---

## 六、系统状态对比

| 指标 | v1.6 | v1.7 |
|------|------|------|
| 总测试 | 43 | **59** |
| Capability 测试 | 0 | **15** |
| 代码总量（.py） | 757 行 | **957 行** |
| 文件数 | 28 | **36** |
| 控制层文件修改 | 0 | **0** |
| 新增目录 | — | `capabilities/`（6 文件） |

### 冻结层完整性验证

| 文件 | 版本 | 行数 | 变更 |
|------|------|------|------|
| `core/kernel.py` | v1.3 | 76 | 未修改 |
| `core/executor.py` | v1.6 | 82 | 未修改 |
| `core/guard.py` | v1.6 | 53 | 未修改 |
| `agents/base_agent.py` | v1.5 | 110 | 未修改 |

---

## 七、风险评估

| 风险 | 等级 | 说明 |
|------|------|------|
| 架构复杂度 | LOW | Capability Layer 清晰隔离，不影响控制层 |
| 控制流混乱 | LOW | 冻结层零改动，CBF 在线 |
| 能力膨胀 | **MEDIUM** | Capability Layer 可能无限扩张，需关注 skill 质量 |
| MCP 扩展 | MEDIUM | 仍默认 disabled |
| 冻结层污染 | LOW | Capability Layer 不引用上层模块 |

---

## 八、系统判断

**阶段：架构稳定期（A）**

v1.7 完成后，DVexa 正式划分为两个隔离区域：

| 区域 | 特性 |
|------|------|
| **控制区**（冻结） | Kernel / CBF / Planner / Executor — **永久冻结** |
| **能力区**（增长） | Capability Layer — **可无限扩展** |

> **DVexa 现在是"控制冻结 + 能力隔离"的单核 AI 系统。能力可以无限增强，但控制结构永远冻结。这是从"AI 执行引擎"走向"AI OS 内核"的关键转折点。**

---

## 九、知识库索引

| 文件 | 内容 |
|------|------|
| `ZSK/ZT1.md` | v1.5+ 初始系统状态 |
| `ZSK/ZT2.md` | v1.6 控制稳定性强化 |
| `ZSK/ZT3.md` | GLM-4V-Flash 接入验证 |
| `ZSK/ZT4.md` | **当前** — v1.7 能力增长隔离架构 |
