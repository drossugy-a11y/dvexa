"""吞并日志系统 — 系统进化历史档案（v1.89）

每次外部分析器分析外部项目后，自动生成标准化日志文件。
日志是 DVexa 的"进化记忆"，纯观察层，不参与任何控制流。

约束：
  - 不允许进入 kernel
  - 不允许影响 router
  - 不允许影响 governance
  - 不允许自动触发注册
  - 不允许自动修改系统

依赖白名单：dataclasses, pathlib, json, typing, external.
禁止引用：kernel, executor, router, governor.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


# ─── 常量 ──────────────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).resolve().parent.parent / "ZSK" / "TBRZ"

VALID_DECISIONS = {"approved", "rejected", "pending"}

SEARCH_FIELDS = {
    "project", "capability", "capabilities", "risk", "decision",
}


# ─── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class CandidateCapability:
    """候选吞并能力"""
    candidate_skill: str
    source_module: str
    confidence: float = 0.0
    complexity: str = "medium"     # low / medium / high
    risk: str = "low"              # low / medium / high
    estimated_value: str = ""      # 价值描述


@dataclass
class RejectedCapability:
    """被拒绝的能力"""
    candidate_skill: str
    source_module: str
    reason: str = ""


@dataclass
class ObservedArchitecture:
    """观察到的架构"""
    modules: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    memory: list[str] = field(default_factory=list)
    workflow: list[str] = field(default_factory=list)


@dataclass
class AssimilationLogEntry:
    """单次外部项目吞并分析日志。"""
    source_project: str
    github_url: str = ""
    analyzed_commit: str = ""
    analysis_time: str = ""
    observed_architecture: ObservedArchitecture = field(default_factory=ObservedArchitecture)
    candidate_capabilities: list[CandidateCapability] = field(default_factory=list)
    rejected_capabilities: list[RejectedCapability] = field(default_factory=list)
    decision: str = "pending"
    future_notes: str = ""

    def __post_init__(self):
        if not self.analysis_time:
            self.analysis_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.decision not in VALID_DECISIONS:
            self.decision = "pending"

    def to_dict(self) -> dict:
        """序列化为 dict。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AssimilationLogEntry":
        """从 dict 反序列化。"""
        arch = data.get("observed_architecture", {})
        if isinstance(arch, dict):
            data["observed_architecture"] = ObservedArchitecture(**arch)
        caps = data.get("candidate_capabilities", [])
        data["candidate_capabilities"] = [
            CandidateCapability(**c) if isinstance(c, dict) else c for c in caps
        ]
        rejs = data.get("rejected_capabilities", [])
        data["rejected_capabilities"] = [
            RejectedCapability(**r) if isinstance(r, dict) else r for r in rejs
        ]
        return cls(**data)


# ─── 日志器 ────────────────────────────────────────────────────────────────────

class AssimilationLogger:
    """吞并日志记录器。

    管理 ZSK/TBRZ/ 目录，所有日志以 TB 序号命名。
    所有操作纯文件 IO，不涉及任何系统控制层。
    """

    def __init__(self, log_dir: str | Path | None = None):
        self._log_dir = Path(log_dir) if log_dir else LOG_DIR
        self._log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def log_dir(self) -> Path:
        return self._log_dir

    # ─── 写入 ────────────────────────────────────────────────────────────

    def save_log(self, entry: AssimilationLogEntry) -> str:
        """保存日志到文件（JSON 格式），返回文件名。"""
        filename = self._make_filename(entry, self._log_dir)
        filepath = self._log_dir / filename

        data = entry.to_dict()
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        return filename

    def save_log_markdown(self, entry: AssimilationLogEntry) -> str:
        """以 Markdown 格式导出日志，返回文件路径。"""
        filename = self._make_filename(entry, self._log_dir, md=True)
        filepath = self._log_dir / filename
        md = self._to_markdown(entry)
        filepath.write_text(md, encoding="utf-8")
        return str(filepath)

    # ─── 读取 ────────────────────────────────────────────────────────────

    def load_log(self, filename: str) -> AssimilationLogEntry | None:
        """加载单条日志。"""
        filepath = self._log_dir / filename
        if not filepath.exists():
            return None
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return AssimilationLogEntry.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def list_all(self) -> list[str]:
        """列出所有日志文件名（仅 JSON）。"""
        if not self._log_dir.exists():
            return []
        files = sorted(self._log_dir.glob("TB*.json"))
        return [f.name for f in files]

    # ─── 搜索 ────────────────────────────────────────────────────────────

    def search_logs(self, keyword: str, field: str | None = None) -> list[AssimilationLogEntry]:
        """搜索日志。

        Args:
            keyword: 搜索关键词（大小写不敏感）
            field: 限定搜索范围，None 为全部字段。
                   "project" — 按项目名搜索
                   "capability" / "capabilities" — 按候选能力搜索
                   "risk" — 按风险等级搜索
                   "decision" — 按决策状态搜索

        Returns:
            匹配的日志列表。
        """
        keyword_lower = keyword.lower()
        results: list[AssimilationLogEntry] = []

        for fname in self.list_all():
            entry = self.load_log(fname)
            if not entry:
                continue

            if field and field not in SEARCH_FIELDS:
                field = None

            if field == "project":
                if keyword_lower in entry.source_project.lower():
                    results.append(entry)
            elif field == "capability" or field == "capabilities":
                for cap in entry.candidate_capabilities:
                    if keyword_lower in cap.candidate_skill.lower():
                        results.append(entry)
                        break
            elif field == "risk":
                for cap in entry.candidate_capabilities:
                    if keyword_lower in cap.risk.lower():
                        results.append(entry)
                        break
            elif field == "decision":
                if keyword_lower in entry.decision.lower():
                    results.append(entry)
            else:
                # 全字段搜索
                if self._match_any_field(entry, keyword_lower):
                    results.append(entry)

        return results

    def summarize_project_history(self, project_name: str) -> dict:
        """汇总指定项目的吞并分析历史。

        Returns:
            {
                "project": str,
                "analysis_count": int,
                "candidate_skills": [str],
                "rejected_skills": [str],
                "decision": str,
                "avg_confidence": float,
            }
        """
        entries = self.search_logs(project_name, field="project")
        if not entries:
            return {"project": project_name, "analysis_count": 0}

        latest = entries[-1]
        all_candidates = []
        all_rejected = []
        total_confidence = 0.0
        count = 0

        for e in entries:
            for c in e.candidate_capabilities:
                all_candidates.append(c.candidate_skill)
                total_confidence += c.confidence
                count += 1
            for r in e.rejected_capabilities:
                all_rejected.append(r.candidate_skill)

        return {
            "project": project_name,
            "analysis_count": len(entries),
            "candidate_skills": all_candidates,
            "rejected_skills": all_rejected,
            "decision": latest.decision,
            "avg_confidence": round(total_confidence / count, 2) if count > 0 else 0.0,
        }

    # ─── 内部方法 ────────────────────────────────────────────────────────

    def _make_filename(self, entry: AssimilationLogEntry, log_dir: Path | None = None, md: bool = False) -> str:
        """生成下一个 TB 序号文件名。

        扫描全部 TB 文件实现统一编号，JSON 和 MD 共享序号序列。
        例：TB1.json, TB2.md, TB3.json, ...
        """
        ext = ".md" if md else ".json"

        if log_dir is None:
            log_dir = self._log_dir

        # 扫描所有 TB 文件（无论扩展名），找到最大序号
        max_num = 0
        for f in log_dir.glob("TB*"):
            match = re.match(r"^TB(\d+)\.(json|md)$", f.name)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num

        return f"TB{max_num + 1}{ext}"

    def _match_any_field(self, entry: AssimilationLogEntry, keyword: str) -> bool:
        """检查日志任意字段是否包含关键词。"""
        if keyword in entry.source_project.lower():
            return True
        if keyword in entry.decision.lower():
            return True
        if keyword in entry.future_notes.lower():
            return True
        for cap in entry.candidate_capabilities:
            if keyword in cap.candidate_skill.lower():
                return True
            if keyword in cap.risk.lower():
                return True
        for rej in entry.rejected_capabilities:
            if keyword in rej.candidate_skill.lower():
                return True
            if keyword in rej.reason.lower():
                return True
        return False

    def _to_markdown(self, entry: AssimilationLogEntry) -> str:
        """生成中文 Markdown 格式日志。"""
        lines = [
            "---",
            f"project: {entry.source_project}",
            f"github: {entry.github_url}",
            f"commit: {entry.analyzed_commit}",
            f"analyzed: {entry.analysis_time}",
            "---",
            "",
            f"# 吞并分析报告：{entry.source_project}",
            "",
            "## 来源信息",
            "",
            f"- 项目名称：{entry.source_project}",
            f"- GitHub 地址：{entry.github_url}",
            f"- 分析提交：{entry.analyzed_commit}",
            f"- 分析时间：{entry.analysis_time}",
            "",
        ]

        arch = entry.observed_architecture
        lines.append("## 观察到的架构")
        lines.append("")
        for field_name, label in [("modules", "模块结构"), ("agents", "Agent 结构"),
                                   ("tools", "工具结构"), ("memory", "Memory 结构"),
                                   ("workflow", "工作流结构")]:
            items = getattr(arch, field_name, [])
            if items:
                lines.append(f"### {label}")
                for item in items:
                    lines.append(f"- {item}")
                lines.append("")

        if entry.candidate_capabilities:
            lines.append("## 候选吞并能力")
            lines.append("")
            for c in entry.candidate_capabilities:
                lines.append(f"### {c.candidate_skill}")
                lines.append(f"- 来源模块：{c.source_module}")
                lines.append(f"- 置信度：{c.confidence}")
                lines.append(f"- 复杂度：{c.complexity}")
                lines.append(f"- 风险等级：{c.risk}")
                if c.estimated_value:
                    lines.append(f"- 预估价值：{c.estimated_value}")
                lines.append("")

        if entry.rejected_capabilities:
            lines.append("## 已拒绝的能力")
            lines.append("")
            for r in entry.rejected_capabilities:
                lines.append(f"### {r.candidate_skill}")
                lines.append(f"- 来源模块：{r.source_module}")
                lines.append(f"- 拒绝原因：{r.reason}")
                lines.append("")

        lines.append("## 吞并决策")
        lines.append("")
        lines.append(f"- **{entry.decision}**")
        lines.append("")

        if entry.future_notes:
            lines.append("## 后续备注")
            lines.append("")
            lines.append(entry.future_notes)
            lines.append("")

        return "\n".join(lines)
