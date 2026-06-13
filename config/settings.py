"""全局配置"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM 配置 ──────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")

# 自动设置 base_url（如果未指定）
if not LLM_BASE_URL:
    if LLM_PROVIDER == "deepseek":
        LLM_BASE_URL = "https://api.deepseek.com"
    elif LLM_PROVIDER == "dashscope":
        LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    else:
        LLM_BASE_URL = "https://api.openai.com/v1"

# ── 数据配置 ──────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "cache.db")
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "data/dvexa_memory.db")
REQUEST_INTERVAL = 0.5
CACHE_EXPIRE_HOURS = 24

# ── 五维评分权重 ──────────────────────────────────────
WEIGHT_GROWTH = 0.25
WEIGHT_PROFITABILITY = 0.25
WEIGHT_VALUATION = 0.20
WEIGHT_HEALTH = 0.15
WEIGHT_QUALITY = 0.15

# ── 筛选阈值 ──────────────────────────────────────────
DEFAULT_TOP_N = 10
MIN_MARKET_CAP_YI = 50
MIN_TURNOVER = 0.5

# ── TradingAgents-CN 配置 ─────────────────────────────
TA_DEPTH = int(os.getenv("TA_DEPTH", "3"))
TA_MARKET = os.getenv("TA_MARKET", "A")

# ── 通知配置 ──────────────────────────────────────────
NOTIFY_CHANNEL = os.getenv("NOTIFY_CHANNEL", "console")  # telegram / wechat / console
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
WECHAT_WEBHOOK_URL = os.getenv("WECHAT_WEBHOOK_URL", "")

# ── 调度配置 ──────────────────────────────────────────
SCAN_HOUR = int(os.getenv("SCAN_HOUR", "15"))
SCAN_MINUTE = int(os.getenv("SCAN_MINUTE", "30"))
