"""DVX Runtime Engine Flight Test v1.0

Phase 5: Final Assembly — 用真实模块实例化 DVXRuntimeEngine，
验证完整流水线 + 状态存储 + 回放引擎的集成。
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Real modules ──────────────────────────────────────────────────────────
from governance.dvx_loader import DVXLoader
from governance.semantic_governance import SemanticGovernanceLayer
from governance.assimilation_test_system import AssimilationTestSystem
from governance.assimilation_scheduler import AssimilationScheduler
from governance.skill_governor import SkillGovernor

from runtime import (
    DVXRuntimeEngine,
    RuntimeStateStore,
    ExecutionTrace,
    DVXReplayEngine,
    ExecutionStage,
    Event,
    EventStore,
)

# ── Output ────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(PROJECT_ROOT, "DvexaZSK", "logs")
REPORT_FILE = os.path.join(LOG_DIR, "runtime_engine_flight_test.md")
JSON_LOG = os.path.join(LOG_DIR, "runtime_engine_flight_test.json")

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


# ── Tests ─────────────────────────────────────────────────────────────────

class RuntimeEngineFlightTest:
    """Runtime Engine 飞行测试 — 验证 4 大核心能力。"""

    def __init__(self):
        self.store = RuntimeStateStore()
        self.results: dict[str, Any] = {
            "test_name": "DVX Runtime Engine Flight Test v1.0",
            "timestamp": datetime.now().isoformat(),
            "suites": {},
            "summary": {"total": 0, "passed": 0, "failed": 0},
        }
        self._engine = None

    # ── Suite A: Engine Run ──────────────────────────────────────────────

    def suite_a_engine_run(self, case: dict) -> dict[str, Any]:
        """验证 DVXRuntimeEngine.run() 完整执行。"""
        result: dict[str, Any] = {"checks": {}}
        ctx = self._engine.run(case["raw_input"])

        # A1: context 非空
        result["checks"]["a1_context_not_none"] = ctx is not None
        result["context"] = ctx

        # A2: trace_id 生成
        result["checks"]["a2_trace_id_valid"] = ctx.trace_id.startswith("trc-") and len(ctx.trace_id) > 4

        # A3: 至少 6 阶段（scheduler 可能产生多事件）
        stages_executed = [e.stage for e in ctx.events]
        required = {"load", "semantic", "validate", "schedule", "govern", "log"}
        result["checks"]["a3_all_stages_present"] = required.issubset(set(stages_executed))
        result["stages"] = list(set(stages_executed))

        # A4: 各阶段有 Event（至少有 6 个事件）
        result["checks"]["a4_min_6_events"] = len(ctx.events) >= 6
        result["event_count"] = len(ctx.events)

        # A5: 事件都是 Event 实例
        from runtime import Event as RTEvent
        result["checks"]["a5_all_are_events"] = all(isinstance(e, RTEvent) for e in ctx.events)

        # A6: 无错误事件
        error_events = [e for e in ctx.events if e.event_type == "error"]
        result["checks"]["a6_no_errors"] = len(error_events) == 0
        result["error_events"] = error_events

        # A7-A8: passed / risk_score 属性计算正确
        result["checks"]["a7_passed_boolean"] = isinstance(ctx.passed, bool)
        result["checks"]["a8_risk_score_float"] = isinstance(ctx.risk_score, float)

        # A9: total_latency_s > 0
        result["checks"]["a9_latency_positive"] = ctx.total_latency_s > 0

        # A10: overall_status == "complete"
        result["checks"]["a10_status_complete"] = ctx.overall_status == "complete"

        # A11: EventStore 已包含事件
        es = self._engine.event_store
        stored = es.read_by_trace(ctx.trace_id)
        result["checks"]["a11_events_in_store"] = len(stored) >= 6

        # A12: 向后兼容属性
        result["checks"]["a12_dvx_action_backcompat"] = bool(ctx.dvx_action.get("target"))

        return result

    # ── Suite B: ExecutionTrace ──────────────────────────────────────────

    def suite_b_execution_trace(self, ctx) -> dict[str, Any]:
        """验证 ExecutionTrace 工具类。"""
        result: dict[str, Any] = {"checks": {}}
        et = ExecutionTrace(ctx)

        # B1: summary 返回完整结构
        summary = et.summary()
        result["checks"]["b1_summary_complete"] = all(k in summary for k in
            ["trace_id", "total_stages", "completed_stages", "total_latency_s"])

        # B2: all() 返回 >= 6 个事件
        result["checks"]["b2_all_events"] = len(et.all()) >= 6
        result["event_count"] = len(et.all())

        # B3: stages() 包含所有必要阶段
        result["checks"]["b3_stages_complete"] = {"load", "semantic", "validate", "schedule", "govern", "log"}.issubset(set(et.stages()))

        # B4: errors() 正确
        result["checks"]["b4_errors_empty"] = len(et.errors()) == 0

        # B5: has_errors() 正确
        result["checks"]["b5_has_errors_false"] = not et.has_errors()

        # B6: decision_chain 提取
        dc = et.decision_chain()
        result["checks"]["b6_decision_chain"] = len(dc) >= 1

        # B7: to_text 可读
        text = et.to_text()
        result["checks"]["b7_to_text"] = "Execution Trace" in text

        # B8: to_json 可解析
        j = et.to_json()
        parsed = json.loads(j)
        result["checks"]["b8_to_json"] = parsed.get("trace_id") == ctx.trace_id

        # B9: get(stage) 按阶段查询
        load_event = et.get(ExecutionStage.LOAD)
        result["checks"]["b9_get_by_stage"] = load_event is not None and load_event.stage == "load"

        return result

    # ── Suite C: State Store ─────────────────────────────────────────────

    def suite_c_state_store(self, ctx) -> dict[str, Any]:
        """验证 RuntimeStateStore 持久化和查询。"""
        result: dict[str, Any] = {"checks": {}}

        # C1: write_state → 返回路径
        path = self.store.write_state(ctx)
        result["checks"]["c1_write_success"] = os.path.exists(path)
        result["trace_file"] = path

        # C2-C3: read_state → 返回投影 dict
        projection = self.store.read_state(ctx.trace_id)
        result["checks"]["c2_read_returns_dict"] = projection is not None and isinstance(projection, dict)
        result["checks"]["c3_trace_id_match"] = projection is not None and projection.get("trace_id") == ctx.trace_id

        if projection:
            # C4: 有 stages
            result["checks"]["c4_has_stages"] = projection.get("stage_count", 0) >= 6
            # C5-C6: risk_score 一致
            result["checks"]["c5_risk_consistent"] = abs(projection.get("risk_score", 0) - ctx.risk_score) < 0.01

        # C7: list_traces
        traces_list = self.store.list_traces()
        result["checks"]["c7_list_traces"] = ctx.trace_id in [t["trace_id"] for t in traces_list]

        # C8: query_state 过滤
        queried = self.store.query_state(risk_gt=0.0)
        result["checks"]["c8_query_returns_list"] = isinstance(queried, list)

        return result

    # ── Suite D: Replay Engine ───────────────────────────────────────────

    def suite_d_replay_engine(self, trace_id: str) -> dict[str, Any]:
        """验证 DVXReplayEngine 回放和差异分析。"""
        result: dict[str, Any] = {"checks": {}}
        replay = DVXReplayEngine(self.store.event_store)

        # D1: replay(trace_id) 完整
        full = replay.replay(trace_id)
        result["checks"]["d1_replay_complete"] = full is not None and full.get("trace_id") == trace_id
        result["replay_keys"] = list(full.keys()) if full else []

        # D2: replay 包含 events
        result["checks"]["d2_has_events"] = full is not None and len(full.get("events", [])) >= 6

        # D3: replay 包含 stages
        result["checks"]["d3_has_stages"] = full is not None and "stages" in full

        # D4: replay_stage 单阶段（返回事件列表）
        load_stage = replay.replay_stage(trace_id, "load")
        result["checks"]["d4_replay_stage"] = load_stage is not None and len(load_stage) >= 1 and load_stage[0].get("stage") == "load"

        # D5: 不存在 trace_id 返回 None
        none_ret = replay.replay("trc-nonexistent")
        result["checks"]["d5_nonexistent_returns_none"] = none_ret is None

        # D6: 不存在 trace_id 的 stage 返回 None
        none_stage = replay.replay_stage("trc-nonexistent", "load")
        result["checks"]["d6_nonexistent_stage"] = none_stage is None

        # D7: diff_execution — 自对比
        diff = replay.diff_execution(trace_id, trace_id)
        result["checks"]["d7_diff_self"] = "overall" in diff and "stage_diffs" in diff
        if "overall" in diff:
            # 自对比 divergence 应为 False
            result["checks"]["d7a_no_divergence"] = diff["overall"].get("divergence") is False

        return result

    # ── Suite E: DevLog Compatibility ────────────────────────────────────

    def suite_e_devlog(self, ctx) -> dict[str, Any]:
        """验证 DevLog 兼容写入。"""
        result: dict[str, Any] = {"checks": {}}

        log_file = self.store.append_to_devlog(ctx)
        result["checks"]["e1_devlog_written"] = log_file is not None and os.path.exists(log_file)
        result["devlog_file"] = log_file

        if log_file and os.path.exists(log_file):
            content = open(log_file, "r", encoding="utf-8").read()
            result["checks"]["e2_devlog_contains_trace_id"] = ctx.trace_id in content
            result["checks"]["e3_devlog_contains_risk"] = str(round(ctx.risk_score, 2)) in content

        return result

    # ── Runner ───────────────────────────────────────────────────────────

    def run_all(self):
        """执行全部测试套件。"""
        os.makedirs(LOG_DIR, exist_ok=True)

        print("=" * 70)
        print("  DVX Runtime Engine Flight Test v1.0")
        print("  Pipeline: DVX → SGL → ATS → Scheduler → Govern → Log")
        print("=" * 70)

        for case in TEST_CASES:
            cid = case["case_id"]
            print(f"\n{'#' * 70}")
            print(f"  Case {cid}: {case['title']}")
            print(f"{'#' * 70}")

            # ── Reset scheduler state ────────────────────────────────────
            scheduler = AssimilationScheduler()

            # ── Create engine ────────────────────────────────────────────
            self._engine = DVXRuntimeEngine(
                dvx_loader=DVXLoader(),
                sgl=SemanticGovernanceLayer(),
                ats=AssimilationTestSystem(),
                scheduler=scheduler,
                governor=SkillGovernor(),
            )

            suite_results: dict[str, Any] = {}

            # Suite A
            print(f"\n  ── Suite A: Engine Run ──")
            t0 = time.perf_counter()
            a_result = self.suite_a_engine_run(case)
            a_lat = time.perf_counter() - t0
            ctx = a_result.pop("context", None)
            a_passed = all(a_result["checks"].values())
            suite_results["suite_a_engine_run"] = {
                "passed": a_passed,
                "latency_s": round(a_lat, 5),
                "detail": a_result,
            }
            print(f"    {'✓' if a_passed else '✗'} Engine Run: {a_passed}")

            if ctx is None:
                suite_results["error"] = "Engine returned None context — cannot continue"
                self.results["suites"][f"case_{cid}"] = suite_results
                continue

            # Suite B
            print(f"  ── Suite B: ExecutionTrace ──")
            t0 = time.perf_counter()
            b_result = self.suite_b_execution_trace(ctx)
            b_lat = time.perf_counter() - t0
            b_passed = all(b_result["checks"].values())
            suite_results["suite_b_execution_trace"] = {
                "passed": b_passed,
                "latency_s": round(b_lat, 5),
                "detail": b_result,
            }
            print(f"    {'✓' if b_passed else '✗'} ExecutionTrace: {b_passed}")

            # Suite C
            print(f"  ── Suite C: State Store ──")
            t0 = time.perf_counter()
            c_result = self.suite_c_state_store(ctx)
            c_lat = time.perf_counter() - t0
            c_passed = all(c_result["checks"].values())
            suite_results["suite_c_state_store"] = {
                "passed": c_passed,
                "latency_s": round(c_lat, 5),
                "detail": c_result,
            }
            print(f"    {'✓' if c_passed else '✗'} State Store: {c_passed}")

            # Suite D
            print(f"  ── Suite D: Replay Engine ──")
            t0 = time.perf_counter()
            d_result = self.suite_d_replay_engine(ctx.trace_id)
            d_lat = time.perf_counter() - t0
            d_passed = all(d_result["checks"].values())
            suite_results["suite_d_replay_engine"] = {
                "passed": d_passed,
                "latency_s": round(d_lat, 5),
                "detail": d_result,
            }
            print(f"    {'✓' if d_passed else '✗'} Replay Engine: {d_passed}")

            # Suite E
            print(f"  ── Suite E: DevLog ──")
            t0 = time.perf_counter()
            e_result = self.suite_e_devlog(ctx)
            e_lat = time.perf_counter() - t0
            e_passed = all(e_result["checks"].values())
            suite_results["suite_e_devlog"] = {
                "passed": e_passed,
                "latency_s": round(e_lat, 5),
                "detail": e_result,
            }
            print(f"    {'✓' if e_passed else '✗'} DevLog: {e_passed}")

            # Case summary
            case_passed = all(
                suite_results[s]["passed"]
                for s in suite_results
                if s.startswith("suite_")
            )
            suite_results["case_passed"] = case_passed
            print(f"\n  >> Case {cid}: {'PASSED' if case_passed else 'FAILED'}")

            self.results["suites"][f"case_{cid}"] = suite_results

        # ── Cross-case: diff_execution ───────────────────────────────────
        print(f"\n{'#' * 70}")
        print(f"  Cross-Case: Diff Execution")
        print(f"{'#' * 70}")

        trace_ids = self.store.event_store.list_traces()
        for tid in trace_ids:
            print(f"  Trace in store: {tid}")

        replay = DVXReplayEngine(self.store.event_store)
        cross_diffs = []
        trace_ids = self.store.event_store.list_traces()
        if len(trace_ids) >= 2:
            diff = replay.diff_execution(trace_ids[0], trace_ids[1])
            cross_diffs.append(diff)
            diff_ok = "overall" in diff and "stage_diffs" in diff
            print(f"  Diff {trace_ids[0][:16]} vs {trace_ids[1][:16]}: {'✓' if diff_ok else '✗'}")
            report = replay.diff_execution_report(trace_ids[0], trace_ids[1])
            print(f"\n{report}\n")

        if len(trace_ids) >= 3:
            diff = replay.diff_execution(trace_ids[0], trace_ids[2])
            cross_diffs.append(diff)
            diff_ok = "overall" in diff and "stage_diffs" in diff
            print(f"  Diff {trace_ids[0][:16]} vs {trace_ids[2][:16]}: {'✓' if diff_ok else '✗'}")

        self.results["cross_case_diffs"] = cross_diffs

        # ── Summary ──────────────────────────────────────────────────────
        suite_count = 0
        pass_count = 0
        fail_count = 0
        for case_result in self.results["suites"].values():
            for s_name, s_data in case_result.items():
                if s_name.startswith("suite_"):
                    suite_count += 1
                    if s_data.get("passed"):
                        pass_count += 1
                    else:
                        fail_count += 1

        self.results["summary"] = {
            "total_suites": suite_count,
            "passed": pass_count,
            "failed": fail_count,
            "total_cases": len(TEST_CASES),
            "cases_passed": sum(
                1 for s in self.results["suites"].values() if s.get("case_passed")
            ),
            "cases_failed": sum(
                1 for s in self.results["suites"].values() if not s.get("case_passed")
            ),
        }

        print(f"\n{'=' * 70}")
        print(f"  FLIGHT TEST COMPLETE")
        print(f"{'=' * 70}")
        print(f"  Suites: {suite_count} total, {pass_count} passed, {fail_count} failed")
        print(f"  Cases:  {self.results['summary']['total_cases']} total, "
              f"{self.results['summary']['cases_passed']} passed")

        return self.results


def generate_report(results: dict) -> str:
    """生成可读的 Markdown 报告。"""
    lines = [
        f"# DVX Runtime Engine Flight Test Report\n",
        f"> **Generated**: {results['timestamp']}\n",
        f"> **Test**: {results['test_name']}\n",
        f"\n## Summary\n",
        f"\n| Metric | Value |",
        f"|--------|-------|",
        f"| Total Suites | {results['summary']['total_suites']} |",
        f"| Passed | {results['summary']['passed']} |",
        f"| Failed | {results['summary']['failed']} |",
        f"| Cases Passed | {results['summary']['cases_passed']}/{results['summary']['total_cases']} |",
    ]

    for case_id, case_result in results["suites"].items():
        lines.append(f"\n---\n")
        lines.append(f"\n## {case_id}\n")
        passed = case_result.get("case_passed", False)
        lines.append(f"\n**Status**: {'✅ PASSED' if passed else '❌ FAILED'}\n")

        for suite_name, suite_data in case_result.items():
            if not suite_name.startswith("suite_"):
                continue
            sp = suite_data.get("passed", False)
            icon = "✓" if sp else "✗"
            lat = suite_data.get("latency_s", 0)
            lines.append(f"\n### {suite_name} {icon}\n")
            lines.append(f"\n- **Passed**: {sp}")
            lines.append(f"\n- **Latency**: {lat}s")

            detail = suite_data.get("detail", {})
            checks = detail.get("checks", {})
            if checks:
                lines.append(f"\n- **Checks**:")
                for ck, cv in checks.items():
                    lines.append(f"\n  - {ck}: {'✓' if cv else '✗'}")

    return "\n".join(lines) + "\n"


def main():
    test = RuntimeEngineFlightTest()
    results = test.run_all()

    md_report = generate_report(results)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"\n  Report: {REPORT_FILE}")

    with open(JSON_LOG, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  JSON:   {JSON_LOG}")

    # Exit code based on results
    failed = results["summary"]["failed"] > 0 or results["summary"]["cases_failed"] > 0
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
