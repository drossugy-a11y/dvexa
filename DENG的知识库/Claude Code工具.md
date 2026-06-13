# Claude Code 可用工具

Claude Code 内置工具和能力清单。

## 核心工具

| 工具 | 功能 | 使用场景 |
|------|------|----------|
| **Read** | 读取文件 | 查看代码、配置、文档 |
| **Write** | 写入文件 | 创建新文件 |
| **Edit** | 编辑文件 | 修改现有代码 |
| **Bash** | 执行命令 | 运行脚本、安装依赖、Git 操作 |
| **Grep** | 搜索内容 | 查找代码中的关键词 |
| **Glob** | 文件匹配 | 按模式查找文件 |
| **Agent** | 子代理 | 委派复杂任务给专门代理 |

## MCP 工具（需配置）

| 工具 | 功能 | 来源 |
|------|------|------|
| **Playwright** | 浏览器自动化 | MCP 服务 |
| **GitHub** | GitHub 操作 | MCP 服务 |
| **Context7** | 文档查询 | MCP 服务 |

## 专业代理类型

可通过 `Agent` 工具调用的专业代理：

| 代理 | 用途 |
|------|------|
| `code-reviewer` | 代码审查 |
| `python-reviewer` | Python 代码审查 |
| `react-reviewer` | React 代码审查 |
| `security-reviewer` | 安全审查 |
| `build-error-resolver` | 构建错误修复 |
| `planner` | 实现规划 |
| `architect` | 架构设计 |
| `tdd-guide` | 测试驱动开发 |
| `e2e-runner` | E2E 测试 |
| `performance-optimizer` | 性能优化 |

## Slash 命令

| 命令 | 功能 |
|------|------|
| `/tdd` | 测试驱动开发工作流 |
| `/plan` | 实现规划 |
| `/e2e` | 生成并运行 E2E 测试 |
| `/code-review` | 代码审查 |
| `/build-fix` | 修复构建错误 |
| `/learn` | 从会话中提取模式 |

## 相关链接

- [[MCP服务清单]]
- [[项目技术栈]]
