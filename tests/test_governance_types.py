"""Tests for Governance Types — HARD/SOFT 治理分类"""

from __future__ import annotations

from governance.governance_types import (
    GovernanceType, GovCheckpoint, CHECKPOINTS,
)


class TestGovernanceType:

    def test_hard_is_deterministic(self):
        assert GovernanceType.HARD.value == "hard"

    def test_soft_value(self):
        assert GovernanceType.SOFT.value == "soft"


class TestGovCheckpoint:

    def test_hard_checkpoint_deterministic(self):
        cp = GovCheckpoint("test", GovernanceType.HARD, "desc")
        assert cp.deterministic is True
        assert cp.gov_type == GovernanceType.HARD

    def test_to_dict_includes_type(self):
        cp = GovCheckpoint("test", GovernanceType.HARD, "desc")
        d = cp.to_dict()
        assert d["name"] == "test"
        assert d["type"] == "hard"


class TestCheckpointRegistry:

    def test_all_checkpoints_have_type(self):
        for name, cp in CHECKPOINTS.items():
            assert cp.gov_type in (GovernanceType.HARD, GovernanceType.SOFT), \
                f"{name} missing governance type"

    def test_most_checkpoints_are_hard(self):
        hard_count = sum(
            1 for cp in CHECKPOINTS.values()
            if cp.gov_type == GovernanceType.HARD
        )
        assert hard_count >= 6  # at least 6 of 8 are HARD

    def test_strategy_override_is_soft(self):
        assert CHECKPOINTS["strategy_override"].gov_type == GovernanceType.SOFT

    def test_tool_policy_is_hard(self):
        assert CHECKPOINTS["tool_policy"].gov_type == GovernanceType.HARD

    def test_checkpoint_count(self):
        assert len(CHECKPOINTS) >= 8
