"""Stock Governance Kernel — 选股分析数据质量检查

职责：
  - 数据质量检查（完整性、异常、时效性）
  - 分析一致性检查（AI结论 vs 量化评分）
  - 筛选条件验证
"""

from __future__ import annotations


class StockGovernanceKernel:
    """选股分析治理。"""

    def check_data_quality(self, financial_data: dict) -> dict:
        """数据质量检查。"""
        warnings = []
        errors = []
        indicators = financial_data.get("indicators", {})

        required = ["roe", "gross_margin", "debt_ratio"]
        for field in required:
            if field not in indicators or not indicators[field]:
                errors.append(f"缺少必要字段: {field}")

        if not errors:
            try:
                roe_val = float(indicators["roe"][0]) if indicators.get("roe") else None
                if roe_val is not None and roe_val > 100:
                    warnings.append(f"ROE异常偏高: {roe_val}%")
                if roe_val is not None and roe_val < -50:
                    warnings.append(f"ROE异常偏低: {roe_val}%")
            except (ValueError, TypeError, IndexError):
                pass

            try:
                debt_val = float(indicators["debt_ratio"][0]) if indicators.get("debt_ratio") else None
                if debt_val is not None and debt_val > 100:
                    errors.append(f"资产负债率超过100%: {debt_val}%")
            except (ValueError, TypeError, IndexError):
                pass

        return {
            "passed": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
        }

    def check_analysis_consistency(self, scores: dict, ai_conclusion: dict) -> dict:
        """分析一致性检查。"""
        conflicts = []

        composite = scores.get("composite_score", 0)
        ai_score = ai_conclusion.get("score", 5)
        valuation = ai_conclusion.get("valuation_assessment", "")

        dims = scores.get("dimensions", {})
        valuation_dim = dims.get("valuation", 50)

        if valuation in ("低估", "偏低") and valuation_dim < 40:
            conflicts.append(f"AI判断'{valuation}'但估值评分仅{valuation_dim}")
        if valuation in ("高估", "偏高") and valuation_dim > 70:
            conflicts.append(f"AI判断'{valuation}'但估值评分高达{valuation_dim}")

        if ai_score >= 8 and composite < 50:
            conflicts.append(f"AI评分{ai_score}但综合量化分仅{composite}")
        if ai_score <= 3 and composite > 70:
            conflicts.append(f"AI评分{ai_score}但综合量化分高达{composite}")

        return {
            "consistent": len(conflicts) == 0,
            "conflicts": conflicts,
        }

    def validate_screening_conditions(self, conditions: dict) -> dict:
        """筛选条件验证。"""
        warnings = []

        pe_max = conditions.get("pe_max")
        if pe_max is not None and pe_max <= 0:
            warnings.append("PE上限应大于0")
        if pe_max is not None and pe_max > 200:
            warnings.append("PE上限过高，可能筛选出大量股票")

        roe_min = conditions.get("roe_min")
        if roe_min is not None and roe_min > 50:
            warnings.append("ROE下限过高，可能结果过少")

        return {
            "valid": True,
            "warnings": warnings,
        }
