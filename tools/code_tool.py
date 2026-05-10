"""Code Execution Tool — 沙箱化 Python 执行"""

import sys
import io
import logging
from tools.base_tool import Tool

logger = logging.getLogger("dvexa.tools.code")

# 危险内置函数/模块名黑名单
_DANGEROUS_BUILTINS = {
    "__import__", "eval", "exec", "compile",
    "open", "input", "breakpoint",
    "memoryview", "bytearray",
}

# 安全的 __builtins__ — 只允许纯计算函数
_SAFE_BUILTINS: dict[str, object] = {
    "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
    "chr": chr, "complex": complex, "dict": dict, "divmod": divmod,
    "enumerate": enumerate, "filter": filter, "float": float,
    "format": format, "frozenset": frozenset, "hash": hash, "hex": hex,
    "int": int, "isinstance": isinstance, "issubclass": issubclass,
    "iter": iter, "len": len, "list": list, "map": map, "max": max,
    "min": min, "next": next, "oct": oct, "ord": ord, "pow": pow,
    "print": print, "range": range, "repr": repr, "reversed": reversed,
    "round": round, "set": set, "slice": slice, "sorted": sorted,
    "str": str, "sum": sum, "tuple": tuple, "type": type, "zip": zip,
    "True": True, "False": False, "None": None,
}


class CodeExecutorTool(Tool):
    def call(self, input_data) -> dict:
        code = input_data.strip()
        if not code:
            return {"content": "代码为空"}

        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        try:
            # 沙箱 exec: 过滤 __builtins__ + 限制全局命名空间
            safe_globals: dict = {
                "__builtins__": _SAFE_BUILTINS,
            }
            exec(code, safe_globals)
            output = buffer.getvalue()
            return {"content": output.strip() if output else "代码执行完成（无输出）"}
        except SyntaxError as e:
            logger.warning("Syntax error in user code: %s", e)
            return {"content": f"语法错误: {e}"}
        except Exception as e:
            logger.warning("Runtime error in user code: %s", e)
            return {"content": f"代码执行错误: {str(e)}"}
        finally:
            sys.stdout = old_stdout
