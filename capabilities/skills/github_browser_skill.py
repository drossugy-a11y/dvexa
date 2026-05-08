"""GitHub Browser Skill — GitHub 仓库浏览能力

stateless: 每次请求独立
no decision: 只返回数据，不做判断
no self modify: 只读浏览
"""

from tools.base_tool import Tool


class GitHubBrowserSkill(Tool):
    """GitHub 浏览技能 — 8 种仓库浏览操作。

    输入：{"action": "结构|readme|文件树|文件|依赖|描述|模块|统计", "repo": "owner/repo", ...}
    """

    def __init__(self, gh_tool):
        self._gh = gh_tool

    def call(self, input_data) -> dict:
        if isinstance(input_data, str):
            repo = input_data.strip()
            return self._gh.call({"action": "repo_info", "repo": repo})

        action = input_data.get("action", "")
        repo = input_data.get("repo", "")
        path = input_data.get("path", "")
        branch = input_data.get("branch", "main")

        if not repo:
            return {"status": "error", "data": None, "error": "缺少 repo 参数 (格式: owner/repo)"}

        action_map = {
            "结构": ("contents", {"action": "contents", "repo": repo, "path": path}),
            "readme": ("readme", {"action": "readme", "repo": repo}),
            "文件树": ("tree", {"action": "tree", "repo": repo, "branch": branch}),
            "文件": ("file", {"action": "file", "repo": repo, "path": path}),
            "依赖": ("deps", {"action": "tree", "repo": repo, "branch": branch}),
            "描述": ("description", {"action": "repo_info", "repo": repo}),
            "模块": ("modules", {"action": "tree", "repo": repo, "branch": branch}),
            "统计": ("stats", {"action": "languages", "repo": repo}),
        }

        mapped = action_map.get(action)
        if not mapped:
            return {"status": "error", "data": None,
                    "error": f"不支持的动作: {action}，可选: {list(action_map.keys())}"}

        action_type, gh_input = mapped
        if action_type == "deps":
            return self._analyze_deps(repo, branch)
        if action_type == "modules":
            return self._analyze_modules(repo, branch)

        return self._gh.call(gh_input)

    def _analyze_deps(self, repo: str, branch: str) -> dict:
        """分析依赖文件。"""
        result = self._gh.call({"action": "tree", "repo": repo, "branch": branch})
        if result.get("status") != "ok":
            return result

        deps_files = []
        files = result["data"]["files"]
        dep_patterns = ["requirements.txt", "pyproject.toml", "setup.py",
                        "setup.cfg", "Pipfile", "poetry.lock", "package.json",
                        "go.mod", "Cargo.toml"]

        for f in files:
            name = f["path"].rsplit("/", 1)[-1] if "/" in f["path"] else f["path"]
            if name in dep_patterns:
                content_result = self._gh.call({"action": "file", "repo": repo, "path": f["path"]})
                deps_files.append({
                    "path": f["path"],
                    "name": name,
                    "content": content_result.get("data", {}).get("content", "") if content_result.get("status") == "ok" else "",
                })

        return {"status": "ok", "data": deps_files}

    def _analyze_modules(self, repo: str, branch: str) -> dict:
        """分析 Python 模块结构。"""
        result = self._gh.call({"action": "tree", "repo": repo, "branch": branch})
        if result.get("status") != "ok":
            return result

        files = result["data"]["files"]
        modules = []
        for f in files:
            if f["path"].endswith("__init__.py"):
                pkg_dir = f["path"].rsplit("/", 1)[0] if "/" in f["path"] else "."
                modules.append({"package": pkg_dir, "type": "package"})
            elif f["path"].endswith(".py") and "/" in f["path"]:
                parts = f["path"].split("/")
                if len(parts) >= 2:
                    mod_name = parts[-1].replace(".py", "")
                    pkg = "/".join(parts[:-1])
                    modules.append({"package": pkg, "module": mod_name, "file": f["path"], "type": "module"})

        return {"status": "ok", "data": {"module_count": len(modules), "modules": modules}}
