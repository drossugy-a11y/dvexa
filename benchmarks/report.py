"""Benchmark report generation.

Aggregates metrics from BenchmarkRunner results and produces
JSON reports and human-readable summaries.
"""

from __future__ import annotations

import json
from typing import Any


def _flatten_results(
    results: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Flatten nested results dict into a list of test records."""
    flat: list[dict[str, Any]] = []
    for category, tests in results.items():
        for test_name, metrics in tests.items():
            flat.append({
                "category": category,
                "test_name": test_name,
                **metrics,
            })
    return flat


def aggregate(results: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    """Aggregate results into summary statistics per category."""
    flat = _flatten_results(results)
    categories: dict[str, list[dict[str, Any]]] = {}
    for record in flat:
        cat = record["category"]
        categories.setdefault(cat, []).append(record)

    per_category: dict[str, dict[str, Any]] = {}
    total_tests = 0
    total_pass = 0
    total_fail = 0
    total_latency = 0.0

    for cat, records in sorted(categories.items()):
        n = len(records)
        passed = sum(1 for r in records if r.get("status") == "pass")
        failed = sum(1 for r in records if r.get("status") == "fail")
        latencies = [r.get("latency_ms", 0) for r in records if r.get("latency_ms") is not None]
        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        max_latency = round(max(latencies), 2) if latencies else 0.0
        failures = [
            {"test": r["test_name"], "error": r.get("notes", "")}
            for r in records if r.get("status") == "fail"
        ]

        per_category[cat] = {
            "total": n,
            "pass": passed,
            "fail": failed,
            "pass_rate": round(passed / n * 100, 1) if n > 0 else 0.0,
            "avg_latency_ms": avg_latency,
            "max_latency_ms": max_latency,
            "failures": failures,
        }
        total_tests += n
        total_pass += passed
        total_fail += failed

    all_latencies = [r.get("latency_ms", 0) for r in flat if r.get("latency_ms") is not None]
    overall_avg = round(sum(all_latencies) / len(all_latencies), 2) if all_latencies else 0.0
    overall_max = round(max(all_latencies), 2) if all_latencies else 0.0

    return {
        "summary": {
            "total_tests": total_tests,
            "total_pass": total_pass,
            "total_fail": total_fail,
            "pass_rate": round(total_pass / total_tests * 100, 1) if total_tests > 0 else 0.0,
            "overall_avg_latency_ms": overall_avg,
            "overall_max_latency_ms": overall_max,
        },
        "categories": per_category,
        "details": flat,
    }


def save_report(
    results: dict[str, dict[str, dict[str, Any]]],
    path: str,
) -> None:
    """Save aggregated benchmark report to a JSON file."""
    report = aggregate(results)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Report saved to {path}")


def print_summary(results: dict[str, dict[str, dict[str, Any]]]) -> None:
    """Print a human-readable summary of benchmark results."""
    report = aggregate(results)
    s = report["summary"]

    print("=" * 64)
    print("  DVexa Benchmark Suite — Summary")
    print("=" * 64)
    print(f"  Total tests : {s['total_tests']}")
    print(f"  Passed      : {s['total_pass']}")
    print(f"  Failed      : {s['total_fail']}")
    print(f"  Pass rate   : {s['pass_rate']}%")
    print(f"  Avg latency : {s['overall_avg_latency_ms']}ms")
    print(f"  Max latency : {s['overall_max_latency_ms']}ms")
    print()

    for cat_name, cat_data in sorted(report["categories"].items()):
        bar = "=" * 40
        print(f"  [{cat_name}]")
        print(f"    Total : {cat_data['total']}")
        print(f"    Pass  : {cat_data['pass']}")
        print(f"    Fail  : {cat_data['fail']}")
        print(f"    Rate  : {cat_data['pass_rate']}%")
        print(f"    Avg   : {cat_data['avg_latency_ms']}ms")
        print(f"    Max   : {cat_data['max_latency_ms']}ms")
        if cat_data["failures"]:
            print(f"    Failures:")
            for f in cat_data["failures"]:
                print(f"      - {f['test']}: {f['error']}")
        print()

    print("=" * 64)
