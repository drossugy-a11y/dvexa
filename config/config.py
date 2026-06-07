"""Stock Agent 配置管理。"""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM 配置
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")

# 数据库
DB_PATH = os.getenv("DB_PATH", "data/stock.db")

# akshare 缓存
CACHE_DIR = os.getenv("CACHE_DIR", "data/cache")
CACHE_EXPIRE_HOURS = int(os.getenv("CACHE_EXPIRE_HOURS", "24"))

# 分析默认参数
DEFAULT_ANALYSIS_YEARS = int(os.getenv("DEFAULT_ANALYSIS_YEARS", "5"))
DEFAULT_STRATEGY = os.getenv("DEFAULT_STRATEGY", "comprehensive")

# 事件存储
EVENT_STORE_PATH = os.getenv("EVENT_STORE_PATH", "data/events.jsonl")


def validate_config() -> list[str]:
    missing = []
    if not LLM_API_KEY:
        missing.append("LLM_API_KEY")
    return missing
