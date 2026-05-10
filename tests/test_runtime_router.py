"""Tests for Runtime Router v1 — 自适应运行时路由"""

from __future__ import annotations

from runtime.runtime_router import is_simple_conversation, _TASK_KEYWORDS


class TestIsSimpleConversation:

    def test_empty_input(self):
        assert is_simple_conversation("") is True
        assert is_simple_conversation("  ") is True

    def test_greeting_short(self):
        assert is_simple_conversation("你好") is True
        assert is_simple_conversation("哈哈") is True
        assert is_simple_conversation("谢谢") is True
        assert is_simple_conversation("早上好") is True
        assert is_simple_conversation("ok") is True
        assert is_simple_conversation("yes") is True

    def test_short_chat(self):
        assert is_simple_conversation("今天天气怎么样") is True
        assert is_simple_conversation("你叫什么名字") is True
        assert is_simple_conversation("推荐一本书") is True
        # "帮我" 含任务关键词 → 走 runtime
        assert is_simple_conversation("帮我推荐一本书") is False

    def test_task_keywords_trigger_runtime(self):
        for kw in _TASK_KEYWORDS:
            msg = f"帮我{kw}一个系统"
            assert is_simple_conversation(msg) is False, \
                f"should be False for: {msg}"

    def test_code_request_is_task(self):
        assert is_simple_conversation("帮我写一个Python脚本") is False
        assert is_simple_conversation("实现一个量化回测系统") is False
        assert is_simple_conversation("分析这个仓库的代码") is False
        assert is_simple_conversation("重构我的项目") is False

    def test_english_task_keywords(self):
        assert is_simple_conversation("create a new project") is False
        assert is_simple_conversation("implement login system") is False
        assert is_simple_conversation("build a web app") is False
        assert is_simple_conversation("refactor this code") is False

    def test_mixed_chat_and_task(self):
        """含任务关键词的长消息走 runtime。"""
        assert is_simple_conversation("你好，帮我分析一下这个项目") is False
        assert is_simple_conversation("谢谢，但是我想让你帮我实现一个功能") is False

    def test_pure_question_long(self):
        """长纯提问不走 runtime。"""
        long_q = "请问你对人工智能在医疗领域的应用有什么看法？"
        assert is_simple_conversation(long_q) is True

    def test_task_keyword_list_nonempty(self):
        assert len(_TASK_KEYWORDS) > 5
