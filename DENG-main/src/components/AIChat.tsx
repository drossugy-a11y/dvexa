/**
 * AI 聊天页面 - 基于 CopilotKit
 * 流式输出 + Agent 步骤展示 + 股票问答 + 系统操作
 */

import { useState, useEffect } from 'react';
import { CopilotKit } from '@copilotkit/react-core';
import { CopilotChat } from '@copilotkit/react-ui';
import { useCopilotReadable } from '@copilotkit/react-core';
import { useCopilotAction } from '@copilotkit/react-core';
import { Stock } from '../types';
import { Brain, TrendingUp, Search, Activity } from 'lucide-react';

// CopilotKit runtime URL
const COPILOTKIT_URL = 'http://localhost:3001/api/copilotkit';

interface AIChatPageProps {
  stocks: Stock[];
  onSelectStock?: (stock: Stock) => void;
}

export default function AIChatPage({ stocks, onSelectStock }: AIChatPageProps) {
  const [runtimeStatus, setRuntimeStatus] = useState<'checking' | 'ok' | 'error'>('checking');

  // 检查 CopilotKit runtime 状态
  useEffect(() => {
    fetch(`${COPILOTKIT_URL}/health`)
      .then(res => res.json())
      .then(() => setRuntimeStatus('ok'))
      .catch(() => setRuntimeStatus('error'));
  }, []);

  return (
    <div className="h-[calc(100vh-3rem)] flex flex-col bg-background">
      {/* 状态栏 */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border bg-surface">
        <div className="flex items-center gap-3">
          <Brain className="w-5 h-5 text-primary" />
          <h1 className="text-lg font-semibold text-text-primary">AI 助手</h1>
          <span className="text-xs font-mono text-text-tertiary">MiMo-V2.5-Pro</span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            runtimeStatus === 'ok' ? 'bg-green-500' :
            runtimeStatus === 'error' ? 'bg-red-500' : 'bg-yellow-500 animate-pulse'
          }`} />
          <span className="text-xs text-text-tertiary">
            {runtimeStatus === 'ok' ? '已连接' :
             runtimeStatus === 'error' ? '未连接' : '检查中...'}
          </span>
        </div>
      </div>

      {/* 聊天区域 */}
      {runtimeStatus === 'error' ? (
        <DisconnectedView />
      ) : (
        <CopilotKit runtimeUrl={COPILOTKIT_URL}>
          <CopilotKitActions stocks={stocks} onSelectStock={onSelectStock} />
          <div className="flex-1 overflow-hidden">
            <CopilotChat
              labels={{
                title: 'DVexa AI 助手',
                initial: '你好！我是 DVexa AI 助手，可以帮你：\n\n📊 **分析股票** — 输入 "分析一下茅台"\n🔍 **市场扫描** — 输入 "帮我跑一次扫描"\n📈 **查看市场状态** — 输入 "现在是什么行情"\n💬 **自由对话** — 任何股票相关问题',
                placeholder: '输入你的问题...',
              }}
              className="h-full"
            />
          </div>
        </CopilotKit>
      )}
    </div>
  );
}

// ── CopilotKit Actions（注册 AI 可调用的工具）─────────────

function CopilotKitActions({ stocks, onSelectStock }: AIChatPageProps) {
  // 暴露当前股票列表给 AI
  useCopilotReadable({
    description: '当前系统中的股票列表，包含评分和基本信息',
    value: JSON.stringify(stocks.map(s => ({
      id: s.id,
      name: s.name,
      nameZh: s.nameZh,
      price: s.price,
      aiScore: s.aiScore,
      ratingType: s.ratingType,
      sector: s.sector,
    }))),
  });

  // Action: 分析单只股票
  useCopilotAction({
    name: 'analyzeStock',
    description: '分析某只股票的详细信息，包括五维评分、AI分析、风险提示。当用户提到具体股票代码或名称时使用。',
    parameters: [
      {
        name: 'ticker',
        type: 'string',
        description: '股票代码，如 NVDA、TSLA、600519',
        required: true,
      },
    ],
    handler: async ({ ticker }) => {
      // 从本地数据查找
      const stock = stocks.find(s =>
        s.id.toUpperCase() === ticker.toUpperCase() ||
        s.nameZh.includes(ticker) ||
        s.name.toLowerCase().includes(ticker.toLowerCase())
      );

      if (stock) {
        return JSON.stringify({
          found: true,
          stock: {
            code: stock.id,
            name: `${stock.nameZh} (${stock.name})`,
            price: stock.price,
            aiScore: stock.aiScore,
            rating: stock.ratingType,
            factors: stock.factors,
            analysis: stock.aiAnalysis,
            financials: stock.financials,
          }
        });
      }

      // 尝试从后端获取
      try {
        const res = await fetch(`http://localhost:8000/api/stocks/${ticker}`);
        if (res.ok) {
          const data = await res.json();
          return JSON.stringify({ found: true, stock: data });
        }
      } catch {}

      return JSON.stringify({ found: false, message: `未找到股票 ${ticker}，请检查代码是否正确。` });
    },
    render: ({ status, result }) => (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 my-2">
        <div className="flex items-center gap-2 text-blue-700 font-medium text-sm mb-1">
          <Search className="w-4 h-4" />
          {status === 'inProgress' ? '正在分析...' : '分析完成'}
        </div>
        {status === 'complete' && result && (
          <pre className="text-xs text-gray-600 whitespace-pre-wrap">{result}</pre>
        )}
      </div>
    ),
  });

  // Action: 触发市场扫描
  useCopilotAction({
    name: 'runMarketScan',
    description: '触发全市场股票扫描，筛选出优质候选股票。当用户说"扫描"、"选股"、"跑一次"时使用。',
    parameters: [],
    handler: async () => {
      try {
        const res = await fetch('http://localhost:8000/api/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ depth: 3 }),
        });
        const data = await res.json();
        return JSON.stringify({
          status: 'started',
          scanId: data.scan_id,
          message: '扫描已启动，正在分析全市场股票...',
        });
      } catch {
        return JSON.stringify({
          status: 'error',
          message: '扫描启动失败，请确认后端服务已启动 (port 8000)。',
        });
      }
    },
    render: ({ status }) => (
      <div className="bg-green-50 border border-green-200 rounded-lg p-3 my-2">
        <div className="flex items-center gap-2 text-green-700 font-medium text-sm">
          <Activity className="w-4 h-4" />
          {status === 'inProgress' ? '正在启动扫描...' : '扫描已启动'}
        </div>
      </div>
    ),
  });

  // Action: 获取市场状态
  useCopilotAction({
    name: 'getMarketRegime',
    description: '获取当前市场状态（牛市/熊市/震荡市）。当用户问"行情"、"市场状态"、"现在是什么市"时使用。',
    parameters: [],
    handler: async () => {
      try {
        const res = await fetch('http://localhost:8000/api/regime');
        const data = await res.json();
        return JSON.stringify(data);
      } catch {
        return JSON.stringify({
          regime: 'unknown',
          message: '无法获取市场状态，请确认后端服务已启动。',
        });
      }
    },
    render: ({ status, result }) => (
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 my-2">
        <div className="flex items-center gap-2 text-purple-700 font-medium text-sm">
          <TrendingUp className="w-4 h-4" />
          {status === 'inProgress' ? '正在获取市场状态...' : '市场状态'}
        </div>
        {status === 'complete' && result && (
          <pre className="text-xs text-gray-600 whitespace-pre-wrap mt-1">{result}</pre>
        )}
      </div>
    ),
  });

  return null;
}

// ── 未连接视图 ─────────────────────────────────────────

function DisconnectedView() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center max-w-md">
        <Brain className="w-16 h-16 text-text-tertiary mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-text-primary mb-2">AI 助手未连接</h2>
        <p className="text-text-secondary mb-4">
          请先启动 CopilotKit 后端服务：
        </p>
        <div className="bg-surface-container-low border border-border rounded-lg p-4 text-left">
          <code className="text-sm font-mono text-primary">
            cd DENG-main<br />
            node server/copilotkit.js
          </code>
        </div>
        <p className="text-xs text-text-tertiary mt-3">
          确保 MiMo API Key 已配置在 .env 文件中
        </p>
      </div>
    </div>
  );
}
