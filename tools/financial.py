"""Financial Analyzer — 财务指标计算和评分

五维度评分体系：
  - 成长性评分（0-100）
  - 盈利能力评分（0-100）
  - 估值评分（0-100）
  - 财务健康评分（0-100）
  - 质量评分（0-100）
"""

from __future__ import annotations


class FinancialAnalyzer:
    def __init__(self, stock_data_tool=None):
        self._stock_data = stock_data_tool

    def call(self, input_data) -> dict:
        if isinstance(input_data, str):
            input_data = {"action": "score", "stock_code": input_data}
        action = input_data.get("action", "score")
        stock_code = input_data.get("stock_code", "")
        data = input_data.get("data", {})

        if action == "score":
            if not data and self._stock_data:
                data = self._stock_data.get_financial_indicators(stock_code)
            return self.calculate_composite_score(data)
        elif action == "growth":
            return self.calculate_growth_score(data)
        elif action == "profitability":
            return self.calculate_profitability_score(data)
        elif action == "valuation":
            return self.calculate_valuation_score(data)
        elif action == "health":
            return self.calculate_health_score(data)
        elif action == "quality":
            return self.calculate_quality_score(data)
        return {"error": f"unknown action: {action}"}

    def calculate_growth_score(self, financial_data: dict) -> dict:
        indicators = financial_data.get("indicators", {})
        revenue_growth = indicators.get("revenue_growth", [])
        profit_growth = indicators.get("net_profit_growth", [])

        score = 50.0
        details = []

        if revenue_growth:
            avg_rev = sum(float(x) for x in revenue_growth[:3] if x) / max(len(revenue_growth[:3]), 1)
            if avg_rev > 20:
                score += 20
                details.append(f"营收增速优秀({avg_rev:.1f}%)")
            elif avg_rev > 10:
                score += 10
                details.append(f"营收增速良好({avg_rev:.1f}%)")
            elif avg_rev < 0:
                score -= 15
                details.append(f"营收下滑({avg_rev:.1f}%)")

            if len(revenue_growth) >= 2:
                try:
                    trend = float(revenue_growth[0]) - float(revenue_growth[-1])
                    if trend > 5:
                        score += 10
                        details.append("增速加速趋势")
                    elif trend < -10:
                        score -= 10
                        details.append("增速放缓趋势")
                except (ValueError, TypeError):
                    pass

        if profit_growth:
            avg_profit = sum(float(x) for x in profit_growth[:3] if x) / max(len(profit_growth[:3]), 1)
            if avg_profit > 25:
                score += 15
                details.append(f"利润增速优秀({avg_profit:.1f}%)")
            elif avg_profit < 0:
                score -= 15
                details.append(f"利润下滑({avg_profit:.1f}%)")

        return {"dimension": "growth", "score": max(0, min(100, score)), "details": details}

    def calculate_profitability_score(self, financial_data: dict) -> dict:
        indicators = financial_data.get("indicators", {})
        roe = indicators.get("roe", [])
        gross_margin = indicators.get("gross_margin", [])

        score = 50.0
        details = []

        if roe:
            try:
                latest_roe = float(roe[0])
                if latest_roe > 20:
                    score += 25
                    details.append(f"ROE优秀({latest_roe:.1f}%)")
                elif latest_roe > 15:
                    score += 15
                    details.append(f"ROE良好({latest_roe:.1f}%)")
                elif latest_roe < 8:
                    score -= 15
                    details.append(f"ROE偏低({latest_roe:.1f}%)")
            except (ValueError, TypeError, IndexError):
                pass

            if len(roe) >= 3:
                try:
                    roe_vals = [float(x) for x in roe[:3] if x]
                    if roe_vals and all(r > 15 for r in roe_vals):
                        score += 10
                        details.append("连续3年ROE>15%")
                except (ValueError, TypeError):
                    pass

        if gross_margin:
            try:
                latest_gm = float(gross_margin[0])
                if latest_gm > 40:
                    score += 15
                    details.append(f"毛利率优秀({latest_gm:.1f}%)")
                elif latest_gm > 25:
                    score += 5
                    details.append(f"毛利率良好({latest_gm:.1f}%)")
            except (ValueError, TypeError, IndexError):
                pass

        return {"dimension": "profitability", "score": max(0, min(100, score)), "details": details}

    def calculate_valuation_score(self, financial_data: dict) -> dict:
        indicators = financial_data.get("indicators", {})
        eps = indicators.get("eps", [])
        bvps = indicators.get("bvps", [])

        score = 50.0
        details = []

        if eps:
            try:
                latest_eps = float(eps[0])
                if latest_eps > 0 and len(eps) >= 2:
                    growth = (float(eps[0]) - float(eps[1])) / abs(float(eps[1])) * 100 if float(eps[1]) != 0 else 0
                    if growth > 20:
                        score += 15
                        details.append(f"EPS增速良好({growth:.1f}%)")
                    elif growth < -20:
                        score -= 15
                        details.append(f"EPS下滑({growth:.1f}%)")
            except (ValueError, TypeError, IndexError):
                pass

        if bvps:
            try:
                latest_bvps = float(bvps[0])
                if latest_bvps > 0:
                    score += 10
                    details.append(f"每股净资产充裕({latest_bvps:.2f}元)")
            except (ValueError, TypeError, IndexError):
                pass

        return {"dimension": "valuation", "score": max(0, min(100, score)), "details": details}

    def calculate_health_score(self, financial_data: dict) -> dict:
        indicators = financial_data.get("indicators", {})
        debt_ratio = indicators.get("debt_ratio", [])
        current_ratio = indicators.get("current_ratio", [])
        cash_flow = indicators.get("cash_flow_per_share", [])

        score = 50.0
        details = []

        if debt_ratio:
            try:
                latest_debt = float(debt_ratio[0])
                if latest_debt < 40:
                    score += 20
                    details.append(f"资产负债率优秀({latest_debt:.1f}%)")
                elif latest_debt < 60:
                    score += 10
                    details.append(f"资产负债率合理({latest_debt:.1f}%)")
                elif latest_debt > 75:
                    score -= 20
                    details.append(f"资产负债率过高({latest_debt:.1f}%)")
            except (ValueError, TypeError, IndexError):
                pass

        if current_ratio:
            try:
                latest_cr = float(current_ratio[0])
                if latest_cr > 2:
                    score += 10
                    details.append(f"流动比率充裕({latest_cr:.2f})")
                elif latest_cr < 1:
                    score -= 15
                    details.append(f"流动比率不足({latest_cr:.2f})")
            except (ValueError, TypeError, IndexError):
                pass

        if cash_flow:
            try:
                latest_cf = float(cash_flow[0])
                if latest_cf > 0:
                    score += 15
                    details.append(f"每股经营现金流为正({latest_cf:.2f}元)")
                else:
                    score -= 10
                    details.append("经营现金流为负")
            except (ValueError, TypeError, IndexError):
                pass

        return {"dimension": "health", "score": max(0, min(100, score)), "details": details}

    def calculate_quality_score(self, financial_data: dict) -> dict:
        indicators = financial_data.get("indicators", {})
        gross_margin = indicators.get("gross_margin", [])
        roe = indicators.get("roe", [])

        score = 50.0
        details = []

        if gross_margin and len(gross_margin) >= 3:
            try:
                gm_vals = [float(x) for x in gross_margin[:3] if x]
                if gm_vals:
                    avg_gm = sum(gm_vals) / len(gm_vals)
                    std_gm = (sum((x - avg_gm) ** 2 for x in gm_vals) / len(gm_vals)) ** 0.5
                    if std_gm < 3:
                        score += 15
                        details.append("毛利率稳定性优秀")
                    elif std_gm > 10:
                        score -= 10
                        details.append("毛利率波动较大")
            except (ValueError, TypeError):
                pass

        if roe and len(roe) >= 3:
            try:
                roe_vals = [float(x) for x in roe[:3] if x]
                if roe_vals and all(r > 15 for r in roe_vals):
                    score += 20
                    details.append("连续3年ROE>15%，持续性强")
                elif roe_vals and all(r > 10 for r in roe_vals):
                    score += 10
                    details.append("连续3年ROE>10%")
            except (ValueError, TypeError):
                pass

        return {"dimension": "quality", "score": max(0, min(100, score)), "details": details}

    def calculate_composite_score(self, financial_data: dict, weights: dict = None) -> dict:
        if weights is None:
            weights = {
                "growth": 0.25,
                "profitability": 0.25,
                "valuation": 0.20,
                "health": 0.15,
                "quality": 0.15,
            }

        dims = {
            "growth": self.calculate_growth_score(financial_data),
            "profitability": self.calculate_profitability_score(financial_data),
            "valuation": self.calculate_valuation_score(financial_data),
            "health": self.calculate_health_score(financial_data),
            "quality": self.calculate_quality_score(financial_data),
        }

        total = sum(dims[k]["score"] * weights.get(k, 0.2) for k in dims)
        stock_code = financial_data.get("stock_code", "")

        return {
            "stock_code": stock_code,
            "composite_score": round(total, 1),
            "dimensions": {k: v["score"] for k, v in dims.items()},
            "details": {k: v["details"] for k, v in dims.items()},
        }
