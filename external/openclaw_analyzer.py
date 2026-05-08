"""OpenClaw Analyzer — 外部项目分析与吞并建议生成

输入：GitHub 仓库 URL
输出：结构化吞并分析报告

红线：
  - 不自动 merge
  - 不自动 register
  - 不写入 router
  - 不修改 governance
  - 纯分析，零副作用
"""

from __future__ import annotations
from datetime import datetime


class OpenClawAnalyzer:
    """OpenClaw 项目分析器 — 分析外部项目并生成吞并建议。

    使用 GitHubCLITool 获取远程仓库数据，纯只读操作。
    所有输出为结构化 dict，由人工审批后实施。
    """

    def __init__(self, gh_tool):
        self._gh = gh_tool

    def analyze(self, repo_url: str, branch: str = "main") -> dict:
        """完整分析外部项目。"""
        owner, repo = self._parse_repo_url(repo_url)
        meta = {"repo_url": repo_url, "full_name": f"{owner}/{repo}", "analyzed_at": datetime.now().isoformat()}

        project_summary = self._build_project_summary(owner, repo)
        if project_summary.get("status") == "error":
            return {"meta": meta, "error": project_summary.get("error", "分析失败")}

        tree = self._get_tree(owner, repo, branch)
        architecture = self._analyze_architecture(tree, owner, repo, branch)
        useful_modules = self._find_useful_modules(tree)
        candidate_skills = self._extract_candidate_skills(useful_modules, architecture)
        conflicts = self._detect_conflicts(candidate_skills, architecture)
        risk_analysis = self._analyze_risks(project_summary, architecture)
        merge_suggestions = self._generate_merge_suggestions(useful_modules, conflicts, risk_analysis)
        recommended_strategy = self._build_strategy(merge_suggestions, useful_modules)

        return {
            "meta": meta,
            "project_summary": project_summary,
            "architecture": architecture,
            "useful_modules": useful_modules,
            "candidate_skills": candidate_skills,
            "conflicts": conflicts,
            "risk_analysis": risk_analysis,
            "merge_suggestions": merge_suggestions,
            "recommended_strategy": recommended_strategy,
        }

    # ─── 内部方法 ───────────────────────────────────────────────────

    def _parse_repo_url(self, url: str) -> tuple[str, str]:
        """从 GitHub URL 提取 owner/repo。"""
        url = url.rstrip("/")
        # https://github.com/owner/repo
        parts = url.split("/")
        if "github.com" in url:
            idx = parts.index("github.com")
            owner = parts[idx + 1] if len(parts) > idx + 1 else ""
            repo = parts[idx + 2] if len(parts) > idx + 2 else ""
            return owner, repo
        # owner/repo 格式
        if "/" in url and not url.startswith("http"):
            p = url.split("/")
            return p[0], p[1] if len(p) > 1 else ""
        return url, ""

    def _build_project_summary(self, owner: str, repo: str) -> dict:
        """获取项目基本信息。"""
        info = self._gh.call({"action": "repo_info", "repo": f"{owner}/{repo}"})
        if info.get("status") != "ok":
            return info

        readme = self._gh.call({"action": "readme", "repo": f"{owner}/{repo}"})
        d = info.get("data", {})

        return {
            "name": d.get("name", repo),
            "full_name": f"{owner}/{repo}",
            "description": d.get("description", ""),
            "language": d.get("language", ""),
            "stars": d.get("stars", 0),
            "license": d.get("license", ""),
            "disk_usage_kb": d.get("disk_usage_kb", 0),
            "readme_preview": readme.get("data", {}).get("readme", "")[:500] if readme.get("status") == "ok" else "",
        }

    def _get_tree(self, owner: str, repo: str, branch: str) -> dict:
        """获取文件树。"""
        result = self._gh.call({"action": "tree", "repo": f"{owner}/{repo}", "branch": branch})
        return result.get("data", {})

    def _analyze_architecture(self, tree: dict, owner: str, repo: str, branch: str) -> dict:
        """分析项目架构。"""
        files = tree.get("files", [])
        dirs = tree.get("dirs", [])

        top_level = [d for d in dirs if "/" not in d]
        py_files = [f["path"] for f in files if f["path"].endswith(".py")]
        ext_map: dict[str, int] = {}
        for f in files:
            ext = f["path"].rsplit(".", 1)[-1] if "." in f["path"] else "none"
            ext_map[ext] = ext_map.get(ext, 0) + 1

        deps_result = self._get_deps(owner, repo, branch)

        return {
            "top_level_dirs": top_level,
            "file_count": tree.get("file_count", 0),
            "dir_count": tree.get("dir_count", 0),
            "python_files": len(py_files),
            "py_files_list": py_files[:50],  # 限制输出
            "extension_breakdown": dict(sorted(ext_map.items(), key=lambda x: -x[1])[:10]),
            "dependencies": deps_result,
        }

    def _get_deps(self, owner: str, repo: str, branch: str) -> list[dict]:
        """获取依赖文件内容。"""
        dep_files = self._gh.call({"action": "tree", "repo": f"{owner}/{repo}", "branch": branch})
        if dep_files.get("status") != "ok":
            return []

        patterns = ["requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
                     "Pipfile", "package.json", "go.mod", "Cargo.toml"]
        result = []
        for f in dep_files.get("data", {}).get("files", []):
            name = f["path"].rsplit("/", 1)[-1] if "/" in f["path"] else f["path"]
            if name in patterns:
                content = self._gh.call({"action": "file", "repo": f"{owner}/{repo}", "path": f["path"]})
                result.append({
                    "path": f["path"],
                    "name": name,
                    "content_preview": content.get("data", {}).get("content", "")[:300] if content.get("status") == "ok" else "",
                })
        return result

    def _find_useful_modules(self, tree: dict) -> list[dict]:
        """识别对 DVexa 有价值的模块。"""
        files = tree.get("files", [])
        useful = []

        for f in files:
            path = f["path"]
            name = path.rsplit("/", 1)[-1] if "/" in path else path
            if not path.endswith(".py") or path.endswith("__init__.py") or path.endswith("__main__.py"):
                continue

            score, cat, reason = self._score_module(path, name)
            if score >= 0.5:
                useful.append({
                    "path": path,
                    "name": name.replace(".py", ""),
                    "size": f.get("size", 0),
                    "category": cat,
                    "relevance_score": round(score, 2),
                    "reason": reason,
                })

        useful.sort(key=lambda x: -x["relevance_score"])
        return useful

    def _score_module(self, path: str, name: str) -> tuple[float, str, str]:
        """评估模块对 DVexa 的价值。"""
        path_lower = path.lower()

        # 测试模块 — 最低分
        if "test" in path_lower.split("/") or name.startswith("test_"):
            return (0.20, "util", "测试模块，低吞并价值")

        # 工具类模块
        if any(kw in path_lower for kw in ["/tools/", "/utils/", "/helpers/", "/lib/"]) or \
           any(kw in name.lower() for kw in ["tool", "util", "helper", "base"]):
            return (0.85, "tool", f"工具类模块，适合封装为 DVexa Tool")

        # Agent 模块
        if any(kw in path_lower for kw in ["/agent", "/planner", "/strateg"]) or \
           any(kw in name.lower() for kw in ["agent", "planner", "strateg"]):
            return (0.70, "agent", f"Agent 类模块，可参考但不直接吞并（架构差异）")

        # Router/Handler 模块
        if any(kw in path_lower for kw in ["/router", "/handler", "/dispatch"]) or \
           any(kw in name.lower() for kw in ["router", "handler", "dispatch", "route"]):
            return (0.65, "router", f"路由类模块，可适配为 CapabilityRouter")

        # Skill/Capability 模块 — 高价值
        if any(kw in path_lower for kw in ["/skill", "/capability", "/plugin_manager"]) or \
           any(kw in name.lower() for kw in ["skill_registry", "capability", "plugin_manager"]):
            return (0.90, "skill", f"能力管理模块，高吞并价值")

        # 入口/主模块
        if name in ("main", "app", "cli", "__main__"):
            return (0.50, "pipeline", f"入口模块，参考架构设计")

        # 管道/流程模块
        if any(kw in path_lower for kw in ["/pipeline", "/workflow", "/execut"]) or \
           any(kw in name.lower() for kw in ["pipeline", "workflow", "execut"]):
            return (0.50, "pipeline", f"流程类模块，参考但不直接吞并（控制流差异）")

        # API 接口模块
        if any(kw in path_lower for kw in ["/api/", "/endpoint", "/server"]) or \
           any(kw in name.lower() for kw in ["api", "server", "endpoint"]):
            return (0.55, "api", f"API 接口模块，适合参考重构")

        # 配置模块
        if any(kw in path_lower for kw in ["/config/", "/setting"]) or \
           any(kw in name.lower() for kw in ["config", "setting"]):
            return (0.40, "util", f"配置模块，参考设计模式")

        # 数据库/存储
        if any(kw in path_lower for kw in ["/db/", "/store", "/repository"]) or \
           any(kw in name.lower() for kw in ["database", "store", "repository", "db"]):
            return (0.60, "tool", f"存储模块，可封装为 DVexa Memory 或 Tool")

        # 核心控制模块
        if any(kw in path_lower for kw in ["/core/", "/kernel"]) or \
           any(kw in name.lower() for kw in ["core", "kernel"]):
            return (0.40, "router", f"核心控制模块，不直接吞并，参考设计")

        # 通用 plugin — 降低分数避免噪声
        if any(kw in path_lower for kw in ["/plugin", "/extension", "/addon"]) or \
           any(kw in name.lower() for kw in ["plugin"]):
            return (0.50, "skill", f"插件类模块，需评估具体能力价值")

        return (0.0, "other", "无直接关联")

    def _extract_candidate_skills(self, modules: list[dict], architecture: dict) -> list[dict]:
        """从有用模块中提取候选技能（去重 + 限高）。"""
        seen: set[str] = set()
        candidates = []
        for m in modules:
            if m["relevance_score"] < 0.6:
                continue
            if m["name"] in seen:
                continue
            seen.add(m["name"])

            type_hint = self._infer_skill_type(m)
            candidates.append({
                "name": m["name"],
                "source_module": m["path"],
                "type_hint": type_hint,
                "keywords": [m["name"], type_hint, "external"],
                "description": m["reason"],
                "complexity": self._estimate_complexity(m["size"]),
                "estimated_lines": m["size"],
                "relevance": m["relevance_score"],
            })

        # 按相关度降序，限前 30 个
        candidates.sort(key=lambda x: -x["relevance"])
        return candidates[:30]

    def _infer_skill_type(self, module: dict) -> str:
        """推断技能类型。"""
        path = module["path"].lower()
        if "http" in path or "network" in path or "api" in path:
            return "http"
        if "llm" in path or "ai" in path or "model" in path:
            return "llm"
        if "code" in path or "execut" in path or "sandbox" in path:
            return "code"
        if "tool" in path or "util" in path:
            return "other"
        return "other"

    def _estimate_complexity(self, lines: int) -> str:
        if lines < 50:
            return "low"
        if lines < 200:
            return "medium"
        return "high"

    def _detect_conflicts(self, candidates: list[dict], architecture: dict) -> list[dict]:
        """检测与 DVexa 架构的冲突。"""
        conflicts = []

        for c in candidates:
            # 检查命名冲突
            conflicts.append({
                "module": c["source_module"],
                "conflict_type": "duplicate_skill",
                "severity": "medium",
                "description": f"技能 {c['name']} 可能与 DVexa 已有能力重叠",
                "dvx_equivalent": "参考已有 skill 模式",
            })

        # 架构层面冲突
        if architecture.get("file_count", 0) > 500:
            conflicts.append({
                "module": "（整体项目）",
                "conflict_type": "architecture_clash",
                "severity": "low",
                "description": "项目规模较大，需选择性参考而非整体吞并",
                "dvx_equivalent": "DVexa 单核架构",
            })

        return conflicts

    def _analyze_risks(self, summary: dict, architecture: dict) -> list[dict]:
        """分析吞并风险。"""
        risks = []

        # 许可证风险
        if summary.get("license"):
            risks.append({
                "category": "license",
                "level": "low",
                "detail": f"许可证: {summary['license']}，需确认兼容性",
            })

        # 依赖风险
        deps = architecture.get("dependencies", [])
        external_deps = [d for d in deps if d.get("content_preview")]
        if external_deps:
            risks.append({
                "category": "dependency",
                "level": "medium",
                "detail": f"发现 {len(external_deps)} 个依赖文件，需评估外部依赖",
            })

        # 架构风险
        if summary.get("stars", 0) > 1000:
            risks.append({
                "category": "architecture",
                "level": "low",
                "detail": "成熟项目，架构稳定，直接吞并需大幅改造",
            })

        return risks

    def _generate_merge_suggestions(self, modules: list[dict], conflicts: list[dict], risks: list[dict]) -> list[dict]:
        """生成吞并建议分类。"""
        suggestions = []

        for i, m in enumerate(modules):
            if m["relevance_score"] >= 0.8:
                action = "assimilate_as_skill"
                priority = 1
                refactor = "wrap_as_skill"
            elif m["relevance_score"] >= 0.6:
                action = "extract_pattern"
                priority = 2
                refactor = "rewrite_for_capability"
            elif m["relevance_score"] >= 0.4:
                action = "reference_only"
                priority = 3
                refactor = "keep_external"
            else:
                action = "reject"
                priority = 5
                refactor = "keep_external"

            suggestions.append({
                "module": m["path"],
                "action": action,
                "priority": priority,
                "rationale": m["reason"],
                "refactor_type": refactor,
                "estimated_effort": self._estimate_complexity(m["size"]),
            })

        suggestions.sort(key=lambda x: x["priority"])
        return suggestions

    def _build_strategy(self, suggestions: list[dict], modules: list[dict]) -> dict:
        """汇总建议策略。"""
        quick_wins = [s["module"] for s in suggestions if s["priority"] == 1]
        needs_review = [s["module"] for s in suggestions if s["priority"] in (2, 3)]
        should_reject = [s["module"] for s in suggestions if s["priority"] >= 5]

        scores = [m["relevance_score"] for m in modules if m.get("relevance_score")]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0

        return {
            "overall_approach": "分优先级吞并：高价值模块直接封装为 Skill，中等模块提取模式后重构，低价值仅参考",
            "quick_wins": quick_wins,
            "needs_human_review": needs_review,
            "should_reject": should_reject,
            "total_candidates": len(modules),
            "avg_relevance_score": avg_score,
        }
