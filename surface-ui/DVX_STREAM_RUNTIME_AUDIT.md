# DVX Stream Runtime Audit

> 全面审查 Chat Runtime 流式状态机问题

---

## 问题清单

### 1. Assistant 消息重复

**根因:** `useChatStore` 每 2s 轮询 `/chat/history`，每次轮询覆盖 `messages` 数组。当 backend 追加了 assistant message 后，前端立即读取到并显示为新的气泡，同时历史中可能已经有一条来自上一次轮询的同内容消息。

**影响:** 多轮对话后，assistant 消息呈指数级重复。

**文件:** `useChatStore.ts:72-77`

### 2. Thinking... 永不结束

**根因:** `ThinkingBlock` 的 `isRunning` 状态只依赖 `chatStore.isRunning`，而 `isRunning` 只在前端收到 `execution_complete` 事件时才重置。如果 WebSocket 断开或事件丢失，`isRunning` 永远为 `true`。

**文件:** `ChatConsole.tsx:48`, `useChatStore.ts:86-95`

### 3. Waiting for response... 卡住

**根因:** `ChatInput` 的 `disabled={isRunning}`。当 `isRunning` 因事件丢失而无法重置时，输入框永久锁定。

**文件:** `ChatConsole.tsx:84`, `ChatInput.tsx`

### 4. Streaming 状态无法 reset

**根因:** `wsStatus` 只在 WebSocket `onclose` 和 `stream_completed` 时转换到 `'idle'`。缺少以下路径：
- WebSocket 连接失败后重试超时
- 后端任务异常退出未发 completion
- 页面刷新/导航后的状态恢复

**文件:** `useChatStore.ts:64-67`

### 5. WebSocket 生命周期不完整

**根因:** `connectChatStream()` 只建立了基本连接，缺少：
- 心跳检测 (`ping/pong`)
- 断线重连
- 连接超时处理
- 陈旧 stream 清理

**文件:** `api/chat.ts:57-88`

### 6. 事件流缺少强制 finalize

**根因:** `chat_runtime.py` 的 `_run()` 函数缺少 `finally` 块来确保 `stream_completed` 事件始终发射。异常路径下 emitter 不会被清理。

**文件:** `chat_runtime.py:50-82`

### 7. 全局状态机缺失

**根因:** 没有统一的 RuntimeState 枚举。前端使用零散的 `isRunning` / `wsStatus` / `activeTaskId` 组合推断状态，导致竞态条件。

**文件:** `useChatStore.ts:10-28`

### 8. 消息聚合缺陷

**根因:** 后端每完成一个 task 才创建一条 assistant message，前端无法增量追加 token。所有内容一次性出现。

**文件:** `chat_runtime.py:73-79`

---

## 修复优先级

```
P0 — 状态卡死 (Thinking/Waiting/Input lock)
P1 — 消息重复 (Polling duplication)
P2 — 状态机 (RuntimeState)
P3 — WebSocket 生命周期
P4 — 增量 Streaming (future)
```

---

## 架构决策

### 状态机

```
IDLE → SUBMITTING → STREAMING → COMPLETED → IDLE
                        ↓
                     ERROR → IDLE
```

### 单消息聚合

每个 task 只生成一条 assistant message。前端收到 `message_chunk` 事件时更新该消息的 `content`。

### 强制 Cleanup

后端 `finally` 中确保：
1. `stream_completed` 事件发射
2. emitter 从 `_emitters` 移除
3. task 标记为完成
