# MCP 服务清单

已安装和激活的 MCP (Model Context Protocol) 服务器。

## 当前激活的服务

| 服务 | 用途 | 配置位置 |
|------|------|----------|
| **Playwright** | 浏览器自动化、E2E测试、截图 | `~/.claude/.mcp.json` |
| **Chrome DevTools** | Chrome 浏览器调试 | `~/.claude/.mcp.json` |

## Playwright MCP

```json
{
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest", "--browser", "chromium"]
}
```

**功能：**
- 打开网页并自动化操作
- 点击、输入、选择等表单操作
- 页面截图和 PDF 生成
- 网页内容抓取
- E2E 端到端测试

**安装位置：** `C:\Users\Deng\AppData\Local\ms-playwright\chromium-1223`

## 可用但未激活的服务

配置文件：`~/.claude/mcp-configs/mcp-servers.json`

| 服务 | 用途 | 状态 |
|------|------|------|
| GitHub | PR、Issue、仓库操作 | 需配置 Token |
| Context7 | 文档查询 | 可用 |
| Memory | 持久化记忆 | 可用 |
| Exa | 网页搜索 | 需配置 API Key |
| Supabase | 数据库操作 | 需配置 |
| Sequential Thinking | 链式推理 | 可用 |

## 相关链接

- [[Claude Code 工具]]
- [[项目技术栈]]
