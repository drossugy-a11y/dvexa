# ZT2 — DVexa v1.6 控制稳定性强化

> **日期**：2026-05-07
> **版本**：v1.6
> **主题**：控制稳定性工程 — 防 Executor 膨胀 + 防 MCP 变第二内核
> **测试**：43 个，全部通过

---

## 一、v1.6 核心目标

v1.6 不是功能增强，而是**结构冻结**。三件事：

| # | 目标 | 风险来源 |
|---|------|----------|
| 1 | 防 executor 变成第二个 brain | `_validate_result` + `confidence` 判断 |
| 2 | 防 MCP 变成第二个 runtime kernel | MCP 可能知晓 context/state |
| 3 | 防 planner 变成隐性决策层 | prompt 中隐含控制逻辑 |

**一句话**：让系统只能"变强"，不能"变结构复杂"。

---

## 二、变更清单

### 修改文件

| 文件 | 变更 | 说明 |
|------|------|------|
| `core/guard.py` | **ControlGuard → CBF** | 升级为 Control Boundary Filter，强化清洗规则 |
| `core/executor.py` | **去智能化** | 移除 `_validate_result`，返回值仅含 `step_id` + `output` |
| `core/kernel.py` | **使用 CBF** | `ControlGuard.sanitize` → `CBF.sanitize` |
| `tools/mcp_tool.py` | **隔离强化** | 增强三不原则契约，明确 stateless IO |
| `tests/test_executor.py` | **重构** | 移除 ValidateResult 测试，新增 ExecuteStep 测试 |
| `tests/test_guard.py` | **新增** | 20 个 CBF 测试：sanitize/assert_signal/verify |

### 删除内容

| 删除 | 行数 | 原因 |
|------|------|------|
| `Executor._validate_result()` | 26 行 | executor 不做"正确性判断" |
| executor 返回中的 `confidence` | — | 禁止评分信号进入返回路径 |
| executor 返回中的 `status` | — | 禁止状态判断进入返回路径 |
| `TestValidateResult` 类 | 30 行 | 对应功能已移除 |

### 未修改文件

`agents/base_agent.py`、`core/scheduler.py`、`core/state.py`、`memory/memory_store.py`、`tools/base_tool.py`、`tools/code_tool.py`、`tools/http_tool.py`、`tools/llm_tool.py`、`config/`、`api/server.py`、`main.py`

---

## 三、CBF（Control Boundary Filter）详解

### 定位

```
Kernel ← CBF ← Executor ← Tool
           ↑
   唯一的数据净化关口
```

### 清洗规则

| 允许通过 | 自动剥离 |
|----------|----------|
| `step_id` | `confidence`、`score`、`risk`、`validation` |
| `output` | `suggestion`、`status`、`tool`、`tool_metadata` |
| | `heuristic_suggestion`、`validation_result` |

### 控制信号白名单（5 种）

```
step_completed
step_failed
retry_exceeded
plan_ready
execution_result
```

任何不在白名单中的信号试图进入控制流 → `ValueError`

### 工作方式

```
Executor 返回: {step_id, output}
                    │
     CBF.sanitize()  ← 无字段可剥离（executor 已去智能化）
                    │
Kernel 接收:  {step_id, output}
```

executor 现在已经不产生非控制字段，CBF 是第二道防线。

---

## 四、Executor 去智能化详情

### v1.5 的 executor（含判断逻辑）

```
execute_step:
  → agent.execute_step → LLM
  → _select_tool → 规则映射
  → _call_tool → IO
  → _validate_result → 评分判断 ← 半脑化
  → return {step_id, output, confidence, status} ← 含判断信号
```

### v1.6 的 executor（纯执行机）

```
execute_step:
  → agent.execute_step → LLM
  → _select_tool → 规则映射
  → _call_tool → IO
  → return {step_id, output} ← 只有事实
```

**移除**：
- `_validate_result()` 方法（26 行）
- 返回值中的 `confidence` 字段
- 返回值中的 `status` 字段
- 所有评分/判断逻辑

**保留**：
- `_select_tool()` — 纯关键词映射，非推理
- `_call_tool()` — 内部 try/except 消化错误，不抛异常

---

## 五、MCP 隔离状态

| 约束 | 状态 |
|------|------|
| Stateless IO adapter | ✔ 契约声明 |
| 不访问 context/history/state | ✔ 无相关引用 |
| 不引用 executor/planner/kernel | ✔ 仅引用 `base_tool.Tool` |
| 返回值纯数据 | ✔ `{"content": str}` |
| 默认 disabled | ✔ `mcp_servers.json` 全部 `"enabled": false` |

---

## 六、v1.6 执行链路

```
User
  │
  ▼
Kernel (唯一决策)          ← 执行/重试/重规划/终止
  │
  ├─ Planner (只输出计划)   ← 无控制权
  │
  ├─ Executor (只执行动作)   ← 无判断，无评分
  │     └─ _select_tool (规则)
  │     └─ _call_tool (IO)
  │     └─ 返回 {step_id, output}
  │
  ├─ CBF (数据净化)          ← 剥离非控制信号（二道防线）
  │
  └─ Kernel (只接收结果)     ← 只看"事实"，不看"评价"
```

---

## 七、系统状态对比

| 维度 | v1.5+ | v1.6 |
|------|-------|------|
| 总测试 | 29 | **43** |
| CBF 测试 | 0 | **20** |
| Executor 行数 | 93 | **82**（-11） |
| Executor 方法 | 5 | **4**（-1） |
| 评分系统 | `_validate_result` + `_compute_confidence` | `_compute_confidence` 仅存于 agent（metadata） |
| CBF 命名 | ControlGuard | **CBF（Control Boundary Filter）** |
| 控制信号 | 4 种 | **5 种** |
| 模块权限 | 6 级 | **6 级 + CBF 净化闸口** |

---

## 八、风险评估

| 风险 | 等级 | v1.6 变化 |
|------|------|-----------|
| 架构复杂度 | LOW | 不变，kernel 仍 76 行 |
| 控制流混乱 | LOW | **CBF 强化，executor 去智能化，风险进一步降低** |
| MCP 扩展 | LOW→MEDIUM | 契约强化，但子进程+线程风险仍在 |
| Tool 爆炸 | MEDIUM | 不变 |
| Executor 膨胀 | MEDIUM→**LOW** | **已去智能化，职责收缩** |
| 版本追踪 | LOW | 不变 |

---

## 九、系统判断

**阶段：架构稳定期（A）初期**

v1.6 完成后，DVexa 正式进入架构稳定期：
- Kernel 76 行零膨胀，唯一控制中心
- Executor 82 行纯执行机，不做判断
- CBF 作为数据净化闸口，防止任何非控制信号进入 kernel
- MCP 完全隔离在 tool layer，默认 disabled
- 43 测试全部通过

> **DVexa 现在是"结构冻结"的单核 AI 系统。控制边界有明确的数据净化闸口（CBF），Executor 回归纯执行机定位，MCP 被完全隔离在工具层。系统可以继续变强，但控制结构已被冻结。**
