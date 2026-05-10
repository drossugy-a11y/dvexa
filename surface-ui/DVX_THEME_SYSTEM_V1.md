# DVX Theme System v1

> 从"纯黑 UI"升级为"专业 AI Runtime / Governance OS 风格"

---

## 设计哲学

DVexa 不是消费级聊天产品，是 **AI Runtime Operating System** 的监控面板。

所以主题不能：
- 炫酷 neon / 赛博朋克
- 大面积玻璃拟态
- 纯黑 (#000000) 无层次
- Hacker green 终端风

应该：
- 低饱和，专业
- 长期监控不疲劳
- 信息层级清晰
- 系统级可信赖感

### 视觉气质

参考融合：
- **Claude Code** — 深色终端专业感
- **Linear** — 工程化 UI，克制动画
- **Vercel** — 干净排版，呼吸感
- **OpenAI internal** — 工具感，信息密度可控
- **Deep runtime systems (Datadog/Grafana)** — 状态色语义明确

---

## 色彩系统

### Background

```
--bg-primary:   #0F1115  (最外层背景)
--bg-secondary: #151922  (面板/卡片背景)
--bg-tertiary:  #1B2130  (hover/强调区域)
```

### Border

```
--border-primary: #252B36  (默认边框)
--border-soft:    #2F3744  (弱化边框)
```

### Text

```
--text-primary:   #E6EAF2  (主要文字)
--text-secondary: #9AA4B2  (次要文字)
--text-muted:     #6B7280  (辅助信息)
```

### Accent

```
--accent-primary: #7C9EFF  (主色调)
--accent-blue:    #38BDF8
--accent-purple:  #A78BFA
```

### Semantic

```
--success: #4ADE80
--warning: #FBBF24
--danger:  #F87171
--info:    #38BDF8
--optimization: #A78BFA
```

---

## Governance State Theme

### BALANCED
- Badge: blue-gray bg, soft blue border
- Border: `--accent-primary` at low opacity
- Glow: none

### STRICT
- Badge: amber-tinted bg, amber border  
- Border: `--warning` at low opacity
- Tint: subtle warm

### CONSERVATIVE
- Badge: cyan-gray bg, cyan border
- Border: cyan at low opacity

### EXPLORATION
- Badge: purple-tinted bg, purple border
- Border: `--accent-purple` at low opacity
- Glow: minimal purple shimmer

### ROLLBACK
- Badge: red-tinted bg, red border
- Border: `--danger` at low opacity

### OPTIMIZED
- Badge: emerald-tinted bg, emerald border
- Border: `--success` at low opacity

### DRIFT_DETECTED
- Badge: orange-red tinted bg, orange-red border
- Border: orange-red at low opacity

---

## Runtime Hierarchy

```
L0 — User / AI Messages
  └─ font-size: 14px
  └─ font-weight: 400 → 500 (headers)
  └─ spacing: 16px between bubbles
  └─ opacity: 1.0

L1 — Thinking / Reasoning
  └─ font-size: 13px
  └─ font-weight: 400
  └─ border: --border-primary
  └─ bg: --bg-tertiary
  └─ opacity: 0.9

L2 — Tool Execution
  └─ font-size: 12px
  └─ border: soft left accent
  └─ bg: --bg-secondary
  └─ opacity: 0.85

L3 — Governance Events
  └─ font-size: 11px
  └─ low-sat state color border
  └─ bg: --bg-secondary, lower opacity
  └─ opacity: 0.75

L4 — Optimization / Debug
  └─ font-size: 11px
  └─ text-muted borders
  └─ bg: faint
  └─ opacity: 0.6
```

---

## Animation Rules

Duration: 120ms–220ms
Easing: ease-out
No: bounce, spring, stagger, keyframe loops

Allowed:
- Pulse (only for streaming/WS)
- Shimmer (low opacity, only active state)
- Fade in (opacity 0→1, 150ms)
- Slide up (drawer, 200ms)
- Collapse/expand (max-height, 200ms)
- Hover bg transition (150ms)

---

## Accessibility

- All text ≥ 11px in UI
- Contrast ratio ≥ 4.5:1 for primary text
- Reduced motion: `prefers-reduced-motion`
- Touch targets ≥ 44px
- Scrollbar styling consistent
- Focus visible indicators

---

## Implementation Plan

### Step 1: Theme Tokens
- `tokens.ts` — raw design tokens
- `semantic.ts` — semantic color mapping
- `runtime-colors.ts` — runtime event colors
- `governance-states.ts` — governance state theme
- `tailwind-preset.ts` — Tailwind preset

### Step 2: Update Tailwind Config
- Use preset from theme system
- Add new surface/text/accent colors
- Add governance state colors

### Step 3: Refactor Components (One by One)
- Each component uses semantic tokens only
- No hardcoded colors

### Step 4: Add Runtime Feel
- Streaming pulse animation
- WS live indicator
- Minimial shimmer

### Step 5: Mobile Optimization
- Safe area support
- Keyboard avoidance
- Touch-friendly

### Step 6: Accessibility Pass
- Contrast check
- Reduced motion
- Focus indicators
