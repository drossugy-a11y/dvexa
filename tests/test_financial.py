"""Tests for financial scoring."""

from tools.financial import FinancialAnalyzer


class TestFinancialAnalyzer:
    def setup_method(self):
        self.analyzer = FinancialAnalyzer()

    def test_growth_score_with_data(self):
        data = {
            "indicators": {
                "revenue_growth": [25, 20, 15],
                "net_profit_growth": [30, 25, 20],
            }
        }
        result = self.analyzer.calculate_growth_score(data)
        assert result["dimension"] == "growth"
        assert result["score"] > 50

    def test_growth_score_negative(self):
        data = {
            "indicators": {
                "revenue_growth": [-10, -5, -2],
                "net_profit_growth": [-20, -15, -10],
            }
        }
        result = self.analyzer.calculate_growth_score(data)
        assert result["score"] < 50

    def test_profitability_score_high_roe(self):
        data = {
            "indicators": {
                "roe": [25, 22, 20],
                "gross_margin": [50, 48, 45],
            }
        }
        result = self.analyzer.calculate_profitability_score(data)
        assert result["score"] > 70

    def test_health_score_low_debt(self):
        data = {
            "indicators": {
                "debt_ratio": [30, 35, 32],
                "current_ratio": [2.5, 2.3, 2.1],
                "cash_flow_per_share": [1.5, 1.2, 1.0],
            }
        }
        result = self.analyzer.calculate_health_score(data)
        assert result["score"] > 70

    def test_health_score_high_debt(self):
        data = {
            "indicators": {
                "debt_ratio": [80, 85, 82],
            }
        }
        result = self.analyzer.calculate_health_score(data)
        assert result["score"] < 50

    def test_quality_score_stable_margins(self):
        data = {
            "indicators": {
                "gross_margin": [45, 44, 46],
                "roe": [18, 17, 19],
            }
        }
        result = self.analyzer.calculate_quality_score(data)
        assert result["score"] > 60

    def test_composite_score(self):
        data = {
            "indicators": {
                "revenue_growth": [15, 12, 10],
                "net_profit_growth": [20, 18, 15],
                "roe": [18, 17, 16],
                "gross_margin": [40, 38, 42],
                "debt_ratio": [45, 42, 40],
                "current_ratio": [2.0, 1.8, 2.2],
                "cash_flow_per_share": [1.0, 0.8, 1.2],
            }
        }
        result = self.analyzer.calculate_composite_score(data)
        assert "composite_score" in result
        assert "dimensions" in result
        assert 0 <= result["composite_score"] <= 100
        assert len(result["dimensions"]) == 5

    def test_composite_score_empty(self):
        result = self.analyzer.calculate_composite_score({})
        assert result["composite_score"] >= 0
