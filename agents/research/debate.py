"""研究 Agent - 看涨/看跌辩论"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)


@dataclass
class DebateResult:
    ticker: str
    bull_argument: str
    bear_argument: str
    bull_score: float      # 0-100
    bear_score: float      # 0-100
    verdict: str           # 'bull_win' | 'bear_win' | 'neutral'
    confidence: float      # 0-1
    key_factors: list      # 关键判断因子


class StockDebater:
    """股票辩论 Agent - 看涨/看跌双视角分析"""

    def __init__(self):
        self._cache = {}  # 同一天同一只股票不重复调用

    def debate(self, stock_data: dict, factor_scores: dict, regime: str) -> DebateResult:
        """执行看涨/看跌辩论

        Args:
            stock_data: 股票基础数据
            factor_scores: 因子评分
            regime: 市场状态
        """
        ticker = stock_data.get('code', stock_data.get('stock_code', ''))

        # 检查缓存
        cache_key = f"{ticker}_{datetime.now().strftime('%Y%m%d')}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not LLM_API_KEY:
            return self._fallback(ticker, factor_scores)

        try:
            client = self._get_client()

            # 看涨论证
            bull = self._call_llm(client, self._bull_prompt(stock_data, factor_scores, regime))
            # 看跌论证
            bear = self._call_llm(client, self._bear_prompt(stock_data, factor_scores, regime))
            # 裁判
            judge = self._call_llm(client, self._judge_prompt(bull, bear, factor_scores))

            result = DebateResult(
                ticker=ticker,
                bull_argument=bull,
                bear_argument=bear,
                bull_score=judge.get('bull_score', 50),
                bear_score=judge.get('bear_score', 50),
                verdict=judge.get('verdict', 'neutral'),
                confidence=judge.get('confidence', 0.5),
                key_factors=judge.get('key_factors', []),
            )

            self._cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"辩论失败 {ticker}: {e}")
            return self._fallback(ticker, factor_scores)

    def _get_client(self):
        from openai import OpenAI
        return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    def _call_llm(self, client, prompt: str) -> dict:
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是资深A股分析师。输出严格JSON。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500,
            )
            content = response.choices[0].message.content.strip()
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            logger.warning(f"LLM 调用失败: {e}")
        return {}

    def _bull_prompt(self, stock: dict, scores: dict, regime: str) -> str:
        name = stock.get('name', stock.get('stock_code', ''))
        total = scores.get('total_score', 0)
        tech = scores.get('technical', {})
        return f"""你是看涨分析师。论证为什么应该买入 {name}。

数据：总分={total}, 动量20d={tech.get('momentum_20d', 'N/A')}, MA趋势={tech.get('ma_trend', 'N/A')}, 市场={regime}

返回JSON：
{{"argument": "看涨论证(3句话以内)", "score": 0-100}}"""

    def _bear_prompt(self, stock: dict, scores: dict, regime: str) -> str:
        name = stock.get('name', stock.get('stock_code', ''))
        total = scores.get('total_score', 0)
        val = scores.get('valuation_scores', {})
        return f"""你是看跌分析师。论证为什么不应该买入 {name}。

数据：总分={total}, PE评分={val.get('pe_score', 'N/A')}, PB评分={val.get('pb_score', 'N/A')}, 市场={regime}

返回JSON：
{{"argument": "看跌论证(3句话以内)", "score": 0-100}}"""

    def _judge_prompt(self, bull: str, bear: str, scores: dict) -> str:
        return f"""你是裁判。综合看涨和看跌观点，给出裁决。

看涨：{bull}
看跌：{bear}
总分：{scores.get('total_score', 0)}

返回JSON：
{{"bull_score": 0-100, "bear_score": 0-100, "verdict": "bull_win/bear_win/neutral", "confidence": 0-1, "key_factors": ["因子1", "因子2"]}}"""

    def _fallback(self, ticker: str, scores: dict) -> DebateResult:
        total = scores.get('total_score', 50)
        return DebateResult(
            ticker=ticker,
            bull_argument=f"综合评分 {total:.0f} 分",
            bear_argument="LLM 不可用，无法深度分析",
            bull_score=total,
            bear_score=100 - total,
            verdict='bull_win' if total > 60 else 'bear_win' if total < 40 else 'neutral',
            confidence=0.3,
            key_factors=['基础评分'],
        )
