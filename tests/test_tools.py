import pytest
from tools.base_tool import Tool


class TestToolBase:
    def test_tool_base_raises_not_implemented(self):
        tool = Tool()
        with pytest.raises(NotImplementedError):
            tool.call("test")


class TestCodeExecutorTool:
    @pytest.fixture
    def tool(self):
        from tools.code_tool import CodeExecutorTool
        return CodeExecutorTool()

    def test_execute_simple_code(self, tool):
        result = tool.call("print('hello')")
        assert "hello" in str(result)

    def test_execute_math(self, tool):
        result = tool.call("print(1 + 2)")
        assert "3" in str(result)

    def test_error_handling(self, tool):
        result = tool.call("raise ValueError('test error')")
        assert "错误" in str(result) or "Error" in str(result)


class TestHTTPTool:
    @pytest.fixture
    def tool(self):
        from tools.http_tool import HTTPTool
        return HTTPTool()

    def test_invalid_url(self, tool):
        result = tool.call("not-a-url")
        assert "失败" in str(result) or "Failed" in str(result)
