"""Browser Use Tool — 浏览器自动化能力（基于 browser-use）

stateless: 每次调用独立
no decision: 只返回浏览结果，不做判断
no self modify: 只读操作
"""

import asyncio
from tools.base_tool import Tool

try:
    from browser_use import Agent, Browser
    HAS_BROWSER_USE = True
except ImportError:
    HAS_BROWSER_USE = False


class BrowserUseTool(Tool):
    """浏览器自动化工具 — 通过 browser-use 执行网页浏览。

    输入格式：{"action": "navigate", "url": "https://...", "task": "..."}
    action 支持：
      - navigate: 导航到 URL 并获取页面内容
      - search: 在网页上执行特定搜索/浏览任务
    """

    def __init__(self, llm=None):
        self._llm = llm

    def call(self, input_data) -> dict:
        if not HAS_BROWSER_USE:
            return {"content": "错误: browser-use 未安装 (pip install browser-use playwright)"}

        if isinstance(input_data, str):
            return _err("输入必须为 dict 格式")

        action = input_data.get("action", "navigate")
        url = input_data.get("url", "")
        task = input_data.get("task", "")

        if action == "navigate":
            if not url:
                return _err("缺少 url 参数")
            return asyncio.run(self._navigate(url))
        elif action == "search":
            if not task:
                return _err("缺少 task 参数")
            return asyncio.run(self._search(task))
        return _err(f"不支持的操作: {action}")

    async def _navigate(self, url: str) -> dict:
        """导航到网页并提取内容。"""
        browser = Browser()
        try:
            page = await browser.new_page()
            await page.goto(url, timeout=30000)
            title = await page.title()
            content = await page.evaluate("document.body.innerText")
            truncated = content[:5000] if len(content) > 5000 else content
            return {
                "status": "ok",
                "data": {
                    "url": url,
                    "title": title,
                    "content_length": len(content),
                    "content": truncated,
                },
            }
        except Exception as e:
            return _err(f"浏览失败: {str(e)}")
        finally:
            await browser.close()

    async def _search(self, task: str) -> dict:
        """使用 AI Agent 执行网页任务。"""
        if not self._llm:
            return _err("搜索任务需要配置 LLM")
        browser = Browser()
        try:
            agent = Agent(task=task, llm=self._llm, browser=browser)
            result = await agent.run()
            return {
                "status": "ok",
                "data": {"result": str(result)},
            }
        except Exception as e:
            return _err(f"搜索任务失败: {str(e)}")
        finally:
            await browser.close()


def _err(msg: str) -> dict:
    return {"status": "error", "data": None, "error": msg}
