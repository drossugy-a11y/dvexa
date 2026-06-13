"""FastAPI REST API 服务"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from core.engine.kernel import Kernel
from agents.research.analyzer import ResearchAnalyzer
from agents.research.report import ReportGenerator
from data.market.akshare_feed import AkshareFeed
from agents.analysis.factor_calc import FactorCalculator
from strategies.engine import StrategyEngine

app = FastAPI(title="DVexa Stock Radar", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化模块
kernel = Kernel()
data_feed = AkshareFeed()
factor_calc = FactorCalculator()
strategy_engine = StrategyEngine()
researcher = ResearchAnalyzer()
report_gen = ReportGenerator()


@app.get("/api/health")
def health():
    """健康检查"""
    return {"status": "ok"}


@app.get("/api/stocks")
def get_stocks(
    top_n: int = Query(default=10, ge=1, le=50),
    pe_min: float = Query(default=0),
    pe_max: float = Query(default=200),
    industry: Optional[str] = Query(default=None)
):
    """获取 Top N 股票列表"""
    try:
        # 检测市场状态
        regime = strategy_engine.detect_regime()
        strategy = strategy_engine.load_strategy(regime)
        
        # 获取数据
        stocks = data_feed.get_stock_list(industry=industry)
        
        # 计算因子并筛选
        results = []
        for stock in stocks[:100]:
            code = stock.get('代码', '')
            if not code:
                continue
            
            fin = data_feed.get_financial_indicators(code)
            if fin.get('error'):
                continue
            
            factors = factor_calc.calculate(fin)
            stock_data = {**stock, **factors, 'code': code}
            
            # 应用策略过滤
            if strategy_engine._apply_filters(stock_data, strategy.get('filters', {})):
                results.append(stock_data)
        
        # 排序
        results.sort(key=lambda x: x.get('total_score', 0), reverse=True)
        results = results[:top_n]
        
        # 转换为前端格式
        stocks_json = []
        for r in results:
            stocks_json.append({
                'id': r.get('code', ''),
                'name': r.get('名称', ''),
                'price': r.get('最新价', 0),
                'changePercent': r.get('涨跌幅', 0),
                'aiScore': round(r.get('total_score', 0)),
                'factors': {
                    '动量': r.get('growth', 50),
                    '成长': r.get('growth', 50),
                    '质量': r.get('profitability', 50),
                    '估值': r.get('valuation', 50),
                    '波动': r.get('health', 50)
                }
            })
        
        return {
            "stocks": stocks_json,
            "total": len(stocks_json),
            "regime": regime,
            "strategy": strategy.get('name', '')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/{code}")
def get_stock_detail(code: str):
    """获取单只股票详情"""
    try:
        # 获取数据
        info = data_feed.get_stock_info(code)
        fin = data_feed.get_financial_indicators(code)
        
        if fin.get('error'):
            raise HTTPException(status_code=404, detail=f"无法获取 {code} 数据")
        
        # 计算因子
        factors = factor_calc.calculate(fin)
        
        # AI 分析
        stock_data = {**info, **factors, 'code': code}
        analysis = researcher.analyze(stock_data)
        
        # 生成报告
        report = report_gen.generate(stock_data, analysis)
        
        return {
            "id": code,
            "name": info.get('name', ''),
            "factors": factors,
            "analysis": analysis,
            "report": report
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze")
def run_analysis():
    """运行完整分析"""
    try:
        result = kernel.run()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Phase 3: 新增端点 ─────────────────────────────────

import threading
from core.engine.orchestrator import Orchestrator
from core.memory.store import AnalysisMemory

orchestrator = Orchestrator()
memory = AnalysisMemory()

# 后台扫描状态
_scan_status = {}


class ScanRequest(BaseModel):
    depth: Optional[int] = 3


class ConfirmRequest(BaseModel):
    scan_id: str
    confirmed_tickers: list[str]


@app.post("/api/scan")
def start_scan(req: ScanRequest):
    """触发新一轮扫描（后台运行）"""
    scan_id = f"scan_{len(_scan_status) + 1}"

    def _run():
        try:
            _scan_status[scan_id] = {"status": "running", "progress": [], "result": None}
            result = orchestrator.run_daily_scan(
                progress_callback=lambda msg: _scan_status[scan_id]["progress"].append(msg)
            )
            _scan_status[scan_id]["status"] = "done"
            _scan_status[scan_id]["result"] = result
        except Exception as e:
            _scan_status[scan_id]["status"] = "failed"
            _scan_status[scan_id]["error"] = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"scan_id": scan_id, "status": "running"}


@app.get("/api/scan/{scan_id}")
def get_scan(scan_id: str):
    """查询扫描结果"""
    if scan_id in _scan_status:
        return _scan_status[scan_id]
    # 从数据库查找
    result = memory.get_scan(scan_id)
    if result:
        return {"status": "done", "result": result}
    raise HTTPException(status_code=404, detail="Scan not found")


@app.get("/api/regime")
def get_regime():
    """获取当前市场状态"""
    try:
        regime = orchestrator.regime_detector.detect()
        return regime
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pending")
def get_pending():
    """获取待确认的选股结果"""
    scans = memory.get_recent_scans(1)
    if not scans:
        return {"scan_id": None, "decisions": []}
    latest = memory.get_scan(scans[0]['scan_id'])
    if not latest:
        return {"scan_id": None, "decisions": []}
    return {
        "scan_id": latest.get('scan_id'),
        "decisions": latest.get('decisions', []),
    }


@app.post("/api/confirm")
def confirm_trade(req: ConfirmRequest):
    """确认下单"""
    confirmed = []
    skipped = []
    for ticker in req.confirmed_tickers:
        memory.confirm_trade(ticker, req.scan_id)
        confirmed.append(ticker)
    return {"status": "confirmed", "confirmed": confirmed, "skipped": skipped}


@app.get("/api/history")
def get_history():
    """获取扫描历史"""
    scans = memory.get_recent_scans(20)
    return {"scans": scans}
