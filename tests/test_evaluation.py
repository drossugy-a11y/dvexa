"""Tests for evaluation module — ExecutionProof, CapabilityScore, EvolutionProof."""
import json
import pytest
from evaluation.proof import ExecutionProof, StrategyRecord, ToolCallRecord
from evaluation.score import CapabilityScore, DimensionScore
from evaluation.evolution import EvolutionProof, MemoryInfluence, PolicyDelta
from evaluation.pack import EvaluationPack


class TestExecutionProof:
    def test_empty_proof(self):
        proof = ExecutionProof()
        assert proof.task_input == ""
        assert proof.strategies == []
        assert proof.tool_calls == []
        assert not proof.success

    def test_add_strategy(self):
        proof = ExecutionProof()
        proof.add_strategy(StrategyRecord(id=1, description="test strategy", plan={"steps": []}))
        assert len(proof.strategies) == 1
        assert proof.strategies[0].description == "test strategy"

    def test_add_tool_call(self):
        proof = ExecutionProof()
        proof.add_tool_call(ToolCallRecord(step_id=1, action="test", tool="llm", tool_input="in", tool_output_summary="out"))
        assert len(proof.tool_calls) == 1
        assert proof.tool_calls[0].tool == "llm"

    def test_to_json_serializable(self):
        proof = ExecutionProof(task_input="test task", task_id="test-001", success=True)
        proof.add_strategy(StrategyRecord(id=1, description="s1", plan={"goal": "g", "steps": []}))
        proof.add_tool_call(ToolCallRecord(step_id=1, action="a", tool="llm", tool_input="i", tool_output_summary="o"))
        data = json.loads(proof.to_json())
        assert data["task_input"] == "test task"
        assert data["task_id"] == "test-001"
        assert data["success"] is True
        assert len(data["strategies"]) == 1
        assert len(data["tool_calls"]) == 1

    def test_to_text_human_readable(self):
        proof = ExecutionProof(task_input="readable test", success=True, goal="test goal")
        proof.add_strategy(StrategyRecord(id=1, description="strat-a", plan={"steps": []}, selected=True, selection_reason="best"))
        text = proof.to_text()
        assert "readable test" in text
        assert "test goal" in text
        assert "strat-a" in text
        assert "SELECTED" in text

    def test_from_kernel_result(self):
        kernel_result = {
            "task_id": "k-test",
            "status": "completed",
            "goal": "kernel goal",
            "plan": [{"step_id": 1, "action": "do thing"}],
            "steps": [{"step_id": 1, "action": "do thing", "tool": "llm", "tool_input": "in", "tool_output": "done"}],
            "result": "completed ok",
        }
        proof = ExecutionProof.from_kernel_result("kernel task", kernel_result)
        assert proof.task_id == "k-test"
        assert proof.goal == "kernel goal"
        assert proof.success is True
        assert len(proof.tool_calls) == 1


class TestCapabilityScore:
    def test_empty_proof_scores_zero(self):
        proof = ExecutionProof()
        score = CapabilityScore.compute(proof)
        # Most dimensions should be near zero for empty proof
        assert score.total_score < 50

    def test_successful_execution_scores_high(self):
        proof = ExecutionProof(task_input="complex task", success=True)
        proof.add_strategy(StrategyRecord(id=1, description="s1", plan={"goal": "g", "steps": [{"id": 1}, {"id": 2}, {"id": 3}]}))
        proof.add_strategy(StrategyRecord(id=2, description="s2", plan={"goal": "g2", "steps": [{"id": 1}, {"id": 2}]}, selected=True, selection_reason="better"))
        for i in range(3):
            proof.add_tool_call(ToolCallRecord(step_id=i, action=f"step{i}", tool="llm" if i == 0 else "code_executor", tool_input="i", tool_output_summary="ok", success=True))
        score = CapabilityScore.compute(proof)
        assert score.total_score >= 50

    def test_planning_quality_multi_strategy(self):
        from evaluation.score import CapabilityScore as CS
        proof = ExecutionProof()
        proof.add_strategy(StrategyRecord(id=1, description="a", plan={"goal": "g", "steps": [{"id": 1}, {"id": 2}, {"id": 3}]}))
        proof.add_strategy(StrategyRecord(id=2, description="b", plan={"goal": "g", "steps": [{"id": 1}, {"id": 2}]}, selected=True, selection_reason="best"))
        d = CS._score_planning(proof)
        assert d.score >= 70  # multi-strategy bonus

    def test_execution_reliability_all_pass(self):
        from evaluation.score import CapabilityScore as CS
        proof = ExecutionProof(success=True)
        for i in range(5):
            proof.add_tool_call(ToolCallRecord(step_id=i, action="a", tool="llm", tool_input="i", tool_output_summary="ok", success=True))
        d = CS._score_execution(proof)
        assert d.score >= 80

    def test_tool_diversity_scoring(self):
        from evaluation.score import CapabilityScore as CS
        proof = ExecutionProof()
        proof.add_tool_call(ToolCallRecord(step_id=1, action="a", tool="llm", tool_input="i", tool_output_summary="ok"))
        proof.add_tool_call(ToolCallRecord(step_id=2, action="b", tool="code_executor", tool_input="i", tool_output_summary="ok"))
        d = CS._score_tool_usage(proof)
        assert d.score >= 50  # multi-tool bonus

    def test_to_dict_structure(self):
        proof = ExecutionProof(success=True)
        proof.add_strategy(StrategyRecord(id=1, description="s", plan={"steps": []}))
        score = CapabilityScore.compute(proof)
        d = score.to_dict()
        assert "total_score" in d
        assert "dimensions" in d
        assert len(d["dimensions"]) == 7
        for dim in d["dimensions"]:
            assert "name" in dim
            assert "score" in dim
            assert "weight" in dim
            assert "evidence" in dim

    def test_weights_sum_to_one(self):
        proof = ExecutionProof(success=True)
        score = CapabilityScore.compute(proof)
        total_wt = sum(d.weight for d in score.dimensions)
        assert abs(total_wt - 1.0) < 0.01


class TestEvolutionProof:
    def test_empty_memory(self):
        evolution = EvolutionProof.compute(memory_tasks=[])
        assert evolution.historical_task_count == 0
        assert evolution.memory_influences == []

    def test_with_memory_tasks(self):
        tasks = [
            {"task_id": "t1", "input": "task one", "status": "completed",
             "steps": [{"step_id": 1, "tool": "llm"}]},
            {"task_id": "t2", "input": "task two", "status": "failed",
             "steps": [{"step_id": 1, "tool": "code_executor"}],
             "plan": []},
        ]
        evolution = EvolutionProof.compute(memory_tasks=tasks, current_task_id="t3")
        assert evolution.historical_task_count == 2
        assert len(evolution.memory_influences) >= 1

    def test_policy_deltas_detection(self):
        tool_policy = {
            "allowed_tools": {"code_executor": 0.7, "http_request": 0.5},
            "denied_tools": ["unsafe_tool"],
        }
        evolution = EvolutionProof.compute(memory_tasks=[], tool_policy_state=tool_policy)
        assert len(evolution.policy_deltas) >= 1

    def test_strategy_shifts_detection(self):
        tasks = [
            {"task_id": "t1", "status": "completed", "steps": [{"tool": "llm"}], "plan": []},
            {"task_id": "t2", "status": "completed", "steps": [{"tool": "llm"}, {"tool": "code_executor"}], "plan": []},
            {"task_id": "t3", "status": "completed", "steps": [{"tool": "http_request"}, {"tool": "code_executor"}], "plan": []},
        ]
        evolution = EvolutionProof.compute(memory_tasks=tasks)
        assert len(evolution.strategy_preference_shifts) >= 1

    def test_memory_influence_type(self):
        tasks = [{"task_id": "t1", "input": "fail task", "status": "failed",
                  "steps": [{"step_id": 1, "tool": "llm"}], "plan": []}]
        evolution = EvolutionProof.compute(memory_tasks=tasks, current_task_id="t2")
        assert any(inf.influence_type == "strategy_shift" for inf in evolution.memory_influences)

    def test_serialization(self):
        evolution = EvolutionProof(historical_task_count=3)
        d = evolution.to_dict()
        assert d["historical_task_count"] == 3
        json_str = evolution.to_json()
        assert json.loads(json_str)["historical_task_count"] == 3


class TestEvaluationPack:
    def test_pack_creation(self):
        proof = ExecutionProof(task_input="pack test", success=True)
        proof.add_strategy(StrategyRecord(id=1, description="s", plan={"steps": []}))
        score = CapabilityScore.compute(proof)
        evolution = EvolutionProof.compute(memory_tasks=[])
        pack = EvaluationPack(execution_proof=proof, capability_score=score, evolution_proof=evolution)
        assert pack.execution_proof.task_input == "pack test"
        assert pack.capability_score.total_score > 0

    def test_pack_json(self):
        proof = ExecutionProof(task_input="json test")
        score = CapabilityScore.compute(proof)
        evolution = EvolutionProof.compute(memory_tasks=[])
        pack = EvaluationPack(proof, score, evolution)
        data = json.loads(pack.to_json())
        assert "execution_proof" in data
        assert "capability_score" in data
        assert "evolution_proof" in data
        assert "pack_metadata" in data

    def test_pack_summary(self):
        proof = ExecutionProof(task_input="summary test", success=True, total_latency_s=5.0)
        score = CapabilityScore.compute(proof)
        evolution = EvolutionProof.compute(memory_tasks=[])
        pack = EvaluationPack(proof, score, evolution)
        s = pack.summary()
        assert s["success"] is True
        assert s["overall_score"] > 0
        assert "task" in s
