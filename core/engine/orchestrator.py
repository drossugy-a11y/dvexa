"""主控编排器 - 串联所有模块"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import time
import uuid
import logging
from datetime import datetime

from strategies.regime.detector import RegimeDetector
from strategies.engine import StrategyEngine
from agents.analysis.factor_calc import FactorCalculator
from integrations import TradingAgentsWrapper
from agents.research.debate import StockDebater
from agents.trading.decision import TradeDecisionMaker
from core.memory.store import AnalysisMemory
from data.market.akshare_feed import AkshareFeed

logger = logging.getLogger(__name__)


class Orchestrator:
    """主控编排器 - 全流程串联"""

    def __init__(self):
        self.regime_detector = RegimeDetector()
        self.strategy_engine = StrategyEngine()
        self.factor_calc = FactorCalculator()
        self.ta_wrapper = TradingAgentsWrapper()
        self.debater = StockDebater()
        self.decision_maker = TradeDecisionMaker()
        self.memory = AnalysisMemory()
        self.data_feed = AkshareFeed()

    def run_daily_scan(self, progress_callback=None) -> dict:
        """每日扫描主流程"""

        scan_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        def log(msg):
            logger.info(msg)
            if progress_callback:
                progress_callback(msg)

        # Step 1: 检测市场状态
        log("[1/10] 检测市场状态...")
        regime_result = self.regime_detector.detect()
        regime = regime_result.get('regime', 'shock')
        log(f"  市场状态: {regime} (综合分: {regime_result.get('score', 0)})")

        # Step 2: 加载策略
        log("[2/10] 加载策略配置...")
        strategy_config = self.strategy_engine.load_strategy(regime)
        log(f"  策略: {strategy_config.get('name', '')}")

        # Step 3: 获取股票池
        log("[3/10] 获取A股股票池...")
        all_stocks = self.data_feed.get_stock_list()
        stock_pool = self._filter_stock_pool(all_stocks, strategy_config)
        log(f"  股票池: {len(stock_pool)} 只")

        # Step 4: 因子计算 + 初步筛选
        log("[4/10] 因子计算 + 初步筛选...")
        candidates = self._score_and_filter(stock_pool, strategy_config)
        log(f"  候选: {len(candidates)} 只")

        # Step 5: 检查缓存
        log("[5/10] 检查缓存...")
        to_analyze = []
        for c in candidates[:30]:
            cached = self.memory.get_cached_analysis(c.get('code', ''))
            if cached:
                c['analysis'] = cached
            else:
                to_analyze.append(c)
        log(f"  需分析: {len(to_analyze)} 只 (缓存命中: {len(candidates[:30]) - len(to_analyze)})")

        # Step 6: TradingAgents-CN 深度分析（Top 10）
        log("[6/10] 深度分析...")
        for i, stock in enumerate(to_analyze[:10]):
            ticker = stock.get('code', '')
            if self.ta_wrapper.is_available():
                result = self.ta_wrapper.analyze(ticker)
                stock['analysis'] = result
                self.memory.cache_analysis(ticker, result)
            time.sleep(0.5)

        # Step 7: 辩论
        log("[7/10] 研究员辩论...")
        debate_results = []
        for stock in candidates[:15]:
            dr = self.debater.debate(stock, stock, regime)
            debate_results.append(dr)

        # Step 8: 交易决策
        log("[8/10] 交易决策...")
        decisions = []
        for dr in debate_results:
            d = self.decision_maker.decide(dr, regime, strategy_config, dr)
            decisions.append(d)

        # 只保留 buy/hold
        top_decisions = [d for d in decisions if d.action in ('buy', 'hold')][:10]

        # Step 9: 保存结果
        log("[9/10] 保存结果...")
        scan_result = {
            'scan_id': scan_id,
            'regime': regime,
            'regime_result': regime_result,
            'strategy_name': strategy_config.get('name', ''),
            'candidates': [self._decision_to_dict(d) for d in top_decisions],
            'decisions': [self._decision_to_dict(d) for d in decisions],
        }
        self.memory.save_scan(scan_id, scan_result)
        self.memory.save_regime(datetime.now().strftime('%Y-%m-%d'), regime, regime_result.get('score', 0), regime_result)

        # Step 10: 返回
        log("[10/10] 扫描完成!")
        return scan_result

    def run_single_analysis(self, ticker: str) -> dict:
        """单股深度分析"""
        # 获取数据
        info = self.data_feed.get_stock_info(ticker)
        fin = self.data_feed.get_financial_indicators(ticker)

        # 因子计算
        scores = self.factor_calc.calculate(fin)

        # 辩论
        regime_result = self.regime_detector.detect()
        regime = regime_result.get('regime', 'shock')
        debate = self.debater.debate(info, scores, regime)

        # 决策
        decision = self.decision_maker.decide(debate, regime, {}, {**info, **scores})

        return {
            'ticker': ticker,
            'info': info,
            'scores': scores,
            'debate': debate.__dict__ if hasattr(debate, '__dict__') else debate,
            'decision': self._decision_to_dict(decision),
            'regime': regime_result,
        }

    def get_status(self) -> dict:
        """系统状态"""
        return {
            'trading_agents': self.ta_wrapper.is_available(),
            'llm_configured': bool(os.getenv('LLM_API_KEY')),
            'recent_scans': self.memory.get_recent_scans(5),
        }

    def _filter_stock_pool(self, stocks: list, config: dict) -> list:
        """筛选股票池"""
        filters = config.get('filters', {})
        pool = []
        for s in stocks:
            name = str(s.get('名称', ''))
            if filters.get('st_exclude') and 'ST' in name.upper():
                continue
            mc = self._safe_float(s.get('总市值'))
            if filters.get('min_market_cap') and mc < filters['min_market_cap']:
                continue
            price = self._safe_float(s.get('最新价'))
            if price <= 0:
                continue
            pool.append(s)
        return pool

    def _score_and_filter(self, pool: list, config: dict) -> list:
        """因子计算 + 筛选"""
        min_score = config.get('output', {}).get('min_score', 60)
        results = []
        for stock in pool[:200]:  # 限制处理数量
            code = stock.get('代码', '')
            if not code:
                continue
            fin = self.data_feed.get_financial_indicators(code)
            if fin.get('error'):
                continue
            scores = self.factor_calc.calculate(fin)
            if scores.get('total_score', 0) >= min_score:
                results.append({**stock, **scores, 'code': code})
        results.sort(key=lambda x: x.get('total_score', 0), reverse=True)
        return results

    def _decision_to_dict(self, d) -> dict:
        if hasattr(d, '__dict__'):
            return d.__dict__
        return d

    def _safe_float(self, v, default=0.0) -> float:
        try:
            return float(v) if v else default
        except:
            return default
