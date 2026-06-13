/**
 * Stock Radar API Client
 *
 * 连接 stock_radar Python 后端，获取真实 A 股数据。
 * API 不可用时自动降级到本地硬编码数据。
 */

import { Stock } from './types';
import { ALL_STOCKS } from './data/stocks';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

// ── 健康检查 ─────────────────────────────────────────

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

// ── 获取股票列表 ─────────────────────────────────────

export async function fetchStocks(params?: {
  top_n?: number;
  pe_min?: number;
  pe_max?: number;
  industry?: string;
}): Promise<{ stocks: Stock[]; fromApi: boolean }> {
  try {
    const qs = new URLSearchParams();
    if (params?.top_n) qs.set('top_n', String(params.top_n));
    if (params?.pe_min) qs.set('pe_min', String(params.pe_min));
    if (params?.pe_max) qs.set('pe_max', String(params.pe_max));
    if (params?.industry) qs.set('industry', params.industry);

    const res = await fetch(`${API_BASE}/api/stocks?${qs}`, {
      signal: AbortSignal.timeout(30000),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);

    const data = await res.json();
    return { stocks: data.stocks || [], fromApi: true };
  } catch (err) {
    console.warn('[API] 获取股票列表失败，使用本地数据:', err);
    return { stocks: ALL_STOCKS, fromApi: false };
  }
}

// ── 获取单只股票详情 ─────────────────────────────────

export async function fetchStockDetail(code: string): Promise<Stock | null> {
  try {
    const res = await fetch(`${API_BASE}/api/stocks/${code}`, {
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`[API] 获取 ${code} 详情失败:`, err);
    // 降级到本地数据
    return ALL_STOCKS.find((s) => s.id === code) || null;
  }
}

// ── 运行新分析 ───────────────────────────────────────

export async function runAnalysis(params?: {
  industry?: string;
  pe_min?: number;
  pe_max?: number;
  top_n?: number;
}): Promise<{ stocks: Stock[]; fromApi: boolean }> {
  try {
    const res = await fetch(`${API_BASE}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        industry: params?.industry || null,
        pe_min: params?.pe_min || 0,
        pe_max: params?.pe_max || 200,
        top_n: params?.top_n || 10,
      }),
      signal: AbortSignal.timeout(120000), // 分析可能较慢
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);

    const data = await res.json();
    return { stocks: data.stocks || [], fromApi: true };
  } catch (err) {
    console.warn('[API] 分析失败:', err);
    return { stocks: ALL_STOCKS, fromApi: false };
  }
}
