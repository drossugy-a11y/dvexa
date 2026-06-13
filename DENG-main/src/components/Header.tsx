/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { Search, Bell, Settings, User, Menu, X } from 'lucide-react';
import { Tab } from '../types';

interface HeaderProps {
  onSearch: (query: string) => void;
  onMobileToggle: () => void;
  isMobileOpen: boolean;
  activeTab: Tab;
  onChangeTab: (tab: Tab) => void;
  onNotificationClick: () => void;
  onSettingsClick: () => void;
}

export default function Header({
  onSearch,
  onMobileToggle,
  isMobileOpen,
  activeTab,
  onChangeTab,
  onNotificationClick,
  onSettingsClick
}: HeaderProps) {
  return (
    <header className="bg-surface-container-low border-b border-border fixed top-0 w-full h-12 flex justify-between items-center px-container-padding z-55">
      {/* Drawer Toggle & Ticker brand */}
      <div className="flex items-center gap-4 md:gap-6">
        <button 
          id="mobile-sidebar-toggle"
          className="md:hidden text-text-secondary hover:text-text-primary transition-colors p-1"
          onClick={onMobileToggle}
          aria-label="Toggle navigation"
        >
          {isMobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
        
        <span 
          id="brand-logo"
          onClick={() => onChangeTab('market')}
          className="text-lg font-serif font-semibold uppercase tracking-widest text-primary cursor-pointer hover:opacity-90 select-none flex items-center gap-1.5"
        >
          DVexa
          <span className="text-[9px] bg-primary/10 text-primary border border-primary/20 px-1.5 py-0.5 rounded-sm font-sans tracking-normal uppercase font-medium">Terminal v2.1</span>
        </span>
        
        {/* Horizontal Navigation Categories on Web View */}
        <nav className="hidden md:flex items-center space-x-5 h-full pt-0.5">
          <button 
            onClick={() => onChangeTab('market')}
            className={`text-xs py-1 transition-all border-b-2 font-medium ${
              activeTab === 'market' 
                ? 'text-primary-container border-primary-container opacity-100' 
                : 'text-text-secondary hover:text-text-primary border-transparent opacity-80'
            }`}
          >
            市场
          </button>
          <button 
            onClick={() => onChangeTab('comparison')}
            className={`text-xs py-1 transition-all border-b-2 font-medium ${
              activeTab === 'comparison' 
                ? 'text-primary-container border-primary-container opacity-100' 
                : 'text-text-secondary hover:text-text-primary border-transparent opacity-80'
            }`}
          >
            板块对比
          </button>
          <button 
            onClick={() => onChangeTab('logs')}
            className={`text-xs py-1 transition-all border-b-2 font-medium ${
              activeTab === 'logs' 
                ? 'text-primary-container border-primary-container opacity-100' 
                : 'text-text-secondary hover:text-text-primary border-transparent opacity-80'
            }`}
          >
            重要日志
          </button>
        </nav>
      </div>

      {/* Global Utilities */}
      <div className="flex items-center space-x-3.5">
        {/* Search Input block */}
        <div className="relative bg-surface border border-border/80 hover:border-text-tertiary focus-within:border-primary-container transition-colors rounded-sm px-2.5 py-1.2 flex items-center w-36 sm:w-48 md:w-56">
          <Search className="text-text-tertiary w-3.5 h-3.5 mr-2 shrink-0" />
          <input 
            id="global-search-input"
            type="text" 
            placeholder="搜索代码或名称..." 
            onChange={(e) => onSearch(e.target.value)}
            className="bg-transparent border-none outline-none text-xs font-sans text-text-primary placeholder-text-tertiary w-full focus:ring-0 p-0 leading-none h-3.5"
          />
        </div>

        {/* Dynamic Buttons */}
        <button 
          id="nav-bell"
          onClick={onNotificationClick}
          className="text-text-secondary hover:text-text-primary transition-colors cursor-pointer relative"
          title="系统通知"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-0 right-0 w-1.5 h-1.5 bg-error rounded-full" />
        </button>

        <button 
          id="nav-settings"
          onClick={onSettingsClick}
          className="text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
          title="配置面板"
        >
          <Settings className="w-4 h-4" />
        </button>

        <div 
          className="w-6 h-6 rounded-full bg-primary/10 border border-primary/25 flex items-center justify-center cursor-pointer hover:bg-primary/20 transition-colors"
          onClick={() => onChangeTab('portfolio')}
          title="我的投资主页"
        >
          <User className="w-3.5 h-3.5 text-primary" />
        </div>
      </div>
    </header>
  );
}
