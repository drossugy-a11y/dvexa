/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState } from 'react';
import { ResearchLog } from '../types';
import { 
  Calendar, 
  CheckCircle, 
  Filter, 
  Terminal, 
  TrendingUp, 
  Sparkles,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';

interface ResearchLogsProps {
  logs: ResearchLog[];
  onSelectStockById: (ticker: string) => void;
}

export default function ResearchLogs({
  logs,
  onSelectStockById
}: ResearchLogsProps) {
  const [selectedLogId, setSelectedLogId] = useState(logs[0]?.id || '');
  const [filterActive, setFilterActive] = useState(false);

  const activeLog = logs.find(l => l.id === selectedLogId) || logs[0];

  // Handle active radar SVG vertices for factors: [动量, 情绪, 成长, 质量, 估值]
  // Center: (50, 50)
  const drawLogRadar = (factors: Record<string, number>) => {
    const fMom = (factors['动量'] || 50) / 100;
    const fEmo = (factors['情绪'] || 50) / 100;
    const fGro = (factors['成长'] || 50) / 100;
    const fQlt = (factors['质量'] || 50) / 100;
    const fVal = (factors['估值'] || 50) / 100;

    const y1 = 50 - 38 * fMom;

    const x2 = 50 + 38 * fEmo * Math.cos(18 * Math.PI / 180);
    const y2 = 50 - 38 * fEmo * Math.sin(18 * Math.PI / 180);

    const x3 = 50 + 38 * fGro * Math.cos(54 * Math.PI / 180);
    const y3 = 50 + 38 * fGro * Math.sin(54 * Math.PI / 180);

    const x4 = 50 - 38 * fQlt * Math.cos(54 * Math.PI / 180);
    const y4 = 50 + 38 * fQlt * Math.sin(54 * Math.PI / 180);

    const x5 = 50 - 38 * fVal * Math.cos(18 * Math.PI / 180);
    const y5 = 50 - 38 * fVal * Math.sin(18 * Math.PI / 180);

    return `${50},${y1} ${x2},${y2} ${x3},${y3} ${x4},${y4} ${x5},${y5}`;
  };

  const calculatedReturnSum = activeLog?.corePool.reduce((acc, current) => acc + current.returnT5, 0) || 0;
  const isReturnPositive = calculatedReturnSum >= 0;

  return (
    <div className="space-y-4 h-full flex flex-col">
      {/* Sub-header context widgets */}
      <section className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-3 shrink-0">
        <div>
          <h2 className="text-display-lg font-bold font-sans text-white tracking-tight flex items-center gap-2">
            选股复盘日志
            <span className="text-[10px] bg-surface-container-high border border-border px-2 py-0.5 rounded-sm text-text-secondary font-mono tracking-normal">
              Research / Timeline Logs
            </span>
          </h2>
          <p className="text-xs text-text-secondary font-mono">
            复盘本终端 AI 前期发布的组合模型胜率，评估多维核心因子在后市的表现状态。
          </p>
        </div>

        {/* Date capsule or widgets */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Calendar Picker Chip mock */}
          <div className="flex items-center bg-surface border border-border rounded-sm px-3 py-1.5 cursor-pointer hover:border-text-tertiary transition-colors text-xs font-mono">
            <Calendar className="w-3.5 h-3.5 text-text-tertiary mr-2 shrink-0" />
            <span className="text-white">2023.10.01 - 2023.10.31</span>
          </div>

          {/* Sentiment capsule */}
          <div className="flex bg-surface rounded-sm border border-border overflow-hidden text-xs font-mono">
            <div className="px-3 py-1.5 border-r border-border flex items-center gap-1.5 bg-surface-container-low/20">
              <span className="w-2 h-2 rounded-full bg-secondary" />
              <span className="text-text-secondary">多头氛围</span>
              <span className="text-white font-bold">68%</span>
            </div>
            <div className="px-3 py-1.5 flex items-center gap-1.5 bg-primary/10">
              <TrendingUp className="text-secondary w-3.5 h-3.5" />
              <span className="text-secondary font-semibold">VIX 14.2</span>
            </div>
          </div>
        </div>
      </section>

      {/* Main split viewport (List Left, Console Right) */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch min-h-0">
        {/* LEFT COMPONENT: Timeline list (4/12 width) */}
        <div className="lg:col-span-4 flex flex-col bg-surface border border-border rounded-sm overflow-hidden min-h-[350px]">
          <div className="p-3 border-b border-border bg-surface-container-low/30 flex justify-between items-center shrink-0">
            <span className="text-[11px] font-mono text-text-secondary uppercase tracking-wider font-semibold">历史日志归档 ARCHIVES</span>
            <button 
              onClick={() => setFilterActive(!filterActive)} 
              className={`p-1 rounded-xs hover:bg-surface-container-high transition-colors ${filterActive ? 'text-primary' : 'text-text-tertiary'}`}
              title="过滤"
            >
              <Filter className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2.5 space-y-2.5">
            {logs.map((log) => {
              const isActive = selectedLogId === log.id;
              return (
                <div 
                  key={log.id}
                  id={`log-item-${log.id}`}
                  onClick={() => setSelectedLogId(log.id)}
                  className={`p-3.5 rounded-xs transition-all duration-200 cursor-pointer border ${
                    isActive 
                      ? 'bg-surface-container-high border-primary-container/40 shadow-[0_0_15px_rgba(212,175,55,0.06)]' 
                      : 'bg-surface border-transparent hover:border-border hover:bg-surface-container-high/30'
                  }`}
                >
                  <div className="flex justify-between items-center mb-2">
                    <span className={`text-[11px] font-mono font-bold ${isActive ? 'text-white' : 'text-text-secondary'}`}>
                      {log.date}
                    </span>
                    <span className="text-[10px] font-mono text-secondary bg-primary/10 px-1.5 py-0.5 rounded-xs border border-primary/20">
                      平均评分: {log.avgScore}
                    </span>
                  </div>

                  {/* Stock tag list */}
                  <div className="flex gap-1.5 mb-2.5 flex-wrap">
                    {log.tickers.map((t) => (
                      <span 
                        key={t} 
                        className="bg-surface-container-lowest border border-border text-text-primary px-2 py-0.5 rounded-xs text-[10px] font-mono font-bold"
                      >
                        {t}
                      </span>
                    ))}
                  </div>

                  {/* short log summary paragraph */}
                  <p className="text-xs text-text-secondary leading-relaxed line-clamp-2">
                    {log.summary}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT COMPONENT: Detail Terminal inspector console (8/12 width) */}
        {activeLog ? (
          <div className="lg:col-span-8 flex flex-col bg-surface border border-border rounded-sm relative overflow-hidden">
            {/* Background cyber blur effect */}
            <div className="absolute top-[-25%] right-[-15%] w-[450px] h-[450px] bg-primary-container/4 rounded-full blur-3xl pointer-events-none" />

            {/* Header top panel */}
            <div className="p-4 border-b border-border flex flex-col sm:flex-row justify-between items-start sm:items-end gap-3 relative z-10 bg-surface-container-lowest/25 shrink-0">
              <div>
                <div className="flex flex-wrap items-center gap-2.5 mb-1">
                  <h2 className="text-base font-semibold text-white font-sans tracking-wide">
                    {activeLog.date} 选股逻辑透视
                  </h2>
                  <span className="bg-primary/10 border border-primary/20 text-secondary px-2 py-0.5 rounded-xs text-[10px] font-mono flex items-center gap-1.5">
                    <CheckCircle className="w-3 h-3 text-secondary" />
                    验证成功 / VALIDATED
                  </span>
                </div>
                <p className="text-xs text-text-secondary font-mono">
                  T+5日追踪表现归因分析与预测因子雷达
                </p>
              </div>

              {/* performance returns absolute summary */}
              <div className="text-left sm:text-right">
                <div className="text-[10px] font-mono text-text-tertiary mb-0.5">T+5 组合绝对收益率 / Total Return</div>
                <div className={`text-xl font-mono font-extrabold flex items-center gap-1 leading-none ${isReturnPositive ? 'text-secondary-fixed' : 'text-error'}`}>
                  {isReturnPositive ? <ArrowUpRight className="w-5 h-5 text-secondary-fixed" /> : <ArrowDownRight className="w-5 h-5 text-error" />}
                  {isReturnPositive ? '+' : ''}{calculatedReturnSum.toFixed(2)}%
                </div>
              </div>
            </div>

            {/* Scrollable details body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4.5 relative z-10">
              {/* Terminal code styled logic summary card */}
              <div className="bg-surface-container-lowest border border-border rounded-sm p-4 font-mono text-text-secondary leading-relaxed text-xs">
                <div className="flex items-center gap-2 mb-2 border-b border-border/80 pb-2 text-primary">
                  <Terminal className="w-4 h-4 text-primary" />
                  <span className="font-bold">AI_Engine_Output // Summary</span>
                </div>
                <div className="space-y-2">
                  <p>
                    <span className="text-text-tertiary mr-1 font-bold">&gt; [ANALYSIS]</span> 
                    {activeLog.outputText.analysis}
                  </p>
                  <p>
                    <span className="text-text-tertiary mr-1 font-bold">&gt; [CATALYST]</span> 
                    {activeLog.outputText.catalyst}
                  </p>
                  <p>
                    <span className="text-text-tertiary mr-1 font-bold">&gt; [DECISION]</span> 
                    <span className="text-white">{activeLog.outputText.decision}</span>
                  </p>
                </div>
              </div>

              {/* Bento Grid: Model radar & Top Stocks pool table */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Visualizer Radar Chart (Box 1) */}
                <div className="bg-surface-container-lowest/50 border border-border p-4.5 rounded-sm flex flex-col justify-between">
                  <span className="text-xs font-semibold text-white font-sans flex items-center gap-1.5 mb-4">
                    <Sparkles className="w-3.5 h-3.5 text-primary-container" />
                    模型平均因子雷达 / Factor Radar
                  </span>

                  <div className="flex-1 flex items-center justify-center relative min-h-[160px] max-h-[180px] my-1">
                    {/* SVG Radar */}
                    <svg className="w-full h-full overflow-visible" viewBox="0 0 100 100">
                      {/* background axes circles */}
                      {[20, 35].map(radius => (
                        <circle key={radius} cx="50" cy="50" r={radius} className="stroke-border fill-none" strokeWidth="0.5" />
                      ))}
                      {/* spoke axes lines */}
                      <line x1="50" y1="50" x2="50" y2="10" className="stroke-border" strokeWidth="0.5" />
                      <line x1="50" y1="50" x2="88" y2="38" className="stroke-border" strokeWidth="0.5" />
                      <line x1="50" y1="50" x2="73" y2="84" className="stroke-border" strokeWidth="0.5" />
                      <line x1="50" y1="50" x2="27" y2="84" className="stroke-border" strokeWidth="0.5" />
                      <line x1="50" y1="50" x2="12" y2="38" className="stroke-border" strokeWidth="0.5" />

                      {/* Vertices Polygon mapping log.factors */}
                      <polygon 
                        points={drawLogRadar(activeLog.factors)} 
                        className="stroke-primary fill-primary/15" 
                        strokeWidth="1.2" 
                      />
                    </svg>

                    {/* Outer corner label absolute text nodes */}
                    <span className="absolute top-[-2px] left-1/2 -translate-x-1/2 text-[9px] font-mono text-text-tertiary">动量</span>
                    <span className="absolute top-[32%] right-[2%] text-[9px] font-mono text-text-tertiary">情绪</span>
                    <span className="absolute bottom-[-2px] right-[20%] text-[9px] font-mono text-text-tertiary">成长</span>
                    <span className="absolute bottom-[-2px] left-[20%] text-[9px] font-mono text-text-tertiary">质量</span>
                    <span className="absolute top-[32%] left-[2%] text-[9px] font-mono text-text-tertiary">估值</span>
                  </div>
                </div>

                {/* Core stocks pool returns table (Box 2) */}
                <div className="bg-surface-container-lowest/50 border border-border rounded-sm flex flex-col justify-between overflow-hidden">
                  <div className="p-3 border-b border-border bg-surface-container-low/15 text-xs font-sans font-semibold text-white flex items-center justify-between">
                    <span>核心标的池 (Top Pools)</span>
                    <span className="text-[10px] text-text-tertiary font-mono">T+5 Days</span>
                  </div>

                  <div className="flex-1 overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="text-[10px] font-mono text-text-tertiary bg-surface-container-lowest border-b border-border/80">
                          <th className="py-2.5 px-3.5 font-normal">标的代码 / Code</th>
                          <th className="py-2.5 px-3 font-normal text-right">综合评分</th>
                          <th className="py-2.5 px-3.5 font-normal text-right">T+5 涨幅</th>
                        </tr>
                      </thead>
                      <tbody className="text-xs font-mono text-white">
                        {activeLog.corePool.map((item) => {
                          const isPos = item.returnT5 >= 0;
                          return (
                            <tr key={item.ticker} className="border-b border-border/40 hover:bg-surface-container-high/20 transition-colors">
                              <td className="py-2.5 px-3.5">
                                <div className="flex items-center gap-2">
                                  {/* green status pulse dot */}
                                  <span className="w-1.5 h-1.5 rounded-full bg-secondary-fixed animate-pulse" />
                                  <span 
                                    className="font-bold hover:underline cursor-pointer"
                                    onClick={() => onSelectStockById(item.ticker)}
                                  >
                                    {item.ticker}
                                  </span>
                                </div>
                              </td>
                              <td className="py-2.5 px-3 text-right text-text-secondary">{item.score}</td>
                              <td className={`py-2.5 px-3.5 text-right font-semibold ${isPos ? 'text-secondary-fixed' : 'text-error'}`}>
                                {isPos ? '+' : ''}{item.returnT5}%
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
          </div>
        ) : (
          <div className="lg:col-span-8 flex items-center justify-center bg-surface border border-border rounded-sm">
            <p className="text-text-secondary text-sm">选择日期以查看详细的选股透视。</p>
          </div>
        )}
      </div>
    </div>
  );
}
