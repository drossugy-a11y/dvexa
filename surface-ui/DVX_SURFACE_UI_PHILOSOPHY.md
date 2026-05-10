# DVX Surface UI Philosophy

> 什么是"AI Runtime Operating Surface"？

---

## 核心命题

DVexa 不是一个 chatbot。

用户打开 Surface 的目标不是"发一条消息等回复"。

目标是：
> **观察智能体系统如何思考、决策、执行。**

这是一个根本性的设计前提差异：

| | Chatbot | Runtime OS |
|---|---|---|
| 用户身份 | 对话者 | 操作员/观察者 |
| 交互模式 | 会话 | 控制+观察 |
| 信息结构 | 线性消息流 | 层次化执行日志 |
| 状态表达 | 打字指示器 | 完整的 WS/执行/治理状态 |
| 复杂度 | 扁平 | 渐进式（L0-L4） |
| 纵深 | 无 | timeline/replay/trace |

---

## 渐进式复杂度

这是 DVX Surface 最核心的设计原则：

```
L0 — User Layer（始终可见）
  └─ 聊天消息、输入框、简洁状态

L1 — Thinking Layer（点击展开）
  └─ thinking block、进度、推理摘要

L2 — Runtime Layer（默认折叠）
  └─ execution timeline、tool events、governance actions

L3 — Governance Layer（未来）
  └─ optimization、strategy、policy、drift

L4 — Debug Layer（未来）
  └─ raw trace、websocket、event replay
```

每一层都是前一层的基础。用户从 L0 开始，根据需要向下深入。

**不把 runtime 信息默认暴露给普通用户。**

---

## 三源融合

### 70% Claude — 极简与专注

- 干净的主内容区
- 克制的信息密度
- thinking block 可折叠
- 自然的呼吸感
- 长文本阅读节奏

### 20% Manus — Runtime Timeline

- 执行步骤可视化
- 工具调用链
- 任务进度追踪
- Agent 状态表达

### 10% LangSmith — Observability

- Trace 语义
- 事件时间线
- 执行详情下钻

---

## 视觉语言

### 不是 Dashboard

Dashboard 设计适合监控指标（数字、图表、面板）。

但用户使用 DVexa 不是在"看仪表盘"。

他们是在：
- **阅读**（agent 的思考过程）
- **观察**（系统如何决策）
- **理解**（执行链路）

所以视觉语言是：
- 以文本和卡片为主体
- 信息密度由用户控制（展开/折叠）
- 颜色只用于语义和状态
- 动效克制且有用

### 系统感

- 深色主题不是装饰，是终端/控制台原型的延续
- 间距和呼吸感传达精确性
- 状态变化有可预测的视觉反馈
- 每个 UI 元素回答问题："我现在应该看哪里？"

---

## 移动端哲学

移动端不是"PC 的缩小版"。

移动端意味着：
- **Chat-first**：聊天是主要界面
- **Runtime hidden**：执行细节默认隐藏
- **Gesture-native**：swipe、tap、pull
- **Safe area**：键盘适配是必需的，不是可选的

正确隐喻：
- Desktop = AI Runtime IDE
- Mobile = AI Operating App

---

## 设计红线

| ✅ 应该做 | ❌ 禁止做 |
|-----------|----------|
| 渐进式信息揭示 | 一次性暴露所有 runtime 信息 |
| 折叠/展开 | 固定面板 |
| 语义颜色 | 装饰颜色 |
| 克制动效 | 炫转动效 |
| 文本优先 | 图表优先 |
| 消息呼吸感 | 紧凑 dashboard |
| 移动端 gesture | 移动端缩小 PC 布局 |
