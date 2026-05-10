"""Tests for Runtime Router v1 — 自适应运行时路由

路由决策委托给 SystemDirectiveEngine.classify_intent()。
测试验证 dispatch 决策正确性而非关键词匹配。
"""

from __future__ import annotations

from runtime.runtime_router import is_simple_conversation


class TestIsSimpleConversation:

    def test_empty_input(self):
        assert is_simple_conversation("") is True

    def test_greeting_short(self):
        assert is_simple_conversation("你好") is True
        assert is_simple_conversation("哈哈") is True
        assert is_simple_conversation("谢谢") is True
        assert is_simple_conversation("早上好") is True
        assert is_simple_conversation("ok") is True
        assert is_simple_conversation("yes") is True

    def test_simple_chat(self):
        assert is_simple_conversation("今天天气怎么样") is True
        assert is_simple_conversation("你叫什么名字") is True
        assert is_simple_conversation("推荐一本书") is True

    def test_code_request_is_task(self):
        """含 TASK 关键词 → SDE 返回 task 模式 → 走 runtime。

        注意：分类决策完全委托 SDE，Router 不维护独立关键词。
        """
        assert is_simple_conversation("实现一个量化回测系统") is False
        assert is_simple_conversation("重构我的项目") is False

    def test_english_task_keywords(self):
        assert is_simple_conversation("create a new project") is False
        assert is_simple_conversation("implement login system") is False
        assert is_simple_conversation("build a web app") is False
        assert is_simple_conversation("refactor this code") is False

    def test_mixed_chat_and_task(self):
        """含任务关键词的消息走 runtime。"""
        assert is_simple_conversation("你好，帮我分析一下这个项目") is False
        assert is_simple_conversation("谢谢，帮我实现一个功能") is False

    def test_long_question_still_chat(self):
        """长纯提问仍然是 chat 模式。"""
        long_q = "请问你对人工智能在医疗领域的应用有什么看法？"
        assert is_simple_conversation(long_q) is True

    def test_analyze_triggers_runtime(self):
        """分析类关键词触发 runtime。"""
        assert is_simple_conversation("分析这个项目结构") is False

    def test_bug_fix_triggers_runtime(self):
        """修复类关键词触发 runtime。"""
        assert is_simple_conversation("修复这个bug") is False

    def test_run_triggers_runtime(self):
        """执行类关键词触发 runtime。"""
        assert is_simple_conversation("运行测试") is False
