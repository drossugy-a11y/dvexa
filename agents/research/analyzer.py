"""研究分析 Agent - 深度分析股票"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


class ResearchAnalyzer:
    """研究分析 Agent"""
    
    def analyze(self, stock_data: dict) -> dict:
        """深度分析单只股票"""
        if not LLM_API_KEY:
            return self._fallback(stock_data)
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
            
            prompt = self._build_prompt(stock_data)
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是资深A股分析师，只做研究分析，不参与决策。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            return self._parse_response(stock_data, response.choices[0].message.content)
        except Exception as e:
            return self._fallback(stock_data)
    
    def _build_prompt(self, stock: dict) -> str:
        return f"""分析以下A股股票：

股票代码：{stock.get('code', '')}
股票名称：{stock.get('name', '')}
综合评分：{stock.get('total_score', 0):.1f}/100
五维评分：成长={stock.get('growth', 0)}, 盈利={stock.get('profitability', 0)}, 估值={stock.get('valuation', 0)}, 健康={stock.get('health', 0)}, 质量={stock.get('quality', 0)}

请返回JSON格式：
{{
  "catalyst": "入选原因(1-2句)",
  "trend_logic": "中线逻辑(2-3句)",
  "risk_alert": "风险提示(1-2句)",
  "action": "观察建议"
}}"""
    
    def _parse_response(self, stock: dict, content: str) -> dict:
        try:
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
                result['stock_code'] = stock.get('code', '')
                result['stock_name'] = stock.get('name', '')
                return result
        except:
            pass
        return self._fallback(stock)
    
    def _fallback(self, stock: dict) -> dict:
        return {
            'stock_code': stock.get('code', ''),
            'stock_name': stock.get('name', ''),
            'catalyst': '综合指标表现良好',
            'trend_logic': f"五维评分 {stock.get('total_score', 0):.0f} 分",
            'risk_alert': '请结合市场环境判断',
            'action': '观察'
        }
