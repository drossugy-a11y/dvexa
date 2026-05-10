# DVX Runtime Layout Architecture

> Desktop 像 AI Runtime IDE，Mobile 像 AI Operating App

---

## Desktop Layout (≥768px)

```
┌─────────────────────────────────────────────────────────────┐
│  Navbar                                         [WS] [v2]  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Logo    Chat ✦    Capabilities    Governance    ...  │ │
│  └───────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─Main Column──────────────────────────────────────────┐   │
│  │                                                      │   │
│  │  ┌─L0: Messages (max-w-chat, centered)───────────┐  │   │
│  │  │                                                 │  │   │
│  │  │  MessageBubble (user)                           │  │   │
│  │  │  MessageBubble (assistant)                      │  │   │
│  │  │    └─ ThinkingBlock (collapsible)              │  │   │
│  │  │    └─ Response content                         │  │   │
│  │  │                                                 │  │   │
│  │  │  MessageBubble (user)                           │  │   │
│  │  │  MessageBubble (assistant)                      │  │   │
│  │  │    └─ ThinkingBlock (collapsible)              │  │   │
│  │  │    └─ RuntimeSummary (collapsed by default)    │  │   │
│  │  │       └─ TimelineEvent × N                     │  │   │
│  │  │                                                 │  │   │
│  │  └─────────────────────────────────────────────────┘  │   │
│  │                                                      │   │
│  │  ┌─ChatInput──────────────────────────────────────┐  │   │
│  │  │  [Textarea]                          [Send]    │  │   │
│  │  └─────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─Runtime Timeline (w-80, optional toggle)──────┐         │
│  │  StreamStatus ● Connected                      │         │
│  │                                                 │         │
│  │  ┌─Event────────────────────────────────────┐  │         │
│  │  │  🧠 Planning                              │  │         │
│  │  │   analyzing request...                    │  │         │
│  │  └───────────────────────────────────────────┘  │         │
│  │                                                 │         │
│  │  ┌─Event────────────────────────────────────┐  │         │
│  │  │  ⚖️ Governance  ● approved               │  │         │
│  │  │  BALANCED → allow                         │  │         │
│  │  └───────────────────────────────────────────┘  │         │
│  │                                                 │         │
│  │  ┌─Event────────────────────────────────────┐  │         │
│  │  │  🔧 Tool Execution  ● 3/5 done           │  │         │
│  │  │  [▼] 3 calls                              │  │         │
│  │  │    • llm_call ✓                           │  │         │
│  │  │    • code_exec ✓                          │  │         │
│  │  │    • http_call ⟳                          │  │         │
│  │  └───────────────────────────────────────────┘  │         │
│  │                                                 │         │
│  │  ┌─Event────────────────────────────────────┐  │         │
│  │  │  💾 Memory Hit                            │  │         │
│  │  │  recalled pattern: X                      │  │         │
│  │  └───────────────────────────────────────────┘  │         │
│  └─────────────────────────────────────────────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Column behavior

- **Main Column**: flex-1, centered, max-width 720px
- **Runtime Timeline**: w-80, padding to viewport edge
- **Desktop toggle**: Timeline can be hidden via hotkey / toggle
- **Navbar**: h-10, compact, WS indicator on right

---

## Mobile Layout (<768px)

```
┌──────────────────────────┐
│  Navbar          [WS]    │  h-10
├──────────────────────────┤
│                         │
│  Messages (scroll)      │  flex-1
│                         │  no side panels
│  ┌─Bubble────────────┐  │
│  │  user message     │  │
│  └───────────────────┘  │
│  ┌─Bubble────────────┐  │
│  │  assistant         │  │
│  │  ┌─Thinking─────┐  │  │
│  │  │ [▼] thinking │  │  │
│  │  └──────────────┘  │  │
│  │  response text     │  │
│  └───────────────────┘  │
│                         │
│  ┌─RuntimeStatus──────┐ │
│  │  ● 3 events  [Tap] │ │  floating indicator
│  └────────────────────┘ │
│                         │
├──────────────────────────┤
│  ChatInput (safe area)   │  sticky, keyboard-safe
└──────────────────────────┘

┌──────────────────────────┐
│  Runtime Drawer (overlay) │  ↑ swipe from bottom
│                         │  max 70vh
│  ┌─Event──────────────┐ │  scrollable
│  │  🧠 Planning       │ │
│  └────────────────────┘ │
│  ┌─Event──────────────┐ │
│  │  ⚖️ Governance     │ │
│  └────────────────────┘ │
│  ┌─Event──────────────┐ │
│  │  🔧 Tool x3 [▼]   │ │
│  └────────────────────┘ │
│                         │
│  [Drag down to close]   │
└──────────────────────────┘
```

### Mobile interaction rules

1. Runtime 完全默认隐藏
2. 浮动按钮显示事件计数 + 状态
3. 点击/上滑打开 runtime drawer
4. Drawer 可下滑关闭
5. 新事件到达时浮动按钮更新计数
6. 键盘打开时输入框固定在 keyboard 上方
7. 无水平滚动

---

## Complexity Layers Mapping

### Desktop

```
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│   L0 Chat    │  │   L1 Think   │  │ L2 Runtime   │
│              │  │              │  │              │
│ 可见         │  │ 折叠         │  │ 侧栏/折叠    │
│ 默认         │  │ 点击展开     │  │ 点击展开     │
│ 呼吸感       │  │ 阅读模式     │  │ 执行日志     │
└─────────────┘  └──────────────┘  └──────────────┘
```

### Mobile

```
┌──────────────────────────┐
│  L0 Chat (full screen)    │
├──────────────────────────┤
│  L1 Think (inline fold)   │
├──────────────────────────┤
│  L2 Runtime (bottom      │
│  drawer, overlay)         │
└──────────────────────────┘
```

---

## Responsive Breakpoints

| Breakpoint | Layout | Timeline | Input |
|-----------|--------|----------|-------|
| ≥768px (desktop) | main + side | side panel, visible | fixed bottom |
| <768px (mobile) | single column | drawer, hidden | keyboard-safe |

---

## z-Index Stacking

| Layer | z-index | Description |
|-------|---------|-------------|
| base | 0 | content |
| sticky | 50 | navbar, input |
| dropdown | 60 | menus, autocomplete |
| drawer-backdrop | 90 | overlay backdrop |
| drawer | 100 | mobile runtime drawer |
| modal | 200 | future dialogs |
| toast | 300 | notifications |
