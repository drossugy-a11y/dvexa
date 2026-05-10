"""Comprehensive tests for cognitive stream mapping.

Covers: get_cognitive() per StepType, COGNITIVE_MAP integrity,
StepStreamer auto-population of cognitive fields, RuntimeStep dict
serialization, CoT leakage checks, and determinism guarantees.
"""

from runtime.step_events import StepType, RuntimeStep
from runtime.cognitive_mapping import COGNITIVE_MAP, get_cognitive
from runtime.step_streamer import StepStreamer


class TestCognitiveStream:
    """Suite: cognitive mapping, streamer integration, and data integrity."""

    # ═══════════════════════════════════════════════════════════════════
    # 1. Cognitive mapping coverage — one test per StepType (13 tests)
    # ═══════════════════════════════════════════════════════════════════

    def test_directive_mapping(self):
        state, label = get_cognitive(StepType.DIRECTIVE)
        assert state == "understanding"
        assert label == "Understanding Request"
        assert COGNITIVE_MAP[StepType.DIRECTIVE] == (
            "understanding", "Understanding Request",
        )

    def test_governance_mapping(self):
        state, label = get_cognitive(StepType.GOVERNANCE)
        assert state == "evaluating"
        assert label == "Evaluating Safety Constraints"
        assert COGNITIVE_MAP[StepType.GOVERNANCE] == (
            "evaluating", "Evaluating Safety Constraints",
        )

    def test_planning_mapping(self):
        state, label = get_cognitive(StepType.PLANNING)
        assert state == "planning"
        assert label == "Preparing Execution Strategy"
        assert COGNITIVE_MAP[StepType.PLANNING] == (
            "planning", "Preparing Execution Strategy",
        )

    def test_execution_mapping(self):
        state, label = get_cognitive(StepType.EXECUTION)
        assert state == "executing"
        assert label == "Executing Task Pipeline"
        assert COGNITIVE_MAP[StepType.EXECUTION] == (
            "executing", "Executing Task Pipeline",
        )

    def test_tool_call_mapping(self):
        state, label = get_cognitive(StepType.TOOL_CALL)
        assert state == "selecting"
        assert label == "Selecting Runtime Capability"
        assert COGNITIVE_MAP[StepType.TOOL_CALL] == (
            "selecting", "Selecting Runtime Capability",
        )

    def test_tool_result_mapping(self):
        state, label = get_cognitive(StepType.TOOL_RESULT)
        assert state == "verifying"
        assert label == "Processing Tool Results"
        assert COGNITIVE_MAP[StepType.TOOL_RESULT] == (
            "verifying", "Processing Tool Results",
        )

    def test_thinking_mapping(self):
        state, label = get_cognitive(StepType.THINKING)
        assert state == "analyzing"
        assert label == "Reasoning About Approach"
        assert COGNITIVE_MAP[StepType.THINKING] == (
            "analyzing", "Reasoning About Approach",
        )

    def test_memory_mapping(self):
        state, label = get_cognitive(StepType.MEMORY)
        assert state == "summarizing"
        assert label == "Updating System Memory"
        assert COGNITIVE_MAP[StepType.MEMORY] == (
            "summarizing", "Updating System Memory",
        )

    def test_output_mapping(self):
        state, label = get_cognitive(StepType.OUTPUT)
        assert state == "summarizing"
        assert label == "Finalizing Response"
        assert COGNITIVE_MAP[StepType.OUTPUT] == (
            "summarizing", "Finalizing Response",
        )

    def test_complete_mapping(self):
        state, label = get_cognitive(StepType.COMPLETE)
        assert state == "completed"
        assert label == "Task Complete"
        assert COGNITIVE_MAP[StepType.COMPLETE] == (
            "completed", "Task Complete",
        )

    def test_error_mapping(self):
        state, label = get_cognitive(StepType.ERROR)
        assert state == "completed"
        assert label == "Error Encountered"
        assert COGNITIVE_MAP[StepType.ERROR] == (
            "completed", "Error Encountered",
        )

    def test_blocked_mapping(self):
        state, label = get_cognitive(StepType.BLOCKED)
        assert state == "evaluating"
        assert label == "Execution Blocked by Policy"
        assert COGNITIVE_MAP[StepType.BLOCKED] == (
            "evaluating", "Execution Blocked by Policy",
        )

    def test_recovery_mapping(self):
        state, label = get_cognitive(StepType.RECOVERY)
        assert state == "analyzing"
        assert label == "Attempting Automatic Recovery"
        assert COGNITIVE_MAP[StepType.RECOVERY] == (
            "analyzing", "Attempting Automatic Recovery",
        )

    # ═══════════════════════════════════════════════════════════════════
    # 2. Unknown step type fallback
    # ═══════════════════════════════════════════════════════════════════

    def test_unknown_step_type_fallback(self):
        """A value not present in COGNITIVE_MAP returns the default."""
        state, label = get_cognitive("not_a_real_step_type")  # type: ignore[arg-type]
        assert state == "processing"
        assert label == "Processing"

    # ═══════════════════════════════════════════════════════════════════
    # 3. StepStreamer convenience methods auto-populate cognitive fields
    #    (12 convenience methods — 12 tests)
    # ═══════════════════════════════════════════════════════════════════

    def test_directive_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.directive(title="test")
        assert step.cognitive_state == "understanding"
        assert step.cognitive_label == "Understanding Request"

    def test_governance_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.governance(title="testing governance")
        assert step.cognitive_state == "evaluating"
        assert step.cognitive_label == "Evaluating Safety Constraints"

    def test_planning_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.planning(title="testing planning")
        assert step.cognitive_state == "planning"
        assert step.cognitive_label == "Preparing Execution Strategy"

    def test_execution_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.execution(title="testing execution")
        assert step.cognitive_state == "executing"
        assert step.cognitive_label == "Executing Task Pipeline"

    def test_tool_call_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.tool_call(title="testing tool_call")
        assert step.cognitive_state == "selecting"
        assert step.cognitive_label == "Selecting Runtime Capability"

    def test_tool_result_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.tool_result(title="testing tool_result")
        assert step.cognitive_state == "verifying"
        assert step.cognitive_label == "Processing Tool Results"

    def test_thinking_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.thinking(title="testing thinking")
        assert step.cognitive_state == "analyzing"
        assert step.cognitive_label == "Reasoning About Approach"

    def test_memory_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.memory(title="testing memory")
        assert step.cognitive_state == "summarizing"
        assert step.cognitive_label == "Updating System Memory"

    def test_output_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.output(title="testing output")
        assert step.cognitive_state == "summarizing"
        assert step.cognitive_label == "Finalizing Response"

    def test_complete_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.complete()
        assert step.cognitive_state == "completed"
        assert step.cognitive_label == "Task Complete"

    def test_error_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.error()
        assert step.cognitive_state == "completed"
        assert step.cognitive_label == "Error Encountered"

    def test_blocked_emit_has_cognitive(self):
        streamer = StepStreamer()
        step = streamer.blocked(reason="policy violation")
        assert step.cognitive_state == "evaluating"
        assert step.cognitive_label == "Execution Blocked by Policy"

    # ═══════════════════════════════════════════════════════════════════
    # 4. RuntimeStep.to_dict() includes cognitive fields
    # ═══════════════════════════════════════════════════════════════════

    def test_to_dict_includes_cognitive_fields(self):
        step = RuntimeStep(
            step_type=StepType.DIRECTIVE,
            title="test",
            cognitive_state="understanding",
            cognitive_label="Understanding Request",
        )
        d = step.to_dict()
        assert d["cognitive_state"] == "understanding"
        assert d["cognitive_label"] == "Understanding Request"

    # ═══════════════════════════════════════════════════════════════════
    # 5. No CoT leakage
    # ═══════════════════════════════════════════════════════════════════

    def test_no_raw_cot_in_cognitive_label(self):
        """Verify labels never contain leaked internal text or exceed 50 chars."""
        # Check for patterns that indicate raw internal data leaking into
        # human-facing labels -- not legitimate English words.
        forbidden = (
            "step_type=", "chain of thought",
            "cot:", "debug:",
        )
        for step_type in StepType:
            _, label = get_cognitive(step_type)
            lower = label.lower()
            for token in forbidden:
                assert token not in lower, (
                    f"CoT leak in {step_type.value}: {label!r}"
                )
            assert len(label) <= 50, (
                f"cognitive_label too long ({len(label)} chars): {label!r}"
            )

    # ═══════════════════════════════════════════════════════════════════
    # 6. Deterministic mapping
    # ═══════════════════════════════════════════════════════════════════

    def test_mapping_is_deterministic(self):
        """Calling get_cognitive twice with the same input returns the same output."""
        for step_type in StepType:
            result1 = get_cognitive(step_type)
            result2 = get_cognitive(step_type)
            assert result1 == result2, (
                f"Non-deterministic for {step_type.value}: "
                f"{result1} != {result2}"
            )

    # ═══════════════════════════════════════════════════════════════════
    # 7. All COGNITIVE_MAP keys are valid StepTypes
    # ═══════════════════════════════════════════════════════════════════

    def test_all_step_types_covered(self):
        """Every StepType has an entry in COGNITIVE_MAP and vice versa."""
        expected = set(StepType)
        actual = set(COGNITIVE_MAP.keys())
        assert actual == expected, (
            f"Missing from map: {expected - actual}; "
            f"Extra in map: {actual - expected}"
        )
