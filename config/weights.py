"""因子权重配置"""

# 默认权重
DEFAULT_WEIGHTS = {
    'growth': 0.25,
    'profitability': 0.25,
    'valuation': 0.20,
    'health': 0.15,
    'quality': 0.15
}

# 牛市权重
BULL_WEIGHTS = {
    'momentum': 0.35,
    'trend': 0.25,
    'growth': 0.20,
    'valuation': 0.10,
    'quality': 0.10
}

# 熊市权重
BEAR_WEIGHTS = {
    'valuation': 0.35,
    'quality': 0.30,
    'health': 0.20,
    'momentum': 0.10,
    'trend': 0.05
}
