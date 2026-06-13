/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect, useCallback } from 'react';
import { Tab, Stock, PortfolioPosition, ResearchLog } from './types';
import { ALL_STOCKS, RESEARCH_LOGS } from './data/stocks';
import { fetchStocks, fetchStockDetail, runAnalysis } from './api';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import MarketRanking from './components/MarketRanking';
import MultiAssetComparison from './components/MultiAssetComparison';
import ResearchLogs from './components/ResearchLogs';
import StockDetailAnalysis from './components/StockDetailAnalysis';
import Portfolio from './components/Portfolio';
import NewAnalysisModal from './components/NewAnalysisModal';
import AIChatPage from './components/AIChat';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    const saved = localStorage.getItem('dvexa_active_tab');
    return (saved as Tab) || 'market';
  });

  const [stocks, setStocks] = useState<Stock[]>(() => {
    const saved = localStorage.getItem('dvexa_stocks');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        return ALL_STOCKS;
      }
    }
    return ALL_STOCKS;
  });

  const [comparedIds, setComparedIds] = useState<string[]>(() => {
    const saved = localStorage.getItem('dvexa_compared');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        return ['NVDA', 'TSLA', 'AMD'];
      }
    }
    return ['NVDA', 'TSLA', 'AMD'];
  });

  const [selectedStockId, setSelectedStockId] = useState<string>(() => {
    return localStorage.getItem('dvexa_selected_stock') || 'NVDA';
  });

  const [watchlist, setWatchlist] = useState<string[]>(() => {
    const saved = localStorage.getItem('dvexa_watchlist');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        return ['NVDA', 'MSFT'];
      }
    }
    return ['NVDA', 'MSFT'];
  });

  // Simulated cash and positions state
  const [cash, setCash] = useState<number>(() => {
    const saved = localStorage.getItem('dvexa_cash');
    return saved ? parseFloat(saved) : 485000.00;
  });

  const [positions, setPositions] = useState<PortfolioPosition[]>(() => {
    const saved = localStorage.getItem('dvexa_positions');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        return [
          { ticker: 'NVDA', shares: 150, avgCost: 840.00, totalInvestment: 126000.00 },
          { ticker: 'TSM', shares: 100, avgCost: 130.00, totalInvestment: 13000.00 }
        ];
      }
    }
    return [
      { ticker: 'NVDA', shares: 150, avgCost: 840.00, totalInvestment: 126000.00 },
      { ticker: 'TSM', shares: 100, avgCost: 130.00, totalInvestment: 13000.00 }
    ];
  });

  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isNewAnalysisOpen, setIsNewAnalysisOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isFromApi, setIsFromApi] = useState(false);

  // On mount: try to fetch real data from Python backend
  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    fetchStocks().then(({ stocks: apiStocks, fromApi }) => {
      if (!cancelled && fromApi && apiStocks.length > 0) {
        setStocks(apiStocks);
        setIsFromApi(true);
        // Auto-select first stock
        if (apiStocks[0]) setSelectedStockId(apiStocks[0].id);
        // Set compared to first 3
        const first3 = apiStocks.slice(0, 3).map(s => s.id);
        setComparedIds(first3);
      }
    }).catch(() => { /* fallback already handled in api.ts */ }
    ).finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // Sync state to local storage
  useEffect(() => {
    localStorage.setItem('dvexa_active_tab', activeTab);
  }, [activeTab]);

  useEffect(() => {
    localStorage.setItem('dvexa_stocks', JSON.stringify(stocks));
  }, [stocks]);

  useEffect(() => {
    localStorage.setItem('dvexa_compared', JSON.stringify(comparedIds));
  }, [comparedIds]);

  useEffect(() => {
    localStorage.setItem('dvexa_selected_stock', selectedStockId);
  }, [selectedStockId]);

  useEffect(() => {
    localStorage.setItem('dvexa_watchlist', JSON.stringify(watchlist));
  }, [watchlist]);

  useEffect(() => {
    localStorage.setItem('dvexa_positions', JSON.stringify(positions));
  }, [positions]);

  useEffect(() => {
    localStorage.setItem('dvexa_cash', cash.toString());
  }, [cash]);

  // Find currently selected stock
  const selectedStock = stocks.find(s => s.id === selectedStockId) || stocks[0];

  const handleMobileToggle = () => setIsMobileOpen(!isMobileOpen);

  // Buy Simulator handler
  const handleBuyStock = (ticker: string, shares: number, price: number) => {
    const cost = shares * price;
    if (cash < cost) {
      alert("购买失败！现金剩余不足。");
      return;
    }

    setCash(prev => prev - cost);
    setPositions(prev => {
      const existing = prev.find(p => p.ticker === ticker);
      if (existing) {
        const totalCost = existing.totalInvestment + cost;
        const totalShares = existing.shares + shares;
        return prev.map(p => p.ticker === ticker ? { 
          ticker, 
          shares: totalShares, 
          avgCost: totalCost / totalShares,
          totalInvestment: totalCost
        } : p);
      } else {
        return [...prev, { ticker, shares, avgCost: price, totalInvestment: cost }];
      }
    });

    // Automatically add bought stock to compared stocks so it appears in analytics
    if (!comparedIds.includes(ticker)) {
      setComparedIds(prev => [...prev, ticker]);
    }
  };

  // Sell Simulator handler
  const handleSellStock = (ticker: string, shares: number) => {
    const existing = positions.find(p => p.ticker === ticker);
    if (!existing || existing.shares < shares) {
      alert("出售失败！持股数量不足。");
      return;
    }

    const targetStock = stocks.find(s => s.id === ticker);
    if (!targetStock) return;

    const proceeds = shares * targetStock.price;
    setCash(prev => prev + proceeds);

    setPositions(prev => {
      if (existing.shares === shares) {
        return prev.filter(p => p.ticker !== ticker);
      } else {
        const remainingShares = existing.shares - shares;
        // recalculating investment proportion
        const remainingInvestment = existing.totalInvestment * (remainingShares / existing.shares);
        return prev.map(p => p.ticker === ticker ? {
          ticker,
          shares: remainingShares,
          avgCost: existing.avgCost,
          totalInvestment: remainingInvestment
        } : p);
      }
    });
  };

  // Switch detail to a stock and view it in detail dashboard
  const handleSelectStock = (stock: Stock) => {
    setSelectedStockId(stock.id);
    setActiveTab('analysis'); // automatically transition to core single-stock analysis dashboard
  };

  const handleSelectStockById = (ticker: string) => {
    const stock = stocks.find(s => s.id === ticker);
    if (stock) {
      handleSelectStock(stock);
    } else {
      // If stock not found in loaded array, check pre-fills to dynamically load it
      alert(`无法在本地数据库中查找到 ${ticker} 的完整因子库。建议点击左侧 "新建分析" 按钮一键解算其完整模型！`);
    }
  };

  const handleWatchlistToggle = (id: string) => {
    setWatchlist(prev => 
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  // Add compared asset
  const handleAddCompared = (ticker: string) => {
    if (!comparedIds.includes(ticker)) {
      setComparedIds(prev => [...prev, ticker]);
    }
  };

  // Remove compared asset
  const handleRemoveCompared = (ticker: string) => {
    if (comparedIds.length > 2) {
      setComparedIds(prev => prev.filter(item => item !== ticker));
    } else {
      alert("由于至少需要2个资产进行多维交叉对标，当前已达下限不可删除。");
    }
  };

  // Add synthesized asset
  const handleNewAnalysisSuccess = (newStock: Stock) => {
    setStocks(prev => {
      // Avoid duplicated id
      if (prev.some(s => s.id === newStock.id)) {
        return prev.map(s => s.id === newStock.id ? newStock : s);
      }
      return [newStock, ...prev];
    });

    // Injects directly into compared ids line
    if (!comparedIds.includes(newStock.id)) {
      setComparedIds(prev => [...prev, newStock.id]);
    }

    setSelectedStockId(newStock.id); // set as active detail
    setActiveTab('analysis'); // route her to the detailed analysis tab!
    setIsNewAnalysisOpen(false); // close modal
  };

  return (
    <div className="bg-background text-on-background font-sans min-h-screen flex flex-col md:flex-row select-none">
      
      {/* Global Navigation Header (Standard top block height: 3rem / h-12) */}
      <Header 
        onSearch={setSearchQuery}
        onMobileToggle={handleMobileToggle}
        isMobileOpen={isMobileOpen}
        activeTab={activeTab}
        onChangeTab={setActiveTab}
        onNotificationClick={() => alert("系统消息 \n【多头氛围指数】由先前 81.5 上浮至 84.2，板块轮动向超前硬件制造聚拢。")}
        onSettingsClick={() => alert("系统配对状态 \n运行环境: Cloud Sandbox Container \nT+1结算机制: 开启 \n数据刷新周期: 实时流(无延迟)\n当前密钥状态: GEMINI_API_KEY 已注入")}
      />

      {/* Side Navigation panel */}
      <Sidebar 
        activeTab={activeTab}
        onChangeTab={setActiveTab}
        onNewAnalysisClick={() => setIsNewAnalysisOpen(true)}
        isMobileOpen={isMobileOpen}
        onMobileToggle={handleMobileToggle}
      />

      {/* Main Container Viewport (Displaced with sidebar 64 columns in large screen, and header 3rem margin top) */}
      <main className="flex-1 md:ml-64 mt-12 p-margin-mobile md:p-margin-desktop overflow-y-auto max-w-full">
        {activeTab === 'market' && (
          <MarketRanking 
            stocks={stocks}
            searchQuery={searchQuery}
            onSelectStock={handleSelectStock}
          />
        )}

        {activeTab === 'comparison' && (
          <MultiAssetComparison 
            stocks={stocks}
            comparedIds={comparedIds}
            onAddCompared={handleAddCompared}
            onRemoveCompared={handleRemoveCompared}
            onSelectStock={handleSelectStock}
          />
        )}

        {activeTab === 'logs' && (
          <ResearchLogs 
            logs={RESEARCH_LOGS}
            onSelectStockById={handleSelectStockById}
          />
        )}

        {activeTab === 'analysis' && (
          <StockDetailAnalysis 
            selectedStock={selectedStock}
            stocks={stocks}
            onSelectStock={(s) => setSelectedStockId(s.id)}
            onTradeClick={(s) => {
              // Buy stock directly from detail trigger (takes users directly to simulated portfolio buy pane!)
              setActiveTab('portfolio');
            }}
            onWatchlistToggle={handleWatchlistToggle}
            isWatchlisted={watchlist.includes(selectedStock.id)}
          />
        )}

        {activeTab === 'portfolio' && (
          <Portfolio
            stocks={stocks}
            positions={positions}
            cash={cash}
            onBuy={handleBuyStock}
            onSell={handleSellStock}
          />
        )}

        {activeTab === 'chat' && (
          <AIChatPage
            stocks={stocks}
            onSelectStock={handleSelectStock}
          />
        )}
      </main>

      {/* New Analysis pop-up popup Modal */}
      {isNewAnalysisOpen && (
        <NewAnalysisModal 
          onClose={() => setIsNewAnalysisOpen(false)}
          onAnalysisSuccess={handleNewAnalysisSuccess}
        />
      )}
    </div>
  );
}
