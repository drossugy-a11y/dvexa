"""GitHub CLI Tool — GitHub API 只读访问工具

stateless: 每次调用独立
no decision: 只返回数据，不做判断
no self modify: 只读操作

通过 GitHub REST API 直接访问，无需 gh CLI 认证。
"""

import base64
import os
import requests
from tools.base_tool import Tool


GITHUB_API = "https://api.github.com"


class GitHubCLITool(Tool):
    """GitHub 仓库只读访问工具。

    通过 GitHub REST API 获取仓库信息，无需认证（公开仓库）。
    输入格式：{"action": "...", "repo": "owner/repo", ...}
    """

    def __init__(self, token: str | None = None):
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

    def call(self, input_data) -> dict:
        """执行 GitHub API 调用。"""
        if isinstance(input_data, str):
            return _error("输入必须为 dict 格式")

        action = input_data.get("action", "")
        repo = input_data.get("repo", "")
        path = input_data.get("path", "")
        branch = input_data.get("branch", "main")

        if not repo:
            return _error("缺少 repo 参数 (格式: owner/repo)")

        actions = {
            "repo_info": self._repo_info,
            "contents": self._contents,
            "tree": self._tree,
            "file": self._file,
            "readme": self._readme,
            "languages": self._languages,
        }

        handler = actions.get(action)
        if not handler:
            return _error(f"不支持的操作: {action}")

        return handler(repo, path, branch)

    def _get(self, url: str) -> dict:
        """GET 请求包装。"""
        try:
            resp = requests.get(url, headers=self._headers, timeout=15)
            if resp.status_code == 403:
                return _error("API 限流，请稍后重试或设置 GITHUB_TOKEN")
            if resp.status_code == 404:
                return _error("资源不存在")
            if resp.status_code != 200:
                return _error(f"API 返回 {resp.status_code}")
            return {"status": "ok", "data": resp.json()}
        except requests.RequestException as e:
            return _error(f"请求失败: {e}")

    def _repo_info(self, repo: str, path: str = "", branch: str = "") -> dict:
        """获取仓库元信息。"""
        result = self._get(f"{GITHUB_API}/repos/{repo}")
        if result["status"] != "ok":
            return result
        d = result["data"]
        return {
            "status": "ok",
            "data": {
                "name": d.get("name", ""),
                "description": d.get("description", ""),
                "language": d.get("language", ""),
                "stars": d.get("stargazers_count", 0),
                "license": d.get("license", {}).get("spdx_id", "") if d.get("license") else "",
                "disk_usage_kb": d.get("size", 0),
                "url": d.get("html_url", f"https://github.com/{repo}"),
            },
        }

    def _contents(self, repo: str, path: str = "", branch: str = "") -> dict:
        """列出目录内容。"""
        url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
        if branch:
            url += f"?ref={branch}"
        result = self._get(url)
        if result["status"] != "ok":
            return result
        items = result["data"]
        if isinstance(items, dict):
            items = [items]
        return {
            "status": "ok",
            "data": [
                {"name": i.get("name", ""), "type": i.get("type", ""),
                 "path": i.get("path", ""), "size": i.get("size", 0)}
                for i in items
            ],
        }

    def _tree(self, repo: str, path: str = "", branch: str = "") -> dict:
        """获取文件树。"""
        urls = [
            f"{GITHUB_API}/repos/{repo}/git/trees/{branch}?recursive=1",
            f"{GITHUB_API}/repos/{repo}/git/trees/main?recursive=1",
            f"{GITHUB_API}/repos/{repo}/git/trees/master?recursive=1",
        ]
        data = None
        for url in urls:
            result = self._get(url)
            if result["status"] == "ok":
                data = result["data"]
                break

        if not data:
            return _error("无法获取文件树")

        tree = data.get("tree", [])
        files = [n for n in tree if n.get("type") == "blob"]
        dirs = [n for n in tree if n.get("type") == "tree"]
        return {
            "status": "ok",
            "data": {
                "file_count": len(files),
                "dir_count": len(dirs),
                "files": [{"path": f["path"], "size": f.get("size", 0), "mode": f.get("mode", "")} for f in files],
                "dirs": [d["path"] for d in dirs],
            },
        }

    def _file(self, repo: str, path: str = "", branch: str = "") -> dict:
        """获取文件内容。"""
        if not path:
            return _error("缺少 path 参数")
        url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
        result = self._get(url)
        if result["status"] != "ok":
            return result
        d = result["data"]
        content_b64 = d.get("content", "")
        content = ""
        if content_b64:
            try:
                content = base64.b64decode(content_b64).decode("utf-8")
            except (base64.binascii.Error, UnicodeDecodeError):
                content = "[二进制文件]"
        return {
            "status": "ok",
            "data": {"path": d.get("path", path), "size": d.get("size", 0),
                     "content": content, "encoding": d.get("encoding", "")},
        }

    def _readme(self, repo: str, path: str = "", branch: str = "") -> dict:
        """获取 README。"""
        # 直接从 API 获取 README（base64 编码）
        url = f"{GITHUB_API}/repos/{repo}/readme"
        result = self._get(url)
        if result["status"] != "ok":
            return result
        d = result["data"]
        content_b64 = d.get("content", "")
        content = ""
        if content_b64:
            try:
                content = base64.b64decode(content_b64).decode("utf-8")
            except (base64.binascii.Error, UnicodeDecodeError):
                content = "[读取失败]"
        return {"status": "ok", "data": {"readme": content[:2000]}}

    def _languages(self, repo: str, path: str = "", branch: str = "") -> dict:
        """获取语言统计。"""
        result = self._get(f"{GITHUB_API}/repos/{repo}/languages")
        if result["status"] != "ok":
            return result
        data = result["data"]
        total = sum(data.values())
        languages = sorted(
            [{"name": k, "bytes": v, "percent": round(v / total * 100, 1)} for k, v in data.items()],
            key=lambda x: x["bytes"], reverse=True,
        )
        return {"status": "ok", "data": {"total_bytes": total, "languages": languages}}


def _error(message: str) -> dict:
    return {"status": "error", "data": None, "error": message}
