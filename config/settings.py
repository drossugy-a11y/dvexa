"""全局配置"""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM 配置
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")

# 数据配置
DB_PATH = os.getenv("DB_PATH", "cache.db")
REQUEST_INTERVAL = 0.5
CACHE_EXPIRE_HOURS = 24

# 五维评分权重
WEIGHT_GROWTH = 0.25
WEIGHT_PROFITABILITY = 0.25
WEIGHT_VALUATION = 0.20
WEIGHT_HEALTH = 0.15
WEIGHT_QUALITY = 0.15

# 筛选阈值
DEFAULT_TOP_N = 10
MIN_MARKET_CAP_YI = 50
MIN_TURNOVER = 0.5
