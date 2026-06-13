/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState } from 'react';
import { Stock } from '../types';
import { 
  Plus, 
  Check, 
  Bookmark, 
  BookmarkCheck,
  TrendingUp, 
  TrendingDown, 
  ChevronDown,
  Info,
  LineChart,
  Grid,
  Heart,
  Radar,
  Activity
} from 'lucide-react';

interface StockDetailAnalysisProps {
  selectedStock: Stock;
  stocks: Stock[];
  onSelectStock: (stock: Stock) => void;
  onTradeClick: (stock: Stock) => void;
  onWatchlistToggle: (id: string) => void;
  isWatchlisted: boolean;
}

export default function StockDetailAnalysis({
  selectedStock,
  stocks,
  onSelectStock,
  onTradeClick,
  onWatchlistToggle,
  isWatchlisted
}: StockDetailAnalysisProps) {
  const [trendRange, setTrendRange] = useState<'6M' | '1Y'>('6M');
  const [showStockDropdown, setShowStockDropdown] = useState(false);

  // Vertices calculated relative to center (50, 50) of size 100x100
  // Corners: Momentum (Top), Growth (Right Top), Quality (Right Bottom), Value (Left Bottom), Volatility (Left Top)
  const mom = selectedStock.factors['动量'] / 100;
  const gro = selectedStock.factors['成长'] / 100;
  const qlt = selectedStock.factors['质量'] / 100;
  const val = selectedStock.factors['估值'] / 100;
  const vol = selectedStock.factors['波动'] / 100;

  const y1 = 50 - 36 * mom;

  const x2 = 50 + 36 * gro * Math.cos(18 * Math.PI / 180);
  const y2 = 50 - 36 * gro * Math.sin(18 * Math.PI / 180);

  const x3 = 50 + 36 * qlt * Math.cos(54 * Math.PI / 180);
  const y3 = 50 + 36 * qlt * Math.sin(54 * Math.PI / 180);

  const x4 = 50 - 36 * val * Math.cos(54 * Math.PI / 180);
  const y4 = 50 + 36 * val * Math.sin(54 * Math.PI / 180);

  const x5 = 50 - 36 * vol * Math.cos(18 * Math.PI / 180);
  const y5 = 50 - 36 * vol * Math.sin(18 * Math.PI / 180);

  const radarPoints = `${50},${y1} ${x2},${y2} ${x3},${y3} ${x4},${y4} ${x5},${y5}`;

  // Custom polyline points for dynamic trend area depending on stock's historical list
  const history = selectedStock.historyTrend;
  const maxIdx = history.length - 1;
  const linePoints = history.map((pt, idx) => {
    const x = (idx / maxIdx) * 100;
    // score ranges 0 - 100, map to SVG y: 90 - 10 (higher score is lower Y coordinate)
    const y = 90 - (pt.score / 100) * 80;
    return `${x},${y}`;
  }).join(' ');

  // Create polyline points string
  const polylineStr = linePoints;
  const areaPolygonStr = `0,100 ${linePoints} 100,100`;

  const isChangePositive = selectedStock.changePercent >= 0;

  return (
    <div className="space-y-6">
      {/* Dynamic Header Section */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-surface p-5 rounded-sm border border-border">
        <div className="relative">
          {/* Stock selector dropdown trigger */}
          <div className="flex items-center gap-3 mb-1.5">
            <div className="relative">
              <button 
                id="stock-selector-dropdown-btn"
                onClick={() => setShowStockDropdown(!showStockDropdown)}
                className="flex items-center gap-1.5 text-md font-sans font-bold text-white hover:text-primary transition-colors cursor-pointer"
              >
                <span>{selectedStock.name}</span>
                <ChevronDown className="w-4 h-4 text-text-tertiary" />
              </button>

              {/* Ticker dropdown */}
              {showStockDropdown && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setShowStockDropdown(false)} />
                  <div className="absolute left-0 mt-2.5 w-64 bg-surface-container-high border border-border rounded-sm shadow-2xl z-20 py-1.5 max-h-60 overflow-y-auto">
                    <p className="px-3.5 py-1 text-[10px] font-mono text-text-tertiary uppercase tracking-wider">选择分析标的 Tickers</p>
                    {stocks.map(s => (
                      <button
                        key={s.id}
                        id={`detail-select-${s.id}`}
                        onClick={() => {
                          onSelectStock(s);
                          setShowStockDropdown(false);
                        }}
                        className={`w-full text-left px-3.5 py-2 text-xs transition-colors flex justify-between items-center ${
                          s.id === selectedStock.id 
                            ? 'bg-primary-container/10 text-primary-container font-semibold' 
                            : 'text-text-secondary hover:text-white hover:bg-surface-container-highest'
                        }`}
                      >
                        <span className="font-mono">{s.id} · {s.nameZh}</span>
                        {s.id === selectedStock.id && <Check className="w-3.5 h-3.5" />}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            <span className="bg-primary/10 text-primary font-mono text-[10px] px-2 py-0.5 rounded-xs border border-primary/25 uppercase">
              {selectedStock.id}
            </span>
            <span className="bg-primary/10 text-primary font-mono text-[10px] px-2 py-0.5 rounded-xs border border-primary/25 uppercase tracking-wide">
              {selectedStock.sector}
            </span>
          </div>

          <p className="text-xs text-text-secondary font-mono">
            NASDAQ Global Select Market • 机构级阿尔法实时解算 / Real-time Computed Data
          </p>
        </div>

        {/* Global Control Widget buttons */}
        <div className="flex items-center gap-3.5 w-full sm:w-auto">
          <button 
            id="watchlist-btn"
            onClick={() => onWatchlistToggle(selectedStock.id)}
            className={`flex-1 sm:flex-none border px-4 py-2 rounded-xs font-sans text-xs transition-all flex items-center justify-center gap-2 ${
              isWatchlisted 
                ? 'bg-primary/10 border-primary/45 text-primary font-medium' 
                : 'text-text-secondary hover:text-white hover:bg-surface-container-high border-border/85'
            }`}
          >
            {isWatchlisted ? <BookmarkCheck className="w-[15px] h-[15px]" /> : <Bookmark className="w-[15px] h-[15px]" />}
            <span>{isWatchlisted ? '已加入自选' : '关注 Watchlist'}</span>
          </button>
          
          <button 
            id="trade-btn"
            onClick={() => onTradeClick(selectedStock)}
            className="flex-1 sm:flex-none bg-primary-container hover:bg-primary-container/90 active:scale-98 text-on-primary-container px-5 py-2 rounded-xs font-sans font-medium text-xs transition-all flex items-center justify-center gap-2 shadow-md"
          >
            <span>Bolt Trade 闪击交易</span>
          </button>
        </div>
      </header>

      {/* Top row bento block grid (Core metrics + radar + AI deep analysis) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Core metrics snapshot (3/12 width) */}
        <div className="lg:col-span-3 bg-surface border border-border rounded-sm p-5 shadow-sm flex flex-col justify-between min-h-[350px]">
          <h2 className="text-xs font-sans font-bold text-text-primary uppercase tracking-wide mb-3 flex items-center gap-2 border-b border-border/60 pb-2">
            <Heart className="w-3.5 h-3.5 text-text-tertiary" />
            核心主标指标 / Core Snap
          </h2>
          
          {/* Main Price Box */}
          <div className="my-1.5">
            <div className="flex justify-between items-end mb-1">
              <span className="text-[10px] font-mono text-text-tertiary uppercase">Current Price</span>
              <span className={`text-xs font-mono font-bold ${isChangePositive ? 'text-secondary' : 'text-error'}`}>
                {isChangePositive ? '+' : ''}{selectedStock.changePercent.toFixed(2)}%
              </span>
            </div>
            <div className="text-3xl leading-tight font-mono font-bold tracking-tight text-white">
              ${selectedStock.price.toFixed(2)}
            </div>
            <div className={`text-[11px] font-mono mt-1 ${isChangePositive ? 'text-secondary-fixed' : 'text-error'}`}>
              {isChangePositive ? '+$' : '-$'}{Math.abs(selectedStock.changeAmount).toFixed(2)} Today
            </div>
          </div>

          {/* Standard Metrics list */}
          <div className="space-y-2.5 pt-2.5 border-t border-border/60 text-xs font-mono">
            <div className="flex justify-between items-center py-1">
              <span className="text-text-secondary">交易量 (24H)</span>
              <span className="text-white font-bold">{selectedStock.volume}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-t border-border/30">
              <span className="text-text-secondary">总市值 Cap</span>
              <span className="text-white font-bold">{selectedStock.marketCap}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-t border-border/30">
              <span className="text-text-secondary">市盈率 P/E TTM</span>
              <span className="text-white font-bold">{selectedStock.peRatio !== null ? selectedStock.peRatio : '亏损/NA'}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-t border-border/30">
              <span className="text-text-secondary">波动 Beta (5Y)</span>
              <span className="text-white font-bold">{selectedStock.beta}</span>
            </div>
          </div>
        </div>

        {/* Middle Column: Factor Radar (5/12 width) */}
        <div className="lg:col-span-5 bg-surface border border-border rounded-sm p-4.5 flex flex-col justify-between h-full min-h-[350px]">
          <div className="border-b border-border/60 pb-2">
            <h2 className="text-xs font-sans font-bold text-text-primary uppercase tracking-wide flex items-center gap-2">
              <Radar className="w-3.5 h-3.5 text-text-tertiary" />
              五维量化因子拆解 / Factor Radar
            </h2>
            <p className="text-[10px] font-mono text-text-secondary mt-1">
              AI智能综合研判评分: 
              <span className="text-primary font-mono font-extrabold text-sm ml-1.5">{selectedStock.aiScore} / 100</span>
              <span className="ml-1 text-text-tertiary">({selectedStock.ratingType})</span>
            </p>
          </div>

          {/* Central responsive SVG radar */}
          <div className="flex-1 relative radar-chart-gradient rounded-sm border border-border/50 flex items-center justify-center my-4 min-h-[200px] overflow-hidden">
            <svg className="w-full h-full p-4 overflow-visible" viewBox="0 0 100 100">
              {/* Backing polar mesh lines */}
              {[15, 27, 39].map(radius => (
                <polygon 
                  key={radius} 
                  points={`
                    50,${50-radius} 
                    ${50 + radius * Math.cos(18 * Math.PI / 180)},${50 - radius * Math.sin(18 * Math.PI / 180)} 
                    ${50 + radius * Math.cos(54 * Math.PI / 180)},${50 + radius * Math.sin(54 * Math.PI / 180)} 
                    ${50 - radius * Math.cos(54 * Math.PI / 180)},${50 + radius * Math.sin(54 * Math.PI / 180)} 
                    ${50 - radius * Math.cos(18 * Math.PI / 180)},${50 - radius * Math.sin(18 * Math.PI / 180)}
                  `}
                  className="stroke-border fill-none" 
                  strokeWidth="0.5" 
                />
              ))}

              {/* spoke axes */}
              <line x1="50" y1="50" x2="50" y2="10" className="stroke-border" strokeWidth="0.5" />
              <line x1="50" y1="50" x2="88" y2="38" className="stroke-border" strokeWidth="0.5" />
              <line x1="50" y1="50" x2="73" y2="84" className="stroke-border" strokeWidth="0.5" />
              <line x1="50" y1="50" x2="27" y2="84" className="stroke-border" strokeWidth="0.5" />
              <line x1="50" y1="50" x2="12" y2="38" className="stroke-border" strokeWidth="0.5" />

              {/* Factor Polygon */}
              <polygon 
                points={radarPoints} 
                className="stroke-primary fill-primary/18 transition-all duration-300" 
                strokeWidth="1.2" 
              />
              
              {/* Vertices dot highlights */}
              <circle cx="50" cy={y1} r="1.5" className="fill-white" />
              <circle cx={x2} cy={y2} r="1.5" className="fill-white" />
              <circle cx={x3} cy={y3} r="1.5" className="fill-white" />
              <circle cx={x4} cy={y4} r="1.5" className="fill-white" />
              <circle cx={x5} cy={y5} r="1.5" className="fill-white" />
            </svg>

            {/* Corner Labels absolute nodes */}
            <span className="absolute top-[2%] left-1/2 -translate-x-1/2 text-[10px] font-mono text-white font-semibold">动量 ({selectedStock.factors['动量']})</span>
            <span className="absolute top-[32%] right-[1%] text-[10px] font-mono text-white font-semibold">成长 ({selectedStock.factors['成长']})</span>
            <span className="absolute bottom-[2%] right-[12%] text-[10px] font-mono text-white font-semibold">质量 ({selectedStock.factors['质量']})</span>
            <span className="absolute bottom-[2%] left-[12%] text-[10px] font-mono text-white font-semibold">估值 ({selectedStock.factors['估值']})</span>
            <span className="absolute top-[32%] left-[1%] text-[10px] font-mono text-white font-semibold">波动 ({selectedStock.factors['波动']})</span>
          </div>
        </div>

        {/* Right Column: AI Deep Analysis scroll view (4/12 width) */}
        <div className="lg:col-span-4 bg-surface-container-low border border-border rounded-sm h-[350px] overflow-hidden flex flex-col relative">
          {/* Top colored aesthetic block line */}
          <div className="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-primary-container via-secondary to-primary-container opacity-60" />
          
          <div className="p-4 flex-1 flex flex-col overflow-hidden">
            <h2 className="text-xs font-sans font-bold text-text-primary uppercase tracking-wide border-b border-border/60 pb-2 mb-3 flex items-center gap-2">
              <Info className="w-3.5 h-3.5 text-primary-container" />
              AI 智能深度多头研判 / Deep Quant Analysis
            </h2>

            {/* Scrollable pane */}
            <div className="flex-1 overflow-y-auto pr-1.5 space-y-4">
              {/* Catalysts */}
              <div>
                <h3 className="text-[10px] font-mono text-text-secondary uppercase mb-1.5 border-l-2 border-secondary pl-2 leading-none font-bold">
                  入选催化剂原因 (Catalysts)
                </h3>
                <p className="text-xs text-on-surface leading-relaxed font-sans">
                  {selectedStock.aiAnalysis.catalysts}
                </p>
              </div>

              {/* Trend Logic */}
              <div>
                <h3 className="text-[10px] font-mono text-text-secondary uppercase mb-1.5 border-l-2 border-primary-container pl-2 leading-none font-bold">
                  量能趋势逻辑 (Trend Logic)
                </h3>
                <p className="text-xs text-on-surface leading-relaxed font-sans">
                  {selectedStock.aiAnalysis.trendLogic}
                </p>
              </div>

              {/* Risk details */}
              <div>
                <h3 className="text-[10px] font-mono text-text-secondary uppercase mb-1.5 border-l-2 border-error pl-2 leading-none font-bold">
                  宏观及溢价风险提示 (Risk Alerts)
                </h3>
                <p className="text-xs text-on-surface leading-relaxed font-sans">
                  {selectedStock.aiAnalysis.riskAlerts}
                </p>
              </div>

              {/* collar option strategic action advice block */}
              <div className="bg-surface border border-border p-3.5 rounded-sm">
                <h3 className="text-[10px] font-mono text-primary uppercase mb-1.5 flex items-center gap-1.5 leading-none font-bold">
                  <Activity className="w-3 h-3 text-primary" />
                  战术策略配置建议 (Options Collar Action)
                </h3>
                <p className="text-xs text-on-surface leading-relaxed font-sans">
                  {selectedStock.aiAnalysis.action}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Row grid (Line Trend Area chart + Competitors peer comparison table) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Historical Rating rating trend (6/12 width) */}
        <div className="bg-surface border border-border rounded-sm p-4.5 flex flex-col justify-between">
          <div className="flex justify-between items-center mb-4 border-b border-border/60 pb-2 shrink-0">
            <h2 className="text-xs font-sans font-bold text-text-primary uppercase tracking-wide flex items-center gap-2">
              <LineChart className="w-3.5 h-3.5 text-text-tertiary" />
              阿尔法预测历史趋势 / Historical Score Trend
            </h2>

            {/* Time select option trigger */}
            <select 
              value={trendRange}
              onChange={(e) => setTrendRange(e.target.value as '6M' | '1Y')}
              className="bg-surface-container-high border-border text-text-secondary font-mono text-[10px] px-2.5 py-1 rounded-sm focus:ring-1 focus:ring-primary focus:border-primary shrink-0 outline-none hover:text-white"
            >
              <option value="6M">6 Months Timeline</option>
              <option value="1Y">1 Year Projection</option>
            </select>
          </div>

          {/* Filled Trend line graphs container */}
          <div className="h-44 w-full relative border-l border-b border-border/40 mt-3 pt-2">
            <svg className="absolute inset-0 w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 100">
              <defs>
                <linearGradient id="trendAreaGradient" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="#d4af37" stopOpacity="0.32" />
                  <stop offset="100%" stopColor="#d4af37" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Area path */}
              <polygon points={areaPolygonStr} fill="url(#trendAreaGradient)" className="transition-all duration-300" />
              
              {/* Line path */}
              <polyline 
                points={polylineStr} 
                fill="none" 
                stroke="#d4af37" 
                strokeWidth="1.8" 
                strokeLinecap="round"
                className="transition-all duration-300" 
              />

              {/* Highlighting dot pointers */}
              {history.map((pt, idx) => {
                const cx = (idx / maxIdx) * 100;
                const cy = 90 - (pt.score / 100) * 80;
                return (
                  <circle 
                    key={idx} 
                    cx={cx} 
                    cy={cy} 
                    r="2" 
                    className="fill-white stroke-primary stroke-1 hover:r-3.5 transition-all cursor-pointer" 
                    title={`Score: ${pt.score}`}
                  />
                );
              })}
            </svg>

            {/* Static Axis helper Labels */}
            <div className="absolute -left-6 top-[8px] text-[9px] font-mono text-text-tertiary">100</div>
            <div className="absolute -left-6 bottom-[4px] text-[9px] font-mono text-text-tertiary">0</div>

            <div className="absolute left-[-2px] bottom-[-18px] text-[9px] font-mono text-text-tertiary">{history[0].label}</div>
            <div className="absolute right-[-2px] bottom-[-18px] text-[9px] font-mono text-text-tertiary">{history[maxIdx].label}</div>
          </div>
        </div>

        {/* Competitor Peer matrix table (6/12 width) */}
        <div className="bg-surface border border-border rounded-sm p-4.5 overflow-x-auto flex flex-col justify-between">
          <h2 className="text-xs font-sans font-bold text-text-primary uppercase tracking-wide flex items-center gap-2 border-b border-border/60 pb-2 mb-3">
            <Grid className="w-3.5 h-3.5 text-text-tertiary" />
            竞品多因子矩阵对标 / Peer Comparison Model (Semiconductors)
          </h2>

          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border/80 text-[10px] font-mono text-text-tertiary uppercase tracking-wider bg-surface-container-low/15">
                  <th className="py-2.5 px-3 font-normal">标的代码 / Ticker</th>
                  <th className="py-2.5 px-3 font-normal">AI综合评分</th>
                  <th className="py-2.5 px-3 font-normal">TTM 市盈率</th>
                  <th className="py-2.5 px-3 font-normal">营收同比增速 YoY</th>
                  <th className="py-2.5 px-3 font-normal text-right">动能趋势 / Trend</th>
                </tr>
              </thead>
              <tbody className="text-xs font-mono text-white">
                {selectedStock.peers.map((peer) => {
                  const correlatedStock = stocks.find(s => s.id === peer.ticker);
                  const isUp = peer.trend === 'up';
                  return (
                    <tr 
                      key={peer.ticker} 
                      className="border-b border-border/50 hover:bg-surface-container-high/40 transition-colors last:border-none"
                    >
                      <td className="py-3 px-3 font-bold">
                        <button 
                          onClick={() => {
                            if (correlatedStock) onSelectStock(correlatedStock);
                          }}
                          className="hover:underline hover:text-primary text-left"
                        >
                          {peer.ticker}
                        </button>
                        <span className="block text-[10px] text-text-tertiary font-sans font-normal mt-0.5">{peer.name}</span>
                      </td>
                      <td className="py-3 px-3">
                        <span className={`font-extrabold ${peer.score >= 85 ? 'text-secondary-fixed' : peer.score >= 70 ? 'text-primary-container' : 'text-error'}`}>
                          {peer.score}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-text-secondary">{peer.pe}</td>
                      <td className={`py-3 px-3 ${peer.growth.startsWith('-') ? 'text-error' : 'text-secondary-fixed font-semibold'}`}>
                        {peer.growth}
                      </td>
                      <td className="py-3 px-3 text-right">
                        {isUp ? (
                          <span className="inline-flex items-center text-secondary uppercase text-[10px] font-mono font-bold hover:brightness-110">
                            <TrendingUp className="w-3.5 h-3.5 text-secondary mr-1 animate-pulse" />
                            Bullish
                          </span>
                        ) : (
                          <span className="inline-flex items-center text-error uppercase text-[10px] font-mono font-bold hover:brightness-110">
                            <TrendingDown className="w-3.5 h-3.5 text-error mr-1 animate-pulse" />
                            Bearish
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
