/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState } from 'react';
import { Stock } from '../types';
import { Sparkles, Plus, X, Search, Check } from 'lucide-react';

interface MultiAssetComparisonProps {
  stocks: Stock[];
  comparedIds: string[];
  onAddCompared: (id: string) => void;
  onRemoveCompared: (id: string) => void;
  onSelectStock: (stock: Stock) => void;
}

export default function MultiAssetComparison({
  stocks,
  comparedIds,
  onAddCompared,
  onRemoveCompared,
  onSelectStock
}: MultiAssetComparisonProps) {
  const [searchInput, setSearchInput] = useState('');
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);
  const [metricMode, setMetricMode] = useState<'TTM' | 'FY1_FWD'>('FY1_FWD');

  // Filter stocks currently selected
  const comparedStocks = stocks.filter(s => comparedIds.includes(s.id));

  // Eligible stocks to add
  const availableToAdd = stocks.filter(s => !comparedIds.includes(s.id) && (
    s.id.toLowerCase().includes(searchInput.toLowerCase()) ||
    s.nameZh.toLowerCase().includes(searchInput.toLowerCase())
  ));

  // Premium colors corresponding to compared indices (Luxurious Gold/Brass/Beige tones for Sophisticated Dark)
  const colors = [
    { text: 'text-[#d4af37]', bg: 'bg-[#d4af37]', fill: 'rgba(212, 175, 55, 0.16)', stroke: '#d4af37', hex: '#d4af37' },
    { text: 'text-[#ebd594]', bg: 'bg-[#ebd594]', fill: 'rgba(235, 213, 148, 0.15)', stroke: '#ebd594', hex: '#ebd594' },
    { text: 'text-[#eae0c8]', bg: 'bg-[#eae0c8]', fill: 'rgba(234, 224, 200, 0.15)', stroke: '#eae0c8', hex: '#eae0c8' },
    { text: 'text-[#aa8b2c]', bg: 'bg-[#aa8b2c]', fill: 'rgba(170, 139, 44, 0.15)', stroke: '#aa8b2c', hex: '#aa8b2c' },
    { text: 'text-[#f5c469]', bg: 'bg-[#f5c469]', fill: 'rgba(245, 196, 105, 0.15)', stroke: '#f5c469', hex: '#f5c469' }
  ];

  const getStockColor = (index: number) => colors[index % colors.length];

  // Helper to determine the best stock for a metric to highlight it
  const getBestStockForMetric = (metricKey: 'peForecast' | 'growthYoY' | 'margin' | 'debtRatio' | 'alpha1Y') => {
    if (comparedStocks.length === 0) return null;
    
    let bestStock: Stock = comparedStocks[0];
    let bestValue = parseFloat(comparedStocks[0].financials[metricKey].replace(/[x%]/g, ''));
    if (isNaN(bestValue)) bestValue = -999999;

    for (let i = 1; i < comparedStocks.length; i++) {
      const currentStock = comparedStocks[i];
      const origStr = currentStock.financials[metricKey];
      let value = parseFloat(origStr.replace(/[x%]/g, ''));
      if (isNaN(value)) value = -999999;

      if (metricKey === 'peForecast' || metricKey === 'debtRatio') {
        // Lower is better
        if (value !== -999999 && (bestValue === -999999 || value < bestValue)) {
          bestValue = value;
          bestStock = currentStock;
        }
      } else {
        // Higher is better
        if (value > bestValue) {
          bestValue = value;
          bestStock = currentStock;
        }
      }
    }
    return bestStock.id;
  };

  const bestPeStock = getBestStockForMetric('peForecast');
  const bestGrowthStock = getBestStockForMetric('growthYoY');
  const bestMarginStock = getBestStockForMetric('margin');
  const bestDebtStock = getBestStockForMetric('debtRatio');
  const bestAlphaStock = getBestStockForMetric('alpha1Y');

  // Handle adding stock
  const handleAddStock = (ticker: string) => {
    if (comparedIds.length >= 5) {
      alert("为保证图形清晰度，对比资产不宜超过5个。");
      return;
    }
    onAddCompared(ticker);
    setSearchInput('');
    setShowSearchDropdown(false);
  };

  return (
    <div className="space-y-6">
      {/* Search selection header */}
      <section className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface p-4 rounded-sm border border-border shadow-md">
        <div>
          <h2 className="text-display-lg font-bold text-white tracking-tight flex items-center gap-2">
            多资产因子透视
            <span className="text-xs bg-primary-container/15 text-primary-container border border-primary-container/20 px-2 py-0.5 rounded-xs font-mono">
              Beta / Factors Grid
            </span>
          </h2>
          <p className="text-xs font-mono text-text-secondary mt-1">
            动态叠加雷达因子与财务比率，快速对比得出多头组合权重。
          </p>
        </div>

        {/* Selected stocks control bar widgets */}
        <div className="flex flex-wrap items-center gap-2 bg-surface-container-low border border-border p-1.5 rounded-sm relative max-w-lg">
          {comparedStocks.map((stock, idx) => {
            const stockColor = getStockColor(idx);
            return (
              <div 
                key={stock.id} 
                className={`pl-2.5 pr-1.5 py-1 bg-surface-container-high rounded-xs border-l-2 text-xs font-mono font-bold text-white flex items-center gap-1.5 border-l-${stockColor.stroke}`}
                style={{ borderLeftColor: stockColor.hex }}
              >
                <span className="cursor-pointer hover:underline" onClick={() => onSelectStock(stock)}>{stock.id}</span>
                <button 
                  onClick={() => comparedIds.length > 1 ? onRemoveCompared(stock.id) : alert("对比标的不可清空。")} 
                  className="text-text-tertiary hover:text-error transition-colors p-0.5"
                  title="删除"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            );
          })}

          <div className="w-px h-5 bg-border mx-1" />

          {/* Quick Input Add dropdown */}
          <div className="relative">
            <div className="flex items-center text-xs font-mono pl-2">
              <Search className="w-3.5 h-3.5 text-text-tertiary mr-1.5 shrink-0" />
              <input 
                id="matrix-add-ticker-input"
                type="text"
                placeholder="添加多头代码..."
                value={searchInput}
                onFocus={() => setShowSearchDropdown(true)}
                onChange={(e) => setSearchInput(e.target.value)}
                className="bg-transparent border-none outline-none text-xs text-text-primary placeholder-text-tertiary w-32 focus:ring-0 p-0"
              />
            </div>

            {showSearchDropdown && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowSearchDropdown(false)} />
                <div className="absolute right-0 top-full mt-2 w-56 bg-surface-container-high border border-border rounded-sm shadow-xl z-20 py-1 max-h-48 overflow-y-auto">
                  {availableToAdd.length === 0 ? (
                    <div className="px-3 py-2 text-xs text-text-tertiary">没有可添加的标的</div>
                  ) : (
                    availableToAdd.map(stock => (
                      <button
                        key={stock.id}
                        onClick={() => handleAddStock(stock.id)}
                        className="w-full text-left px-3 py-1.5 text-xs text-text-secondary hover:text-white hover:bg-surface-container-highest transition-colors flex justify-between items-center"
                      >
                        <span className="font-mono font-semibold">{stock.id} ({stock.nameZh})</span>
                        <Plus className="w-3 h-3 text-primary-container" />
                      </button>
                    ))
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </section>

      {/* Grid panels */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Radar Overlay SVG Chart Column (4/12) */}
        <div className="lg:col-span-4 bg-surface border border-border rounded-sm p-4 flex flex-col justify-between h-full min-h-[420px]">
          <div>
            <h3 className="text-[13px] font-sans font-semibold text-text-primary tracking-wide mb-1 uppercase">因子多维叠加图</h3>
            <p className="text-[10px] font-mono text-text-tertiary uppercase">Strategic Overlay radar</p>
          </div>

          {/* SVG Multi Polygon overlay chart container */}
          <div className="flex-1 relative radar-chart-matrix rounded-sm border border-border/60 flex items-center justify-center my-4 overflow-hidden min-h-[240px]">
            <svg className="w-full h-full p-4 overflow-visible" viewBox="0 0 100 100">
              {/* Backing polar axis grid lines */}
              {[20, 35, 50].map((radius) => (
                <polygon 
                  key={radius} 
                  points={`
                    50,${50-radius} 
                    ${50 + radius * Math.cos(18 * Math.PI / 180)},${50 - radius * Math.sin(18 * Math.PI / 180)} 
                    ${50 + radius * Math.cos(54 * Math.PI / 180)},${50 + radius * Math.sin(54 * Math.PI / 180)} 
                    ${50 - radius * Math.cos(54 * Math.PI / 180)},${50 + radius * Math.sin(54 * Math.PI / 180)} 
                    ${50 - radius * Math.cos(18 * Math.PI / 180)},${50 - radius * Math.sin(18 * Math.PI / 180)}
                  `}
                  className="stroke-border fill-none opacity-80" 
                  strokeWidth="0.5" 
                />
              ))}

              {/* Axes lines spokes */}
              <line stroke="rgba(255,255,255,0.08)" strokeWidth="0.5" x1="50" x2="50" y1="50" y2="10"></line>
              <line stroke="rgba(255,255,255,0.08)" strokeWidth="0.5" x1="50" x2="90" y1="50" y2="37"></line>
              <line stroke="rgba(255,255,255,0.08)" strokeWidth="0.5" x1="50" x2="74" y1="50" y2="84"></line>
              <line stroke="rgba(255,255,255,0.08)" strokeWidth="0.5" x1="50" x2="26" y1="50" y2="84"></line>
              <line stroke="rgba(255,255,255,0.08)" strokeWidth="0.5" x1="50" x2="10" y1="50" y2="37"></line>

              {/* Axis Label nodes */}
              <text fill="#8E97A8" fontFamily="Inter" fontSize="3.5" textAnchor="middle" x="50" y="7">动量</text>
              <text fill="#8E97A8" fontFamily="Inter" fontSize="3.5" textAnchor="start" x="92" y="38">成长</text>
              <text fill="#8E97A8" fontFamily="Inter" fontSize="3.5" textAnchor="middle" x="74" y="89">质量</text>
              <text fill="#8E97A8" fontFamily="Inter" fontSize="3.5" textAnchor="middle" x="26" y="89">估值</text>
              <text fill="#8E97A8" fontFamily="Inter" fontSize="3.5" textAnchor="end" x="8" y="38">波动</text>

              {/* Overlay multi polygons */}
              {comparedStocks.map((stock, sIdx) => {
                const stockColor = getStockColor(sIdx);
                const mom = stock.factors['动量'] / 100;
                const gro = stock.factors['成长'] / 100;
                const qlt = stock.factors['质量'] / 100;
                const val = stock.factors['估值'] / 100;
                const vol = stock.factors['波动'] / 100;

                // Vertices calculated relative to center(50,50)
                const y1 = 50 - 40 * mom;

                const x2 = 50 + 40 * gro * Math.cos(18 * Math.PI / 180);
                const y2 = 50 - 40 * gro * Math.sin(18 * Math.PI / 180);

                const x3 = 50 + 40 * qlt * Math.cos(54 * Math.PI / 180);
                const y3 = 50 + 40 * qlt * Math.sin(54 * Math.PI / 180);

                const x4 = 50 - 40 * val * Math.cos(54 * Math.PI / 180);
                const y4 = 50 + 40 * val * Math.sin(54 * Math.PI / 180);

                const x5 = 50 - 40 * vol * Math.cos(18 * Math.PI / 180);
                const y5 = 50 - 40 * vol * Math.sin(18 * Math.PI / 180);

                const polyPts = `${50},${y1} ${x2},${y2} ${x3},${y3} ${x4},${y4} ${x5},${y5}`;

                return (
                  <polygon 
                    key={stock.id}
                    points={polyPts}
                    fill={stockColor.fill}
                    stroke={stockColor.stroke}
                    strokeWidth="1.2"
                    className="transition-all duration-300"
                  />
                );
              })}
            </svg>
          </div>

          {/* Legand elements */}
          <div className="flex flex-wrap justify-center gap-x-4 gap-y-1.5 text-[11px] font-mono">
            {comparedStocks.map((stock, sIdx) => {
              const stockColor = getStockColor(sIdx);
              return (
                <div key={stock.id} className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: stockColor.hex }} />
                  <span className="text-white hover:underline cursor-pointer" onClick={() => onSelectStock(stock)}>{stock.id}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Financial Comparison Quantitative Matrix (8/12) */}
        <div className="lg:col-span-8 bg-surface border border-border rounded-sm flex flex-col justify-between h-full min-h-[420px]">
          {/* Internal Header panel */}
          <div className="p-4 border-b border-border flex justify-between items-center bg-surface-container-low/35 rounded-t-sm">
            <div>
              <h3 className="text-[13px] font-sans font-semibold text-text-primary tracking-wide">量化分析矩阵</h3>
              <p className="text-[10px] font-mono text-text-tertiary uppercase">Quantitative Multi-metric Comparison</p>
            </div>
            {/* TTM vs Fwd buttons */}
            <div className="flex gap-1">
              <button 
                onClick={() => setMetricMode('TTM')}
                className={`px-2.5 py-1 text-[10px] font-mono rounded-xs transition-colors ${
                  metricMode === 'TTM' 
                    ? 'bg-surface-container-high text-white font-semibold' 
                    : 'border border-border text-text-tertiary hover:bg-surface-container-high/40'
                }`}
              >
                TTM Mode
              </button>
              <button 
                onClick={() => setMetricMode('FY1_FWD')}
                className={`px-2.5 py-1 text-[10px] font-mono rounded-xs transition-colors ${
                  metricMode === 'FY1_FWD' 
                    ? 'bg-surface-container-high text-white font-semibold' 
                    : 'border border-border text-text-tertiary hover:bg-surface-container-high/40'
                }`}
              >
                FY1 FWD
              </button>
            </div>
          </div>

          {/* Table Container */}
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="text-[10px] font-mono text-text-tertiary border-b border-border bg-surface-container-lowest/25">
                  <th className="p-4 font-normal w-1/4 uppercase tracking-wider">测算指标 / Metrics</th>
                  {comparedStocks.map((stock, idx) => {
                    const blockCol = getStockColor(idx);
                    return (
                      <th key={stock.id} className="p-4 font-bold w-1/4">
                        <div className="flex items-center gap-1.5 cursor-pointer hover:underline" onClick={() => onSelectStock(stock)}>
                          <span className="text-white">{stock.id}</span>
                          <span className={`text-[9px] ${blockCol.text}`}>●</span>
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="text-xs font-mono text-text-primary">
                {/* Row 1: PE */}
                <tr className="border-b border-border/60 hover:bg-surface-container-low/30 transition-colors">
                  <td className="p-4 hover:text-white transition-colors">
                    <span className="text-text-secondary">市盈率 (预测)</span>
                    <span className="block text-[10px] text-text-tertiary font-mono">P/E Ratio (Fwd)</span>
                  </td>
                  {comparedStocks.map((stock) => {
                    const isBest = stock.id === bestPeStock;
                    return (
                      <td key={stock.id} className={`p-4 ${isBest ? 'shimmer-ai text-[#d4af37] font-extrabold' : 'text-on-surface'}`}>
                        {stock.financials.peForecast}
                      </td>
                    );
                  })}
                </tr>

                {/* Row 2: Revenue Growth */}
                <tr className="border-b border-border/60 hover:bg-surface-container-low/30 transition-colors">
                  <td className="p-4 hover:text-white transition-colors">
                    <span className="text-text-secondary">营收增长 (同比)</span>
                    <span className="block text-[10px] text-text-tertiary font-mono">YoY Revenue Growth</span>
                  </td>
                  {comparedStocks.map((stock) => {
                    const isBest = stock.id === bestGrowthStock;
                    return (
                      <td key={stock.id} className={`p-4 ${isBest ? 'shimmer-ai text-[#d4af37] font-extrabold' : 'text-on-surface'}`}>
                        {stock.financials.growthYoY}
                      </td>
                    );
                  })}
                </tr>

                {/* Row 3: Margin */}
                <tr className="border-b border-border/60 hover:bg-surface-container-low/30 transition-colors">
                  <td className="p-4 hover:text-white transition-colors">
                    <span className="text-text-secondary">销售毛利率</span>
                    <span className="block text-[10px] text-text-tertiary font-mono">Gross Margin</span>
                  </td>
                  {comparedStocks.map((stock) => {
                    const isBest = stock.id === bestMarginStock;
                    return (
                      <td key={stock.id} className={`p-4 ${isBest ? 'shimmer-ai text-[#d4af37] font-extrabold' : 'text-on-surface'}`}>
                        {stock.financials.margin}
                      </td>
                    );
                  })}
                </tr>

                {/* Row 4: Debt Ratio */}
                <tr className="border-b border-border/60 hover:bg-surface-container-low/30 transition-colors">
                  <td className="p-4 hover:text-white transition-colors">
                    <span className="text-text-secondary">资产负债率</span>
                    <span className="block text-[10px] text-text-tertiary font-mono">Debt-to-Asset Ratio</span>
                  </td>
                  {comparedStocks.map((stock) => {
                    const isBest = stock.id === bestDebtStock;
                    const stockIdx = comparedStocks.findIndex(s => s.id === stock.id);
                    const specificCol = getStockColor(stockIdx);
                    return (
                      <td key={stock.id} className={`p-4 ${isBest ? `shimmer-ai ${specificCol.text} font-extrabold` : 'text-on-surface'}`}>
                        {stock.financials.debtRatio}
                      </td>
                    );
                  })}
                </tr>

                {/* Row 5: Alpha */}
                <tr className="hover:bg-surface-container-low/30 transition-colors">
                  <td className="p-4 hover:text-white transition-colors">
                    <span className="text-text-secondary">超额收益率 Alpha</span>
                    <span className="block text-[10px] text-text-tertiary font-mono">1Yr Alpha (Realized)</span>
                  </td>
                  {comparedStocks.map((stock) => {
                    const isBest = stock.id === bestAlphaStock;
                    const valNum = parseFloat(stock.financials.alpha1Y);
                    const isPositive = valNum >= 0;
                    return (
                      <td key={stock.id} className={`p-4 ${isBest ? 'shimmer-ai text-[#d4af37] font-extrabold' : isPositive ? 'text-secondary-fixed' : 'text-error'}`}>
                        {isPositive ? '+' : ''}{stock.financials.alpha1Y}
                      </td>
                    );
                  })}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* AI Comparative Summary Panel */}
      <section className="bg-surface-container-low border border-border rounded-sm p-4.5 flex gap-4 shimmer-ai">
        <div className="text-secondary mt-1 shrink-0">
          <Sparkles className="w-5 h-5 animate-pulse text-secondary" />
        </div>
        <div className="text-xs text-on-surface-variant leading-relaxed">
          <span className="text-white font-bold font-sans text-sm block mb-1">AI 独立量化研判摘要:</span>
          {comparedIds.includes('NVDA') && comparedIds.includes('AMD') && comparedIds.includes('TSLA') ? (
            <p>
              研究模型研判：<span className="text-primary-container font-semibold">NVDA</span> 在品质及扩展性指标方面享有压倒性估值霸权，同比超 125% 的极端高营收增长支撑了当前估值中枢，做多筹码依旧牢固。
              <span className="text-secondary-fixed font-semibold ml-1">TSLA</span> 虽然持有最优异财务稳健度 (最低资产负债率 0.15)，但核心毛利润率以及阶段性动量正处于周期筑底状态。
              <span className="text-tertiary-container font-semibold ml-1 font-mono">AMD</span> 目前定位为芯片大厂高性价比备选对冲品，拥有较保守的折价空间，提供一定边际安全。
            </p>
          ) : (
            <p>
              综合多因子多头叠加对比：
              {comparedStocks.map((stock, sIdx) => {
                const colorsArr = getStockColor(sIdx);
                return (
                  <span key={stock.id} className="mr-2">
                    <span className={`${colorsArr.text} font-bold font-mono`}>{stock.id}</span>
                    (综合评分: <span className="text-white">{stock.aiScore}</span>/100, {stock.ratingType})，
                  </span>
                )
              })}
              多头动量因子集中流向具有高度现金流壁垒及先进制程垄断的卓越企业。
              目前本组合中，超额表现（Alpha 1Y）最优的标的是
              <span className="text-primary-container font-bold font-mono ml-1">
                {bestAlphaStock}
              </span>。
              推荐在战术配置上，将部分仓位向高毛利率及稳定复合成长优势突出的核心权重股进行调增配置。
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
