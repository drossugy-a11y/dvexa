import requests
from tools.base_tool import Tool


class HTTPTool(Tool):
    def call(self, input_data) -> dict:
        try:
            resp = requests.get(input_data, timeout=5)
            return {"content": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"content": f"HTTP请求失败: {str(e)}"}
