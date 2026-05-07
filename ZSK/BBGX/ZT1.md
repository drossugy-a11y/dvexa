# ZT1 — DVexa 系统状态快照

> **日期**：2026-05-07
> **版本**：v1.5+（控制权锁定协议 v1.0 已实施）
> **代码**：872 行 | 20 文件 | 29 测试全部通过

---

## 一、项目定位

DVexa = AI Execution OS — 单核 AI 操作系统

- **技术栈**：Python 3.12 + FastAPI + OpenAI SDK
- **核心架构**：Kernel 唯一控制，5 层单向依赖
- **依赖**：fastapi, uvicorn, python-dotenv, openai, requests

---

## 二、版本演进

| 版本 | 说明 |
|------|------|
| v1.0 | JG1.0 骨架搭建（20 文件，6 包） |
| v1.2 | 多步执行 + 上下文传递 |
| v1.3 | 状态机（6 状态），retry + replan |
| v1.5 | Claude 生态融合：结构化规划、质量验证、MCP 适配器、测试骨架 |
| v1.5+ | **控制权锁定协议落地**：ControlGuard、Tool Sandbox、MCP 三不原则 |

---

## 三、系统架构

```
                     ┌──────────────────────┐
                     │   Kernel             │  ← 唯一控制中心
                     │   core/kernel.py     │     状态机控制
                     │   71 行              │     执行/重试/重规划决策
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │   Planner            │  ← 只规划，不控制
                     │   agents/base_agent  │     生成步骤列表
                     │   110 行             │     重规划
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │   Executor           │  ← 只执行，不决策
                     │   core/executor.py   │     选工具→调工具→验证
                     │   93 行              │     错误内部消化
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │   Tools              │  ← 纯 IO，不参与逻辑
                     │   tools/ (5 文件)    │     call(input) → dict
                     │   173 行             │     output == data
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │   API                │  ← 展示层
                     │   api/server.py      │     POST /task
                     │   49 行              │     GET /tasks /health
                     └──────────────────────┘
```

**支撑模块**：

| 模块 | 行数 | 职责 |
|------|------|------|
| core/state.py | 56 | TaskState + TaskStatus 枚举 |
| core/scheduler.py | 14 | 任务创建 |
| core/guard.py | 53 | **ControlGuard（控制权锁定协议）** |
| memory/memory_store.py | 26 | 内存存储 |
| config/config.py | 11 | LLM 配置 |
| config/mcp_servers.json | — | MCP 服务器配置（默认 disabled） |

---

## 四、执行链路

```
用户输入
    │
    ▼
Kernel.run_task()
    │
    ├─ PLANNING: Executor.plan_task() → Agent.plan() → LLM → steps
    │
    ├─ EXECUTING: loop steps:
    │     │
    │     ├─ Executor.execute_step()
    │     │     ├─ Agent.execute_step() → LLM → tool_input
    │     │     ├─ _select_tool(action) → tool_name
    │     │     ├─ _call_tool() → Tool.call() → raw output
    │     │     └─ _validate_result() → confidence (仅记录)
    │     │
    │     ├─ ControlGuard.sanitize()  ← 剥离 confidence/score/status
    │     │
    │     └─ Kernel 接收 {step_id, output}
    │           ├─ 成功 → history.append, step_index++
    │           └─ 异常 → retry / replan / fail
    │
    ├─ COMPLETED / FAILED
    │
    └─ Memory.save()
```

**关键约束**：

- 单向：Kernel → Planner → Executor → Tool → Result
- 禁止回流：Tool/Executor 的评分信号不能进入 Kernel 决策路径
- ControlGuard 只允许 `step_id` + `output` 进入 kernel

---

## 五、控制权锁定协议 v1.0

### 核心原则

| 编号 | 原则 | 含义 |
|------|------|------|
| P1 | Kernel 唯一控制权 | 所有"是否执行"的决策只能由 kernel 做出 |
| P2 | 执行与决策彻底分离 | Planner 只负责"想法"，Executor 只负责"动作"，Kernel 只负责"决定" |
| P3 | 工具永远不参与逻辑 | Tool/MCP = 纯函数 IO，不得参与推理或流程判断 |

### 落地措施

| 组件 | 文件 | 作用 |
|------|------|------|
| **ControlGuard** | core/guard.py | 净化进入 kernel 的信号，自动剥离非控制字段 |
| **Decision Isolation** | ControlSignal 枚举 | 只允许 4 种信号进入控制流 |
| **Tool Sandbox** | tools/base_tool.py | 契约：output == data, never == decision |
| **MCP 三不原则** | tools/mcp_tool.py | 不参与 planning / execution control / kernel decision |

### 决策黑名单（永远不能进入 kernel）

```
confidence    score    risk    validation_result
tool_metadata    heuristic_suggestion
```

### ControlGuard 工作方式

```
Executor 返回: {step_id, output, confidence, status, tool, score}
                    │
                    ▼
        ControlGuard.sanitize()
                    │
                    ▼
Kernel 接收:  {step_id, output}
```

---

## 六、模块权限

| 模块 | 权限 | 引用方向 |
|------|------|----------|
| kernel | 决策 + 控制流 | → executor, memory |
| planner | 生成计划 | → llm_tool |
| executor | 执行步骤 + 选工具 | → agent, tools |
| tools | IO 操作 | 无（不引用上层） |
| MCP | IO 扩展 | 无（不引用上层） |
| API | 展示层 | → kernel |

---

## 七、风险评估

| 风险 | 等级 | 说明 |
|------|------|------|
| 架构复杂度 | LOW | 20 文件 / 872 行 / 5 层单向，在可控范围 |
| 控制流混乱 | LOW | ControlGuard 护栏已锁定，kernel 零改动 |
| MCP 扩展 | MEDIUM | MCPTool 119 行含子进程+线程，当前 disabled |
| Tool 爆炸 | MEDIUM | MCPTool 可封装任意 MCP，复杂度集中点 |
| Executor 膨胀 | MEDIUM | 93 行 5 方法，需关注单一职责 |
| 版本追踪 | LOW | v1.4 跳号，无 CHANGELOG |
| Prompt 污染 | LOW | 静态 prompt + JSON fallback，无外部注入路径 |

---

## 八、系统阶段判断

**B→A 过渡期（快速增强末期 → 架构稳定期）**

- 非架构稳定期(A)：v1.5 刚完成融合，尚未经多轮运行验证
- 非复杂化风险期(C)：kernel 零膨胀，无新增控制层，29 测试全部通过
- 非失控风险期(D)：控制权 100% 在 kernel，ControlGuard 已锁定

> **DVexa 仍然是单核 AI 系统。控制权锁定协议 v1.0 已落地，所有外部能力被包裹在 tool/executor/planner 中作为纯能力接入，系统可以继续变强，但永远不会失去单核控制。**

---

## 九、文件清单

```
dvexa/
├── ZSK/ZT1.md                          知识库
├── main.py                             组装入口 (37行)
├── requirements.txt                    依赖清单
│
├── agents/
│   └── base_agent.py                   Planner (110行)
│
├── api/
│   └── server.py                       FastAPI 接口 (49行)
│
├── config/
│   ├── config.py                       LLM 配置 (11行)
│   └── mcp_servers.json                MCP 服务器配置
│
├── core/
│   ├── kernel.py                       唯一控制中心 (76行)
│   ├── executor.py                     执行引擎 (93行)
│   ├── guard.py                        控制守卫 (53行)
│   ├── scheduler.py                    任务调度 (14行)
│   └── state.py                        状态枚举 (56行)
│
├── memory/
│   └── memory_store.py                 内存存储 (26行)
│
├── tests/
│   ├── test_executor.py                12 测试
│   ├── test_kernel.py                  3 测试
│   ├── test_state.py                   10 测试
│   └── test_tools.py                   4 测试
│
└── tools/
    ├── base_tool.py                    抽象基类 + 沙箱契约
    ├── code_tool.py                    代码执行工具
    ├── http_tool.py                    HTTP 请求工具
    ├── llm_tool.py                     LLM 调用工具
    └── mcp_tool.py                     MCP 适配器（默认 disabled）
```
