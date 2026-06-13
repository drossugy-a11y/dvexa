/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState } from 'react';
import { Stock, PortfolioPosition } from '../types';
import { 
  Briefcase, 
  Wallet, 
  ArrowUpRight, 
  ArrowDownRight, 
  Activity, 
  Plus, 
  Trash2,
  TrendingUp,
  Brain
} from 'lucide-react';

interface PortfolioProps {
  stocks: Stock[];
  positions: PortfolioPosition[];
  cash: number;
  onBuy: (ticker: string, shares: number, price: number) => void;
  onSell: (ticker: string, shares: number) => void;
}

export default function Portfolio({
  stocks,
  positions,
  cash,
  onBuy,
  onSell
}: PortfolioProps) {
  const [buyTicker, setBuyTicker] = useState(stocks[0]?.id || 'NVDA');
  const [buyShares, setBuyShares] = useState(10);

  const getStockById = (ticker: string) => stocks.find(s => s.id === ticker);

  // Math variables
  const positionsValue = positions.reduce((acc, pos) => {
    const stock = getStockById(pos.ticker);
    return acc + (stock ? stock.price * pos.shares : 0);
  }, 0);

  const totalAssetValue = cash + positionsValue;
  const initialAssetValue = cash + positions.reduce((acc, pos) => acc + pos.totalInvestment, 0);
  const totalReturnPercent = initialAssetValue > 0 ? ((totalAssetValue - initialAssetValue) / initialAssetValue) * 100 : 0;
  const isGainPositive = totalAssetValue >= initialAssetValue;

  // Weighted Portfolio AI Score
  const weightedAIScore = positions.length > 0 
    ? positions.reduce((acc, pos) => {
        const stock = getStockById(pos.ticker);
        const weight = (stock ? stock.price * pos.shares : 0) / positionsValue;
        return acc + (stock ? stock.aiScore * weight : 0);
      }, 0)
    : 0;

  const currentSelectedStock = getStockById(buyTicker);

  return (
    <div className="space-y-6">
      {/* Introduction */}
      <section className="bg-surface p-4.5 rounded-sm border border-border shadow-md">
        <h2 className="text-display-lg font-bold text-white tracking-tight flex items-center gap-2">
          我的 AI 机构投资组合 / Institutional Portfolio
          <span className="text-xs bg-secondary/15 text-secondary-fixed border border-secondary/20 px-2 py-0.5 rounded-sm font-mono tracking-normal capitalize">
            Active Simulator
          </span>
        </h2>
        <p className="text-xs font-mono text-text-secondary mt-1">
          基于终端 AI 因子排名分配权重，仿真交易及收益实时计算。
        </p>
      </section>

      {/* Stats Counters Grid */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Net Asset Value */}
        <div className="bg-surface border border-border p-4.5 rounded-sm flex flex-col justify-between h-24">
          <div className="flex justify-between items-start">
            <span className="text-[10px] font-mono text-text-secondary uppercase">净资产总值 Net Worth</span>
            <Briefcase className="text-primary w-4 h-4" />
          </div>
          <div>
            <div className="text-2xl font-bold font-mono text-white">${totalAssetValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
          </div>
        </div>

        {/* Free Cash */}
        <div className="bg-surface border border-border p-4.5 rounded-sm flex flex-col justify-between h-24">
          <div className="flex justify-between items-start">
            <span className="text-[10px] font-mono text-text-secondary uppercase">可用购买资金 Cash Balance</span>
            <Wallet className="text-secondary-fixed w-4 h-4" />
          </div>
          <div>
            <div className="text-2xl font-bold font-mono text-secondary-fixed">${cash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
          </div>
        </div>

        {/* Total Returns */}
        <div className="bg-surface border border-border p-4.5 rounded-sm flex flex-col justify-between h-24">
          <div className="flex justify-between items-start">
            <span className="text-[10px] font-mono text-text-secondary uppercase">持仓累计收益 Returns</span>
            {isGainPositive ? <ArrowUpRight className="text-secondary w-4 h-4" /> : <ArrowDownRight className="text-error w-4 h-4" />}
          </div>
          <div className="flex items-end gap-1.5">
            <div className={`text-2xl font-bold font-mono ${isGainPositive ? 'text-secondary' : 'text-error'}`}>
              {isGainPositive ? '+' : ''}{totalReturnPercent.toFixed(2)}%
            </div>
            <span className="text-[10px] font-mono text-text-tertiary mb-1">
              {isGainPositive ? 'Profit' : 'Loss'}
            </span>
          </div>
        </div>

        {/* Combined Portfolio AI Score */}
        <div className="bg-surface border border-border p-4.5 rounded-sm flex flex-col justify-between h-24">
          <div className="flex justify-between items-start">
            <span className="text-[10px] font-mono text-text-secondary uppercase">持仓加权AI质检评分 Risk Rating</span>
            <Brain className="text-primary w-4 h-4" />
          </div>
          <div className="flex items-end gap-2">
            <div className="text-2xl font-bold font-mono text-primary leading-none">
              {weightedAIScore > 0 ? weightedAIScore.toFixed(0) : '0'}
            </div>
            <span className="text-[10px] font-mono text-text-tertiary uppercase mb-0.5">
              {weightedAIScore >= 85 ? 'AAA Class' : weightedAIScore >= 70 ? 'BBB Class' : weightedAIScore > 0 ? 'CCC Speculative' : 'No Assets'}
            </span>
          </div>
        </div>
      </section>

      {/* Lower Bento sections */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Table representation (8/12 width) */}
        <div className="lg:col-span-8 bg-surface border border-border rounded-sm flex flex-col overflow-hidden min-h-[300px]">
          <div className="p-4 border-b border-border bg-surface-container-low/20">
            <h3 className="text-xs font-sans font-bold text-white uppercase tracking-wider">我的投资持仓细分 / Active Positions</h3>
          </div>

          <div className="overflow-x-auto flex-1">
            {positions.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center p-12 text-center">
                <Briefcase className="w-8 h-8 text-text-tertiary mb-2 text-center" />
                <p className="text-xs text-text-secondary">目前暂无持股。请在右侧选择标的并买入以构建您的投资组合！</p>
              </div>
            ) : (
              <table className="w-full text-left border-collapse text-xs font-mono">
                <thead>
                  <tr className="border-b border-border text-[10px] text-text-tertiary uppercase tracking-wider bg-surface-container-lowest/15">
                    <th className="py-2.5 px-4 font-normal">标的代码</th>
                    <th className="py-2.5 px-3 font-normal">持股数量</th>
                    <th className="py-2.5 px-3 font-normal">持仓成本</th>
                    <th className="py-3 px-3 font-normal">当前市价</th>
                    <th className="py-3 px-3 font-normal text-right">持仓总价值</th>
                    <th className="py-3 px-4 font-normal text-right">即时盈余</th>
                  </tr>
                </thead>
                <tbody className="text-white">
                  {positions.map((pos) => {
                    const stock = getStockById(pos.ticker);
                    if (!stock) return null;

                    const currentValue = stock.price * pos.shares;
                    const posReturnAmount = currentValue - pos.totalInvestment;
                    const posReturnPct = pos.totalInvestment > 0 ? (posReturnAmount / pos.totalInvestment) * 100 : 0;
                    const isPosGain = posReturnAmount >= 0;

                    return (
                      <tr key={pos.ticker} className="border-b border-border/50 hover:bg-surface-container-low/20 transition-colors last:border-none">
                        <td className="py-3.5 px-4">
                          <div className="flex flex-col">
                            <span className="font-bold text-white text-xs">{pos.ticker}</span>
                            <span className="text-[10px] text-text-tertiary">{stock.nameZh}</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-3 text-white font-medium">{pos.shares}</td>
                        <td className="py-3.5 px-3 text-text-secondary">${pos.avgCost.toFixed(2)}</td>
                        <td className="py-3.5 px-3 text-text-secondary">${stock.price.toFixed(2)}</td>
                        <td className="py-3.5 px-3 text-right text-white font-semibold">${currentValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-3">
                            <div className="flex flex-col">
                              <span className={`font-semibold ${isPosGain ? 'text-secondary-fixed' : 'text-error'}`}>
                                {isPosGain ? '+' : ''}${posReturnAmount.toFixed(2)}
                              </span>
                              <span className={`text-[9px] ${isPosGain ? 'text-secondary' : 'text-error'}`}>
                                {isPosGain ? '+' : ''}{posReturnPct.toFixed(2)}%
                              </span>
                            </div>
                            <button 
                              onClick={() => {
                                if (confirm(`确认卖出所有 ${pos.ticker} 的持仓吗?`)) {
                                  onSell(pos.ticker, pos.shares);
                                }
                              }}
                              className="text-text-tertiary hover:text-error transition-colors p-1 bg-surface-container-high hover:bg-error/15 rounded-xs"
                              title="全部结清"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Quick Simulator trade action panel (4/12 width) */}
        <div className="lg:col-span-4 bg-surface border border-border rounded-sm p-4.5 flex flex-col justify-between min-h-[300px]">
          <div>
            <h3 className="text-xs font-sans font-bold text-white uppercase tracking-wider mb-2.5 pb-2 border-b border-border/80 flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-primary-container" />
              仿真快速交易面板 / Buy Order
            </h3>

            {/* Selector Stock */}
            <div className="space-y-4 pt-1 font-mono text-xs">
              <div>
                <label className="block text-[10px] text-text-secondary uppercase mb-1.5 font-bold">选择购买股票 Ticker</label>
                <select 
                  value={buyTicker}
                  onChange={(e) => setBuyTicker(e.target.value)}
                  className="w-full bg-surface-container-high border-border text-white text-xs px-3 py-2 rounded-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none"
                >
                  {stocks.map(s => (
                    <option key={s.id} value={s.id}>{s.id} - {s.nameZh} (${s.price.toFixed(2)})</option>
                  ))}
                </select>
              </div>

              {/* Shares input */}
              <div>
                <label className="block text-[10px] text-text-secondary uppercase mb-1.5 font-bold">加码持股股数 Shares</label>
                <div className="flex items-center bg-surface-container-high border border-border rounded-sm overflow-hidden px-2 py-1.5">
                  <input 
                    type="number"
                    min="1"
                    max="10000"
                    value={buyShares}
                    onChange={(e) => setBuyShares(Math.max(1, parseInt(e.target.value) || 0))}
                    className="bg-transparent border-none outline-none text-xs text-white p-0 w-full focus:ring-0"
                  />
                  <span className="text-[10px] text-text-tertiary">Shares</span>
                </div>
              </div>

              {/* Cost Estimator */}
              {currentSelectedStock && (
                <div className="bg-surface-container-low/40 p-3 rounded-sm border border-border/60 text-xs">
                  <div className="flex justify-between py-1 text-text-secondary">
                    <span>当前市场单价:</span>
                    <span className="text-white">${currentSelectedStock.price.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between py-1 text-text-secondary">
                    <span>预估总支出 Cost:</span>
                    <span className="text-white font-bold">${(currentSelectedStock.price * buyShares).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between py-1 border-t border-border/40 mt-1.5 pt-1.5 font-bold">
                    <span>购买后可用现金:</span>
                    <span className={cash >= currentSelectedStock.price * buyShares ? 'text-secondary-fixed' : 'text-error'}>
                      ${(cash - currentSelectedStock.price * buyShares).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>

          <button 
            id="buy-execute-btn"
            disabled={!currentSelectedStock || cash < currentSelectedStock.price * buyShares}
            onClick={() => {
              if (currentSelectedStock) {
                onBuy(buyTicker, buyShares, currentSelectedStock.price);
                alert(`交易成功！买入 ${buyShares} 股 ${buyTicker}。`);
              }
            }}
            className="w-full bg-primary hover:bg-[#ebd594] disabled:bg-surface-container-high disabled:text-text-tertiary text-black mt-5 py-2.5 px-4 font-sans font-bold rounded-sm text-xs transition-colors flex items-center justify-center gap-2 shadow-md uppercase tracking-wider"
          >
            <Plus className="w-4 h-4" />
            <span>执行购买下单 Submit Buy Order</span>
          </button>
        </div>
      </div>
    </div>
  );
}
