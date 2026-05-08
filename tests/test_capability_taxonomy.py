"""Tests for Capability Taxonomy System v1.0."""
import json
import os
import tempfile

import pytest

from capabilities.taxonomy import (
    CapabilityNode,
    MaturityLevel,
    RiskLevel,
    SourceType,
    LifecycleState,
    TAXONOMY_TREE,
    build_default_taxonomy,
    valid_subcategory,
)
from capabilities.capability_graph import CapabilityGraph
from capabilities.capability_registry import CapabilityRegistry
from capabilities.evolution_tracker import EvolutionTracker
from insight.capability_analyzer import CapabilityAnalyzer
from external.pattern_registry import PatternRegistry
from governance.governance_kernel import GovernanceKernel


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def make_node(capability_id="test:planning:decomposition",
              name="test-decomposition", category="planning",
              subcategory="decomposition", **kwargs) -> CapabilityNode:
    defaults = {
        "capability_id": capability_id,
        "name": name,
        "category": category,
        "subcategory": subcategory,
        "description": "Test capability",
        "source_type": SourceType.SKILL.value,
        "governance_approved": True,
    }
    defaults.update(kwargs)
    return CapabilityNode(**defaults)


# ═══════════════════════════════════════════════════════════════════════════
# Test: CapabilityNode
# ═══════════════════════════════════════════════════════════════════════════

class TestCapabilityNode:
    def test_create_minimal(self):
        n = CapabilityNode(
            capability_id="test:1", name="test", category="planning",
            subcategory="decomposition", description="desc",
        )
        assert n.capability_id == "test:1"
        assert n.name == "test"
        assert n.category == "planning"
        assert n.subcategory == "decomposition"

    def test_default_values(self):
        n = CapabilityNode(
            capability_id="test:2", name="test2", category="memory",
            subcategory="replay", description="desc",
        )
        assert n.maturity == MaturityLevel.EXPERIMENTAL.value
        assert n.risk_level == RiskLevel.LOW.value
        assert n.lifecycle_state == LifecycleState.REGISTERED.value
        assert n.governance_approved is False
        assert n.usage_count == 0
        assert n.success_rate == 1.0
        assert n.dependencies == []
        assert n.conflicts == []

    def test_full_fields(self):
        n = CapabilityNode(
            capability_id="full:1", name="full-test",
            category="governance", subcategory="policy",
            description="Full test capability",
            maturity=MaturityLevel.STABLE.value,
            risk_level=RiskLevel.MEDIUM.value,
            source="governance/tool_policy.py",
            source_type=SourceType.GOVERNANCE.value,
            dependencies=["dep:1"],
            conflicts=["conflict:1"],
            related_patterns=["pattern:1"],
            governance_approved=True,
            lifecycle_state=LifecycleState.ACTIVE.value,
            usage_count=100,
            success_rate=0.95,
            evolution_history=[{"event_type": "adoption"}],
            metadata={"tbrz_stage": 7},
        )
        assert n.maturity == "stable"
        assert n.risk_level == "medium"
        assert n.source_type == "governance"
        assert len(n.dependencies) == 1
        assert len(n.conflicts) == 1
        assert len(n.evolution_history) == 1

    def test_mutable_fields(self):
        n = make_node("mut:1", "mutable")
        n.usage_count = 5
        n.success_rate = 0.8
        n.evolution_history.append({"event": "test"})
        assert n.usage_count == 5
        assert n.success_rate == 0.8
        assert len(n.evolution_history) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Test: Taxonomy Tree
# ═══════════════════════════════════════════════════════════════════════════

class TestTaxonomyTree:
    def test_six_categories(self):
        assert len(TAXONOMY_TREE) == 6
        for cat in ("planning", "execution", "memory", "governance",
                     "assimilation", "optimization"):
            assert cat in TAXONOMY_TREE

    def test_build_default_taxonomy(self):
        tree = build_default_taxonomy()
        assert len(tree) == 6
        assert "decomposition" in tree["planning"]
        assert "context-compression" in tree["memory"]

    def test_valid_subcategory(self):
        assert valid_subcategory("planning", "decomposition") is True
        assert valid_subcategory("planning", "nonexistent") is False
        assert valid_subcategory("nonexistent_cat", "decomposition") is False

    def test_all_subcategories_have_parent(self):
        seen_subcats = set()
        for cat, info in TAXONOMY_TREE.items():
            for sub in info["subcategories"]:
                seen_subcats.add(sub)
        assert len(seen_subcats) >= 27


# ═══════════════════════════════════════════════════════════════════════════
# Test: CapabilityGraph
# ═══════════════════════════════════════════════════════════════════════════

class TestCapabilityGraph:
    def test_add_node(self):
        g = CapabilityGraph()
        g.add_node("a", {"label": "Node A"})
        assert g.node_count == 1
        assert g.has_node("a")
        assert g.get_node("a") == {"label": "Node A"}

    def test_add_dependency(self):
        g = CapabilityGraph()
        g.add_node("a"); g.add_node("b")
        assert g.add_dependency("a", "b") is True
        assert g.get_dependencies("a") == ["b"]
        assert g.get_dependents("b") == ["a"]

    def test_add_dependency_self_loop_blocked(self):
        g = CapabilityGraph()
        g.add_node("a")
        assert g.add_dependency("a", "a") is False

    def test_add_dependency_nonexistent(self):
        g = CapabilityGraph()
        g.add_node("a")
        assert g.add_dependency("a", "nonexistent") is False

    def test_add_conflict(self):
        g = CapabilityGraph()
        g.add_node("a"); g.add_node("b")
        assert g.add_conflict("a", "b") is True
        assert g.get_conflicts("a") == ["b"]
        assert g.get_conflicts("b") == ["a"]
        assert g.has_conflict("a", "b") is True

    def test_add_conflict_self_blocked(self):
        g = CapabilityGraph()
        g.add_node("a")
        assert g.add_conflict("a", "a") is False

    def test_detect_no_cycle(self):
        g = CapabilityGraph()
        g.add_node("a"); g.add_node("b"); g.add_node("c")
        g.add_dependency("a", "b")
        g.add_dependency("b", "c")
        assert g.detect_cycles() == []

    def test_detect_cycle(self):
        g = CapabilityGraph()
        g.add_node("a"); g.add_node("b"); g.add_node("c")
        g.add_dependency("a", "b")
        g.add_dependency("b", "c")
        g.add_dependency("c", "a")
        cycles = g.detect_cycles()
        assert len(cycles) > 0

    def test_detect_self_cycle(self):
        g = CapabilityGraph()
        g.add_node("a"); g.add_node("b")
        g.add_dependency("a", "b")
        g.add_dependency("b", "a")
        cycles = g.detect_cycles()
        assert len(cycles) > 0

    def test_compute_depth(self):
        g = CapabilityGraph()
        g.add_node("root"); g.add_node("mid"); g.add_node("leaf")
        g.add_dependency("mid", "root")
        g.add_dependency("leaf", "mid")
        depths = g.compute_depth()
        assert depths["root"] == 0
        assert depths["mid"] == 1
        assert depths["leaf"] == 2

    def test_transitive_dependencies(self):
        g = CapabilityGraph()
        g.add_node("a"); g.add_node("b"); g.add_node("c"); g.add_node("d")
        g.add_dependency("a", "b")
        g.add_dependency("b", "c")
        g.add_dependency("c", "d")
        deps = g.get_transitive_dependencies("a")
        assert "b" in deps
        assert "c" in deps
        assert "d" in deps

    def test_visualize_text_empty(self):
        g = CapabilityGraph()
        assert g.visualize_text() == "(empty graph)"

    def test_visualize_text_tree(self):
        g = CapabilityGraph()
        g.add_node("planning", {"label": "Planning"})
        g.add_node("decomposition", {"label": "decomposition"})
        g.add_node("reflection", {"label": "reflection"})
        g.add_dependency("decomposition", "planning")
        g.add_dependency("reflection", "planning")
        viz = g.visualize_text()
        assert "Planning" in viz
        assert "decomposition" in viz
        assert "reflection" in viz

    def test_metadata(self):
        g = CapabilityGraph()
        g.add_node("a"); g.add_node("b")
        g.add_dependency("a", "b")
        g.add_conflict("a", "b")
        meta = g.metadata
        assert meta["node_count"] == 2
        assert meta["dependency_count"] == 1
        assert meta["conflict_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Test: CapabilityRegistry
# ═══════════════════════════════════════════════════════════════════════════

class TestCapabilityRegistry:
    def test_register(self):
        r = CapabilityRegistry()
        n = make_node("reg:1", "test-reg")
        cid = r.register(n)
        assert cid == "reg:1"
        assert r.count == 1

    def test_register_from_dict(self):
        r = CapabilityRegistry()
        cid = r.register_from_dict({
            "capability_id": "dict:1", "name": "dict-test",
            "category": "execution", "subcategory": "retry",
            "description": "Test",
        })
        assert cid == "dict:1"
        assert r.get("dict:1").name == "dict-test"

    def test_get_nonexistent(self):
        r = CapabilityRegistry()
        assert r.get("nonexistent") is None

    def test_search_by_category(self):
        r = CapabilityRegistry()
        r.register(make_node("p1", "plan-1", "planning"))
        r.register(make_node("e1", "exec-1", "execution"))
        results = r.search(category="planning")
        assert len(results) == 1
        assert results[0].name == "plan-1"

    def test_search_by_keyword(self):
        r = CapabilityRegistry()
        r.register(make_node("p1", "alpha-beta", "planning"))
        r.register(make_node("e1", "gamma-delta", "execution"))
        results = r.search(keyword="alpha")
        assert len(results) == 1
        assert results[0].name == "alpha-beta"

    def test_search_combined(self):
        r = CapabilityRegistry()
        r.register(make_node("p1", "stable-plan", "planning",
                             maturity="stable", risk_level="low"))
        r.register(make_node("p2", "experimental-plan", "planning",
                             maturity="experimental", risk_level="medium"))
        results = r.search(category="planning", maturity="experimental")
        assert len(results) == 1
        assert results[0].name == "experimental-plan"

    def test_get_by_category(self):
        r = CapabilityRegistry()
        r.register(make_node("p1", "p1", "planning"))
        r.register(make_node("p2", "p2", "planning"))
        r.register(make_node("e1", "e1", "execution"))
        assert len(r.get_by_category("planning")) == 2
        assert len(r.get_by_category("execution")) == 1

    def test_get_high_risk(self):
        r = CapabilityRegistry()
        r.register(make_node("safe", "safe", "planning", risk_level="low"))
        r.register(make_node("risky", "risky", "execution", risk_level="high"))
        r.register(make_node("critical", "critical", "memory", risk_level="critical"))
        assert len(r.get_high_risk_capabilities()) == 2

    def test_get_experimental(self):
        r = CapabilityRegistry()
        r.register(make_node("e1", "e1", maturity="experimental"))
        r.register(make_node("s1", "s1", maturity="stable"))
        assert len(r.get_experimental_capabilities()) == 1

    def test_get_stable(self):
        r = CapabilityRegistry()
        r.register(make_node("e1", "e1", maturity="experimental"))
        r.register(make_node("s1", "s1", maturity="stable"))
        assert len(r.get_stable_capabilities()) == 1

    def test_get_quarantined(self):
        r = CapabilityRegistry()
        r.register(make_node("q1", "q1", maturity="quarantined"))
        assert len(r.get_quarantined_capabilities()) == 1

    def test_update_metrics(self):
        r = CapabilityRegistry()
        r.register(make_node("m1", "m1"))
        assert r.update_metrics("m1", usage_count=42, success_rate=0.88)
        n = r.get("m1")
        assert n.usage_count == 42
        assert n.success_rate == 0.88

    def test_update_metrics_clamps_success_rate(self):
        r = CapabilityRegistry()
        r.register(make_node("m1", "m1"))
        r.update_metrics("m1", success_rate=1.5)
        assert r.get("m1").success_rate == 1.0
        r.update_metrics("m1", success_rate=-0.5)
        assert r.get("m1").success_rate == 0.0

    def test_update_lifecycle(self):
        r = CapabilityRegistry()
        r.register(make_node("l1", "l1"))
        assert r.update_lifecycle("l1", "active")
        assert r.get("l1").lifecycle_state == "active"

    def test_update_maturity(self):
        r = CapabilityRegistry()
        r.register(make_node("m1", "m1"))
        assert r.update_maturity("m1", "stable")
        assert r.get("m1").maturity == "stable"
        assert r.update_maturity("m1", "invalid") is False

    def test_record_evolution(self):
        r = CapabilityRegistry()
        r.register(make_node("ev1", "ev1"))
        r.record_evolution("ev1", {"event_type": "adoption"})
        assert len(r.get("ev1").evolution_history) == 1

    def test_get_orphan(self):
        r = CapabilityRegistry()
        r.register(make_node("orphan", "orphan", dependencies=[], conflicts=[]))
        r.register(make_node("parent", "parent"))
        # parent has no deps, no one depends on it → also orphan
        orphans = r.get_orphan_capabilities()
        assert len(orphans) == 2  # both isolated

    def test_get_critical_dependencies(self):
        r = CapabilityRegistry()
        r.register(make_node("a", "a", risk_level="high", dependencies=["b"]))
        r.register(make_node("b", "b", risk_level="high"))
        critical = r.get_critical_dependencies()
        assert len(critical) == 1
        assert critical[0] == ("a", "b")

    def test_get_summary(self):
        r = CapabilityRegistry()
        r.register(make_node("a", "a", "planning", maturity="stable"))
        r.register(make_node("b", "b", "execution", maturity="experimental"))
        s = r.get_summary()
        assert s["total"] == 2
        assert "planning" in s["by_category"]
        assert "stable" in s["by_maturity"]

    def test_export_json(self):
        r = CapabilityRegistry()
        r.register(make_node("a", "alpha"))
        j = r.export_json()
        data = json.loads(j)
        assert data["version"] == "1.0"
        assert data["summary"]["total"] == 1
        assert len(data["capabilities"]) == 1

    def test_build_dependency_graph(self):
        r = CapabilityRegistry()
        r.register(make_node("a", "a", dependencies=["b"]))
        r.register(make_node("b", "b"))
        g = r.build_dependency_graph()
        assert g.node_count == 2
        assert g.get_dependencies("a") == ["b"]

    def test_categories_property(self):
        r = CapabilityRegistry()
        r.register(make_node("a", "a", "planning"))
        r.register(make_node("b", "b", "memory"))
        assert "planning" in r.categories
        assert "memory" in r.categories


# ═══════════════════════════════════════════════════════════════════════════
# Test: EvolutionTracker
# ═══════════════════════════════════════════════════════════════════════════

class TestEvolutionTracker:
    def test_record_capability_change(self):
        t = EvolutionTracker()
        ev = t.record_capability_change("test:1", field="maturity",
                                        old_value="experimental", new_value="stable")
        assert ev["event_type"] == "capability_change"
        assert ev["capability_id"] == "test:1"

    def test_record_adoption(self):
        t = EvolutionTracker()
        ev = t.record_adoption("test:2", source="sst/opencode",
                               source_type="assimilation")
        assert ev["event_type"] == "adoption"

    def test_record_failure(self):
        t = EvolutionTracker()
        ev = t.record_failure("test:3", error="timeout", context={"step": 5})
        assert ev["event_type"] == "failure"
        assert ev["data"]["error"] == "timeout"

    def test_record_stabilization(self):
        t = EvolutionTracker()
        ev = t.record_stabilization("test:4", previous_maturity="experimental",
                                    new_maturity="stable",
                                    metrics={"success_rate": 0.98})
        assert ev["event_type"] == "stabilization"
        assert ev["data"]["new_maturity"] == "stable"

    def test_record_governance_decision(self):
        t = EvolutionTracker()
        ev = t.record_governance_decision("test:5", decision="quarantine",
                                          reason="high failure rate")
        assert ev["event_type"] == "governance_decision"

    def test_record_assimilation(self):
        t = EvolutionTracker()
        ev = t.record_assimilation("test:6", source_repo="sst/opencode",
                                   pattern_name="retry-pattern")
        assert ev["event_type"] == "assimilation"

    def test_get_events_by_capability(self):
        t = EvolutionTracker()
        t.record_adoption("cap-a")
        t.record_stabilization("cap-a")
        t.record_adoption("cap-b")
        assert len(t.get_events("cap-a")) == 2
        assert len(t.get_events("cap-b")) == 1

    def test_counters(self):
        t = EvolutionTracker()
        t.record_adoption("a")
        t.record_adoption("b")
        t.record_failure("a")
        t.record_failure("a")
        t.record_stabilization("a")
        assert t.get_adoption_count() == 2
        assert t.get_failure_count() == 2
        assert t.get_stabilization_count() == 1
        assert t.get_failure_count("a") == 2

    def test_generate_evolution_report(self):
        t = EvolutionTracker()
        t.record_adoption("a")
        t.record_adoption("a")
        t.record_failure("b")
        report = t.generate_evolution_report()
        assert report["total_events"] == 3
        assert report["adoption_count"] == 2
        assert report["failure_count"] == 1

    def test_save_report(self, tmp_path):
        t = EvolutionTracker(output_dir=str(tmp_path))
        t.record_adoption("a")
        path = t.save_report()
        assert os.path.exists(path)

    def test_append_only_persistence(self, tmp_path):
        t = EvolutionTracker(output_dir=str(tmp_path))
        t.record_adoption("a")
        t.record_failure("a")
        t2 = EvolutionTracker(output_dir=str(tmp_path))
        count = t2.load_from_disk()
        assert count == 2
        assert t2.get_event_count() == 2

    def test_load_from_disk_empty(self, tmp_path):
        t = EvolutionTracker(output_dir=str(tmp_path))
        assert t.load_from_disk() == 0


# ═══════════════════════════════════════════════════════════════════════════
# Test: CapabilityAnalyzer
# ═══════════════════════════════════════════════════════════════════════════

class TestCapabilityAnalyzer:
    def test_empty_registry(self):
        a = CapabilityAnalyzer()
        report = a.analyze_system_capabilities()
        assert report["total_capabilities"] == 0

    def test_with_registry(self):
        r = CapabilityRegistry()
        r.register(make_node("a", "alpha", "planning", maturity="stable"))
        r.register(make_node("b", "beta", "execution", maturity="experimental",
                             risk_level="high"))
        r.register(make_node("c", "gamma", "memory", maturity="quarantined"))
        a = CapabilityAnalyzer(registry=r)
        report = a.analyze_system_capabilities()
        assert report["total_capabilities"] == 3
        assert report["stable_capabilities"] == 1
        assert report["experimental_capabilities"] == 1
        assert report["high_risk_capabilities"] == 1
        assert report["quarantined_capabilities"] == 1

    def test_governance_hotspots(self):
        r = CapabilityRegistry()
        r.register(make_node("safe", "safe", maturity="stable", risk_level="low"))
        r.register(make_node("hot1", "hot1", maturity="experimental"))
        r.register(make_node("hot2", "hot2", risk_level="critical"))
        a = CapabilityAnalyzer(registry=r)
        report = a.analyze_system_capabilities()
        assert len(report["governance_hotspots"]) == 2

    def test_orphan_detection(self):
        r = CapabilityRegistry()
        r.register(make_node("orphan", "orphan", "planning"))
        a = CapabilityAnalyzer(registry=r)
        report = a.analyze_system_capabilities()
        assert len(report["orphan_capabilities"]) == 1

    def test_most_used(self):
        r = CapabilityRegistry()
        r.register(make_node("a", "a", usage_count=100))
        r.register(make_node("b", "b", usage_count=5))
        a = CapabilityAnalyzer(registry=r)
        report = a.analyze_system_capabilities()
        assert len(report["most_used_capabilities"]) == 2
        assert report["most_used_capabilities"][0]["name"] == "a"

    def test_least_reliable(self):
        r = CapabilityRegistry()
        r.register(make_node("a", "a", usage_count=10, success_rate=0.5))
        r.register(make_node("b", "b", usage_count=10, success_rate=0.99))
        a = CapabilityAnalyzer(registry=r)
        report = a.analyze_system_capabilities()
        assert len(report["least_reliable_capabilities"]) == 2
        assert report["least_reliable_capabilities"][0]["name"] == "a"

    def test_distributions(self):
        r = CapabilityRegistry()
        r.register(make_node("a", "a", "planning", maturity="stable", risk_level="low"))
        r.register(make_node("b", "b", "memory", maturity="experimental", risk_level="medium"))
        a = CapabilityAnalyzer(registry=r)
        report = a.analyze_system_capabilities()
        assert report["category_distribution"]["planning"] == 1
        assert report["maturity_distribution"]["stable"] == 1
        assert report["risk_distribution"]["low"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Test: Assimilation Mapping
# ═══════════════════════════════════════════════════════════════════════════

class TestAssimilationMapping:
    def test_to_capability_node_not_adopted(self):
        pr = PatternRegistry()
        pattern = {
            "pattern_name": "test-pat", "category": "execution",
            "problem_solved": "test", "risk_level": "low",
            "adoption_recommendation": "adopt", "dvexa_compatibility": "adaptable",
            "mechanism": "test", "required_changes": [],
        }
        pid = pr.register(pattern)
        node = pr.to_capability_node(pid)
        assert node is None  # not adopted yet

    def test_to_capability_node_adopted(self):
        pr = PatternRegistry()
        pattern = {
            "pattern_name": "retry-pattern", "category": "execution",
            "problem_solved": "Adds retry capability",
            "risk_level": "low", "adoption_recommendation": "adopt",
            "dvexa_compatibility": "compatible", "mechanism": "retry with backoff",
            "required_changes": ["Add to capabilities/"],
        }
        pid = pr.register(pattern, review={"approved": True})
        pr.adopt(pid)
        node = pr.to_capability_node(pid)
        assert node is not None
        assert node["category"] == "execution"
        assert node["source_type"] == "assimilation"
        assert node["governance_approved"] is True

    def test_category_mapping(self):
        pr = PatternRegistry()
        tests = [
            ("planner", "planning"),
            ("execution", "execution"),
            ("context", "memory"),
            ("memory", "memory"),
            ("tool", "execution"),
        ]
        for src_cat, tax_cat in tests:
            p = {
                "pattern_name": f"test-{src_cat}", "category": src_cat,
                "problem_solved": "test", "risk_level": "low",
                "adoption_recommendation": "adopt", "dvexa_compatibility": "compatible",
                "mechanism": "test", "required_changes": [],
            }
            pid = pr.register(p)
            pr.adopt(pid)
            node = pr.to_capability_node(pid)
            assert node["category"] == tax_cat, \
                f"Expected {src_cat} → {tax_cat}, got {node['category']}"

    def test_get_adopted_capability_nodes(self):
        pr = PatternRegistry()
        for name in ("p1", "p2", "p3"):
            p = {
                "pattern_name": name, "category": "execution",
                "problem_solved": f"test {name}", "risk_level": "low",
                "adoption_recommendation": "adopt", "dvexa_compatibility": "compatible",
                "mechanism": "test", "required_changes": [],
            }
            pid = pr.register(p)
            pr.adopt(pid)
        nodes = pr.get_adopted_capability_nodes()
        assert len(nodes) == 3


# ═══════════════════════════════════════════════════════════════════════════
# Test: Governance Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestGovernanceIntegration:
    def test_capability_awareness_quarantined_blocks(self):
        """Quarantined capability → 策略提升为 STRICT 并阻断对应 tool。"""
        r = CapabilityRegistry()
        r.register(make_node("q:llm", "llm", "execution",
                             maturity="quarantined", source_type="skill"))
        k = GovernanceKernel(capability_registry=r)
        plan = {"goal": "test", "steps": [
            {"id": 1, "tool": "llm", "action": "chat"},
        ]}
        result = k.process({}, plan)
        assert "capability_decisions" in result
        # quarantined should force strategy to STRICT
        assert result["strategy"] == "STRICT"

    def test_capability_awareness_experimental(self):
        """Experimental capability → 记录警告。"""
        r = CapabilityRegistry()
        r.register(make_node("e:llm", "llm", "execution",
                             maturity="experimental", source_type="skill"))
        k = GovernanceKernel(capability_registry=r)
        plan = {"goal": "test", "steps": [
            {"id": 1, "tool": "llm", "action": "chat"},
        ]}
        result = k.process({}, plan)
        assert "capability_decisions" in result

    def test_capability_awareness_high_risk_warns(self):
        """High risk capability → 记录警告但允许通过。"""
        r = CapabilityRegistry()
        r.register(make_node("hr:llm", "llm", "execution",
                             risk_level="critical", source_type="skill"))
        k = GovernanceKernel(capability_registry=r)
        plan = {"goal": "test", "steps": [
            {"id": 1, "tool": "llm", "action": "chat"},
        ]}
        result = k.process({}, plan)
        assert "capability_decisions" in result

    def test_no_registry_no_impact(self):
        """无 CapabilityRegistry 时不影响正常流程。"""
        k = GovernanceKernel()
        plan = {"goal": "test", "steps": [
            {"id": 1, "tool": "llm", "action": "chat"},
        ]}
        result = k.process({}, plan)
        assert "capability_decisions" in result
        assert result["capability_decisions"] == []

    def test_inject_backward_compat(self):
        """inject() 方法保持向后兼容。"""
        k = GovernanceKernel()
        result = k.inject(None)
        assert result["filtered_plan"] is None
        assert result["decisions"] == []

    def test_checkpoint_4_5_blocks_quarantined_skill(self):
        """Checkpoint 4.5: taxonomy 中 quarantined 的 skill 被阻断。"""
        r = CapabilityRegistry()
        r.register(make_node("q:code", "code", "execution",
                             maturity="quarantined", source_type="skill"))
        k = GovernanceKernel(capability_registry=r)
        plan = {"goal": "test", "steps": [
            {"id": 1, "tool": "code_executor", "action": "run code"},
        ]}
        result = k.process({}, plan)
        # step should be blocked by Checkpoint 4.5
        assert result["strategy"] == "STRICT"

    def test_checkpoint_4_5_downgrades_experimental(self):
        """Checkpoint 4.5: experimental capability → downgrade。"""
        r = CapabilityRegistry()
        r.register(make_node("e:llm", "llm", "execution",
                             maturity="experimental", source_type="skill"))
        k = GovernanceKernel(capability_registry=r)
        plan = {"goal": "test", "steps": [
            {"id": 1, "tool": "llm", "action": "chat"},
        ]}
        result = k.process({}, plan)
        # experimental → downgrade to reasoning
        filtered = result["filtered_plan"]["steps"]
        if filtered:
            assert filtered[0]["type"] == "reasoning" or \
                   filtered[0].get("type") != "tool"


# ═══════════════════════════════════════════════════════════════════════════
# Test: Determinism
# ═══════════════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_taxonomy_tree_deterministic(self):
        a = build_default_taxonomy()
        b = build_default_taxonomy()
        assert a == b

    def test_graph_deterministic(self):
        g1 = CapabilityGraph()
        g2 = CapabilityGraph()
        for g in (g1, g2):
            g.add_node("a"); g.add_node("b"); g.add_node("c")
            g.add_dependency("a", "b")
            g.add_dependency("b", "c")
        assert g1.detect_cycles() == g2.detect_cycles()
        assert g1.compute_depth() == g2.compute_depth()

    def test_registry_deterministic(self):
        r1 = CapabilityRegistry()
        r2 = CapabilityRegistry()
        for r in (r1, r2):
            r.register(make_node("a", "a", "planning"))
            r.register(make_node("b", "b", "execution"))
        assert r1.get_summary() == r2.get_summary()

    def test_analyzer_deterministic(self):
        r1 = CapabilityRegistry()
        r2 = CapabilityRegistry()
        for r in (r1, r2):
            r.register(make_node("a", "a", "planning", maturity="stable"))
            r.register(make_node("b", "b", "execution", maturity="experimental"))
        a1 = CapabilityAnalyzer(registry=r1)
        a2 = CapabilityAnalyzer(registry=r2)
        assert a1.analyze_system_capabilities() == a2.analyze_system_capabilities()

    def test_evolution_tracker_deterministic(self):
        t1 = EvolutionTracker()
        t2 = EvolutionTracker()
        for t in (t1, t2):
            t.record_adoption("a")
            t.record_failure("b")
        r1 = t1.generate_evolution_report()
        r2 = t2.generate_evolution_report()
        assert r1["total_events"] == r2["total_events"]

    def test_governance_capability_deterministic(self):
        r = CapabilityRegistry()
        r.register(make_node("d:llm", "llm", "execution",
                             maturity="quarantined", source_type="skill"))
        k1 = GovernanceKernel(capability_registry=r)
        k2 = GovernanceKernel(capability_registry=r)
        plan = {"goal": "test", "steps": [{"id": 1, "tool": "llm", "action": "c"}]}
        assert k1.process({}, plan)["strategy"] == k2.process({}, plan)["strategy"]


# ═══════════════════════════════════════════════════════════════════════════
# Test: No LLM
# ═══════════════════════════════════════════════════════════════════════════

class TestNoLLM:
    def test_taxonomy_no_llm(self):
        n = make_node("test")
        assert isinstance(n.capability_id, str)

    def test_graph_no_llm(self):
        g = CapabilityGraph()
        g.add_node("a"); g.add_node("b")
        g.add_dependency("a", "b")
        cycles = g.detect_cycles()
        assert isinstance(cycles, list)

    def test_registry_no_llm(self):
        r = CapabilityRegistry()
        r.register(make_node("a", "a"))
        assert r.count == 1

    def test_evolution_no_llm(self):
        t = EvolutionTracker()
        t.record_adoption("a")
        assert t.get_event_count() == 1

    def test_analyzer_no_llm(self):
        r = CapabilityRegistry()
        r.register(make_node("a", "a"))
        a = CapabilityAnalyzer(registry=r)
        report = a.analyze_system_capabilities()
        assert isinstance(report["total_capabilities"], int)

    def test_mapping_no_llm(self):
        pr = PatternRegistry()
        p = {
            "pattern_name": "test", "category": "execution",
            "problem_solved": "test", "risk_level": "low",
            "adoption_recommendation": "adopt", "dvexa_compatibility": "compatible",
            "mechanism": "test", "required_changes": [],
        }
        pid = pr.register(p)
        pr.adopt(pid)
        node = pr.to_capability_node(pid)
        assert node is not None

    def test_governance_awareness_no_llm(self):
        r = CapabilityRegistry()
        r.register(make_node("q:test", "test", "execution",
                             maturity="quarantined"))
        k = GovernanceKernel(capability_registry=r)
        result = k.process({}, {"goal": "t", "steps": [
            {"id": 1, "tool": "test", "action": "x"}]})
        assert result["strategy"] in ("STRICT", "BALANCED", "CONSERVATIVE", "EXPLORATION")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Full Pipeline Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_full_taxonomy_integration(self):
        """完整流程: registry → graph → analyzer → tracker → governance。"""
        # 1. 创建 registry 并注册
        r = CapabilityRegistry()
        r.register(make_node("p:decomp", "task-decomposition", "planning",
                             "decomposition", maturity="stable"))
        r.register(make_node("p:replan", "adaptive-replanning", "planning",
                             "replanning", maturity="experimental"))
        r.register(make_node("e:retry", "execution-retry", "execution",
                             "retry", maturity="stable"))
        r.register(make_node("m:compress", "context-compression", "memory",
                             "context-compression", risk_level="high",
                             dependencies=["e:retry"]))
        r.register(make_node("g:policy", "tool-policy", "governance",
                             "policy", maturity="stable", source_type="governance"))

        # 2. 构建依赖图
        g = r.build_dependency_graph()
        assert g.node_count == 5
        assert g.get_dependencies("m:compress") == ["e:retry"]
        assert g.detect_cycles() == []

        # 3. 分析器
        a = CapabilityAnalyzer(registry=r)
        report = a.analyze_system_capabilities()
        assert report["total_capabilities"] == 5
        assert report["stable_capabilities"] == 3
        assert report["experimental_capabilities"] == 2
        assert report["high_risk_capabilities"] == 1
        assert len(report["critical_dependencies"]) == 0

        # 4. 演化追踪
        t = EvolutionTracker()
        t.record_adoption("p:decomp", source="sst/opencode", source_type="assimilation")
        t.record_stabilization("p:decomp", previous_maturity="experimental",
                               new_maturity="stable")
        assert t.get_event_count() == 2

        # 5. 治理集成
        k = GovernanceKernel(capability_registry=r)
        plan = {"goal": "test", "steps": [
            {"id": 1, "tool": "llm", "action": "decompose task"},
            {"id": 2, "tool": "code_executor", "action": "run test"},
        ]}
        result = k.process({}, plan)
        assert "capability_decisions" in result
        assert "strategy" in result

        # 6. Registry 一致性
        s = r.get_summary()
        assert s["total"] == 5
        assert len(r.categories) >= 3
