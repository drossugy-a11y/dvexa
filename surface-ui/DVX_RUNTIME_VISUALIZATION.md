# Runtime Visualization & Mobile Interaction Rules

---

## 1. Runtime Event Color System

### Event type → color mapping

```
planning_started       → #3b82f6 (blue)    — 系统在思考/规划
governance_decision    → #8b5cf6 (purple)  — 治理层决策
tool_execution         → #22c55e (green)   — 工具执行中
memory_hit             → #eab308 (yellow)  — 记忆/模式命中
execution_complete     → #22c55e (green)   — 执行完成
error                  → #ef4444 (red)     — 错误
```

### Status → visual mapping

```
running     → pulsing dot, muted bg
completed   → solid dot, normal bg
error       → red dot, red-tinted bg
approved    → green check, green-tinted bg
blocked     → red x, red-tinted bg
```

### No decorative colors

所有颜色必须表达语义。不使用颜色做装饰。

---

## 2. Event Compression Rules

### When to compress

连续相同类型的 tool_execution 事件自动合并为一个组：

```
Before (flat):
  🔧 tool_execution   llm_call       → analyzing
  🔧 tool_execution   code_exec      → running test
  🔧 tool_execution   llm_call       → summarizing

After (grouped):
  🔧 Tool Execution (3 calls)
  [▼] Show details
    • llm_call    ✓  analyzing
    • code_exec   ✓  running test
    • llm_call    ✓  summarizing
```

### Compression threshold
- 连续 2+ 个 tool_execution → 自动分组
- 组内最多展示前 5 条，其余折叠为 "+N more"
- 组状态：all completed → ✓ | any error → ✗ | any running → ⟳

### Content truncation
- 单条 content 超过 120 字符 → 截断 + "..."
- 完整内容通过展开查看

---

## 3. WebSocket Status Visualization

```
● Connected      → #22c55e, steady dot    — 正常连接
◐ Reconnecting   → #eab308, pulsing dot   — 正在重连
○ Disconnected   → #ef4444, dim dot       — 断开
▶ Streaming      → #22c55e, animated      — 正在接收事件
```

WS 状态在两个位置显示：
1. **Navbar** — 全局状态指示器（小圆点）
2. **Timeline header** — 详细状态（桌面 side panel / 移动端 drawer header）

---

## 4. Mobile Interaction Rules

### Touch targets
- 所有可交互元素最小 44px
- 按钮、折叠/展开、链接
- 卡片内部间距保证 touch 区域

### Gestures
| Gesture | Action |
|---------|--------|
| Tap runtime indicator | Open runtime drawer |
| Swipe down on drawer | Close drawer |
| Swipe up from bottom | Open drawer (if closed) |
| Tap thinking block header | Toggle expand/collapse |
| Tap tool group header | Toggle expand/collapse |

### Keyboard handling
- Input 自动跟随键盘（`env(safe-area-inset-bottom)`）
- 键盘打开时不做 layout shift（输入框 fixed）
- 发送后不清除输入框内容直到确认

### Runtime drawer
- 默认隐藏
- 浮动按钮：右下角，圆形，显示事件计数
- 打开方式：点击浮动按钮 | 从底部上滑
- 关闭方式：下滑 | 点击 backdrop | 点击关闭按钮
- 最大高度：70vh
- 圆角顶部，有 drag handle

### No horizontal scroll
- 所有内容自适应宽度
- 长文本自动换行
- 代码块横向可滚动（仅代码块）

---

## 5. Animation Spec

### Allowed
| Property | Duration | Easing | Use |
|----------|----------|--------|-----|
| opacity | 150ms | ease | 出现/消失 |
| transform: translateY | 200ms | ease-out | drawer slide |
| height (max-height) | 200ms | ease | collapse/expand |
| background-color | 150ms | ease | 状态变化 |
| box-shadow | 150ms | ease | hover |

### Forbidden
- Keyframe animations (spin, bounce, pulse) — 除了 WS reconnecting pulse
- Page transitions
- Stagger/sequential animation
- Spring physics

---

## 6. Empty & Loading States

### Empty chat
```
┌─────────────────────────────┐
│                             │
│         [icon]              │
│     DVX Surface             │
│  Enter a task to begin      │
│                             │
│    ┌─────────────────┐      │
│    │  Type something   │    │
│    └─────────────────┘      │
│                             │
└─────────────────────────────┘
```
- Centered, minimal
- 只有一个提示和输入框

### Loading / Thinking
```
┌─ThinkingBlock──────────────┐
│ [▼] Thinking...  ● ⟳       │
│  ┌────────────────────────┐│
│  │ Analyzing request...   ││
│  │ Formulating plan...    ││
│  │ Evaluating approach... ││
│  └────────────────────────┘│
└────────────────────────────┘
```
- 折叠状态时只显示 "Thinking..." + spinner
- 展开后显示推理进度

### Error state
- 消息气泡内：红色边框，错误图标
- 输入区上方：toast 式错误条
- Runtime timeline：红色事件卡片
