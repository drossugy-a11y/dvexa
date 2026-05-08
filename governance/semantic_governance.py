"""Semantic Governance Layer v1.0 — 语义治理层

定位：纯观察层，位于 Input → SGL → ATS → Governance → DevLog 流水线的最前端。
核心原则：
  - 不执行任何代码
  - 不影响系统状态
  - 不注册能力
  - 不绕过 governance
  - 不直接修改 routing

红线（绝对禁止）：
  - 不引用 core/kernel.py / core/executor.py / core/guard.py / agents/base_agent.py
  - 不调用 SkillRegistry.register()
  - 不调用 SkillHandler.call()
  - 不修改 SkillGovernor
  - 不修改 ToolPolicy
"""

from __future__ import annotations

import re
import os
from datetime import datetime
from typing import Any


# ─── Intent Detection ───────────────────────────────────────────────────────

class IntentDetector:
    """意图识别器 — 识别 5 种意图。

    纯规则模式匹配，无 LLM 依赖。
    优先级: manipulation > execution > extraction > analysis > unknown
    """

    # 每条规则: (keywords, intent_name, priority)
    # priority 越高，同时匹配时优先级越高
    _INTENT_RULES = [
        (["忽略", "绕过", "覆盖", "override", "bypass", "忽略规则",
          "跳过检查", "忽略指令", "忽略安全"], "manipulation", 100),
        (["执行", "运行", "创建", "修改", "删除", "部署", "run",
          "execute", "deploy", "create", "modify", "delete"], "execution", 80),
        (["读取", "获取", "导出", "下载", "提取", "read", "export",
          "extract", "download", "fetch", "harvest"], "extraction", 60),
        (["分析", "检查", "总结", "查看", "搜索", "列出", "analyze",
          "check", "summarize", "view", "search", "list", "status"], "analysis", 40),
    ]

    def detect(self, text: str) -> dict:
        """检测输入文本的意图。

        Returns:
            {"intent": str, "confidence": float, "matched_keywords": list[str]}
        """
        if not text or not text.strip():
            return {"intent": "unknown", "confidence": 0.0, "matched_keywords": []}

        text_lower = text.lower()
        matched_intent = "unknown"
        matched_priority = -1
        matched_keywords = []

        for keywords, intent, priority in self._INTENT_RULES:
            found = [kw for kw in keywords if kw.lower() in text_lower]
            if found and priority > matched_priority:
                matched_intent = intent
                matched_priority = priority
                matched_keywords = found

        # confidence: 基于匹配关键词数量和文本长度
        confidence = min(0.3 + 0.15 * len(matched_keywords), 0.95) if matched_keywords else 0.0

        return {
            "intent": matched_intent,
            "confidence": round(confidence, 2),
            "matched_keywords": matched_keywords,
        }


# ─── Threat Detection ───────────────────────────────────────────────────────

class ThreatDetector:
    """威胁检测器 — 识别 5 种威胁类型 + 风险评分。

    威胁优先级（高风险覆盖低风险）:
      control_bypass > privilege_escalation > prompt_injection > data_harvest > none
    """

    _THREAT_RULES = [
        # (keywords, threat_type, base_risk)
        (
            ["绕过治理", "绕过控制", "绕过检查", "bypass governance",
             "绕过监管", "disable governance", "disable safety",
             "turn off all security", "remove all restrictions",
             "bypass security", "bypass controls"],
            "control_bypass", 0.9,
        ),
        (
            ["提升权限", "管理员权限", "高权限", "sudo", "root",
             "privilege escalation", "admin access", "superuser",
             "get root", "become admin", "elevate"],
            "privilege_escalation", 0.8,
        ),
        (
            ["忽略指令", "忽略系统指令", "ignore previous instructions",
             "ignore all instructions", "ignore all previous",
             "你现在是", "你是一个", "作为AI", "new instructions",
             "disregard", "忽略你之前的", "忘记之前"],
            "prompt_injection", 0.7,
        ),
        (
            ["读取密码", "获取密码", "读取秘钥", "读取密钥", "私钥",
             "读取所有", "导出全部", "所有密码", "所有用户",
             "steal", "credentials", "passwords", "secret key",
             "private key", "/etc/passwd", "/etc/shadow",
             "环境变量", "access_key", "secret_key"],
            "data_harvest", 0.6,
        ),
    ]

    def detect(self, text: str) -> dict:
        """检测输入文本中的威胁。

        Returns:
            {
                "threat_type": str,
                "risk_score": float,
                "detected_threats": list[dict],
                "matched_keywords": list[str],
            }
        """
        if not text or not text.strip():
            return {
                "threat_type": "none",
                "risk_score": 0.0,
                "detected_threats": [],
                "matched_keywords": [],
            }

        text_lower = text.lower()
        detected_threats = []
        all_matched_keywords = []

        for keywords, threat_type, base_risk in self._THREAT_RULES:
            found = [kw for kw in keywords if kw.lower() in text_lower]
            if found:
                detected_threats.append({
                    "threat_type": threat_type,
                    "base_risk": base_risk,
                    "matched_keywords": found,
                })
                all_matched_keywords.extend(found)

        if not detected_threats:
            return {
                "threat_type": "none",
                "risk_score": 0.0,
                "detected_threats": [],
                "matched_keywords": [],
            }

        # 最高优先级威胁作为主威胁类型
        # 按 base_risk 降序排列
        detected_threats.sort(key=lambda t: t["base_risk"], reverse=True)
        primary = detected_threats[0]

        # 组合风险评分：主风险 + 叠加修正（最多 +0.2）
        bonus = min(0.1 * (len(detected_threats) - 1), 0.2)
        risk_score = min(primary["base_risk"] + bonus, 1.0)

        return {
            "threat_type": primary["threat_type"],
            "risk_score": round(risk_score, 3),
            "detected_threats": detected_threats,
            "matched_keywords": all_matched_keywords,
        }


# ─── Capability Mapping ─────────────────────────────────────────────────────

class CapabilityMapper:
    """能力映射器 — 将输入映射到已有能力。

    红线：只返回 skill 名称字符串，不获取 SkillDef 实例，不调用 handler。
    """

    # 外部能力关键词: 当输入匹配这些时，映射到 external_ 前缀的能力
    _EXTERNAL_KEYWORDS = {
        "scanner": "external_scanner",
        "analyzer": "external_analyzer",
        "browser": "external_browser",
        "github": "external_github",
    }

    def __init__(self, registry=None):
        # registry 是可选引用，仅用于查询 skill 名称
        # 设计约束：从不调用 registry.register() 或 registry.get().handler
        self._registry = registry
        # 注意：_registry 可以是 None（SGL 独立运行）

    def map(self, text: str) -> str | None:
        """将输入文本映射到能力名称。

        映射优先级：
          1. 外部能力关键词匹配
          2. SkillRegistry keyword 匹配
          3. 无匹配返回 None

        Returns:
            str | None: 能力名称字符串，或 None
        """
        if not text or not text.strip():
            return None

        text_lower = text.lower()

        # 1. 检查外部能力
        for keyword, capability in self._EXTERNAL_KEYWORDS.items():
            if keyword in text_lower:
                return capability

        # 2. 检查 SkillRegistry（如果可用）
        if self._registry is not None:
            matched = self._registry.match(text)
            if matched:
                return matched

        return None

    @property
    def has_registry(self) -> bool:
        """SGL 是否持有 registry 引用。"""
        return self._registry is not None


# ─── Governance Decision ────────────────────────────────────────────────────

class GovernanceDecider:
    """治理决策器 — 根据风险评分决定治理影响。

    Decision rules:
      risk < 0.3  → "advisory"   (建议观察)
      0.3 ≤ r < 0.7 → "restricted" (受限模式)
      r ≥ 0.7     → "blocked"    (阻断 + DevLog)
    """

    def decide(self, risk_score: float) -> dict:
        """根据风险评分做出治理决策。

        Returns:
            {
                "governance_impact": str,
                "risk_level": str,
                "reason": str,
            }
        """
        if risk_score >= 0.7:
            return {
                "governance_impact": "blocked",
                "risk_level": "high",
                "reason": f"risk_score={risk_score} >= 0.7: 阻断 + DevLog记录",
            }
        elif risk_score >= 0.3:
            return {
                "governance_impact": "restricted",
                "risk_level": "medium",
                "reason": f"risk_score={risk_score} in [0.3, 0.7): 受限模式",
            }
        else:
            return {
                "governance_impact": "advisory",
                "risk_level": "low",
                "reason": f"risk_score={risk_score} < 0.3: 允许观察",
            }


# ─── Semantic Governance Layer — 主入口 ──────────────────────────────────────

class SemanticGovernanceLayer:
    """语义治理层 — SGL 主入口。

    纯观察层，位于输入处理流水线最前端。
    输入 → SGL(语义判断) → ATS(行为验证) → Governance(决策) → DevLog(记录)

    Usage:
        sgl = SemanticGovernanceLayer()
        result = sgl.analyze("分析系统状态")
        # → {"intent": "analysis", "threat_type": "none", ...}
    """

    # DevLog 目录
    DEVLOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "DvexaZSK", "devlog")
    _analysis_counter = 0  # 类级计数器

    def __init__(self, registry=None):
        self._intent_detector = IntentDetector()
        self._threat_detector = ThreatDetector()
        self._capability_mapper = CapabilityMapper(registry)
        self._decider = GovernanceDecider()

        # 确保 DevLog 目录存在
        os.makedirs(self.DEVLOG_DIR, exist_ok=True)

    @property
    def intent_detector(self) -> IntentDetector:
        return self._intent_detector

    @property
    def threat_detector(self) -> ThreatDetector:
        return self._threat_detector

    @property
    def capability_mapper(self) -> CapabilityMapper:
        return self._capability_mapper

    @property
    def decider(self) -> GovernanceDecider:
        return self._decider

    def analyze_event(self, event: "Event") -> "Event":
        """Event Transformer: input Event → output Event。

        将 analyze() 的输出包装为 Event，不修改内部逻辑。
        """
        from runtime.event import Event as RuntimeEvent
        input_text = event.payload.get("input", "")
        result = self.analyze(input_text)
        return RuntimeEvent(
            trace_id=event.trace_id,
            stage="semantic",
            event_type="decision",
            payload={
                "intent": result["intent"],
                "threat_type": result["threat_type"],
                "risk_score": result["risk_score"],
                "governance_impact": result["governance_impact"],
                "mapped_skill": result["mapped_skill"],
                "reason": result["reason"],
            },
            metadata={"input_event_id": event.trace_id},
        )

    def analyze(self, action_input: str) -> dict:
        """完整语义分析流水线。

        接受 `ACTION <target> { ... }` 格式或纯文本输入。

        Returns:
            {
                "intent": str,
                "threat_type": str,
                "risk_score": float,
                "governance_impact": str,
                "mapped_skill": str | None,
                "reason": str,
            }
        """
        # 1. 解析输入（支持 ACTION 格式和纯文本）
        parsed = self._parse_action(action_input)
        # 使用完整原始输入进行语义分析（确保 ACTION 格式中的关键词也被检测）
        text = action_input
        mode = parsed.get("mode", "observe")

        # 2. 意图检测
        intent_result = self._intent_detector.detect(text)

        # 3. 威胁检测
        threat_result = self._threat_detector.detect(text)

        # 4. 能力映射
        mapped_skill = self._capability_mapper.map(text)

        # 5a. 如果输入是 ACTION 格式且显式声明了合法意图，且未检测到威胁，
        #     优先使用声明的意图而非全文检测结果
        VALID_SGL_INTENTS = {"analysis", "execution", "manipulation", "extraction"}
        parsed_intent = parsed.get("intent", "")
        if parsed_intent in VALID_SGL_INTENTS and threat_result["threat_type"] == "none":
            intent_result = {
                "intent": parsed_intent,
                "confidence": 0.9,
                "matched_keywords": intent_result.get("matched_keywords", []),
            }

        # 5b. 风险评分（综合意图置信度和威胁评分）
        risk_score = threat_result["risk_score"]
        # 如果威胁为 none 但意图是 manipulation，设为基础风险 + 标记政策违反
        if threat_result["threat_type"] == "none" and intent_result["intent"] == "manipulation":
            risk_score = max(risk_score, 0.3)
            threat_result = dict(threat_result)  # 创建新 dict 避免潜在的副作用
            threat_result["threat_type"] = "policy_violation"

        # 6. 治理决策
        decision = self._decider.decide(risk_score)

        # 7. 构建输出
        result = {
            "intent": intent_result["intent"],
            "threat_type": threat_result["threat_type"],
            "risk_score": risk_score,
            "governance_impact": decision["governance_impact"],
            "mapped_skill": mapped_skill,
            "reason": (
                f"intent={intent_result['intent']}({intent_result['confidence']}), "
                f"threat={threat_result['threat_type']}({risk_score}), "
                f"decision={decision['governance_impact']}, "
                f"mapped={mapped_skill or 'none'}"
            ),
        }

        # 8. 记录 DevLog（仅当 blocked 或 restricted 时）
        if decision["governance_impact"] in ("blocked", "restricted"):
            self._write_devlog(result, text)

        return result

    def analyze_raw(self, input: str = "", context: str = "", mode: str = "observe") -> dict:
        """直接传入分析参数（兼容简写格式）。

        Args:
            input: 输入文本
            context: 上下文（用于分析）
            mode: observe | strict | simulate

        Returns:
            dict: 与 analyze() 相同格式的分析结果
        """
        if not input:
            return {
                "intent": "unknown",
                "threat_type": "none",
                "risk_score": 0.0,
                "governance_impact": "advisory",
                "mapped_skill": None,
                "reason": "empty input, no analysis possible",
            }
        return self.analyze(input)

    def _parse_action(self, text: str) -> dict:
        """解析 ACTION <target> { ... } 格式。

        Returns dict with keys: intent, context, mode, input
        Falls back to raw text if not valid ACTION format.
        """
        result = {"intent": "", "context": "", "mode": "observe", "input": text}

        # Try to match ACTION <target> { ... } format
        action_match = re.search(
            r'ACTION\s+(\S+)\s*\{(.+?)\}',
            text,
            re.DOTALL,
        )
        if not action_match:
            return result

        body = action_match.group(1)  # target
        content = action_match.group(2)  # {...} content

        # Parse key: "value" pairs from content
        for key in ("intent", "context", "mode", "input"):
            m = re.search(rf'{key}\s*:\s*"([^"]*)"', content)
            if m:
                result[key] = m.group(1)

        # mode defaults to "observe"
        if "mode" not in result or not result["mode"]:
            result["mode"] = "observe"

        return result

    def _write_devlog(self, result: dict, original_input: str):
        """将分析结果写入 DevLog。"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.DEVLOG_DIR, f"{today}_semantic_governance.md")

        # 自增分析编号（类级）
        type(self)._analysis_counter += 1
        seq = type(self)._analysis_counter

        entry = (
            f"\n## Analysis #{seq:03d}\n"
            f"- **Timestamp**: {datetime.now().isoformat()}\n"
            f"- **Input**: `{original_input[:200]}`\n"
            f"- **Intent**: {result['intent']}\n"
            f"- **Threat**: {result['threat_type']}\n"
            f"- **Risk**: {result['risk_score']}\n"
            f"- **Decision**: {result['governance_impact']}\n"
            f"- **Mapped Skill**: {result['mapped_skill'] or 'none'}\n"
        )

        # Append to log file
        if not os.path.exists(log_file):
            header = (
                f"# Semantic Governance Log — {today}\n"
                f"\n"
                f"Automated analysis log from SemanticGovernanceLayer.\n"
                f"Only BLOCKED and RESTRICTED decisions are recorded.\n"
            )
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(header)

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
