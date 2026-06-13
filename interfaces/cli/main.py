"""命令行接口"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.engine.kernel import Kernel


def main():
    """命令行入口"""
    kernel = Kernel()
    result = kernel.run()
    
    print(f"\n市场状态: {result['regime']}")
    print(f"使用策略: {result['strategy']}")
    print(f"\n候选股票 ({len(result['candidates'])} 只):")
    
    for i, stock in enumerate(result['candidates'], 1):
        print(f"{i}. {stock.get('name', '')} ({stock.get('code', '')}) - 评分: {stock.get('total_score', 0):.0f}")
    
    print(f"\n研究报告已生成 {len(result['reports'])} 份")


if __name__ == '__main__':
    main()
