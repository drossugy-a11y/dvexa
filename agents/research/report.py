"""研究报告生成器 - 标准版"""


class ReportGenerator:
    """生成标准版研究报告"""
    
    def generate(self, stock: dict, analysis: dict) -> str:
        """生成 Markdown 格式研究报告"""
        report = f"""## {analysis.get('stock_name', '')} 研究报告
**日期：** 2024-01-15  |  **评分：** {stock.get('total_score', 0):.0f}/100  |  **建议：** {analysis.get('action', '观察')}

---

### 一、入选原因
{analysis.get('catalyst', '-')}

### 二、中线逻辑
{analysis.get('trend_logic', '-')}

### 三、风险提示
⚠️ {analysis.get('risk_alert', '-')}

### 四、观察建议
- **建议**：{analysis.get('action', '观察')}
- **评分详情**：成长={stock.get('growth', 0)}, 盈利={stock.get('profitability', 0)}, 估值={stock.get('valuation', 0)}, 健康={stock.get('health', 0)}, 质量={stock.get('quality', 0)}
"""
        return report
