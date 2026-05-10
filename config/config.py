import os
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

MAX_STEPS = 5
PLAN_TEMPERATURE = 0.1


def validate_config() -> list[str]:
    """验证配置完整性，返回缺失项列表。"""
    missing = []
    if not LLM_API_KEY:
        missing.append("LLM_API_KEY")
    if not LLM_BASE_URL:
        missing.append("LLM_BASE_URL")
    if not LLM_MODEL:
        missing.append("LLM_MODEL")
    return missing
