"""Drift Detector — 系统漂移检测

检测 skill 使用偏移、延迟漂移、失败模式变化。

以本地基线快照为对比参照，不依赖外部存储。
"""

from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, asdict

SNAPSHOT_FILE = os.path.join(os.path.dirname(__file__), ".baseline.json")


@dataclass
class DriftResult:
    drift_detected: bool = False
    drift_score: float = 0.0
    affected_components: list[str] | None = None


class DriftDetector:
    """漂移检测器 — 比较当前系统状态与历史基线。

    首次调用建立基线，后续调用比较变化。
    基线存储在本地 JSON，不写入任何控制层。
    """

    def __init__(self, snapshot_path: str = SNAPSHOT_FILE):
        self._snapshot_path = snapshot_path
        self._baseline = self._load_baseline()

    def detect(self, current_data: dict) -> dict:
        """检测系统漂移。无基线时建立基线并返回空检测。"""
        baseline = self._baseline

        if not baseline:
            self._save_baseline(current_data)
            self._baseline = dict(current_data)
            return {
                "drift_detected": False,
                "drift_score": 0.0,
                "affected_components": [],
                "note": "首次分析，已建立基线。下次调用将检测漂移。",
            }

        result = self._compare(baseline, current_data)
        self._save_baseline(current_data)
        self._baseline = dict(current_data)
        return result

    def _compare(self, baseline: dict, current: dict) -> dict:
        """比较基线 vs 当前，返回漂移检测结果。"""
        signals = []
        score = 0.0

        # 比较 skill usage 偏移
        bl_skills = {s["name"]: s for s in baseline.get("skill_summary", [])}
        cu_skills = {s["name"]: s for s in current.get("skill_summary", [])}

        for name, cs in cu_skills.items():
            bs = bl_skills.get(name)
            if not bs:
                continue

            usage_delta = cs["usage"] - bs["usage"]
            error_delta = cs["error_rate"] - bs["error_rate"]
            latency_delta = cs["latency"] - bs["latency"]

            if usage_delta > 0:
                signals.append(f"{name}: usage +{usage_delta}")
                score += 0.1
            if error_delta > 0.05:
                signals.append(f"{name}: error_rate +{error_delta:.2f}")
                score += 0.2
            if latency_delta > 1.0:
                signals.append(f"{name}: latency +{latency_delta:.2f}s")
                score += 0.15

        # 冲突数量变化
        bl_conflicts = len(baseline.get("conflicts", []))
        cu_conflicts = len(current.get("conflicts", []))
        if cu_conflicts > bl_conflicts:
            signals.append(f"conflicts: {bl_conflicts} → {cu_conflicts}")
            score += 0.25

        return {
            "drift_detected": score >= 0.3,
            "drift_score": round(score, 3),
            "affected_components": signals,
        }

    def _load_baseline(self) -> dict | None:
        try:
            with open(self._snapshot_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _save_baseline(self, data: dict):
        snapshot = {
            "timestamp": time.time(),
            "skill_summary": data.get("skill_summary", []),
            "conflicts": data.get("conflicts", []),
            "execution_count": data.get("execution_count", 0),
        }
        with open(self._snapshot_path, "w") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
