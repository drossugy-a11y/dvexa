# DVX Surface V2 — Phase 1: Foundation Rewrite

> 目标：从"聊天网页"重构为"AI Runtime Operating Surface"

---

## 0. UI Philosophy

DVexa 不是 chatbot。DVexa 是 **Runtime OS**。

用户打开 Surface 不是在"发消息等回复"，而是在**观察一个运行时系统如何运行**。Chat 是交互入口，Timeline 是执行日志，每一行 event 都是系统状态的不可变记录。

设计语言：
- **系统感**：深色终端/仪表盘风格，信息密度可控
- **确定性**：所有状态变化有对应视觉反馈（WS 状态、执行进度、事件）
- **可观察性**：运行时的每个阶段都有专属的可视化表达
- **克制**：不炫技，动效只在必要时出现

---

## 1. Layout Architecture

### Desktop (≥768px)

```
┌──────────────────────────────────────────────────┐
│  Navbar (fixed top, h-12)                         │
├───────────┬──────────────────────┬────────────────┤
│           │                      │                │
│  Sidebar  │    Chat Messages     │   Runtime      │
│  (w-48)   │    (flex 1)          │   Timeline     │
│           │                      │   (w-80)       │
│  - 导航    │    Thread / Bubbles  │                │
│  - WS状态  │                      │   - Events     │
│  - 系统信息  │                      │   - Steps      │
│           │                      │   - Progress    │
│           ├──────────────────────┤                │
│           │  Input (fixed bottom) │                │
└───────────┴──────────────────────┴────────────────┘
```

### Mobile (<768px)

```
┌──────────────────────┐
│  Navbar (h-10)        │
├──────────────────────┤
│                      │
│  Chat Messages       │
│  (full width)        │
│                      │
│                      │
├──────────────────────┤
│  Input (safe area)   │
├──────────────────────┤
│  Runtime Drawer      │◄── bottom sheet / overlay
│  (tap to expand)     │     swipe to close
└──────────────────────┘
```

---

## 2. Component System

### New components to create:

| Component | Purpose | States |
|-----------|---------|--------|
| `RuntimeTimeline` | 右侧/抽屉式 timeline 容器 | open, closed, empty, streaming |
| `TimelineEvent` | 单条事件卡片 | running, completed, error, collapsed, expanded |
| `ToolCallCard` | 工具调用可视化 | pending, running, success, error, truncated |
| `ThinkingBlock` | 可折叠 thinking 块 | collapsed, expanded, streaming |
| `GovernanceBadge` | 治理状态标签 | stable, limited, frozen, degraded |
| `StreamStatus` | WebSocket 连接状态 | connected, reconnecting, disconnected, streaming |
| `ChatInput` | 固定底部输入区 | idle, disabled, recording, multi-line |
| `RuntimeDrawer` | 移动端底部抽屉 | hidden, peek, expanded |
| `MessageBubble` | 对话气泡 | user, assistant, error |
| `ScrollAnchor` | 自动滚动锚点 | auto-scroll, paused, manual |

### Refactored components:

| Component | Changes |
|-----------|---------|
| `ChatConsole` | Layout拆分 → 不再render所有内容，做layout编排 |
| `Navbar` | 移动端hamburger, WS状态指示器 |

---

## 3. Responsive Rules

### Breakpoints
- **Mobile**: <768px — 单列布局，runtime 抽屉
- **Desktop**: ≥768px — 三列布局

### Drawer Behavior
- Mobile: runtime 默认折叠，点击展开为 overlay drawer
- Drawer 高度：max 70vh
- Swipe down 关闭
- 有事件流时显示状态指示器 + 未读计数

### Overflow 处理
- Chat messages: 独立 scroll, 最大宽度 720px, 居中
- Timeline: 独立 scroll, 最大高度 calc(100vh - header - safe)
- 全局: overflow-x-hidden, 无水平滚动

### Touch Spacing
- 最小 touch target: 44px
- 移动端 padding: 16px
- 消息间距: 12px
- 事件卡片间距: 8px

---

## 4. Runtime Visualization

### Execution event color system

```
planning_started    → accent-blue    # 计划中
governance_decision → accent-purple  # 治理决策
tool_execution      → accent-green   # 工具运行中 → 完成/失败
memory_hit          → accent-yellow  # 记忆命中
execution_complete  → accent-green   # 执行完成
error               → accent-red     # 错误
```

### Event hierarchy
```
┌──────────────────────────────────┐
│  Execution Phase Header          │◄── 阶段分组
│  ┌─ TimelineEvent ────────────┐  │
│  │  governance_decision       │  │
│  │  strategy: BALANCED        │  │
│  │  status: approved          │  │
│  └────────────────────────────┘  │
│  ┌─ TimelineEvent ────────────┐  │
│  │  tool_execution            │  │
│  │  tool: llm_call            │  │
│  │  content: "analyzing..."   │  │
│  └────────────────────────────┘  │
│  ┌─ ToolCallCard ─────────────┐  │
│  │  [▼] 3 tool calls total    │  │◄── 可折叠
│  │  • llm_call ✓              │  │
│  │  • code_exec ✓             │  │
│  │  • http_call ⟳             │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

### WebSocket states
```
● Connected     → accent-green, pulsing when streaming
◐ Reconnecting  → accent-yellow, animated
○ Disconnected  → accent-red, error state
▶ Streaming     → accent-green, with data flow indicator
```

---

## 5. Animation Rules

Allowed:
- `opacity` 过渡 (150-200ms)
- `transform` 位移 (200-300ms, ease-out)
- 折叠/展开高度动画 (200ms)
- 状态颜色过渡 (150ms)
- Scroll 平滑

Forbidden:
- 弹跳动画
- 旋转加载
- 闪烁/频闪
- 页面切换动画
- 超过 300ms 的动效

---

## 6. Design Token System

创建 `surface-ui/src/theme/tokens.ts`:

```typescript
export const tokens = {
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  radius: { sm: 4, md: 6, lg: 8, xl: 12, full: 9999 },
  fontSize: { xs: 10, sm: 12, md: 13, lg: 15, xl: 18, xxl: 24 },
  zIndex: { base: 0, dropdown: 50, drawer: 100, modal: 200, toast: 300 },
  runtime: {
    planning: '#3b82f6',
    governance: '#8b5cf6',
    tool: '#22c55e',
    memory: '#eab308',
    complete: '#22c55e',
    error: '#ef4444',
  },
  ws: {
    connected: '#22c55e',
    reconnecting: '#eab308',
    disconnected: '#ef4444',
    streaming: '#22c55e',
  },
}
```

---

## 7. Mobile First Constraints

- Keyboard safe area: `env(safe-area-inset-bottom)` 确保输入框在键盘之上
- 无固定宽度面板（所有宽度用 flex / max-w 控制）
- Runtime 自动折叠（默认折叠，有事件时显示红点指示器）
- Scroll stabilization：新消息 auto-scroll，用户手动滚动时暂停
- Touch targets ≥ 44px
- No horizontal scroll

---

## 8. Future Expansion Slots（仅规划，不实现）

- **Capability Graph Explorer**: `/chat` 页面可扩展为 capability 可视化层
- **Replay Panel**: TimelineEvent 可扩展为时间轴 replay
- **Optimization Dashboard**: 治理指标面板
- **Memory Explorer**: 记忆检索可视化
- **Governance Inspector**: 治理决策详情
- **Artifact Workspace**: 执行产物预览

---

## Implementation Order (Phase 1 Only)

### Step 1: Design Token System
- `src/theme/tokens.ts` — all design constants
- `src/theme/index.ts` — re-export
- Update `tailwind.config.js` with new colors and spacing

### Step 2: New Component Scaffold
- `src/components/RuntimeTimeline.tsx`
- `src/components/TimelineEvent.tsx`
- `src/components/ToolCallCard.tsx`
- `src/components/ThinkingBlock.tsx`
- `src/components/StreamStatus.tsx`
- `src/components/ChatInput.tsx`
- `src/components/MessageBubble.tsx`
- `src/components/RuntimeDrawer.tsx`
- `src/components/ScrollAnchor.tsx`
- `src/components/GovernanceBadge.tsx`

### Step 3: Store Enhancement
- Add WebSocket state tracking to useChatStore
- Add scroll state (auto-scroll on/off)
- Add event compression logic (collapsible tool groups)

### Step 4: Page Rewrite
- Rewrite ChatConsole.tsx as layout orchestrator
- Integrate all new components
- Desktop: 3-column layout
- Mobile: single column + drawer

### Step 5: CSS & Integration
- Update `index.css` with runtime-specific styles
- Fix all responsive breakpoints
- Ensure mobile keyboard safe area
- Test all states

---

## File Change Summary

### New files (12):
- `src/theme/tokens.ts`
- `src/components/RuntimeTimeline.tsx`
- `src/components/TimelineEvent.tsx`
- `src/components/ToolCallCard.tsx`
- `src/components/ThinkingBlock.tsx`
- `src/components/StreamStatus.tsx`
- `src/components/ChatInput.tsx`
- `src/components/MessageBubble.tsx`
- `src/components/RuntimeDrawer.tsx`
- `src/components/ScrollAnchor.tsx`
- `src/components/GovernanceBadge.tsx`

### Modified files (5):
- `tailwind.config.js` — add new tokens
- `src/index.css` — add runtime styles
- `src/store/useChatStore.ts` — add ws state, scroll state
- `src/pages/ChatConsole.tsx` — full rewrite as orchestrator
- `src/components/Navbar.tsx` — add ws status, mobile hamburger

### Unchanged:
- All backend code
- All other pages (Dashboard, etc.)
- Governance/kernel/core
- Tests

---

## Verification Checklist

- [ ] Desktop: 3-column layout renders correctly
- [ ] Mobile (<768px): single column, no overlap, no horizontal scroll
- [ ] Mobile: runtime drawer opens/closes
- [ ] Mobile: keyboard does not cover input
- [ ] WS status shows connected/disconnected/reconnecting/streaming
- [ ] Timeline events render with correct colors
- [ ] Event compression: consecutive tool calls grouped
- [ ] Auto-scroll works; manual scroll pauses it
- [ ] Thinking block collapsible
- [ ] No console errors
- [ ] All existing chat tests pass
- [ ] Touch targets ≥ 44px on mobile
