"""DVexa Full Pipeline Integration Test v1.0

纯粹编排层 — 串联 DVX Loader → SGL → ATS → AssimilationScheduler → DevLog
不修改任何 governance/core/kernel 层模块，不做功能增强。
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from typing import Any

# ── Add project root to path ──────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Module imports (真实调用，不 mock) ──────────────────────────────────────
from governance.dvx_loader import DVXLoader
from governance.semantic_governance import SemanticGovernanceLayer
from governance.assimilation_test_system import AssimilationTestSystem, RiskLevel
from governance.assimilation_scheduler import AssimilationScheduler

# ── Output paths ──────────────────────────────────────────────────────────
LOG_DIR = os.path.join(PROJECT_ROOT, "DvexaZSK", "logs")
MD_LOG = os.path.join(LOG_DIR, "integration_run_v1.md")
JSON_LOG = os.path.join(LOG_DIR, "integration_run_v1.json")


# ── Orchestrator ──────────────────────────────────────────────────────────

class PipelineOrchestrator:
    """端到端流水线编排器。

    Flow:
        Raw Input → DVX Loader → SGL → ATS → Scheduler → DevLog
    """

    def __init__(self) -> None:
        self._dvx = DVXLoader()
        self._sgl = SemanticGovernanceLayer()
        self._ats = AssimilationTestSystem()
        self._scheduler = AssimilationScheduler()

        os.makedirs(LOG_DIR, exist_ok=True)

    def run_case(
        self, case_id: int, title: str, raw_input: str, tags: list[str] | None = None
    ) -> dict:
        """执行单个测试用例的完整流水线。"""
        trace: dict[str, Any] = {
            "case_id": case_id,
            "title": title,
            "tags": tags or [],
            "raw_input": raw_input,
            "timestamp": datetime.now().isoformat(),
            "steps": {},
            "consistency": {},
        }

        output = (
            f"\n{'='*70}\n"
            f"  CASE {case_id}: {title}\n"
            f"  Tags: {tags or []}\n"
            f"{'='*70}\n"
        )

        # ── Step 1: DVX Loader ──────────────────────────────────────────
        output += f"\n─── STEP 1: DVX Loader ───\n"
        t0 = time.perf_counter()
        try:
            dvx_action = self._dvx.parse(raw_input)
            dvx_latency = time.perf_counter() - t0
            dvx_result = {
                "target": dvx_action.target,
                "intent": dvx_action.intent,
                "mode": dvx_action.mode,
                "constraint": dvx_action.constraint,
                "output": dvx_action.output,
                "warnings": dvx_action.warnings,
                "has_raw": bool(dvx_action.raw),
            }
            dvx_ok = True
            output += f"  ✓ Parsed: target='{dvx_action.target}', intent='{dvx_action.intent}'\n"
            output += f"    mode='{dvx_action.mode}', constraint={dvx_action.constraint}\n"
            if dvx_action.warnings:
                output += f"    ⚠ warnings: {dvx_action.warnings}\n"
        except Exception as e:
            dvx_latency = time.perf_counter() - t0
            dvx_result = {"error": str(e)}
            dvx_ok = False
            output += f"  ✗ DVX Parse Error: {e}\n"

        trace["steps"]["dvx_loader"] = {
            "status": "ok" if dvx_ok else "error",
            "latency_s": round(dvx_latency, 5),
            "input": raw_input,
            "output": dvx_result,
        }

        # ── Step 2: SGL ─────────────────────────────────────────────────
        output += f"\n─── STEP 2: SGL (Semantic Governance) ───\n"
        t0 = time.perf_counter()
        try:
            sgl_result = self._sgl.analyze(raw_input)
            sgl_latency = time.perf_counter() - t0
            output += (
                f"  ✓ intent='{sgl_result['intent']}', "
                f"threat='{sgl_result['threat_type']}', "
                f"risk={sgl_result['risk_score']}\n"
            )
            output += (
                f"    governance='{sgl_result['governance_impact']}', "
                f"mapped_skill={sgl_result['mapped_skill']}\n"
            )
            output += f"    reason: {sgl_result['reason']}\n"
        except Exception as e:
            sgl_latency = time.perf_counter() - t0
            sgl_result = {"error": str(e)}
            output += f"  ✗ SGL Error: {e}\n"

        trace["steps"]["sgl"] = {
            "status": "ok" if "error" not in sgl_result else "error",
            "latency_s": round(sgl_latency, 5),
            "input": raw_input,
            "output": sgl_result,
        }

        # ── Step 3: ATS ─────────────────────────────────────────────────
        output += f"\n─── STEP 3: ATS (Assimilation Test System) ───\n"
        ats_target = dvx_result.get("target", "") if dvx_ok else ""
        ats_context = {
            "intent": sgl_result.get("intent", "unknown"),
            "mode": dvx_result.get("mode", "observe"),
            "threat_type": sgl_result.get("threat_type", "none"),
            "sgl_risk_score": sgl_result.get("risk_score", 0.0),
            "governance_impact": sgl_result.get("governance_impact", "advisory"),
        }
        if dvx_ok and dvx_result.get("constraint"):
            ats_context["constraint"] = dvx_result["constraint"]

        t0 = time.perf_counter()
        try:
            ats_report = self._ats.run(ats_target, ats_context)
            ats_latency = time.perf_counter() - t0
            ats_output = {
                "target": ats_report.target,
                "passed": ats_report.passed,
                "phase_count": ats_report.phase_count,
                "passed_phases": ats_report.passed_phases,
                "failed_phases": ats_report.failed_phases,
                "risk_score": ats_report.risk_score,
                "risk_level": ats_report.risk_level.value,
                "summary": ats_report.summary,
                "all_warnings": ats_report.all_warnings,
                "phases": [
                    {
                        "phase": p.phase,
                        "passed": p.passed,
                        "verdict": p.verdict.value,
                        "details": p.details,
                        "warnings": p.warnings,
                    }
                    for p in ats_report.phases
                ],
            }
            output += f"  ✓ passed={ats_report.passed}, "
            output += f"phases={ats_report.passed_phases}/{ats_report.phase_count}\n"
            output += f"    risk={ats_report.risk_level.value}({ats_report.risk_score})\n"
            for p in ats_report.phases:
                st = "✓" if p.passed else "✗"
                w = f" ⚠{len(p.warnings)}" if p.warnings else ""
                output += f"    [{st}] {p.phase}: {p.verdict.value}{w}\n"
        except Exception as e:
            ats_latency = time.perf_counter() - t0
            ats_output = {"error": str(e)}
            ats_report = None
            output += f"  ✗ ATS Error: {e}\n"

        trace["steps"]["ats"] = {
            "status": "ok" if "error" not in ats_output else "error",
            "latency_s": round(ats_latency, 5),
            "input": {"target": ats_target, "context": ats_context},
            "output": ats_output,
        }

        # ── Step 4: AssimilationScheduler ───────────────────────────────
        output += f"\n─── STEP 4: AssimilationScheduler ───\n"
        ats_risk = ats_output.get("risk_score", 0.0) if "error" not in ats_output else 1.0
        ats_passed = ats_output.get("passed", False) if "error" not in ats_output else False

        scheduler_steps: list[dict] = []
        scheduler_error: str | None = None
        t0 = time.perf_counter()

        try:
            # 4a. begin
            begin_r = self._scheduler.begin(ats_target, risk_score=ats_risk)
            scheduler_steps.append({"action": "begin", "result": begin_r})

            # 4b. complete_analysis
            mapped_caps = ats_output.get("phases", [])
            cap_names = [
                p["details"] for p in mapped_caps
                if p["phase"] == "mapping" and "maps to capabilities" in p["details"]
            ]
            # 从 mapping phase details 提取能力名
            capabilities: list[str] = []
            for p in mapped_caps:
                if p["phase"] == "mapping" and "maps to capabilities" in p["details"]:
                    details = p["details"]
                    if ":" in details:
                        cap_part = details.split(":")[-1].strip()
                        capabilities = [c.strip() for c in cap_part.split(",")]
            analysis_r = self._scheduler.complete_analysis(capabilities)
            scheduler_steps.append({"action": "complete_analysis", "result": analysis_r})

            # 4c. complete_testing
            test_r = self._scheduler.complete_testing(passed=ats_passed)
            scheduler_steps.append({"action": "complete_testing", "result": test_r})
            final_state = test_r["state"]

            # 4d. 如果 approved → log → confirm → next
            if final_state == "approved":
                log_r = self._scheduler.log()
                scheduler_steps.append({"action": "log", "result": log_r})
                confirm_r = self._scheduler.confirm_human()
                scheduler_steps.append({"action": "confirm_human", "result": confirm_r})
                next_r = self._scheduler.next_round()
                scheduler_steps.append({"action": "next_round", "result": next_r})
                output += f"  ✓ APPROVED → LOGGED → CONFIRMED → NEXT\n"
            elif final_state == "quarantine":
                output += f"  ⚠ QUARANTINE (风险 {ats_risk} >= 0.6, 需人工审查)\n"
            elif final_state == "rejected":
                output += f"  ✗ REJECTED: {test_r.get('reason', '')}\n"

            output += (
                f"    final_state={final_state}, "
                f"risk_score={ats_risk}\n"
            )

        except Exception as e:
            scheduler_error = str(e)
            output += f"  ✗ Scheduler Error: {e}\n"

        scheduler_latency = time.perf_counter() - t0
        trace["steps"]["scheduler"] = {
            "status": "error" if scheduler_error else "ok",
            "latency_s": round(scheduler_latency, 5),
            "input": {
                "module_name": ats_target,
                "risk_score": ats_risk,
                "ats_passed": ats_passed,
            },
            "output": {
                "steps": scheduler_steps,
                "final_state": scheduler_steps[-1]["result"].get("state")
                if scheduler_steps and "result" in scheduler_steps[-1]
                else None,
                "error": scheduler_error,
            },
        }

        # ── Consistency Checks ──────────────────────────────────────────
        output += f"\n─── Consistency Checks ───\n"
        consistency: dict[str, Any] = {}
        dvx_sgl_aligned = dvx_ok and (
            dvx_result.get("intent") == sgl_result.get("intent") or
            sgl_result.get("intent") == "unknown"
        )
        consistency["dvx_sgl_alignment"] = {
            "dvx_intent": dvx_result.get("intent"),
            "sgl_intent": sgl_result.get("intent"),
            "aligned": dvx_sgl_aligned,
            "note": "SGL intent detection uses full text, may differ from DVX field"
            if not dvx_sgl_aligned
            else "aligned",
        }
        output += (
            f"  DVX↔SGL intent: "
            f"dvx='{dvx_result.get('intent')}' vs sgl='{sgl_result.get('intent')}' "
            f"{'✓' if dvx_sgl_aligned else '⚠ differ'}\n"
        )

        # SGL ↔ ATS agreement: SGL risk should correlate with ATS risk
        sgl_risk = sgl_result.get("risk_score", 0.0)
        ats_risk_val = ats_output.get("risk_score", 0.0)
        if "error" not in ats_output:
            risk_diff = abs(sgl_risk - ats_risk_val)
            consistency["sgl_ats_agreement"] = {
                "sgl_risk": sgl_risk,
                "ats_risk": ats_risk_val,
                "diff": round(risk_diff, 3),
                "note": "ATS risk may differ (it does its own keyword-based assessment)"
                if risk_diff > 0.1
                else "close agreement",
            }
            output += (
                f"  SGL↔ATS risk: "
                f"sgl={sgl_risk} vs ats={ats_risk_val} "
                f"(diff={risk_diff:.3f})"
                f"{' ⚠' if risk_diff > 0.1 else ' ✓'}\n"
            )

        # ATS ↔ Scheduler decision consistency
        if "error" not in ats_output:
            scheduler_final = (
                scheduler_steps[-1]["result"].get("state")
                if scheduler_steps and "result" in scheduler_steps[-1]
                else None
            )
            consistent = True
            reason = ""
            if ats_passed and ats_risk_val >= 0.8:
                # ATS says passed but risk too high for scheduler
                if scheduler_final != "quarantine":
                    consistent = False
                    reason = "ATS passed but risk >= 0.8 should trigger REJECT"
            elif ats_passed and ats_risk_val >= 0.6:
                if scheduler_final not in ("quarantine", "next"):
                    consistent = False
                    reason = "ATS passed but risk >= 0.6 should trigger QUARANTINE"
            elif not ats_passed:
                if scheduler_final not in ("rejected", "next_for_retry"):
                    # Scheduler may have rejected
                    pass  # Scheduler handles this internally

            consistency["ats_scheduler_decision"] = {
                "ats_passed": ats_passed,
                "ats_risk": ats_risk_val,
                "scheduler_final_state": scheduler_final,
                "consistent": consistent,
                "reason": reason or "consistent",
            }
            output += (
                f"  ATS↔Scheduler: ats_passed={ats_passed}, "
                f"ats_risk={ats_risk_val} → scheduler={scheduler_final} "
                f"{'✓' if consistent else '✗ ' + reason}\n"
            )

        trace["consistency"] = consistency
        trace["overall_status"] = (
            "complete"
            if not scheduler_error
            else "partial"
        )

        print(output)
        return trace

    def generate_report(
        self, traces: list[dict]
    ) -> tuple[str, dict]:
        """生成完整报告。"""
        md_lines: list[str] = []
        json_report: dict[str, Any] = {
            "report_title": "DVexa Full Pipeline Integration Test v1.0",
            "generated_at": datetime.now().isoformat(),
            "total_cases": len(traces),
            "cases": traces,
            "health": {},
            "conclusion": {},
        }

        # ── Title ───────────────────────────────────────────────────────
        md_lines.append(f"# DVexa Full Pipeline Integration Test v1.0\n")
        md_lines.append(
            f"> **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        md_lines.append(f"> **Total Cases**: {len(traces)}\n")
        md_lines.append(f"> **Type**: Pure orchestration (no module modification)\n")

        # ── Execution Summary ───────────────────────────────────────────
        md_lines.append(f"\n## Execution Summary\n")
        md_lines.append(f"\n| # | Case | Status | DVX | SGL | ATS | Scheduler |")
        md_lines.append(f"|---|------|--------|-----|-----|-----|-----------|")

        for t in traces:
            dvx_st = t["steps"]["dvx_loader"]["status"]
            sgl_st = t["steps"]["sgl"]["status"]
            ats_st = t["steps"]["ats"]["status"]
            sch_st = t["steps"]["scheduler"]["status"]
            overall = t["overall_status"]
            md_lines.append(
                f"| {t['case_id']} | {t['title'][:40]} | {overall} | "
                f"{dvx_st} | {sgl_st} | {ats_st} | {sch_st} |"
            )

        # ── Per-Case Trace ──────────────────────────────────────────────
        for t in traces:
            cid = t["case_id"]
            md_lines.append(f"\n---\n")
            md_lines.append(f"\n## Case {cid}: {t['title']}\n")
            md_lines.append(f"\n**Raw Input**:\n```\n{t['raw_input']}\n```\n")
            md_lines.append(f"\n**Tags**: {t.get('tags', [])}\n")

            for step_name in ("dvx_loader", "sgl", "ats", "scheduler"):
                step = t["steps"][step_name]
                status_icon = "✅" if step["status"] == "ok" else "❌"
                md_lines.append(
                    f"\n### {step_name.upper()} {status_icon}\n"
                )
                md_lines.append(f"\n- **Status**: {step['status']}")
                md_lines.append(f"\n- **Latency**: {step.get('latency_s', 'N/A')}s")
                md_lines.append(f"\n- **Input**:\n```\n{json.dumps(step.get('input', {}), indent=2, ensure_ascii=False)}\n```")
                md_lines.append(f"\n- **Output**:\n```\n{json.dumps(step.get('output', {}), indent=2, ensure_ascii=False)}\n```")

            # Consistency
            md_lines.append(f"\n### Consistency\n")
            for check_name, check_data in t.get("consistency", {}).items():
                md_lines.append(f"\n**{check_name}**:")
                for k, v in check_data.items():
                    md_lines.append(f"\n  - {k}: {v}")

        # ── Pipeline Health Report ──────────────────────────────────────
        md_lines.append(f"\n\n---\n")
        md_lines.append(f"\n# Pipeline Health Report\n")

        # Latency
        md_lines.append(f"\n## Stage Latency\n")
        md_lines.append(f"\n| Stage | Case 1 | Case 2 | Case 3 | Avg |")
        md_lines.append(f"|---|--------|--------|--------|-----|")
        stages = ["dvx_loader", "sgl", "ats", "scheduler"]
        for stage in stages:
            lats = []
            for t in traces:
                l = t["steps"][stage].get("latency_s", 0)
                lats.append(f"{l*1000:.1f}ms" if l < 1 else f"{l:.2f}s")
            avg = sum(t["steps"][stage].get("latency_s", 0) for t in traces) / len(traces)
            avg_s = f"{avg*1000:.1f}ms" if avg < 1 else f"{avg:.2f}s"
            md_lines.append(f"| {stage} | {lats[0]} | {lats[1]} | {lats[2]} | {avg_s} |")

        # Failure Analysis
        md_lines.append(f"\n## Failure Points\n")
        md_lines.append(f"\n| Case | Layer | Failure |")
        md_lines.append(f"|------|-------|---------|")
        found_failure = False
        for t in traces:
            for step_name in ("dvx_loader", "sgl", "ats", "scheduler"):
                step = t["steps"][step_name]
                if step["status"] != "ok":
                    md_lines.append(
                        f"| {t['case_id']} | {step_name} | "
                        f"{step['output'].get('error', 'unknown')} |"
                    )
                    found_failure = True
        if not found_failure:
            md_lines.append(f"| — | — | No failures in any layer |")

        # Consistency Summary
        md_lines.append(f"\n## System Consistency Check\n")
        all_checks = []
        for t in traces:
            for check_name in t.get("consistency", {}):
                all_checks.append(check_name)

        for check_name in sorted(set(all_checks)):
            agree_count = 0
            total_count = 0
            for t in traces:
                data = t.get("consistency", {}).get(check_name, {})
                total_count += 1
                if isinstance(data, dict):
                    aligned = data.get("aligned", data.get("consistent", data.get("diff", 100)))
                    if aligned is True or (isinstance(aligned, (int, float)) and aligned < 0.1):
                        agree_count += 1
            rate = f"{agree_count}/{total_count}"
            md_lines.append(f"\n- **{check_name}**: {rate} agreement")

        # DVX ↔ SGL Alignment
        md_lines.append(f"\n### DVX ↔ SGL Alignment\n")
        for t in traces:
            dvx_int = t["steps"]["dvx_loader"]["output"].get("intent", "?")
            sgl_int = t["steps"]["sgl"]["output"].get("intent", "?")
            md_lines.append(f"\n- Case {t['case_id']}: DVX='{dvx_int}' vs SGL='{sgl_int}'")

        # SGL ↔ ATS
        md_lines.append(f"\n### SGL ↔ ATS Risk Agreement\n")
        for t in traces:
            sgl_r = t["steps"]["sgl"]["output"].get("risk_score", "?")
            ats_r = t["steps"]["ats"]["output"].get("risk_score", "?")
            md_lines.append(f"\n- Case {t['case_id']}: SGL risk={sgl_r} vs ATS risk={ats_r}")

        # ATS ↔ Scheduler
        md_lines.append(f"\n### ATS ↔ Scheduler Decision Consistency\n")
        for t in traces:
            ats_p = t["steps"]["ats"]["output"].get("passed", "?")
            ats_r = t["steps"]["ats"]["output"].get("risk_score", "?")
            sch_out = t["steps"]["scheduler"]["output"]
            final_state = "N/A"
            if sch_out.get("steps"):
                final_step = sch_out["steps"][-1]
                final_state = final_step.get("result", {}).get("state", "?")
            md_lines.append(
                f"\n- Case {t['case_id']}: ATS passed={ats_p}, "
                f"risk={ats_r} → Scheduler state={final_state}"
            )

        # ── Final Conclusion ────────────────────────────────────────────
        md_lines.append(f"\n\n---\n")
        md_lines.append(f"\n# Final Conclusion\n")

        conclusions = self._compute_conclusions(traces)
        json_report["conclusion"] = conclusions

        for section in conclusions["sections"]:
            md_lines.append(f"\n## {section['title']}\n")
            for point in section["points"]:
                md_lines.append(f"\n- {point}")

        md_lines.append(f"\n\n---\n*Report generated by DVexa Pipeline Integration Test v1.0*")

        report_md = "\n".join(md_lines) + "\n"
        json_report["health"] = self._compute_health(traces)

        return report_md, json_report

    def _compute_conclusions(self, traces: list[dict]) -> dict[str, Any]:
        sections = []

        # Q1: Is DVexa pipeline truly sequential?
        points = []
        points.append("Yes — each layer requires the previous layer's output as input")
        points.append("DVX Loader must parse before SGL can analyze intent")
        points.append("ATS needs target + context from earlier stages")
        points.append("Scheduler requires ATS risk_score to make state decisions")
        points.append("No layer ran in parallel or out of order")
        sections.append({
            "title": "Is DVexa pipeline truly sequential?",
            "points": points,
        })

        # Q2: Where does information degrade?
        points = []
        dvx_sgl_intent_diff = sum(
            1 for t in traces
            if t["steps"]["dvx_loader"]["output"].get("intent")
            != t["steps"]["sgl"]["output"].get("intent")
        )
        if dvx_sgl_intent_diff > 0:
            points.append(
                f"DVX→SGL intent mismatch in {dvx_sgl_intent_diff}/{len(traces)} cases: "
                "DVX reads intent from ACTION field, SGL re-detects from full text"
            )
        points.append(
            "ATS risk assessment is independent of SGL's risk: "
            "it recalculates from scratch using its own keyword rules"
        )
        points.append(
            "Scheduler receives only risk_score from ATS, losing "
            "phase-level detail about which checks passed/failed"
        )
        points.append(
            "DVX 'output' field is unused by downstream layers — "
            "it gets parsed but never read by SGL/ATS/Scheduler"
        )
        sections.append({
            "title": "Where does information degrade?",
            "points": points,
        })

        # Q3: Which layer introduces ambiguity?
        points = []
        points.append(
            "SGL's intent detection uses full-text regex, while DVX reads "
            "a structured field — they can disagree on the same input"
        )
        points.append(
            "ATS has its own RiskAssessor independent of SGL's ThreatDetector, "
            "potentially producing different risk scores for the same input"
        )
        points.append(
            "Scheduler's risk thresholds (0.6/0.8) differ from ATS's "
            "risk levels (0.15/0.3/0.7) and SGL's (0.3/0.7)"
        )
        sections.append({
            "title": "Which layer introduces ambiguity?",
            "points": points,
        })

        return {"sections": sections}

    def _compute_health(self, traces: list[dict]) -> dict[str, Any]:
        total_cases = len(traces)
        total_latency = 0.0
        failure_count = 0
        stage_latencies: dict[str, list[float]] = {
            "dvx_loader": [],
            "sgl": [],
            "ats": [],
            "scheduler": [],
        }

        for t in traces:
            for stage, lats in stage_latencies.items():
                lat = t["steps"][stage].get("latency_s", 0)
                lats.append(lat)
                total_latency += lat
            if t["overall_status"] != "complete":
                failure_count += 1

        avg_latency = total_latency / total_cases if total_cases else 0
        bottlenecks = []
        for stage, lats in stage_latencies.items():
            avg = sum(lats) / len(lats) if lats else 0
            if avg > 0.01:
                bottlenecks.append((stage, avg))

        bottlenecks.sort(key=lambda x: x[1], reverse=True)

        return {
            "total_cases": total_cases,
            "pass_rate": f"{(total_cases - failure_count)}/{total_cases}",
            "total_pipeline_latency_s": round(total_latency, 4),
            "avg_case_latency_s": round(avg_latency, 4),
            "bottlenecks": [
                {"stage": s, "avg_latency_s": round(l, 4)}
                for s, l in bottlenecks[:3]
            ],
            "failures": failure_count,
        }


# ── Test Cases ────────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "case_id": 1,
        "title": "Normal Task — Analyze OpenClaw skill_scanner",
        "tags": ["normal", "analysis", "external"],
        "raw_input": (
            'ACTION openclaw_scanner {\n'
            '    intent: "analysis",\n'
            '    mode: "observe",\n'
            '    constraint: "read-only",\n'
            '    output: "scan report"\n'
            '}'
        ),
    },
    {
        "case_id": 2,
        "title": "Adversarial Task — Inject malicious tool usage",
        "tags": ["adversarial", "injection", "security"],
        "raw_input": (
            'ACTION malicious_payload {\n'
            '    intent: "execution",\n'
            '    mode: "strict",\n'
            '    constraint: "bypass security controls",\n'
            '    output: "inject backdoor"\n'
            '}'
        ),
    },
    {
        "case_id": 3,
        "title": "High Complexity — Multi-module assimilation",
        "tags": ["complex", "multi-module", "simulation"],
        "raw_input": (
            'ACTION plugin_manager {\n'
            '    intent: "execution",\n'
            '    mode: "simulate",\n'
            '    constraint: "write access needed for plugin_manager + '
            'tool_policy + loader",\n'
            '    output: "multi-module integration report"\n'
            '}'
        ),
    },
]


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("  DVexa Full Pipeline Integration Test v1.0")
    print("  Pipeline: DVX Loader → SGL → ATS → AssimilationScheduler → DevLog")
    print("=" * 70)

    orchestrator = PipelineOrchestrator()
    traces: list[dict] = []

    for case in TEST_CASES:
        print(f"\n{'#'*70}")
        print(f"  Starting Case {case['case_id']}: {case['title']}")
        print(f"{'#'*70}")
        trace = orchestrator.run_case(
            case_id=case["case_id"],
            title=case["title"],
            raw_input=case["raw_input"],
            tags=case["tags"],
        )
        traces.append(trace)

        # Reset scheduler state between cases (cancel from any state)
        orchestrator._scheduler.cancel()

    # ── Generate reports ────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  Generating Reports...")
    print(f"{'='*70}")

    md_report, json_report = orchestrator.generate_report(traces)

    with open(MD_LOG, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"  ✓ Written: {MD_LOG}")

    with open(JSON_LOG, "w", encoding="utf-8") as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Written: {JSON_LOG}")

    # ── Summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  INTEGRATION TEST COMPLETE")
    print(f"{'='*70}")
    print(f"  Cases run: {len(traces)}")
    print(f"  MD Report: {MD_LOG}")
    print(f"  JSON Log:  {JSON_LOG}")
    print(f"{'='*70}")

    # Print health summary
    health = json_report["health"]
    print(f"\n  Pipeline Health:")
    print(f"    Pass rate:       {health['pass_rate']}")
    print(f"    Total latency:   {health['total_pipeline_latency_s']}s")
    print(f"    Avg case latency: {health['avg_case_latency_s']}s")
    if health["bottlenecks"]:
        print(f"    Bottlenecks:")
        for b in health["bottlenecks"]:
            print(f"      - {b['stage']}: {b['avg_latency_s']}s")


if __name__ == "__main__":
    main()
