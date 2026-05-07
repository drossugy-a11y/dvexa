"""MCP Tool — v1.6 控制稳定性强化

MCP 三不原则（强化版）：
  ✗ 不参与 planning — 不知道 task context / history
  ✗ 不参与 execution control — 不能影响 executor flow
  ✗ 不参与 kernel decision — 不返回结构化 decision

MCP 安全边界：
  1. 仅作为 stateless IO adapter：input → MCP → output(data only)
  2. 不访问 context / history / state / kernel state
  3. 不引用 executor / planner / kernel 任何模块
  4. 返回值是纯数据，不含控制信号
  5. MCP 永远不知道：task context, history, kernel state, execution plan

定位：纯 IO 工具层，不参与任何逻辑判断。
"""

import json
import subprocess
import threading
from pathlib import Path
from tools.base_tool import Tool


class MCPTool(Tool):
    """通用 MCP 协议适配器 — stateless IO only。

    通过 stdio JSON-RPC 2.0 与 MCP 服务器进程通信。
    配置见 config/mcp_servers.json（默认全部 disabled）。
    """

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or str(
            Path(__file__).parent.parent / "config" / "mcp_servers.json"
        )
        self._servers: dict[str, dict] = self._load_config()
        self._processes: dict[str, subprocess.Popen] = {}

    def _load_config(self) -> dict[str, dict]:
        try:
            with open(self.config_path) as f:
                config = json.load(f)
            return {name: srv for name, srv in config.items() if srv.get("enabled", False)}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def call(self, input_data) -> dict:
        if isinstance(input_data, str):
            try:
                data = json.loads(input_data)
            except json.JSONDecodeError:
                return {"content": f"[MCP] 输入必须是JSON格式: {input_data[:200]}"}
        else:
            data = input_data

        server_name = data.get("server", "")
        tool_name = data.get("tool", "")
        tool_args = data.get("input", {})

        if server_name not in self._servers:
            return {"content": f"[MCP] 服务器不可用: {server_name}（请先在 mcp_servers.json 中启用）"}

        proc = self._get_process(server_name)
        if not proc:
            return {"content": f"[MCP] 无法启动服务器: {server_name}"}

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": tool_args if isinstance(tool_args, dict) else {"input": str(tool_args)}},
        }

        try:
            result = self._send_request(proc, request)
            return {"content": json.dumps(result, ensure_ascii=False, indent=2)[:2000]}
        except Exception as e:
            return {"content": f"[MCP] 调用失败 {server_name}/{tool_name}: {str(e)}"}

    def _get_process(self, server_name: str) -> subprocess.Popen | None:
        if server_name in self._processes and self._processes[server_name].poll() is None:
            return self._processes[server_name]

        config = self._servers[server_name]
        try:
            proc = subprocess.Popen(
                [config["command"]] + config.get("args", []),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**config.get("env", {})},
                text=True,
            )
            self._processes[server_name] = proc
            return proc
        except FileNotFoundError:
            return None

    def _send_request(self, proc: subprocess.Popen, request: dict, timeout: float = 15.0) -> dict:
        line = json.dumps(request) + "\n"
        proc.stdin.write(line)
        proc.stdin.flush()

        result_lines = []
        event = threading.Event()

        def reader():
            for raw in proc.stdout:
                result_lines.append(raw)
                try:
                    json.loads(raw)
                    event.set()
                    return
                except json.JSONDecodeError:
                    continue

        t = threading.Thread(target=reader, daemon=True)
        t.start()

        if not event.wait(timeout=timeout):
            proc.kill()
            self._processes.pop(proc.pid, None)
            return {"error": f"请求超时 ({timeout}s)"}

        if result_lines:
            return json.loads(result_lines[-1])
        return {"error": "无响应"}

    def cleanup(self):
        for name, proc in self._processes.items():
            try:
                proc.kill()
                proc.wait(timeout=3)
            except Exception:
                pass
        self._processes.clear()
