# ZT3 — DVexa v1.6 GLM-4V-Flash 接入验证

> **日期**：2026-05-07
> **版本**：v1.6
> **主题**：LLM 引擎切换 + 全链路执行验证 + 系统状态快照

---

## 一、变更内容

将 LLM 引擎从 DeepSeek 切换为智谱 GLM-4V-Flash（免费模型）。

### 配置更新

| 配置项 | 旧值 | 新值 |
|--------|------|------|
| `LLM_API_KEY` | `sk-xxxx` | `68f079a3...` |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | `https://open.bigmodel.cn/api/paas/v4` |
| `LLM_MODEL` | `deepseek-chat` | `glm-4v-flash` |

---

## 二、全链路执行验证

### 测试 1：代码执行任务

```
输入: "用python计算 23 * 47 的结果"

链路:
  Kernel.run_task()
    → PLANNING: GLM 生成 plan（1步，risk=LOW）
    → EXECUTING:
        → Agent.execute_step → GLM 输出 Python 代码
        → Executor._select_tool("代码") → "code_executor"
        → Executor._call_tool → exec("print(23*47)")
        → CBF.sanitize → 仅保留 {step_id, output}
    → COMPLETED

结果: success: true, 步骤记录含代码执行输出
```

### 测试 2：LLM 问答任务

```
输入: "tell me what model you are"

链路:
  Kernel.run_task()
    → PLANNING: GLM 生成 plan
    → EXECUTING:
        → Agent.execute_step → GLM 输出 "I'm ChatGLM..."
        → Executor._select_tool("tell") → "llm"（默认）
        → Executor._call_tool → llm_tool 调用 GLM
        → CBF.sanitize → 仅保留 {step_id, output}
    → COMPLETED

结果: success: true, 模型回答 "ChatGLM by Zhipu AI"
```

---

## 三、系统状态快照

### 版本信息

| 项目 | 值 |
|------|-----|
| 版本 | v1.6 |
| 当前 LLM | GLM-4V-Flash（智谱） |
| 代码总量 | 757 行 |
| 文件数 | 28（.py + .json + .md） |
| 测试 | 43 个，全部通过 |

### 架构分层（稳定）

```
Kernel (76行) → 唯一决策
  Planner (110行) → 只规划
    Executor (82行) → 只执行
      Tools (173行) → 纯 IO
        CBF (53行) → 数据净化闸口
```

### 控制权锁定状态

| 协议 | 状态 |
|------|------|
| P1: Kernel 唯一控制权 | ✔ 锁定 |
| P2: 执行与决策分离 | ✔ 锁定 |
| P3: 工具不参与逻辑 | ✔ 锁定 |
| CBF 数据净化 | ✔ 在线 |
| executor 去智能化 | ✔ 已完成 |
| MCP 三不原则 | ✔ 已声明（默认 disabled） |

---

## 四、GLM-4V-Flash 表现评估

| 维度 | 评估 |
|------|------|
| 规划结构化输出 | ✔ 输出含 phase/risk/depends_on |
| 代码生成 | ✔ 生成 Python 代码 |
| 工具选择配合度 | ✔ action 描述支持规则匹配 |
| 响应速度 | 正常（免费模型） |
| JSON 格式稳定性 | ✔ 可解析 |

---

## 五、知识库索引

| 文件 | 内容 |
|------|------|
| `ZSK/ZT1.md` | v1.5+ 初始系统状态 |
| `ZSK/ZT2.md` | v1.6 控制稳定性强化 |
| `ZSK/ZT3.md` | **当前** — GLM 接入验证 + 系统状态 |
