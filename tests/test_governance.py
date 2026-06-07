"""Tests for stock governance."""

from governance.governance_kernel import StockGovernanceKernel


class TestStockGovernanceKernel:
    def setup_method(self):
        self.gk = StockGovernanceKernel()

    def test_data_quality_pass(self):
        data = {
            "indicators": {
                "roe": [18, 17, 16],
                "gross_margin": [40, 38, 42],
                "debt_ratio": [45, 42, 40],
            }
        }
        result = self.gk.check_data_quality(data)
        assert result["passed"] is True
        assert len(result["errors"]) == 0

    def test_data_quality_missing_field(self):
        data = {"indicators": {"roe": [18]}}
        result = self.gk.check_data_quality(data)
        assert result["passed"] is False
        assert any("gross_margin" in e for e in result["errors"])

    def test_data_quality_abnormal_roe(self):
        data = {
            "indicators": {
                "roe": [150],
                "gross_margin": [40],
                "debt_ratio": [45],
            }
        }
        result = self.gk.check_data_quality(data)
        assert len(result["warnings"]) > 0

    def test_analysis_consistency_match(self):
        scores = {"composite_score": 75, "dimensions": {"valuation": 70}}
        conclusion = {"score": 8, "valuation_assessment": "合理"}
        result = self.gk.check_analysis_consistency(scores, conclusion)
        assert result["consistent"] is True

    def test_analysis_consistency_mismatch(self):
        scores = {"composite_score": 30, "dimensions": {"valuation": 30}}
        conclusion = {"score": 9, "valuation_assessment": "低估"}
        result = self.gk.check_analysis_consistency(scores, conclusion)
        assert len(result["conflicts"]) > 0

    def test_screening_conditions_valid(self):
        conditions = {"pe_max": 30, "roe_min": 15}
        result = self.gk.validate_screening_conditions(conditions)
        assert result["valid"] is True

    def test_screening_conditions_extreme(self):
        conditions = {"pe_max": 300}
        result = self.gk.validate_screening_conditions(conditions)
        assert len(result["warnings"]) > 0
