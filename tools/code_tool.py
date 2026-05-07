import sys
import io
from tools.base_tool import Tool


class CodeExecutorTool(Tool):
    def call(self, input_data) -> dict:
        code = input_data.strip()
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        try:
            exec(code, {"__builtins__": __builtins__})
            output = buffer.getvalue()
            return {"content": output.strip() if output else "代码执行完成（无输出）"}
        except Exception as e:
            return {"content": f"代码执行错误: {str(e)}"}
        finally:
            sys.stdout = old_stdout
