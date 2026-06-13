/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { Tab } from '../types';
import { 
  BarChart3, 
  Sliders, 
  ScrollText, 
  Brain, 
  Wallet, 
  Plus, 
  Code, 
  HelpCircle,
  Menu,
  X
} from 'lucide-react';

interface SidebarProps {
  activeTab: Tab;
  onChangeTab: (tab: Tab) => void;
  onNewAnalysisClick: () => void;
  isMobileOpen: boolean;
  onMobileToggle: () => void;
  userEmail?: string;
}

export default function Sidebar({
  activeTab,
  onChangeTab,
  onNewAnalysisClick,
  isMobileOpen,
  onMobileToggle,
  userEmail = 'institutional@dvexa.com'
}: SidebarProps) {
  
  const menuItems = [
    {
      id: 'market' as Tab,
      nameZh: 'AI 评分榜',
      nameEn: 'AI Ranking',
      icon: BarChart3,
    },
    {
      id: 'comparison' as Tab,
      nameZh: '多资产对比',
      nameEn: 'Factor Scoring',
      icon: Sliders,
    },
    {
      id: 'logs' as Tab,
      nameZh: '研究日志',
      nameEn: 'Research Logs',
      icon: ScrollText,
    },
    {
      id: 'analysis' as Tab,
      nameZh: '分析 / 详情',
      nameEn: 'Analysis',
      icon: Brain,
    },
    {
      id: 'portfolio' as Tab,
      nameZh: '投资组合',
      nameEn: 'Portfolio',
      icon: Wallet,
    }
  ];

  return (
    <>
      {/* Mobile Sidebar overlay */}
      {isMobileOpen && (
        <div 
          className="fixed inset-0 bg-black/60 z-30 md:hidden backdrop-blur-xs transition-opacity"
          onClick={onMobileToggle}
        />
      )}

      {/* Main Sidebar Container */}
      <aside 
        id="sidebar"
        className={`fixed left-0 top-12 bottom-0 w-64 bg-surface-container-lowest border-r border-border shrink-0 z-40 flex flex-col transition-transform duration-300 md:translate-x-0 ${
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* User Identity Box */}
        <div className="p-container-padding flex items-center gap-3 border-b border-border/80">
          <div className="w-8 h-8 rounded-full bg-primary-container/20 flex items-center justify-center text-primary font-bold text-sm">
            {userEmail[0].toUpperCase()}
          </div>
          <div className="min-w-0">
            <h3 className="text-label-mono font-medium text-text-primary text-xs truncate">DVexa Terminal</h3>
            <p className="text-[10px] font-mono text-text-tertiary">Institutional Access</p>
          </div>
        </div>

        {/* New Analysis Trigger */}
        <div className="px-container-padding my-4">
          <button 
            id="new-analysis-btn"
            onClick={() => {
              onNewAnalysisClick();
              if (isMobileOpen) onMobileToggle();
            }}
            className="w-full bg-primary-container hover:bg-primary-container/90 text-on-primary-container rounded-sm font-sans font-medium text-sm py-2 px-3 flex items-center justify-center gap-2 transition-all active:scale-98 shadow-md"
          >
            <Plus className="w-4 h-4" />
            <span>新建分析</span>
          </button>
        </div>

        {/* Tab Links */}
        <nav className="flex-1 overflow-y-auto px-2 space-y-1 py-1">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                id={`sidebar-tab-${item.id}`}
                onClick={() => {
                  onChangeTab(item.id);
                  if (isMobileOpen) onMobileToggle();
                }}
                className={`w-full flex items-center gap-3 py-2 px-3 rounded-sm transition-all text-left ${
                  isActive 
                    ? 'bg-primary-container/10 text-primary-container border-r-2 border-primary-container scale-98 font-semibold' 
                    : 'text-text-secondary hover:text-text-primary hover:bg-surface-container-high'
                }`}
              >
                <Icon className={`w-[18px] h-[18px] ${isActive ? 'text-primary-container' : 'text-text-secondary'}`} />
                <div className="flex flex-col">
                  <span className="text-[13px] tracking-wide leading-normal">{item.nameZh}</span>
                  <span className="text-[10px] font-mono opacity-60 leading-none">{item.nameEn}</span>
                </div>
              </button>
            );
          })}
        </nav>

        {/* Footer info logs */}
        <div className="mt-auto border-t border-border/80 p-container-padding flex flex-col gap-2.5">
          <a 
            id="api-docs-link"
            href="#api-docs" 
            onClick={(e) => {
              e.preventDefault();
              alert("DVexa API \nInstitutional REST API: https://api.dvexa.com/v2/indicators \nRefer to API credentials in developer platform.");
            }}
            className="flex items-center gap-3 text-text-tertiary hover:text-text-secondary transition-colors text-xs font-mono"
          >
            <Code className="w-[15px] h-[15px]" />
            <span>API 文档</span>
          </a>
          <a 
            id="help-link"
            href="#help" 
            onClick={(e) => {
              e.preventDefault();
              alert("帮助中心 \n如有数据延迟或模型评分疑问，请联系: quant-support@dvexa.com");
            }}
            className="flex items-center gap-3 text-text-tertiary hover:text-text-secondary transition-colors text-xs font-mono"
          >
            <HelpCircle className="w-[15px] h-[15px]" />
            <span>帮助中心</span>
          </a>
        </div>
      </aside>
    </>
  );
}
