"""Security Scanner Tool — 静态代码安全扫描

stateless: 每次扫描独立（仅 lru_cache 缓存相同文件的扫描结果）
no decision: 只返回匹配结果，不做判断
no self modify: 纯只读分析

提取自 openxjarvis/openclaw-python security/skill_scanner.py 的 7 类危险模式设计。
吞并原则：提取设计思想，按 DVexa stateless Tool 风格重构。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from tools.base_tool import Tool

ScanRuleId = Literal[
    "dangerous-exec",
    "dynamic-code",
    "crypto-mining",
    "exfiltration",
    "obfuscation",
    "env-harvesting",
    "suspicious-network",
]


@dataclass(frozen=True)
class ScanMatch:
    line: int
    snippet: str


@dataclass(frozen=True)
class ScanResult:
    file_path: str
    rule_id: ScanRuleId
    description: str
    matches: list[ScanMatch] = field(default_factory=list)


@dataclass(frozen=True)
class _ScanRule:
    id: ScanRuleId
    description: str
    patterns: list[re.Pattern[str]]


# ─── 7 类危险模式规则（提取自 OpenClaw skill_scanner.py） ───────────────

_RULES: list[_ScanRule] = [
    _ScanRule(
        id="dangerous-exec",
        description="Direct subprocess or os.system execution",
        patterns=[
            re.compile(r"\bsubprocess\.(?:run|call|Popen|check_output|check_call)\s*\(", re.IGNORECASE),
            re.compile(r"\bos\.(?:system|popen|execv?[pe]?)\s*\(", re.IGNORECASE),
            re.compile(r"\b__import__\s*\(\s*['\"]subprocess", re.IGNORECASE),
        ],
    ),
    _ScanRule(
        id="dynamic-code",
        description="Dynamic code execution (eval/exec/compile of runtime strings)",
        patterns=[
            re.compile(r"\beval\s*\(", re.IGNORECASE),
            re.compile(r"\bexec\s*\((?!\s*['\"])", re.IGNORECASE),
            re.compile(r"\bcompile\s*\(\s*(?:input|request|data|body|text|msg)\b", re.IGNORECASE),
            re.compile(r"\b__import__\s*\(", re.IGNORECASE),
            re.compile(r"\bimportlib\.import_module\s*\(", re.IGNORECASE),
        ],
    ),
    _ScanRule(
        id="crypto-mining",
        description="Cryptocurrency mining indicators",
        patterns=[
            re.compile(r"\bmonero\b|\bxmr\b|\bstratum\+tcp://", re.IGNORECASE),
            re.compile(r"\bxmrig\b|\bwildrig\b|\bcpuminer\b|\bnsfminer\b", re.IGNORECASE),
            re.compile(r"\bpool\.minergate\.com\b|\bpool\.supportxmr\.com\b", re.IGNORECASE),
        ],
    ),
    _ScanRule(
        id="exfiltration",
        description="Suspicious data exfiltration patterns",
        patterns=[
            re.compile(
                r"requests\.post\s*\([^)]*\b(?:environ|password|token|secret|api_key)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"urllib\.request\.urlopen\s*\([^)]*\b(?:data=|POST)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bsmtplib\b.*\bsendmail\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:http|https)://(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?/(?:upload|exfil|data|collect)",
                re.IGNORECASE,
            ),
        ],
    ),
    _ScanRule(
        id="obfuscation",
        description="Code obfuscation (base64 decode→exec, fromCharCode chains)",
        patterns=[
            re.compile(
                r"base64\.b64decode\s*\([^)]+\)\s*[,;)\n].*(?:exec|eval|compile)",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"(?:bytes\.fromhex|binascii\.unhexlify)\s*\([^)]+\).*(?:exec|eval)",
                re.IGNORECASE,
            ),
            re.compile(r"\\u[0-9a-fA-F]{4}.*\\u[0-9a-fA-F]{4}.*\\u[0-9a-fA-F]{4}"),
            re.compile(r"String\.fromCharCode\s*\((?:\d+\s*,\s*){5,}", re.IGNORECASE),
            re.compile(r"\.decode\s*\(\s*['\"](?:rot.?13|base64|zip|bz2)['\"]", re.IGNORECASE),
        ],
    ),
    _ScanRule(
        id="env-harvesting",
        description="Bulk environment variable harvesting",
        patterns=[
            re.compile(r"\bos\.environ\s*(?:\.copy\s*\(\)|\.items\s*\()|dict\s*\(\s*os\.environ\s*\)", re.IGNORECASE),
            re.compile(r"\bgetenv\s*\(\s*['\"](?:HOME|PATH|USER|LOGNAME|TOKEN|SECRET|API_KEY|PASSWORD)['\"]", re.IGNORECASE),
            re.compile(r"os\.environ.*requests\.(?:post|get)\b", re.IGNORECASE | re.DOTALL),
        ],
    ),
    _ScanRule(
        id="suspicious-network",
        description="Suspicious raw network connections (Tor, SOCKS, raw TCP)",
        patterns=[
            re.compile(r"\bsocket\.socket\s*\(.*SOCK_STREAM\b.*\bconnect\b", re.IGNORECASE),
            re.compile(r"\bsocks5h?://|socks4a?://", re.IGNORECASE),
            re.compile(r"\.onion\b", re.IGNORECASE),
        ],
    ),
]

_MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB
_RULE_MAP: dict[str, _ScanRule] = {r.id: r for r in _RULES}


class SecurityScannerTool(Tool):
    """静态代码安全扫描工具。

    使用 7 类危险模式对代码进行正则扫描。
    纯分析，零副作用。

    输入:
      {"action": "scan_text", "text": "...", "source": "optional_path"}
      {"action": "scan_file", "path": "/path/to/file"}
      {"action": "rules"}  — 列出所有可用规则
      {"action": "scan_rules", "rules": ["dangerous-exec", ...], "text": "..."}
    """

    def call(self, input_data) -> dict:
        if isinstance(input_data, str):
            return {"status": "error", "error": "输入必须为 dict，包含 action 字段"}

        action = input_data.get("action", "")
        if not action:
            return {"status": "error", "error": "缺少 action 字段"}

        actions = {
            "scan_text": self._scan_text,
            "scan_file": self._scan_file,
            "rules": self._list_rules,
            "scan_rules": self._scan_custom_rules,
        }

        handler = actions.get(action)
        if not handler:
            return {
                "status": "error",
                "error": f"不支持的动作: {action}，可选: {list(actions.keys())}",
            }

        return handler(input_data)

    # ─── 公开接口 ─────────────────────────────────────────────────────

    def _scan_text(self, data: dict) -> dict:
        """扫描文本内容。"""
        text = data.get("text", "")
        source = data.get("source", "<text>")
        if not text:
            return {"status": "ok", "data": {"scanned": source, "clean": True, "matches": []}}

        matches = _scan_content(text)
        return {
            "status": "ok",
            "data": {
                "scanned": source,
                "clean": not matches,
                "match_count": len(matches),
                "matches": [_match_to_dict(m) for m in matches],
            },
        }

    def _scan_file(self, data: dict) -> dict:
        """扫描文件。"""
        path_str = data.get("path", "")
        if not path_str:
            return {"status": "error", "error": "缺少 path 参数"}

        path = Path(path_str)
        if not path.exists():
            return {"status": "error", "error": f"文件不存在: {path}"}
        if not path.is_file():
            return {"status": "error", "error": f"不是文件: {path}"}

        try:
            st = path.stat()
            if st.st_size > _MAX_FILE_SIZE:
                return {
                    "status": "ok",
                    "data": {
                        "scanned": str(path),
                        "clean": True,
                        "match_count": 0,
                        "matches": [],
                        "note": f"文件超过大小限制 ({_MAX_FILE_SIZE} bytes)，跳过扫描",
                    },
                }
            text = path.read_text(encoding="utf-8", errors="replace")
            return self._scan_text({"text": text, "source": str(path)})
        except PermissionError as e:
            return {"status": "error", "error": f"权限拒绝: {e}"}
        except Exception as e:
            return {"status": "error", "error": f"读取失败: {e}"}

    def _list_rules(self, data: dict) -> dict:
        """列出所有可用规则。"""
        rules = []
        for r in _RULES:
            rules.append({
                "id": r.id,
                "description": r.description,
                "pattern_count": len(r.patterns),
            })
        return {"status": "ok", "data": {"rule_count": len(rules), "rules": rules}}

    def _scan_custom_rules(self, data: dict) -> dict:
        """使用指定规则子集扫描。"""
        rule_ids = data.get("rules", [])
        text = data.get("text", "")
        source = data.get("source", "<text>")

        if not rule_ids:
            return {"status": "error", "error": "请指定至少一个规则 ID"}
        if not text:
            return {"status": "ok", "data": {"scanned": source, "clean": True, "matches": []}}

        selected: list[_ScanRule] = []
        for rid in rule_ids:
            rule = _RULE_MAP.get(rid)
            if rule:
                selected.append(rule)
            else:
                return {"status": "error", "error": f"未知规则: {rid}，可用: {list(_RULE_MAP.keys())}"}

        matches = _scan_with_rules(text, selected)
        return {
            "status": "ok",
            "data": {
                "scanned": source,
                "clean": not matches,
                "match_count": len(matches),
                "rules_applied": list(rule_ids),
                "matches": [_match_to_dict(m) for m in matches],
            },
        }


# ─── 核心扫描函数 ──────────────────────────────────────────────────────


def _locate_line(text: str, offset: int) -> int:
    """从字符偏移量计算行号（从 1 开始）。"""
    return text.count("\n", 0, offset) + 1


def _line_at(text: str, offset: int) -> str:
    """获取偏移量所在的行内容。"""
    start = text.rfind("\n", 0, offset)
    end = text.find("\n", offset)
    if start == -1:
        start = 0
    else:
        start += 1
    if end == -1:
        end = len(text)
    return text[start:end].strip()


def _scan_content(text: str) -> list[dict]:
    """扫描文本内容，返回匹配列表。全文搜索 + 行号定位。"""
    matches: list[dict] = []

    for rule in _RULES:
        for pattern in rule.patterns:
            m = pattern.search(text)
            if not m:
                continue
            lineno = _locate_line(text, m.start())
            snippet = _line_at(text, m.start())[:120]
            matches.append({
                "rule_id": rule.id,
                "description": rule.description,
                "line": lineno,
                "snippet": snippet,
            })
            break  # 每类规则每文件只报告一次

    return matches


def _scan_with_rules(text: str, rules: list[_ScanRule]) -> list[dict]:
    """使用指定规则扫描。"""
    matches: list[dict] = []

    for rule in rules:
        for pattern in rule.patterns:
            m = pattern.search(text)
            if not m:
                continue
            lineno = _locate_line(text, m.start())
            snippet = _line_at(text, m.start())[:120]
            matches.append({
                "rule_id": rule.id,
                "description": rule.description,
                "line": lineno,
                "snippet": snippet,
            })
            break

    return matches


def _match_to_dict(m: dict) -> dict:
    return {
        "rule_id": m["rule_id"],
        "description": m["description"],
        "line": m["line"],
        "snippet": m["snippet"],
    }
