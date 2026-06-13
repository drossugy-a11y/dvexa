/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export type Tab = 'market' | 'comparison' | 'logs' | 'analysis' | 'portfolio' | 'chat';

export interface FactorWeights {
  '动量': number;
  '成长': number;
  '质量': number;
  '估值': number;
  '波动': number;
}

export interface AIAnalysis {
  catalysts: string;
  trendLogic: string;
  riskAlerts: string;
  action: string;
}

export interface PeerMetric {
  ticker: string;
  name: string;
  score: number;
  pe: string;
  growth: string;
  trend: 'up' | 'down';
}

export interface FinancialMetrics {
  peForecast: string;
  growthYoY: string;
  margin: string;
  debtRatio: string;
  alpha1Y: string;
}

export interface Stock {
  id: string; // Ticker (e.g., NVDA)
  name: string;
  nameZh: string;
  sector: string;
  price: number;
  changePercent: number;
  changeAmount: number;
  volume: string;
  marketCap: string;
  peRatio: number | null;
  beta: number;
  aiScore: number;
  ratingType: 'Strong Buy' | 'Buy' | 'Hold' | 'Reduce';
  factors: FactorWeights;
  aiAnalysis: AIAnalysis;
  historyTrend: Array<{ label: string; score: number }>;
  peers: PeerMetric[];
  financials: FinancialMetrics;
  sparkline: number[];
}

export interface ResearchLogPoolItem {
  ticker: string;
  score: number;
  returnT5: number;
  isPositive: boolean;
}

export interface ResearchLog {
  id: string;
  date: string;
  avgScore: number;
  tickers: string[];
  summary: string;
  outputText: {
    analysis: string;
    catalyst: string;
    decision: string;
  };
  factors: {
    '动量': number;
    '情绪': number;
    '成长': number;
    '质量': number;
    '估值': number;
  };
  corePool: ResearchLogPoolItem[];
}

export interface PortfolioPosition {
  ticker: string;
  shares: number;
  avgCost: number;
  totalInvestment: number;
}
