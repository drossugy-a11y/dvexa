"""Benchmark runner for DVexa Benchmark Suite.

Discovers test files, executes them, and collects timing/pass-fail metrics.
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any


# Add project root to sys.path so benchmarks/ can import project modules
_BENCHMARKS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BENCHMARKS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class BenchmarkRunner:
    """Discovers and runs benchmark tests, collecting metrics."""

    def __init__(self, benchmarks_dir: str | Path | None = None) -> None:
        self.benchmarks_dir = Path(benchmarks_dir or _BENCHMARKS_DIR)
        self.results: dict[str, dict[str, dict[str, Any]]] = {}

    # ── Discovery ───────────────────────────────────────────────────────

    def discover(self) -> dict[str, list[str]]:
        """Walk benchmarks/ and discover all test_*.py files per category.

        Returns: {category: [test_file_path, ...]}
        """
        categories: dict[str, list[str]] = {}
        for entry in sorted(self.benchmarks_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            test_files = sorted(entry.glob("test_*.py"))
            if test_files:
                categories[entry.name] = [str(f) for f in test_files]
        return categories

    # ── Test Loading & Execution ────────────────────────────────────────

    @staticmethod
    def _load_module(file_path: str) -> object:
        """Dynamically import a Python file as a module."""
        path = Path(file_path).resolve()
        module_name = f"_benchmark_{path.stem}"

        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _run_test_method(test_instance: object, method_name: str) -> dict[str, Any]:
        """Run a single test method and collect metrics."""
        start = time.perf_counter()
        status = "pass"
        notes = ""
        try:
            getattr(test_instance, method_name)()
        except AssertionError as e:
            status = "fail"
            notes = str(e)
        except Exception as e:
            status = "fail"
            notes = f"{type(e).__name__}: {e}"
        elapsed_ms = round((time.perf_counter() - start) * 1000, 3)

        return {
            "status": status,
            "latency_ms": elapsed_ms,
            "failures": 1 if status == "fail" else 0,
            "notes": notes,
        }

    def _run_file(self, file_path: str) -> dict[str, dict[str, Any]]:
        """Run all test classes in a single file and return metrics."""
        module = self._load_module(file_path)
        results: dict[str, dict[str, Any]] = {}

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not name.startswith("Test"):
                continue
            try:
                test_instance = obj()
            except Exception as e:
                results[name] = {
                    "status": "fail",
                    "latency_ms": 0.0,
                    "failures": 1,
                    "notes": f"Class instantiation failed: {e}",
                }
                continue

            for method_name, _ in inspect.getmembers(test_instance, inspect.ismethod):
                if not method_name.startswith("test_"):
                    continue
                test_key = f"{name}.{method_name}"
                results[test_key] = self._run_test_method(test_instance, method_name)

        return results

    # ── Run Commands ────────────────────────────────────────────────────

    def run_all(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Discover and run all benchmarks across all categories."""
        categories = self.discover()
        self.results = {}

        for category, files in sorted(categories.items()):
            self.results[category] = {}
            for file_path in files:
                file_results = self._run_file(file_path)
                self.results[category].update(file_results)

        return self.results

    def run_category(self, name: str) -> dict[str, dict[str, Any]]:
        """Run all benchmarks in a single category (baseline, isolation, resilience)."""
        category_dir = self.benchmarks_dir / name
        if not category_dir.is_dir():
            print(f"Category '{name}' not found in {self.benchmarks_dir}")
            return {}

        test_files = sorted(category_dir.glob("test_*.py"))
        if not test_files:
            print(f"No test files found in category '{name}'")
            return {}

        self.results[name] = {}
        for file_path in test_files:
            file_results = self._run_file(str(file_path))
            self.results[name].update(file_results)

        return self.results[name]

    # ── Output ──────────────────────────────────────────────────────────

    def print_summary(self) -> None:
        """Print a formatted summary table to stdout."""
        from benchmarks.report import print_summary

        print_summary(self.results)

    def _status_icon(self, status: str) -> str:
        return "PASS" if status == "pass" else "FAIL"

    def print_table(self) -> None:
        """Print a detailed test-by-test results table."""
        if not self.results:
            print("No results to display. Run benchmarks first.")
            return

        print(f"{'Category':<16} {'Test':<50} {'Status':<8} {'Latency(ms)':<12} Notes")
        print("-" * 140)
        for category, tests in sorted(self.results.items()):
            for test_name, metrics in sorted(tests.items()):
                status = self._status_icon(metrics["status"])
                latency = metrics["latency_ms"]
                notes = metrics.get("notes", "")
                notes_short = notes[:40] if notes else ""
                print(f"{category:<16} {test_name:<50} {status:<8} {latency:<12.3f} {notes_short}")


# ── CLI Entrypoint ──────────────────────────────────────────────────────


def main() -> None:
    """CLI entrypoint for running benchmarks."""
    import argparse

    parser = argparse.ArgumentParser(description="DVexa Benchmark Suite")
    parser.add_argument(
        "category",
        nargs="?",
        default=None,
        help="Category to run (baseline, isolation, resilience). Runs all if omitted.",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Save JSON report to this path",
    )
    parser.add_argument(
        "--table",
        action="store_true",
        help="Print detailed test-by-test table",
    )

    args = parser.parse_args()

    runner = BenchmarkRunner()

    if args.category:
        runner.run_category(args.category)
    else:
        runner.run_all()

    runner.print_summary()

    if args.table:
        print()
        runner.print_table()

    if args.save:
        from benchmarks.report import save_report
        save_report(runner.results, args.save)


if __name__ == "__main__":
    main()
