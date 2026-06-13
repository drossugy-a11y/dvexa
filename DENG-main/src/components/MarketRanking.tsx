/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { Stock } from '../types';
import { TrendingUp, Sparkles, Activity, ShieldAlert, Cpu } from 'lucide-react';

interface MarketRankingProps {
  stocks: Stock[];
  searchQuery: string;
  onSelectStock: (stock: Stock) => void;
}

export default function MarketRanking({
  stocks,
  searchQuery,
  onSelectStock
}: MarketRankingProps) {
  
  // Filter stocks based on query
  const filteredStocks = stocks.filter(s => 
    s.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.nameZh.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.sector.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Sort them so the highest AI score comes first
  const sortedStocks = [...filteredStocks].sort((a, b) => b.aiScore - a.aiScore);

  return (
    <div className="space-y-6">
      {/* Upper Widgets: Market Sentiment & Indicators */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Core AI Index */}
        <div className="bg-surface border border-border p-4 rounded-sm flex flex-col justify-between h-24 hover:border-border/100 transition-colors">
          <div className="flex justify-between items-start">
            <span className="text-xs font-mono text-text-secondary">AI 情绪指数 / Global Sentiment</span>
            <TrendingUp className="text-secondary w-4 h-4" />
          </div>
          <div className="flex items-end gap-2.5">
            <span className="text-2xl font-bold tracking-tight text-secondary">84.2</span>
            <span className="text-xs font-mono text-secondary mb-1 font-semibold">+2.4%</span>
          </div>
        </div>

        {/* Global Flow Indicator */}
        <div className="bg-surface border border-border p-4 rounded-sm flex flex-col justify-between h-24 hover:border-border/100 transition-colors">
          <div className="flex justify-between items-start">
            <span className="text-xs font-mono text-text-secondary">全球资金流向 / Fund Inflow</span>
            <Activity className="text-primary-container w-4 h-4" />
          </div>
          <div className="flex items-end gap-2.5">
            <span className="text-xl font-bold tracking-tight text-white">$12.4B</span>
            <span className="text-xs font-mono text-secondary mb-1 font-semibold">净流入 / Net</span>
          </div>
        </div>

        {/* Option Volatility index */}
        <div className="bg-surface border border-border p-4 rounded-sm flex flex-col justify-between h-24 hover:border-border/100 transition-colors">
          <div className="flex justify-between items-start">
            <span className="text-xs font-mono text-text-secondary">波动率曲面 / VIX Surface</span>
            <ShieldAlert className="text-tertiary-container w-4 h-4" />
          </div>
          <div className="flex items-end gap-2.5">
            <span className="text-xl font-bold tracking-tight text-white">14.8</span>
            <span className="text-xs font-mono text-tertiary-container mb-1 font-semibold">-1.2%</span>
          </div>
        </div>

        {/* Live System state */}
        <div className="bg-surface border border-border p-4 rounded-sm flex flex-col justify-between h-24 hover:border-border/100 transition-colors">
          <div className="flex justify-between items-start">
            <span className="text-xs font-mono text-text-secondary">AI引擎状态 / Engine Status</span>
            <Cpu className="text-primary-container w-4 h-4" />
          </div>
          <div className="flex items-center gap-2 mt-auto">
            <div className="w-2.5 h-2.5 rounded-full bg-secondary-fixed animate-pulse" />
            <span className="text-xs font-mono text-secondary-fixed font-semibold">在线运行 / Computing Live</span>
          </div>
        </div>
      </section>

      {/* Category Header */}
      <div className="flex items-center gap-2 mb-4 border-b border-border pb-3">
        <Sparkles className="text-primary-container w-5 h-5 animate-pulse" />
        <h3 className="text-[15px] font-sans font-semibold text-text-primary uppercase tracking-wider">排名前列的AI资产评分 / Top Strategic AI Assets</h3>
      </div>

      {/* Main Grid Section */}
      {sortedStocks.length === 0 ? (
        <div className="bg-surface/50 border border-border p-12 text-center rounded-sm">
          <p className="text-text-secondary text-sm">未能匹配到相关股票，请尝试其他关键词。</p>
        </div>
      ) : (
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {sortedStocks.map((stock) => {
            
            // Calculate a mini polygon path inside 100x100
            // Polygon corners: Top(0,-40), RightTop(38,-12), RightBottom(24,32), LeftBottom(-24,32), LeftTop(-38,-12)
            // Center is (50, 50)
            const momentumRank = stock.factors['动量'] / 100;
            const growthRank = stock.factors['成长'] / 100;
            const qualityRank = stock.factors['质量'] / 100;
            const valueRank = stock.factors['估值'] / 100;
            const volatilityRank = stock.factors['波动'] / 100;

            const p1x = 50;
            const p1y = 50 - 32 * momentumRank;

            const p2x = 50 + 32 * growthRank * Math.cos(18 * Math.PI / 180);
            const p2y = 50 - 32 * growthRank * Math.sin(18 * Math.PI / 180);

            const p3x = 50 + 32 * qualityRank * Math.cos(54 * Math.PI / 180);
            const p3y = 50 + 32 * qualityRank * Math.sin(54 * Math.PI / 180);

            const p4x = 50 - 32 * valueRank * Math.cos(54 * Math.PI / 180);
            const p4y = 50 + 32 * valueRank * Math.sin(54 * Math.PI / 180);

            const p5x = 50 - 32 * volatilityRank * Math.cos(18 * Math.PI / 180);
            const p5y = 50 - 32 * volatilityRank * Math.sin(18 * Math.PI / 180);

            const pointsStr = `${p1x},${p1y} ${p2x},${p2y} ${p3x},${p3y} ${p4x},${p4y} ${p5x},${p5y}`;

            // Create sparkline path
            const sparkPoints = stock.sparkline;
            const pathSegments = sparkPoints.map((val, idx) => {
              const xPos = idx * 16;
              const yPos = val;
              return `${idx === 0 ? 'M' : 'L'}${xPos},${yPos}`;
            }).join(' ');

            const isPricePositive = stock.changePercent >= 0;

            return (
              <article 
                key={stock.id}
                id={`market-card-${stock.id}`}
                onClick={() => onSelectStock(stock)}
                className="bg-surface border border-border p-4 rounded-sm hover:border-primary-container/80 hover:bg-surface-container-high/40 transition-all duration-250 group cursor-pointer flex flex-col justify-between"
              >
                {/* Header */}
                <header className="flex justify-between items-start mb-2">
                  <div>
                    <h4 className="text-sm font-sans font-extrabold text-white group-hover:text-primary-container transition-colors tracking-wide flex items-center gap-1.5">
                      {stock.id}
                      <span className="text-[10px] text-text-tertiary p-0 font-normal">{stock.sector}</span>
                    </h4>
                    <p className="text-xs font-mono text-text-secondary mt-0.5">{stock.nameZh}</p>
                  </div>
                  <div className="bg-primary-container/10 px-2 py-1 rounded-xs border border-primary-container/15 group-hover:border-primary-container/40 transition-colors">
                    <span className="text-sm font-mono font-bold text-primary-container">{stock.aiScore}</span>
                  </div>
                </header>

                {/* Tag Badges */}
                <div className="flex gap-1.5 mb-4 flex-wrap">
                  <span className="text-[9px] uppercase font-mono bg-surface-container-high border border-border text-text-secondary px-1.5 py-0.5 rounded-xs">
                    成长 {stock.factors['成长']}
                  </span>
                  <span className="text-[9px] uppercase font-mono bg-surface-container-high border border-border text-text-secondary px-1.5 py-0.5 rounded-xs">
                    动量 {stock.factors['动量']}
                  </span>
                  {stock.aiScore >= 85 && (
                    <span className="text-[9px] uppercase font-mono bg-[#00c087]/12 text-secondary-fixed border border-[#00c087]/20 px-1.5 py-0.5 rounded-xs">
                      AI首选
                    </span>
                  )}
                </div>

                {/* Price indicators */}
                <div className="mb-4 flex justify-between items-center bg-surface-container-low/40 py-1.5 px-2.5 rounded-sm">
                  <span className="text-xs font-mono text-white font-semibold">${stock.price.toFixed(2)}</span>
                  <span className={`text-[11px] font-mono font-semibold ${isPricePositive ? 'text-secondary-fixed' : 'text-error'}`}>
                    {isPricePositive ? '+' : ''}{stock.changePercent}%
                  </span>
                </div>

                {/* SVG Visualizations Row: Micro Radar & Sparkline */}
                <div className="flex justify-between items-center h-16 pt-1 border-t border-border/40">
                  {/* Small Radar Outline */}
                  <div className="w-14 h-14 relative" title="五维因子图">
                    <svg className="w-full h-full" viewBox="0 0 100 100">
                      {/* outer shell */}
                      <polygon points="50,15 82,38 70,75 30,75 18,38" className="stroke-[#242B3A] fill-none" strokeWidth="1" />
                      <line x1="50" y1="50" x2="50" y2="15" className="stroke-[#242B3A]" strokeWidth="0.5" />
                      <line x1="50" y1="50" x2="82" y2="38" className="stroke-[#242B3A]" strokeWidth="0.5" />
                      <line x1="50" y1="50" x2="70" y2="75" className="stroke-[#242B3A]" strokeWidth="0.5" />
                      <line x1="50" y1="50" x2="30" y2="75" className="stroke-[#242B3A]" strokeWidth="0.5" />
                      <line x1="50" y1="50" x2="18" y2="38" className="stroke-[#242B3A]" strokeWidth="0.5" />
                      {/* live points polygon */}
                      <polygon 
                        points={pointsStr} 
                        className="stroke-primary-container fill-primary-container/20" 
                        strokeWidth="1.5" 
                      />
                    </svg>
                  </div>

                  {/* Sparkline trend representation */}
                  <div className="w-20 h-10" title="价格趋势(小时线)">
                    <svg className="w-full h-full overflow-visible" viewBox="0 0 80 40">
                      <path 
                        d={pathSegments} 
                        className={`fill-none stroke-2 ${isPricePositive ? 'stroke-secondary' : 'stroke-error'}`}
                        strokeLinecap="round" 
                        strokeLinejoin="round" 
                      />
                    </svg>
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}
